"""Add funnel metrics columns to ads_performance and ad_combos.

New columns: lp_views, add_to_cart, initiate_checkout

Revision ID: 015
Revises: 014
"""

from alembic import op
import sqlalchemy as sa


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    # ads_performance — add funnel columns
    op.add_column("ads_performance", sa.Column("lp_views", sa.Integer(), nullable=True))
    op.add_column("ads_performance", sa.Column("add_to_cart", sa.Integer(), nullable=True))
    op.add_column("ads_performance", sa.Column("initiate_checkout", sa.Integer(), nullable=True))

    # ad_combos — add funnel columns
    op.add_column("ad_combos", sa.Column("lp_views", sa.Integer(), nullable=True))
    op.add_column("ad_combos", sa.Column("add_to_cart", sa.Integer(), nullable=True))
    op.add_column("ad_combos", sa.Column("initiate_checkout", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("ad_combos", "initiate_checkout")
    op.drop_column("ad_combos", "add_to_cart")
    op.drop_column("ad_combos", "lp_views")

    op.drop_column("ads_performance", "initiate_checkout")
    op.drop_column("ads_performance", "add_to_cart")
    op.drop_column("ads_performance", "lp_views")
