"""add memory tables and pgvector extension

Revision ID: 0007_memory_block7
Revises: 0006_proactivity_block6
Create Date: 2025-01-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "0007_memory_block7"
down_revision = "0006_proactivity_block6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "memory_chunks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("embedding", Vector(384), nullable=True),
    )
    op.create_index("ix_memory_chunks_chat_id", "memory_chunks", ["chat_id"], unique=False)
    op.create_index(
        "ix_memory_chunks_tags",
        "memory_chunks",
        ["tags"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_memory_chunks_source",
        "memory_chunks",
        ["source_type", "source_ref"],
        unique=True,
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memory_chunks_embedding "
        "ON memory_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "assistant_notes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
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
        "memory_facts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_memory_facts_subject_key",
        "memory_facts",
        ["subject", "key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_memory_facts_subject_key", table_name="memory_facts")
    op.drop_table("memory_facts")
    op.drop_table("assistant_notes")
    op.execute("DROP INDEX IF EXISTS ix_memory_chunks_embedding")
    op.drop_index("ix_memory_chunks_source", table_name="memory_chunks")
    op.drop_index("ix_memory_chunks_tags", table_name="memory_chunks")
    op.drop_index("ix_memory_chunks_chat_id", table_name="memory_chunks")
    op.drop_table("memory_chunks")
