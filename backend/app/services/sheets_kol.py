"""
Sync KOL booking data from the combined KOL Google Sheet.

Sheet: "KOL Combine All Branch (VND)"
Spreadsheet: 1K9EIAzCUpWaTsXFvmGhYTfyq8f_SjcR-e1fx3mUqV0s

Column indices (0-based):
  0  → Branch (Saigon, Osaka, Taipei, 1948, Oani)
  3  → Published Date (M/D/YYYY)
  6  → Invitation Date
  7  → Reservation Number (cloudbeds_reservation_id)
  8  → Revenue VND (e.g. "3,240,000 ₫")
  13 → KOL Rate Plan Name (e.g. "KOL_Kennababe")
  14 → KOL Nationality
"""
from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

SHEETS_API   = "https://sheets.googleapis.com/v4/spreadsheets"
TOKEN_URL    = "https://oauth2.googleapis.com/token"

KOL_SHEET_ID = "1K9EIAzCUpWaTsXFvmGhYTfyq8f_SjcR-e1fx3mUqV0s"
KOL_TAB      = "KOL Combine All Branch (VND)"

COL_BRANCH      = 0
COL_PUBLISHED   = 3
COL_INVITATION  = 6
COL_RES_NUM     = 7
COL_REVENUE_VND = 8
COL_KOL_NAME    = 13
COL_NATIONALITY = 14


def _get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def _read_sheet(access_token: str, spreadsheet_id: str, tab: str) -> list[list[str]]:
    url = f"{SHEETS_API}/{spreadsheet_id}/values/{urllib.parse.quote(tab)}?majorDimension=ROWS"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("values", [])


def _safe(row: list, idx: int) -> str:
    try:
        return str(row[idx]).strip()
    except IndexError:
        return ""


def _parse_vnd(val: str) -> Optional[float]:
    """Parse VND amount like '3,240,000 ₫' → 3240000.0"""
    if not val:
        return None
    v = re.sub(r"[₫VND,\s]", "", val).strip()
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _parse_date(val: str) -> Optional[str]:
    """Parse M/D/YYYY, MM/DD/YYYY, DD/MM/YYYY → YYYY-MM-DD"""
    if not val:
        return None
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(val.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def read_kol_bookings(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    spreadsheet_id: str = KOL_SHEET_ID,
    tab: str = KOL_TAB,
) -> list[dict]:
    """
    Read all KOL booking rows from the sheet.
    Returns list of dicts, one per booking row.
    """
    access_token = _get_access_token(client_id, client_secret, refresh_token)
    rows = _read_sheet(access_token, spreadsheet_id, tab)

    if not rows or len(rows) < 2:
        log.warning("KOL sheet empty or missing header")
        return []

    results = []
    for row in rows[1:]:  # skip header
        branch_raw = _safe(row, COL_BRANCH)
        kol_raw    = _safe(row, COL_KOL_NAME)
        res_num    = _safe(row, COL_RES_NUM)

        if not branch_raw or not kol_raw or not res_num:
            continue

        # Strip "KOL_" prefix
        kol_name = kol_raw[4:].strip() if kol_raw.upper().startswith("KOL_") else kol_raw.strip()
        if not kol_name:
            continue

        results.append({
            "branch_name":    branch_raw,
            "kol_name":       kol_name,
            "kol_raw":        kol_raw,
            "res_num":        res_num,
            "revenue_vnd":    _parse_vnd(_safe(row, COL_REVENUE_VND)) or 0.0,
            "published_date": _parse_date(_safe(row, COL_PUBLISHED)),
            "invitation_date":_parse_date(_safe(row, COL_INVITATION)),
            "kol_nationality":_safe(row, COL_NATIONALITY) or None,
        })

    log.info("KOL sheet: %d booking rows parsed", len(results))
    return results
