"""Marketing Activity Log router"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.activity import MarketingActivity

router = APIRouter()


def _envelope(data):
    return {"success": True, "data": data, "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat()}


def _clean(data: dict) -> dict:
    for k in ("date_from", "date_to"):
        if data.get(k) == "":
            data[k] = None
    return data


class ActivityIn(BaseModel):
    branch_id: UUID
    target_country: Optional[str] = None
    activity_type: Optional[str] = None   # PaidAds, KOL, CRM, Event, Organic
    target_audience: Optional[str] = None
    description: Optional[str] = None
    result_notes: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


@router.get("")
def list_activities(
    branch_id: Optional[UUID] = Query(None),
    activity_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(MarketingActivity)
    if branch_id:
        q = q.filter(MarketingActivity.branch_id == branch_id)
    if activity_type:
        q = q.filter(MarketingActivity.activity_type == activity_type)
    rows = q.order_by(MarketingActivity.date_from.desc().nullslast()).limit(limit).all()
    return _envelope([_row(r) for r in rows])


@router.post("")
def create_activity(body: ActivityIn, db: Session = Depends(get_db)):
    obj = MarketingActivity(**_clean(body.model_dump()))
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _envelope(_row(obj))


@router.put("/{activity_id}")
def update_activity(activity_id: UUID, body: ActivityIn, db: Session = Depends(get_db)):
    obj = db.query(MarketingActivity).filter(MarketingActivity.id == activity_id).first()
    if not obj:
        raise HTTPException(404, "Activity not found")
    for k, v in _clean(body.model_dump(exclude_unset=True)).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return _envelope(_row(obj))


@router.delete("/{activity_id}")
def delete_activity(activity_id: UUID, db: Session = Depends(get_db)):
    obj = db.query(MarketingActivity).filter(MarketingActivity.id == activity_id).first()
    if not obj:
        raise HTTPException(404, "Activity not found")
    db.delete(obj)
    db.commit()
    return _envelope({"deleted": str(activity_id)})


def _row(r: MarketingActivity):
    return {
        "id": str(r.id),
        "branch_id": str(r.branch_id),
        "target_country": r.target_country,
        "activity_type": r.activity_type,
        "target_audience": r.target_audience,
        "description": r.description,
        "result_notes": r.result_notes,
        "date_from": r.date_from.isoformat() if r.date_from else None,
        "date_to": r.date_to.isoformat() if r.date_to else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
