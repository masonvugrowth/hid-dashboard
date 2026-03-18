"""
KPI Engine — Phase 2
Calculates KPI achievement %, run-rate forecast, and OCC-based forecast.

Revenue rule: sum grand_total_native for reservations with check_in_date in the
given month (full month, including future bookings already made).
Excludes: cancelled / no_show statuses and internal sources
(Blogger, House Use, KOL, Maintenance).
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

# Sources excluded from revenue (case-insensitive match against stored source)
_EXCLUDED_STATUSES = {"cancelled", "canceled", "no_show", "noshow"}
_EXCLUDED_SOURCES  = {
    "blogger", "house use", "houseuse", "kol",
    "maintenance", "maintain", "day use", "dayuse",
}


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
) -> dict:
    """
    Forecast revenue for next month using:
      - ADR derived from reservations already booked with check-in in next month
        ADR = SUM(grand_total_native) / SUM(nights)  [industry-standard weighted ADR]
      - predicted_occ_pct from KPITarget for next month
      - Forecast = predicted_occ * total_rooms * ADR * days_in_next_month
    """
    next_month = cur_month + 1 if cur_month < 12 else 1
    next_year  = cur_year if cur_month < 12 else cur_year + 1
    total_days = _days_in_month(next_year, next_month)

    # ADR from already-booked next-month reservations
    rows = (
        _revenue_query(db, branch_id, next_year, next_month)
        .with_entities(
            func.sum(Reservation.grand_total_native),
            func.sum(Reservation.nights),
        )
        .one()
    )
    total_revenue = float(rows[0] or 0)
    total_nights  = int(rows[1] or 0)
    adr = (total_revenue / total_nights) if total_nights > 0 else None

    # Predicted OCC for next month
    target_row = (
        db.query(KPITarget)
        .filter_by(branch_id=branch_id, year=next_year, month=next_month)
        .first()
    )
    predicted_occ_next = float(target_row.predicted_occ_pct) if (target_row and target_row.predicted_occ_pct) else None
    next_month_target = float(target_row.target_revenue_native) if (target_row and target_row.target_revenue_native) else None

    forecast = None
    if adr and predicted_occ_next and total_rooms > 0:
        forecast = round(predicted_occ_next * total_rooms * adr * total_days, 2)

    return {
        "next_year": next_year,
        "next_month": next_month,
        "next_month_target_native": next_month_target,
        "next_month_adr": round(adr, 2) if adr else None,
        "next_month_booked_revenue": round(total_revenue, 2),
        "next_month_booked_nights": total_nights,
        "predicted_occ_next": predicted_occ_next,
        "next_month_forecast_native": forecast,
    }


def compute_kpi_summary(
    db: Session,
    branch_id: UUID,
    year: int,
    month: int,
    total_rooms: int,
) -> dict:
    """
    Return full KPI summary dict for a branch/month.
    """
    today = _today()
    total_days = _days_in_month(year, month)

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

    # True ADR = SUM(grand_total_native) / SUM(nights) — nightly rate (industry standard)
    # Must use reservations directly, NOT daily_metrics, because daily_metrics.revenue_native
    # is now check-in attributed (full stay value on check-in night), so
    # revenue/rooms_sold would give full-stay ADR, not nightly rate.
    adr_res = (
        _revenue_query(db, branch_id, year, month)
        .with_entities(
            func.coalesce(func.sum(Reservation.grand_total_native), 0),
            func.coalesce(func.sum(Reservation.nights), 0),
        )
        .one()
    )
    adr_total_rev   = float(adr_res[0] or 0)
    adr_total_nights = int(adr_res[1] or 0)
    avg_adr = round(adr_total_rev / adr_total_nights, 2) if adr_total_nights > 0 else None

    # Actual OCC: use KPI target's predicted_occ as the best available estimate
    # (check-in based OCC from daily_metrics is much lower than traditional OCC
    #  and would produce wrong fallback ADR estimates)
    avg_occ = predicted_occ_pct

    # Forecasts
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
        # Actuals
        "actual_revenue_native": round(actual_native, 2),
        "actual_revenue_vnd": round(actual_vnd, 2),
        "avg_occ_pct": round(avg_occ, 4) if avg_occ is not None else None,
        "avg_adr_native": round(avg_adr, 2) if avg_adr is not None else None,
        "nights_booked": nights_booked,
        # KPI
        "achievement_pct": achievement_pct,
        # Forecasts
        "occ_forecast_native": occ_forecast,
    }
