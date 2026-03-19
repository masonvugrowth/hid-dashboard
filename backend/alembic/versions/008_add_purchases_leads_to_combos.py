"""Add leads and purchases columns to ad_combos

Revision ID: 008
Revises: 007
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ad_combos", sa.Column("leads", sa.Integer(), nullable=True))
    op.add_column("ad_combos", sa.Column("purchases", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ad_combos", "purchases")
    op.drop_column("ad_combos", "leads")
