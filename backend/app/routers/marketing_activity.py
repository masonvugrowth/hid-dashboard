"""
Marketing Activity router — consolidated view of Paid Ads, KOL, and CRM performance.

Data sources:
  - Paid Ads: Google Sheet (combined all branches, VND) — also has native currency cols
  - KOL:      Cloudbeds reservations (room_type ILIKE '%KOL_%')
  - CRM:      Cloudbeds reservations (CRM/MEANDER'S FRIEND/Travel guide/Grand Open)
"""
import logging
import re
import time
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, extract
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.models.reservation import Reservation
from app.models.kol import KOLRecord
from app.config import settings
from app.services.google_sheets_ads import _get_access_token, _read_sheet

router = APIRouter()
log = logging.getLogger(__name__)

_KOL_RE = re.compile(r"\(KOL_([^)]+)\)")
_CANCELLED = {"canceled", "cancelled", "no_show", "no-show", "cancelled_by_guest"}

# Combined Google Sheet for Paid Ads
COMBINED_SHEET_ID = "1h2cogiqbUkJ5yxJjoH0U5afSGhEMrJQRlXlSOb8DMms"
COMBINED_SHEET_TAB = "Combine all branch (VND)"

# Branch name → branch_id mapping
_BRANCH_NAME_TO_ID = {
    "taipei":  "11111111-1111-1111-1111-111111111101",
    "saigon":  "11111111-1111-1111-1111-111111111102",
    "1948":    "11111111-1111-1111-1111-111111111103",
    "oani":    "11111111-1111-1111-1111-111111111104",
    "osaka":   "11111111-1111-1111-1111-111111111105",
}

# ── In-memory cache for Google Sheet data (5-minute TTL) ─────────────────────
_sheet_cache: dict = {"data": None, "ts": 0}
_CACHE_TTL = 300  # 5 minutes


def _envelope(data):
    return {
        "success": True,
        "data": data,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _crm_filter():
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


# ── Google Sheet Parsing ─────────────────────────────────────────────────────

def _parse_float(val: str) -> Optional[float]:
    if not val or val.strip() in ("", "-", "N/A"):
        return None
    try:
        return float(val.replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def _parse_int(val: str) -> Optional[int]:
    f = _parse_float(val)
    return int(f) if f is not None else None


def _parse_date(val: str) -> Optional[date]:
    val = val.strip()
    if not val:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            pass
    return None


def _safe(row: list, idx: int) -> str:
    try:
        return row[idx].strip()
    except (IndexError, AttributeError):
        return ""


def _resolve_branch_id(branch_name: str) -> Optional[str]:
    lower = branch_name.lower().strip()
    for key, bid in _BRANCH_NAME_TO_ID.items():
        if key in lower:
            return bid
    return None


def _fetch_sheet_rows() -> list[dict]:
    """
    Read combined Google Sheet and return parsed Paid Ads rows.

    Column mapping:
      0:  MKT Activity       14: Currency
      1:  Branch              15: Channel
      2:  Cost -VAT (VND)     16: Funnel
      3:  Revenue (VND)       17: Date
      4:  ROAS (VND)          19: Month
      21: Country             22: Cost (-VAT) [native]
      26: Booking             28: Revenue [native]
    """
    now = time.time()
    if _sheet_cache["data"] is not None and (now - _sheet_cache["ts"]) < _CACHE_TTL:
        return _sheet_cache["data"]

    try:
        access_token = _get_access_token(
            settings.GOOGLE_CLIENT_ID,
            settings.GOOGLE_CLIENT_SECRET,
            settings.GOOGLE_REFRESH_TOKEN,
        )
        raw = _read_sheet(access_token, COMBINED_SHEET_ID, COMBINED_SHEET_TAB)
    except Exception as e:
        log.error("Failed to read combined Google Sheet: %s", e)
        return _sheet_cache["data"] or []

    if not raw or len(raw) < 2:
        return []

    data_rows = raw[1:]
    parsed = []

    for row in data_rows:
        mkt_activity = _safe(row, 0)
        if not mkt_activity or mkt_activity.lower() == "mkt activity":
            continue

        row_date = _parse_date(_safe(row, 17))
        branch_name = _safe(row, 1)
        branch_id = _resolve_branch_id(branch_name)

        parsed.append({
            "mkt_activity": mkt_activity,
            "branch_id": branch_id,
            "branch_name": branch_name,
            "cost_vnd": _parse_float(_safe(row, 2)) or 0,
            "revenue_vnd": _parse_float(_safe(row, 3)) or 0,
            "cost_native": _parse_float(_safe(row, 22)) or 0,
            "revenue_native": _parse_float(_safe(row, 28)) or 0,
            "currency": _safe(row, 14) or "VND",
            "channel": _safe(row, 15),
            "funnel": _safe(row, 16),
            "date": row_date,
            "month": _safe(row, 19),
            "country": _safe(row, 21),
            "bookings": _parse_int(_safe(row, 26)) or 0,
        })

    _sheet_cache["data"] = parsed
    _sheet_cache["ts"] = now
    log.info("Loaded %d rows from combined Google Sheet", len(parsed))
    return parsed


def _filter_sheet_rows(rows, branch_id, d_from, d_to):
    bid_str = str(branch_id) if branch_id else None
    result = []
    for r in rows:
        if bid_str and r["branch_id"] != bid_str:
            continue
        if r["date"]:
            if r["date"] < d_from or r["date"] > d_to:
                continue
        result.append(r)
    return result


def _normalize_month(month_str: str) -> str:
    """Normalize month format to YYYY-MM."""
    if not month_str:
        return ""
    if len(month_str) <= 7 and "-" in month_str:
        return month_str
    for fmt in ("%b %Y", "%B %Y", "%m/%Y"):
        try:
            dt = datetime.strptime(month_str.strip(), fmt)
            return dt.strftime("%Y-%m")
        except ValueError:
            continue
    return month_str


@router.get("/summary")
def get_marketing_activity_summary(
    branch_id: Optional[UUID] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    today = date.today()
    d_from = date.fromisoformat(date_from) if date_from else date(today.year, 1, 1)
    d_to = date.fromisoformat(date_to) if date_to else today

    all_sheet_rows = _fetch_sheet_rows()
    ads_rows = _filter_sheet_rows(all_sheet_rows, branch_id, d_from, d_to)

    # Determine if single branch (use native currency) or all (use VND)
    use_native = branch_id is not None

    overview = _build_overview(db, branch_id, d_from, d_to, ads_rows, use_native)
    monthly = _build_monthly_by_country(db, branch_id, d_from, d_to, ads_rows, use_native)
    suggestions = _build_kol_suggestions(db, branch_id, d_from, d_to)

    # Get currency label
    currency = "VND"
    if use_native and ads_rows:
        currency = ads_rows[0].get("currency", "VND")

    return _envelope({
        "overview": overview,
        "monthly_by_country": monthly,
        "kol_suggestions": suggestions,
        "currency": currency,
    })


# ── Overview KPIs ────────────────────────────────────────────────────────────

def _build_overview(db, branch_id, d_from, d_to, ads_rows, use_native):
    # Paid Ads (from Google Sheet)
    cost_key = "cost_native" if use_native else "cost_vnd"
    rev_key = "revenue_native" if use_native else "revenue_vnd"

    ads_bookings = sum(r["bookings"] for r in ads_rows)
    ads_revenue = sum(r[rev_key] for r in ads_rows)
    ads_cost = sum(r[cost_key] for r in ads_rows)
    ads_roas = round(ads_revenue / ads_cost, 2) if ads_cost > 0 else 0

    # KOL (from Cloudbeds reservations)
    rev_col = Reservation.grand_total_native if use_native else Reservation.grand_total_vnd
    kol_q = db.query(
        func.count(Reservation.id).label("bookings"),
        func.coalesce(func.sum(rev_col), 0).label("revenue"),
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
    kol_revenue = float(kol_row.revenue)

    # KOL cost (always VND in kol_records — use cost_native if available)
    cost_col = KOLRecord.cost_native if use_native else KOLRecord.cost_vnd
    kol_cost_q = db.query(func.coalesce(func.sum(cost_col), 0))
    if branch_id:
        kol_cost_q = kol_cost_q.filter(KOLRecord.branch_id == branch_id)
    kol_cost = float(kol_cost_q.scalar() or 0)

    # CRM (from Cloudbeds reservations)
    crm_q = db.query(
        func.count(Reservation.id).label("bookings"),
        func.coalesce(func.sum(rev_col), 0).label("revenue"),
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
    crm_revenue = float(crm_row.revenue)

    total_bookings = ads_bookings + kol_bookings + crm_bookings
    total_revenue = ads_revenue + kol_revenue + crm_revenue
    total_cost = ads_cost + kol_cost
    total_roas = round(total_revenue / total_cost, 2) if total_cost > 0 else 0

    return {
        "paid_ads": {
            "bookings": ads_bookings,
            "revenue": ads_revenue,
            "cost": ads_cost,
            "roas": ads_roas,
        },
        "kol": {
            "bookings": kol_bookings,
            "revenue": kol_revenue,
            "cost": kol_cost,
        },
        "crm": {
            "bookings": crm_bookings,
            "revenue": crm_revenue,
        },
        "total": {
            "bookings": total_bookings,
            "revenue": total_revenue,
            "cost": total_cost,
            "roas": total_roas,
        },
    }


# ── Monthly by Country ───────────────────────────────────────────────────────

def _build_monthly_by_country(db, branch_id, d_from, d_to, ads_rows, use_native):
    grid = defaultdict(lambda: {
        "paid_ads": {"bookings": 0, "revenue": 0, "cost": 0},
        "kol": {"bookings": 0, "revenue": 0},
        "crm": {"bookings": 0, "revenue": 0},
    })

    cost_key = "cost_native" if use_native else "cost_vnd"
    rev_key = "revenue_native" if use_native else "revenue_vnd"

    # Paid Ads from Google Sheet
    for r in ads_rows:
        month_str = _normalize_month(r["month"]) or (r["date"].strftime("%Y-%m") if r["date"] else None)
        if not month_str:
            continue
        country = r["country"] or "Unknown"
        grid[(month_str, country)]["paid_ads"]["bookings"] += r["bookings"]
        grid[(month_str, country)]["paid_ads"]["revenue"] += r[rev_key]
        grid[(month_str, country)]["paid_ads"]["cost"] += r[cost_key]

    # KOL from Cloudbeds
    rev_col = Reservation.grand_total_native if use_native else Reservation.grand_total_vnd
    kol_q = db.query(
        extract("year", Reservation.check_in_date).label("yr"),
        extract("month", Reservation.check_in_date).label("mo"),
        Reservation.guest_country_code,
        func.count(Reservation.id),
        func.coalesce(func.sum(rev_col), 0),
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
        grid[(month_str, c)]["kol"]["revenue"] += float(rev)

    # CRM from Cloudbeds
    crm_q = db.query(
        extract("year", Reservation.check_in_date).label("yr"),
        extract("month", Reservation.check_in_date).label("mo"),
        Reservation.guest_country_code,
        func.count(Reservation.id),
        func.coalesce(func.sum(rev_col), 0),
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
        grid[(month_str, c)]["crm"]["revenue"] += float(rev)

    # Flatten
    result = []
    for (month_str, country), data in sorted(grid.items()):
        activities = []
        if data["paid_ads"]["bookings"] > 0 or data["paid_ads"]["cost"] > 0:
            activities.append("Paid Ads")
        if data["kol"]["bookings"] > 0:
            activities.append("KOL")
        if data["crm"]["bookings"] > 0:
            activities.append("CRM")

        total_rev = data["paid_ads"]["revenue"] + data["kol"]["revenue"] + data["crm"]["revenue"]
        total_cost = data["paid_ads"]["cost"]
        total_bookings = data["paid_ads"]["bookings"] + data["kol"]["bookings"] + data["crm"]["bookings"]

        result.append({
            "month": month_str,
            "country": country,
            "paid_ads": data["paid_ads"],
            "kol": data["kol"],
            "crm": data["crm"],
            "activities": activities,
            "total_bookings": total_bookings,
            "total_revenue": total_rev,
            "total_cost": total_cost,
            "roas": round(total_rev / total_cost, 2) if total_cost > 0 else None,
        })

    return result


# ── KOL Suggestions for Paid Ads ─────────────────────────────────────────────

def _build_kol_suggestions(db: Session, branch_id: Optional[UUID], d_from: date, d_to: date):
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

    agg = defaultdict(lambda: {"organic_bookings": 0, "organic_revenue_vnd": 0.0})

    for room_type, country, total_vnd, status, bid, branch_name in rows:
        m = _KOL_RE.search(room_type or "")
        if not m:
            continue
        kol_name = "KOL_" + m.group(1).strip()
        if (status or "").lower() in _CANCELLED:
            continue
        country = country or "Unknown"
        key = (kol_name, country, str(bid), branch_name)
        agg[key]["organic_bookings"] += 1
        agg[key]["organic_revenue_vnd"] += float(total_vnd or 0)

    if not agg:
        return []

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
