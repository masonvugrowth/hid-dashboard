"""
Pull grand_total_native from Cloudbeds reservation Google Sheets.

Column indices (0-based, same across all 5 branches):
  9  → Reservation Number (cloudbeds_reservation_id)
  24 → Accommodation Total
  26 → Check in Date      (DD/MM/YYYY)
  27 → Check out Date
  28 → Nights
  30 → Grand Total        ← primary revenue field
  36 → Source
  38 → Status
  39 → Country

Excluded statuses: Cancelled, Canceled, No-Show, No Show
Excluded sources:  KOL, Blogger, Maintenance, House Use, Day Use
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)

SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
TOKEN_URL  = "https://oauth2.googleapis.com/token"

EXCLUDED_STATUSES = {"cancelled", "canceled", "no-show", "no show", "noshow"}
EXCLUDED_SOURCES  = {"kol", "blogger", "maintenance", "house use", "day use", "houseuse", "dayuse", "maintain"}

# Column indices
COL_RES_NUM   = 9
COL_ACCOM     = 24
COL_CHECKIN   = 26
COL_NIGHTS    = 28
COL_GRAND     = 30
COL_SOURCE    = 36
COL_STATUS    = 38
COL_COUNTRY   = 39


def _get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def _read_sheet(access_token: str, spreadsheet_id: str, tab: str = "Raw_data") -> list[list[str]]:
    url = f"{SHEETS_API}/{spreadsheet_id}/values/{urllib.parse.quote(tab)}?majorDimension=ROWS"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("values", [])


def _safe(row: list, idx: int) -> str:
    try: return str(row[idx]).strip()
    except IndexError: return ""


def _parse_float(val: str) -> Optional[float]:
    if not val: return None
    try:
        # Handle European format (1.234,56) or standard (1234.56 or 1,234.56)
        v = val.replace(" ", "")
        if "," in v and "." in v:
            # Determine which is thousands vs decimal
            if v.rindex(",") > v.rindex("."):
                v = v.replace(".", "").replace(",", ".")
            else:
                v = v.replace(",", "")
        elif "," in v:
            # Could be thousands sep or decimal
            parts = v.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                v = v.replace(",", ".")   # decimal comma
            else:
                v = v.replace(",", "")    # thousands comma
        return float(v)
    except (ValueError, AttributeError):
        return None


def read_revenue_from_sheet(
    spreadsheet_id: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    tab: str = "Raw_data",
) -> list[dict]:
    """
    Read all reservation rows from Google Sheet.
    Returns list of dicts: {reservation_number, grand_total, check_in, nights, status}
    Excludes cancelled/no-show reservations.
    """
    access_token = _get_access_token(client_id, client_secret, refresh_token)
    rows = _read_sheet(access_token, spreadsheet_id, tab)

    if not rows or len(rows) < 2:
        return []

    results = []
    skipped = 0

    for row in rows[1:]:  # skip header
        res_num = _safe(row, COL_RES_NUM)
        if not res_num or not res_num.isdigit():
            skipped += 1
            continue

        status = _safe(row, COL_STATUS).lower().replace("-", " ")
        if status in EXCLUDED_STATUSES:
            skipped += 1
            continue

        source = _safe(row, COL_SOURCE).lower().strip()
        if source in EXCLUDED_SOURCES:
            skipped += 1
            continue

        grand_total = _parse_float(_safe(row, COL_GRAND))
        if grand_total is None or grand_total <= 0:
            # Fallback to Accommodation Total
            grand_total = _parse_float(_safe(row, COL_ACCOM))

        if grand_total is None or grand_total <= 0:
            skipped += 1
            continue

        results.append({
            "reservation_number": res_num,
            "grand_total": grand_total,
            "check_in": _safe(row, COL_CHECKIN),
            "nights": _safe(row, COL_NIGHTS),
            "status": _safe(row, COL_STATUS),
        })

    log.info("Sheet read: %d valid rows, %d skipped", len(results), skipped)
    return results
