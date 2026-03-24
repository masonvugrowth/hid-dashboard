"""Ad Analysis Results — AI-powered ad analysis with funnel diagnostics."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class AdAnalysisResult(Base):
    __tablename__ = "ad_analysis_results"
    __table_args__ = (
        UniqueConstraint("combo_id", name="uq_analysis_combo"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    combo_id = Column(UUID(as_uuid=True), ForeignKey("ad_combos.id", ondelete="CASCADE"), nullable=False)

    # AI-detected fields
    detected_angles = Column(ARRAY(Text), nullable=True)       # e.g. ["Location", "Experience"]
    detected_ta = Column(ARRAY(Text), nullable=True)            # e.g. ["Solo", "Couple"]
    keypoints = Column(ARRAY(Text), nullable=True)              # 3-5 keypoints extracted
    visual_summary = Column(Text, nullable=True)                # AI description of visual

    # Funnel analysis
    funnel_analysis = Column(JSONB, nullable=True)              # Full funnel breakdown + bottleneck

    # Recommendation
    ai_recommendation = Column(Text, nullable=True)             # Human-readable recommendation
    recommendation_type = Column(String(30), nullable=True)     # scale_up / optimize / pause / test_new / insufficient_data
    confidence_score = Column(Numeric(3, 2), nullable=True)     # 0.00 - 1.00

    # Meta
    model_used = Column(String(50), nullable=True)
    analyzed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    combo = relationship("AdCombo", backref="analysis")
