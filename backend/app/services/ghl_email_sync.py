"""
Daily GHL Email Stats Sync — pulls stats from GHL API for both:
  1. Workflow campaigns (automated nurture flows) — full stats via stats API
  2. Bulk email campaigns (one-time blasts) — send counts from schedule API

Upserts into email_campaign_stats with campaign_type = 'workflow' or 'bulk'.
"""
import logging
from datetime import date, datetime, timezone
from typing import List, Optional

import httpx
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.models.email_campaign_stats import EmailCampaignStats

logger = logging.getLogger(__name__)

GHL_BASE = "https://services.leadconnectorhq.com"


def _ghl_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.GHL_API_KEY}",
        "Version": "2021-07-28",
        "Accept": "application/json",
    }


# ── Workflow campaigns ────────────────────────────────────────────────────────

def _fetch_workflows(client: httpx.Client) -> List[dict]:
    """Get all workflows for the location."""
    resp = client.get(
        f"{GHL_BASE}/workflows/",
        params={"locationId": settings.GHL_LOCATION_ID},
        headers=_ghl_headers(),
    )
    resp.raise_for_status()
    return resp.json().get("workflows", [])


def _fetch_workflow_stats(client: httpx.Client, workflow_id: str) -> Optional[dict]:
    """Get cumulative email stats for a single workflow."""
    try:
        resp = client.get(
            f"{GHL_BASE}/emails/stats/location/{settings.GHL_LOCATION_ID}/workflow-campaigns/{workflow_id}",
            headers=_ghl_headers(),
        )
        if resp.status_code == 200:
            return resp.json().get("stats")
        return None
    except Exception:
        return None


def _sync_workflows(client: httpx.Client, db: Session, today: date, now: datetime) -> int:
    """Sync workflow campaign stats. Returns count of rows upserted."""
    workflows = _fetch_workflows(client)
    logger.info("GHL email sync: found %d workflows", len(workflows))
    count = 0

    for wf in workflows:
        wf_id = wf["id"]
        wf_name = wf["name"]

        stats = _fetch_workflow_stats(client, wf_id)
        if not stats:
            continue

        delivered = stats.get("delivered", 0)
        if delivered == 0:
            continue

        total_sent = delivered + stats.get("permanentFail", 0) + stats.get("temporaryFail", 0)
        total_opened = stats.get("opened", 0)
        total_clicked = stats.get("clicked", 0)
        total_bounced = stats.get("permanentFail", 0) + stats.get("temporaryFail", 0)
        total_unsub = stats.get("unsubscribed", 0)
        total_complained = stats.get("complained", 0)

        _upsert_stats(db, {
            "workflow_id": wf_id,
            "workflow_name": wf_name,
            "campaign_type": "workflow",
            "stat_date": today,
            "total_sent": total_sent,
            "total_delivered": delivered,
            "total_opened": total_opened,
            "unique_opened": total_opened,
            "total_clicked": total_clicked,
            "unique_clicked": total_clicked,
            "total_bounced": total_bounced,
            "total_unsubscribed": total_unsub,
            "total_complained": total_complained,
            "computed_at": now,
        })
        count += 1

    return count


# ── Bulk email campaigns ──────────────────────────────────────────────────────

def _fetch_bulk_campaigns(client: httpx.Client) -> List[dict]:
    """Get all bulk email schedules/campaigns for the location."""
    try:
        resp = client.get(
            f"{GHL_BASE}/emails/schedule",
            params={"locationId": settings.GHL_LOCATION_ID},
            headers=_ghl_headers(),
        )
        resp.raise_for_status()
        return resp.json().get("schedules", [])
    except Exception:
        logger.exception("Failed to fetch bulk campaigns")
        return []


def _sync_bulk_campaigns(client: httpx.Client, db: Session, today: date, now: datetime) -> int:
    """Sync bulk email campaign stats. Returns count of rows upserted."""
    campaigns = _fetch_bulk_campaigns(client)
    logger.info("GHL email sync: found %d bulk campaigns", len(campaigns))
    count = 0

    for c in campaigns:
        if c.get("status") != "complete":
            continue

        c_id = c["id"]
        c_name = c.get("name", c_id)
        success_count = c.get("successCount", 0) or c.get("success", 0) or 0
        failed_count = c.get("failed", 0) or 0
        total_sent = success_count + failed_count

        if success_count == 0:
            continue

        # Use scheduled date as stat_date for bulk campaigns
        date_scheduled = c.get("dateScheduled")
        if date_scheduled:
            stat_date = datetime.fromtimestamp(date_scheduled / 1000).date()
        else:
            created = c.get("createdAt", "")
            stat_date = datetime.fromisoformat(created.replace("Z", "+00:00")).date() if created else today

        _upsert_stats(db, {
            "workflow_id": c_id,
            "workflow_name": c_name,
            "campaign_type": "bulk",
            "stat_date": stat_date,
            "total_sent": total_sent,
            "total_delivered": success_count,
            "total_opened": 0,      # GHL API doesn't expose open/click for bulk
            "unique_opened": 0,
            "total_clicked": 0,
            "total_bounced": failed_count,
            "total_unsubscribed": 0,
            "total_complained": 0,
            "computed_at": now,
        })
        count += 1

    return count


# ── Shared upsert helper ─────────────────────────────────────────────────────

def _upsert_stats(db: Session, values: dict):
    """Upsert a row into email_campaign_stats with computed rates."""
    total_sent = values["total_sent"]
    total_opened = values.get("total_opened", 0)
    total_clicked = values.get("total_clicked", 0)
    total_bounced = values.get("total_bounced", 0)
    total_unsub = values.get("total_unsubscribed", 0)

    values.update({
        "open_rate": round(total_opened / total_sent, 4) if total_sent > 0 else 0,
        "click_rate": round(total_clicked / total_sent, 4) if total_sent > 0 else 0,
        "bounce_rate": round(total_bounced / total_sent, 4) if total_sent > 0 else 0,
        "unsubscribe_rate": round(total_unsub / total_sent, 4) if total_sent > 0 else 0,
    })

    stmt = pg_insert(EmailCampaignStats).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_email_stats_workflow_date",
        set_={k: v for k, v in values.items() if k not in ("workflow_id", "stat_date", "campaign_type")},
    )
    db.execute(stmt)


# ── Main sync function ───────────────────────────────────────────────────────

def sync_ghl_email_stats(db: Session) -> int:
    """Pull stats from GHL API for all workflows + bulk campaigns.

    Returns total number of items synced.
    """
    if not settings.GHL_API_KEY or not settings.GHL_LOCATION_ID:
        logger.warning("GHL credentials not configured, skipping email sync")
        return 0

    today = date.today()
    now = datetime.now(timezone.utc)

    with httpx.Client(timeout=30) as client:
        wf_count = _sync_workflows(client, db, today, now)
        bulk_count = _sync_bulk_campaigns(client, db, today, now)

    db.commit()
    total = wf_count + bulk_count
    logger.info("GHL email sync complete: %d workflows + %d bulk = %d total for %s",
                wf_count, bulk_count, total, today)
    return total
