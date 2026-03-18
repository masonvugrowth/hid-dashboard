"""
Google Sheets → Google Ads sync service.

Each branch has a Google Sheet with a "Google Ads" tab containing daily ad data
exported from Google Ads. This service reads those sheets and upserts rows into
the ads_performance table.

Column mapping (0-indexed):
  0:  Channel          → channel
  1:  Funnel           → funnel_stage
  2:  Day              → date_from / date_to  (M/D/YYYY)
  3:  Week
  4:  Month
  5:  Campaign category → campaign_category
  6:  Country          → target_country
  7:  Cost (-VAT)      → cost_native
  8:  Impression       → impressions
  9:  Leads            → leads
  10: Cost per lead
  11: Booking          → bookings
  12: Cost per booking
  13: Revenue          → revenue_native
  14: ROAS
  15: Clicks           → clicks
  16: CPC
  17: CTR
  18: CPM
  25: Campaign name    → campaign_name
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Optional

log = logging.getLogger(__name__)

SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEET_TAB = "Google Ads"


# ── OAuth helpers ─────────────────────────────────────────────────────────────

def _get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def _read_sheet(access_token: str, spreadsheet_id: str, tab: str = SHEET_TAB) -> list[list[str]]:
    url = (
        f"{SHEETS_API_BASE}/{spreadsheet_id}/values/{urllib.parse.quote(tab)}"
        "?majorDimension=ROWS"
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("values", [])


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_date(val: str) -> Optional[date]:
    """Parse M/D/YYYY or YYYY-MM-DD → date."""
    val = val.strip()
    if not val:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            pass
    return None


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


def _safe(row: list[str], idx: int) -> str:
    try:
        return row[idx].strip()
    except IndexError:
        return ""


# ── Main sync ─────────────────────────────────────────────────────────────────

def sync_google_ads_sheet(
    branch_id: str,
    branch_name: str,
    spreadsheet_id: str,
    currency: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """
    Read a branch's Google Ads Google Sheet and return structured rows.
    Filters by date_from / date_to if provided.
    Returns: {"rows": [...], "fetched": N, "filtered": N}
    """
    access_token = _get_access_token(client_id, client_secret, refresh_token)
    raw = _read_sheet(access_token, spreadsheet_id)

    if not raw or len(raw) < 2:
        return {"rows": [], "fetched": 0, "filtered": 0}

    headers = raw[0]
    data_rows = raw[1:]
    fetched = len(data_rows)
    parsed = []

    for row in data_rows:
        # Skip empty / header repeat rows
        channel = _safe(row, 0)
        if not channel or channel.lower() == "channel":
            continue

        row_date = _parse_date(_safe(row, 2))
        if row_date is None:
            continue

        # Date filter
        if date_from and row_date < date_from:
            continue
        if date_to and row_date > date_to:
            continue

        cost = _parse_float(_safe(row, 7))
        parsed.append({
            "branch_id":        branch_id,
            "channel":          channel or "Google",
            "funnel_stage":     _safe(row, 1),
            "date_from":        row_date,
            "date_to":          row_date,
            "campaign_category": _safe(row, 5),
            "target_country":   _safe(row, 6),
            "cost_native":      cost,
            "cost_vnd":         None,  # caller converts if needed
            "impressions":      _parse_int(_safe(row, 8)),
            "leads":            _parse_int(_safe(row, 9)),
            "bookings":         _parse_int(_safe(row, 11)),
            "revenue_native":   _parse_float(_safe(row, 13)),
            "revenue_vnd":      None,
            "clicks":           _parse_int(_safe(row, 15)),
            "campaign_name":    _safe(row, 25) or _safe(row, 26),
            "currency":         currency,
        })

    return {"rows": parsed, "fetched": fetched, "filtered": len(parsed)}
