"""Meta Graph API client — pulls ad-level data for one ad account."""
import logging
import re
import httpx

logger = logging.getLogger(__name__)

BASE = "https://graph.facebook.com/v21.0"

TA_KEYWORDS = ["Solo", "Friend", "Couple", "Family", "Business", "Group"]

COUNTRY_TOKENS = {
    "VN": "Vietnam", "PH": "Philippines", "ID": "Indonesia",
    "AU": "Australia", "UK": "United Kingdom", "US": "United States",
    "TW": "Taiwan", "KR": "South Korea", "JPN": "Japan",
    "TH": "Thailand", "MY": "Malaysia", "SG": "Singapore",
    "ENG": None,  # language flag, not country — skip
}


def _get(token: str, endpoint: str, params: dict) -> dict:
    r = httpx.get(
        f"{BASE}/{endpoint}",
        params={"access_token": token, **params},
        timeout=60,
        follow_redirects=True,
    )
    r.raise_for_status()
    return r.json()


def _paginate(token: str, endpoint: str, params: dict) -> list:
    """Collect all pages using cursor-based pagination (avoids redirect issues)."""
    results = []
    url = f"{BASE}/{endpoint}"
    p = {"access_token": token, **params}
    while True:
        r = httpx.get(url, params=p, timeout=60, follow_redirects=True)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("data", []))
        after = data.get("paging", {}).get("cursors", {}).get("after")
        if not after:
            break
        p = {"access_token": token, **params, "after": after}
    return results


def parse_campaign_name(name: str) -> dict:
    """Extract funnel, TA, country, PIC from campaign name.

    Format: {PIC}_{Branch}_[{Funnel}] {Objective}_{Description} {Country}
    Example: Mason_SGN_[TOF] Sales_Landing Page Solo ID
    """
    funnel = None
    for f in ("TOF", "MOF", "BOF"):
        if f"[{f}]" in name:
            funnel = f
            break

    # MOF → High Intent Audience (regardless of TA keyword)
    if funnel == "MOF":
        ta = "High Intent Audience"
    else:
        ta = None
        name_lower = name.lower()
        for kw in TA_KEYWORDS:
            if kw.lower() in name_lower:
                ta = kw
                break

    # Country: look for known tokens in the name (case-insensitive word match)
    country = None
    tokens = re.split(r"[\s_\-]+", name)
    for tok in reversed(tokens):
        key = tok.upper()
        if key in COUNTRY_TOKENS and COUNTRY_TOKENS[key] is not None:
            country = COUNTRY_TOKENS[key]
            break

    # PIC: first segment before underscore
    pic = name.split("_")[0].strip() if "_" in name else None

    return {"funnel": funnel, "ta": ta, "country": country, "pic": pic}


def sync_ads(token: str, account_id: str, date_preset: str = "last_30d") -> list[dict]:
    """Return list of ad-level dicts with insights (no ad copy — Meta API doesn't return revenue per ad)."""

    # ── 1. Fetch all ads (name only — no creative body) ────────────────────
    # Note: date_preset is not supported on /ads — fetch all ads, filter via insights
    ads_raw = _paginate(token, f"{account_id}/ads", {
        "fields": "id,name,campaign_id,adset_id,status",
        "limit": 200,
    })
    ad_map = {a["id"]: a for a in ads_raw}

    # ── 2. Fetch ad-level insights ─────────────────────────────────────────
    insights_raw = _paginate(token, f"{account_id}/insights", {
        "fields": "ad_id,campaign_id,campaign_name,adset_name,spend,impressions,clicks,actions",
        "date_preset": date_preset,
        "level": "ad",
        "limit": 200,
    })

    # ── 3. Merge ───────────────────────────────────────────────────────────
    results = []
    for ins in insights_raw:
        ad_id = ins.get("ad_id", "")
        ad = ad_map.get(ad_id, {})
        campaign_name = ins.get("campaign_name", "")
        parsed = parse_campaign_name(campaign_name)

        actions = ins.get("actions", [])
        leads = next(
            (int(a["value"]) for a in actions
             if a.get("action_type") in ("lead", "onsite_conversion.lead_grouped")),
            0,
        )
        lp_views = next(
            (int(a["value"]) for a in actions
             if a.get("action_type") in ("landing_page_view", "omni_landing_page_view")),
            0,
        )

        results.append({
            "meta_ad_id": ad_id,
            "meta_campaign_id": ins.get("campaign_id", ""),
            "ad_name": ad.get("name", ""),
            "campaign_name": campaign_name,
            "adset_name": ins.get("adset_name", ""),
            "ad_body": "",
            "funnel_stage": parsed["funnel"],
            "target_audience": parsed["ta"],
            "target_country": parsed["country"],
            "pic": parsed["pic"],
            "spend_vnd": float(ins.get("spend", 0)),
            "impressions": int(ins.get("impressions", 0)),
            "clicks": int(ins.get("clicks", 0)),
            "leads": leads,
            "lp_views": lp_views,
            "date_start": ins.get("date_start"),
            "date_stop": ins.get("date_stop"),
        })

    logger.info("Meta sync: %d ads fetched for account %s", len(results), account_id)
    return results
