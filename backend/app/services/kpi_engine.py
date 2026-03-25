"""
KPI Engine — v3.2 (Cloudbeds Insights API as single source of truth)

Both current and next month: revenue, ADR, rooms_sold all come from
Cloudbeds Data Insights API (via daily_metrics cache or live API call).
  → Uses room_revenue (accommodation only, no tax/fees) = USALI standard.
  → Each month uses its OWN ADR.

Forecast formula:
  Current ADR = Current Revenue / Current Rooms Sold
  Predicted Room Sold = Round(predicted_occ x inventory x total_days, 0)
  Forecast Revenue = Current ADR x Predicted Room Sold

Revenue EXCLUDES sources: "House use", "Blogger", "Special case"
(handled at Cloudbeds level — Insights API already excludes these.)
Room/Dorm split ADR still uses reservation_daily (Insights doesn't split by room type).
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.daily_metrics import DailyMetrics
from app.models.kpi import KPITarget
from app.models.reservation import Reservation
from app.models.reservation_daily import ReservationDaily

logger = logging.getLogger(__name__)

# Statuses excluded from all queries (cancelled / no-show reservations)
_EXCLUDED_STATUSES = {"cancelled", "canceled", "no_show", "noshow", "no show", "no-show"}

# Sources excluded from revenue, ADR, OCC, and rooms sold — consistent everywhere
_EXCLUDED_SOURCES = {
    "blogger", "house use", "houseuse",
    "special case",
}


# ── helpers ────────────────────────────────────────────────────────────────────

def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _base_reservation_daily_query(
    db: Session, branch_id: UUID, first_day: date, last_day: date,
):
    """
    Base query on reservation_daily joined to reservations, filtering:
    - branch_id matches
    - date within [first_day, last_day]
    - reservation status is not cancelled/no-show
    - source is not in excluded sources (House use, Blogger, Special case)
    Returns a SQLAlchemy query on ReservationDaily.
    """
    return (
        db.query(ReservationDaily)
        .join(Reservation, ReservationDaily.reservation_id == Reservation.id)
        .filter(
            ReservationDaily.branch_id == branch_id,
            ReservationDaily.date >= first_day,
            ReservationDaily.date <= last_day,
            # Exclude cancelled/no-show
            ~func.lower(func.coalesce(Reservation.status, "")).in_(list(_EXCLUDED_STATUSES)),
            # Exclude House use, Blogger, Special case
            ~func.lower(func.coalesce(Reservation.source, "")).in_(list(_EXCLUDED_SOURCES)),
        )
    )


def _count_dorm_beds(room_number: str) -> int:
    """
    Count individual dorm beds from room_number string.
    Dorm beds use patterns like '211-1, 211-2' (hyphenated).
    Returns at least 1.
    """
    if not room_number:
        return 1
    parts = [p.strip() for p in room_number.split(",") if p.strip()]
    return max(len(parts), 1)


def _is_combo_booking(room_type: str) -> bool:
    """
    Detect combo bookings that mix room types (e.g. 'Superior Room, 8 Beds Dormitory').
    These should be excluded from both Room and Dorm ADR to avoid cross-contamination.
    """
    rt = (room_type or "").lower()
    room_keywords = ("superior", "balcony", "double", "twin", "single", "deluxe", "family", "private", "standard")
    dorm_keywords = ("dorm", "bed ")
    has_room = any(k in rt for k in room_keywords)
    has_dorm = any(k in rt for k in dorm_keywords)
    return has_room and has_dorm


def _get_revenue_from_insights(
    db: Session, branch_id: UUID, year: int, month: int,
) -> tuple[float, float]:
    """
    Actual revenue from daily_metrics (synced from Cloudbeds Data Insights API).
    Uses room_revenue (accommodation only, no tax/fees) — matches Cloudbeds dashboard.
    Returns (revenue_native, revenue_vnd).
    """
    first_day = date(year, month, 1)
    last_day = date(year, month, _days_in_month(year, month))

    row = db.query(
        func.coalesce(func.sum(DailyMetrics.revenue_native), 0),
        func.coalesce(func.sum(DailyMetrics.revenue_vnd), 0),
    ).filter(
        DailyMetrics.branch_id == branch_id,
        DailyMetrics.date >= first_day,
        DailyMetrics.date <= last_day,
    ).one()

    return float(row[0]), float(row[1])


def _get_adr_occ_from_insights(
    db: Session, branch_id: UUID, first_day: date, last_day: date,
) -> tuple[Optional[float], int]:
    """
    ADR and rooms_sold from daily_metrics (Cloudbeds Insights).
    ADR = total_room_revenue / total_rooms_sold.
    Returns: (adr, total_rooms_sold).
    """
    row = db.query(
        func.coalesce(func.sum(DailyMetrics.revenue_native), 0),
        func.coalesce(func.sum(DailyMetrics.rooms_sold), 0),
    ).filter(
        DailyMetrics.branch_id == branch_id,
        DailyMetrics.date >= first_day,
        DailyMetrics.date <= last_day,
    ).one()

    total_rev = float(row[0])
    total_sold = int(row[1])
    adr = round(total_rev / total_sold, 2) if total_sold > 0 else None

    return adr, total_sold


def _get_insights_live(
    db: Session, branch_id: UUID, year: int, month: int,
) -> tuple[float, int, Optional[float]]:
    """
    Fetch revenue, rooms_sold, ADR directly from Cloudbeds Insights API (live call).
    Falls back to cached daily_metrics if API call fails.
    Returns: (revenue, rooms_sold, adr).
    """
    from app.models.branch import Branch
    from app.config import settings

    first_day = date(year, month, 1)
    last_day = date(year, month, _days_in_month(year, month))

    branch = db.query(Branch).filter_by(id=branch_id, is_active=True).first()
    if not branch:
        return 0.0, 0, None

    pid = branch.cloudbeds_property_id
    api_key = settings.get_api_key_for_property(str(pid)) if pid else None

    if pid and api_key:
        try:
            from app.services.cloudbeds import fetch_cloudbeds_occupancy
            occ_data = fetch_cloudbeds_occupancy(pid, api_key, first_day, last_day)
            total_rev = sum(d.get("room_revenue", 0) for d in occ_data.values())
            total_sold = sum(int(d.get("rooms_sold", 0)) for d in occ_data.values())
            adr = round(total_rev / total_sold, 2) if total_sold > 0 else None
            logger.info(
                "Live Insights for %s %d/%d: rev=%.0f sold=%d adr=%s",
                branch.name, year, month, total_rev, total_sold, adr,
            )
            return total_rev, total_sold, adr
        except Exception as e:
            logger.warning("Live Insights failed for %s: %s, falling back to cache", branch.name, e)

    # Fallback to cached daily_metrics
    adr_cached, sold_cached = _get_adr_occ_from_insights(db, branch_id, first_day, last_day)
    rev_cached, _ = _get_revenue_from_insights(db, branch_id, year, month)
    return rev_cached, sold_cached, adr_cached


def _get_room_dorm_adr_from_daily(
    db: Session, branch_id: UUID, first_day: date, last_day: date,
) -> tuple[Optional[float], Optional[float], float, int, float, int]:
    """
    Room/Dorm ADR from reservation_daily.
    ADR = revenue / rooms_sold (where rooms_sold = count of reservation-night rows).
    Excludes cancelled/no-show and excluded sources (House use, Blogger, Special case).
    For Dorm: counts per-BED (not per-reservation), excludes combo bookings.

    Returns: (room_adr, dorm_adr, room_revenue, room_sold, dorm_revenue, dorm_sold)
    """
    base = _base_reservation_daily_query(db, branch_id, first_day, last_day)

    # ── Room ADR (1 reservation_daily row = 1 room-night sold) ──────────────
    room_q = base.filter(
        func.lower(ReservationDaily.room_type_category) == "room",
    )
    room_row = room_q.with_entities(
        func.coalesce(func.sum(ReservationDaily.nightly_rate), 0),
        func.count(ReservationDaily.id),
    ).one()
    room_rev = float(room_row[0])
    room_nights = int(room_row[1])
    room_adr = round(room_rev / room_nights, 2) if room_nights > 0 else None

    # ── Dorm ADR (per-bed: count beds from room_number, exclude combos) ───
    dorm_q = (
        _base_reservation_daily_query(db, branch_id, first_day, last_day)
        .filter(func.lower(ReservationDaily.room_type_category) == "dorm")
    )
    dorm_rows = dorm_q.with_entities(
        ReservationDaily.nightly_rate,
        Reservation.room_number,
        Reservation.room_type,
    ).all()

    dorm_total_rev = 0.0
    dorm_total_beds = 0
    for row in dorm_rows:
        if _is_combo_booking(row.room_type):
            continue  # skip combo bookings — mixed room+dorm revenue can't be split
        rate = float(row.nightly_rate or 0)
        beds = _count_dorm_beds(row.room_number)
        dorm_total_rev += rate
        dorm_total_beds += beds

    dorm_adr = round(dorm_total_rev / dorm_total_beds, 2) if dorm_total_beds > 0 else None

    return room_adr, dorm_adr, room_rev, room_nights, dorm_total_rev, dorm_total_beds


def _get_total_adr_from_daily(
    db: Session, branch_id: UUID, first_day: date, last_day: date,
) -> tuple[Optional[float], float, int]:
    """
    Overall ADR from reservation_daily (all room types combined).
    ADR = total_revenue / total_room_nights_sold.
    Returns: (adr, total_revenue, total_sold).
    """
    base = _base_reservation_daily_query(db, branch_id, first_day, last_day)

    row = base.with_entities(
        func.coalesce(func.sum(ReservationDaily.nightly_rate), 0),
        func.count(ReservationDaily.id),
    ).one()

    total_rev = float(row[0])
    total_sold = int(row[1])
    adr = round(total_rev / total_sold, 2) if total_sold > 0 else None

    return adr, total_rev, total_sold


# ── core calculations ──────────────────────────────────────────────────────────

def get_actual_revenue(db: Session, branch_id: UUID, year: int, month: int) -> float:
    """
    Revenue from Cloudbeds Insights (daily_metrics.revenue_native = room_revenue).
    This is accommodation revenue only — matches Cloudbeds dashboard exactly.
    """
    rev_native, _ = _get_revenue_from_insights(db, branch_id, year, month)
    return rev_native


def get_actual_revenue_vnd(db: Session, branch_id: UUID, year: int, month: int) -> float:
    """Revenue in VND from Cloudbeds Insights (daily_metrics)."""
    _, rev_vnd = _get_revenue_from_insights(db, branch_id, year, month)
    return rev_vnd


def calculate_achievement_pct(actual: float, target: float) -> Optional[float]:
    """Return actual/target as a decimal (e.g. 0.85 = 85%). None if no target."""
    if not target:
        return None
    return round(actual / target, 4)


# ── public API ─────────────────────────────────────────────────────────────────

def compute_next_month_forecast(
    db: Session,
    branch_id: UUID,
    total_rooms: int,
    cur_year: int,
    cur_month: int,
    total_room_count: int = 0,
    total_dorm_count: int = 0,
) -> dict:
    """
    Forecast revenue for NEXT month using NEXT month's own ADR from reservation_daily.
    Formula:
      Predict Room Sold = Round(total_days x num_rooms x Predict_OCC, 0)
      Forecast Revenue = Next Month ADR x Predict Room Sold
    For room+dorm split: calculate room and dorm separately.
    """
    next_month = cur_month + 1 if cur_month < 12 else 1
    next_year = cur_year if cur_month < 12 else cur_year + 1
    total_days = _days_in_month(next_year, next_month)
    first_day_next = date(next_year, next_month, 1)
    last_day_next = date(next_year, next_month, total_days)

    # ── Next-month ADR & revenue from Cloudbeds Insights API (live) ──────
    has_split = total_room_count > 0 and total_dorm_count > 0

    room_adr = dorm_adr = None
    room_rev = dorm_rev = 0.0
    room_sold = dorm_sold = 0

    # Live call to Cloudbeds Insights API for next month
    total_revenue, total_sold, total_adr = _get_insights_live(
        db, branch_id, next_year, next_month,
    )

    # Room/Dorm split still from reservation_daily (Insights doesn't split)
    if has_split:
        room_adr, dorm_adr, room_rev, room_sold, dorm_rev, dorm_sold = \
            _get_room_dorm_adr_from_daily(db, branch_id, first_day_next, last_day_next)

    # For rooms-only branches, room_adr = total_adr
    if total_room_count > 0 and total_dorm_count == 0:
        room_adr = total_adr

    # ── Predicted OCC for next month ──────────────────────────────────────
    target_row = (
        db.query(KPITarget)
        .filter_by(branch_id=branch_id, year=next_year, month=next_month)
        .first()
    )
    predicted_occ_next = float(target_row.predicted_occ_pct) if (target_row and target_row.predicted_occ_pct) else None
    predicted_room_occ_next = float(target_row.predicted_room_occ_pct) if (target_row and target_row.predicted_room_occ_pct) else None
    predicted_dorm_occ_next = float(target_row.predicted_dorm_occ_pct) if (target_row and target_row.predicted_dorm_occ_pct) else None
    next_month_target = float(target_row.target_revenue_native) if (target_row and target_row.target_revenue_native) else None

    # ── Forecast ──────────────────────────────────────────────────────────
    room_forecast = dorm_forecast = None
    forecast = None

    can_split = (has_split
                 and predicted_room_occ_next is not None
                 and predicted_dorm_occ_next is not None)

    if can_split and room_adr and dorm_adr:
        # Predict Room Sold = Round(total_days x num_rooms x Predict_OCC, 0)
        pred_room_sold = round(total_days * total_room_count * predicted_room_occ_next)
        pred_dorm_sold = round(total_days * total_dorm_count * predicted_dorm_occ_next)
        # Forecast Revenue = ADR x Predict Room Sold
        room_forecast = round(room_adr * pred_room_sold, 2)
        dorm_forecast = round(dorm_adr * pred_dorm_sold, 2)
        forecast = round(room_forecast + dorm_forecast, 2)
    elif total_adr and predicted_occ_next and total_rooms > 0:
        pred_sold = round(total_days * total_rooms * predicted_occ_next)
        forecast = round(total_adr * pred_sold, 2)

    return {
        "next_year": next_year,
        "next_month": next_month,
        "next_month_target_native": next_month_target,
        "next_month_adr": round(total_adr, 2) if total_adr else None,
        "next_month_room_adr": room_adr,
        "next_month_dorm_adr": dorm_adr,
        "next_month_booked_revenue": round(total_revenue, 2),
        "next_month_booked_nights": total_sold,
        "predicted_occ_next": predicted_occ_next,
        "predicted_room_occ_next": predicted_room_occ_next,
        "predicted_dorm_occ_next": predicted_dorm_occ_next,
        "next_month_forecast_native": forecast,
        "next_month_room_forecast": room_forecast,
        "next_month_dorm_forecast": dorm_forecast,
        "next_month_forecast_room_adr": room_adr,
        "next_month_forecast_dorm_adr": dorm_adr,
    }


def compute_kpi_summary(
    db: Session,
    branch_id: UUID,
    year: int,
    month: int,
    total_rooms: int,
    total_room_count: int = 0,
    total_dorm_count: int = 0,
) -> dict:
    """
    Return full KPI summary dict for a branch/month.
    Revenue & ADR from reservation_daily. Excludes House use, Blogger, Special case.
    Forecast = ADR x Round(total_days x num_rooms x predicted_occ, 0).
    """
    today = _today()
    total_days = _days_in_month(year, month)
    first_day = date(year, month, 1)
    last_day = date(year, month, total_days)

    # Days elapsed in this month (cap at total_days)
    if today.year == year and today.month == month:
        days_elapsed = today.day
    elif (year, month) < (today.year, today.month):
        days_elapsed = total_days
    else:
        days_elapsed = 0

    # Target
    target_row = (
        db.query(KPITarget)
        .filter_by(branch_id=branch_id, year=year, month=month)
        .first()
    )

    target_revenue_native = float(target_row.target_revenue_native) if target_row else None
    target_revenue_vnd = float(target_row.target_revenue_vnd) if target_row else None
    predicted_occ_pct = float(target_row.predicted_occ_pct) if (target_row and target_row.predicted_occ_pct) else None
    predicted_room_occ = float(target_row.predicted_room_occ_pct) if (target_row and target_row.predicted_room_occ_pct) else None
    predicted_dorm_occ = float(target_row.predicted_dorm_occ_pct) if (target_row and target_row.predicted_dorm_occ_pct) else None

    # ── Actuals from Cloudbeds Insights API (live call) ───────────────────
    actual_native, total_sold, avg_adr = _get_insights_live(db, branch_id, year, month)
    # VND conversion
    from app.services.cloudbeds import get_cached_rate
    from app.models.branch import Branch
    branch_obj = db.query(Branch).filter_by(id=branch_id).first()
    vnd_rate = get_cached_rate(branch_obj.currency or "USD", "VND") if branch_obj else None
    actual_vnd = round(actual_native * vnd_rate, 2) if vnd_rate and actual_native else 0.0

    # Room/Dorm split ADR — still from reservation_daily (Insights doesn't split)
    room_adr = dorm_adr = None
    has_split = total_room_count > 0 and total_dorm_count > 0

    room_rev = dorm_rev = 0.0
    room_sold = dorm_sold = 0

    if has_split:
        room_adr, dorm_adr, room_rev, room_sold, dorm_rev, dorm_sold = \
            _get_room_dorm_adr_from_daily(db, branch_id, first_day, last_day)
    elif total_room_count > 0 and total_dorm_count == 0:
        room_adr = avg_adr

    avg_occ = predicted_occ_pct

    # ── Forecasts ─────────────────────────────────────────────────────────
    # Forecast = ADR x Round(total_days x num_rooms x predicted_occ, 0)
    room_forecast = dorm_forecast = None
    occ_forecast = None

    can_split = (has_split
                 and predicted_room_occ is not None
                 and predicted_dorm_occ is not None)

    if can_split and room_adr and dorm_adr:
        pred_room_sold = round(total_days * total_room_count * predicted_room_occ)
        pred_dorm_sold = round(total_days * total_dorm_count * predicted_dorm_occ)
        room_forecast = round(room_adr * pred_room_sold, 2)
        dorm_forecast = round(dorm_adr * pred_dorm_sold, 2)
        occ_forecast = round(room_forecast + dorm_forecast, 2)
    elif avg_adr and predicted_occ_pct and total_rooms > 0:
        pred_sold = round(total_days * total_rooms * predicted_occ_pct)
        occ_forecast = round(avg_adr * pred_sold, 2)

    # Achievement
    achievement_pct = calculate_achievement_pct(actual_native, target_revenue_native)

    return {
        "branch_id": str(branch_id),
        "year": year,
        "month": month,
        "total_days": total_days,
        "days_elapsed": days_elapsed,
        # Target
        "target_revenue_native": target_revenue_native,
        "target_revenue_vnd": target_revenue_vnd,
        "predicted_occ_pct": predicted_occ_pct,
        "predicted_room_occ_pct": predicted_room_occ,
        "predicted_dorm_occ_pct": predicted_dorm_occ,
        # Actuals
        "actual_revenue_native": round(actual_native, 2),
        "actual_revenue_vnd": round(actual_vnd, 2),
        "avg_occ_pct": round(avg_occ, 4) if avg_occ is not None else None,
        "avg_adr_native": round(avg_adr, 2) if avg_adr is not None else None,
        "room_adr_native": room_adr,
        "dorm_adr_native": dorm_adr,
        "nights_booked": total_sold,
        # KPI
        "achievement_pct": achievement_pct,
        # Forecasts
        "occ_forecast_native": occ_forecast,
        "room_forecast_native": room_forecast,
        "dorm_forecast_native": dorm_forecast,
        "forecast_room_adr": room_adr,
        "forecast_dorm_adr": dorm_adr,
        # Room/Dorm capability flag
        "has_room_dorm_split": can_split and room_adr is not None and dorm_adr is not None,
    }
