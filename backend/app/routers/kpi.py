from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.branch import Branch
from app.models.kpi import KPITarget
from app.services.kpi_engine import compute_kpi_summary, compute_next_month_forecast

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class KPITargetCreate(BaseModel):
    branch_id: UUID
    year: int
    month: int
    target_revenue_native: float
    target_revenue_vnd: float
    predicted_occ_pct: Optional[float] = None


class KPITargetPatch(BaseModel):
    target_revenue_native: Optional[float] = None
    target_revenue_vnd: Optional[float] = None
    predicted_occ_pct: Optional[float] = None
    predicted_room_occ_pct: Optional[float] = None
    predicted_dorm_occ_pct: Optional[float] = None


class KPITargetUpsert(BaseModel):
    branch_id: UUID
    year: int
    month: int
    target_revenue_native: float
    predicted_occ_pct: Optional[float] = None
    predicted_room_occ_pct: Optional[float] = None
    predicted_dorm_occ_pct: Optional[float] = None


class KPITargetOut(BaseModel):
    id: UUID
    branch_id: UUID
    year: int
    month: int
    target_revenue_native: float
    target_revenue_vnd: float
    predicted_occ_pct: Optional[float]
    predicted_room_occ_pct: Optional[float] = None
    predicted_dorm_occ_pct: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def _envelope(data):
    return {
        "success": True,
        "data": data,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── CRUD Endpoints ─────────────────────────────────────────────────────────────

@router.post("/targets", status_code=201)
def create_kpi_target(payload: KPITargetCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(KPITarget)
        .filter_by(branch_id=payload.branch_id, year=payload.year, month=payload.month)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="KPI target already exists for this branch/year/month")

    target = KPITarget(**payload.model_dump())
    db.add(target)
    db.commit()
    db.refresh(target)
    return _envelope(KPITargetOut.model_validate(target).model_dump())


@router.get("/targets")
def list_kpi_targets(
    branch_id: Optional[UUID] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(KPITarget)
    if branch_id:
        q = q.filter(KPITarget.branch_id == branch_id)
    if year:
        q = q.filter(KPITarget.year == year)
    targets = q.order_by(KPITarget.year, KPITarget.month).all()
    return _envelope([KPITargetOut.model_validate(t).model_dump() for t in targets])


@router.put("/targets/upsert")
def upsert_kpi_target(payload: KPITargetUpsert, db: Session = Depends(get_db)):
    """Create or update a KPI target for a branch/year/month."""
    existing = (
        db.query(KPITarget)
        .filter_by(branch_id=payload.branch_id, year=payload.year, month=payload.month)
        .first()
    )
    if existing:
        existing.target_revenue_native = payload.target_revenue_native
        existing.target_revenue_vnd = payload.target_revenue_native  # placeholder
        if payload.predicted_occ_pct is not None:
            existing.predicted_occ_pct = payload.predicted_occ_pct
        if payload.predicted_room_occ_pct is not None:
            existing.predicted_room_occ_pct = payload.predicted_room_occ_pct
        if payload.predicted_dorm_occ_pct is not None:
            existing.predicted_dorm_occ_pct = payload.predicted_dorm_occ_pct
        db.commit()
        db.refresh(existing)
        return _envelope(KPITargetOut.model_validate(existing).model_dump())
    else:
        target = KPITarget(
            branch_id=payload.branch_id,
            year=payload.year,
            month=payload.month,
            target_revenue_native=payload.target_revenue_native,
            target_revenue_vnd=payload.target_revenue_native,
            predicted_occ_pct=payload.predicted_occ_pct,
            predicted_room_occ_pct=payload.predicted_room_occ_pct,
            predicted_dorm_occ_pct=payload.predicted_dorm_occ_pct,
        )
        db.add(target)
        db.commit()
        db.refresh(target)
        return _envelope(KPITargetOut.model_validate(target).model_dump())


@router.patch("/targets/{target_id}")
def update_kpi_target(target_id: UUID, payload: KPITargetPatch, db: Session = Depends(get_db)):
    target = db.query(KPITarget).filter_by(id=target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="KPI target not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(target, field, value)

    db.commit()
    db.refresh(target)
    return _envelope(KPITargetOut.model_validate(target).model_dump())


# ── Summary Endpoints (Phase 2) ────────────────────────────────────────────────

def _branch_summary(db, branch, year, month):
    total_room_count = branch.total_room_count or 0
    total_dorm_count = branch.total_dorm_count or 0

    summary = compute_kpi_summary(
        db=db,
        branch_id=branch.id,
        year=year,
        month=month,
        total_rooms=branch.total_rooms or 0,
        total_room_count=total_room_count,
        total_dorm_count=total_dorm_count,
    )
    summary["branch_id"]   = str(branch.id)
    summary["branch_name"] = branch.name
    summary["branch_city"] = branch.city
    summary["currency"]    = branch.currency or branch.native_currency or "VND"
    summary["total_room_count"] = total_room_count
    summary["total_dorm_count"] = total_dorm_count

    # Always include next-month forecast
    next_data = compute_next_month_forecast(
        db=db,
        branch_id=branch.id,
        total_rooms=branch.total_rooms or 0,
        cur_year=year,
        cur_month=month,
        total_room_count=total_room_count,
        total_dorm_count=total_dorm_count,
    )
    summary.update(next_data)
    return summary


@router.get("/summary")
def kpi_summary_all(
    year: int = Query(...),
    month: int = Query(...),
    months: Optional[str] = Query(None, description="'current,next' for All Branches table"),
    branch_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
):
    """
    KPI achievement summary for all active branches (or a single branch if branch_id provided).
    ?months=current,next also returns next-month OCC-based forecast per branch.
    """
    now = datetime.now(timezone.utc)
    q = db.query(Branch).filter_by(is_active=True)
    if branch_id:
        q = q.filter(Branch.id == branch_id)
    branches = q.all()
    results = []

    for branch in branches:
        row = _branch_summary(db, branch, year, month)
        results.append(row)

    return _envelope(results)


@router.get("/summary/{branch_id}")
def kpi_summary_branch(
    branch_id: UUID,
    year: int = Query(...),
    month: int = Query(...),
    db: Session = Depends(get_db),
):
    """KPI achievement summary for a single branch."""
    branch = db.query(Branch).filter_by(id=branch_id, is_active=True).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    return _envelope(_branch_summary(db, branch, year, month))
