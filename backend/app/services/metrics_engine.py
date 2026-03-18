"""
Metrics Engine — v1.5
Both OCC and Revenue attributed to CHECK-IN DATE:
  - OCC     = rooms checking in on date / total_rooms
  - Revenue = sum(grand_total_native) for check-ins on date
Monthly aggregates therefore match Cloudbeds / Google Sheet totals exactly.
Business exclusion filters applied permanently (not configurable):
  - status: cancelled, canceled, no_show, no show, no-show
  - source: house use, blogger, kol, day use, maintenance
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
EXCLUDED_STATUSES = {"cancelled", "canceled", "no_show", "noshow", "no show", "no-show"}
EXCLUDED_SOURCES  = {"house use", "blogger", "kol", "day use", "maintain", "maintenance", "houseuse", "dayuse"}


def _is_excluded(reservation: Reservation) -> bool:
    status = (reservation.status or "").lower().strip()
    source = (reservation.source or "").lower().strip()
    # Normalise both hyphen and underscore variants so all forms match
    status_norm = status.replace("-", "_").replace(" ", "_")
    return (
        status in EXCLUDED_STATUSES
        or status_norm in EXCLUDED_STATUSES
        or source in EXCLUDED_SOURCES
    )


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
    Both OCC and Revenue attributed to CHECK-IN DATE:
      - Only reservations checking in on target_date are counted
      - OCC  = rooms checking in / total_rooms
      - Revenue = sum(grand_total_native) for check-ins on target_date
    This matches Cloudbeds / Google Sheet monthly totals.
    Upserts into daily_metrics table.
    """
    total_rooms: int = branch.total_rooms or 0
    total_room_count: int = branch.total_room_count or 0
    total_dorm_count: int = branch.total_dorm_count or 0

    # Only reservations checking IN on target_date (check-in date attribution)
    all_res = db.query(Reservation).filter(
        Reservation.branch_id == branch.id,
        Reservation.check_in_date == target_date,
    ).all()

    # Apply exclusion filters (v2 business rules — permanent, not configurable)
    checkin_res = [r for r in all_res if not _is_excluded(r)]

    # Split by room type for separate room/dorm OCC
    room_res = [r for r in checkin_res if (r.room_type_category or "").lower() == "room"]
    dorm_res = [r for r in checkin_res if (r.room_type_category or "").lower() == "dorm"]

    # Room-night expansion → distinct room counts checking in today
    rooms_occupied = _room_night_expand(room_res)
    dorms_occupied = _room_night_expand(dorm_res)

    rooms_sold = len(rooms_occupied)
    dorms_sold = len(dorms_occupied)
    total_sold = rooms_sold + dorms_sold

    # OCC% — based on check-ins today (consistent with revenue attribution)
    occ_pct       = round(total_sold / total_rooms, 4) if total_rooms > 0 else 0.0
    room_occ_pct  = round(rooms_sold / total_room_count, 4) if total_room_count > 0 else None
    dorm_occ_pct  = round(dorms_sold / total_dorm_count, 4) if total_dorm_count > 0 else None

    # Revenue — full grand_total for check-ins on target_date
    revenue_native = round(sum(float(r.grand_total_native or 0) for r in checkin_res), 2)
    revenue_vnd    = round(sum(float(r.grand_total_vnd or 0) for r in checkin_res), 2)

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

    # 1. All reservations with check_in_date in the date range (check-in date attribution)
    raw_res = db.query(Reservation).filter(
        Reservation.branch_id == branch.id,
        Reservation.check_in_date >= date_from,
        Reservation.check_in_date <= date_to,
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

    # Pre-index valid reservations by check-in date for O(1) revenue lookup
    from collections import defaultdict as _defaultdict
    checkin_map: dict = _defaultdict(list)
    for r in valid_res:
        if r.check_in_date is not None:
            checkin_map[r.check_in_date].append(r)

    while current <= date_to:
        # Both OCC and Revenue use check-in date attribution
        checkin_res = checkin_map.get(current, [])

        room_res = [r for r in checkin_res if (r.room_type_category or "").lower() == "room"]
        dorm_res = [r for r in checkin_res if (r.room_type_category or "").lower() == "dorm"]

        rooms_occupied = _room_night_expand(room_res)
        dorms_occupied = _room_night_expand(dorm_res)

        rooms_sold = len(rooms_occupied)
        dorms_sold = len(dorms_occupied)
        total_sold = rooms_sold + dorms_sold

        occ_pct      = round(total_sold / total_rooms, 4) if total_rooms > 0 else 0.0
        room_occ_pct = round(rooms_sold / total_room_count, 4) if total_room_count > 0 else None
        dorm_occ_pct = round(dorms_sold / total_dorm_count, 4) if total_dorm_count > 0 else None

        revenue_native = round(sum(float(r.grand_total_native or 0) for r in checkin_res), 2)
        revenue_vnd    = round(sum(float(r.grand_total_vnd or 0) for r in checkin_res), 2)
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
    """Channel mix by individual OTA source (Direct aggregated, OTA broken out by name)."""
    q = db.query(
        Reservation.source,
        Reservation.source_category,
        func.count(Reservation.id).label("count"),
        func.coalesce(func.sum(Reservation.grand_total_native), 0).label("revenue_native"),
        func.coalesce(func.sum(Reservation.grand_total_vnd), 0).label("revenue_vnd"),
    ).filter(
        Reservation.check_in_date >= date_from,
        Reservation.check_in_date <= date_to,
        func.lower(Reservation.status).notin_(list(EXCLUDED_STATUSES)),
        func.lower(Reservation.source).notin_(list(EXCLUDED_SOURCES)),
    )
    if branch_id:
        q = q.filter(Reservation.branch_id == branch_id)

    rows = q.group_by(Reservation.source, Reservation.source_category).all()

    channels: dict = {}
    for row in rows:
        cat = row.source_category or "OTA"
        key = "Direct" if cat == "Direct" else (row.source or "Unknown")
        if key not in channels:
            channels[key] = {"count": 0, "revenue_native": 0.0, "revenue_vnd": 0.0, "category": cat}
        channels[key]["count"] += row.count
        channels[key]["revenue_native"] += float(row.revenue_native)
        channels[key]["revenue_vnd"] += float(row.revenue_vnd)
    return channels


def get_channel_rates(
    db: Session,
    branch_id: Optional[UUID],
    date_from: date,
    date_to: date,
) -> list[dict]:
    """Cancellation rate and check-in rate by channel (individual OTA source or Direct).
    Includes ALL statuses so cancelled bookings count toward the totals.
    """
    from sqlalchemy import case as sa_case

    q = db.query(
        Reservation.source,
        Reservation.source_category,
        func.count(Reservation.id).label("total"),
        func.sum(sa_case((Reservation.status.in_(["cancelled", "canceled"]), 1), else_=0)).label("cancelled"),
        func.sum(sa_case((Reservation.status.in_(["no_show", "noshow"]), 1), else_=0)).label("no_show"),
        func.sum(sa_case((Reservation.status.in_(["checked_in", "checked_out"]), 1), else_=0)).label("checked_in"),
    ).filter(
        Reservation.check_in_date >= date_from,
        Reservation.check_in_date <= date_to,
        func.lower(Reservation.source).notin_(list(EXCLUDED_SOURCES)),
    )
    if branch_id:
        q = q.filter(Reservation.branch_id == branch_id)

    rows = q.group_by(Reservation.source, Reservation.source_category).all()

    channels: dict = {}
    for row in rows:
        cat = row.source_category or "OTA"
        key = "Direct" if cat == "Direct" else (row.source or "Unknown")
        if key not in channels:
            channels[key] = {"total": 0, "cancelled": 0, "no_show": 0, "checked_in": 0, "category": cat}
        channels[key]["total"]      += row.total
        channels[key]["cancelled"]  += int(row.cancelled or 0)
        channels[key]["no_show"]    += int(row.no_show or 0)
        channels[key]["checked_in"] += int(row.checked_in or 0)

    result = []
    for channel, v in sorted(channels.items(), key=lambda x: -x[1]["total"]):
        total        = v["total"]
        cancelled    = v["cancelled"]
        no_show      = v["no_show"]
        checked_in   = v["checked_in"]
        non_cancelled = total - cancelled
        result.append({
            "channel":      channel,
            "category":     v["category"],
            "total":        total,
            "cancelled":    cancelled,
            "no_show":      no_show,
            "checked_in":   checked_in,
            "confirmed":    max(0, non_cancelled - no_show - checked_in),
            "cancel_rate":  round(cancelled / total, 4) if total > 0 else 0,
            "checkin_rate": round(checked_in / non_cancelled, 4) if non_cancelled > 0 else 0,
            "noshow_rate":  round(no_show / non_cancelled, 4) if non_cancelled > 0 else 0,
        })
    return result


def get_ota_trend(
    db: Session,
    branch_id: Optional[UUID],
    mode: str = "daily",
) -> dict:
    """OTA channel share pivot table.
    mode: daily (last 7 days) | weekly (last 7 weeks) | monthly (last 3 months)
    Returns: periods (labels) × channels (rows) with count + pct per cell.
    """
    from collections import defaultdict

    today = date.today()

    if mode == "daily":
        date_from = today - timedelta(days=6)
    elif mode == "weekly":
        start_of_this_week = today - timedelta(days=today.weekday())
        date_from = start_of_this_week - timedelta(weeks=6)
    else:  # monthly
        m, y = today.month - 2, today.year
        while m <= 0:
            m += 12; y -= 1
        date_from = date(y, m, 1)

    # Choose period expression
    if mode == "daily":
        period_expr = Reservation.check_in_date
    elif mode == "weekly":
        period_expr = func.date_trunc("week", Reservation.check_in_date)
    else:
        period_expr = func.date_trunc("month", Reservation.check_in_date)

    q = db.query(
        period_expr.label("period"),
        Reservation.source,
        Reservation.source_category,
        func.count(Reservation.id).label("count"),
    ).filter(
        Reservation.check_in_date >= date_from,
        Reservation.check_in_date <= today,
        Reservation.status.notin_(list(EXCLUDED_STATUSES)),
        func.lower(Reservation.source).notin_(list(EXCLUDED_SOURCES)),
    )
    if branch_id:
        q = q.filter(Reservation.branch_id == branch_id)
    q = q.group_by(period_expr, Reservation.source, Reservation.source_category)
    rows = q.all()

    # Normalize period keys → date objects
    period_channel: dict = defaultdict(lambda: defaultdict(int))
    all_channels: set = set()
    for row in rows:
        cat = row.source_category or "OTA"
        channel = "Direct" if cat == "Direct" else (row.source or "Unknown")
        p = row.period
        if hasattr(p, "date"):
            p = p.date()
        elif not isinstance(p, date):
            p = date.fromisoformat(str(p)[:10])
        period_channel[p][channel] += row.count
        all_channels.add(channel)

    # Build canonical period list
    if mode == "daily":
        periods = [today - timedelta(days=i) for i in range(6, -1, -1)]
        labels  = [d.strftime("%b %d") for d in periods]
    elif mode == "weekly":
        start_of_this_week = today - timedelta(days=today.weekday())
        periods = [start_of_this_week - timedelta(weeks=i) for i in range(6, -1, -1)]
        labels  = [f"W{d.isocalendar()[1]:02d} ({d.strftime('%m/%d')})" for d in periods]
    else:
        periods = []
        for i in range(2, -1, -1):
            m, y = today.month - i, today.year
            while m <= 0:
                m += 12; y -= 1
            periods.append(date(y, m, 1))
        labels = [d.strftime("%b %Y") for d in periods]

    # Sort: OTAs by total desc, Direct always last
    channel_totals: dict = defaultdict(int)
    for pc in period_channel.values():
        for ch, cnt in pc.items():
            channel_totals[ch] += cnt

    sorted_channels = sorted(all_channels - {"Direct"}, key=lambda c: -channel_totals[c])
    if "Direct" in all_channels:
        sorted_channels.append("Direct")

    # Build result
    result_channels = []
    for channel in sorted_channels:
        cells = []
        for p in periods:
            cnt = period_channel.get(p, {}).get(channel, 0)
            period_total = sum(period_channel.get(p, {}).values())
            pct = cnt / period_total if period_total > 0 else 0
            cells.append({"count": cnt, "pct": round(pct, 4)})
        result_channels.append({
            "channel":   channel,
            "is_direct": channel == "Direct",
            "total":     channel_totals[channel],
            "cells":     cells,
        })

    return {"mode": mode, "periods": labels, "channels": result_channels}


def get_rates_trend(
    db: Session,
    branch_id: Optional[UUID],
    mode: str = "daily",
) -> dict:
    """Cancel rate & check-in rate pivot: per channel × per time period.
    mode: daily (last 7 days) | weekly (last 7 weeks) | monthly (last 3 months)
    """
    from collections import defaultdict
    from sqlalchemy import case as sa_case

    today = date.today()

    if mode == "daily":
        date_from = today - timedelta(days=6)
    elif mode == "weekly":
        start_of_this_week = today - timedelta(days=today.weekday())
        date_from = start_of_this_week - timedelta(weeks=6)
    else:
        m, y = today.month - 2, today.year
        while m <= 0:
            m += 12; y -= 1
        date_from = date(y, m, 1)

    if mode == "daily":
        period_expr = Reservation.check_in_date
    elif mode == "weekly":
        period_expr = func.date_trunc("week", Reservation.check_in_date)
    else:
        period_expr = func.date_trunc("month", Reservation.check_in_date)

    q = db.query(
        period_expr.label("period"),
        Reservation.source,
        Reservation.source_category,
        func.count(Reservation.id).label("total"),
        func.sum(sa_case((Reservation.status.in_(["cancelled", "canceled"]), 1), else_=0)).label("cancelled"),
        func.sum(sa_case((Reservation.status.in_(["no_show", "noshow"]), 1), else_=0)).label("no_show"),
        func.sum(sa_case((Reservation.status.in_(["checked_in", "checked_out"]), 1), else_=0)).label("checked_in"),
    ).filter(
        Reservation.check_in_date >= date_from,
        Reservation.check_in_date <= today,
        func.lower(Reservation.source).notin_(list(EXCLUDED_SOURCES)),
    )
    if branch_id:
        q = q.filter(Reservation.branch_id == branch_id)
    q = q.group_by(period_expr, Reservation.source, Reservation.source_category)
    rows = q.all()

    # Aggregate into period × channel buckets
    _empty = lambda: {"total": 0, "cancelled": 0, "no_show": 0, "checked_in": 0}
    period_channel: dict = defaultdict(lambda: defaultdict(_empty))
    all_channels: set = set()

    for row in rows:
        cat = row.source_category or "OTA"
        channel = "Direct" if cat == "Direct" else (row.source or "Unknown")
        p = row.period
        if hasattr(p, "date"):
            p = p.date()
        elif not isinstance(p, date):
            p = date.fromisoformat(str(p)[:10])
        d = period_channel[p][channel]
        d["total"]      += row.total
        d["cancelled"]  += int(row.cancelled or 0)
        d["no_show"]    += int(row.no_show or 0)
        d["checked_in"] += int(row.checked_in or 0)
        all_channels.add(channel)

    # Build canonical period list
    if mode == "daily":
        periods = [today - timedelta(days=i) for i in range(6, -1, -1)]
        labels  = [d.strftime("%b %d") for d in periods]
    elif mode == "weekly":
        start_of_this_week = today - timedelta(days=today.weekday())
        periods = [start_of_this_week - timedelta(weeks=i) for i in range(6, -1, -1)]
        labels  = [f"W{d.isocalendar()[1]:02d} ({d.strftime('%m/%d')})" for d in periods]
    else:
        periods = []
        for i in range(2, -1, -1):
            m, y = today.month - i, today.year
            while m <= 0:
                m += 12; y -= 1
            periods.append(date(y, m, 1))
        labels = [d.strftime("%b %Y") for d in periods]

    # Sort: OTAs by total desc, Direct always last
    channel_totals: dict = defaultdict(int)
    for pc in period_channel.values():
        for ch, v in pc.items():
            channel_totals[ch] += v["total"]

    sorted_channels = sorted(all_channels - {"Direct"}, key=lambda c: -channel_totals[c])
    if "Direct" in all_channels:
        sorted_channels.append("Direct")

    # Pre-compute total checked_in across ALL channels per period
    period_total_checkin: dict = {}
    for p in periods:
        period_total_checkin[p] = sum(
            (period_channel.get(p, {}).get(ch) or _empty())["checked_in"]
            for ch in all_channels
        )

    result_channels = []
    for channel in sorted_channels:
        cancel_cells  = []
        checkin_cells = []
        for p in periods:
            v = period_channel.get(p, {}).get(channel) or _empty()
            total         = v["total"]
            cancelled     = v["cancelled"]
            total_ckin    = period_total_checkin.get(p, 0)
            cancel_cells.append({
                "total":     total,
                "cancelled": cancelled,
                "rate":      round(cancelled / total, 4) if total > 0 else None,
            })
            # Check-in rate = channel checked_in / ALL channels checked_in (this period)
            checkin_cells.append({
                "total":      total_ckin,
                "checked_in": v["checked_in"],
                "rate":       round(v["checked_in"] / total_ckin, 4) if total_ckin > 0 else None,
            })
        result_channels.append({
            "channel":       channel,
            "is_direct":     channel == "Direct",
            "total":         channel_totals[channel],
            "cancel_cells":  cancel_cells,
            "checkin_cells": checkin_cells,
        })

    return {"mode": mode, "periods": labels, "channels": result_channels}


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
