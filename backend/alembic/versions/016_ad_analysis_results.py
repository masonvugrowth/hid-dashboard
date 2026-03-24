"""Create ad_analysis_results table for AI-powered ad analysis.

Revision ID: 016
Revises: 015
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    # Guard: skip if table already exists
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name='ad_analysis_results'"
    ))
    if result.fetchone():
        return

    op.create_table(
        "ad_analysis_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("combo_id", UUID(as_uuid=True), sa.ForeignKey("ad_combos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("detected_angles", ARRAY(sa.Text()), nullable=True),
        sa.Column("detected_ta", ARRAY(sa.Text()), nullable=True),
        sa.Column("keypoints", ARRAY(sa.Text()), nullable=True),
        sa.Column("visual_summary", sa.Text(), nullable=True),
        sa.Column("funnel_analysis", JSONB, nullable=True),
        sa.Column("ai_recommendation", sa.Text(), nullable=True),
        sa.Column("recommendation_type", sa.String(30), nullable=True),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("model_used", sa.String(50), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_analysis_combo", "ad_analysis_results", ["combo_id"])
    op.create_index("ix_analysis_combo_id", "ad_analysis_results", ["combo_id"])


def downgrade():
    op.drop_table("ad_analysis_results")
