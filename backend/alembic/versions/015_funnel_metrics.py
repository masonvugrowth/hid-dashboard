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


def _col_exists(table, column):
    conn = op.get_bind()
    result = conn.execute(sa.text(
        f"SELECT 1 FROM information_schema.columns "
        f"WHERE table_name='{table}' AND column_name='{column}'"
    ))
    return result.fetchone() is not None


def upgrade():
    for table in ("ads_performance", "ad_combos"):
        for col in ("lp_views", "add_to_cart", "initiate_checkout"):
            if not _col_exists(table, col):
                op.add_column(table, sa.Column(col, sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("ad_combos", "initiate_checkout")
    op.drop_column("ad_combos", "add_to_cart")
    op.drop_column("ad_combos", "lp_views")

    op.drop_column("ads_performance", "initiate_checkout")
    op.drop_column("ads_performance", "add_to_cart")
    op.drop_column("ads_performance", "lp_views")
