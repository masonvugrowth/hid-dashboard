import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class GovVisitorData(Base):
    __tablename__ = "gov_visitor_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    destination = Column(String(100), nullable=False)      # e.g. "Taiwan", "Japan", "Vietnam"
    source_country = Column(String(100), nullable=False)   # e.g. "Korea", "China"
    rank = Column(Integer, nullable=True)
    jan = Column(Integer, default=0)
    feb = Column(Integer, default=0)
    mar = Column(Integer, default=0)
    apr = Column(Integer, default=0)
    may = Column(Integer, default=0)
    jun = Column(Integer, default=0)
    jul = Column(Integer, default=0)
    aug = Column(Integer, default=0)
    sep = Column(Integer, default=0)
    oct = Column(Integer, default=0)
    nov = Column(Integer, default=0)
    dec = Column(Integer, default=0)
    total = Column(Integer, default=0)
    data_year = Column(Integer, nullable=True)             # year of the data
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
