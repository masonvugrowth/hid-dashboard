"""
Weekly Report router
- GET  /report/weekly       → report data (JSON)
- GET  /report/preview      → HTML email preview (for iframe)
- POST /report/send-weekly  → generate + send email to team
- GET  /report/schedule     → current email schedule config
- PATCH /report/schedule    → update email schedule
"""
import calendar
import json
import logging
import smtplib
import textwrap
from datetime import datetime, date, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.branch import Branch
from app.models.daily_metrics import DailyMetrics
from app.models.kpi import KPITarget
from app.models.reservation import Reservation
from app.services.cloudbeds import sync_cloudbeds_occupancy
from app.services.country_scorer import score_countries
from app.services.kpi_engine import (
    compute_kpi_summary,
    compute_next_month_forecast,
    _EXCLUDED_STATUSES,
    _EXCLUDED_SOURCES,
)

router = APIRouter()

MONTHS_EN = ["", "January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]


def _envelope(data):
    return {"success": True, "data": data, "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat()}


def _fmt(val, currency=""):
    if val is None:
        return "—"
    sym = {"VND": "₫", "TWD": "NT$", "JPY": "¥"}.get(currency, currency + " ")
    if abs(val) >= 1_000_000_000:
        return f"{sym}{val/1_000_000_000:.1f}B"
    if abs(val) >= 1_000_000:
        return f"{sym}{val/1_000_000:.1f}M"
    return f"{sym}{round(val):,}"


def _pct(val):
    return f"{round(val)}%" if val is not None else "—"


def _top_countries(db: Session, branch_id, days: int = 90, limit: int = 5):
    cutoff = date.today() - timedelta(days=days)
    rows = (
        db.query(
            Reservation.guest_country,
            func.count(Reservation.id).label("cnt"),
        )
        .filter(
            Reservation.branch_id == branch_id,
            Reservation.check_in_date >= cutoff,
            Reservation.guest_country.isnot(None),
            ~func.lower(func.coalesce(Reservation.guest_country, "")).contains("unknown"),
            or_(
                Reservation.status == None,
                Reservation.status.notin_(list(_EXCLUDED_STATUSES)),
            ),
        )
        .group_by(Reservation.guest_country)
        .order_by(func.count(Reservation.id).desc())
        .limit(limit)
        .all()
    )
    return [{"country": r.guest_country, "bookings": r.cnt} for r in rows]


def _growth_countries(db: Session, branch_id, limit: int = 3):
    """Top countries with biggest booking growth (90d vs prior 90d)."""
    today = date.today()
    recent_start = today - timedelta(days=90)
    prev_start = today - timedelta(days=180)

    recent = {
        r.guest_country: r.cnt
        for r in db.query(
            Reservation.guest_country,
            func.count(Reservation.id).label("cnt"),
        ).filter(
            Reservation.branch_id == branch_id,
            Reservation.check_in_date >= recent_start,
            Reservation.guest_country.isnot(None),
            ~func.lower(func.coalesce(Reservation.guest_country, "")).contains("unknown"),
            or_(Reservation.status == None,
                Reservation.status.notin_(list(_EXCLUDED_STATUSES))),
        ).group_by(Reservation.guest_country).all()
    }

    prev = {
        r.guest_country: r.cnt
        for r in db.query(
            Reservation.guest_country,
            func.count(Reservation.id).label("cnt"),
        ).filter(
            Reservation.branch_id == branch_id,
            Reservation.check_in_date >= prev_start,
            Reservation.check_in_date < recent_start,
            Reservation.guest_country.isnot(None),
            ~func.lower(func.coalesce(Reservation.guest_country, "")).contains("unknown"),
            or_(Reservation.status == None,
                Reservation.status.notin_(list(_EXCLUDED_STATUSES))),
        ).group_by(Reservation.guest_country).all()
    }

    results = []
    for country, rec_cnt in recent.items():
        if rec_cnt < 2:
            continue
        prv_cnt = prev.get(country, 0)
        if prv_cnt == 0:
            continue
        growth = round((rec_cnt - prv_cnt) / prv_cnt * 100, 1)
        if growth > 0:
            results.append({"country": country, "recent": rec_cnt,
                            "prev": prv_cnt, "growth_pct": growth})

    results.sort(key=lambda x: x["growth_pct"], reverse=True)
    return results[:limit]


def _actual_occ_pct(db: Session, branch_id, year: int, month: int, total_rooms: int) -> Optional[float]:
    """Compute actual average OCC% from daily_metrics for the month (up to today)."""
    if total_rooms <= 0:
        return None
    first_day = date(year, month, 1)
    today = date.today()
    last_day = min(today, date(year, month, calendar.monthrange(year, month)[1]))
    row = db.query(
        func.avg(DailyMetrics.occ_pct),
    ).filter(
        DailyMetrics.branch_id == branch_id,
        DailyMetrics.date >= first_day,
        DailyMetrics.date <= last_day,
    ).scalar()
    return float(row) if row else None


def _sync_fresh_insights(db: Session, branches):
    """Pull latest Cloudbeds Insights data into daily_metrics before report.

    Always syncs the FULL current month (1st → last day) to ensure
    revenue_native in daily_metrics matches the Cloudbeds dashboard exactly.
    """
    import logging
    logger = logging.getLogger(__name__)
    today = date.today()
    month_start = today.replace(day=1)
    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])

    for b in branches:
        pid = b.cloudbeds_property_id
        if not pid:
            continue
        api_key = settings.get_api_key_for_property(str(pid))
        if not api_key:
            continue
        try:
            sync_cloudbeds_occupancy(
                db, str(b.id), pid, b.currency, api_key,
                date_from=month_start, date_to=month_end,
            )
            db.flush()  # ensure fresh data is visible to subsequent queries
            logger.info("Report pre-sync OK branch=%s [%s..%s]", b.name, month_start, month_end)
        except Exception as e:
            logger.warning("Report pre-sync FAIL branch=%s: %s", b.name, e)


def _build_report(db: Session):
    today = date.today()
    branches = db.query(Branch).filter_by(is_active=True).all()
    report = []

    # Sync fresh Cloudbeds Insights before building report
    _sync_fresh_insights(db, branches)

    for b in branches:
        total_rooms = b.total_rooms or 0
        kpi = compute_kpi_summary(db, b.id, today.year, today.month, total_rooms)
        nxt = compute_next_month_forecast(db, b.id, total_rooms, today.year, today.month)
        top = _top_countries(db, b.id)
        growth = _growth_countries(db, b.id)

        # Country Intel scores (Hot / Warm / Cold)
        country_intel = score_countries(db, branch_id=b.id, top_n=10)

        # Actual OCC from daily_metrics
        actual_occ = _actual_occ_pct(db, b.id, today.year, today.month, total_rooms)

        # Predicted/forecast OCC from KPI targets
        predicted_occ_current = kpi.get("predicted_occ_pct")
        predicted_occ_next = nxt.get("predicted_occ_next")

        report.append({
            "branch_id": str(b.id),
            "branch_name": b.name,
            "branch_city": b.city,
            "currency": b.currency,
            # This month
            "actual_revenue": kpi["actual_revenue_native"],
            "target_revenue": kpi["target_revenue_native"],
            "achievement_pct": round(kpi["achievement_pct"] * 100, 1) if kpi["achievement_pct"] else None,
            "avg_adr": kpi["avg_adr_native"],
            "avg_occ_pct": round(actual_occ * 100, 1) if actual_occ else None,
            "predicted_occ_pct": round(predicted_occ_current * 100, 1) if predicted_occ_current else None,
            "days_elapsed": kpi["days_elapsed"],
            "total_days": kpi["total_days"],
            "occ_forecast": kpi["occ_forecast_native"],
            "occ_forecast_pct": round(kpi["occ_forecast_native"] / kpi["target_revenue_native"] * 100, 1)
                if (kpi["occ_forecast_native"] and kpi["target_revenue_native"]) else None,
            # Next month
            "next_month": nxt["next_month"],
            "next_year": nxt["next_year"],
            "next_forecast": nxt["next_month_forecast_native"],
            "next_target": nxt["next_month_target_native"],
            "next_forecast_pct": round(nxt["next_month_forecast_native"] / nxt["next_month_target_native"] * 100, 1)
                if (nxt["next_month_forecast_native"] and nxt["next_month_target_native"]) else None,
            "next_adr": nxt["next_month_adr"],
            "next_booked_nights": nxt["next_month_booked_nights"],
            "predicted_occ_next": round(predicted_occ_next * 100, 1) if predicted_occ_next else None,
            # Country intel
            "top_countries": top,
            "growth_countries": growth,
            "country_intel": country_intel,
        })

    return report


def _build_html(report: list, today: date) -> str:
    month_name = MONTHS_EN[today.month]
    next_month_name = MONTHS_EN[today.month % 12 + 1]

    sections = []
    next_actions_all = []

    for b in report:
        cur = b["currency"]
        ach = b["achievement_pct"]
        ach_color = "#16a34a" if ach and ach >= 100 else "#ca8a04" if ach and ach >= 80 else "#dc2626"
        ach_str = f"{ach}%" if ach else "—"

        # Country intel next actions — driven by country_scorer tiers
        actions = []
        intel = b.get("country_intel", [])
        hot_countries = [c for c in intel if c["tier"] == "Hot"]
        warm_countries = [c for c in intel if c["tier"] == "Warm"]
        cold_countries = [c for c in intel if c["tier"] == "Cold"]

        for c in hot_countries[:3]:
            wow = f" (WoW {c['wow_growth_pct']:+.0f}%)" if c.get("wow_growth_pct") is not None else ""
            actions.append(
                f"🔥 {c['country']} — Hot (score {c['score']}){wow} — scale ad spend & prioritize OTA rates"
            )
        for c in warm_countries[:2]:
            actions.append(
                f"📈 {c['country']} — Warm (score {c['score']}) — test new ad creatives & increase visibility"
            )
        for c in cold_countries[:1]:
            if c.get("booking_count_this_week", 0) > 0:
                actions.append(
                    f"❄️ {c['country']} — Cold (score {c['score']}) — review content relevance & consider pausing low-ROAS ads"
                )

        if not b["occ_forecast"]:
            actions.append("⚠️ Predicted OCC% not set — go to KPI Dashboard to input")
        if b["achievement_pct"] and b["achievement_pct"] < 80:
            actions.append(f"🔴 KPI at {ach_str} — review pricing and promotions")

        next_actions_all.append({
            "branch": b["branch_name"],
            "city": b["branch_city"],
            "actions": actions,
        })

        top_c = " · ".join(f"{c['country']} ({c['bookings']})" for c in b["top_countries"][:3])
        growth_c = " · ".join(
            f"{g['country']} <span style='color:#16a34a'>▲{g['growth_pct']}%</span>"
            for g in b["growth_countries"][:3]
        ) or "—"

        # Country Intel tier summary
        tier_colors = {"Hot": "#dc2626", "Warm": "#f59e0b", "Cold": "#6b7280"}
        intel_c = " · ".join(
            f"<span style='color:{tier_colors.get(c['tier'], '#6b7280')};font-weight:600;'>"
            f"{c['country']} ({c['tier']} {c['score']})</span>"
            for c in intel[:5]
        ) or "—"

        sections.append(f"""
        <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
            <div>
              <h3 style="margin:0;font-size:16px;font-weight:700;color:#111827;">{b['branch_name']}</h3>
              <p style="margin:2px 0 0;font-size:12px;color:#6b7280;">{b['branch_city']} · {cur}</p>
            </div>
            <span style="background:#f3f4f6;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:700;color:{ach_color};">
              {ach_str} of target
            </span>
          </div>

          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <tr style="background:#f9fafb;">
              <th style="padding:8px 12px;text-align:left;color:#6b7280;font-weight:500;font-size:11px;text-transform:uppercase;">Metric</th>
              <th style="padding:8px 12px;text-align:right;color:#6b7280;font-weight:500;font-size:11px;text-transform:uppercase;">{month_name} (MTD {b['days_elapsed']}/{b['total_days']}d)</th>
              <th style="padding:8px 12px;text-align:right;color:#6b7280;font-weight:500;font-size:11px;text-transform:uppercase;">{next_month_name}</th>
            </tr>
            <tr style="border-top:1px solid #f3f4f6;">
              <td style="padding:8px 12px;color:#374151;">Revenue</td>
              <td style="padding:8px 12px;text-align:right;font-weight:600;color:#111827;">{_fmt(b['actual_revenue'], cur)}</td>
              <td style="padding:8px 12px;text-align:right;color:#6b7280;">booked: {_fmt(b.get('next_booked_nights'), '')} nights</td>
            </tr>
            <tr style="border-top:1px solid #f3f4f6;background:#f9fafb;">
              <td style="padding:8px 12px;color:#374151;">Target</td>
              <td style="padding:8px 12px;text-align:right;color:#6b7280;">{_fmt(b['target_revenue'], cur)}</td>
              <td style="padding:8px 12px;text-align:right;color:#6b7280;">{_fmt(b['next_target'], cur)}</td>
            </tr>
            <tr style="border-top:1px solid #f3f4f6;">
              <td style="padding:8px 12px;color:#374151;">ADR</td>
              <td style="padding:8px 12px;text-align:right;font-weight:600;color:#111827;">{_fmt(b['avg_adr'], cur)}</td>
              <td style="padding:8px 12px;text-align:right;font-weight:600;color:#111827;">{_fmt(b['next_adr'], cur)}</td>
            </tr>
            <tr style="border-top:1px solid #f3f4f6;background:#f9fafb;">
              <td style="padding:8px 12px;color:#374151;">OCC% (actual)</td>
              <td style="padding:8px 12px;text-align:right;font-weight:600;color:#111827;">{_pct(b['avg_occ_pct'])}</td>
              <td style="padding:8px 12px;text-align:right;color:#6b7280;">—</td>
            </tr>
            <tr style="border-top:1px solid #f3f4f6;">
              <td style="padding:8px 12px;color:#374151;">OCC% (forecast)</td>
              <td style="padding:8px 12px;text-align:right;font-weight:600;color:#4f46e5;">{_pct(b['predicted_occ_pct'])}</td>
              <td style="padding:8px 12px;text-align:right;font-weight:600;color:#059669;">{_pct(b['predicted_occ_next'])}</td>
            </tr>
            <tr style="border-top:1px solid #f3f4f6;">
              <td style="padding:8px 12px;color:#374151;font-weight:600;">Forecast</td>
              <td style="padding:8px 12px;text-align:right;font-weight:700;color:#4f46e5;">
                {_fmt(b['occ_forecast'], cur)}
                {f"<span style='font-weight:400;color:#6b7280;'> ({b['occ_forecast_pct']}%)</span>" if b['occ_forecast_pct'] else ""}
              </td>
              <td style="padding:8px 12px;text-align:right;font-weight:700;color:#059669;">
                {_fmt(b['next_forecast'], cur)}
                {f"<span style='font-weight:400;color:#6b7280;'> ({b['next_forecast_pct']}%)</span>" if b['next_forecast_pct'] else ""}
              </td>
            </tr>
          </table>

          <div style="margin-top:14px;padding-top:12px;border-top:1px solid #f3f4f6;font-size:12px;color:#6b7280;">
            <strong style="color:#374151;">Top markets (90d):</strong> {top_c or '—'}<br/>
            <strong style="color:#374151;">Growing markets:</strong> {growth_c}<br/>
            <strong style="color:#374151;">Country Intel:</strong> {intel_c}
          </div>
        </div>""")

    # Next actions section
    action_html = ""
    for na in next_actions_all:
        if not na["actions"]:
            continue
        items = "".join(f"<li style='margin:4px 0;'>{a}</li>" for a in na["actions"])
        action_html += f"""
        <div style="margin-bottom:12px;">
          <strong style="font-size:13px;color:#374151;">{na['branch']} — {na['city']}</strong>
          <ul style="margin:6px 0 0;padding-left:20px;color:#374151;font-size:13px;">{items}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f3f4f6;margin:0;padding:24px;">
  <div style="max-width:680px;margin:0 auto;">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:12px;padding:24px;margin-bottom:20px;color:#fff;">
      <h1 style="margin:0;font-size:22px;font-weight:700;">HiD Weekly Report</h1>
      <p style="margin:6px 0 0;opacity:0.85;font-size:14px;">
        {today.strftime('%A, %d %B %Y')} · {month_name} {today.year}
      </p>
    </div>

    <!-- Branch sections -->
    {''.join(sections)}

    <!-- Next Actions -->
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;margin-bottom:16px;">
      <h3 style="margin:0 0 14px;font-size:15px;font-weight:700;color:#111827;">🎯 Next Actions</h3>
      {action_html or '<p style="color:#6b7280;font-size:13px;">No actions required this week.</p>'}
    </div>

    <!-- Footer -->
    <p style="text-align:center;font-size:11px;color:#9ca3af;margin-top:16px;">
      Generated by HiD Dashboard · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
    </p>
  </div>
</body>
</html>"""


@router.get("/weekly")
def weekly_report(db: Session = Depends(get_db)):
    """Return weekly report data as JSON."""
    today = date.today()
    report = _build_report(db)
    return _envelope({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "month": today.month,
        "year": today.year,
        "branches": report,
    })


@router.post("/send-weekly")
def send_weekly_email(to: Optional[str] = None, db: Session = Depends(get_db)):
    """Generate and send weekly HTML email via Gmail SMTP.
    Pass ?to=email@example.com to override recipients (useful for testing)."""
    gmail_user = getattr(settings, "GMAIL_USER", "") or ""
    gmail_pass = getattr(settings, "GMAIL_APP_PASSWORD", "") or ""
    recipients_raw = getattr(settings, "EMAIL_RECIPIENTS", "") or ""

    if not gmail_user or not gmail_pass:
        raise HTTPException(
            status_code=500,
            detail="GMAIL_USER and GMAIL_APP_PASSWORD not configured in .env"
        )

    if to:
        recipients = [t.strip() for t in to.split(",") if t.strip()]
    else:
        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    if not recipients:
        raise HTTPException(status_code=500, detail="EMAIL_RECIPIENTS not configured in .env")

    today = date.today()
    report = _build_report(db)
    html = _build_html(report, today)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"HiD Weekly Report — {today.strftime('%d %b %Y')}"
    msg["From"] = gmail_user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, recipients, msg.as_string())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Email send failed: {e}")

    return _envelope({
        "sent_to": recipients,
        "subject": msg["Subject"],
        "branches_included": len(report),
    })


# ── Email preview ─────────────────────────────────────────────────────────────

@router.get("/preview", response_class=HTMLResponse)
def preview_email(db: Session = Depends(get_db)):
    """Return rendered HTML email for iframe preview (no sending)."""
    today = date.today()
    report = _build_report(db)
    html = _build_html(report, today)
    return HTMLResponse(content=html)


# ── Email schedule management ─────────────────────────────────────────────────

_schedule_logger = logging.getLogger(__name__)

# In-memory schedule config (loaded from env on startup, updated via API)
_email_schedule: dict = {
    "enabled": False,
    "day_of_week": "mon",  # mon,tue,wed,thu,fri,sat,sun
    "hour": 7,
    "minute": 0,
    "recipients": [],
}

_DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_DAY_NAMES = {v: k for k, v in _DAY_MAP.items()}


def _init_schedule():
    """Initialize schedule from env var EMAIL_RECIPIENTS."""
    recipients_raw = getattr(settings, "EMAIL_RECIPIENTS", "") or ""
    _email_schedule["recipients"] = [
        r.strip() for r in recipients_raw.split(",") if r.strip()
    ]


_init_schedule()


class ScheduleUpdate(BaseModel):
    enabled: Optional[bool] = None
    day_of_week: Optional[str] = None  # mon-sun
    hour: Optional[int] = None         # 0-23
    minute: Optional[int] = None       # 0-59
    recipients: Optional[list[str]] = None


def _apply_schedule_to_scheduler():
    """Create or update the APScheduler job based on current _email_schedule."""
    from app.scheduler import scheduler
    from apscheduler.triggers.cron import CronTrigger

    job_id = "weekly_email_send"

    if not _email_schedule["enabled"]:
        try:
            scheduler.remove_job(job_id)
            _schedule_logger.info("Weekly email job removed (disabled)")
        except Exception:
            pass
        return

    day = _email_schedule["day_of_week"]
    hour = _email_schedule["hour"]
    minute = _email_schedule["minute"]

    def _send_weekly_job():
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            report = _build_report(db)
            html = _build_html(report, date.today())
            gmail_user = getattr(settings, "GMAIL_USER", "") or ""
            gmail_pass = getattr(settings, "GMAIL_APP_PASSWORD", "") or ""
            recipients = _email_schedule.get("recipients", [])
            if not gmail_user or not gmail_pass or not recipients:
                _schedule_logger.warning("Weekly email job: missing credentials or recipients")
                return
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"HiD Weekly Report — {date.today().strftime('%d %b %Y')}"
            msg["From"] = gmail_user
            msg["To"] = ", ".join(recipients)
            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(gmail_user, gmail_pass)
                server.sendmail(gmail_user, recipients, msg.as_string())
            _schedule_logger.info("Weekly email sent to %s", recipients)
        except Exception as e:
            _schedule_logger.error("Weekly email job failed: %s", e)
        finally:
            db.close()

    scheduler.add_job(
        _send_weekly_job,
        trigger=CronTrigger(day_of_week=day, hour=hour, minute=minute),
        id=job_id,
        replace_existing=True,
    )
    _schedule_logger.info(
        "Weekly email job scheduled: %s at %02d:%02d ICT", day, hour, minute
    )


@router.get("/schedule")
def get_schedule():
    """Return current email schedule configuration."""
    from app.scheduler import scheduler

    job = scheduler.get_job("weekly_email_send")
    next_run = str(job.next_run_time) if job else None

    return _envelope({
        **_email_schedule,
        "next_run": next_run,
    })


@router.patch("/schedule")
def update_schedule(body: ScheduleUpdate):
    """Update email schedule and reschedule the APScheduler job."""
    if body.enabled is not None:
        _email_schedule["enabled"] = body.enabled
    if body.day_of_week is not None:
        if body.day_of_week not in _DAY_MAP:
            raise HTTPException(400, f"Invalid day_of_week: {body.day_of_week}")
        _email_schedule["day_of_week"] = body.day_of_week
    if body.hour is not None:
        if not (0 <= body.hour <= 23):
            raise HTTPException(400, "hour must be 0-23")
        _email_schedule["hour"] = body.hour
    if body.minute is not None:
        if not (0 <= body.minute <= 59):
            raise HTTPException(400, "minute must be 0-59")
        _email_schedule["minute"] = body.minute
    if body.recipients is not None:
        _email_schedule["recipients"] = [r.strip() for r in body.recipients if r.strip()]

    _apply_schedule_to_scheduler()

    return _envelope(_email_schedule)
