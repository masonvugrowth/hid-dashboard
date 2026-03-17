"""Seed team accounts

Revision ID: 006
Revises: 005
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
import bcrypt
import uuid

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

DEFAULT_PASSWORD = "Meander@2026"

TEAM = [
    {"email": "leo@staymeander.com",    "name": "Leo",    "role": "editor"},
    {"email": "nuha@staymeander.com",   "name": "Nuha",   "role": "editor"},
    {"email": "alice@staymeander.com",  "name": "Alice",  "role": "editor"},
    {"email": "tszkin@staymeander.com", "name": "Tszkin", "role": "editor"},
]


def upgrade():
    conn = op.get_bind()
    users = sa.table(
        "users",
        sa.column("id", sa.String),
        sa.column("email", sa.String),
        sa.column("name", sa.String),
        sa.column("role", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("is_active", sa.Boolean),
    )

    pw_hash = bcrypt.hashpw(DEFAULT_PASSWORD.encode(), bcrypt.gensalt()).decode()

    for member in TEAM:
        existing = conn.execute(
            sa.text("SELECT id FROM users WHERE email = :email"),
            {"email": member["email"]},
        ).fetchone()

        if existing:
            conn.execute(
                sa.text(
                    "UPDATE users SET role=:role, password_hash=:pw, is_active=true, name=:name WHERE email=:email"
                ),
                {"role": member["role"], "pw": pw_hash, "name": member["name"], "email": member["email"]},
            )
        else:
            conn.execute(
                users.insert().values(
                    id=str(uuid.uuid4()),
                    email=member["email"],
                    name=member["name"],
                    role=member["role"],
                    password_hash=pw_hash,
                    is_active=True,
                )
            )


def downgrade():
    emails = [m["email"] for m in TEAM]
    for email in emails:
        op.execute(f"DELETE FROM users WHERE email = '{email}'")
