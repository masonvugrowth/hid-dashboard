"""Website Metrics CRUD router — Phase 2"""
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.website_metrics import WebsiteMetrics

router = APIRouter()


def _envelope(data):
    return {"success": True, "data": data, "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat()}


class WebsiteMetricsCreate(BaseModel):
    branch_id: Optional[UUID] = None
    week_start_date: date
    platform: str
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    ctr: Optional[float] = None
    website_traffic: Optional[int] = None
    add_to_cart: Optional[int] = None
    checkout_initiated: Optional[int] = None
    conversions: Optional[int] = None
    conversion_pct: Optional[float] = None
    conversion_hit_pct: Optional[float] = None
    notes: Optional[str] = None


class WebsiteMetricsPatch(BaseModel):
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    ctr: Optional[float] = None
    website_traffic: Optional[int] = None
    add_to_cart: Optional[int] = None
    checkout_initiated: Optional[int] = None
    conversions: Optional[int] = None
    conversion_pct: Optional[float] = None
    conversion_hit_pct: Optional[float] = None
    notes: Optional[str] = None


class WebsiteMetricsOut(BaseModel):
    id: UUID
    branch_id: Optional[UUID]
    week_start_date: date
    platform: str
    impressions: Optional[int]
    clicks: Optional[int]
    ctr: Optional[float]
    website_traffic: Optional[int]
    add_to_cart: Optional[int]
    checkout_initiated: Optional[int]
    conversions: Optional[int]
    conversion_pct: Optional[float]
    conversion_hit_pct: Optional[float]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("")
def list_website_metrics(
    branch_id: Optional[UUID] = Query(None),
    platform: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(WebsiteMetrics)
    if branch_id:
        q = q.filter(WebsiteMetrics.branch_id == branch_id)
    if platform:
        q = q.filter(WebsiteMetrics.platform == platform)
    if date_from:
        q = q.filter(WebsiteMetrics.week_start_date >= date_from)
    if date_to:
        q = q.filter(WebsiteMetrics.week_start_date <= date_to)
    rows = q.order_by(WebsiteMetrics.week_start_date.desc()).all()
    return _envelope([WebsiteMetricsOut.model_validate(r).model_dump() for r in rows])


@router.post("", status_code=201)
def create_website_metrics(payload: WebsiteMetricsCreate, db: Session = Depends(get_db)):
    row = WebsiteMetrics(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _envelope(WebsiteMetricsOut.model_validate(row).model_dump())


@router.get("/{record_id}")
def get_website_metrics(record_id: UUID, db: Session = Depends(get_db)):
    row = db.query(WebsiteMetrics).filter_by(id=record_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Record not found")
    return _envelope(WebsiteMetricsOut.model_validate(row).model_dump())


@router.patch("/{record_id}")
def update_website_metrics(record_id: UUID, payload: WebsiteMetricsPatch, db: Session = Depends(get_db)):
    row = db.query(WebsiteMetrics).filter_by(id=record_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Record not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _envelope(WebsiteMetricsOut.model_validate(row).model_dump())


@router.delete("/{record_id}", status_code=204)
def delete_website_metrics(record_id: UUID, db: Session = Depends(get_db)):
    row = db.query(WebsiteMetrics).filter_by(id=record_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(row)
    db.commit()
