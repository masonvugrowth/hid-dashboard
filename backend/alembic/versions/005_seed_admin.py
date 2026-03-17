"""Seed default admin user

Revision ID: 005
Revises: 004
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
import bcrypt
import uuid

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

ADMIN_EMAIL = "mason@staymeander.com"
ADMIN_NAME = "Mason"
ADMIN_PASSWORD = "Meander@2026"


def upgrade():
    users = table(
        "users",
        column("id", sa.String),
        column("email", sa.String),
        column("name", sa.String),
        column("role", sa.String),
        column("password_hash", sa.String),
        column("is_active", sa.Boolean),
    )

    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT id FROM users WHERE email = :email"),
        {"email": ADMIN_EMAIL},
    ).fetchone()

    pw_hash = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()

    if existing:
        conn.execute(
            sa.text(
                "UPDATE users SET role='admin', password_hash=:pw, is_active=true, name=:name WHERE email=:email"
            ),
            {"pw": pw_hash, "name": ADMIN_NAME, "email": ADMIN_EMAIL},
        )
    else:
        conn.execute(
            users.insert().values(
                id=str(uuid.uuid4()),
                email=ADMIN_EMAIL,
                name=ADMIN_NAME,
                role="admin",
                password_hash=pw_hash,
                is_active=True,
            )
        )


def downgrade():
    op.execute(f"DELETE FROM users WHERE email = '{ADMIN_EMAIL}'")
