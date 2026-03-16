"""Add hook_type, keypoints, verdict, angle_code to ad_angles; add meta_ad_id to ads_performance

Revision ID: 003
Revises: 002
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ad_angles", sa.Column("angle_code", sa.String(20), nullable=True))
    op.add_column("ad_angles", sa.Column("hook_type", sa.String(50), nullable=True))
    op.add_column("ad_angles", sa.Column("keypoint_1", sa.Text, nullable=True))
    op.add_column("ad_angles", sa.Column("keypoint_2", sa.Text, nullable=True))
    op.add_column("ad_angles", sa.Column("keypoint_3", sa.Text, nullable=True))
    op.add_column("ad_angles", sa.Column("keypoint_4", sa.Text, nullable=True))
    op.add_column("ad_angles", sa.Column("keypoint_5", sa.Text, nullable=True))
    op.add_column("ad_angles", sa.Column("verdict", sa.String(50), nullable=True))

    op.add_column("ads_performance", sa.Column("meta_ad_id", sa.String(50), nullable=True))
    op.add_column("ads_performance", sa.Column("meta_campaign_id", sa.String(50), nullable=True))
    # funnel_stage already exists in 002 migration — skip
    op.add_column("ads_performance", sa.Column("pic", sa.String(50), nullable=True))
    op.add_column("ads_performance", sa.Column("ad_body", sa.Text, nullable=True))


def downgrade():
    for col in ["angle_code", "hook_type", "keypoint_1", "keypoint_2", "keypoint_3",
                "keypoint_4", "keypoint_5", "verdict"]:
        op.drop_column("ad_angles", col)

    for col in ["meta_ad_id", "meta_campaign_id", "funnel_stage", "pic", "ad_body"]:
        op.drop_column("ads_performance", col)
