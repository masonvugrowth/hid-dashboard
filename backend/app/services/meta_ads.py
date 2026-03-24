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


def sync_ads(
    token: str,
    account_id: str,
    date_preset: str = "last_30d",
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    """Return list of ad-level dicts with insights.
    If date_from/date_to provided, uses time_range instead of date_preset.
    """
    import json

    # ── 1. Fetch all ads (name only — no creative body) ────────────────────
    ads_raw = _paginate(token, f"{account_id}/ads", {
        "fields": "id,name,campaign_id,adset_id,status",
        "limit": 200,
    })
    ad_map = {a["id"]: a for a in ads_raw}

    # ── 2. Build date filter ───────────────────────────────────────────────
    insight_params: dict = {
        "fields": "ad_id,campaign_id,campaign_name,adset_name,spend,impressions,clicks,actions,action_values",
        "level": "ad",
        "limit": 200,
    }
    if date_from or date_to:
        from datetime import date
        since = date_from or date.today().replace(day=1).isoformat()
        until = date_to or date.today().isoformat()
        insight_params["time_range"] = json.dumps({"since": since, "until": until})
    else:
        insight_params["date_preset"] = date_preset

    # ── 3. Fetch ad-level insights ─────────────────────────────────────────
    insights_raw = _paginate(token, f"{account_id}/insights", insight_params)

    # ── 4. Merge ───────────────────────────────────────────────────────────
    results = []
    for ins in insights_raw:
        ad_id = ins.get("ad_id", "")
        ad = ad_map.get(ad_id, {})
        campaign_name = ins.get("campaign_name", "")
        parsed = parse_campaign_name(campaign_name)

        actions = ins.get("actions", [])
        action_values = ins.get("action_values", [])
        PURCHASE_TYPES = ("purchase", "offsite_conversion.fb_pixel_purchase", "omni_purchase", "onsite_conversion.purchase")
        leads = next((int(float(a["value"])) for a in actions if a.get("action_type") in ("lead", "onsite_conversion.lead_grouped")), 0)
        lp_views = next((int(float(a["value"])) for a in actions if a.get("action_type") in ("landing_page_view", "omni_landing_page_view")), 0)
        add_to_cart = next((int(float(a["value"])) for a in actions if a.get("action_type") in ("add_to_cart", "offsite_conversion.fb_pixel_add_to_cart", "omni_add_to_cart")), 0)
        initiate_checkout = next((int(float(a["value"])) for a in actions if a.get("action_type") in ("initiate_checkout", "offsite_conversion.fb_pixel_initiate_checkout", "omni_initiated_checkout")), 0)
        bookings = next((int(float(a["value"])) for a in actions if a.get("action_type") in PURCHASE_TYPES), 0)
        revenue = next((float(a["value"]) for a in action_values if a.get("action_type") in PURCHASE_TYPES), 0.0)

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
            "add_to_cart": add_to_cart,
            "initiate_checkout": initiate_checkout,
            "bookings": bookings,
            "revenue": revenue,
            "date_start": ins.get("date_start"),
            "date_stop": ins.get("date_stop"),
        })

    logger.info("Meta sync: %d ads fetched for account %s", len(results), account_id)
    return results


# ── Ad Creative fetcher ─────────────────────────────────────────────────
def fetch_ad_creatives(
    token: str,
    account_id: str,
    status_filter: str = "ACTIVE",
) -> list[dict]:
    """Fetch all ads with their creative content (headline, body, image/video URL).

    Returns list of dicts, each representing one ad with its creative:
      ad_id, ad_name, campaign_name, adset_name, status,
      headline, primary_text, image_url, video_thumb_url,
      call_to_action_type, link_url, target_audience, country, funnel
    """
    # 1. Fetch ads with creative fields + preview link
    ads_raw = _paginate(token, f"{account_id}/ads", {
        "fields": ",".join([
            "id", "name", "status",
            "preview_shareable_link",
            "campaign{id,name}",
            "adset{id,name,targeting}",
            "creative{id,name,title,body,image_url,thumbnail_url,"
            "object_story_spec,asset_feed_spec,effective_object_story_id}",
        ]),
        "filtering": f'[{{"field":"effective_status","operator":"IN","value":["{status_filter}"]}}]',
        "limit": 200,
    })

    results = []
    for ad in ads_raw:
        ad_id = ad.get("id", "")
        ad_name = ad.get("name", "")
        campaign = ad.get("campaign", {})
        campaign_name = campaign.get("name", "")
        adset = ad.get("adset", {})
        adset_name = adset.get("name", "")
        creative = ad.get("creative", {})
        parsed = parse_campaign_name(campaign_name)

        # Extract creative content
        headline = creative.get("title", "")
        body = creative.get("body", "")
        image_url = creative.get("image_url", "")
        video_thumb = creative.get("thumbnail_url", "")

        # Try deeper: object_story_spec has the real creative data
        oss = creative.get("object_story_spec", {})
        link_data = oss.get("link_data", {})
        video_data = oss.get("video_data", {})

        if not headline and link_data:
            headline = link_data.get("name", "") or link_data.get("title", "")
        if not body and link_data:
            body = link_data.get("message", "")
        if not body and video_data:
            body = video_data.get("message", "")
        if not image_url and link_data:
            image_url = link_data.get("image_hash", "") or link_data.get("picture", "")
        if not video_thumb and video_data:
            video_thumb = video_data.get("image_url", "")

        link_url = link_data.get("link", "") or video_data.get("call_to_action", {}).get("value", {}).get("link", "")
        cta_type = link_data.get("call_to_action", {}).get("type", "")

        # Determine if this is video or image
        has_video = bool(video_data or video_thumb)

        # Try asset_feed_spec for dynamic creatives
        afs = creative.get("asset_feed_spec", {})
        if afs and not body:
            bodies = afs.get("bodies", [])
            if bodies:
                body = bodies[0].get("text", "")
        if afs and not headline:
            titles = afs.get("titles", [])
            if titles:
                headline = titles[0].get("text", "")

        # Skip ads with no creative content
        if not body and not headline and not image_url and not video_thumb:
            continue

        # Preview link: shareable ad preview URL (full-size, not thumbnail)
        preview_link = ad.get("preview_shareable_link", "")

        results.append({
            "ad_id": ad_id,
            "ad_name": ad_name,
            "campaign_name": campaign_name,
            "adset_name": adset_name,
            "status": ad.get("status", ""),
            "headline": headline,
            "primary_text": body,
            "image_url": image_url,
            "video_thumb_url": video_thumb,
            "preview_link": preview_link,
            "has_video": has_video,
            "call_to_action_type": cta_type,
            "link_url": link_url,
            "target_audience": parsed["ta"],
            "country": parsed["country"],
            "funnel": parsed["funnel"],
            "pic": parsed["pic"],
        })

    logger.info("Meta creatives: %d ads with content for account %s", len(results), account_id)
    return results
