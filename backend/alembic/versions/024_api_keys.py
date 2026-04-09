"""Create api_keys table for external API access.

Revision ID: 024
Revises: 023
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("key_hash", sa.String(200), nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_api_keys_prefix", "api_keys", ["key_prefix"])
    op.create_index("idx_api_keys_active", "api_keys", ["is_active"])


def downgrade():
    op.drop_index("idx_api_keys_active")
    op.drop_index("idx_api_keys_prefix")
    op.drop_table("api_keys")
