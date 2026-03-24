"""Drop UNIQUE constraint on ad_combos.meta_ad_name.

Same Meta ad can legitimately map to multiple combos when copy/material
dedup produces different pairs. Keeping exact Meta name is critical for
performance sync matching.

Revision ID: 017
Revises: 016
"""

from alembic import op
import sqlalchemy as sa


revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    # Safe idempotent drop — constraint may already be gone
    conn = op.get_bind()

    # Check if constraint still exists before trying to drop
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.table_constraints "
        "WHERE table_name='ad_combos' AND constraint_name='ad_combos_meta_ad_name_key'"
    ))
    if result.fetchone():
        op.drop_constraint("ad_combos_meta_ad_name_key", "ad_combos", type_="unique")


def downgrade():
    op.create_unique_constraint("ad_combos_meta_ad_name_key", "ad_combos", ["meta_ad_name"])
