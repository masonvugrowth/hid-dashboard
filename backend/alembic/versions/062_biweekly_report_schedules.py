"""biweekly_report_schedules table

Revision ID: 062
Revises: 061
Create Date: 2026-09-03

A standing instruction to email one branch's Bi-Weekly report automatically,
to a saved list, on the day the period closes. One row per branch.

See app/models/biweekly_report_schedule.py for why the send days are two
bounded integers rather than a cron string, and why last_sent_period_key is
the column the whole job's correctness rests on.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "062"
down_revision = "061"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "biweekly_report_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "branch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("recipient_user_ids", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("extra_emails", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        # Bounded so a send can never be scheduled before its period closes:
        # 15-28 lands after the 1st-14th half, 1-14 lands in the month after
        # the 15th-EOM half.
        sa.Column("send_day_h1", sa.Integer(), nullable=False,
                  server_default="15"),
        sa.Column("send_day_h2", sa.Integer(), nullable=False,
                  server_default="1"),
        sa.Column("hour", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_sent_period_key", sa.String(16), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sent_to", postgresql.JSONB(), nullable=True),
        sa.Column("last_failed", postgresql.JSONB(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        # One schedule per branch. The runner locks this row while it sends,
        # so a second row for the same branch would be a second, unlocked
        # path to the same mailbox.
        sa.UniqueConstraint("branch_id", name="uq_biweekly_schedule_branch"),
        sa.CheckConstraint("send_day_h1 BETWEEN 15 AND 28",
                           name="ck_biweekly_schedule_day_h1"),
        sa.CheckConstraint("send_day_h2 BETWEEN 1 AND 14",
                           name="ck_biweekly_schedule_day_h2"),
        sa.CheckConstraint("hour BETWEEN 0 AND 23",
                           name="ck_biweekly_schedule_hour"),
        sa.CheckConstraint("minute BETWEEN 0 AND 59",
                           name="ck_biweekly_schedule_minute"),
    )
    op.create_index(
        "ix_biweekly_schedule_branch", "biweekly_report_schedules",
        ["branch_id"], unique=True,
    )


def downgrade():
    op.drop_index("ix_biweekly_schedule_branch",
                  table_name="biweekly_report_schedules")
    op.drop_table("biweekly_report_schedules")
