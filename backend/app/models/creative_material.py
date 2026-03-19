import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Boolean, Integer, String, Date, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.database import Base


class CreativeMaterial(Base):
    __tablename__ = "creative_materials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_code = Column(String(20), unique=True, nullable=False)
    angle_id = Column(UUID(as_uuid=True), ForeignKey("creative_angles.id", ondelete="SET NULL"), nullable=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    material_type = Column(String(30), nullable=False)  # image / video / kol_video / gif / carousel_set / story_template
    design_type = Column(String(50), nullable=True)
    format_ratio = Column(String(50), nullable=True)  # can be multi e.g. "1:1, 4:5"
    channel = Column(String(50), nullable=True)
    target_audience = Column(String(100), nullable=False)
    language = Column(String(50), nullable=True)
    file_link = Column(Text, nullable=True)
    kol_name = Column(String(100), nullable=True)
    kol_nationality = Column(String(100), nullable=True)
    paid_ads_eligible = Column(Boolean, default=False, server_default="false")
    paid_ads_channel = Column(String(50), nullable=True)
    usage_rights_until = Column(Date, nullable=True)
    assigned_to = Column(String(100), nullable=True)
    order_status = Column(String(30), nullable=True)  # Briefing / In Progress / Done / Cancelled
    derived_verdict = Column(String(30), nullable=True)  # Computed nightly from combos
    combo_count = Column(Integer, default=0, server_default="0")
    tags = Column(ARRAY(Text), nullable=True)
    is_active = Column(Boolean, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    angle = relationship("CreativeAngle", back_populates="materials")
    combos = relationship("AdCombo", back_populates="material")
