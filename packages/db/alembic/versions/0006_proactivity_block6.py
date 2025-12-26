"""extend proactive_events and add digests/system_config/tasks

Revision ID: 0006_proactivity_block6
Revises: 0005_proactive_events
Create Date: 2025-01-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006_proactivity_block6"
down_revision = "0005_proactive_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proactive_events", sa.Column("entity_id", sa.Text(), nullable=True))
    op.add_column("proactive_events", sa.Column("priority", sa.Integer(), nullable=True))

    op.create_table(
        "digests",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_digests_day", "digests", ["day"], unique=True)

    op.create_table(
        "system_config",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("quiet_hours_start", sa.Time(), nullable=False),
        sa.Column("quiet_hours_end", sa.Time(), nullable=False),
        sa.Column("strong_window_start", sa.Time(), nullable=False),
        sa.Column("strong_window_end", sa.Time(), nullable=False),
        sa.Column("daily_proactive_limit", sa.Integer(), nullable=False),
        sa.Column("maybe_cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("urgent_threshold", sa.Integer(), nullable=False),
        sa.Column("maybe_threshold", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_tasks_due_date", "tasks", ["due_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tasks_due_date", table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("system_config")
    op.drop_index("ix_digests_day", table_name="digests")
    op.drop_table("digests")
    op.drop_column("proactive_events", "priority")
    op.drop_column("proactive_events", "entity_id")
