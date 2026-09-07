"""seasonal_campaigns table

Revision ID: 063
Revises: 062
Create Date: 2026-09-07

One row per seasonal marketing push, holding the two keys the team types at
set-up: the ad campaign name(s) that carry its spend, and the rate plan
name(s) that carry its real bookings. Marketing Activity -> Seasonal Campaign
joins the two at read time. See app/models/seasonal_campaign.py.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "063"
down_revision = "062"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "seasonal_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("ads_campaign_names", sa.JSON(), nullable=False,
                  server_default="[]"),
        sa.Column("rate_plan_names", sa.JSON(), nullable=False,
                  server_default="[]"),
        sa.Column("cost_pct", sa.Numeric(6, 2), nullable=False,
                  server_default="0"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_seasonal_campaign_name"),
    )


def downgrade():
    op.drop_table("seasonal_campaigns")
