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
  ads bookings/rev  the conversions and revenue on those same metrics rows.
                    ads_booking_matches would be the better-attributed
                    source - it ties each booking to a real reservation -
                    but the upstream matcher goes quiet for whole months at
                    a time (org-wide zero for Sept 2026, while /spend/daily
                    reported 106 conversions), and a campaign tab that
                    reads 0 whenever the matcher sleeps is worse than one
                    reading the platform's own conversion count. It stays
                    as the fallback for when metrics carries no conversion
                    field at all, and each row says which source it used.
  actual bookings   reservations matched on rate plan, by Date Booked, with
    /revenue        the same status + non-paying-source exclusions the rest
                    of Marketing Activity uses.

Taking spend AND ad-side revenue from one set of rows has a second benefit:
the ROAS (Ads) numerator and denominator sit on the same ledger, so it can
be argued with as a ratio even where ad-grain attribution under-counts both.

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

# "not supplied", so a caller CAN pass metrics=None to mean "upstream is down"
# without build_rows helpfully going and fetching them itself.
_UNSET = object()


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


def fetch_ad_metrics(d_from: date, d_to: date,
                     keys_seen: Optional[set] = None) -> Optional[dict]:
    """{ad_id: {spend, revenue, conversions, currency}}, or None if Ads is down.

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
                if keys_seen is not None:
                    keys_seen.update(r.keys())
                ad_id = str(r.get("ad_id") or r.get("id") or "").strip()
                if not ad_id:
                    continue
                entry = rows_by_ad.setdefault(ad_id, {
                    "spend": 0.0, "spend_vnd": None,
                    "revenue": 0.0, "revenue_vnd": None,
                    "conversions": 0.0, "has_conversions": False,
                    "currency": None,
                })
                entry["spend"] += _num(r.get("spend"), r.get("cost"),
                                       r.get("spend_native"))
                vnd = _num_or_none(r.get("spend_vnd"), r.get("cost_vnd"))
                if vnd is not None:
                    entry["spend_vnd"] = (entry["spend_vnd"] or 0.0) + vnd

                entry["revenue"] += _num(r.get("revenue"), r.get("revenue_native"))
                rev_vnd = _num_or_none(r.get("revenue_vnd"))
                if rev_vnd is not None:
                    entry["revenue_vnd"] = (entry["revenue_vnd"] or 0.0) + rev_vnd

                # has_conversions distinguishes "this ad genuinely sold
                # nothing" from "this export doesn't carry a conversion
                # field", which decide different fallbacks downstream.
                conv = _num_or_none(r.get("conversions"), r.get("purchases"),
                                    r.get("bookings"))
                if conv is not None:
                    entry["conversions"] += conv
                    entry["has_conversions"] = True

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


def _money_vnd(scope: dict, metrics: dict, rate_for, field: str) -> float:
    """Sum one money field across this campaign's ads, in VND.

    Upstream reports money in the AD ACCOUNT's currency (same convention
    ads_platform_sync._sync_spend_daily reads it under), so each row is
    converted with its own account's rate rather than the branch's. A row
    that already carries a ``<field>_vnd`` figure is taken as-is.
    """
    total = 0.0
    for ad_id in scope["ad_ids"]:
        row = metrics.get(ad_id)
        if not row:
            continue
        if row.get(f"{field}_vnd") is not None:
            total += row[f"{field}_vnd"]
            continue
        meta = scope["currency_by_ad"].get(ad_id) or {}
        currency = row.get("currency") or meta.get("branch_currency") or "VND"
        rate = rate_for(currency)
        if not rate:
            log.warning("no FX rate for %s - ad %s %s dropped",
                        currency, ad_id, field)
            continue
        total += (row.get(field) or 0.0) * rate
    return total


def _spend_vnd(scope: dict, metrics: dict, rate_for) -> float:
    """This campaign's ad spend, in VND."""
    return _money_vnd(scope, metrics, rate_for, "spend")


def _ads_from_metrics(scope: dict, metrics: dict, rate_for):
    """(bookings, revenue_vnd, usable) straight off the campaign's ad rows.

    ``usable`` is False when not one of the campaign's ads carried a
    conversion field — that is a shape problem with the export, not a
    campaign that sold nothing, and the caller falls back to the matcher
    rather than printing a confident zero.
    """
    bookings = 0
    usable = False
    for ad_id in scope["ad_ids"]:
        row = metrics.get(ad_id)
        if not row:
            continue
        if row.get("has_conversions"):
            usable = True
            bookings += int(round(row.get("conversions") or 0))
    if not usable:
        return 0, 0.0, False
    return bookings, _money_vnd(scope, metrics, rate_for, "revenue"), True


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
    metrics=_UNSET,
) -> list[dict]:
    """One performance row per campaign, in the caller's display currency.

    ``to_view_currency`` converts a VND figure to what the page shows (VND
    for All Branches, the branch's own currency otherwise); ``rate_for``
    gives native->VND for a currency code. Both are injected so this module
    stays free of the router's currency plumbing.

    Pass ``metrics`` to reuse an already-fetched ad-metrics dict (None for
    "upstream was down"). The branch comparison calls this once per branch
    and must not hit the Ads Platform five times for one page.
    """
    if not campaigns:
        return []

    if metrics is _UNSET:
        # Skip the upstream call entirely when nobody named an ad campaign: a
        # rate-plan-only campaign has a real spend of zero, and calling out
        # just to fail would put an "Ads Platform unavailable" warning on a
        # tab where ad spend was never part of the answer.
        metrics = (
            fetch_ad_metrics(d_from, d_to)
            if any(c.ads_campaign_names for c in campaigns) else {}
        )
    ads_available = metrics is not None

    rows = []
    for c in campaigns:
        scope = _ad_scope(db, c.ads_campaign_names, branch_id)

        # Bookings and revenue come off the campaign's own ad rows, the same
        # ones spend is summed from. The matcher is the fallback, not the
        # default: it reported org-wide zero for all of Sept 2026 while
        # /spend/daily saw 106 conversions.
        ads_bookings, ads_revenue_vnd, from_metrics = (
            _ads_from_metrics(scope, metrics, rate_for) if ads_available
            else (0, 0.0, False)
        )
        if not from_metrics:
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
            "ads_source": "ads_metrics" if from_metrics else "booking_matches",
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
