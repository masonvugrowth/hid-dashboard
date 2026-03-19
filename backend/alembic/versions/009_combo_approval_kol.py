"""Add approval workflow + KOL link to ad_combos

Revision ID: 009
Revises: 008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ad_combos", sa.Column("kol_id", UUID(as_uuid=True), sa.ForeignKey("kol_records.id", ondelete="SET NULL"), nullable=True))
    op.add_column("ad_combos", sa.Column("approval_status", sa.String(30), nullable=True))
    op.add_column("ad_combos", sa.Column("submitted_by", sa.String(100), nullable=True))
    op.add_column("ad_combos", sa.Column("reviewer_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("ad_combos", sa.Column("approval_deadline", sa.Date(), nullable=True))
    op.add_column("ad_combos", sa.Column("approval_feedback", sa.Text(), nullable=True))
    op.add_column("ad_combos", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_combos_approval_status", "ad_combos", ["approval_status"])
    op.create_index("idx_combos_reviewer", "ad_combos", ["reviewer_id"])


def downgrade() -> None:
    op.drop_index("idx_combos_reviewer")
    op.drop_index("idx_combos_approval_status")
    op.drop_column("ad_combos", "approved_at")
    op.drop_column("ad_combos", "approval_feedback")
    op.drop_column("ad_combos", "approval_deadline")
    op.drop_column("ad_combos", "reviewer_id")
    op.drop_column("ad_combos", "submitted_by")
    op.drop_column("ad_combos", "approval_status")
    op.drop_column("ad_combos", "kol_id")
