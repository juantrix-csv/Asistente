"""add contacts trust, threads, events, privacy rules

Revision ID: 0010_relations_block10
Revises: 0009_requests_block9
Create Date: 2025-01-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0010_relations_block10"
down_revision = "0009_requests_block9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("trust_level", sa.Integer(), nullable=False, server_default="20"))
    op.add_column("contacts", sa.Column("trust_label", sa.Text(), nullable=False, server_default="unknown"))
    op.add_column("contacts", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("contacts", sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "contacts",
        sa.Column("preferred_channel", sa.Text(), nullable=False, server_default="whatsapp"),
    )
    op.add_column(
        "contacts",
        sa.Column("allow_auto_reply", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "conversation_threads",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("contact_id", sa.BigInteger(), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False, server_default="whatsapp"),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_summary", sa.Text(), nullable=True),
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
    op.create_index(
        "ix_conversation_threads_contact_id",
        "conversation_threads",
        ["contact_id"],
        unique=False,
    )

    op.create_table(
        "conversation_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("thread_id", sa.BigInteger(), sa.ForeignKey("conversation_threads.id"), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("message_raw_id", sa.BigInteger(), sa.ForeignKey("messages_raw.id"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("extracted", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_conversation_events_thread_id",
        "conversation_events",
        ["thread_id"],
        unique=False,
    )

    op.create_table(
        "privacy_rules",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("rule_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("rule_name", name="uq_privacy_rules_rule_name"),
    )
    op.create_index("ix_privacy_rules_rule_name", "privacy_rules", ["rule_name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_privacy_rules_rule_name", table_name="privacy_rules")
    op.drop_table("privacy_rules")
    op.drop_index("ix_conversation_events_thread_id", table_name="conversation_events")
    op.drop_table("conversation_events")
    op.drop_index("ix_conversation_threads_contact_id", table_name="conversation_threads")
    op.drop_table("conversation_threads")

    op.drop_column("contacts", "allow_auto_reply")
    op.drop_column("contacts", "preferred_channel")
    op.drop_column("contacts", "last_interaction_at")
    op.drop_column("contacts", "notes")
    op.drop_column("contacts", "trust_label")
    op.drop_column("contacts", "trust_level")
