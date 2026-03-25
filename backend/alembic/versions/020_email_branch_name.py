"""Add branch_name to email_campaign_stats for multi-location GHL support.

Revision ID: 020
Revises: 019
"""
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "email_campaign_stats",
        sa.Column("branch_name", sa.String(50), server_default="Saigon", nullable=False),
    )
    op.create_index("idx_email_stats_branch", "email_campaign_stats", ["branch_name"])

    # Update unique constraint to include branch_name
    op.drop_constraint("uq_email_stats_workflow_date", "email_campaign_stats", type_="unique")
    op.create_unique_constraint(
        "uq_email_stats_workflow_date",
        "email_campaign_stats",
        ["workflow_id", "stat_date", "campaign_type", "branch_name"],
    )


def downgrade():
    op.drop_constraint("uq_email_stats_workflow_date", "email_campaign_stats", type_="unique")
    op.create_unique_constraint(
        "uq_email_stats_workflow_date",
        "email_campaign_stats",
        ["workflow_id", "stat_date", "campaign_type"],
    )
    op.drop_index("idx_email_stats_branch", "email_campaign_stats")
    op.drop_column("email_campaign_stats", "branch_name")
