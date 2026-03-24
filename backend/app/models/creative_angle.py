import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Boolean, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.database import Base


class CreativeAngle(Base):
    __tablename__ = "creative_angles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    angle_code = Column(String(20), unique=True, nullable=False)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(200), nullable=False)
    hook_type = Column(String(50), nullable=False)
    keypoint_1 = Column(String(200), nullable=False)
    keypoint_2 = Column(String(200), nullable=True)
    keypoint_3 = Column(String(200), nullable=True)
    keypoint_4 = Column(String(200), nullable=True)
    keypoint_5 = Column(String(200), nullable=True)
    target_audience = Column(ARRAY(Text), nullable=True)
    notes = Column(Text, nullable=True)
    added_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    copies = relationship("CreativeCopy", back_populates="angle")
    materials = relationship("CreativeMaterial", back_populates="angle")
    combos = relationship("AdCombo", back_populates="angle")
