"""Seasonal Campaign performance - joins ad spend to real Cloudbeds bookings.

One campaign row answers two questions side by side:

  Ads side     - what did we spend, and what did the ad platform's matcher
                 manage to attribute back to those ads?
  Reality side - how many bookings actually came in on the campaign's rate
                 plan, and what did they bill?

The two never agree, and that gap is the point of the tab. Ad-attributed
bookings miss the guest who saw the ad on Tuesday and booked by phone on
Friday; rate-plan bookings include guests the ads never touched. Showing
both, with a ROAS on each, is what lets the team argue about which number to
plan on instead of arguing about which one is broken.

Where each figure comes from, and why:

  spend             ads_platform /export/ads/metrics, summed over the ads
                    whose campaign name matches. The ONLY export with a
                    spend figure traceable to one campaign - see
                    AdsPlatformClient.get_ads_metrics for what that costs us
                    (Google campaign-grain spend can read low).
  ads bookings/rev  ads_booking_matches, the de-duped booking-level table
                    that carries external_campaign_id. Deliberately NOT the
                    conversions on the metrics rows above, which under-count
                    at ad grain by upstream design.
  actual bookings   reservations matched on rate plan, by Date Booked, with
    /revenue        the same status + non-paying-source exclusions the rest
                    of Marketing Activity uses.

Campaign cost is ``cost_pct`` percent of ACTUAL revenue (not ad-attributed
revenue): the discount and amenity a campaign gives away are owed on every
booking that came in on the rate plan, however the guest found it.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Iterable, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.ads import AdsPerformance
from app.models.ads_booking_match import AdsBookingMatch
from app.models.branch import Branch
from app.models.seasonal_campaign import SeasonalCampaign
from app.services.ads_platform import branch_slug_for, get_client
from app.services.crm_filters import rate_plan_pattern_filter

log = logging.getLogger(__name__)

_PLATFORMS = ("meta", "google", "tiktok")


def list_campaigns(db: Session) -> list[SeasonalCampaign]:
    """Every campaign definition, newest name-ordered.

    Zeabur does not run Alembic on deploy, so between this code landing and
    ``POST /api/sync/run-migrations`` the table does not exist. An empty tab
    is a smaller problem than a 500 on the page it lives in.
    """
    try:
        return (
            db.query(SeasonalCampaign)
            .order_by(SeasonalCampaign.is_active.desc(), SeasonalCampaign.name)
            .all()
        )
    except Exception:
        db.rollback()
        log.warning("seasonal_campaigns unavailable - serving an empty list",
                    exc_info=True)
        return []


def clean_patterns(values) -> list[str]:
    """Trim, drop blanks, de-dupe (case-insensitively) a typed name list."""
    out: list[str] = []
    seen: set[str] = set()
    for v in values or []:
        s = str(v or "").strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def serialize(c: SeasonalCampaign) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "ads_campaign_names": list(c.ads_campaign_names or []),
        "rate_plan_names": list(c.rate_plan_names or []),
        "cost_pct": float(c.cost_pct or 0),
        "notes": c.notes,
        "is_active": bool(c.is_active),
    }


# -- Ads side ----------------------------------------------------------------


def _ad_scope(db: Session, patterns: Iterable[str], branch_id) -> dict:
    """Resolve typed campaign names to the ad + campaign ids they cover.

    ``ads_performance`` rows at ``grain='ad'`` are the local mirror of
    /export/ads: one row per ad, carrying its campaign name, campaign id and
    account. That mirror is what turns "TET2027" (what a human typed) into
    the ids the metrics and booking-match tables are keyed by.
    """
    scope = {"ad_ids": set(), "campaign_ids": set(), "currency_by_ad": {}}
    patterns = list(patterns or [])
    if not patterns:
        return scope

    q = db.query(
        AdsPerformance.external_ad_id,
        AdsPerformance.external_campaign_id,
        AdsPerformance.account_id,
        AdsPerformance.branch_id,
    ).filter(
        AdsPerformance.grain == "ad",
        or_(*[AdsPerformance.campaign_name.ilike(f"%{p}%") for p in patterns]),
    )
    if branch_id is not None:
        q = q.filter(AdsPerformance.branch_id == branch_id)

    branch_currency = {
        b.id: (b.currency or "VND").upper()
        for b in db.query(Branch).all()
    }
    for ad_id, campaign_id, account_id, ad_branch_id in q.all():
        if campaign_id:
            scope["campaign_ids"].add(str(campaign_id))
        if ad_id:
            scope["ad_ids"].add(str(ad_id))
            scope["currency_by_ad"][str(ad_id)] = {
                "account_id": str(account_id) if account_id else None,
                "branch_currency": branch_currency.get(ad_branch_id, "VND"),
            }
    return scope


def fetch_ad_metrics(d_from: date, d_to: date) -> Optional[dict]:
    """{ad_id: {spend, currency}} for the window, or None if Ads is down.

    None rather than an empty dict on failure: a 0 spend would turn every
    ROAS on the tab into a confident-looking infinity, and the team would act
    on it. The tab shows a dash instead.
    """
    try:
        client = get_client()
    except Exception as exc:
        log.warning("Ads Platform client unavailable: %s", exc)
        return None

    try:
        accounts = {
            str(a.get("id") or a.get("account_id") or ""): (
                a.get("currency") or ""
            ).upper()
            for a in client.get_accounts()
        }
    except Exception as exc:
        # Not fatal: fall back to the ad's branch currency per row.
        log.warning("accounts lookup failed, falling back to branch currency: %s", exc)
        accounts = {}

    df, dt = d_from.isoformat(), d_to.isoformat()
    rows_by_ad: dict[str, dict] = {}
    any_platform_ok = False

    with ThreadPoolExecutor(max_workers=len(_PLATFORMS)) as ex:
        futures = {
            ex.submit(client.get_ads_metrics, df, dt, platform=p): p
            for p in _PLATFORMS
        }
        for future in as_completed(futures):
            platform = futures[future]
            try:
                rows = future.result()
            except Exception as exc:
                log.warning("ads/metrics failed (platform=%s): %s", platform, exc)
                continue
            any_platform_ok = True
            for r in rows or []:
                ad_id = str(r.get("ad_id") or r.get("id") or "").strip()
                if not ad_id:
                    continue
                entry = rows_by_ad.setdefault(
                    ad_id, {"spend": 0.0, "spend_vnd": None, "currency": None},
                )
                entry["spend"] += _num(r.get("spend"), r.get("cost"),
                                       r.get("spend_native"))
                vnd = _num_or_none(r.get("spend_vnd"), r.get("cost_vnd"))
                if vnd is not None:
                    entry["spend_vnd"] = (entry["spend_vnd"] or 0.0) + vnd
                cur = (r.get("currency") or "").upper() or None
                if cur is None:
                    acc = str(r.get("account_id") or "")
                    cur = accounts.get(acc) or None
                entry["currency"] = entry["currency"] or cur

    if not any_platform_ok:
        return None
    return rows_by_ad


def _num(*candidates) -> float:
    for c in candidates:
        if c is None:
            continue
        try:
            return float(c)
        except (TypeError, ValueError):
            continue
    return 0.0


def _num_or_none(*candidates) -> Optional[float]:
    for c in candidates:
        if c is None:
            continue
        try:
            return float(c)
        except (TypeError, ValueError):
            continue
    return None


def _spend_vnd(scope: dict, metrics: dict, rate_for) -> float:
    """Sum this campaign's ad spend, in VND.

    Upstream reports spend in the AD ACCOUNT's currency (same convention
    ads_platform_sync._sync_spend_daily reads it under), so each row is
    converted with its own account's rate rather than the branch's.
    """
    total = 0.0
    for ad_id in scope["ad_ids"]:
        row = metrics.get(ad_id)
        if not row:
            continue
        if row.get("spend_vnd") is not None:
            total += row["spend_vnd"]
            continue
        meta = scope["currency_by_ad"].get(ad_id) or {}
        currency = row.get("currency") or meta.get("branch_currency") or "VND"
        rate = rate_for(currency)
        if not rate:
            log.warning("no FX rate for %s - ad %s spend dropped", currency, ad_id)
            continue
        total += row["spend"] * rate
    return total


def _ads_bookings(db: Session, scope: dict, d_from: date, d_to: date,
                  branch_id) -> tuple[int, float]:
    """(bookings, revenue_vnd) the ad platform attributes to this campaign.

    Matched on campaign id, falling back to ad id, because a match made
    before the campaign tree was mirrored can carry one without the other.
    """
    if not scope["campaign_ids"] and not scope["ad_ids"]:
        return 0, 0.0

    clauses = []
    if scope["campaign_ids"]:
        clauses.append(
            AdsBookingMatch.external_campaign_id.in_(sorted(scope["campaign_ids"]))
        )
    if scope["ad_ids"]:
        clauses.append(
            AdsBookingMatch.external_ad_id.in_(sorted(scope["ad_ids"]))
        )

    q = db.query(
        func.count(AdsBookingMatch.id).label("bookings"),
        func.coalesce(func.sum(AdsBookingMatch.revenue_vnd), 0).label("revenue"),
    ).filter(
        or_(*clauses),
        AdsBookingMatch.booking_date >= d_from,
        AdsBookingMatch.booking_date <= d_to,
    )
    if branch_id is not None:
        q = q.filter(AdsBookingMatch.branch_id == branch_id)
    row = q.one()
    return int(row.bookings or 0), float(row.revenue or 0)


# -- Reality side ------------------------------------------------------------


def actual_bookings(db: Session, patterns, d_from: date, d_to: date, branch_id,
                    status_filter, source_filter, rev_col):
    """(bookings, nights, revenue) really booked on the campaign's rate plans.

    Filtered by Date Booked, matching every other Marketing Activity surface:
    a campaign is measured by when its bookings landed, not when the guests
    eventually stay.
    """
    pattern_filter = rate_plan_pattern_filter(patterns)
    if pattern_filter is None:
        return 0, 0, 0.0

    from app.models.reservation import Reservation

    q = db.query(
        func.count(Reservation.id).label("bookings"),
        func.coalesce(func.sum(Reservation.nights), 0).label("nights"),
        func.coalesce(func.sum(rev_col), 0).label("revenue"),
    ).filter(
        pattern_filter,
        Reservation.reservation_date >= d_from,
        Reservation.reservation_date <= d_to,
        status_filter,
        source_filter,
    )
    if branch_id is not None:
        q = q.filter(Reservation.branch_id == branch_id)
    row = q.one()
    return int(row.bookings or 0), int(row.nights or 0), float(row.revenue or 0)


# -- The row -----------------------------------------------------------------


def build_rows(
    db: Session,
    campaigns: list[SeasonalCampaign],
    d_from: date,
    d_to: date,
    branch_id,
    *,
    status_filter,
    source_filter,
    rev_col,
    rate_for,
    to_view_currency,
) -> list[dict]:
    """One performance row per campaign, in the caller's display currency.

    ``to_view_currency`` converts a VND figure to what the page shows (VND
    for All Branches, the branch's own currency otherwise); ``rate_for``
    gives native->VND for a currency code. Both are injected so this module
    stays free of the router's currency plumbing.
    """
    if not campaigns:
        return []

    # Skip the upstream call entirely when nobody named an ad campaign: a
    # rate-plan-only campaign has a real spend of zero, and calling out just to
    # fail would put an "Ads Platform unavailable" warning on a tab where ad
    # spend was never part of the answer.
    if any(c.ads_campaign_names for c in campaigns):
        metrics = fetch_ad_metrics(d_from, d_to)
    else:
        metrics = {}
    ads_available = metrics is not None

    rows = []
    for c in campaigns:
        scope = _ad_scope(db, c.ads_campaign_names, branch_id)
        ads_bookings, ads_revenue_vnd = _ads_bookings(
            db, scope, d_from, d_to, branch_id,
        )
        spend = (
            to_view_currency(_spend_vnd(scope, metrics, rate_for))
            if ads_available else None
        )
        ads_revenue = to_view_currency(ads_revenue_vnd)

        bookings, nights, revenue = actual_bookings(
            db, c.rate_plan_names, d_from, d_to, branch_id,
            status_filter, source_filter, rev_col,
        )

        cost_pct = float(c.cost_pct or 0)
        campaign_cost = revenue * cost_pct / 100.0
        # A dash for spend must not silently become a zero in the total:
        # the true cost is unknown, so the true ROAS is too.
        total_cost = None if spend is None else spend + campaign_cost

        rows.append({
            **serialize(c),
            "spend": spend,
            "ads_bookings": ads_bookings,
            "ads_revenue": ads_revenue,
            "roas_ads": _roas(ads_revenue, spend),
            "actual_bookings": bookings,
            "actual_nights": nights,
            "actual_revenue": revenue,
            "campaign_cost": campaign_cost,
            "total_cost": total_cost,
            "roas_actual": _roas(revenue, total_cost),
            "matched_ads": len(scope["ad_ids"]),
            "matched_ad_campaigns": len(scope["campaign_ids"]),
            "spend_available": ads_available,
        })

    rows.sort(key=lambda r: -(r["actual_revenue"] or 0))
    return rows


def _roas(revenue: Optional[float], cost: Optional[float]) -> Optional[float]:
    """None, not 0, when there is no cost to divide by - the tab prints a dash.

    A campaign that spent nothing has no ROAS; calling it 0 reads as "it
    failed", which is the opposite of what the data says.
    """
    if cost is None or cost <= 0:
        return None
    return round((revenue or 0) / cost, 2)
