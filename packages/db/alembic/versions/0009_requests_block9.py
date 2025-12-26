"""add assistant requests tables

Revision ID: 0009_requests_block9
Revises: 0008_llm_planner
Create Date: 2025-01-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0009_requests_block9"
down_revision = "0008_llm_planner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("request_type", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("dedupe_key", name="uq_assistant_requests_dedupe_key"),
    )

    op.create_table(
        "assistant_request_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("request_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
    )
    op.create_index(
        "ix_assistant_request_events_request_id",
        "assistant_request_events",
        ["request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_request_events_request_id", table_name="assistant_request_events")
    op.drop_table("assistant_request_events")
    op.drop_table("assistant_requests")
