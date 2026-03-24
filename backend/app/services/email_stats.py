"""Aggregate email_events into email_campaign_stats (per workflow per day)."""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, case, text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models.email_event import EmailEvent
from app.models.email_campaign_stats import EmailCampaignStats

logger = logging.getLogger(__name__)


def aggregate_email_stats(db: Session, date_from: date, date_to: date) -> int:
    """Compute daily stats from email_events and upsert into email_campaign_stats.

    Returns the number of rows upserted.
    """
    rows = (
        db.query(
            EmailEvent.ghl_workflow_id.label("workflow_id"),
            func.max(EmailEvent.workflow_name).label("workflow_name"),
            func.cast(EmailEvent.event_timestamp, type_=func.date if hasattr(func, 'date') else None).label("stat_date"),
            func.count(case((EmailEvent.event_type == "sent", 1))).label("total_sent"),
            func.count(case((EmailEvent.event_type == "delivered", 1))).label("total_delivered"),
            func.count(case((EmailEvent.event_type == "opened", 1))).label("total_opened"),
            func.count(case((EmailEvent.event_type == "clicked", 1))).label("total_clicked"),
            func.count(case((EmailEvent.event_type == "bounced", 1))).label("total_bounced"),
            func.count(case((EmailEvent.event_type == "unsubscribed", 1))).label("total_unsubscribed"),
            func.count(case((EmailEvent.event_type == "complained", 1))).label("total_complained"),
        )
        .filter(
            EmailEvent.ghl_workflow_id.isnot(None),
            func.cast(EmailEvent.event_timestamp, db.bind.dialect.type_descriptor(type(None))).between(date_from, date_to)
            if False else
            EmailEvent.event_timestamp >= datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc),
        )
        .filter(
            EmailEvent.event_timestamp < datetime.combine(date_to + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc),
        )
        .group_by(
            EmailEvent.ghl_workflow_id,
            func.date(EmailEvent.event_timestamp),
        )
        .all()
    )

    count = 0
    now = datetime.now(timezone.utc)

    for row in rows:
        total_sent = row.total_sent or 0
        total_opened = row.total_opened or 0
        total_clicked = row.total_clicked or 0
        total_bounced = row.total_bounced or 0
        total_unsub = row.total_unsubscribed or 0

        open_rate = (total_opened / total_sent) if total_sent > 0 else 0
        click_rate = (total_clicked / total_sent) if total_sent > 0 else 0
        bounce_rate = (total_bounced / total_sent) if total_sent > 0 else 0
        unsub_rate = (total_unsub / total_sent) if total_sent > 0 else 0

        stat_date = row.stat_date if isinstance(row.stat_date, date) else date_from

        values = {
            "workflow_id": row.workflow_id,
            "workflow_name": row.workflow_name,
            "stat_date": stat_date,
            "total_sent": total_sent,
            "total_delivered": row.total_delivered or 0,
            "total_opened": total_opened,
            "unique_opened": total_opened,  # approximation from events
            "total_clicked": total_clicked,
            "unique_clicked": total_clicked,
            "total_bounced": total_bounced,
            "total_unsubscribed": total_unsub,
            "total_complained": row.total_complained or 0,
            "open_rate": round(open_rate, 4),
            "click_rate": round(click_rate, 4),
            "bounce_rate": round(bounce_rate, 4),
            "unsubscribe_rate": round(unsub_rate, 4),
            "computed_at": now,
        }

        stmt = insert(EmailCampaignStats).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_email_stats_workflow_date",
            set_={k: v for k, v in values.items() if k not in ("workflow_id", "stat_date")},
        )
        db.execute(stmt)
        count += 1

    db.commit()
    logger.info("Email stats aggregation: %d rows upserted for %s to %s", count, date_from, date_to)
    return count
