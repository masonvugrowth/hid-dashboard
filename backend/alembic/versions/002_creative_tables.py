"""002 creative tables

Revision ID: 002
Revises: 001
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 13. branch_keypoints
    op.create_table(
        "branch_keypoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keypoint", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 14. ad_copies
    op.create_table(
        "ad_copies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("copy_id", sa.String(20), unique=True, nullable=False),
        sa.Column("angle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ad_angles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("ad_format", sa.String(50), nullable=True),
        sa.Column("target_audience", sa.String(100), nullable=True),
        sa.Column("target_country", sa.String(100), nullable=True),
        sa.Column("language", sa.String(100), nullable=True),
        sa.Column("headline", sa.String(500), nullable=True),
        sa.Column("primary_text", sa.Text(), nullable=True),
        sa.Column("copywriter", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), server_default="Draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 15. ad_materials
    op.create_table(
        "ad_materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("material_id", sa.String(20), unique=True, nullable=False),
        sa.Column("angle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ad_angles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_type", sa.String(50), nullable=True),
        sa.Column("format_ratio", sa.String(20), nullable=True),
        sa.Column("design_type", sa.String(50), nullable=True),
        sa.Column("assigned_to", sa.String(100), nullable=True),
        sa.Column("brief_link", sa.Text(), nullable=True),
        sa.Column("order_status", sa.String(50), server_default="Briefing"),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("file_link", sa.Text(), nullable=True),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 16. ad_approvals
    op.create_table(
        "ad_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("copy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ad_copies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ad_materials.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kol_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kol_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("submitted_by", sa.String(100), nullable=True),
        sa.Column("submitted_date", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("landing_page_url", sa.Text(), nullable=True),
        sa.Column("reviewer", sa.String(100), nullable=True),
        sa.Column("approval_status", sa.String(30), server_default="Pending"),
        sa.Column("approval_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 17. ad_names
    op.create_table(
        "ad_names",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ad_approvals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("copy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ad_copies.id"), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ad_materials.id"), nullable=True),
        sa.Column("generated_name", sa.String(500), nullable=False),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("ad_names")
    op.drop_table("ad_approvals")
    op.drop_table("ad_materials")
    op.drop_table("ad_copies")
    op.drop_table("branch_keypoints")
