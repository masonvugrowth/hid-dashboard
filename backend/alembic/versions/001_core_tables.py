"""001 core tables

Revision ID: 001
Revises:
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. branches
    op.create_table(
        "branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("total_rooms", sa.Integer(), nullable=False),
        sa.Column("total_room_count", sa.Integer(), nullable=True),
        sa.Column("total_dorm_count", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=False),
        sa.Column("cloudbeds_property_id", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 2. users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(200), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("role", sa.String(20), server_default="editor"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 3. kpi_targets
    op.create_table(
        "kpi_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("target_revenue_native", sa.Numeric(15, 2), nullable=False),
        sa.Column("target_revenue_vnd", sa.Numeric(18, 2), nullable=False),
        sa.Column("predicted_occ_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("branch_id", "year", "month", name="uq_kpi_branch_year_month"),
    )

    # 4. reservations
    op.create_table(
        "reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cloudbeds_reservation_id", sa.String(50), unique=True, nullable=False),
        sa.Column("guest_country", sa.String(100), nullable=True),
        sa.Column("guest_country_code", sa.String(50), nullable=True),
        sa.Column("room_type", sa.String(100), nullable=True),
        sa.Column("room_type_category", sa.String(10), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("source_category", sa.String(20), nullable=True),
        sa.Column("check_in_date", sa.Date(), nullable=False),
        sa.Column("check_out_date", sa.Date(), nullable=False),
        sa.Column("nights", sa.Integer(), nullable=False),
        sa.Column("adults", sa.Integer(), nullable=True),
        sa.Column("grand_total_native", sa.Numeric(12, 2), nullable=True),
        sa.Column("grand_total_vnd", sa.Numeric(15, 2), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("cancellation_date", sa.Date(), nullable=True),
        sa.Column("reservation_date", sa.Date(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_reservations_branch_checkin", "reservations", ["branch_id", "check_in_date"])
    op.create_index("idx_reservations_status", "reservations", ["status"])
    op.create_index("idx_reservations_source_category", "reservations", ["source_category"])
    op.create_index("idx_reservations_country_code", "reservations", ["guest_country_code"])

    # 5. daily_metrics
    op.create_table(
        "daily_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("rooms_sold", sa.Integer(), server_default="0"),
        sa.Column("dorms_sold", sa.Integer(), server_default="0"),
        sa.Column("total_sold", sa.Integer(), server_default="0"),
        sa.Column("occ_pct", sa.Numeric(5, 4), server_default="0"),
        sa.Column("room_occ_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("dorm_occ_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("revenue_native", sa.Numeric(15, 2), server_default="0"),
        sa.Column("revenue_vnd", sa.Numeric(18, 2), server_default="0"),
        sa.Column("adr_native", sa.Numeric(12, 2), server_default="0"),
        sa.Column("revpar_native", sa.Numeric(12, 2), server_default="0"),
        sa.Column("new_bookings", sa.Integer(), server_default="0"),
        sa.Column("cancellations", sa.Integer(), server_default="0"),
        sa.Column("cancellation_pct", sa.Numeric(5, 4), server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("branch_id", "date", name="uq_daily_metrics_branch_date"),
    )
    op.create_index("idx_daily_metrics_branch_date", "daily_metrics", ["branch_id", "date"])

    # 6. events
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("event_name", sa.String(200), nullable=False),
        sa.Column("event_date_from", sa.Date(), nullable=False),
        sa.Column("event_date_to", sa.Date(), nullable=False),
        sa.Column("estimated_attendance", sa.Integer(), nullable=True),
        sa.Column("is_key_event", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 7. website_metrics
    op.create_table(
        "website_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("week_start_date", sa.Date(), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("ctr", sa.Numeric(8, 6), nullable=True),
        sa.Column("website_traffic", sa.Integer(), nullable=True),
        sa.Column("add_to_cart", sa.Integer(), nullable=True),
        sa.Column("checkout_initiated", sa.Integer(), nullable=True),
        sa.Column("conversions", sa.Integer(), nullable=True),
        sa.Column("conversion_pct", sa.Numeric(8, 6), nullable=True),
        sa.Column("conversion_hit_pct", sa.Numeric(8, 6), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 8. ad_angles
    op.create_table(
        "ad_angles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 9. ads_performance
    op.create_table(
        "ads_performance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_name", sa.String(200), nullable=True),
        sa.Column("adset_name", sa.String(200), nullable=True),
        sa.Column("ad_name", sa.String(200), nullable=True),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("target_country", sa.String(100), nullable=True),
        sa.Column("target_audience", sa.String(100), nullable=True),
        sa.Column("ad_angle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ad_angles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("campaign_category", sa.String(100), nullable=True),
        sa.Column("funnel_stage", sa.String(20), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("cost_native", sa.Numeric(12, 2), nullable=True),
        sa.Column("cost_vnd", sa.Numeric(15, 2), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("leads", sa.Integer(), nullable=True),
        sa.Column("bookings", sa.Integer(), nullable=True),
        sa.Column("revenue_native", sa.Numeric(12, 2), nullable=True),
        sa.Column("revenue_vnd", sa.Numeric(15, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 10. kol_records
    op.create_table(
        "kol_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kol_name", sa.String(100), nullable=False),
        sa.Column("kol_nationality", sa.String(100), nullable=True),
        sa.Column("language", sa.String(100), nullable=True),
        sa.Column("target_audience", sa.String(100), nullable=True),
        sa.Column("ad_angle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ad_angles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cost_native", sa.Numeric(12, 2), nullable=True),
        sa.Column("cost_vnd", sa.Numeric(15, 2), nullable=True),
        sa.Column("is_gifted_stay", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("invitation_date", sa.Date(), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.Column("link_ig", sa.Text(), nullable=True),
        sa.Column("link_tiktok", sa.Text(), nullable=True),
        sa.Column("link_youtube", sa.Text(), nullable=True),
        sa.Column("deliverable_status", sa.String(50), nullable=True),
        sa.Column("paid_ads_eligible", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("paid_ads_usage_fee_vnd", sa.Numeric(15, 2), nullable=True),
        sa.Column("paid_ads_channel", sa.String(100), nullable=True),
        sa.Column("usage_rights_expiry_date", sa.Date(), nullable=True),
        sa.Column("contract_status", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 11. kol_bookings
    op.create_table(
        "kol_bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("kol_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kol_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attributed_revenue_vnd", sa.Numeric(15, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 12. marketing_activities
    op.create_table(
        "marketing_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_country", sa.String(100), nullable=True),
        sa.Column("activity_type", sa.String(50), nullable=True),
        sa.Column("target_audience", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("result_notes", sa.Text(), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("marketing_activities")
    op.drop_table("kol_bookings")
    op.drop_table("kol_records")
    op.drop_table("ads_performance")
    op.drop_table("ad_angles")
    op.drop_table("website_metrics")
    op.drop_table("events")
    op.drop_index("idx_daily_metrics_branch_date", table_name="daily_metrics")
    op.drop_table("daily_metrics")
    op.drop_index("idx_reservations_country_code", table_name="reservations")
    op.drop_index("idx_reservations_source_category", table_name="reservations")
    op.drop_index("idx_reservations_status", table_name="reservations")
    op.drop_index("idx_reservations_branch_checkin", table_name="reservations")
    op.drop_table("reservations")
    op.drop_table("kpi_targets")
    op.drop_table("users")
    op.drop_table("branches")
