from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from packages.db.models import AssistantRequest, SystemConfig

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


class RequestPolicy:
    def should_ask(
        self,
        request: AssistantRequest,
        now_local: datetime,
        autonomy_mode: str,
        config: SystemConfig,
        asked_today: int,
    ) -> bool:
        if request.status != "open":
            return False

        local_time = now_local.astimezone(TIMEZONE).time()
        if _in_quiet_hours(local_time, config):
            return False

        if autonomy_mode in {"focus", "urgencies_only"}:
            return False

        if asked_today >= 1:
            return False

        if request.priority >= 85:
            return True

        return _in_strong_window(local_time, config)


def _in_quiet_hours(local_time: time, config: SystemConfig) -> bool:
    return config.quiet_hours_start <= local_time < config.quiet_hours_end


def _in_strong_window(local_time: time, config: SystemConfig) -> bool:
    return config.strong_window_start <= local_time < config.strong_window_end
