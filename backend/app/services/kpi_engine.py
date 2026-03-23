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


def _get_room_dorm_adr(
    db: Session, branch_id: UUID, first_day: date, last_day: date,
) -> tuple[Optional[float], Optional[float]]:
    """
    Room/Dorm ADR from reservation_daily (same source for both revenue & nights).
    Excludes: cancelled/noshow statuses + ADR-excluded sources (blogger, house use, special case).
    Returns (room_adr, dorm_adr).
    """
    result = {}
    for cat in ("room", "dorm"):
        row = (
            db.query(
                func.coalesce(func.sum(ReservationDaily.nightly_rate), 0),
                func.count(ReservationDaily.id),
            )
            .join(Reservation, ReservationDaily.reservation_id == Reservation.id)
            .filter(
                ReservationDaily.branch_id == branch_id,
                ReservationDaily.date >= first_day,
                ReservationDaily.date <= last_day,
                func.lower(ReservationDaily.room_type_category) == cat,
                ~func.lower(func.coalesce(Reservation.status, "")).in_(list(_EXCLUDED_STATUSES)),
                ~func.lower(func.coalesce(Reservation.source, "")).in_(list(_ADR_EXCLUDED_SOURCES)),
            )
            .one()
        )
        rev = float(row[0])
        nights = int(row[1])
        result[cat] = round(rev / nights, 2) if nights > 0 else None

    return result["room"], result["dorm"]


# ── core calculations ──────────────────────────────────────────────────────────

def get_actual_revenue(db: Session, branch_id: UUID, year: int, month: int) -> float:
    """
    Full-month revenue using daily_metrics (per-night prorated).
    Covers all days in the month — including future days already in DB
    from upcoming confirmed reservations — so current month shows the
    full-month total, not just MTD.
    """
    first_day = date(year, month, 1)
    last_day = date(year, month, _days_in_month(year, month))

    result = db.query(
        func.coalesce(func.sum(DailyMetrics.revenue_native), 0)
    ).filter(
        DailyMetrics.branch_id == branch_id,
        DailyMetrics.date >= first_day,
        DailyMetrics.date <= last_day,
    ).scalar()
    return float(result or 0)


def get_actual_revenue_vnd(db: Session, branch_id: UUID, year: int, month: int) -> float:
    """Full-month revenue in VND using daily_metrics (per-night prorated)."""
    first_day = date(year, month, 1)
    last_day = date(year, month, _days_in_month(year, month))

    result = db.query(
        func.coalesce(func.sum(DailyMetrics.revenue_vnd), 0)
    ).filter(
        DailyMetrics.branch_id == branch_id,
        DailyMetrics.date >= first_day,
        DailyMetrics.date <= last_day,
    ).scalar()
    return float(result or 0)


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

    # Overall ADR from daily_metrics (Cloudbeds Insights — includes future confirmed bookings)
    metrics_agg = db.query(
        func.coalesce(func.sum(DailyMetrics.revenue_native), 0),
        func.coalesce(func.sum(DailyMetrics.total_sold), 0),
    ).filter(
        DailyMetrics.branch_id == branch_id,
        DailyMetrics.date >= first_day_next,
        DailyMetrics.date <= last_day_next,
    ).one()

    dm_revenue = float(metrics_agg[0])
    dm_sold = int(metrics_agg[1])

    # Subtract ADR-excluded source revenue (blogger, house use, special case)
    excl_total, _, _ = _get_excluded_source_revenue(db, branch_id, first_day_next, last_day_next)

    # Use daily_metrics if Insights data exists for next month, else fall back to reservations
    if dm_sold > 0:
        total_revenue = dm_revenue
        total_nights = dm_sold
        adr = round((dm_revenue - excl_total) / dm_sold, 2)
    else:
        # FALLBACK: ADR from already-booked next-month reservations
        base_q = _revenue_query(db, branch_id, next_year, next_month)
        rows = base_q.with_entities(
            func.sum(Reservation.grand_total_native),
            func.sum(Reservation.nights),
        ).one()
        total_revenue = float(rows[0] or 0)
        total_nights = int(rows[1] or 0)
        adr = round(total_revenue / total_nights, 2) if total_nights > 0 else None

    # Room/Dorm ADR from reservation_daily (same source for revenue & nights)
    room_adr = dorm_adr = None
    if total_room_count > 0 and total_dorm_count > 0:
        room_adr, dorm_adr = _get_room_dorm_adr(db, branch_id, first_day_next, last_day_next)

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

    # Try split forecast first
    room_forecast = dorm_forecast = None
    forecast = None
    has_split = (total_room_count > 0 and total_dorm_count > 0
                 and predicted_room_occ_next is not None
                 and predicted_dorm_occ_next is not None)

    if has_split and room_adr and dorm_adr:
        room_forecast = round(predicted_room_occ_next * total_room_count * room_adr * total_days, 2)
        dorm_forecast = round(predicted_dorm_occ_next * total_dorm_count * dorm_adr * total_days, 2)
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

    # Overall ADR from Cloudbeds Insights (full month)
    # Revenue for ADR: exclude blogger, house use, special case
    # Rooms Sold (denominator): NO source exclusion
    metrics_agg = db.query(
        func.coalesce(func.sum(DailyMetrics.revenue_native), 0),
        func.coalesce(func.sum(DailyMetrics.total_sold), 0),
    ).filter(
        DailyMetrics.branch_id == branch_id,
        DailyMetrics.date >= first_day,
        DailyMetrics.date <= last_day,
    ).one()

    total_revenue_dm = float(metrics_agg[0])
    total_sold_dm = int(metrics_agg[1])       # no source exclusion

    # Subtract revenue from ADR-excluded sources (blogger, house use, special case)
    excl_total, _, _ = _get_excluded_source_revenue(db, branch_id, first_day, last_day)
    adr_revenue = total_revenue_dm - excl_total

    # Overall ADR = (Insights Revenue − excluded sources) / Insights Rooms Sold
    avg_adr = round(adr_revenue / total_sold_dm, 2) if total_sold_dm > 0 else None

    # Room/Dorm ADR from reservation_daily (same source for both revenue & nights)
    # This avoids mismatch between Insights total_sold and compute_day rooms_sold/dorms_sold
    room_adr = dorm_adr = None
    if total_room_count > 0 and total_dorm_count > 0:
        room_adr, dorm_adr = _get_room_dorm_adr(db, branch_id, first_day, last_day)

    avg_occ = predicted_occ_pct

    # Forecasts — try split first, fall back to single
    room_forecast = dorm_forecast = None
    has_split = (total_room_count > 0 and total_dorm_count > 0
                 and predicted_room_occ is not None
                 and predicted_dorm_occ is not None)

    if has_split and room_adr and dorm_adr:
        room_forecast = round(predicted_room_occ * total_room_count * room_adr * total_days, 2)
        dorm_forecast = round(predicted_dorm_occ * total_dorm_count * dorm_adr * total_days, 2)
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
        # Room/Dorm capability flag
        "has_room_dorm_split": has_split and room_adr is not None and dorm_adr is not None,
    }
