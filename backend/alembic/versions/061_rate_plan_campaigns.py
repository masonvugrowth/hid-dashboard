"""rate_plan_campaigns table

Revision ID: 061
Revises: 060
Create Date: 2026-08-27

Hand-typed campaign label for each CRM rate plan name, shown next to the
rate plan in Marketing Activity → CRM Reservations so people outside the
marketing team can tell what a row was for. One row per rate plan label,
global across branches. See app/models/rate_plan_campaign.py.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "061"
down_revision = "060"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rate_plan_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rate_plan_name", sa.String(300), nullable=False),
        sa.Column("campaign_name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("rate_plan_name", name="uq_rate_plan_campaign_name"),
    )


def downgrade():
    op.drop_table("rate_plan_campaigns")
