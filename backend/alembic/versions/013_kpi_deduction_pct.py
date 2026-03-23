"""Add deduction_pct column to kpi_targets for forecast adjustment.

Revision ID: 013
Revises: 012
"""

from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "kpi_targets",
        sa.Column("deduction_pct", sa.Numeric(5, 2), nullable=True, server_default="0"),
    )


def downgrade():
    op.drop_column("kpi_targets", "deduction_pct")
