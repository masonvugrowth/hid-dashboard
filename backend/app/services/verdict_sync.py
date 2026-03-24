"""Nightly verdict sync — three jobs:
1. Sync ad_combos performance from ads_performance via meta_ad_name match
2. Compute combo verdict using TOF Sales benchmark logic (WIN/TEST/LOSE)
3. Compute derived_verdict on Copy and Material components from their combos
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.ad_combo import AdCombo
from app.models.creative_copy import CreativeCopy
from app.models.creative_material import CreativeMaterial
from app.models.ads import AdsPerformance

logger = logging.getLogger(__name__)

# ── Verdict priority for derived_verdict (best of combos) ────
VERDICT_PRIORITY = {"WIN": 3, "TEST": 2, "LOSE": 1}

# ── Thresholds ───────────────────────────────────────────────
MIN_IMPRESSIONS = 20_000
MIN_BOOKINGS = 5


def _compute_branch_benchmarks(db: Session) -> dict[str, float]:
    """Compute AVG ROAS for TOF Sales campaigns per branch from ads_performance."""
    rows = (
        db.query(
            AdsPerformance.branch_id,
            func.sum(func.coalesce(AdsPerformance.revenue_vnd, AdsPerformance.revenue_native)).label("total_rev"),
            func.sum(func.coalesce(AdsPerformance.cost_vnd, AdsPerformance.cost_native)).label("total_cost"),
        )
        .filter(
            AdsPerformance.funnel_stage == "TOF",
            AdsPerformance.campaign_name.ilike("%Sales%"),
            func.coalesce(AdsPerformance.cost_vnd, AdsPerformance.cost_native) > 0,
        )
        .group_by(AdsPerformance.branch_id)
        .all()
    )
    benchmarks = {}
    for r in rows:
        total_rev = float(r.total_rev or 0)
        total_cost = float(r.total_cost or 0)
        if total_cost > 0:
            benchmarks[str(r.branch_id)] = round(total_rev / total_cost, 2)
    return benchmarks


def _is_tof_sales(combo: AdCombo, db: Session) -> tuple[bool, AdsPerformance | None]:
    """Check if a combo's matched ad is a TOF Sales campaign."""
    if not combo.meta_ad_name:
        return False, None
    perf = db.query(AdsPerformance).filter(
        AdsPerformance.ad_name == combo.meta_ad_name
    ).first()
    if not perf:
        return False, None
    if perf.funnel_stage == "TOF" and perf.campaign_name and "sales" in perf.campaign_name.lower():
        return True, perf
    return False, perf


def sync_combo_performance(db: Session) -> int:
    """Job 1: Pull ROAS/Spend/Revenue into ad_combos via meta_ad_name match.
    Then compute verdict using TOF Sales benchmark logic.
    """
    combos = db.query(AdCombo).filter(
        AdCombo.meta_ad_name.isnot(None),
        AdCombo.is_active == True,
    ).all()

    # Compute branch benchmarks once
    benchmarks = _compute_branch_benchmarks(db)

    synced = 0
    for combo in combos:
        perf = db.query(AdsPerformance).filter(
            AdsPerformance.ad_name == combo.meta_ad_name
        ).first()

        if not perf:
            continue

        # Sync performance data
        combo.spend_vnd = getattr(perf, 'cost_vnd', None) or getattr(perf, 'cost_native', None) or 0
        combo.revenue_vnd = getattr(perf, 'revenue_vnd', None) or getattr(perf, 'revenue_native', None) or 0
        spend = float(combo.spend_vnd) if combo.spend_vnd else 0
        rev = float(combo.revenue_vnd) if combo.revenue_vnd else 0
        combo.roas = rev / spend if spend > 0 else None
        combo.impressions = perf.impressions or 0
        combo.clicks = perf.clicks or 0
        combo.leads = getattr(perf, 'leads', None) or 0
        combo.purchases = getattr(perf, 'bookings', None) or 0
        combo.lp_views = getattr(perf, 'lp_views', None) or 0
        combo.add_to_cart = getattr(perf, 'add_to_cart', None) or 0
        combo.initiate_checkout = getattr(perf, 'initiate_checkout', None) or 0
        combo.last_synced_at = datetime.now(timezone.utc)

        # Auto-update verdict only if not manually set
        if combo.verdict_source != "manual":
            is_tof = (perf.funnel_stage == "TOF" and
                      perf.campaign_name and
                      "sales" in perf.campaign_name.lower())

            if not is_tof:
                combo.verdict = "TEST"
                combo.verdict_notes = "not TOF Sales"
                combo.verdict_source = "auto_meta"
            else:
                benchmark = benchmarks.get(str(combo.branch_id))
                impr = combo.impressions or 0
                bk = combo.purchases or 0
                roas = float(combo.roas) if combo.roas else 0

                if impr < MIN_IMPRESSIONS or bk < MIN_BOOKINGS:
                    combo.verdict = "TEST"
                    reasons = []
                    if impr < MIN_IMPRESSIONS:
                        reasons.append(f"{impr/1000:.1f}K/{MIN_IMPRESSIONS/1000:.0f}K impr")
                    if bk < MIN_BOOKINGS:
                        reasons.append(f"{bk}/{MIN_BOOKINGS} bookings")
                    combo.verdict_notes = "insufficient data: " + ", ".join(reasons)
                elif not benchmark or benchmark == 0:
                    combo.verdict = "TEST"
                    combo.verdict_notes = "no benchmark"
                elif roas >= benchmark:
                    combo.verdict = "WIN"
                    combo.verdict_notes = f"ROAS {roas:.2f}x vs BM {benchmark}x"
                elif roas <= 0.6 * benchmark:
                    combo.verdict = "LOSE"
                    combo.verdict_notes = f"ROAS {roas:.2f}x vs BM {benchmark}x (≤0.6×)"
                else:
                    combo.verdict = "TEST"
                    combo.verdict_notes = f"ROAS {roas:.2f}x vs BM {benchmark}x"
                combo.verdict_source = "auto_meta"

        synced += 1

    db.commit()
    logger.info("Verdict sync: %d/%d combos synced", synced, len(combos))
    return synced


def compute_derived_verdicts(db: Session) -> int:
    """Job 2: Compute derived_verdict on Copy and Material from their combos.

    Each component gets the best verdict among all its combos with real data.
    Verdict priority: WIN > TEST > LOSE
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
