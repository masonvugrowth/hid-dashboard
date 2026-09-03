"""Standing instruction to email one branch's Bi-Weekly report on its own.

The manual send already exists (`POST /biweekly/send`). What this table adds
is the part a person keeps forgetting: doing it every fortnight, on the day,
for the same list of people.

One row per branch, because that is the shape of everything downstream — a
share link is scoped to one (period, branch), the recipient list is whoever
may see THAT branch, and a branch whose manager left should stop receiving
without touching the other four.

Two send days rather than a cron string:

  * `send_day_h1` — the day of the SAME month on which the just-closed
    1st–14th report goes out. Constrained to 15–28.
  * `send_day_h2` — the day of the FOLLOWING month on which the just-closed
    15th–EOM report goes out. Constrained to 1–14.

The ranges are the point. They make it structurally impossible to schedule a
send before the period it describes has finished, which a free-form cron
expression would happily let someone do — and a report that goes out mid-period
is not an early report, it is a wrong one.

`last_sent_period_key` is what makes the job exactly-once. The runner ticks
every 15 minutes and catches up for a few days after a missed send (a Zeabur
redeploy at 08:00 should cost a delay, not the fortnight's report), so "have I
already sent this period" is the only thing standing between a catch-up and a
manager getting the same email four times an hour. It is read and written
under `SELECT FOR UPDATE`, in the same transaction as the send.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base

# The column defaults and the catch-up window live with the arithmetic that
# uses them, in services/biweekly_schedule.py, which imports no ORM and so can
# be unit-tested without a database. Re-exported here because a reader looking
# for a column's default looks at the model.
from app.services.biweekly_schedule import (  # noqa: F401
    CATCH_UP_DAYS,
    DEFAULT_HOUR,
    DEFAULT_MINUTE,
    DEFAULT_SEND_DAY_H1,
    DEFAULT_SEND_DAY_H2,
)


class BiweeklyReportSchedule(Base):
    __tablename__ = "biweekly_report_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True),
                       ForeignKey("branches.id", ondelete="CASCADE"),
                       nullable=False, unique=True, index=True)
    is_enabled = Column(Boolean, nullable=False, default=False,
                        server_default="false")

    # Who gets it. HiD users by id — so a recipient whose branch access is
    # revoked is re-checked and dropped at send time rather than keeping the
    # subscription forever — plus free-typed addresses for branch managers
    # with no account at all.
    recipient_user_ids = Column(JSONB, nullable=False, default=list,
                                server_default="[]")
    extra_emails = Column(JSONB, nullable=False, default=list,
                          server_default="[]")

    send_day_h1 = Column(Integer, nullable=False, default=DEFAULT_SEND_DAY_H1,
                         server_default=str(DEFAULT_SEND_DAY_H1))
    send_day_h2 = Column(Integer, nullable=False, default=DEFAULT_SEND_DAY_H2,
                         server_default=str(DEFAULT_SEND_DAY_H2))
    hour = Column(Integer, nullable=False, default=DEFAULT_HOUR,
                  server_default=str(DEFAULT_HOUR))
    minute = Column(Integer, nullable=False, default=DEFAULT_MINUTE,
                    server_default=str(DEFAULT_MINUTE))

    # The audit trail the Growth team reads when a manager says "I never got
    # it". `last_error` holds the reason a run reached nobody; it is cleared
    # on the next run that reaches someone, so a stale error never outlives
    # the problem it described.
    last_sent_period_key = Column(String(16), nullable=True)
    last_sent_at = Column(DateTime(timezone=True), nullable=True)
    last_sent_to = Column(JSONB, nullable=True)
    last_failed = Column(JSONB, nullable=True)
    last_error = Column(Text, nullable=True)

    updated_by = Column(UUID(as_uuid=True),
                        ForeignKey("users.id", ondelete="SET NULL"),
                        nullable=True)
    created_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        nullable=False)
    updated_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc),
                        nullable=False)
