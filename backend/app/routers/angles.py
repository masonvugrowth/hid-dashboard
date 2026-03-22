"""Ad Angles router — WIN/TEST/LOSE scoring from creative_angles + ad_combos"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.creative_angle import CreativeAngle
from app.models.ad_combo import AdCombo

router = APIRouter()


def _envelope(data):
    return {"success": True, "data": data, "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat()}


class AngleIn(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[str] = None  # WIN, TEST, LOSE
    branch_id: Optional[UUID] = None
    created_by: Optional[str] = None


# ── verdict → WIN/TEST/LOSE mapping ──────────────────────────
VERDICT_TO_STATUS = {
    "winning": "WIN",
    "good": "WIN",
    "neutral": "TEST",
    "underperformer": "LOSE",
    "kill": "LOSE",
}


def _compute_score(roas, ctr_pct, cpb_native, bookings):
    """
    Angle score 0-100:
    ROAS 40% + CTR 25% + CPB(inverted) 25% + volume 10%
    Each component normalized 0-1 then weighted.
    """
    if roas is None and ctr_pct is None and cpb_native is None and bookings == 0:
        return None

    # ROAS: 0-5+ mapped to 0-1 (cap at 5)
    roas_score = min((roas or 0) / 5.0, 1.0) * 0.40

    # CTR: 0-5% mapped to 0-1 (cap at 5%)
    ctr_score = min((ctr_pct or 0) / 5.0, 1.0) * 0.25

    # CPB (cost per booking): lower is better; 0-500 native range inverted
    if cpb_native and cpb_native > 0:
        cpb_score = max(0, 1 - (cpb_native / 500)) * 0.25
    else:
        cpb_score = 0.0

    # Volume: 0-50 bookings mapped to 0-1
    vol_score = min((bookings or 0) / 50.0, 1.0) * 0.10

    return round((roas_score + ctr_score + cpb_score + vol_score) * 100, 1)


def _derive_status(combos_verdicts: list[str]) -> Optional[str]:
    """Derive angle status from its combos' verdicts using majority rule."""
    if not combos_verdicts:
        return "TEST"  # no combos yet → testing
    statuses = [VERDICT_TO_STATUS.get(v, "TEST") for v in combos_verdicts if v]
    if not statuses:
        return "TEST"
    # majority vote
    from collections import Counter
    counts = Counter(statuses)
    return counts.most_common(1)[0][0]


@router.get("")
def list_angles(
    branch_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    # Query creative_angles (the real source of truth)
    q = db.query(CreativeAngle).filter(CreativeAngle.is_active == True)
    if branch_id:
        q = q.filter(CreativeAngle.branch_id == branch_id)
    angles = q.order_by(CreativeAngle.created_at.desc()).all()

    # Aggregate ad_combos stats per angle
    stats_q = (
        db.query(
            AdCombo.angle_id,
            func.coalesce(func.sum(AdCombo.spend_vnd), 0).label("cost"),
            func.coalesce(func.sum(AdCombo.revenue_vnd), 0).label("revenue"),
            func.coalesce(func.sum(AdCombo.impressions), 0).label("impressions"),
            func.coalesce(func.sum(AdCombo.clicks), 0).label("clicks"),
            func.coalesce(func.sum(AdCombo.purchases), 0).label("bookings"),
        )
        .filter(AdCombo.angle_id.isnot(None), AdCombo.is_active == True)
    )
    if branch_id:
        stats_q = stats_q.filter(AdCombo.branch_id == branch_id)
    stats_map = {str(r.angle_id): r for r in stats_q.group_by(AdCombo.angle_id).all()}

    # Gather verdicts per angle for status derivation
    verdict_q = (
        db.query(AdCombo.angle_id, AdCombo.verdict)
        .filter(AdCombo.angle_id.isnot(None), AdCombo.is_active == True, AdCombo.verdict.isnot(None))
    )
    if branch_id:
        verdict_q = verdict_q.filter(AdCombo.branch_id == branch_id)
    verdicts_map: dict[str, list[str]] = {}
    for row in verdict_q.all():
        verdicts_map.setdefault(str(row.angle_id), []).append(row.verdict)

    result = []
    for a in angles:
        aid = str(a.id)
        s = stats_map.get(aid)
        cost = float(s.cost) if s else 0
        rev = float(s.revenue) if s else 0
        impr = int(s.impressions) if s else 0
        clicks = int(s.clicks) if s else 0
        bookings = int(s.bookings) if s else 0

        roas = round(rev / cost, 2) if cost > 0 else None
        ctr_pct = round(clicks / impr * 100, 2) if impr > 0 else None
        cpb = round(cost / bookings, 2) if bookings > 0 else None
        score = _compute_score(roas, ctr_pct, cpb, bookings)

        angle_status = _derive_status(verdicts_map.get(aid, []))

        result.append({
            "id": aid,
            "angle_code": a.angle_code,
            "name": a.name,
            "description": a.notes,
            "hook_type": a.hook_type,
            "keypoint_1": a.keypoint_1,
            "keypoint_2": a.keypoint_2,
            "keypoint_3": a.keypoint_3,
            "keypoint_4": a.keypoint_4,
            "keypoint_5": a.keypoint_5,
            "status": angle_status,
            "branch_id": str(a.branch_id) if a.branch_id else None,
            "created_by": None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            # Aggregated from ad_combos
            "cost_native": cost,
            "revenue_native": rev,
            "impressions": impr,
            "clicks": clicks,
            "bookings": bookings,
            "roas": roas,
            "ctr_pct": ctr_pct,
            "cpb_native": cpb,
            "score": score,
            "combo_count": len(verdicts_map.get(aid, [])),
        })

    # Filter by status if requested
    if status:
        result = [r for r in result if r["status"] == status]

    # Sort by score desc, then status order WIN > TEST > LOSE
    status_order = {"WIN": 0, "TEST": 1, "LOSE": 2, None: 3}
    result.sort(key=lambda x: (status_order.get(x["status"], 3), -(x["score"] or 0)))
    return _envelope(result)


@router.post("")
def create_angle(body: AngleIn, db: Session = Depends(get_db)):
    """Create a new creative angle (redirects to creative_angles table)."""
    from app.services.id_generator import generate_code
    angle_code = generate_code(db, "ANG", "creative_angles", "angle_code")
    obj = CreativeAngle(
        angle_code=angle_code,
        name=body.name,
        hook_type="Story",  # default
        keypoint_1=body.description or body.name,
        branch_id=body.branch_id,
        notes=body.description,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _envelope({"id": str(obj.id), "name": obj.name, "status": "TEST"})


@router.put("/{angle_id}")
def update_angle(angle_id: UUID, body: AngleIn, db: Session = Depends(get_db)):
    obj = db.query(CreativeAngle).filter(CreativeAngle.id == angle_id, CreativeAngle.is_active == True).first()
    if not obj:
        raise HTTPException(404, "Angle not found")
    obj.name = body.name
    if body.description:
        obj.notes = body.description
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return _envelope({"id": str(obj.id), "name": obj.name, "status": "TEST"})


@router.delete("/{angle_id}")
def delete_angle(angle_id: UUID, db: Session = Depends(get_db)):
    obj = db.query(CreativeAngle).filter(CreativeAngle.id == angle_id).first()
    if not obj:
        raise HTTPException(404, "Angle not found")
    obj.is_active = False
    db.commit()
    return _envelope({"deleted": str(angle_id)})
