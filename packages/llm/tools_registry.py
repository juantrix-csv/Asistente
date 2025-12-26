from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from packages.agent_core.tools.calendar_tool import CalendarTool
from packages.relations.message_tools import build_reply_draft


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
    "message.reply_draft": ToolSpec(
        name="message.reply_draft",
        scope="message_reply",
        description="Generar borrador de respuesta a un contacto",
    ),
    "message.send": ToolSpec(
        name="message.send",
        scope="message_reply",
        description="Enviar mensaje por WhatsApp",
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
    if tool_name == "message.reply_draft":
        return _missing_fields(tool_input, ["incoming_text"])
    if tool_name == "message.send":
        return _missing_fields(tool_input, ["chat_id", "text"])
    return []


def execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    calendar_tool: CalendarTool | None = None,
    message_sender: Callable[[str, str], dict[str, Any]] | None = None,
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
    if tool_name == "message.reply_draft":
        incoming_text = str(tool_input.get("incoming_text", ""))
        contact_name = tool_input.get("contact_name")
        return {"draft": build_reply_draft(incoming_text, contact_name)}
    if tool_name == "message.send":
        if not message_sender:
            raise ValueError("Missing message_sender")
        chat_id = tool_input.get("chat_id")
        text = tool_input.get("text")
        if not chat_id or not text:
            raise ValueError("Missing chat_id/text")
        response = message_sender(chat_id, text)
        return {"response": response}
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
