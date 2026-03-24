"""Add email_events and email_campaign_stats tables for GHL email marketing tracking.

Revision ID: 018
Revises: 017
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ghl_contact_id", sa.String(100), nullable=True),
        sa.Column("ghl_workflow_id", sa.String(100), nullable=True),
        sa.Column("workflow_name", sa.String(200), nullable=True),
        sa.Column("email_subject", sa.String(500), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contact_email", sa.String(200), nullable=True),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("link_url", sa.Text, nullable=True),
        sa.Column("bounce_reason", sa.Text, nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_email_events_workflow_type", "email_events", ["ghl_workflow_id", "event_type"])
    op.create_index("idx_email_events_timestamp", "email_events", ["event_timestamp"])
    op.create_index("idx_email_events_contact", "email_events", ["ghl_contact_id"])

    op.create_table(
        "email_campaign_stats",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workflow_id", sa.String(100), nullable=False),
        sa.Column("workflow_name", sa.String(200), nullable=True),
        sa.Column("stat_date", sa.Date, nullable=False),
        sa.Column("total_sent", sa.Integer, server_default="0"),
        sa.Column("total_delivered", sa.Integer, server_default="0"),
        sa.Column("total_opened", sa.Integer, server_default="0"),
        sa.Column("unique_opened", sa.Integer, server_default="0"),
        sa.Column("total_clicked", sa.Integer, server_default="0"),
        sa.Column("unique_clicked", sa.Integer, server_default="0"),
        sa.Column("total_bounced", sa.Integer, server_default="0"),
        sa.Column("total_unsubscribed", sa.Integer, server_default="0"),
        sa.Column("total_complained", sa.Integer, server_default="0"),
        sa.Column("open_rate", sa.Numeric(5, 4), server_default="0"),
        sa.Column("click_rate", sa.Numeric(5, 4), server_default="0"),
        sa.Column("bounce_rate", sa.Numeric(5, 4), server_default="0"),
        sa.Column("unsubscribe_rate", sa.Numeric(5, 4), server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workflow_id", "stat_date", name="uq_email_stats_workflow_date"),
    )
    op.create_index("idx_email_stats_workflow_date", "email_campaign_stats", ["workflow_id", "stat_date"])
    op.create_index("idx_email_stats_date", "email_campaign_stats", ["stat_date"])


def downgrade():
    op.drop_table("email_campaign_stats")
    op.drop_table("email_events")
