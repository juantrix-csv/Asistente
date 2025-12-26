"""add conversation state and autonomy rules

Revision ID: 0003_agent_core
Revises: 0002_messages_contacts
Create Date: 2025-01-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0003_agent_core"
down_revision = "0002_messages_contacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_state",
        sa.Column("chat_id", sa.Text(), primary_key=True),
        sa.Column("pending_action_json", postgresql.JSONB(), nullable=True),
        sa.Column("pending_question_json", postgresql.JSONB(), nullable=True),
        sa.Column("last_intent", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "autonomy_rules",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("until_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_autonomy_rules_scope", "autonomy_rules", ["scope"], unique=False)
    op.create_index(
        "ix_autonomy_rules_until_at", "autonomy_rules", ["until_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_autonomy_rules_until_at", table_name="autonomy_rules")
    op.drop_index("ix_autonomy_rules_scope", table_name="autonomy_rules")
    op.drop_table("autonomy_rules")
    op.drop_table("conversation_state")