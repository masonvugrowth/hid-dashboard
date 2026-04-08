import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Boolean, Integer, Numeric, String, Text, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.database import Base


class HolidayCalendar(Base):
    __tablename__ = "holiday_calendars"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_code = Column(String(2), nullable=False, index=True)
    country_name = Column(String(100), nullable=False)
    holiday_name = Column(String(200), nullable=False)
    holiday_type = Column(String(50), nullable=False)       # national | school_break | cultural | religious
    month_start = Column(Integer, nullable=False)
    day_start = Column(Integer, nullable=True)
    month_end = Column(Integer, nullable=False)
    day_end = Column(Integer, nullable=True)
    duration_days = Column(Integer, nullable=False)
    is_long_holiday = Column(Boolean, default=False)
    travel_propensity = Column(String(10), nullable=False)   # HIGH | MEDIUM | LOW
    notes = Column(Text, nullable=True)
    data_source = Column(String(50), default="static")       # static | api | manual
    year = Column(Integer, nullable=True)                    # NULL = every year
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class TravelSeasonIndex(Base):
    __tablename__ = "travel_season_index"
    __table_args__ = (
        UniqueConstraint("country_code", "month", name="uq_season_country_month"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_code = Column(String(2), nullable=False, index=True)
    month = Column(Integer, nullable=False)
    season_score = Column(Numeric(4, 2), nullable=False)
    holiday_count = Column(Integer, default=0)
    long_holiday_days = Column(Integer, default=0)
    peak_label = Column(String(20), nullable=True)           # PEAK | SHOULDER | OFF
    holiday_names = Column(ARRAY(Text), nullable=True)
    computed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
