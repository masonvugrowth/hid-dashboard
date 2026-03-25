"""
Daily GHL Email Stats Sync — multi-location support.
Pulls stats from GHL API for each configured location (branch):
  1. Workflow campaigns — full stats (delivered, opened, clicked, etc.)
  2. Bulk email campaigns — send counts from schedule API
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


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Version": "2021-07-28",
        "Accept": "application/json",
    }


# ── Workflow campaigns ────────────────────────────────────────────────────────

def _fetch_workflows(client: httpx.Client, location_id: str, api_key: str) -> List[dict]:
    resp = client.get(
        f"{GHL_BASE}/workflows/",
        params={"locationId": location_id},
        headers=_headers(api_key),
    )
    resp.raise_for_status()
    return resp.json().get("workflows", [])


def _fetch_workflow_stats(client: httpx.Client, location_id: str, api_key: str, workflow_id: str) -> Optional[dict]:
    try:
        resp = client.get(
            f"{GHL_BASE}/emails/stats/location/{location_id}/workflow-campaigns/{workflow_id}",
            headers=_headers(api_key),
        )
        if resp.status_code == 200:
            return resp.json().get("stats")
        return None
    except Exception:
        return None


def _sync_workflows(client: httpx.Client, db: Session, location: dict, today: date, now: datetime) -> int:
    loc_id = location["location_id"]
    api_key = location["api_key"]
    branch = location["name"]

    workflows = _fetch_workflows(client, loc_id, api_key)
    logger.info("GHL [%s]: found %d workflows", branch, len(workflows))
    count = 0

    for wf in workflows:
        stats = _fetch_workflow_stats(client, loc_id, api_key, wf["id"])
        if not stats:
            continue

        delivered = stats.get("delivered", 0)
        if delivered == 0:
            continue

        total_sent = delivered + stats.get("permanentFail", 0) + stats.get("temporaryFail", 0)

        _upsert_stats(db, {
            "workflow_id": wf["id"],
            "workflow_name": wf["name"],
            "campaign_type": "workflow",
            "branch_name": branch,
            "stat_date": today,
            "total_sent": total_sent,
            "total_delivered": delivered,
            "total_opened": stats.get("opened", 0),
            "unique_opened": stats.get("opened", 0),
            "total_clicked": stats.get("clicked", 0),
            "unique_clicked": stats.get("clicked", 0),
            "total_bounced": stats.get("permanentFail", 0) + stats.get("temporaryFail", 0),
            "total_unsubscribed": stats.get("unsubscribed", 0),
            "total_complained": stats.get("complained", 0),
            "computed_at": now,
        })
        count += 1

    return count


# ── Bulk email campaigns ──────────────────────────────────────────────────────

def _fetch_bulk_campaigns(client: httpx.Client, location_id: str, api_key: str) -> List[dict]:
    try:
        resp = client.get(
            f"{GHL_BASE}/emails/schedule",
            params={"locationId": location_id},
            headers=_headers(api_key),
        )
        resp.raise_for_status()
        return resp.json().get("schedules", [])
    except Exception:
        logger.exception("Failed to fetch bulk campaigns")
        return []


def _sync_bulk_campaigns(client: httpx.Client, db: Session, location: dict, today: date, now: datetime) -> int:
    loc_id = location["location_id"]
    api_key = location["api_key"]
    branch = location["name"]

    campaigns = _fetch_bulk_campaigns(client, loc_id, api_key)
    logger.info("GHL [%s]: found %d bulk campaigns", branch, len(campaigns))
    count = 0

    for c in campaigns:
        if c.get("status") != "complete":
            continue

        success_count = c.get("successCount", 0) or c.get("success", 0) or 0
        failed_count = c.get("failed", 0) or 0
        total_sent = success_count + failed_count

        if success_count == 0:
            continue

        date_scheduled = c.get("dateScheduled")
        if date_scheduled:
            stat_date = datetime.fromtimestamp(date_scheduled / 1000).date()
        else:
            created = c.get("createdAt", "")
            stat_date = datetime.fromisoformat(created.replace("Z", "+00:00")).date() if created else today

        _upsert_stats(db, {
            "workflow_id": c["id"],
            "workflow_name": c.get("name", c["id"]),
            "campaign_type": "bulk",
            "branch_name": branch,
            "stat_date": stat_date,
            "total_sent": total_sent,
            "total_delivered": success_count,
            "total_opened": 0,
            "unique_opened": 0,
            "total_clicked": 0,
            "unique_clicked": 0,
            "total_bounced": failed_count,
            "total_unsubscribed": 0,
            "total_complained": 0,
            "computed_at": now,
        })
        count += 1

    return count


# ── Shared upsert ─────────────────────────────────────────────────────────────

def _upsert_stats(db: Session, values: dict):
    total_sent = values["total_sent"]
    values.update({
        "open_rate": round(values.get("total_opened", 0) / total_sent, 4) if total_sent > 0 else 0,
        "click_rate": round(values.get("total_clicked", 0) / total_sent, 4) if total_sent > 0 else 0,
        "bounce_rate": round(values.get("total_bounced", 0) / total_sent, 4) if total_sent > 0 else 0,
        "unsubscribe_rate": round(values.get("total_unsubscribed", 0) / total_sent, 4) if total_sent > 0 else 0,
    })

    stmt = pg_insert(EmailCampaignStats).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_email_stats_workflow_date",
        set_={k: v for k, v in values.items() if k not in ("workflow_id", "stat_date", "campaign_type", "branch_name")},
    )
    db.execute(stmt)


# ── Main sync ─────────────────────────────────────────────────────────────────

def sync_ghl_email_stats(db: Session) -> int:
    """Pull stats from GHL API for all configured locations.

    Returns total number of items synced across all locations.
    """
    locations = settings.ghl_locations
    if not locations:
        logger.warning("No GHL locations configured, skipping email sync")
        return 0

    today = date.today()
    now = datetime.now(timezone.utc)
    total = 0

    with httpx.Client(timeout=30) as client:
        for loc in locations:
            logger.info("GHL email sync starting for %s (location=%s)", loc["name"], loc["location_id"])
            wf_count = _sync_workflows(client, db, loc, today, now)
            bulk_count = _sync_bulk_campaigns(client, db, loc, today, now)
            loc_total = wf_count + bulk_count
            total += loc_total
            logger.info("GHL [%s]: %d workflows + %d bulk = %d", loc["name"], wf_count, bulk_count, loc_total)

    db.commit()
    logger.info("GHL email sync complete: %d total items across %d locations", total, len(locations))
    return total
