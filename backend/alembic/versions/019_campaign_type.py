"""Add campaign_type column to email_campaign_stats.

Differentiates 'workflow' (automated nurture flows) from 'bulk' (one-time blast campaigns).
Also updates the unique constraint to include campaign_type.

Revision ID: 019
Revises: 018
"""
from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    # Add campaign_type column with default 'workflow'
    op.add_column(
        "email_campaign_stats",
        sa.Column("campaign_type", sa.String(20), server_default="workflow", nullable=False),
    )
    op.create_index("idx_email_stats_campaign_type", "email_campaign_stats", ["campaign_type"])

    # Drop old unique constraint and create new one including campaign_type
    op.drop_constraint("uq_email_stats_workflow_date", "email_campaign_stats", type_="unique")
    op.create_unique_constraint(
        "uq_email_stats_workflow_date",
        "email_campaign_stats",
        ["workflow_id", "stat_date", "campaign_type"],
    )


def downgrade():
    op.drop_constraint("uq_email_stats_workflow_date", "email_campaign_stats", type_="unique")
    op.create_unique_constraint(
        "uq_email_stats_workflow_date",
        "email_campaign_stats",
        ["workflow_id", "stat_date"],
    )
    op.drop_index("idx_email_stats_campaign_type", "email_campaign_stats")
    op.drop_column("email_campaign_stats", "campaign_type")
