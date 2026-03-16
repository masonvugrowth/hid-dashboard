"""Events CRUD router — Phase 2"""
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.event import Event

router = APIRouter()


def _envelope(data):
    return {"success": True, "data": data, "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat()}


class EventCreate(BaseModel):
    branch_id: Optional[UUID] = None
    city: str
    event_name: str
    event_date_from: date
    event_date_to: date
    estimated_attendance: Optional[int] = None
    is_key_event: bool = False
    notes: Optional[str] = None


class EventPatch(BaseModel):
    city: Optional[str] = None
    event_name: Optional[str] = None
    event_date_from: Optional[date] = None
    event_date_to: Optional[date] = None
    estimated_attendance: Optional[int] = None
    is_key_event: Optional[bool] = None
    notes: Optional[str] = None


class EventOut(BaseModel):
    id: UUID
    branch_id: Optional[UUID]
    city: str
    event_name: str
    event_date_from: date
    event_date_to: date
    estimated_attendance: Optional[int]
    is_key_event: bool
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("")
def list_events(
    branch_id: Optional[UUID] = Query(None),
    city: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Event)
    if branch_id:
        q = q.filter(Event.branch_id == branch_id)
    if city:
        q = q.filter(Event.city.ilike(f"%{city}%"))
    if date_from:
        q = q.filter(Event.event_date_to >= date_from)
    if date_to:
        q = q.filter(Event.event_date_from <= date_to)
    events = q.order_by(Event.event_date_from).all()
    return _envelope([EventOut.model_validate(e).model_dump() for e in events])


@router.post("", status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    event = Event(**payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return _envelope(EventOut.model_validate(event).model_dump())


@router.get("/{event_id}")
def get_event(event_id: UUID, db: Session = Depends(get_db)):
    event = db.query(Event).filter_by(id=event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return _envelope(EventOut.model_validate(event).model_dump())


@router.patch("/{event_id}")
def update_event(event_id: UUID, payload: EventPatch, db: Session = Depends(get_db)):
    event = db.query(Event).filter_by(id=event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    db.commit()
    db.refresh(event)
    return _envelope(EventOut.model_validate(event).model_dump())


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: UUID, db: Session = Depends(get_db)):
    event = db.query(Event).filter_by(id=event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(event)
    db.commit()
