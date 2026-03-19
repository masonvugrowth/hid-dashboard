"""Phase 4: Creative Intelligence Library — 4 new tables

Revision ID: 007
Revises: 006
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. creative_angles
    op.create_table(
        "creative_angles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("angle_code", sa.String(20), unique=True, nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("hook_type", sa.String(50), nullable=False),
        sa.Column("keypoint_1", sa.String(200), nullable=False),
        sa.Column("keypoint_2", sa.String(200), nullable=True),
        sa.Column("keypoint_3", sa.String(200), nullable=True),
        sa.Column("keypoint_4", sa.String(200), nullable=True),
        sa.Column("keypoint_5", sa.String(200), nullable=True),
        sa.Column("target_audience", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 2. creative_copies
    op.create_table(
        "creative_copies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("copy_code", sa.String(20), unique=True, nullable=False),
        sa.Column("angle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("creative_angles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("ad_format", sa.String(50), nullable=True),
        sa.Column("target_audience", sa.String(100), nullable=False),
        sa.Column("country_target", sa.String(100), nullable=True),
        sa.Column("language", sa.String(50), nullable=False),
        sa.Column("headline", sa.String(500), nullable=True),
        sa.Column("primary_text", sa.Text(), nullable=False),
        sa.Column("landing_page_url", sa.Text(), nullable=True),
        sa.Column("copywriter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("derived_verdict", sa.String(30), nullable=True),
        sa.Column("combo_count", sa.Integer(), server_default="0"),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 3. creative_materials
    op.create_table(
        "creative_materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("material_code", sa.String(20), unique=True, nullable=False),
        sa.Column("angle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("creative_angles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_type", sa.String(30), nullable=False),  # image / video / kol_video / gif / carousel_set / story_template
        sa.Column("design_type", sa.String(50), nullable=True),
        sa.Column("format_ratio", sa.String(50), nullable=True),  # can be multi e.g. "1:1, 4:5"
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("target_audience", sa.String(100), nullable=False),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("file_link", sa.Text(), nullable=True),
        sa.Column("kol_name", sa.String(100), nullable=True),
        sa.Column("kol_nationality", sa.String(100), nullable=True),
        sa.Column("paid_ads_eligible", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("paid_ads_channel", sa.String(50), nullable=True),
        sa.Column("usage_rights_until", sa.Date(), nullable=True),
        sa.Column("assigned_to", sa.String(100), nullable=True),
        sa.Column("order_status", sa.String(30), nullable=True),  # Briefing / In Progress / Done / Cancelled
        sa.Column("derived_verdict", sa.String(30), nullable=True),
        sa.Column("combo_count", sa.Integer(), server_default="0"),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 4. ad_combos — the verdict layer
    op.create_table(
        "ad_combos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("combo_code", sa.String(20), unique=True, nullable=False),
        sa.Column("copy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("creative_copies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("creative_materials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_audience", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("country_target", sa.String(100), nullable=True),
        sa.Column("angle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("creative_angles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("meta_ad_name", sa.String(500), unique=True, nullable=True),
        sa.Column("verdict", sa.String(30), nullable=True),  # winning / good / neutral / underperformer / kill
        sa.Column("verdict_source", sa.String(20), nullable=True),  # manual / auto_meta
        sa.Column("verdict_notes", sa.Text(), nullable=True),
        sa.Column("spend_vnd", sa.Numeric(18, 2), nullable=True),
        sa.Column("revenue_vnd", sa.Numeric(18, 2), nullable=True),
        sa.Column("roas", sa.Numeric(8, 4), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("date_first_run", sa.Date(), nullable=True),
        sa.Column("date_last_run", sa.Date(), nullable=True),
        sa.Column("run_status", sa.String(20), nullable=True),  # Active / Paused / Ended
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("copy_id", "material_id", name="uq_combo_copy_material"),
    )

    # Indexes for common filters
    op.create_index("ix_ad_combos_branch_audience", "ad_combos", ["branch_id", "target_audience"])
    op.create_index("ix_ad_combos_verdict", "ad_combos", ["verdict"])
    op.create_index("ix_ad_combos_angle_id", "ad_combos", ["angle_id"])
    op.create_index("ix_ad_combos_channel", "ad_combos", ["channel"])


def downgrade() -> None:
    op.drop_table("ad_combos")
    op.drop_table("creative_materials")
    op.drop_table("creative_copies")
    op.drop_table("creative_angles")
