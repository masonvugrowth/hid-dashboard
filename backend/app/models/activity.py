import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Date, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class MarketingActivity(Base):
    __tablename__ = "marketing_activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    target_country = Column(String(100), nullable=True)
    activity_type = Column(String(50), nullable=True)  # PaidAds, KOL, CRM, Event, Organic
    target_audience = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    result_notes = Column(Text, nullable=True)
    date_from = Column(Date, nullable=True)
    date_to = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    branch = relationship("Branch", back_populates="marketing_activities")
