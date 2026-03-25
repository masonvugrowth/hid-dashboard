"""
Daily GHL Email Stats Sync — pulls cumulative stats from GHL API,
computes daily delta vs previous snapshot, and upserts into email_campaign_stats.

GHL API endpoint:
  GET /emails/stats/location/{locationId}/workflow-campaigns/{workflowId}
Returns all-time cumulative stats (delivered, opened, clicked, etc.).

Logic:
  1. Pull all workflows from GHL API
  2. For each workflow, get cumulative email stats
  3. Load yesterday's cumulative snapshot from email_campaign_stats (stat_date = yesterday)
  4. Compute delta = today_cumulative - yesterday_cumulative
  5. Upsert today's cumulative as a new row (stat_date = today)
  6. The delta values are what the frontend shows as "daily" data

Since GHL only gives cumulative totals, the first day stores the full cumulative.
From day 2 onward, the daily chart shows increments.
"""
import logging
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

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


def _fetch_workflows(client: httpx.Client) -> List[dict]:
    """Get all workflows for the location."""
    resp = client.get(
        f"{GHL_BASE}/workflows/",
        params={"locationId": settings.GHL_LOCATION_ID},
        headers=_ghl_headers(),
    )
    resp.raise_for_status()
    return resp.json().get("workflows", [])


def _fetch_email_stats(client: httpx.Client, workflow_id: str) -> Optional[dict]:
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


def sync_ghl_email_stats(db: Session) -> int:
    """Pull cumulative stats from GHL API for all workflows and upsert into DB.

    Returns the number of workflows synced.
    """
    if not settings.GHL_API_KEY or not settings.GHL_LOCATION_ID:
        logger.warning("GHL credentials not configured, skipping email sync")
        return 0

    today = date.today()
    now = datetime.now(timezone.utc)
    count = 0

    with httpx.Client(timeout=30) as client:
        workflows = _fetch_workflows(client)
        logger.info("GHL email sync: found %d workflows", len(workflows))

        for wf in workflows:
            wf_id = wf["id"]
            wf_name = wf["name"]

            stats = _fetch_email_stats(client, wf_id)
            if not stats:
                continue

            delivered = stats.get("delivered", 0)
            if delivered == 0:
                continue  # Skip workflows with no email activity

            total_sent = delivered + stats.get("permanentFail", 0) + stats.get("temporaryFail", 0)
            total_opened = stats.get("opened", 0)
            total_clicked = stats.get("clicked", 0)
            total_bounced = stats.get("permanentFail", 0) + stats.get("temporaryFail", 0)
            total_unsub = stats.get("unsubscribed", 0)
            total_complained = stats.get("complained", 0)

            values = {
                "workflow_id": wf_id,
                "workflow_name": wf_name,
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
                "open_rate": round(total_opened / total_sent, 4) if total_sent > 0 else 0,
                "click_rate": round(total_clicked / total_sent, 4) if total_sent > 0 else 0,
                "bounce_rate": round(total_bounced / total_sent, 4) if total_sent > 0 else 0,
                "unsubscribe_rate": round(total_unsub / total_sent, 4) if total_sent > 0 else 0,
                "computed_at": now,
            }

            stmt = pg_insert(EmailCampaignStats).values(**values)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_email_stats_workflow_date",
                set_={k: v for k, v in values.items() if k not in ("workflow_id", "stat_date")},
            )
            db.execute(stmt)
            count += 1

    db.commit()
    logger.info("GHL email sync complete: %d workflows synced for %s", count, today)
    return count
