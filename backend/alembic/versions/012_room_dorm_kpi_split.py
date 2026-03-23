"""Add room/dorm ADR, revenue columns to daily_metrics and predicted OCC split to kpi_targets.

Revision ID: 012
Revises: 011
"""

from alembic import op
import sqlalchemy as sa


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    # daily_metrics: room/dorm revenue and ADR
    op.add_column("daily_metrics", sa.Column("room_revenue_native", sa.Numeric(15, 2), nullable=True))
    op.add_column("daily_metrics", sa.Column("dorm_revenue_native", sa.Numeric(15, 2), nullable=True))
    op.add_column("daily_metrics", sa.Column("room_adr_native", sa.Numeric(12, 2), nullable=True))
    op.add_column("daily_metrics", sa.Column("dorm_adr_native", sa.Numeric(12, 2), nullable=True))

    # kpi_targets: separate room/dorm OCC predictions
    op.add_column("kpi_targets", sa.Column("predicted_room_occ_pct", sa.Numeric(5, 4), nullable=True))
    op.add_column("kpi_targets", sa.Column("predicted_dorm_occ_pct", sa.Numeric(5, 4), nullable=True))


def downgrade():
    op.drop_column("kpi_targets", "predicted_dorm_occ_pct")
    op.drop_column("kpi_targets", "predicted_room_occ_pct")
    op.drop_column("daily_metrics", "dorm_adr_native")
    op.drop_column("daily_metrics", "room_adr_native")
    op.drop_column("daily_metrics", "dorm_revenue_native")
    op.drop_column("daily_metrics", "room_revenue_native")
