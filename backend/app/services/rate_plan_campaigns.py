"""Hand-typed rate plan → campaign labels, and how reports display them.

The team types a campaign name once per CRM rate plan on Marketing Activity
→ CRM Reservations (see app/models/rate_plan_campaign.py). Wherever a report
lists CRM reservations by rate plan, that campaign name is what it shows —
and a rate plan nobody has labelled keeps showing its rate plan name, so a
half-filled table still reads.

Labels are applied at READ time, never baked into a cached payload: the
Weekly and Bi-Weekly reports cache their JSON, and renaming a campaign has
to show up on the next page load, not on the next rebuild.
"""
import logging
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.rate_plan_campaign import RatePlanCampaign

log = logging.getLogger(__name__)


def campaign_map(db: Session) -> Dict[str, str]:
    """{rate_plan_name: campaign_name} for every label the team has tagged.

    Zeabur does not run Alembic on deploy, so between this code landing and
    `POST /api/sync/run-migrations` the table does not exist — and the CRM
    surfaces read it on every request. An unlabelled table is a far smaller
    problem than a 500 on the report it lives in, so a failure here degrades
    to "nothing tagged yet".
    """
    try:
        rows = db.query(RatePlanCampaign).all()
    except Exception:
        db.rollback()
        log.warning("rate_plan_campaigns unavailable — serving empty campaign map",
                    exc_info=True)
        return {}
    return {r.rate_plan_name: r.campaign_name for r in rows}


def label_rows(rows: Optional[Iterable[dict]], cmap: Dict[str, str]) -> None:
    """Stamp `campaign_name` + display `label` onto by_rate_plan rows in place.

    `label` is what every renderer prints; `rate_plan_name` is left alone
    because it is the join key for prior/year-ago rows and the anchor for
    comment and flag-override keys.
    """
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        campaign = cmap.get(r.get("rate_plan_name") or "")
        r["campaign_name"] = campaign or None
        if campaign:
            r["label"] = campaign
        elif not r.get("label"):
            r["label"] = r.get("rate_plan_name") or "—"


def _crm_sections(branch: dict) -> List[dict]:
    """The CRM dicts inside one branch payload — Bi-Weekly nests it at the
    top level, the Weekly report under `analytics`."""
    out = []
    for section in (branch.get("crm"),
                    (branch.get("analytics") or {}).get("crm")):
        if isinstance(section, dict):
            out.append(section)
    return out


def apply_campaign_labels(db: Session, payload) -> None:
    """Relabel every by_rate_plan row in a report payload, in place.

    Accepts the list-of-branches payload both the Weekly and the Bi-Weekly
    report use. Safe to call on a payload that has no CRM section.
    """
    if not payload:
        return
    cmap = campaign_map(db)
    if not cmap:
        return
    for branch in payload:
        if not isinstance(branch, dict):
            continue
        for section in _crm_sections(branch):
            label_rows(section.get("by_rate_plan"), cmap)
