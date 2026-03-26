"""
Sync KOL records from a Lark CSV export.

Upsert key: kol_name (KOL_RatePlanName).
If kol_name already exists → update, otherwise → create.
"""
from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.kol import KOLRecord

log = logging.getLogger(__name__)

# CSV column headers (from Lark export)
COL_NAME = "KOL_RatePlanName"
COL_BRANCH = "Branch"
COL_PUBLISHED = "Published Date"
COL_COST = "Cost (VND)"
COL_NATIONALITY = "KOL Nationality"
COL_LANGUAGE = "Language"
COL_IG = "Link video IG"
COL_TIKTOK = "Link video TikTok"
COL_YOUTUBE = "Link video Youtube"
COL_AUDIENCE = "Target Audience"


def _parse_cost(val: str) -> Optional[float]:
    """Parse cost like '800,000' or '10,800,000' → float. Returns None for empty."""
    if not val or not val.strip():
        return None
    cleaned = re.sub(r"[,\s]", "", val.strip())
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_date(val: str) -> Optional[str]:
    """Parse M/D/YYYY → YYYY-MM-DD."""
    if not val or not val.strip():
        return None
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(val.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _clean_link(val: str) -> Optional[str]:
    """Return link or None if empty."""
    v = (val or "").strip()
    return v if v else None


def _build_branch_map(db: Session) -> dict[str, str]:
    """Return {lowercase_short_name: branch_id_str}.

    DB names are like 'MEANDER Saigon', CSV uses 'Saigon'.
    Map both full name and short suffix for flexible matching.
    """
    branches = db.query(Branch).filter(Branch.is_active.is_(True)).all()
    m: dict[str, str] = {}
    for b in branches:
        bid = str(b.id)
        full = b.name.lower()
        m[full] = bid
        # Also map the short suffix: "MEANDER Saigon" → "saigon"
        parts = full.split()
        if len(parts) > 1:
            m[parts[-1]] = bid  # "saigon", "osaka", "1948", "oani", "taipei"
    return m


def sync_kol_csv(db: Session, csv_content: str) -> dict:
    """
    Parse CSV content and upsert KOL records.

    Returns: {"created": N, "updated": N, "skipped": N, "errors": [...]}
    """
    branch_map = _build_branch_map(db)

    reader = csv.DictReader(io.StringIO(csv_content))

    created = 0
    updated = 0
    skipped = 0
    errors = []

    for i, row in enumerate(reader, start=2):  # row 1 is header
        kol_name = (row.get(COL_NAME) or "").strip()
        if not kol_name:
            skipped += 1
            continue

        branch_raw = (row.get(COL_BRANCH) or "").strip().lower()
        branch_id = branch_map.get(branch_raw)
        if not branch_id:
            errors.append(f"Row {i}: unknown branch '{row.get(COL_BRANCH)}' for {kol_name}")
            skipped += 1
            continue

        cost_vnd = _parse_cost(row.get(COL_COST, ""))
        is_gifted = cost_vnd is not None and cost_vnd == 0

        data = {
            "branch_id": branch_id,
            "kol_nationality": (row.get(COL_NATIONALITY) or "").strip() or None,
            "language": (row.get(COL_LANGUAGE) or "").strip() or None,
            "target_audience": (row.get(COL_AUDIENCE) or "").strip() or None,
            "cost_vnd": cost_vnd,
            "is_gifted_stay": is_gifted,
            "published_date": _parse_date(row.get(COL_PUBLISHED, "")),
            "link_ig": _clean_link(row.get(COL_IG)),
            "link_tiktok": _clean_link(row.get(COL_TIKTOK)),
            "link_youtube": _clean_link(row.get(COL_YOUTUBE)),
        }

        try:
            existing = db.query(KOLRecord).filter(KOLRecord.kol_name == kol_name).first()
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                obj = KOLRecord(kol_name=kol_name, **data)
                db.add(obj)
                created += 1
        except Exception as e:
            errors.append(f"Row {i}: {kol_name} — {str(e)}")
            skipped += 1

    db.commit()
    log.info("KOL CSV sync: created=%d updated=%d skipped=%d errors=%d",
             created, updated, skipped, len(errors))

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:20],  # cap error list
    }
