import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Boolean, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.database import Base


class CreativeCopy(Base):
    __tablename__ = "creative_copies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    copy_code = Column(String(20), unique=True, nullable=False)
    angle_id = Column(UUID(as_uuid=True), ForeignKey("creative_angles.id", ondelete="SET NULL"), nullable=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    channel = Column(String(50), nullable=False)
    ad_format = Column(String(50), nullable=True)
    target_audience = Column(ARRAY(Text), nullable=False, server_default="{}")
    country_target = Column(String(100), nullable=True)
    language = Column(String(50), nullable=False)
    headline = Column(String(500), nullable=True)
    primary_text = Column(Text, nullable=False)
    landing_page_url = Column(Text, nullable=True)
    copywriter_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    derived_verdict = Column(String(30), nullable=True)  # Computed nightly from combos
    combo_count = Column(Integer, default=0, server_default="0")
    tags = Column(ARRAY(Text), nullable=True)
    is_active = Column(Boolean, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    angle = relationship("CreativeAngle", back_populates="copies")
    combos = relationship("AdCombo", back_populates="copy")
