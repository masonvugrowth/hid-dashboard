"""
Metrics Engine — v1.3
OCC computed via room-night expansion from raw reservations.
Business exclusion filters applied permanently (not configurable):
  - status: cancelled, canceled, no_show
  - source: house use, blogger, kol, day use, maintain
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.daily_metrics import DailyMetrics
from app.models.reservation import Reservation

logger = logging.getLogger(__name__)

# ── Exclusion filter constants ─────────────────────────────────────────────────
EXCLUDED_STATUSES = {"cancelled", "canceled", "no_show", "noshow"}
EXCLUDED_SOURCES  = {"house use", "blogger", "kol", "day use", "maintain", "maintenance", "houseuse", "dayuse"}


def _is_excluded(reservation: Reservation) -> bool:
    status = (reservation.status or "").lower().replace("-", "_")
    source = (reservation.source or "").lower().strip()
    return status in EXCLUDED_STATUSES or source in EXCLUDED_SOURCES


def _room_night_expand(reservations) -> set[str]:
    """
    Room-night expansion: split comma-separated room_number fields,
    return set of distinct room identifiers occupied.
    v2 spec: rooms_sold = COUNT(DISTINCT room) across all valid reservations.
    Works with both ORM Reservation objects and lightweight _ResProxy objects.
    """
    rooms: set[str] = set()
    for r in reservations:
        room_num = getattr(r, "room_number", None)
        if not room_num:
            rooms.add(str(r.id))
            continue
        for rm in str(room_num).split(","):
            rm = rm.strip()
            if rm:
                rooms.add(rm)
    return rooms


# ── per-day aggregation ────────────────────────────────────────────────────────

def compute_day(db: Session, branch: Branch, target_date: date) -> DailyMetrics:
    """
    Aggregate reservations for one branch on one date → DailyMetrics row.
    Uses room-night expansion per v2 spec, with source/status exclusion filters.
    Upserts into daily_metrics table.
    """
    total_rooms: int = branch.total_rooms or 0
    total_room_count: int = branch.total_room_count or 0
    total_dorm_count: int = branch.total_dorm_count or 0

    # All reservations spanning target_date (check_in <= date < check_out)
    all_res = db.query(Reservation).filter(
        Reservation.branch_id == branch.id,
        Reservation.check_in_date <= target_date,
        Reservation.check_out_date > target_date,
    ).all()

    # Apply exclusion filters (v2 business rules — permanent, not configurable)
    valid_res = [r for r in all_res if not _is_excluded(r)]

    # Split by room type for separate room/dorm OCC
    room_res = [r for r in valid_res if (r.room_type_category or "").lower() == "room"]
    dorm_res = [r for r in valid_res if (r.room_type_category or "").lower() == "dorm"]

    # Room-night expansion → distinct room counts
    rooms_occupied = _room_night_expand(room_res)
    dorms_occupied = _room_night_expand(dorm_res)

    rooms_sold = len(rooms_occupied)
    dorms_sold = len(dorms_occupied)
    total_sold = rooms_sold + dorms_sold

    # OCC%
    occ_pct       = round(total_sold / total_rooms, 4) if total_rooms > 0 else 0.0
    room_occ_pct  = round(rooms_sold / total_room_count, 4) if total_room_count > 0 else None
    dorm_occ_pct  = round(dorms_sold / total_dorm_count, 4) if total_dorm_count > 0 else None

    # Revenue — spread nightly across stay
    def _nightly_revenue(res_list, col_native=True) -> float:
        total = 0.0
        for r in res_list:
            nights = max(int(r.nights or 1), 1)
            val = float(r.grand_total_native or 0) if col_native else float(r.grand_total_vnd or 0)
            total += val / nights
        return round(total, 2)

    revenue_native = _nightly_revenue(valid_res, col_native=True)
    revenue_vnd    = _nightly_revenue(valid_res, col_native=False)

    # ADR and RevPAR (in native currency)
    adr_native    = round(revenue_native / total_sold, 2) if total_sold > 0 else 0.0
    revpar_native = round(revenue_native / total_rooms, 2) if total_rooms > 0 else 0.0

    # New bookings made on this date
    new_bookings = db.query(Reservation).filter(
        Reservation.branch_id == branch.id,
        Reservation.reservation_date == target_date,
    ).count()

    # Cancellations recorded on this date
    cancellations = db.query(Reservation).filter(
        Reservation.branch_id == branch.id,
        Reservation.cancellation_date == target_date,
    ).count()

    total_activity = new_bookings + cancellations
    cancellation_pct = round(cancellations / total_activity, 4) if total_activity > 0 else 0.0

    # Upsert
    dm = db.query(DailyMetrics).filter_by(branch_id=branch.id, date=target_date).first()
    if not dm:
        dm = DailyMetrics(branch_id=branch.id, date=target_date)
        db.add(dm)

    dm.rooms_sold        = rooms_sold
    dm.dorms_sold        = dorms_sold
    dm.total_sold        = total_sold
    dm.occ_pct           = occ_pct
    dm.room_occ_pct      = room_occ_pct
    dm.dorm_occ_pct      = dorm_occ_pct
    dm.revenue_native    = revenue_native
    dm.revenue_vnd       = revenue_vnd
    dm.adr_native        = adr_native
    dm.revpar_native     = revpar_native
    dm.new_bookings      = new_bookings
    dm.cancellations     = cancellations
    dm.cancellation_pct  = cancellation_pct
    dm.computed_at       = datetime.now(timezone.utc)

    db.commit()
    db.refresh(dm)
    return dm


def recompute_branch_range(
    db: Session,
    branch: Branch,
    date_from: date,
    date_to: date,
) -> int:
    """
    Fast bulk recompute: fetches all reservations once, computes in Python,
    then bulk-upserts. Reduces DB round trips from O(days×4) to O(1) per branch.
    """
    from collections import defaultdict

    total_rooms: int = branch.total_rooms or 0
    total_room_count: int = branch.total_room_count or 0
    total_dorm_count: int = branch.total_dorm_count or 0

    # ── Fetch all data in 3 queries, then detach from session ─────────────────

    class _ResProxy:
        """Lightweight plain-Python copy of a Reservation row — session-independent."""
        __slots__ = ("id", "status", "source", "room_number", "room_type_category",
                     "check_in_date", "check_out_date", "nights",
                     "grand_total_native", "grand_total_vnd")

        def __init__(self, r: Reservation):
            self.id                = r.id
            self.status            = r.status
            self.source            = r.source
            self.room_number       = r.room_number
            self.room_type_category = r.room_type_category
            self.check_in_date     = r.check_in_date
            self.check_out_date    = r.check_out_date
            self.nights            = r.nights
            self.grand_total_native = r.grand_total_native
            self.grand_total_vnd   = r.grand_total_vnd

    # 1. All reservations that overlap the date range (copy to proxies immediately)
    raw_res = db.query(Reservation).filter(
        Reservation.branch_id == branch.id,
        Reservation.check_in_date <= date_to,
        Reservation.check_out_date > date_from,
    ).all()
    all_res = [_ResProxy(r) for r in raw_res]

    # 2. All reservation_dates / cancellation_dates in range
    booking_res = db.query(Reservation).filter(
        Reservation.branch_id == branch.id,
        Reservation.reservation_date >= date_from,
        Reservation.reservation_date <= date_to,
    ).with_entities(Reservation.reservation_date).all()

    cancel_res = db.query(Reservation).filter(
        Reservation.branch_id == branch.id,
        Reservation.cancellation_date >= date_from,
        Reservation.cancellation_date <= date_to,
    ).with_entities(Reservation.cancellation_date).all()

    # ── Precompute day-indexed lookups ─────────────────────────────────────────

    new_bookings_map: dict[date, int] = defaultdict(int)
    for (rd,) in booking_res:
        if rd:
            new_bookings_map[rd] += 1

    cancellations_map: dict[date, int] = defaultdict(int)
    for (cd,) in cancel_res:
        if cd:
            cancellations_map[cd] += 1

    valid_res = [r for r in all_res if not _is_excluded(r)]

    # ── Iterate days in Python (no more DB queries) ───────────────────────────

    current = date_from
    new_dms: list[DailyMetrics] = []
    update_dms: list[DailyMetrics] = []
    count = 0

    # Load existing daily_metrics for this range to decide insert vs update
    existing_map: dict[date, DailyMetrics] = {
        dm.date: dm
        for dm in db.query(DailyMetrics).filter(
            DailyMetrics.branch_id == branch.id,
            DailyMetrics.date >= date_from,
            DailyMetrics.date <= date_to,
        ).all()
    }

    while current <= date_to:
        # Reservations spanning this date
        day_res = [
            r for r in valid_res
            if r.check_in_date <= current < r.check_out_date
        ]

        room_res = [r for r in day_res if (r.room_type_category or "").lower() == "room"]
        dorm_res = [r for r in day_res if (r.room_type_category or "").lower() == "dorm"]

        rooms_occupied = _room_night_expand(room_res)
        dorms_occupied = _room_night_expand(dorm_res)

        rooms_sold = len(rooms_occupied)
        dorms_sold = len(dorms_occupied)
        total_sold = rooms_sold + dorms_sold

        occ_pct      = round(total_sold / total_rooms, 4) if total_rooms > 0 else 0.0
        room_occ_pct = round(rooms_sold / total_room_count, 4) if total_room_count > 0 else None
        dorm_occ_pct = round(dorms_sold / total_dorm_count, 4) if total_dorm_count > 0 else None

        def _nightly(res_list, col_native=True) -> float:
            total = 0.0
            for r in res_list:
                nights = max(int(r.nights or 1), 1)
                val = float(r.grand_total_native or 0) if col_native else float(r.grand_total_vnd or 0)
                total += val / nights
            return round(total, 2)

        revenue_native = _nightly(day_res, col_native=True)
        revenue_vnd    = _nightly(day_res, col_native=False)
        adr_native     = round(revenue_native / total_sold, 2) if total_sold > 0 else 0.0
        revpar_native  = round(revenue_native / total_rooms, 2) if total_rooms > 0 else 0.0

        new_bookings  = new_bookings_map.get(current, 0)
        cancellations = cancellations_map.get(current, 0)
        total_activity = new_bookings + cancellations
        cancellation_pct = round(cancellations / total_activity, 4) if total_activity > 0 else 0.0

        dm = existing_map.get(current)
        if not dm:
            dm = DailyMetrics(branch_id=branch.id, date=current)
            db.add(dm)

        dm.rooms_sold       = rooms_sold
        dm.dorms_sold       = dorms_sold
        dm.total_sold       = total_sold
        dm.occ_pct          = occ_pct
        dm.room_occ_pct     = room_occ_pct
        dm.dorm_occ_pct     = dorm_occ_pct
        dm.revenue_native   = revenue_native
        dm.revenue_vnd      = revenue_vnd
        dm.adr_native       = adr_native
        dm.revpar_native    = revpar_native
        dm.new_bookings     = new_bookings
        dm.cancellations    = cancellations
        dm.cancellation_pct = cancellation_pct
        dm.computed_at      = datetime.now(timezone.utc)

        current += timedelta(days=1)
        count += 1

        # Commit in batches of 90 days to avoid holding large transactions
        if count % 90 == 0:
            db.commit()

    db.commit()
    return count


async def nightly_metrics_job(db_factory) -> None:
    """Async nightly job: recompute yesterday for all active branches."""
    db: Session = db_factory()
    try:
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        branches = db.query(Branch).filter_by(is_active=True).all()
        for branch in branches:
            try:
                compute_day(db, branch, yesterday)
                logger.info(f"Metrics OK branch={branch.name} date={yesterday}")
            except Exception as e:
                logger.error(f"Metrics FAIL branch={branch.name}: {e}")
    finally:
        db.close()


# ── query helpers ──────────────────────────────────────────────────────────────

def get_daily_metrics(
    db: Session,
    branch_id: Optional[UUID],
    date_from: date,
    date_to: date,
) -> list[DailyMetrics]:
    q = db.query(DailyMetrics).filter(
        DailyMetrics.date >= date_from,
        DailyMetrics.date <= date_to,
    )
    if branch_id:
        q = q.filter(DailyMetrics.branch_id == branch_id)
    return q.order_by(DailyMetrics.branch_id, DailyMetrics.date).all()


def get_ota_mix(
    db: Session,
    branch_id: Optional[UUID],
    date_from: date,
    date_to: date,
) -> dict:
    q = db.query(
        Reservation.source_category,
        func.count(Reservation.id).label("count"),
        func.coalesce(func.sum(Reservation.grand_total_native), 0).label("revenue_native"),
        func.coalesce(func.sum(Reservation.grand_total_vnd), 0).label("revenue_vnd"),
    ).filter(
        Reservation.check_in_date >= date_from,
        Reservation.check_in_date <= date_to,
        Reservation.status.notin_(list(EXCLUDED_STATUSES)),
    )
    if branch_id:
        q = q.filter(Reservation.branch_id == branch_id)

    rows = q.group_by(Reservation.source_category).all()
    return {
        (row.source_category or "Unknown"): {
            "count": row.count,
            "revenue_native": float(row.revenue_native),
            "revenue_vnd": float(row.revenue_vnd),
        }
        for row in rows
    }


def get_country_yoy(
    db: Session,
    branch_id: Optional[UUID],
    year: int,
    month: Optional[int] = None,
) -> list[dict]:
    results = []
    for y in [year - 1, year]:
        q = db.query(
            Reservation.guest_country_code,
            Reservation.guest_country,
            func.count(Reservation.id).label("count"),
            func.coalesce(func.sum(Reservation.grand_total_native), 0).label("revenue_native"),
        ).filter(
            func.extract("year", Reservation.check_in_date) == y,
            Reservation.status.notin_(list(EXCLUDED_STATUSES)),
        )
        if branch_id:
            q = q.filter(Reservation.branch_id == branch_id)
        if month:
            q = q.filter(func.extract("month", Reservation.check_in_date) == month)

        rows = q.group_by(
            Reservation.guest_country_code, Reservation.guest_country,
        ).order_by(func.count(Reservation.id).desc()).all()

        results.extend({
            "year": y,
            "country_code": row.guest_country_code,
            "country": row.guest_country,
            "count": row.count,
            "revenue_native": float(row.revenue_native),
        } for row in rows)
    return results
