import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Boolean, Integer, Numeric, String, Date, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class AdCombo(Base):
    __tablename__ = "ad_combos"
    __table_args__ = (
        UniqueConstraint("copy_id", "material_id", name="uq_combo_copy_material"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    combo_code = Column(String(20), unique=True, nullable=False)
    copy_id = Column(UUID(as_uuid=True), ForeignKey("creative_copies.id", ondelete="CASCADE"), nullable=False)
    material_id = Column(UUID(as_uuid=True), ForeignKey("creative_materials.id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    target_audience = Column(String(100), nullable=False)
    channel = Column(String(50), nullable=False)
    language = Column(String(50), nullable=True)
    country_target = Column(String(100), nullable=True)
    angle_id = Column(UUID(as_uuid=True), ForeignKey("creative_angles.id", ondelete="SET NULL"), nullable=True)
    meta_ad_name = Column(String(500), unique=True, nullable=True)
    verdict = Column(String(30), nullable=True)  # winning / good / neutral / underperformer / kill
    verdict_source = Column(String(20), nullable=True)  # manual / auto_meta
    verdict_notes = Column(Text, nullable=True)
    spend_vnd = Column(Numeric(18, 2), nullable=True)
    revenue_vnd = Column(Numeric(18, 2), nullable=True)
    roas = Column(Numeric(8, 4), nullable=True)
    impressions = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    leads = Column(Integer, nullable=True)
    purchases = Column(Integer, nullable=True)
    date_first_run = Column(Date, nullable=True)
    date_last_run = Column(Date, nullable=True)
    run_status = Column(String(20), nullable=True)  # Active / Paused / Ended
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    added_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    copy = relationship("CreativeCopy", back_populates="combos")
    material = relationship("CreativeMaterial", back_populates="combos")
    angle = relationship("CreativeAngle", back_populates="combos")
