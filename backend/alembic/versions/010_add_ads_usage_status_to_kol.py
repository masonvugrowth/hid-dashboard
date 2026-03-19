"""Add ads_usage_status to kol_records

Revision ID: 010
Revises: 009
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kol_records", sa.Column("ads_usage_status", sa.String(30), nullable=True))
    op.create_index("idx_kol_ads_usage_status", "kol_records", ["ads_usage_status"])


def downgrade() -> None:
    op.drop_index("idx_kol_ads_usage_status")
    op.drop_column("kol_records", "ads_usage_status")
