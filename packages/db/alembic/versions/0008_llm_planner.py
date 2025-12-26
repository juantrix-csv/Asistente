"""add llm config and tool_runs audit fields

Revision ID: 0008_llm_planner
Revises: 0007_memory_block7
Create Date: 2025-01-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0008_llm_planner"
down_revision = "0007_memory_block7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tool_runs", sa.Column("decision_source", sa.Text(), nullable=True))
    op.add_column("tool_runs", sa.Column("requested_by", sa.Text(), nullable=True))
    op.add_column("tool_runs", sa.Column("risk_level", sa.Text(), nullable=True))
    op.add_column(
        "tool_runs", sa.Column("autonomy_mode_snapshot", postgresql.JSONB(), nullable=True)
    )

    op.add_column("system_config", sa.Column("llm_provider", sa.Text(), nullable=False, server_default="ollama"))
    op.add_column(
        "system_config",
        sa.Column(
            "llm_base_url",
            sa.Text(),
            nullable=False,
            server_default="http://host.docker.internal:11434",
        ),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "llm_model_name",
            sa.Text(),
            nullable=False,
            server_default="qwen2.5:7b-instruct-q4",
        ),
    )
    op.add_column(
        "system_config",
        sa.Column("llm_temperature", sa.Float(), nullable=False, server_default="0.3"),
    )
    op.add_column(
        "system_config",
        sa.Column("llm_max_tokens", sa.Integer(), nullable=False, server_default="512"),
    )
    op.add_column(
        "system_config",
        sa.Column("llm_json_mode", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.execute(
        "UPDATE system_config SET "
        "llm_provider = COALESCE(llm_provider, 'ollama'), "
        "llm_base_url = COALESCE(llm_base_url, 'http://host.docker.internal:11434'), "
        "llm_model_name = COALESCE(llm_model_name, 'qwen2.5:7b-instruct-q4'), "
        "llm_temperature = COALESCE(llm_temperature, 0.3), "
        "llm_max_tokens = COALESCE(llm_max_tokens, 512), "
        "llm_json_mode = COALESCE(llm_json_mode, true)"
    )


def downgrade() -> None:
    op.drop_column("system_config", "llm_json_mode")
    op.drop_column("system_config", "llm_max_tokens")
    op.drop_column("system_config", "llm_temperature")
    op.drop_column("system_config", "llm_model_name")
    op.drop_column("system_config", "llm_base_url")
    op.drop_column("system_config", "llm_provider")
    op.drop_column("tool_runs", "autonomy_mode_snapshot")
    op.drop_column("tool_runs", "risk_level")
    op.drop_column("tool_runs", "requested_by")
    op.drop_column("tool_runs", "decision_source")
