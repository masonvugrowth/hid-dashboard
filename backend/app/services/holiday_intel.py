"""
Holiday Intelligence service — business logic for Phase 5.
Manages holiday calendar queries, season scoring, and booking cross-reference.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.holiday_intel import HolidayCalendar, TravelSeasonIndex

logger = logging.getLogger(__name__)

# ── Score weights (adjustable by team) ──────────────────────────────────────
WEIGHT_LONG_HOLIDAY = Decimal("1.5")
WEIGHT_HOLIDAY_COUNT = Decimal("0.5")
WEIGHT_SCHOOL_BREAK = Decimal("2.0")
SCORE_CAP = Decimal("10.0")


def get_season_matrix(db: Session) -> list[dict]:
    """
    Returns 25-country x 12-month grid from travel_season_index.
    Each cell: { country_code, month, season_score, peak_label, holiday_names }
    """
    rows = (
        db.query(TravelSeasonIndex)
        .order_by(TravelSeasonIndex.country_code, TravelSeasonIndex.month)
        .all()
    )
    return [
        {
            "country_code": r.country_code,
            "month": r.month,
            "season_score": float(r.season_score),
            "peak_label": r.peak_label,
            "holiday_count": r.holiday_count,
            "long_holiday_days": r.long_holiday_days,
            "holiday_names": r.holiday_names or [],
        }
        for r in rows
    ]


def get_country_holidays(db: Session, country_code: str) -> list[dict]:
    """
    Full holiday list for one country, ordered by month_start.
    """
    rows = (
        db.query(HolidayCalendar)
        .filter(HolidayCalendar.country_code == country_code.upper())
        .order_by(HolidayCalendar.month_start, HolidayCalendar.day_start)
        .all()
    )
    now = datetime.now()
    result = []
    for r in rows:
        # Calculate days until next occurrence (approximate)
        start_month = r.month_start
        target_year = now.year
        if start_month < now.month or (start_month == now.month and (r.day_start or 1) < now.day):
            target_year += 1
        try:
            next_date = datetime(target_year, start_month, r.day_start or 1)
            days_until = (next_date - now).days
        except ValueError:
            days_until = None

        result.append({
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
            "days_until_next": days_until,
        })
    return result


def get_upcoming_windows(db: Session, days_ahead: int = 60) -> list[dict]:
    """
    Returns holiday windows opening in the next N days across all markets.
    Sorted by travel_propensity DESC, proximity ASC.
    """
    now = datetime.now()
    all_holidays = db.query(HolidayCalendar).all()

    upcoming = []
    for h in all_holidays:
        start_month = h.month_start
        target_year = now.year
        if start_month < now.month or (start_month == now.month and (h.day_start or 1) < now.day):
            target_year += 1
        try:
            next_date = datetime(target_year, start_month, h.day_start or 1)
            days_until = (next_date - now).days
        except ValueError:
            continue

        if 0 <= days_until <= days_ahead:
            upcoming.append({
                "country_code": h.country_code,
                "country_name": h.country_name,
                "holiday_name": h.holiday_name,
                "holiday_type": h.holiday_type,
                "month_start": h.month_start,
                "day_start": h.day_start,
                "month_end": h.month_end,
                "day_end": h.day_end,
                "duration_days": h.duration_days,
                "travel_propensity": h.travel_propensity,
                "days_until": days_until,
            })

    # Sort: HIGH first, then closest date
    propensity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    upcoming.sort(key=lambda x: (propensity_order.get(x["travel_propensity"], 3), x["days_until"]))
    return upcoming


def get_month_opportunities(db: Session, month: int) -> list[dict]:
    """
    For a given month: which countries are PEAK or SHOULDER?
    Returns rows from travel_season_index where peak_label != OFF.
    """
    rows = (
        db.query(TravelSeasonIndex)
        .filter(
            TravelSeasonIndex.month == month,
            TravelSeasonIndex.peak_label.in_(["PEAK", "SHOULDER"]),
        )
        .order_by(TravelSeasonIndex.season_score.desc())
        .all()
    )
    return [
        {
            "country_code": r.country_code,
            "month": r.month,
            "season_score": float(r.season_score),
            "peak_label": r.peak_label,
            "holiday_count": r.holiday_count,
            "long_holiday_days": r.long_holiday_days,
            "holiday_names": r.holiday_names or [],
        }
        for r in rows
    ]


def recompute_season_index(db: Session) -> int:
    """
    Recalculates travel_season_index from holiday_calendars using the score formula.
    Returns number of rows upserted.
    """
    all_holidays = db.query(HolidayCalendar).all()

    # Build country x month grid
    grid: dict[tuple[str, int], dict] = {}
    for h in all_holidays:
        # A holiday may span multiple months
        for m in range(h.month_start, (h.month_end if h.month_end >= h.month_start else h.month_end + 12) + 1):
            actual_month = m if m <= 12 else m - 12
            key = (h.country_code, actual_month)
            if key not in grid:
                grid[key] = {
                    "holiday_count": 0,
                    "long_holiday_days": 0,
                    "school_break_overlap": 0,
                    "holiday_names": [],
                }
            cell = grid[key]
            cell["holiday_count"] += 1
            cell["holiday_names"].append(h.holiday_name)
            if h.is_long_holiday:
                cell["long_holiday_days"] += h.duration_days
            if h.holiday_type == "school_break":
                cell["school_break_overlap"] += 1

    count = 0
    for (code, month), cell in grid.items():
        score = (
            Decimal(str(cell["long_holiday_days"])) * WEIGHT_LONG_HOLIDAY
            + Decimal(str(cell["holiday_count"])) * WEIGHT_HOLIDAY_COUNT
            + Decimal(str(cell["school_break_overlap"])) * WEIGHT_SCHOOL_BREAK
        )
        score = min(score, SCORE_CAP)

        if score >= 7:
            label = "PEAK"
        elif score >= 4:
            label = "SHOULDER"
        else:
            label = "OFF"

        # Deduplicate names
        names = list(dict.fromkeys(cell["holiday_names"]))

        existing = (
            db.query(TravelSeasonIndex)
            .filter_by(country_code=code, month=month)
            .first()
        )
        if existing:
            existing.season_score = score
            existing.holiday_count = cell["holiday_count"]
            existing.long_holiday_days = cell["long_holiday_days"]
            existing.peak_label = label
            existing.holiday_names = names
            existing.computed_at = datetime.now(timezone.utc)
        else:
            db.add(TravelSeasonIndex(
                country_code=code,
                month=month,
                season_score=score,
                holiday_count=cell["holiday_count"],
                long_holiday_days=cell["long_holiday_days"],
                peak_label=label,
                holiday_names=names,
            ))
        count += 1

    db.commit()
    logger.info("Season index recomputed — %d cells updated", count)
    return count


def cross_reference_bookings(db: Session, country_code: str, month: int) -> dict:
    """
    Compare holiday calendar data vs actual reservation data.
    Queries reservations by guest_country_code.
    """
    # Get season index data
    season = (
        db.query(TravelSeasonIndex)
        .filter_by(country_code=country_code.upper(), month=month)
        .first()
    )
    expected_peak = season.peak_label == "PEAK" if season else False

    # Query reservations table for this country + month
    result = db.execute(
        text("""
            SELECT COUNT(*) AS booking_count
            FROM reservations
            WHERE status != 'Cancelled'
              AND guest_country_code = :code
              AND EXTRACT(MONTH FROM check_in_date) = :month
        """),
        {"code": country_code.upper(), "month": month},
    ).fetchone()

    booking_count = result[0] if result else 0

    # Determine if this is an actual peak (above average)
    avg_result = db.execute(
        text("""
            SELECT AVG(cnt) FROM (
                SELECT COUNT(*) AS cnt
                FROM reservations
                WHERE status != 'Cancelled'
                  AND guest_country_code = :code
                GROUP BY EXTRACT(MONTH FROM check_in_date)
            ) sub
        """),
        {"code": country_code.upper()},
    ).fetchone()

    avg_bookings = float(avg_result[0]) if avg_result and avg_result[0] else 0
    actual_peak = booking_count > avg_bookings * 1.2 if avg_bookings > 0 else False

    return {
        "country_code": country_code.upper(),
        "month": month,
        "expected_peak": expected_peak,
        "actual_peak": actual_peak,
        "match": expected_peak == actual_peak,
        "booking_count": booking_count,
        "avg_monthly_bookings": round(avg_bookings, 1),
        "holiday_names": season.holiday_names if season else [],
        "season_score": float(season.season_score) if season else 0,
    }
