from __future__ import annotations

import logging
import os
import time

from sqlalchemy import create_engine, text

from packages.db.database import get_database_url

logger = logging.getLogger(__name__)


def wait_for_db() -> None:
    timeout_seconds = int(os.getenv("DB_WAIT_SECONDS", "30"))
    interval_seconds = float(os.getenv("DB_WAIT_INTERVAL", "1"))
    deadline = time.monotonic() + timeout_seconds
    url = get_database_url()

    while True:
        try:
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(interval_seconds)


if __name__ == "__main__":
    wait_for_db()