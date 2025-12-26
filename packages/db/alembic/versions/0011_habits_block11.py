"""add habits and coaching tables

Revision ID: 0011_habits_block11
Revises: 0010_relations_block10
Create Date: 2025-01-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0011_habits_block11"
down_revision = "0010_relations_block10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "habits",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schedule_type", sa.Text(), nullable=False),
        sa.Column("target_per_week", sa.Integer(), nullable=True),
        sa.Column("days_of_week", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("window_start", sa.Time(), nullable=False),
        sa.Column("window_end", sa.Time(), nullable=False),
        sa.Column("min_version_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "habit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("habit_id", sa.BigInteger(), sa.ForeignKey("habits.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_habit_logs_habit_id", "habit_logs", ["habit_id"], unique=False)
    op.create_unique_constraint(
        "uq_habit_logs_habit_id_date",
        "habit_logs",
        ["habit_id", "date"],
    )

    op.create_table(
        "habit_nudges",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("habit_id", sa.BigInteger(), sa.ForeignKey("habits.id"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("strategy", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_habit_nudges_habit_id", "habit_nudges", ["habit_id"], unique=False)

    op.create_table(
        "coaching_profile",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("intensity", sa.Text(), nullable=False, server_default="medium"),
        sa.Column("style", sa.Text(), nullable=False, server_default="formal"),
        sa.Column("preferred_times", postgresql.JSONB(), nullable=True),
        sa.Column("what_works", postgresql.JSONB(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("coaching_profile")
    op.drop_index("ix_habit_nudges_habit_id", table_name="habit_nudges")
    op.drop_table("habit_nudges")
    op.drop_constraint("uq_habit_logs_habit_id_date", "habit_logs", type_="unique")
    op.drop_index("ix_habit_logs_habit_id", table_name="habit_logs")
    op.drop_table("habit_logs")
    op.drop_table("habits")
