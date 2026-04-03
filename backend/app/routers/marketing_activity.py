"""
Marketing Activity router — consolidated view of Paid Ads, KOL, and CRM performance.
"""
import re
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, extract
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.models.ads import AdsPerformance
from app.models.reservation import Reservation
from app.models.kol import KOLRecord

router = APIRouter()

_KOL_RE = re.compile(r"\(KOL_([^)]+)\)")
_CANCELLED = {"canceled", "cancelled", "no_show", "no-show", "cancelled_by_guest"}


def _envelope(data):
    return {
        "success": True,
        "data": data,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _crm_filter():
    """Filter for CRM-related room types/rate plans."""
    return or_(
        Reservation.room_type.ilike("%CRM%"),
        Reservation.rate_plan_name.ilike("%CRM%"),
        Reservation.room_type.ilike("%MEANDER'S FRIEND%"),
        Reservation.rate_plan_name.ilike("%MEANDER'S FRIEND%"),
        Reservation.room_type.ilike("%Travel guide%"),
        Reservation.rate_plan_name.ilike("%Travel guide%"),
        Reservation.room_type.ilike("%Grand Open%"),
        Reservation.rate_plan_name.ilike("%Grand Open%"),
    )


def _month_str(d) -> str:
    """Format a date-like object to 'YYYY-MM'."""
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m")
    return str(d)


@router.get("/summary")
def get_marketing_activity_summary(
    branch_id: Optional[UUID] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Consolidated marketing activity: overview KPIs, monthly breakdown by country,
    and KOL suggestions for paid ads.
    """
    # Default date range: year-to-date
    today = date.today()
    d_from = date.fromisoformat(date_from) if date_from else date(today.year, 1, 1)
    d_to = date.fromisoformat(date_to) if date_to else today

    overview = _build_overview(db, branch_id, d_from, d_to)
    monthly = _build_monthly_by_country(db, branch_id, d_from, d_to)
    suggestions = _build_kol_suggestions(db, branch_id, d_from, d_to)

    return _envelope({
        "overview": overview,
        "monthly_by_country": monthly,
        "kol_suggestions": suggestions,
    })


# ── Overview KPIs ────────────────────────────────────────────────────────────

def _build_overview(db: Session, branch_id: Optional[UUID], d_from: date, d_to: date):
    # Paid Ads
    ads_q = db.query(
        func.coalesce(func.sum(AdsPerformance.bookings), 0).label("bookings"),
        func.coalesce(func.sum(AdsPerformance.revenue_vnd), 0).label("revenue_vnd"),
        func.coalesce(func.sum(AdsPerformance.cost_vnd), 0).label("cost_vnd"),
    ).filter(
        AdsPerformance.date_from >= d_from,
        AdsPerformance.date_to <= d_to,
    )
    if branch_id:
        ads_q = ads_q.filter(AdsPerformance.branch_id == branch_id)
    ads_row = ads_q.one()
    ads_bookings = int(ads_row.bookings)
    ads_revenue = float(ads_row.revenue_vnd)
    ads_cost = float(ads_row.cost_vnd)
    ads_roas = round(ads_revenue / ads_cost, 2) if ads_cost > 0 else 0

    # KOL (from reservations with KOL_ room type)
    kol_q = db.query(
        func.count(Reservation.id).label("bookings"),
        func.coalesce(func.sum(Reservation.grand_total_vnd), 0).label("revenue_vnd"),
    ).filter(
        Reservation.room_type.ilike("%KOL_%"),
        Reservation.check_in_date >= d_from,
        Reservation.check_in_date <= d_to,
        ~Reservation.status.in_(["Cancelled", "Canceled", "No-Show", "No_Show"]),
    )
    if branch_id:
        kol_q = kol_q.filter(Reservation.branch_id == branch_id)
    kol_row = kol_q.one()
    kol_bookings = int(kol_row.bookings)
    kol_revenue = float(kol_row.revenue_vnd)

    # KOL cost (from kol_records)
    kol_cost_q = db.query(
        func.coalesce(func.sum(KOLRecord.cost_vnd), 0).label("cost_vnd"),
    )
    if branch_id:
        kol_cost_q = kol_cost_q.filter(KOLRecord.branch_id == branch_id)
    kol_cost = float(kol_cost_q.scalar() or 0)

    # CRM (from reservations with CRM filter)
    crm_q = db.query(
        func.count(Reservation.id).label("bookings"),
        func.coalesce(func.sum(Reservation.grand_total_vnd), 0).label("revenue_vnd"),
    ).filter(
        _crm_filter(),
        Reservation.check_in_date >= d_from,
        Reservation.check_in_date <= d_to,
        ~Reservation.status.in_(["Cancelled", "Canceled", "No-Show", "No_Show"]),
    )
    if branch_id:
        crm_q = crm_q.filter(Reservation.branch_id == branch_id)
    crm_row = crm_q.one()
    crm_bookings = int(crm_row.bookings)
    crm_revenue = float(crm_row.revenue_vnd)

    total_bookings = ads_bookings + kol_bookings + crm_bookings
    total_revenue = ads_revenue + kol_revenue + crm_revenue
    total_cost = ads_cost + kol_cost
    total_roas = round(total_revenue / total_cost, 2) if total_cost > 0 else 0

    return {
        "paid_ads": {
            "bookings": ads_bookings,
            "revenue_vnd": ads_revenue,
            "cost_vnd": ads_cost,
            "roas": ads_roas,
        },
        "kol": {
            "bookings": kol_bookings,
            "revenue_vnd": kol_revenue,
            "cost_vnd": kol_cost,
        },
        "crm": {
            "bookings": crm_bookings,
            "revenue_vnd": crm_revenue,
        },
        "total": {
            "bookings": total_bookings,
            "revenue_vnd": total_revenue,
            "cost_vnd": total_cost,
            "roas": total_roas,
        },
    }


# ── Monthly by Country ───────────────────────────────────────────────────────

def _build_monthly_by_country(db: Session, branch_id: Optional[UUID], d_from: date, d_to: date):
    """Build monthly × country breakdown of marketing activities."""
    # key = (month_str, country)
    grid = defaultdict(lambda: {
        "paid_ads": {"bookings": 0, "revenue_vnd": 0, "cost_vnd": 0},
        "kol": {"bookings": 0, "revenue_vnd": 0},
        "crm": {"bookings": 0, "revenue_vnd": 0},
    })

    # Paid Ads by month × target_country
    ads_q = db.query(
        extract("year", AdsPerformance.date_from).label("yr"),
        extract("month", AdsPerformance.date_from).label("mo"),
        AdsPerformance.target_country,
        func.coalesce(func.sum(AdsPerformance.bookings), 0),
        func.coalesce(func.sum(AdsPerformance.revenue_vnd), 0),
        func.coalesce(func.sum(AdsPerformance.cost_vnd), 0),
    ).filter(
        AdsPerformance.date_from >= d_from,
        AdsPerformance.date_to <= d_to,
    ).group_by("yr", "mo", AdsPerformance.target_country)
    if branch_id:
        ads_q = ads_q.filter(AdsPerformance.branch_id == branch_id)

    for yr, mo, country, bookings, rev, cost in ads_q.all():
        month_str = f"{int(yr)}-{int(mo):02d}"
        c = country or "Unknown"
        grid[(month_str, c)]["paid_ads"]["bookings"] += int(bookings)
        grid[(month_str, c)]["paid_ads"]["revenue_vnd"] += float(rev)
        grid[(month_str, c)]["paid_ads"]["cost_vnd"] += float(cost)

    # KOL by month × guest_country_code
    kol_q = db.query(
        extract("year", Reservation.check_in_date).label("yr"),
        extract("month", Reservation.check_in_date).label("mo"),
        Reservation.guest_country_code,
        func.count(Reservation.id),
        func.coalesce(func.sum(Reservation.grand_total_vnd), 0),
    ).filter(
        Reservation.room_type.ilike("%KOL_%"),
        Reservation.check_in_date >= d_from,
        Reservation.check_in_date <= d_to,
        ~Reservation.status.in_(["Cancelled", "Canceled", "No-Show", "No_Show"]),
    ).group_by("yr", "mo", Reservation.guest_country_code)
    if branch_id:
        kol_q = kol_q.filter(Reservation.branch_id == branch_id)

    for yr, mo, country, bookings, rev in kol_q.all():
        month_str = f"{int(yr)}-{int(mo):02d}"
        c = country or "Unknown"
        grid[(month_str, c)]["kol"]["bookings"] += int(bookings)
        grid[(month_str, c)]["kol"]["revenue_vnd"] += float(rev)

    # CRM by month × guest_country_code
    crm_q = db.query(
        extract("year", Reservation.check_in_date).label("yr"),
        extract("month", Reservation.check_in_date).label("mo"),
        Reservation.guest_country_code,
        func.count(Reservation.id),
        func.coalesce(func.sum(Reservation.grand_total_vnd), 0),
    ).filter(
        _crm_filter(),
        Reservation.check_in_date >= d_from,
        Reservation.check_in_date <= d_to,
        ~Reservation.status.in_(["Cancelled", "Canceled", "No-Show", "No_Show"]),
    ).group_by("yr", "mo", Reservation.guest_country_code)
    if branch_id:
        crm_q = crm_q.filter(Reservation.branch_id == branch_id)

    for yr, mo, country, bookings, rev in crm_q.all():
        month_str = f"{int(yr)}-{int(mo):02d}"
        c = country or "Unknown"
        grid[(month_str, c)]["crm"]["bookings"] += int(bookings)
        grid[(month_str, c)]["crm"]["revenue_vnd"] += float(rev)

    # Flatten to list
    result = []
    for (month_str, country), data in sorted(grid.items()):
        activities = []
        if data["paid_ads"]["bookings"] > 0 or data["paid_ads"]["cost_vnd"] > 0:
            activities.append("Paid Ads")
        if data["kol"]["bookings"] > 0:
            activities.append("KOL")
        if data["crm"]["bookings"] > 0:
            activities.append("CRM")

        total_rev = (
            data["paid_ads"]["revenue_vnd"]
            + data["kol"]["revenue_vnd"]
            + data["crm"]["revenue_vnd"]
        )
        total_cost = data["paid_ads"]["cost_vnd"]
        total_bookings = (
            data["paid_ads"]["bookings"]
            + data["kol"]["bookings"]
            + data["crm"]["bookings"]
        )

        result.append({
            "month": month_str,
            "country": country,
            "paid_ads": data["paid_ads"],
            "kol": data["kol"],
            "crm": data["crm"],
            "activities": activities,
            "total_bookings": total_bookings,
            "total_revenue_vnd": total_rev,
            "total_cost_vnd": total_cost,
            "roas": round(total_rev / total_cost, 2) if total_cost > 0 else None,
        })

    return result


# ── KOL Suggestions for Paid Ads ─────────────────────────────────────────────

def _build_kol_suggestions(db: Session, branch_id: Optional[UUID], d_from: date, d_to: date):
    """
    KOLs with organic bookings NOT currently used in paid ads.
    Grouped by (kol_name, country) so we can see which countries each KOL drives.
    """
    bid_filter = "AND r.branch_id = :bid" if branch_id else ""

    rows = db.execute(text(f"""
        SELECT r.room_type,
               r.guest_country_code,
               r.grand_total_vnd,
               r.status,
               b.id   AS branch_id,
               b.name AS branch_name
        FROM   reservations r
        JOIN   branches b ON r.branch_id = b.id
        WHERE  r.room_type ILIKE '%KOL_%%'
          AND  r.check_in_date >= :d_from
          AND  r.check_in_date <= :d_to
          {bid_filter}
    """), {
        "d_from": d_from,
        "d_to": d_to,
        **({"bid": str(branch_id)} if branch_id else {}),
    }).fetchall()

    # Aggregate by (kol_name, country, branch)
    agg = defaultdict(lambda: {
        "organic_bookings": 0,
        "organic_revenue_vnd": 0.0,
    })

    for room_type, country, total_vnd, status, bid, branch_name in rows:
        m = _KOL_RE.search(room_type or "")
        if not m:
            continue
        kol_name = "KOL_" + m.group(1).strip()
        st = (status or "").lower()
        if st in _CANCELLED:
            continue
        country = country or "Unknown"
        key = (kol_name, country, str(bid), branch_name)
        agg[key]["organic_bookings"] += 1
        agg[key]["organic_revenue_vnd"] += float(total_vnd or 0)

    if not agg:
        return []

    # Load kol_records to filter out those already in paid ads
    kol_rows = db.execute(text("""
        SELECT kol_name, kol_nationality, usage_rights_expiry_date,
               paid_ads_eligible, paid_ads_channel, ads_usage_status
        FROM   kol_records
    """)).fetchall()

    kol_map = {}
    for kr in kol_rows:
        kol_map[kr[0]] = {
            "kol_nationality": kr[1],
            "usage_rights_until": kr[2].isoformat() if kr[2] else None,
            "paid_ads_eligible": kr[3],
            "paid_ads_channel": kr[4],
            "ads_usage_status": kr[5],
        }

    result = []
    for (kol_name, country, bid, branch_name), data in agg.items():
        if data["organic_bookings"] <= 0:
            continue

        mgmt = kol_map.get(kol_name, {})

        # Filter out KOLs already used in paid ads
        if mgmt.get("paid_ads_channel") or mgmt.get("ads_usage_status") == "In Use":
            continue

        result.append({
            "kol_name": kol_name,
            "country": country,
            "organic_bookings": data["organic_bookings"],
            "organic_revenue_vnd": data["organic_revenue_vnd"],
            "branch_id": bid,
            "branch": branch_name,
            "kol_nationality": mgmt.get("kol_nationality"),
            "usage_rights_until": mgmt.get("usage_rights_until"),
            "paid_ads_eligible": mgmt.get("paid_ads_eligible", False),
        })

    result.sort(key=lambda x: (-x["organic_revenue_vnd"], x["country"], x["kol_name"]))
    return result
