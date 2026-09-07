"""Seasonal campaign — one marketing push, tracked from both sides at once.

A seasonal campaign ("Tet 2027", "Summer Escape") sells through a rate plan
AND buys traffic through ad campaigns, so neither source alone tells the team
whether it worked:

  - the Ads Platform knows what was spent and what it can attribute back to a
    click, but only sees the bookings its matcher recognised;
  - Cloudbeds knows every booking that actually came in on the rate plan —
    walk-ups, phone bookings, and OTA guests who saw the ad and booked days
    later — but knows nothing about the ad spend.

So one row here holds both keys the team types at set-up: the ad campaign
name(s) to sum spend and ad-attributed bookings from, and the rate plan
name(s) that count the real bookings. Everything on the Seasonal Campaign tab
is computed from those two lists at read time; nothing is stored aggregated.

``cost_pct`` is the campaign's own cost as a percentage of the revenue it
brought in (room discount, amenity, gift) — hand-typed, never derived. The tab
charges it against ACTUAL revenue, not ad-attributed revenue, and adds the ad
spend on top to get the true ROAS.

Both name lists match as case-insensitive substrings, the same rule the Rate
Plan Quota engine counts by, because Cloudbeds and Meta each decorate the name
the team typed ("MEANDER Saigon | TET2027 | Couple VN").
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, JSON, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class SeasonalCampaign(Base):
    __tablename__ = "seasonal_campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # What the team calls it. Unique so two people can't track one push twice.
    name = Column(String(200), nullable=False, unique=True)
    # ["TET2027", ...] - matched ILIKE %pattern% on ads_performance.campaign_name.
    ads_campaign_names = Column(JSON, nullable=False, default=list)
    # ["TET 2027 Package", ...] - matched against reservations.rate_plan_name
    # AND reservations.room_type (Cloudbeds packs the tag into either one).
    rate_plan_names = Column(JSON, nullable=False, default=list)
    # Campaign cost as a % of ACTUAL revenue. 0 means "no campaign cost",
    # which leaves the real ROAS equal to actual revenue / ad spend.
    cost_pct = Column(Numeric(6, 2), nullable=False, default=0)
    notes = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
