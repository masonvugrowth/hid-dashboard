import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Date, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    city = Column(String(100), nullable=False)
    event_name = Column(String(200), nullable=False)
    event_date_from = Column(Date, nullable=False)
    event_date_to = Column(Date, nullable=False)
    estimated_attendance = Column(Integer, nullable=True)
    is_key_event = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
