"""
KPI Engine — v2.2 (Cloudbeds Insights-based ADR)
Calculates KPI achievement %, run-rate forecast, and OCC-based forecast.

Revenue & ADR: sourced from daily_metrics (synced from Cloudbeds Data Insights API).
Forecast formula:
  Current ADR = Current Revenue / Current Rooms Sold (from Cloudbeds Insights)
  Predicted Room Sold = predicted_occ × inventory × total_days
  Forecast = Predicted Room Sold × Current ADR
  (Separate for Room and Dorm, then summed)
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.daily_metrics import DailyMetrics
from app.models.kpi import KPITarget
from app.models.reservation import Reservation
from app.models.reservation_daily import ReservationDaily

# Statuses excluded from reservation queries (cancel rate denominator, etc.)
_EXCLUDED_STATUSES = {"cancelled", "canceled", "no_show", "noshow", "no show", "no-show"}

# Sources excluded from revenue queries (for _revenue_query helper)
_EXCLUDED_SOURCES  = {
    "blogger", "house use", "houseuse", "kol",
    "special case",
    "maintenance", "maintain",
}

# Sources excluded from ADR calculation only (revenue numerator)
# OCC / Rooms Sold: NO source exclusion
_ADR_EXCLUDED_SOURCES = {"blogger", "house use", "houseuse", "special case"}


# ── helpers ────────────────────────────────────────────────────────────────────

def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _revenue_query(db: Session, branch_id: UUID, year: int, month: int):
    """
    Base query: reservations with check_in_date in month, excluding bad
    statuses and internal sources. Returns a SQLAlchemy query.
    """
    first_day = date(year, month, 1)
    last_day  = date(year, month, _days_in_month(year, month))
    return (
        db.query(Reservation)
        .filter(
            Reservation.branch_id     == branch_id,
            Reservation.check_in_date >= first_day,
            Reservation.check_in_date <= last_day,
            # NULL status = not yet set → treat as valid (not excluded)
            or_(
                Reservation.status == None,
                Reservation.status.notin_(list(_EXCLUDED_STATUSES)),
            ),
            # NULL source = unknown → not excluded; only exclude known internal sources
            ~func.lower(func.coalesce(Reservation.source, "")).in_(list(_EXCLUDED_SOURCES)),
        )
    )


def _get_excluded_source_revenue(
    db: Session, branch_id: UUID, first_day: date, last_day: date,
) -> tuple[float, float, float]:
    """
    Revenue from ADR-excluded sources (blogger, house use, special case)
    via reservation_daily. Returns (total_excluded, room_excluded, dorm_excluded).
    Non-cancelled reservations only.
    """
    from app.models.reservation_daily import ReservationDaily

    base = (
        db.query(ReservationDaily)
        .join(Reservation, ReservationDaily.reservation_id == Reservation.id)
        .filter(
            ReservationDaily.branch_id == branch_id,
            ReservationDaily.date >= first_day,
            ReservationDaily.date <= last_day,
            func.lower(Reservation.source).in_(list(_ADR_EXCLUDED_SOURCES)),
            ~func.lower(func.coalesce(Reservation.status, "")).in_(list(_EXCLUDED_STATUSES)),
        )
    )

    total = float(
        base.with_entities(func.coalesce(func.sum(ReservationDaily.nightly_rate), 0)).scalar() or 0
    )
    room_excl = float(
        base.filter(func.lower(ReservationDaily.room_type_category) == "room")
        .with_entities(func.coalesce(func.sum(ReservationDaily.nightly_rate), 0)).scalar() or 0
    )
    dorm_excl = float(
        base.filter(func.lower(ReservationDaily.room_type_category) == "dorm")
        .with_entities(func.coalesce(func.sum(ReservationDaily.nightly_rate), 0)).scalar() or 0
    )
    return total, room_excl, dorm_excl


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


def _get_room_dorm_adr(
    db: Session, branch_id: UUID, first_day: date, last_day: date,
    exclude_adr_sources: bool = True,
) -> tuple[Optional[float], Optional[float]]:
    """
    Room/Dorm ADR from reservation_daily (same source for both revenue & nights).
    Excludes: cancelled/noshow statuses.
    When exclude_adr_sources=True (default, for display): also excludes blogger, house use, special case.
    When exclude_adr_sources=False (for forecast): includes all sources so ADR matches OCC scope.
    For Dorm: counts per-BED (not per-reservation), excludes combo bookings.
    Returns (room_adr, dorm_adr).
    """
    # ── Room ADR (simple: 1 reservation-night = 1 unit sold) ──────────────
    room_q = (
        db.query(
            func.coalesce(func.sum(ReservationDaily.nightly_rate), 0),
            func.count(ReservationDaily.id),
        )
        .join(Reservation, ReservationDaily.reservation_id == Reservation.id)
        .filter(
            ReservationDaily.branch_id == branch_id,
            ReservationDaily.date >= first_day,
            ReservationDaily.date <= last_day,
            func.lower(ReservationDaily.room_type_category) == "room",
            ~func.lower(func.coalesce(Reservation.status, "")).in_(list(_EXCLUDED_STATUSES)),
        )
    )
    if exclude_adr_sources:
        room_q = room_q.filter(
            ~func.lower(func.coalesce(Reservation.source, "")).in_(list(_ADR_EXCLUDED_SOURCES)),
        )
    room_row = room_q.one()
    room_rev = float(room_row[0])
    room_nights = int(room_row[1])
    room_adr = round(room_rev / room_nights, 2) if room_nights > 0 else None

    # ── Dorm ADR (per-bed: count beds from room_number, exclude combos) ───
    dorm_q = (
        db.query(
            ReservationDaily.nightly_rate,
            Reservation.room_number,
            Reservation.room_type,
        )
        .join(Reservation, ReservationDaily.reservation_id == Reservation.id)
        .filter(
            ReservationDaily.branch_id == branch_id,
            ReservationDaily.date >= first_day,
            ReservationDaily.date <= last_day,
            func.lower(ReservationDaily.room_type_category) == "dorm",
            ~func.lower(func.coalesce(Reservation.status, "")).in_(list(_EXCLUDED_STATUSES)),
        )
    )
    if exclude_adr_sources:
        dorm_q = dorm_q.filter(
            ~func.lower(func.coalesce(Reservation.source, "")).in_(list(_ADR_EXCLUDED_SOURCES)),
        )
    dorm_rows = dorm_q.all()

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

    return room_adr, dorm_adr


def _get_room_dorm_adr_from_reservations(
    db: Session, branch_id: UUID, year: int, month: int,
    total_dorm_count: int,
) -> tuple[Optional[float], Optional[float]]:
    """
    Room/Dorm ADR from Reservations table (grand_total / nights).
    Uses room_type_category on Reservation for the split.
    For Dorm: ADR per BED = (grand_total / nights) / avg_beds_per_booking.
    Always complete (no sparse data issue like reservation_daily for future months).
    """
    base = _revenue_query(db, branch_id, year, month)

    # Room ADR
    room_row = base.filter(
        func.lower(Reservation.room_type_category) == "room",
    ).with_entities(
        func.coalesce(func.sum(Reservation.grand_total_native), 0),
        func.coalesce(func.sum(Reservation.nights), 0),
    ).one()
    room_rev = float(room_row[0])
    room_nights = int(room_row[1])
    room_adr = round(room_rev / room_nights, 2) if room_nights > 0 else None

    # Dorm ADR (per-bed: divide by average beds per dorm booking)
    dorm_row = base.filter(
        func.lower(Reservation.room_type_category) == "dorm",
    ).with_entities(
        func.coalesce(func.sum(Reservation.grand_total_native), 0),
        func.coalesce(func.sum(Reservation.nights), 0),
        func.count(Reservation.id),
    ).one()
    dorm_rev = float(dorm_row[0])
    dorm_nights = int(dorm_row[1])

    if dorm_nights > 0:
        # Count total beds from room_number to get per-bed ADR
        dorm_bookings = base.filter(
            func.lower(Reservation.room_type_category) == "dorm",
        ).with_entities(
            Reservation.room_number,
            Reservation.nights,
            Reservation.grand_total_native,
        ).all()

        total_bed_nights = 0
        total_dorm_rev = 0.0
        for booking in dorm_bookings:
            beds = _count_dorm_beds(booking.room_number)
            total_bed_nights += beds * int(booking.nights or 1)
            total_dorm_rev += float(booking.grand_total_native or 0)

        dorm_adr = round(total_dorm_rev / total_bed_nights, 2) if total_bed_nights > 0 else None
    else:
        dorm_adr = None

    return room_adr, dorm_adr


# ── core calculations ──────────────────────────────────────────────────────────

def get_actual_revenue(db: Session, branch_id: UUID, year: int, month: int) -> float:
    """
    Revenue from reservations with check-in in this month (matches Cloudbeds report).
    Excludes cancelled/noshow and internal sources.
    """
    row = (
        _revenue_query(db, branch_id, year, month)
        .with_entities(func.coalesce(func.sum(Reservation.grand_total_native), 0))
        .scalar()
    )
    return float(row or 0)


def get_actual_revenue_vnd(db: Session, branch_id: UUID, year: int, month: int) -> float:
    """Revenue in VND from reservations with check-in in this month."""
    row = (
        _revenue_query(db, branch_id, year, month)
        .with_entities(func.coalesce(func.sum(Reservation.grand_total_vnd), 0))
        .scalar()
    )
    return float(row or 0)


def calculate_achievement_pct(actual: float, target: float) -> Optional[float]:
    """Return actual/target as a decimal (e.g. 0.85 = 85%). None if no target."""
    if not target:
        return None
    return round(actual / target, 4)



def calculate_occ_forecast(
    predicted_occ_pct: Optional[float],
    actual_revenue_so_far: float,
    days_elapsed: int,
    total_days: int,
    total_rooms: int,
    avg_rate_native: Optional[float] = None,
    actual_avg_occ_pct: Optional[float] = None,
) -> Optional[float]:
    """
    OCC-based forecast: predicted_occ * total_rooms * ADR * total_days.
    ADR = SUM(revenue) / SUM(rooms_sold) — true weighted ADR (industry standard).
    Fallback: derive from actual_revenue / (days_elapsed * total_rooms * actual_occ).
    """
    if predicted_occ_pct is None or total_rooms <= 0:
        return None

    # Use pre-computed weighted ADR from DailyMetrics
    if avg_rate_native and avg_rate_native > 0:
        adr = avg_rate_native
    # Fallback: derive ADR from actual revenue + actual OCC (not predicted)
    elif actual_avg_occ_pct and actual_avg_occ_pct > 0 and days_elapsed > 0:
        occupied_so_far = days_elapsed * total_rooms * actual_avg_occ_pct
        adr = actual_revenue_so_far / occupied_so_far if occupied_so_far > 0 else 0
    elif days_elapsed > 0 and total_rooms > 0 and actual_revenue_so_far > 0:
        # Last resort: assume predicted OCC matches actual (least accurate)
        occupied_so_far = days_elapsed * total_rooms * float(predicted_occ_pct)
        adr = actual_revenue_so_far / occupied_so_far if occupied_so_far > 0 else 0
    else:
        return None

    if adr <= 0:
        return None

    forecasted = float(predicted_occ_pct) * total_rooms * adr * total_days
    return round(forecasted, 2)


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
    Forecast revenue for next month using:
      - ADR derived from reservations already booked with check-in in next month
        ADR = SUM(grand_total_native) / SUM(nights)  [industry-standard weighted ADR]
      - predicted_occ_pct from KPITarget for next month
      - If room/dorm split available: forecast = room_forecast + dorm_forecast
      - Fallback: forecast = predicted_occ * total_rooms * ADR * days
    """
    next_month = cur_month + 1 if cur_month < 12 else 1
    next_year  = cur_year if cur_month < 12 else cur_year + 1
    total_days = _days_in_month(next_year, next_month)
    first_day_next = date(next_year, next_month, 1)
    last_day_next = date(next_year, next_month, total_days)

    # ── Next-month booked revenue (for display) ────────────────────────
    base_q = _revenue_query(db, branch_id, next_year, next_month)
    rev_row = base_q.with_entities(
        func.sum(Reservation.grand_total_native),
        func.sum(Reservation.nights),
    ).one()
    total_revenue = float(rev_row[0] or 0)
    total_nights = int(rev_row[1] or 0)

    # ── Next-month ADR from Reservations (grand_total / nights — always complete) ──
    adr = round(total_revenue / total_nights, 2) if total_nights > 0 else None

    # Room/Dorm split ADR from Reservations (using room_type_category)
    room_adr = dorm_adr = None
    forecast_room_adr = forecast_dorm_adr = None
    if total_room_count > 0 and total_dorm_count > 0:
        room_adr, dorm_adr = _get_room_dorm_adr_from_reservations(
            db, branch_id, next_year, next_month, total_dorm_count,
        )
        forecast_room_adr = room_adr
        forecast_dorm_adr = dorm_adr
    elif total_room_count > 0 and total_dorm_count == 0:
        room_adr = adr
        forecast_room_adr = adr

    # Predicted OCC for next month
    target_row = (
        db.query(KPITarget)
        .filter_by(branch_id=branch_id, year=next_year, month=next_month)
        .first()
    )
    predicted_occ_next = float(target_row.predicted_occ_pct) if (target_row and target_row.predicted_occ_pct) else None
    predicted_room_occ_next = float(target_row.predicted_room_occ_pct) if (target_row and target_row.predicted_room_occ_pct) else None
    predicted_dorm_occ_next = float(target_row.predicted_dorm_occ_pct) if (target_row and target_row.predicted_dorm_occ_pct) else None
    next_month_target = float(target_row.target_revenue_native) if (target_row and target_row.target_revenue_native) else None

    # Try split forecast first — use forecast ADR (no source exclusion)
    room_forecast = dorm_forecast = None
    forecast = None
    has_split = (total_room_count > 0 and total_dorm_count > 0
                 and predicted_room_occ_next is not None
                 and predicted_dorm_occ_next is not None)

    if has_split and forecast_room_adr and forecast_dorm_adr:
        room_forecast = round(predicted_room_occ_next * total_room_count * forecast_room_adr * total_days, 2)
        dorm_forecast = round(predicted_dorm_occ_next * total_dorm_count * forecast_dorm_adr * total_days, 2)
        forecast = round(room_forecast + dorm_forecast, 2)
    elif adr and predicted_occ_next and total_rooms > 0:
        forecast = round(predicted_occ_next * total_rooms * adr * total_days, 2)

    return {
        "next_year": next_year,
        "next_month": next_month,
        "next_month_target_native": next_month_target,
        "next_month_adr": round(adr, 2) if adr else None,
        "next_month_room_adr": room_adr,
        "next_month_dorm_adr": dorm_adr,
        "next_month_booked_revenue": round(total_revenue, 2),
        "next_month_booked_nights": total_nights,
        "predicted_occ_next": predicted_occ_next,
        "predicted_room_occ_next": predicted_room_occ_next,
        "predicted_dorm_occ_next": predicted_dorm_occ_next,
        "next_month_forecast_native": forecast,
        "next_month_room_forecast": room_forecast,
        "next_month_dorm_forecast": dorm_forecast,
        "next_month_forecast_room_adr": forecast_room_adr,
        "next_month_forecast_dorm_adr": forecast_dorm_adr,
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
    If room/dorm split is available: forecast = room_forecast + dorm_forecast.
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

    # Actuals
    actual_native = get_actual_revenue(db, branch_id, year, month)
    actual_vnd = get_actual_revenue_vnd(db, branch_id, year, month)

    # Nights booked this month (non-cancelled reservations with check-in in month)
    nights_row = (
        _revenue_query(db, branch_id, year, month)
        .with_entities(func.coalesce(func.sum(Reservation.nights), 0))
        .scalar()
    )
    nights_booked = int(nights_row or 0)

    # ADR from Reservations (grand_total / nights — always complete, matches Cloudbeds)
    rev_adr_row = (
        _revenue_query(db, branch_id, year, month)
        .with_entities(
            func.coalesce(func.sum(Reservation.grand_total_native), 0),
            func.coalesce(func.sum(Reservation.nights), 0),
        )
        .one()
    )
    adr_total_rev = float(rev_adr_row[0])
    adr_total_nights = int(rev_adr_row[1])
    avg_adr = round(adr_total_rev / adr_total_nights, 2) if adr_total_nights > 0 else None

    # Room/Dorm ADR from Reservations (using room_type_category)
    room_adr = dorm_adr = None
    forecast_room_adr = forecast_dorm_adr = None
    if total_room_count > 0 and total_dorm_count > 0:
        room_adr, dorm_adr = _get_room_dorm_adr_from_reservations(
            db, branch_id, year, month, total_dorm_count,
        )
        forecast_room_adr = room_adr
        forecast_dorm_adr = dorm_adr
    elif total_room_count > 0 and total_dorm_count == 0:
        room_adr = avg_adr
        forecast_room_adr = avg_adr

    avg_occ = predicted_occ_pct

    # Forecasts — try split first, fall back to single
    # Use forecast ADR (no source exclusion) so forecast matches OCC scope
    room_forecast = dorm_forecast = None
    has_split = (total_room_count > 0 and total_dorm_count > 0
                 and predicted_room_occ is not None
                 and predicted_dorm_occ is not None)

    if has_split and forecast_room_adr and forecast_dorm_adr:
        room_forecast = round(predicted_room_occ * total_room_count * forecast_room_adr * total_days, 2)
        dorm_forecast = round(predicted_dorm_occ * total_dorm_count * forecast_dorm_adr * total_days, 2)
        occ_forecast = round(room_forecast + dorm_forecast, 2)
    else:
        occ_forecast = calculate_occ_forecast(
            predicted_occ_pct,
            actual_native,
            days_elapsed,
            total_days,
            total_rooms,
            avg_adr,
            actual_avg_occ_pct=avg_occ,
        )

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
        "nights_booked": nights_booked,
        # KPI
        "achievement_pct": achievement_pct,
        # Forecasts
        "occ_forecast_native": occ_forecast,
        "room_forecast_native": room_forecast,
        "dorm_forecast_native": dorm_forecast,
        "forecast_room_adr": forecast_room_adr,
        "forecast_dorm_adr": forecast_dorm_adr,
        # Room/Dorm capability flag
        "has_room_dorm_split": has_split and room_adr is not None and dorm_adr is not None,
    }
