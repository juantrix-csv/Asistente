from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from packages.db.database import SessionLocal, get_database_url


@pytest.fixture(scope="session", autouse=True)
def apply_migrations() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    alembic_ini = base_dir / "packages" / "db" / "alembic.ini"
    alembic_dir = base_dir / "packages" / "db" / "alembic"

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(alembic_dir))
    config.set_main_option("sqlalchemy.url", get_database_url())
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clean_db() -> None:
    with SessionLocal() as session:
        session.execute(
            text(
                "TRUNCATE TABLE messages_raw, contacts, conversation_state, autonomy_rules, secrets, tool_runs, proactive_events, digests, system_config, tasks, memory_chunks, assistant_notes, memory_facts, assistant_requests, assistant_request_events RESTART IDENTITY"
            )
        )
        session.commit()
