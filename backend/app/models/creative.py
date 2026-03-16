import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Boolean, String, Date, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class BranchKeypoint(Base):
    __tablename__ = "branch_keypoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    keypoint = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)  # Location, Amenity, Social, Price, Experience
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    branch = relationship("Branch", back_populates="keypoints")


class AdCopy(Base):
    __tablename__ = "ad_copies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    copy_id = Column(String(20), unique=True, nullable=False)  # CPY-001
    angle_id = Column(UUID(as_uuid=True), ForeignKey("ad_angles.id", ondelete="SET NULL"), nullable=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    channel = Column(String(50), nullable=True)
    ad_format = Column(String(50), nullable=True)
    target_audience = Column(String(100), nullable=True)
    target_country = Column(String(100), nullable=True)
    language = Column(String(100), nullable=True)
    headline = Column(String(500), nullable=True)
    primary_text = Column(Text, nullable=True)
    copywriter = Column(String(100), nullable=True)
    status = Column(String(20), default="Draft")  # Draft, Review, Approved
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    angle = relationship("AdAngle", back_populates="ad_copies")
    approvals = relationship("AdApproval", back_populates="copy")
    ad_names = relationship("AdName", back_populates="copy")


class AdMaterial(Base):
    __tablename__ = "ad_materials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id = Column(String(20), unique=True, nullable=False)  # MAT-001
    angle_id = Column(UUID(as_uuid=True), ForeignKey("ad_angles.id", ondelete="SET NULL"), nullable=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    material_type = Column(String(50), nullable=True)
    format_ratio = Column(String(20), nullable=True)
    design_type = Column(String(50), nullable=True)
    assigned_to = Column(String(100), nullable=True)
    brief_link = Column(Text, nullable=True)
    order_status = Column(String(50), default="Briefing")
    deadline = Column(Date, nullable=True)
    file_link = Column(Text, nullable=True)
    channel = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    angle = relationship("AdAngle", back_populates="ad_materials")
    approvals = relationship("AdApproval", back_populates="material")
    ad_names = relationship("AdName", back_populates="material")


class AdApproval(Base):
    __tablename__ = "ad_approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    copy_id = Column(UUID(as_uuid=True), ForeignKey("ad_copies.id", ondelete="CASCADE"), nullable=False)
    material_id = Column(UUID(as_uuid=True), ForeignKey("ad_materials.id", ondelete="SET NULL"), nullable=True)
    kol_id = Column(UUID(as_uuid=True), ForeignKey("kol_records.id", ondelete="SET NULL"), nullable=True)
    submitted_by = Column(String(100), nullable=True)
    submitted_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    landing_page_url = Column(Text, nullable=True)
    reviewer = Column(String(100), nullable=True)
    approval_status = Column(String(30), default="Pending")  # Pending, Approved, Rejected, Needs Revision
    approval_deadline = Column(DateTime(timezone=True), nullable=True)
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    copy = relationship("AdCopy", back_populates="approvals")
    material = relationship("AdMaterial", back_populates="approvals")
    kol = relationship("KOLRecord", back_populates="ad_approvals")
    ad_names = relationship("AdName", back_populates="approval")


class AdName(Base):
    __tablename__ = "ad_names"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_id = Column(UUID(as_uuid=True), ForeignKey("ad_approvals.id", ondelete="CASCADE"), nullable=False)
    copy_id = Column(UUID(as_uuid=True), ForeignKey("ad_copies.id"), nullable=False)
    material_id = Column(UUID(as_uuid=True), ForeignKey("ad_materials.id"), nullable=True)
    generated_name = Column(String(500), nullable=False)
    channel = Column(String(50), nullable=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    approval = relationship("AdApproval", back_populates="ad_names")
    copy = relationship("AdCopy", back_populates="ad_names")
    material = relationship("AdMaterial", back_populates="ad_names")
