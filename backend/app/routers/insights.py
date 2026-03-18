"""Insights router — KOL-to-Paid Ads opportunities"""
import re
from datetime import datetime, date, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.kol import KOLRecord

_KOL_RE = re.compile(r"\(KOL_([^)]+)\)")

# Maps common nationality adjectives → country name fragment for matching
_NAT_MAP = {
    "vietnamese": "vietnam",
    "korean": "korea",
    "japanese": "japan",
    "taiwanese": "taiwan",
    "chinese": "china",
    "indonesian": "indonesia",
    "thai": "thailand",
    "singaporean": "singapore",
    "malaysian": "malaysia",
    "filipino": "philippines",
    "philippine": "philippines",
    "australian": "australia",
    "american": "united states",
    "french": "france",
    "german": "germany",
    "british": "united kingdom",
    "canadian": "canada",
    "spanish": "spain",
    "italian": "italy",
    "dutch": "netherlands",
    "russian": "russia",
    "indian": "india",
    "hongkonger": "hong kong",
    "hong konger": "hong kong",
    "hong kong": "hong kong",
    "swedish": "sweden",
    "norwegian": "norway",
    "danish": "denmark",
    "finnish": "finland",
    "polish": "poland",
    "swiss": "switzerland",
    "austrian": "austria",
    "belgian": "belgium",
    "portuguese": "portugal",
    "greek": "greece",
    "turkish": "turkey",
    "saudi": "saudi arabia",
    "emirati": "united arab emirates",
    "uae": "united arab emirates",
    "new zealander": "new zealand",
    "kiwi": "new zealand",
    "south african": "south africa",
    "mexican": "mexico",
    "brazilian": "brazil",
    "argentinian": "argentina",
    "chilean": "chile",
    "colombian": "colombia",
}


def _nat_matches_country(nationality: str, country: str) -> bool:
    nat = nationality.lower().strip()
    cty = country.lower().strip()
    mapped = _NAT_MAP.get(nat, nat)
    return mapped in cty or cty in mapped or nat in cty or cty in nat

router = APIRouter()


def _envelope(data):
    return {"success": True, "data": data, "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("")
def list_insights(
    branch_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Returns KOL records that are eligible for paid ads (paid_ads_eligible=True)
    but have no paid_ads_channel set yet — i.e. untapped opportunities.
    Also flags records with expiring usage rights.
    """
    today = date.today()
    q = db.query(KOLRecord).filter(KOLRecord.paid_ads_eligible == True)
    if branch_id:
        q = q.filter(KOLRecord.branch_id == branch_id)
    rows = q.order_by(KOLRecord.published_date.desc().nullslast()).all()

    result = []
    for r in rows:
        expiry_days = None
        if r.usage_rights_expiry_date:
            expiry_days = (r.usage_rights_expiry_date - today).days

        opportunity_type = []
        if not r.paid_ads_channel:
            opportunity_type.append("No channel set")
        if expiry_days is not None and 0 < expiry_days <= 30:
            opportunity_type.append(f"Rights expire in {expiry_days}d")
        if expiry_days is not None and expiry_days <= 0:
            opportunity_type.append("Rights expired")

        result.append({
            "id": str(r.id),
            "branch_id": str(r.branch_id),
            "kol_name": r.kol_name,
            "kol_nationality": r.kol_nationality,
            "language": r.language,
            "target_audience": r.target_audience,
            "published_date": r.published_date.isoformat() if r.published_date else None,
            "link_ig": r.link_ig,
            "link_tiktok": r.link_tiktok,
            "link_youtube": r.link_youtube,
            "deliverable_status": r.deliverable_status,
            "paid_ads_channel": r.paid_ads_channel,
            "paid_ads_usage_fee_vnd": float(r.paid_ads_usage_fee_vnd) if r.paid_ads_usage_fee_vnd else None,
            "usage_rights_expiry_date": r.usage_rights_expiry_date.isoformat() if r.usage_rights_expiry_date else None,
            "expiry_days_left": expiry_days,
            "opportunity_type": opportunity_type,
            "is_actionable": len(opportunity_type) > 0,
        })

    # Sort: rights expiring soon first, then unpublished
    result.sort(key=lambda x: (
        0 if (x["expiry_days_left"] is not None and 0 < x["expiry_days_left"] <= 30) else 1,
        x["expiry_days_left"] if x["expiry_days_left"] is not None else 9999,
    ))
    return _envelope(result)


@router.get("/country-intel")
def country_intelligence(
    branch_id: Optional[UUID] = Query(None),
    channel: Optional[str] = Query(None, description="Filter ads by channel: Meta, Google, TikTok"),
    db: Session = Depends(get_db),
):
    """
    Returns two ranked lists per branch:
    - top_volume:  Top 5 countries by all-time booking count
    - top_growth:  Top 5 countries by 90-day booking growth vs prior 90 days
    Cross-referenced with KOL and Paid Ads coverage.
    """
    b_filter = "AND r.branch_id = :bid" if branch_id else ""
    b_params = {"bid": str(branch_id)} if branch_id else {}

    # ── 1. Top 5 by booking volume (all-time) ───────────────────────────────
    country_rows = db.execute(text(f"""
        WITH ranked AS (
            SELECT
                b.id           AS branch_id,
                b.name         AS branch_name,
                b.currency,
                r.guest_country,
                r.guest_country_code,
                COUNT(*)                                          AS booking_count,
                SUM(r.grand_total_vnd)                           AS revenue_vnd,
                ROW_NUMBER() OVER (
                    PARTITION BY b.id
                    ORDER BY COUNT(*) DESC,
                        COALESCE(SUM(r.grand_total_vnd), 0) DESC
                )                                                AS rank
            FROM reservations r
            JOIN branches b ON r.branch_id = b.id
            WHERE r.guest_country IS NOT NULL
              AND r.guest_country != ''
              AND r.guest_country != '0'
              AND length(r.guest_country) > 1
              AND r.status NOT IN (
                  'canceled','cancelled','no_show','no-show','cancelled_by_guest'
              )
              {b_filter}
            GROUP BY b.id, b.name, b.currency, r.guest_country, r.guest_country_code
        )
        SELECT branch_id, branch_name, currency, guest_country, guest_country_code,
               booking_count, revenue_vnd, rank
        FROM ranked
        WHERE rank <= 5
        ORDER BY branch_name, rank
    """), b_params).fetchall()

    # ── 2. Top 5 by growth (recent 90d vs prior 90d) ─────────────────────────
    growth_rows = db.execute(text(f"""
        WITH recent AS (
            SELECT r.branch_id, r.guest_country, r.guest_country_code, COUNT(*) AS cnt
            FROM reservations r
            WHERE r.guest_country IS NOT NULL
              AND r.guest_country != ''
              AND r.guest_country != '0'
              AND length(r.guest_country) > 1
              AND r.status NOT IN ('canceled','cancelled','no_show','no-show','cancelled_by_guest')
              AND r.check_in_date >= CURRENT_DATE - INTERVAL '90 days'
              AND r.guest_country NOT ILIKE '%unknown%'
              {b_filter}
            GROUP BY r.branch_id, r.guest_country, r.guest_country_code
        ),
        prev AS (
            SELECT r.branch_id, r.guest_country, COUNT(*) AS cnt
            FROM reservations r
            WHERE r.guest_country IS NOT NULL
              AND r.guest_country != ''
              AND r.guest_country != '0'
              AND length(r.guest_country) > 1
              AND r.status NOT IN ('canceled','cancelled','no_show','no-show','cancelled_by_guest')
              AND r.check_in_date >= CURRENT_DATE - INTERVAL '180 days'
              AND r.check_in_date < CURRENT_DATE - INTERVAL '90 days'
              AND r.guest_country NOT ILIKE '%unknown%'
              {b_filter}
            GROUP BY r.branch_id, r.guest_country
        ),
        growth AS (
            SELECT
                rec.branch_id,
                rec.guest_country,
                rec.guest_country_code,
                rec.cnt                                          AS recent_bookings,
                COALESCE(prv.cnt, 0)                             AS prev_bookings,
                CASE
                    WHEN COALESCE(prv.cnt, 0) = 0 THEN NULL
                    ELSE ROUND(((rec.cnt - prv.cnt)::numeric / prv.cnt * 100), 1)
                END                                              AS growth_pct,
                ROW_NUMBER() OVER (
                    PARTITION BY rec.branch_id
                    ORDER BY
                        CASE WHEN COALESCE(prv.cnt, 0) > 0 AND rec.cnt > prv.cnt
                             THEN (rec.cnt - prv.cnt)::float / prv.cnt ELSE -1 END DESC
                )                                                AS rank
            FROM recent rec
            LEFT JOIN prev prv
                   ON rec.branch_id = prv.branch_id AND rec.guest_country = prv.guest_country
            WHERE rec.cnt >= 2
        )
        SELECT g.branch_id, b.name AS branch_name, b.currency,
               g.guest_country, g.guest_country_code,
               g.recent_bookings, g.prev_bookings, g.growth_pct, g.rank
        FROM growth g
        JOIN branches b ON g.branch_id = b.id
        WHERE g.rank <= 5
          AND (g.growth_pct > 0 OR g.prev_bookings = 0)
        ORDER BY b.name, g.rank
    """), b_params).fetchall()

    if not country_rows and not growth_rows:
        return _envelope([])

    # ── 2. All KOL records with nationality ──────────────────────────────────
    kol_rows = db.execute(text("""
        SELECT kol_name, kol_nationality, language, target_audience,
               deliverable_status, contract_status, link_ig, link_tiktok, link_youtube,
               branch_id
        FROM kol_records
        WHERE kol_nationality IS NOT NULL AND kol_nationality != ''
    """)).fetchall()

    # ── 3. KOL organic metrics from reservations ─────────────────────────────
    kol_res = db.execute(text("""
        SELECT room_type, branch_id, grand_total_vnd, status
        FROM reservations
        WHERE room_type ILIKE '%KOL_%'
          AND status NOT IN ('canceled','cancelled','no_show','no-show','cancelled_by_guest')
    """)).fetchall()

    kol_metric_map: dict[str, dict] = {}
    for row in kol_res:
        m = _KOL_RE.search(row[0] or "")
        if not m:
            continue
        kol_name = "KOL_" + m.group(1).strip()
        key = kol_name
        if key not in kol_metric_map:
            kol_metric_map[key] = {"organic_bookings": 0, "organic_revenue_vnd": 0.0}
        kol_metric_map[key]["organic_bookings"] += 1
        kol_metric_map[key]["organic_revenue_vnd"] += float(row[2] or 0)

    # ── 4. Ads coverage per (branch_id, target_country) ──────────────────────
    a_filter = "AND a.branch_id = :bid" if branch_id else ""
    a_ch_filter = "AND a.channel = :ch" if channel else ""
    a_params = dict(b_params)
    if channel:
        a_params["ch"] = channel
    ads_rows = db.execute(text(f"""
        SELECT
            a.branch_id,
            a.target_country,
            SUM(a.cost_vnd)       AS total_cost_vnd,
            SUM(a.impressions)    AS total_impressions,
            SUM(a.clicks)         AS total_clicks,
            SUM(a.leads)          AS total_leads,
            STRING_AGG(DISTINCT a.target_audience, ', ') AS target_audiences,
            STRING_AGG(DISTINCT a.funnel_stage, ', ')    AS funnel_stages
        FROM ads_performance a
        WHERE a.target_country IS NOT NULL AND a.target_country != ''
          {a_filter} {a_ch_filter}
        GROUP BY a.branch_id, a.target_country
    """), a_params).fetchall()

    # ads_map: branch_id -> list of {country_lower, ...metrics}
    ads_map: dict[str, list] = {}
    for a in ads_rows:
        bid_str = str(a[0])
        if bid_str not in ads_map:
            ads_map[bid_str] = []
        ads_map[bid_str].append({
            "target_country": a[1],
            "country_lower": (a[1] or "").lower(),
            "total_cost_vnd": float(a[2]) if a[2] else 0,
            "total_impressions": int(a[3] or 0),
            "total_clicks": int(a[4] or 0),
            "total_leads": int(a[5] or 0),
            "target_audiences": a[6],
            "funnel_stages": a[7],
        })

    # ── 5. Helper: build a country entry with KOL/Ads coverage ──────────────
    def _build_country(bid_str, country, country_code):
        cty_lower = country.lower()
        matched_kols = []
        for k in kol_rows:
            if str(k[9]) != bid_str:
                continue
            if k[1] and _nat_matches_country(k[1], country):
                metrics = kol_metric_map.get(k[0], {})
                matched_kols.append({
                    "kol_name": k[0],
                    "kol_nationality": k[1],
                    "language": k[2],
                    "target_audience": k[3],
                    "status": k[4] or k[5],
                    "link_ig": k[6],
                    "link_tiktok": k[7],
                    "link_youtube": k[8],
                    "organic_bookings": metrics.get("organic_bookings", 0),
                    "organic_revenue_vnd": metrics.get("organic_revenue_vnd", 0.0),
                })
        matched_ads = []
        for ad in ads_map.get(bid_str, []):
            ac = ad["country_lower"]
            if ac in cty_lower or cty_lower in ac:
                matched_ads.append({k: v for k, v in ad.items() if k != "country_lower"})
        action_items = []
        if not matched_kols:
            action_items.append(f"No KOL from {country} — identify & recruit")
        if not matched_ads:
            action_items.append(f"No Paid Ads targeting {country} — create campaign")
        return {
            "country": country,
            "country_code": country_code,
            "kol_coverage": matched_kols,
            "ads_coverage": matched_ads,
            "kol_gap": len(matched_kols) == 0,
            "ads_gap": len(matched_ads) == 0,
            "action_items": action_items,
        }

    # ── 6. Build response ────────────────────────────────────────────────────
    branch_map: dict[str, dict] = {}

    for r in country_rows:
        bid_str = str(r[0])
        if bid_str not in branch_map:
            branch_map[bid_str] = {
                "branch_id": bid_str,
                "branch_name": r[1],
                "currency": r[2],
                "top_volume": [],
                "top_growth": [],
            }
        entry = _build_country(bid_str, r[3], r[4])
        entry.update({
            "rank": int(r[7]),
            "booking_count": int(r[5]),
            "revenue_vnd": float(r[6]) if r[6] else 0.0,
        })
        branch_map[bid_str]["top_volume"].append(entry)

    for r in growth_rows:
        bid_str = str(r[0])
        if bid_str not in branch_map:
            branch_map[bid_str] = {
                "branch_id": bid_str,
                "branch_name": r[1],
                "currency": r[2],
                "top_volume": [],
                "top_growth": [],
            }
        entry = _build_country(bid_str, r[3], r[4])
        entry.update({
            "rank": int(r[8]),
            "recent_bookings": int(r[5]),
            "prev_bookings": int(r[6]),
            "growth_pct": float(r[7]) if r[7] is not None else None,
        })
        branch_map[bid_str]["top_growth"].append(entry)

    result = sorted(branch_map.values(), key=lambda x: x["branch_name"])
    return _envelope(result)
