import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Date, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class WebsiteMetrics(Base):
    __tablename__ = "website_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    week_start_date = Column(Date, nullable=False)
    platform = Column(String(50), nullable=False)  # Meta, Google, GA4, TikTok, Overall
    impressions = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    ctr = Column(Numeric(8, 6), nullable=True)
    website_traffic = Column(Integer, nullable=True)
    add_to_cart = Column(Integer, nullable=True)
    checkout_initiated = Column(Integer, nullable=True)
    conversions = Column(Integer, nullable=True)
    conversion_pct = Column(Numeric(8, 6), nullable=True)
    conversion_hit_pct = Column(Numeric(8, 6), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
