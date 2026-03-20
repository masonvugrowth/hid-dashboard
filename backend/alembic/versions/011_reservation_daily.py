"""Add reservation_daily table for v2.0 nightly rate attribution.

Revision ID: 011
Revises: 010
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reservation_daily",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("reservation_id", UUID(as_uuid=True), sa.ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("room_id", sa.String(50), nullable=True),
        sa.Column("nightly_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("nightly_rate_vnd", sa.Numeric(15, 2), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("source_category", sa.String(20), nullable=True),
        sa.Column("room_type_category", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("reservation_id", "date", name="uq_reservation_daily_res_date"),
    )
    op.create_index("idx_reservation_daily_branch_date", "reservation_daily", ["branch_id", "date"])
    op.create_index("idx_reservation_daily_reservation", "reservation_daily", ["reservation_id"])


def downgrade() -> None:
    op.drop_index("idx_reservation_daily_reservation", table_name="reservation_daily")
    op.drop_index("idx_reservation_daily_branch_date", table_name="reservation_daily")
    op.drop_table("reservation_daily")
