"""add proactive_events table

Revision ID: 0005_proactive_events
Revises: 0004_google_calendar
Create Date: 2025-01-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_proactive_events"
down_revision = "0004_google_calendar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proactive_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_proactive_events_dedupe_key", "proactive_events", ["dedupe_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_proactive_events_dedupe_key", table_name="proactive_events")
    op.drop_table("proactive_events")
