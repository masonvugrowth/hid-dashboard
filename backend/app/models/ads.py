import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Date, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class AdsPerformance(Base):
    __tablename__ = "ads_performance"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    meta_ad_id = Column(String(50), nullable=True)           # Meta ad ID for upsert
    meta_campaign_id = Column(String(50), nullable=True)
    campaign_name = Column(String(200), nullable=True)
    adset_name = Column(String(200), nullable=True)
    ad_name = Column(String(200), nullable=True)
    channel = Column(String(50), nullable=True)              # Meta, Google, TikTok
    target_country = Column(String(100), nullable=True)
    target_audience = Column(String(100), nullable=True)     # Solo, Couple, Friend, Family, Business, High Intent
    funnel_stage = Column(String(20), nullable=True)         # TOF, MOF, BOF
    pic = Column(String(50), nullable=True)                  # PIC name from campaign
    ad_body = Column(Text, nullable=True)                    # Primary text from creative
    ad_angle_id = Column(UUID(as_uuid=True), ForeignKey("ad_angles.id", ondelete="SET NULL"), nullable=True)
    campaign_category = Column(String(100), nullable=True)
    date_from = Column(Date, nullable=True)
    date_to = Column(Date, nullable=True)
    cost_native = Column(Numeric(12, 2), nullable=True)
    cost_vnd = Column(Numeric(15, 2), nullable=True)
    impressions = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    leads = Column(Integer, nullable=True)
    bookings = Column(Integer, nullable=True)
    revenue_native = Column(Numeric(12, 2), nullable=True)
    revenue_vnd = Column(Numeric(15, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    branch = relationship("Branch", back_populates="ads_performance")
    angle = relationship("AdAngle", back_populates="ads_performance")
