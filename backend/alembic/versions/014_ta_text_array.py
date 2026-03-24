"""Migrate target_audience from VARCHAR(100) to TEXT[] array.

Backfills existing single values into arrays.

Revision ID: 014
Revises: 013
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    # --- creative_angles: nullable VARCHAR -> nullable TEXT[] ---
    op.execute(
        "ALTER TABLE creative_angles "
        "ALTER COLUMN target_audience TYPE TEXT[] "
        "USING CASE WHEN target_audience IS NOT NULL THEN ARRAY[target_audience] ELSE NULL END"
    )

    # --- creative_copies: NOT NULL VARCHAR -> NOT NULL TEXT[] ---
    op.execute(
        "ALTER TABLE creative_copies "
        "ALTER COLUMN target_audience TYPE TEXT[] "
        "USING ARRAY[target_audience]"
    )
    op.execute(
        "ALTER TABLE creative_copies "
        "ALTER COLUMN target_audience SET DEFAULT '{}'"
    )

    # --- creative_materials: NOT NULL VARCHAR -> NOT NULL TEXT[] ---
    op.execute(
        "ALTER TABLE creative_materials "
        "ALTER COLUMN target_audience TYPE TEXT[] "
        "USING ARRAY[target_audience]"
    )
    op.execute(
        "ALTER TABLE creative_materials "
        "ALTER COLUMN target_audience SET DEFAULT '{}'"
    )

    # --- ad_combos: NOT NULL VARCHAR -> NOT NULL TEXT[] ---
    # Drop the old index first (type incompatible)
    op.execute("DROP INDEX IF EXISTS ix_ad_combos_branch_audience")

    op.execute(
        "ALTER TABLE ad_combos "
        "ALTER COLUMN target_audience TYPE TEXT[] "
        "USING ARRAY[target_audience]"
    )
    op.execute(
        "ALTER TABLE ad_combos "
        "ALTER COLUMN target_audience SET DEFAULT '{}'"
    )

    # Recreate index using GIN for array containment queries
    op.execute(
        "CREATE INDEX ix_ad_combos_branch_audience "
        "ON ad_combos USING GIN (target_audience)"
    )


def downgrade():
    # Revert TEXT[] back to VARCHAR(100) — takes first element
    op.execute("DROP INDEX IF EXISTS ix_ad_combos_branch_audience")

    for table in ("creative_angles", "creative_copies", "creative_materials", "ad_combos"):
        op.execute(
            f"ALTER TABLE {table} "
            f"ALTER COLUMN target_audience TYPE VARCHAR(100) "
            f"USING target_audience[1]"
        )
        op.execute(
            f"ALTER TABLE {table} "
            f"ALTER COLUMN target_audience DROP DEFAULT"
        )

    # Recreate original btree index
    op.execute(
        "CREATE INDEX ix_ad_combos_branch_audience "
        "ON ad_combos (branch_id, target_audience)"
    )
