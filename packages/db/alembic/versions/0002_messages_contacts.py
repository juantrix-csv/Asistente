"""create messages and contacts tables

Revision ID: 0002_messages_contacts
Revises: 0001_initial
Create Date: 2025-01-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002_messages_contacts"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("chat_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
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
    op.create_index("ix_contacts_chat_id", "contacts", ["chat_id"], unique=True)

    op.create_table(
        "messages_raw",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column(
            "platform",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'whatsapp'"),
        ),
        sa.Column("chat_id", sa.Text(), nullable=False),
        sa.Column("sender_id", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_messages_raw_chat_id", "messages_raw", ["chat_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_messages_raw_chat_id", table_name="messages_raw")
    op.drop_table("messages_raw")
    op.drop_index("ix_contacts_chat_id", table_name="contacts")
    op.drop_table("contacts")