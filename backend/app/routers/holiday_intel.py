"""
Holiday Intelligence router — Phase 5 endpoints.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.holiday_intel import HolidayCalendar
from app.services.holiday_intel import (
    get_season_matrix,
    get_country_holidays,
    get_upcoming_windows,
    get_month_opportunities,
    cross_reference_bookings,
    recompute_season_index,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/holiday-intel", tags=["Holiday Intelligence"])


def _ok(data):
    return {
        "success": True,
        "data": data,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _err(msg, code=500):
    raise HTTPException(status_code=code, detail=msg)


# ── GET /api/holiday-intel/calendar ──────────────────────────────────────────
@router.get("/calendar")
def list_holidays(
    country_code: Optional[str] = None,
    month: Optional[int] = None,
    travel_propensity: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """All holidays, filterable by country_code, month, travel_propensity."""
    try:
        q = db.query(HolidayCalendar)
        if country_code:
            q = q.filter(HolidayCalendar.country_code == country_code.upper())
        if month:
            q = q.filter(HolidayCalendar.month_start == month)
        if travel_propensity:
            q = q.filter(HolidayCalendar.travel_propensity == travel_propensity.upper())
        rows = q.order_by(HolidayCalendar.country_code, HolidayCalendar.month_start).all()
        data = [
            {
                "id": str(r.id),
                "country_code": r.country_code,
                "country_name": r.country_name,
                "holiday_name": r.holiday_name,
                "holiday_type": r.holiday_type,
                "month_start": r.month_start,
                "day_start": r.day_start,
                "month_end": r.month_end,
                "day_end": r.day_end,
                "duration_days": r.duration_days,
                "is_long_holiday": r.is_long_holiday,
                "travel_propensity": r.travel_propensity,
                "notes": r.notes,
                "data_source": r.data_source,
            }
            for r in rows
        ]
        return _ok(data)
    except Exception:
        logger.exception("list_holidays failed")
        _err("Failed to fetch holiday calendar")


# ── GET /api/holiday-intel/season-matrix ─────────────────────────────────────
@router.get("/season-matrix")
def season_matrix(db: Session = Depends(get_db)):
    """Full 25-country x 12-month heatmap data."""
    try:
        data = get_season_matrix(db)
        return _ok(data)
    except Exception:
        logger.exception("season_matrix failed")
        _err("Failed to fetch season matrix")


# ── GET /api/holiday-intel/country/{code} ────────────────────────────────────
@router.get("/country/{code}")
def country_holidays(code: str, db: Session = Depends(get_db)):
    """Holiday detail for one country."""
    try:
        data = get_country_holidays(db, code)
        if not data:
            _err(f"No holidays found for country {code.upper()}", 404)
        return _ok(data)
    except HTTPException:
        raise
    except Exception:
        logger.exception("country_holidays failed")
        _err("Failed to fetch country holidays")


# ── GET /api/holiday-intel/month/{month} ─────────────────────────────────────
@router.get("/month/{month}")
def month_view(month: int, db: Session = Depends(get_db)):
    """All countries active/peaking in a given month."""
    try:
        if not 1 <= month <= 12:
            _err("Month must be 1–12", 422)
        data = get_month_opportunities(db, month)
        return _ok(data)
    except HTTPException:
        raise
    except Exception:
        logger.exception("month_view failed")
        _err("Failed to fetch month opportunities")


# ── GET /api/holiday-intel/upcoming ──────────────────────────────────────────
@router.get("/upcoming")
def upcoming_windows(
    days: int = Query(60, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Next N-day holiday windows across all markets."""
    try:
        data = get_upcoming_windows(db, days)
        return _ok(data)
    except Exception:
        logger.exception("upcoming_windows failed")
        _err("Failed to fetch upcoming windows")


# ── POST /api/holiday-intel/holidays ─────────────────────────────────────────
class HolidayCreate(BaseModel):
    country_code: str
    country_name: str
    holiday_name: str
    holiday_type: str
    month_start: int
    day_start: Optional[int] = None
    month_end: int
    day_end: Optional[int] = None
    duration_days: int
    is_long_holiday: bool = False
    travel_propensity: str = "MEDIUM"
    notes: Optional[str] = None
    year: Optional[int] = None


@router.post("/holidays")
def create_holiday(payload: HolidayCreate, db: Session = Depends(get_db)):
    """Admin: add custom holiday entry."""
    try:
        row = HolidayCalendar(
            country_code=payload.country_code.upper(),
            country_name=payload.country_name,
            holiday_name=payload.holiday_name,
            holiday_type=payload.holiday_type,
            month_start=payload.month_start,
            day_start=payload.day_start,
            month_end=payload.month_end,
            day_end=payload.day_end,
            duration_days=payload.duration_days,
            is_long_holiday=payload.is_long_holiday,
            travel_propensity=payload.travel_propensity.upper(),
            notes=payload.notes,
            data_source="manual",
            year=payload.year,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        # Recompute season index after mutation
        recompute_season_index(db)
        return _ok({"id": str(row.id), "holiday_name": row.holiday_name})
    except Exception:
        db.rollback()
        logger.exception("create_holiday failed")
        _err("Failed to create holiday")


# ── PATCH /api/holiday-intel/holidays/{id} ───────────────────────────────────
class HolidayUpdate(BaseModel):
    holiday_name: Optional[str] = None
    holiday_type: Optional[str] = None
    month_start: Optional[int] = None
    day_start: Optional[int] = None
    month_end: Optional[int] = None
    day_end: Optional[int] = None
    duration_days: Optional[int] = None
    is_long_holiday: Optional[bool] = None
    travel_propensity: Optional[str] = None
    notes: Optional[str] = None
    year: Optional[int] = None


@router.patch("/holidays/{holiday_id}")
def update_holiday(holiday_id: UUID, payload: HolidayUpdate, db: Session = Depends(get_db)):
    """Admin: edit holiday record."""
    try:
        row = db.query(HolidayCalendar).filter_by(id=holiday_id).first()
        if not row:
            _err("Holiday not found", 404)
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field == "travel_propensity" and value:
                value = value.upper()
            setattr(row, field, value)
        row.data_source = "manual"
        db.commit()
        # Recompute season index after mutation
        recompute_season_index(db)
        return _ok({"id": str(row.id), "holiday_name": row.holiday_name})
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("update_holiday failed")
        _err("Failed to update holiday")


# ── GET /api/holiday-intel/cross-reference ───────────────────────────────────
@router.get("/cross-reference")
def cross_ref(
    country_code: str = Query(..., min_length=2, max_length=2),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Compare holiday calendar data vs actual reservation data for a country+month."""
    try:
        data = cross_reference_bookings(db, country_code, month)
        return _ok(data)
    except Exception:
        logger.exception("cross_reference failed")
        _err("Failed to cross-reference bookings")


# ── POST /api/holiday-intel/recompute ────────────────────────────────────────
@router.post("/recompute")
def trigger_recompute(db: Session = Depends(get_db)):
    """Admin: manually trigger season index recompute."""
    try:
        count = recompute_season_index(db)
        return _ok({"cells_updated": count})
    except Exception:
        logger.exception("recompute failed")
        _err("Failed to recompute season index")
