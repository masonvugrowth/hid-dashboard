"""
Email Marketing router — GHL email performance analytics.
Pulls stats from GoHighLevel API via daily cron sync.
Supports both workflow campaigns and bulk email campaigns.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.email_campaign_stats import EmailCampaignStats

router = APIRouter()
logger = logging.getLogger(__name__)


def _envelope(data):
    return {
        "success": True,
        "data": data,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _apply_filters(q, date_from, date_to, campaign_type=None, workflow_id=None):
    """Apply common filters to a query."""
    q = q.filter(EmailCampaignStats.stat_date.between(date_from, date_to))
    if campaign_type:
        q = q.filter(EmailCampaignStats.campaign_type == campaign_type)
    if workflow_id:
        q = q.filter(EmailCampaignStats.workflow_id == workflow_id)
    return q


def _default_dates(date_from, date_to):
    today = datetime.now(timezone.utc).date()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = date_to - timedelta(days=90)
    return date_from, date_to


# ── Summary KPIs ─────────────────────────────────────────────────────────────

@router.get("/summary")
def email_summary(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    campaign_type: Optional[str] = Query(None, description="'workflow' or 'bulk'"),
    workflow_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Overall email marketing KPIs."""
    try:
        date_from, date_to = _default_dates(date_from, date_to)

        q = db.query(
            func.coalesce(func.sum(EmailCampaignStats.total_sent), 0).label("total_sent"),
            func.coalesce(func.sum(EmailCampaignStats.total_delivered), 0).label("total_delivered"),
            func.coalesce(func.sum(EmailCampaignStats.total_opened), 0).label("total_opened"),
            func.coalesce(func.sum(EmailCampaignStats.unique_opened), 0).label("unique_opened"),
            func.coalesce(func.sum(EmailCampaignStats.total_clicked), 0).label("total_clicked"),
            func.coalesce(func.sum(EmailCampaignStats.unique_clicked), 0).label("unique_clicked"),
            func.coalesce(func.sum(EmailCampaignStats.total_bounced), 0).label("total_bounced"),
            func.coalesce(func.sum(EmailCampaignStats.total_unsubscribed), 0).label("total_unsubscribed"),
            func.coalesce(func.sum(EmailCampaignStats.total_complained), 0).label("total_complained"),
        )
        q = _apply_filters(q, date_from, date_to, campaign_type, workflow_id)

        row = q.one()
        sent = int(row.total_sent)
        data = {
            "total_sent": sent,
            "total_delivered": int(row.total_delivered),
            "total_opened": int(row.total_opened),
            "unique_opened": int(row.unique_opened),
            "total_clicked": int(row.total_clicked),
            "unique_clicked": int(row.unique_clicked),
            "total_bounced": int(row.total_bounced),
            "total_unsubscribed": int(row.total_unsubscribed),
            "total_complained": int(row.total_complained),
            "open_rate": round(int(row.unique_opened) / sent, 4) if sent > 0 else 0,
            "click_rate": round(int(row.unique_clicked) / sent, 4) if sent > 0 else 0,
            "bounce_rate": round(int(row.total_bounced) / sent, 4) if sent > 0 else 0,
            "unsubscribe_rate": round(int(row.total_unsubscribed) / sent, 4) if sent > 0 else 0,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        }
        return _envelope(data)
    except Exception as e:
        logger.exception("email_summary failed")
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Daily Trend ──────────────────────────────────────────────────────────────

@router.get("/daily")
def email_daily(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    campaign_type: Optional[str] = Query(None),
    workflow_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Daily email stats trend."""
    try:
        date_from, date_to = _default_dates(date_from, date_to)

        q = db.query(
            EmailCampaignStats.stat_date,
            func.sum(EmailCampaignStats.total_sent).label("sent"),
            func.sum(EmailCampaignStats.total_delivered).label("delivered"),
            func.sum(EmailCampaignStats.total_opened).label("opened"),
            func.sum(EmailCampaignStats.total_clicked).label("clicked"),
            func.sum(EmailCampaignStats.total_bounced).label("bounced"),
            func.sum(EmailCampaignStats.total_unsubscribed).label("unsubscribed"),
        )
        q = _apply_filters(q, date_from, date_to, campaign_type, workflow_id)
        q = q.group_by(EmailCampaignStats.stat_date).order_by(EmailCampaignStats.stat_date)
        rows = q.all()

        data = []
        for r in rows:
            sent = int(r.sent or 0)
            opened = int(r.opened or 0)
            clicked = int(r.clicked or 0)
            data.append({
                "date": r.stat_date.isoformat(),
                "sent": sent,
                "delivered": int(r.delivered or 0),
                "opened": opened,
                "clicked": clicked,
                "bounced": int(r.bounced or 0),
                "unsubscribed": int(r.unsubscribed or 0),
                "open_rate": round(opened / sent, 4) if sent > 0 else 0,
                "click_rate": round(clicked / sent, 4) if sent > 0 else 0,
            })

        return _envelope(data)
    except Exception as e:
        logger.exception("email_daily failed")
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}


# ── By Campaign (workflow + bulk combined) ───────────────────────────────────

@router.get("/by-campaign")
def email_by_campaign(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    campaign_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Per-campaign breakdown with campaign_type."""
    try:
        date_from, date_to = _default_dates(date_from, date_to)

        q = db.query(
            EmailCampaignStats.workflow_id,
            func.max(EmailCampaignStats.workflow_name).label("workflow_name"),
            func.max(EmailCampaignStats.campaign_type).label("campaign_type"),
            func.sum(EmailCampaignStats.total_sent).label("sent"),
            func.sum(EmailCampaignStats.total_delivered).label("delivered"),
            func.sum(EmailCampaignStats.total_opened).label("opened"),
            func.sum(EmailCampaignStats.unique_opened).label("unique_opened"),
            func.sum(EmailCampaignStats.total_clicked).label("clicked"),
            func.sum(EmailCampaignStats.unique_clicked).label("unique_clicked"),
            func.sum(EmailCampaignStats.total_bounced).label("bounced"),
            func.sum(EmailCampaignStats.total_unsubscribed).label("unsubscribed"),
        )
        q = _apply_filters(q, date_from, date_to, campaign_type)
        q = q.group_by(EmailCampaignStats.workflow_id).order_by(desc("sent"))

        rows = q.all()
        data = []
        for r in rows:
            sent = int(r.sent or 0)
            opened = int(r.unique_opened or 0)
            clicked = int(r.unique_clicked or 0)
            bounced = int(r.bounced or 0)
            unsub = int(r.unsubscribed or 0)
            data.append({
                "workflow_id": r.workflow_id,
                "workflow_name": r.workflow_name or r.workflow_id,
                "campaign_type": r.campaign_type,
                "sent": sent,
                "delivered": int(r.delivered or 0),
                "opened": int(r.opened or 0),
                "unique_opened": opened,
                "clicked": int(r.clicked or 0),
                "unique_clicked": clicked,
                "bounced": bounced,
                "unsubscribed": unsub,
                "open_rate": round(opened / sent, 4) if sent > 0 else 0,
                "click_rate": round(clicked / sent, 4) if sent > 0 else 0,
                "bounce_rate": round(bounced / sent, 4) if sent > 0 else 0,
                "unsubscribe_rate": round(unsub / sent, 4) if sent > 0 else 0,
            })

        return _envelope(data)
    except Exception as e:
        logger.exception("email_by_campaign failed")
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}


# Keep legacy endpoint for backward compat
@router.get("/by-workflow")
def email_by_workflow(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    campaign_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Alias for /by-campaign."""
    return email_by_campaign(date_from, date_to, campaign_type, db)


# ── GHL API Sync ─────────────────────────────────────────────────────────────

@router.post("/sync-ghl")
def sync_from_ghl(
    secret: str = Query(""),
    db: Session = Depends(get_db),
):
    """Manually trigger GHL email stats sync (workflows + bulk campaigns)."""
    try:
        if settings.GHL_WEBHOOK_SECRET and secret != settings.GHL_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid secret")

        from app.services.ghl_email_sync import sync_ghl_email_stats
        count = sync_ghl_email_stats(db)
        return _envelope({"items_synced": count})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("GHL sync failed")
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}
