"""Add rate_plan_name column to reservations for CRM rate plan tracking.

Revision ID: 022
Revises: 021
"""
from alembic import op
import sqlalchemy as sa

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect
    conn = op.get_bind()
    columns = [c["name"] for c in inspect(conn).get_columns("reservations")]
    if "rate_plan_name" not in columns:
        op.add_column("reservations", sa.Column("rate_plan_name", sa.String(200), nullable=True))
    indexes = [i["name"] for i in inspect(conn).get_indexes("reservations")]
    if "idx_reservations_rate_plan_name" not in indexes:
        op.create_index("idx_reservations_rate_plan_name", "reservations", ["rate_plan_name"])


def downgrade():
    op.drop_index("idx_reservations_rate_plan_name", table_name="reservations")
    op.drop_column("reservations", "rate_plan_name")
