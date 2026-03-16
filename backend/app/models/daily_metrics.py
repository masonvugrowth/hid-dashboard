import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Numeric, Date, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class DailyMetrics(Base):
    __tablename__ = "daily_metrics"
    __table_args__ = (
        UniqueConstraint("branch_id", "date", name="uq_daily_metrics_branch_date"),
        Index("idx_daily_metrics_branch_date", "branch_id", "date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    rooms_sold = Column(Integer, default=0)
    dorms_sold = Column(Integer, default=0)
    total_sold = Column(Integer, default=0)
    occ_pct = Column(Numeric(5, 4), default=0)
    room_occ_pct = Column(Numeric(5, 4), nullable=True)
    dorm_occ_pct = Column(Numeric(5, 4), nullable=True)
    revenue_native = Column(Numeric(15, 2), default=0)
    revenue_vnd = Column(Numeric(18, 2), default=0)
    adr_native = Column(Numeric(12, 2), default=0)
    revpar_native = Column(Numeric(12, 2), default=0)
    new_bookings = Column(Integer, default=0)
    cancellations = Column(Integer, default=0)
    cancellation_pct = Column(Numeric(5, 4), default=0)
    computed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    branch = relationship("Branch", back_populates="daily_metrics")
