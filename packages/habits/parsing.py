from __future__ import annotations

import re


DAY_MAP = {
    "lunes": 0,
    "lun": 0,
    "martes": 1,
    "mar": 1,
    "miercoles": 2,
    "mie": 2,
    "jueves": 3,
    "jue": 3,
    "viernes": 4,
    "vie": 4,
    "sabado": 5,
    "sab": 5,
    "domingo": 6,
    "dom": 6,
}


def parse_habit_text(text: str) -> dict[str, object]:
    folded = _fold(text)
    target_per_week = _parse_target_per_week(folded)
    days_of_week = _parse_days_of_week(folded)

    schedule_type = "daily"
    if days_of_week:
        schedule_type = "scheduled"
    elif target_per_week:
        schedule_type = "weekly"

    return {
        "schedule_type": schedule_type,
        "target_per_week": target_per_week,
        "days_of_week": days_of_week,
    }


def _parse_target_per_week(folded: str) -> int | None:
    match = re.search(r"(\d{1,2})\s*veces\s*por\s*semana", folded)
    if not match:
        return None
    value = int(match.group(1))
    if value <= 0:
        return None
    return value


def _parse_days_of_week(folded: str) -> list[int] | None:
    found: list[int] = []
    for key, idx in DAY_MAP.items():
        if re.search(rf"\\b{re.escape(key)}\\b", folded):
            found.append(idx)
    if not found:
        return None
    return sorted(set(found))


def _fold(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()
