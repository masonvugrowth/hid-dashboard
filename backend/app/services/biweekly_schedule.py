"""Sending each branch's Bi-Weekly report on its own, on the day it closes.

The manual path (`POST /biweekly/send`) already does the hard part: build the
period, mint the no-login link, render the digest, email one message per
recipient. This module answers a different question — *whether today is the
day* — and then walks the saved schedules through that same path.

Two rules shape everything here.

**A report is only ever sent for a period that has finished.** The send days
are stored as bounded integers (15–28 for the 1st–14th half, 1–14 of the NEXT
month for the 15th–EOM half), so "what period is due today" is a lookup, not
an interpretation, and it cannot resolve to a period still running. The job
re-checks `is_complete` anyway, because a check constraint added later is a
promise about new rows, not about the ones already in the table.

**A missed send is caught up; a sent one is never repeated.** The runner ticks
every 15 minutes, which means the interesting case is not the happy one — it
is the redeploy at 08:00, the database blip, the two workers that both wake up
at :00. `last_sent_period_key` is what decides, it is read under
`SELECT FOR UPDATE`, and it is written in the same transaction as the send.
Everything else in this file is arrangement around that one column.

The catch-up window is deliberately short. A fortnightly report that arrives
three days late is late; one that arrives three weeks late is describing a
period the reader has already moved past, and quietly emailing it makes the
dashboard look like it lost track of time rather than that it recovered.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from app.services.biweekly_period import (
    Period,
    is_complete,
    period_for,
    previous_period,
)
from app.services.report_common import ICT_TZ

logger = logging.getLogger(__name__)

#: Defaults: 08:00 ICT on the 15th (for 1-14) and on the 1st (for 15-EOM).
DEFAULT_SEND_DAY_H1 = 15
DEFAULT_SEND_DAY_H2 = 1
DEFAULT_HOUR = 8
DEFAULT_MINUTE = 0

#: Bounds enforced in the DB too (see migration 062). Repeated here so the API
#: can reject a bad value with a sentence instead of an IntegrityError, and so
#: this module needs no ORM import to do its arithmetic.
DAY_H1_RANGE = (15, 28)
DAY_H2_RANGE = (1, 14)

#: A send missed by an outage is still worth making. Beyond this many days
#: late it stops being a report and starts being an artefact - the period is
#: half a month gone and the next one is already being read.
CATCH_UP_DAYS = 3


def period_due_on(day: date, day_h1: int, day_h2: int) -> Optional[Period]:
    """The period whose scheduled send date is exactly `day`, if any.

    `day_h1` names a day in the period's OWN month; `day_h2` names a day in
    the month AFTER the period's. Both windows are bounded so the period is
    always over by the time its date comes round — which is why this returns
    a finished period or nothing, never one still running.
    """
    if day.day == day_h1:
        return period_for(day.year, day.month, 1)
    if day.day == day_h2:
        # The 15th–EOM half of the month before this one.
        return previous_period(period_for(day.year, day.month, 1))
    return None


def due_period(now_ict: datetime, day_h1: int, day_h2: int,
               last_sent_period_key: Optional[str] = None,
               catch_up_days: int = CATCH_UP_DAYS) -> Optional[Period]:
    """The period this schedule owes an email for, ignoring the time of day.

    Walks backwards from today to `catch_up_days` ago and returns the most
    recent scheduled send that has not happened yet.

    `last_sent_period_key` short-circuits the walk rather than being checked
    afterwards: without it, a schedule sent on the 15th would keep matching
    the 15th's entry for three more days and hand the caller a period it has
    already emailed.
    """
    today = now_ict.date()
    for offset in range(catch_up_days + 1):
        day = today - timedelta(days=offset)
        p = period_due_on(day, day_h1, day_h2)
        if p is None:
            continue
        if last_sent_period_key and p.key == last_sent_period_key:
            # Already gone out. Anything behind it is older still, so there is
            # nothing left to catch up on.
            return None
        if not is_complete(p, today):
            continue
        return p
    return None


def is_due(now_ict: datetime, sched) -> Optional[Period]:
    """What a stored schedule owes right now, with today's send held back.

    Today's own entry waits for the configured hour. An entry from an earlier
    day does not: its hour went by while the service was down, and holding it
    until tomorrow morning would not make it more punctual.
    """
    p = due_period(now_ict, sched.send_day_h1, sched.send_day_h2,
                   sched.last_sent_period_key)
    if p is None:
        return None
    today_entry = period_due_on(now_ict.date(), sched.send_day_h1,
                                sched.send_day_h2)
    if today_entry is not None and today_entry.key == p.key:
        if (now_ict.hour, now_ict.minute) < (sched.hour, sched.minute):
            return None
    return p


def next_send_at(now_ict: datetime, day_h1: int, day_h2: int,
                 hour: int, minute: int) -> datetime:
    """When this schedule fires next — what the UI prints.

    Scans forward day by day rather than reasoning about month lengths: the
    send days are two fixed day-numbers, so the first day ahead that matches
    one of them is the answer, and February needs no special case. Today
    counts only if its hour has not passed yet.
    """
    today = now_ict.date()
    for offset in range(0, 40):
        day = today + timedelta(days=offset)
        if day.day not in (day_h1, day_h2):
            continue
        when = datetime(day.year, day.month, day.day, hour, minute,
                        tzinfo=ICT_TZ)
        if when > now_ict:
            return when
    # Unreachable: any two day-numbers in 1–28 recur within 31 days.
    return now_ict


# ── The job ──────────────────────────────────────────────────────────────────


def run_due_schedules(session_factory) -> dict:
    """Send every schedule that is due. Called by APScheduler every 15 min.

    One transaction per branch, and the row is locked for the whole of it, so
    a tick that overlaps the previous one (or a second worker) blocks on the
    lock and then reads a `last_sent_period_key` that already names the period
    it was about to send.

    Returns a small summary for the logs and for the manual "run now" endpoint.
    A branch that raises is logged and skipped — four branches' reports should
    not be lost because the fifth has no data this period.
    """
    # Imported here, not at module scope: the router imports services, so a
    # top-level import back the other way would be a cycle. The report helpers
    # genuinely live in the router today (see biweekly_report.py) and moving
    # them is a larger change than this feature warrants.
    from app.models.biweekly_report_schedule import BiweeklyReportSchedule
    from app.routers.biweekly_report import send_scheduled_report

    now_ict = datetime.now(ICT_TZ)
    summary: dict = {"checked": 0, "sent": [], "skipped": [], "errors": []}

    db = session_factory()
    try:
        rows = (
            db.query(BiweeklyReportSchedule.branch_id)
            .filter(BiweeklyReportSchedule.is_enabled == True)  # noqa: E712
            .all()
        )
        branch_ids = [r[0] for r in rows]
    except Exception:
        # Zeabur does not run Alembic on deploy (POST /api/sync/run-migrations
        # does). Between this code landing and the migration being applied the
        # table is absent, and that must be a quiet no-op rather than an
        # exception every 15 minutes.
        logger.warning(
            "biweekly schedules unavailable — auto-send idle. Has migration "
            "062 been applied?", exc_info=True,
        )
        db.rollback()
        db.close()
        return summary
    finally:
        db.close()

    for branch_id in branch_ids:
        summary["checked"] += 1
        db = session_factory()
        try:
            sched = (
                db.query(BiweeklyReportSchedule)
                .filter(BiweeklyReportSchedule.branch_id == branch_id)
                .with_for_update()
                .first()
            )
            if sched is None or not sched.is_enabled:
                db.rollback()
                continue
            p = is_due(now_ict, sched)
            if p is None:
                db.rollback()
                summary["skipped"].append(str(branch_id))
                continue

            result = send_scheduled_report(db, sched, p)
            sched.last_sent_period_key = p.key
            sched.last_sent_at = datetime.now(ICT_TZ)
            sched.last_sent_to = result.get("sent_to") or []
            sched.last_failed = result.get("failed") or []
            sched.last_error = result.get("error")
            db.commit()

            if result.get("sent_to"):
                summary["sent"].append({
                    "branch_id": str(branch_id), "period": p.key,
                    "sent_to": result["sent_to"],
                    "failed": result.get("failed") or [],
                })
                logger.info(
                    "biweekly auto-send: %s %s -> %s (failed: %s)",
                    branch_id, p.key, result["sent_to"],
                    result.get("failed") or [],
                )
            else:
                summary["errors"].append({
                    "branch_id": str(branch_id), "period": p.key,
                    "error": result.get("error") or "reached nobody",
                })
                logger.error(
                    "biweekly auto-send reached nobody for %s %s: %s",
                    branch_id, p.key, result.get("error"),
                )
        except Exception as e:
            # The period is marked sent only on the happy path above, so a
            # branch that blew up here is retried on the next tick and, if the
            # cause outlasts the catch-up window, is visibly missing rather
            # than silently marked done.
            db.rollback()
            summary["errors"].append({"branch_id": str(branch_id),
                                      "error": str(e)})
            logger.exception("biweekly auto-send failed for branch %s", branch_id)
        finally:
            db.close()

    return summary
