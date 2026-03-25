"""
Email Marketing router — GHL webhook receiver & email performance analytics.
Tracks email sends, opens, clicks, bounces, unsubscribes from GoHighLevel workflows.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy import func, case, desc
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.email_event import EmailEvent
from app.models.email_campaign_stats import EmailCampaignStats
from app.services.email_stats import aggregate_email_stats

router = APIRouter()
logger = logging.getLogger(__name__)


def _envelope(data):
    return {
        "success": True,
        "data": data,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── GHL Webhook Receiver ─────────────────────────────────────────────────────

@router.post("/webhook")
async def ghl_webhook(request: Request, secret: str = Query(""), db: Session = Depends(get_db)):
    """Receive email events from GoHighLevel webhooks.

    Validates via shared secret query param. Stores raw event in email_events table.
    """
    try:
        if settings.GHL_WEBHOOK_SECRET and secret != settings.GHL_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

        payload = await request.json()

        # GHL can send various payload shapes — normalize defensively
        event_type = (
            payload.get("event_type")
            or payload.get("type")
            or payload.get("event")
            or "unknown"
        ).lower().strip()

        # Map common GHL event names
        type_map = {
            "emailsent": "sent",
            "email_sent": "sent",
            "emailopened": "opened",
            "email_opened": "opened",
            "emailclicked": "clicked",
            "email_clicked": "clicked",
            "emailbounced": "bounced",
            "email_bounced": "bounced",
            "emailunsubscribed": "unsubscribed",
            "email_unsubscribed": "unsubscribed",
            "emaildelivered": "delivered",
            "email_delivered": "delivered",
            "emailcomplained": "complained",
            "email_complained": "complained",
        }
        event_type = type_map.get(event_type.replace(" ", "").replace("-", ""), event_type)

        # Extract contact info from various payload positions
        contact = payload.get("contact", {}) or {}
        workflow = payload.get("workflow", {}) or {}

        event = EmailEvent(
            ghl_contact_id=contact.get("id") or payload.get("contact_id") or payload.get("contactId"),
            ghl_workflow_id=workflow.get("id") or payload.get("workflow_id") or payload.get("workflowId"),
            workflow_name=workflow.get("name") or payload.get("workflow_name") or payload.get("workflowName"),
            email_subject=payload.get("subject") or payload.get("email_subject") or payload.get("emailSubject"),
            event_type=event_type,
            event_timestamp=datetime.now(timezone.utc),
            contact_email=contact.get("email") or payload.get("email"),
            contact_name=contact.get("name") or payload.get("contact_name")
                         or f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip() or None,
            link_url=payload.get("link") or payload.get("url") or payload.get("link_url"),
            bounce_reason=payload.get("bounce_reason") or payload.get("bounceReason"),
            raw_payload=payload,
        )

        db.add(event)
        db.commit()

        logger.info("Email event received: %s for %s (workflow: %s)",
                     event_type, event.contact_email, event.workflow_name)
        return _envelope({"processed": True, "event_type": event_type})

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Webhook processing failed")
        db.rollback()
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Summary KPIs ─────────────────────────────────────────────────────────────

@router.get("/summary")
def email_summary(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    workflow_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Overall email marketing KPIs."""
    try:
        today = datetime.now(timezone.utc).date()
        if date_to is None:
            date_to = today
        if date_from is None:
            date_from = date_to - timedelta(days=30)

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
        ).filter(
            EmailCampaignStats.stat_date.between(date_from, date_to),
        )
        if workflow_id:
            q = q.filter(EmailCampaignStats.workflow_id == workflow_id)

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

        # If no stats, fall back to counting from email_events directly
        if sent == 0:
            eq = db.query(
                EmailEvent.event_type,
                func.count().label("cnt"),
            ).filter(
                EmailEvent.event_timestamp >= datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc),
                EmailEvent.event_timestamp < datetime.combine(date_to + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc),
            )
            if workflow_id:
                eq = eq.filter(EmailEvent.ghl_workflow_id == workflow_id)
            eq = eq.group_by(EmailEvent.event_type).all()

            counts = {r.event_type: r.cnt for r in eq}
            sent = counts.get("sent", 0)
            data.update({
                "total_sent": sent,
                "total_delivered": counts.get("delivered", 0),
                "total_opened": counts.get("opened", 0),
                "unique_opened": counts.get("opened", 0),
                "total_clicked": counts.get("clicked", 0),
                "unique_clicked": counts.get("clicked", 0),
                "total_bounced": counts.get("bounced", 0),
                "total_unsubscribed": counts.get("unsubscribed", 0),
                "total_complained": counts.get("complained", 0),
                "open_rate": round(counts.get("opened", 0) / sent, 4) if sent > 0 else 0,
                "click_rate": round(counts.get("clicked", 0) / sent, 4) if sent > 0 else 0,
                "bounce_rate": round(counts.get("bounced", 0) / sent, 4) if sent > 0 else 0,
                "unsubscribe_rate": round(counts.get("unsubscribed", 0) / sent, 4) if sent > 0 else 0,
            })

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
    workflow_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Daily email stats trend."""
    try:
        today = datetime.now(timezone.utc).date()
        if date_to is None:
            date_to = today
        if date_from is None:
            date_from = date_to - timedelta(days=30)

        q = db.query(
            EmailCampaignStats.stat_date,
            func.sum(EmailCampaignStats.total_sent).label("sent"),
            func.sum(EmailCampaignStats.total_delivered).label("delivered"),
            func.sum(EmailCampaignStats.total_opened).label("opened"),
            func.sum(EmailCampaignStats.total_clicked).label("clicked"),
            func.sum(EmailCampaignStats.total_bounced).label("bounced"),
            func.sum(EmailCampaignStats.total_unsubscribed).label("unsubscribed"),
        ).filter(
            EmailCampaignStats.stat_date.between(date_from, date_to),
        )
        if workflow_id:
            q = q.filter(EmailCampaignStats.workflow_id == workflow_id)

        q = q.group_by(EmailCampaignStats.stat_date).order_by(EmailCampaignStats.stat_date)
        rows = q.all()

        data = []
        for r in rows:
            sent = int(r.sent or 0)
            opened = int(r.opened or 0)
            clicked = int(r.clicked or 0)
            bounced = int(r.bounced or 0)
            data.append({
                "date": r.stat_date.isoformat(),
                "sent": sent,
                "delivered": int(r.delivered or 0),
                "opened": opened,
                "clicked": clicked,
                "bounced": bounced,
                "unsubscribed": int(r.unsubscribed or 0),
                "open_rate": round(opened / sent, 4) if sent > 0 else 0,
                "click_rate": round(clicked / sent, 4) if sent > 0 else 0,
            })

        return _envelope(data)
    except Exception as e:
        logger.exception("email_daily failed")
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}


# ── By Workflow ──────────────────────────────────────────────────────────────

@router.get("/by-workflow")
def email_by_workflow(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Per-workflow breakdown of email stats."""
    try:
        today = datetime.now(timezone.utc).date()
        if date_to is None:
            date_to = today
        if date_from is None:
            date_from = date_to - timedelta(days=30)

        q = db.query(
            EmailCampaignStats.workflow_id,
            func.max(EmailCampaignStats.workflow_name).label("workflow_name"),
            func.sum(EmailCampaignStats.total_sent).label("sent"),
            func.sum(EmailCampaignStats.total_delivered).label("delivered"),
            func.sum(EmailCampaignStats.total_opened).label("opened"),
            func.sum(EmailCampaignStats.unique_opened).label("unique_opened"),
            func.sum(EmailCampaignStats.total_clicked).label("clicked"),
            func.sum(EmailCampaignStats.unique_clicked).label("unique_clicked"),
            func.sum(EmailCampaignStats.total_bounced).label("bounced"),
            func.sum(EmailCampaignStats.total_unsubscribed).label("unsubscribed"),
        ).filter(
            EmailCampaignStats.stat_date.between(date_from, date_to),
        ).group_by(
            EmailCampaignStats.workflow_id,
        ).order_by(desc("sent"))

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
        logger.exception("email_by_workflow failed")
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Workflow Events ──────────────────────────────────────────────────────────

@router.get("/workflow/{workflow_id}/events")
def email_workflow_events(
    workflow_id: str,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Paginated event log for a specific workflow."""
    try:
        today = datetime.now(timezone.utc).date()
        if date_to is None:
            date_to = today
        if date_from is None:
            date_from = date_to - timedelta(days=30)

        q = db.query(EmailEvent).filter(
            EmailEvent.ghl_workflow_id == workflow_id,
            EmailEvent.event_timestamp >= datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc),
            EmailEvent.event_timestamp < datetime.combine(date_to + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc),
        )
        if event_type:
            q = q.filter(EmailEvent.event_type == event_type)

        total = q.count()
        events = q.order_by(desc(EmailEvent.event_timestamp)).offset(offset).limit(limit).all()

        data = {
            "total": total,
            "events": [
                {
                    "id": str(e.id),
                    "event_type": e.event_type,
                    "event_timestamp": e.event_timestamp.isoformat() if e.event_timestamp else None,
                    "contact_email": e.contact_email,
                    "contact_name": e.contact_name,
                    "email_subject": e.email_subject,
                    "workflow_name": e.workflow_name,
                    "link_url": e.link_url,
                    "bounce_reason": e.bounce_reason,
                }
                for e in events
            ],
        }
        return _envelope(data)
    except Exception as e:
        logger.exception("email_workflow_events failed")
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Recent Events (all workflows) ───────────────────────────────────────────

@router.get("/events")
def email_events_all(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    event_type: Optional[str] = Query(None),
    workflow_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Paginated event log across all workflows."""
    try:
        today = datetime.now(timezone.utc).date()
        if date_to is None:
            date_to = today
        if date_from is None:
            date_from = date_to - timedelta(days=30)

        q = db.query(EmailEvent).filter(
            EmailEvent.event_timestamp >= datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc),
            EmailEvent.event_timestamp < datetime.combine(date_to + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc),
        )
        if event_type:
            q = q.filter(EmailEvent.event_type == event_type)
        if workflow_id:
            q = q.filter(EmailEvent.ghl_workflow_id == workflow_id)

        total = q.count()
        events = q.order_by(desc(EmailEvent.event_timestamp)).offset(offset).limit(limit).all()

        data = {
            "total": total,
            "events": [
                {
                    "id": str(e.id),
                    "event_type": e.event_type,
                    "event_timestamp": e.event_timestamp.isoformat() if e.event_timestamp else None,
                    "contact_email": e.contact_email,
                    "contact_name": e.contact_name,
                    "email_subject": e.email_subject,
                    "workflow_name": e.workflow_name,
                    "ghl_workflow_id": e.ghl_workflow_id,
                    "link_url": e.link_url,
                    "bounce_reason": e.bounce_reason,
                }
                for e in events
            ],
        }
        return _envelope(data)
    except Exception as e:
        logger.exception("email_events_all failed")
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Manual Aggregation ───────────────────────────────────────────────────────

@router.post("/aggregate")
def trigger_aggregation(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Trigger manual stats aggregation from email_events → email_campaign_stats."""
    try:
        today = datetime.now(timezone.utc).date()
        if date_to is None:
            date_to = today
        if date_from is None:
            date_from = date_to - timedelta(days=30)

        count = aggregate_email_stats(db, date_from, date_to)
        return _envelope({"rows_upserted": count, "date_from": date_from.isoformat(), "date_to": date_to.isoformat()})
    except Exception as e:
        logger.exception("aggregation failed")
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Cleanup (admin) ──────────────────────────────────────────────────────────

@router.delete("/cleanup-test")
def cleanup_test_data(
    secret: str = Query(""),
    db: Session = Depends(get_db),
):
    """Remove test data (contact_email=test@example.com or event_type=test_cleanup)."""
    try:
        if settings.GHL_WEBHOOK_SECRET and secret != settings.GHL_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid secret")

        deleted = db.query(EmailEvent).filter(
            (EmailEvent.contact_email == "test@example.com") |
            (EmailEvent.event_type == "test_cleanup")
        ).delete(synchronize_session=False)
        db.commit()
        return _envelope({"deleted": deleted})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("cleanup failed")
        db.rollback()
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Seed Historical Data ─────────────────────────────────────────────────────

@router.post("/seed-stats")
def seed_campaign_stats(
    request: Request,
    secret: str = Query(""),
    db: Session = Depends(get_db),
):
    """Seed email_campaign_stats with historical data (admin only).

    Body: array of {workflow_id, workflow_name, stat_date, total_sent, total_delivered,
    total_opened, unique_opened, total_clicked, unique_clicked, total_bounced,
    total_unsubscribed, total_complained}
    """
    import asyncio
    try:
        if settings.GHL_WEBHOOK_SECRET and secret != settings.GHL_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid secret")

        # Sync read of body
        loop = asyncio.get_event_loop()
        import json
        # Use a sync approach
        return {"success": False, "data": None, "error": "Use /seed-stats-sync instead",
                "timestamp": datetime.now(timezone.utc).isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("seed failed")
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}


@router.post("/seed-stats-sync")
async def seed_campaign_stats_sync(
    request: Request,
    secret: str = Query(""),
    db: Session = Depends(get_db),
):
    """Seed email_campaign_stats with historical data.

    Body: array of objects with workflow stats per date.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    try:
        if settings.GHL_WEBHOOK_SECRET and secret != settings.GHL_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid secret")

        rows = await request.json()
        if not isinstance(rows, list):
            return {"success": False, "data": None, "error": "Body must be a JSON array",
                    "timestamp": datetime.now(timezone.utc).isoformat()}

        count = 0
        now = datetime.now(timezone.utc)
        for row in rows:
            total_sent = row.get("total_sent", 0)
            unique_opened = row.get("unique_opened", row.get("total_opened", 0))
            unique_clicked = row.get("unique_clicked", row.get("total_clicked", 0))
            total_bounced = row.get("total_bounced", 0)
            total_unsub = row.get("total_unsubscribed", 0)

            values = {
                "workflow_id": row["workflow_id"],
                "workflow_name": row.get("workflow_name"),
                "stat_date": row["stat_date"],
                "total_sent": total_sent,
                "total_delivered": row.get("total_delivered", 0),
                "total_opened": row.get("total_opened", 0),
                "unique_opened": unique_opened,
                "total_clicked": row.get("total_clicked", 0),
                "unique_clicked": unique_clicked,
                "total_bounced": total_bounced,
                "total_unsubscribed": total_unsub,
                "total_complained": row.get("total_complained", 0),
                "open_rate": round(unique_opened / total_sent, 4) if total_sent > 0 else 0,
                "click_rate": round(unique_clicked / total_sent, 4) if total_sent > 0 else 0,
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
        return _envelope({"rows_seeded": count})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("seed failed")
        db.rollback()
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}


# ── GHL Webhook Registration ─────────────────────────────────────────────────

@router.post("/register-webhook")
def register_ghl_webhook(
    webhook_url: str = Query(..., description="Full URL for GHL to send webhooks to"),
):
    """Register a webhook URL with GoHighLevel API."""
    try:
        if not settings.GHL_API_KEY or not settings.GHL_LOCATION_ID:
            return {"success": False, "data": None, "error": "GHL_API_KEY or GHL_LOCATION_ID not configured",
                    "timestamp": datetime.now(timezone.utc).isoformat()}

        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{settings.GHL_BASE_URL}/webhooks/",
                headers={
                    "Authorization": f"Bearer {settings.GHL_API_KEY}",
                    "Version": "2021-07-28",
                    "Content-Type": "application/json",
                },
                json={
                    "url": webhook_url,
                    "locationId": settings.GHL_LOCATION_ID,
                },
            )
            result = resp.json()

        return _envelope({"ghl_response": result, "webhook_url": webhook_url})
    except Exception as e:
        logger.exception("GHL webhook registration failed")
        return {"success": False, "data": None, "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()}
