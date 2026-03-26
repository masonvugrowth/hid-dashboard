"""Create gov_visitor_data table for government country visitor statistics.

Revision ID: 021
Revises: 020
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gov_visitor_data",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("destination", sa.String(100), nullable=False),
        sa.Column("source_country", sa.String(100), nullable=False),
        sa.Column("rank", sa.Integer, nullable=True),
        sa.Column("jan", sa.Integer, server_default="0"),
        sa.Column("feb", sa.Integer, server_default="0"),
        sa.Column("mar", sa.Integer, server_default="0"),
        sa.Column("apr", sa.Integer, server_default="0"),
        sa.Column("may", sa.Integer, server_default="0"),
        sa.Column("jun", sa.Integer, server_default="0"),
        sa.Column("jul", sa.Integer, server_default="0"),
        sa.Column("aug", sa.Integer, server_default="0"),
        sa.Column("sep", sa.Integer, server_default="0"),
        sa.Column("oct", sa.Integer, server_default="0"),
        sa.Column("nov", sa.Integer, server_default="0"),
        sa.Column("dec", sa.Integer, server_default="0"),
        sa.Column("total", sa.Integer, server_default="0"),
        sa.Column("data_year", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_gov_visitor_destination", "gov_visitor_data", ["destination"])
    op.create_index("ix_gov_visitor_source_country", "gov_visitor_data", ["source_country"])


def downgrade():
    op.drop_index("ix_gov_visitor_source_country")
    op.drop_index("ix_gov_visitor_destination")
    op.drop_table("gov_visitor_data")
