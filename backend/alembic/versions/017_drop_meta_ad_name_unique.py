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
    # Drop unique index/constraint on meta_ad_name (may be named differently)
    conn = op.get_bind()
    # Check which constraint/index name exists
    result = conn.execute(sa.text(
        "SELECT indexname FROM pg_indexes "
        "WHERE tablename='ad_combos' AND indexdef LIKE '%meta_ad_name%'"
    ))
    for row in result:
        op.drop_index(row[0], table_name="ad_combos")

    # Also try dropping constraint directly (in case it's a table constraint)
    try:
        op.drop_constraint("ad_combos_meta_ad_name_key", "ad_combos", type_="unique")
    except Exception:
        pass  # Already dropped via index


def downgrade():
    op.create_unique_constraint("ad_combos_meta_ad_name_key", "ad_combos", ["meta_ad_name"])
