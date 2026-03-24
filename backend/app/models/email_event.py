import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class EmailEvent(Base):
    __tablename__ = "email_events"
    __table_args__ = (
        Index("idx_email_events_workflow_type", "ghl_workflow_id", "event_type"),
        Index("idx_email_events_timestamp", "event_timestamp"),
        Index("idx_email_events_contact", "ghl_contact_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ghl_contact_id = Column(String(100), nullable=True)
    ghl_workflow_id = Column(String(100), nullable=True)
    workflow_name = Column(String(200), nullable=True)
    email_subject = Column(String(500), nullable=True)
    event_type = Column(String(50), nullable=False)  # sent/opened/clicked/bounced/unsubscribed/delivered/complained
    event_timestamp = Column(DateTime(timezone=True), nullable=True)
    contact_email = Column(String(200), nullable=True)
    contact_name = Column(String(200), nullable=True)
    link_url = Column(Text, nullable=True)
    bounce_reason = Column(Text, nullable=True)
    raw_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
