"""Rate plan → campaign label typed by the marketing team.

Cloudbeds rate plan names ("WELCOME BACK", "CRM_August 2026 Events") do not
say which campaign they belong to, so anyone outside the team reading the
Marketing Activity → CRM Reservations table cannot tell what a row was for.
This table stores that mapping, hand-entered in the UI.

Keyed by the rate plan LABEL exactly as the table shows it (the output of
`crm_rate_plan_label_expr`), and global across branches — the same rate plan
tag means the same campaign everywhere. Nothing computes or overwrites
campaign_name; it is only ever what a human typed.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class RatePlanCampaign(Base):
    __tablename__ = "rate_plan_campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Matched verbatim against the grouped label, not as a substring.
    rate_plan_name = Column(String(300), nullable=False, unique=True)
    campaign_name = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
