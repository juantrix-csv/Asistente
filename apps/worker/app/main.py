from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from apps.worker.app.proactive import TIMEZONE, run_daily_digest, run_proactive_tick


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    scheduler = BlockingScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        run_proactive_tick,
        "interval",
        minutes=2,
        id="proactive_tick",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_daily_digest,
        "cron",
        hour=21,
        minute=0,
        id="daily_digest",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
