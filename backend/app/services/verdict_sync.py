"""Nightly verdict sync — two jobs:
1. Sync ad_combos performance from ads_performance via meta_ad_name match
2. Compute derived_verdict on Copy and Material components from their combos
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.ad_combo import AdCombo
from app.models.creative_copy import CreativeCopy
from app.models.creative_material import CreativeMaterial
from app.models.ads import AdsPerformance

logger = logging.getLogger(__name__)

VERDICT_PRIORITY = {"winning": 5, "good": 4, "neutral": 3, "underperformer": 2, "kill": 1}


def roas_to_verdict(roas: float) -> str:
    if roas >= 3.0:
        return "winning"
    elif roas >= 1.5:
        return "good"
    elif roas >= 0.8:
        return "neutral"
    elif roas >= 0.3:
        return "underperformer"
    else:
        return "kill"


def sync_combo_performance(db: Session) -> int:
    """Job 1: Pull ROAS/Spend/Revenue into ad_combos via meta_ad_name match."""
    combos = db.query(AdCombo).filter(
        AdCombo.meta_ad_name.isnot(None),
        AdCombo.is_active == True,
    ).all()

    synced = 0
    for combo in combos:
        perf = db.query(AdsPerformance).filter(
            AdsPerformance.ad_name == combo.meta_ad_name
        ).first()

        if not perf:
            continue

        combo.spend_vnd = getattr(perf, 'cost_vnd', None) or getattr(perf, 'cost_native', None) or 0
        combo.revenue_vnd = getattr(perf, 'revenue_vnd', None) or getattr(perf, 'revenue_native', None) or 0
        spend = float(combo.spend_vnd) if combo.spend_vnd else 0
        rev = float(combo.revenue_vnd) if combo.revenue_vnd else 0
        combo.roas = rev / spend if spend > 0 else None
        combo.impressions = perf.impressions or 0
        combo.clicks = perf.clicks or 0
        combo.leads = getattr(perf, 'leads', None) or 0
        combo.purchases = getattr(perf, 'bookings', None) or 0
        combo.last_synced_at = datetime.now(timezone.utc)

        # Auto-update verdict only if not manually set
        if combo.verdict_source != "manual" and combo.roas is not None:
            combo.verdict = roas_to_verdict(float(combo.roas))
            combo.verdict_source = "auto_meta"

        synced += 1

    db.commit()
    logger.info("Verdict sync: %d/%d combos synced", synced, len(combos))
    return synced


def compute_derived_verdicts(db: Session) -> int:
    """Job 2: Compute derived_verdict on Copy and Material from their combos.

    Each component gets the best verdict among all its combos with real data.
    Verdict priority: winning > good > neutral > underperformer > kill
    """
    updated = 0

    # Copies
    for copy in db.query(CreativeCopy).filter(CreativeCopy.is_active == True).all():
        combos = db.query(AdCombo).filter(
            AdCombo.copy_id == copy.id,
            AdCombo.verdict.isnot(None),
            AdCombo.is_active == True,
        ).all()

        if combos:
            best = max(combos, key=lambda c: VERDICT_PRIORITY.get(c.verdict, 0))
            copy.derived_verdict = best.verdict
            copy.combo_count = len(combos)
            updated += 1
        else:
            copy.combo_count = 0

    # Materials
    for mat in db.query(CreativeMaterial).filter(CreativeMaterial.is_active == True).all():
        combos = db.query(AdCombo).filter(
            AdCombo.material_id == mat.id,
            AdCombo.verdict.isnot(None),
            AdCombo.is_active == True,
        ).all()

        if combos:
            best = max(combos, key=lambda c: VERDICT_PRIORITY.get(c.verdict, 0))
            mat.derived_verdict = best.verdict
            mat.combo_count = len(combos)
            updated += 1
        else:
            mat.combo_count = 0

    db.commit()
    logger.info("Derived verdicts: %d components updated", updated)
    return updated
