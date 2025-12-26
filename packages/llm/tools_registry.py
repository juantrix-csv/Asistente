from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from packages.agent_core.tools.calendar_tool import CalendarTool


@dataclass(frozen=True)
class ToolSpec:
    name: str
    scope: str
    description: str


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "calendar.create_event": ToolSpec(
        name="calendar.create_event",
        scope="calendar_create",
        description="Crear un evento en Google Calendar",
    ),
    "calendar.list_events": ToolSpec(
        name="calendar.list_events",
        scope="calendar_create",
        description="Listar eventos entre fechas",
    ),
    "calendar.is_free": ToolSpec(
        name="calendar.is_free",
        scope="calendar_create",
        description="Chequear disponibilidad en un rango",
    ),
}


def get_tool_names() -> set[str]:
    return set(TOOL_REGISTRY.keys())


def get_tool_scope(tool_name: str) -> str | None:
    spec = TOOL_REGISTRY.get(tool_name)
    if not spec:
        return None
    return spec.scope


def validate_tool_input(tool_name: str, tool_input: dict[str, Any]) -> list[str]:
    if tool_name == "calendar.create_event":
        return _missing_fields(tool_input, ["title", "start", "end"])
    if tool_name == "calendar.list_events":
        return _missing_fields(tool_input, ["time_min", "time_max"])
    if tool_name == "calendar.is_free":
        return _missing_fields(tool_input, ["start", "end"])
    return []


def execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    calendar_tool: CalendarTool | None = None,
) -> dict[str, Any]:
    tool = calendar_tool or CalendarTool()
    if tool_name == "calendar.create_event":
        title = tool_input.get("title", "Sin titulo")
        start = _parse_datetime(tool_input.get("start"))
        end = _parse_datetime(tool_input.get("end"))
        if start is None or end is None:
            raise ValueError("Missing start/end")
        return tool.create_event(
            title,
            start,
            end,
            location=tool_input.get("location"),
            notes=tool_input.get("notes"),
        )
    if tool_name == "calendar.list_events":
        time_min = _parse_datetime(tool_input.get("time_min"))
        time_max = _parse_datetime(tool_input.get("time_max"))
        if time_min is None or time_max is None:
            raise ValueError("Missing time_min/time_max")
        return {"events": tool.list_events(time_min, time_max)}
    if tool_name == "calendar.is_free":
        start = _parse_datetime(tool_input.get("start"))
        end = _parse_datetime(tool_input.get("end"))
        if start is None or end is None:
            raise ValueError("Missing start/end")
        return {"is_free": tool.is_free(start, end)}
    raise ValueError(f"Unknown tool {tool_name}")


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        value = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _missing_fields(tool_input: dict[str, Any], required: list[str]) -> list[str]:
    missing = []
    for field in required:
        value = tool_input.get(field)
        if value is None or value == "":
            missing.append(field)
    return missing
