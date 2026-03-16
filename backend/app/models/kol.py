import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Boolean, String, Date, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class KOLRecord(Base):
    __tablename__ = "kol_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    kol_name = Column(String(100), nullable=False)
    kol_nationality = Column(String(100), nullable=True)
    language = Column(String(100), nullable=True)
    target_audience = Column(String(100), nullable=True)
    ad_angle_id = Column(UUID(as_uuid=True), ForeignKey("ad_angles.id", ondelete="SET NULL"), nullable=True)
    cost_native = Column(Numeric(12, 2), nullable=True)
    cost_vnd = Column(Numeric(15, 2), nullable=True)
    is_gifted_stay = Column(Boolean, default=False)
    invitation_date = Column(Date, nullable=True)
    published_date = Column(Date, nullable=True)
    link_ig = Column(Text, nullable=True)
    link_tiktok = Column(Text, nullable=True)
    link_youtube = Column(Text, nullable=True)
    deliverable_status = Column(String(50), nullable=True)  # Not Started, In Progress, Editing, Done
    paid_ads_eligible = Column(Boolean, default=False)
    paid_ads_usage_fee_vnd = Column(Numeric(15, 2), nullable=True)
    paid_ads_channel = Column(String(100), nullable=True)
    usage_rights_expiry_date = Column(Date, nullable=True)
    contract_status = Column(String(50), nullable=True)     # Draft, Negotiating, Signed, Cancelled
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    branch = relationship("Branch", back_populates="kol_records")
    angle = relationship("AdAngle", back_populates="kol_records")
    kol_bookings = relationship("KOLBooking", back_populates="kol")
    ad_approvals = relationship("AdApproval", back_populates="kol")


class KOLBooking(Base):
    __tablename__ = "kol_bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kol_id = Column(UUID(as_uuid=True), ForeignKey("kol_records.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(UUID(as_uuid=True), ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    attributed_revenue_vnd = Column(Numeric(15, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    kol = relationship("KOLRecord", back_populates="kol_bookings")
    reservation = relationship("Reservation", back_populates="kol_bookings")
