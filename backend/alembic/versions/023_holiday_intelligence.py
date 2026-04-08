"""Create holiday_calendars and travel_season_index tables for Holiday Intelligence.

Revision ID: 023
Revises: 022
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect
    conn = op.get_bind()
    tables = inspect(conn).get_table_names()

    if "holiday_calendars" not in tables:
        op.create_table(
            "holiday_calendars",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("country_code", sa.String(2), nullable=False),
            sa.Column("country_name", sa.String(100), nullable=False),
            sa.Column("holiday_name", sa.String(200), nullable=False),
            sa.Column("holiday_type", sa.String(50), nullable=False),
            sa.Column("month_start", sa.Integer, nullable=False),
            sa.Column("day_start", sa.Integer, nullable=True),
            sa.Column("month_end", sa.Integer, nullable=False),
            sa.Column("day_end", sa.Integer, nullable=True),
            sa.Column("duration_days", sa.Integer, nullable=False),
            sa.Column("is_long_holiday", sa.Boolean, server_default="false"),
            sa.Column("travel_propensity", sa.String(10), nullable=False),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("data_source", sa.String(50), server_default="static"),
            sa.Column("year", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("idx_holiday_cal_country_month", "holiday_calendars", ["country_code", "month_start"])
        op.create_index("idx_holiday_cal_month_propensity", "holiday_calendars", ["month_start", "travel_propensity"])

    if "travel_season_index" not in tables:
        op.create_table(
            "travel_season_index",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("country_code", sa.String(2), nullable=False),
            sa.Column("month", sa.Integer, nullable=False),
            sa.Column("season_score", sa.Numeric(4, 2), nullable=False),
            sa.Column("holiday_count", sa.Integer, server_default="0"),
            sa.Column("long_holiday_days", sa.Integer, server_default="0"),
            sa.Column("peak_label", sa.String(20), nullable=True),
            sa.Column("holiday_names", ARRAY(sa.Text), nullable=True),
            sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("country_code", "month", name="uq_season_country_month"),
        )

    # Seed holiday data
    from app.data.holiday_seed import HOLIDAY_SEED
    hc = sa.table(
        "holiday_calendars",
        sa.column("country_code", sa.String),
        sa.column("country_name", sa.String),
        sa.column("holiday_name", sa.String),
        sa.column("holiday_type", sa.String),
        sa.column("month_start", sa.Integer),
        sa.column("day_start", sa.Integer),
        sa.column("month_end", sa.Integer),
        sa.column("day_end", sa.Integer),
        sa.column("duration_days", sa.Integer),
        sa.column("is_long_holiday", sa.Boolean),
        sa.column("travel_propensity", sa.String),
        sa.column("notes", sa.Text),
        sa.column("data_source", sa.String),
    )
    op.bulk_insert(hc, HOLIDAY_SEED)

    # Recompute season index immediately after seed
    from sqlalchemy.orm import Session
    from app.services.holiday_intel import recompute_season_index
    db = Session(bind=op.get_bind())
    try:
        recompute_season_index(db)
    finally:
        db.close()


def downgrade():
    op.drop_table("travel_season_index")
    op.drop_table("holiday_calendars")
