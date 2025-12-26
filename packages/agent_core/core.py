from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
import os
import re
import unicodedata
from typing import Any
from zoneinfo import ZoneInfo

from packages.agent_core.tools.calendar_tool import CalendarNotAuthorized, CalendarTool
from packages.agent_core.tools.google_oauth import OAuthConfigError
from packages.db.database import SessionLocal
from packages.db.models import AutonomyRule, ConversationState

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")

CANCEL_COMMANDS = {"cancelar", "cancela", "olvidalo"}
CONFIRM_COMMANDS = {"confirmo", "si", "s", "ok"}


@dataclass
class Action:
    type: str
    payload: dict[str, Any]


@dataclass
class AgentResult:
    reply_text: str
    actions_to_execute: list[Action] = field(default_factory=list)
    store_updates: list[dict[str, Any]] = field(default_factory=list)


def handle_incoming_message(
    chat_id: str,
    sender_id: str | None,
    text: str | None,
    sender_name: str | None,
    raw_payload: dict[str, Any],
) -> AgentResult:
    normalized = _normalize_text(text)
    folded = _fold_text(normalized) if normalized else None

    if not normalized:
        return AgentResult(reply_text="Recibi tu mensaje")

    with SessionLocal() as session:
        state = _get_or_create_state(session, chat_id)

        if folded and folded in CANCEL_COMMANDS:
            state.pending_action_json = None
            state.pending_question_json = None
            state.last_intent = "cancel"
            session.commit()
            return AgentResult(reply_text="Listo, cancelado.")

        if folded and state.pending_action_json and folded in CONFIRM_COMMANDS:
            result = _confirm_pending_action(session, state)
            if result:
                return result

        focus_result = _handle_focus_commands(session, state, folded)
        if focus_result:
            return focus_result

        if state.pending_question_json:
            pending_result = _handle_pending_question(session, state, normalized)
            if pending_result:
                return pending_result

        if state.pending_action_json and folded:
            return AgentResult(reply_text="Tenes un plan pendiente. Escribi confirmo o cancelar.")

        list_request = _parse_list_request(normalized)
        if list_request:
            return _handle_list_request(list_request)

        schedule_request = _parse_schedule_request(normalized)
        if schedule_request:
            return _handle_schedule_request(session, state, schedule_request)

    return AgentResult(reply_text="Recibi tu mensaje")


def _handle_schedule_request(
    session, state: ConversationState, request: dict[str, Any]
) -> AgentResult:
    title = request["title"]
    start_dt: datetime | None = request.get("start_dt")
    duration = request.get("duration_minutes")

    if start_dt is None:
        state.pending_question_json = {
            "type": "start_time",
            "title": title,
            "duration_minutes": duration,
        }
        state.last_intent = "calendar_schedule"
        session.commit()
        return AgentResult(reply_text="Para que dia y hora? (ej: manana 16)")

    if duration is None:
        state.pending_question_json = {
            "type": "duration_minutes",
            "title": title,
            "start_dt": start_dt.isoformat(),
        }
        state.last_intent = "calendar_schedule"
        session.commit()
        return AgentResult(reply_text="Cuanto dura? 30/60/90")

    calendar_tool = CalendarTool()
    if not calendar_tool.has_token():
        state.last_intent = "needs_auth"
        session.commit()
        return AgentResult(reply_text=_auth_message())

    end_dt = start_dt + timedelta(minutes=duration)
    try:
        if not calendar_tool.is_free(start_dt, end_dt):
            alternatives = _find_alternatives(calendar_tool, start_dt, duration)
            if not alternatives:
                return AgentResult(
                    reply_text="No hay disponibilidad en ese horario. Proba otro."
                )

            state.pending_question_json = {
                "type": "conflict_choice",
                "title": title,
                "duration_minutes": duration,
                "options": [
                    {
                        "start": alt.isoformat(),
                        "end": (alt + timedelta(minutes=duration)).isoformat(),
                    }
                    for alt in alternatives
                ],
            }
            state.last_intent = "calendar_schedule"
            session.commit()

            reply_lines = ["Hay conflicto. Opciones:"]
            for idx, alt in enumerate(alternatives, start=1):
                reply_lines.append(f"{idx}) {_format_datetime(alt)}")
            reply_lines.append("Responde 1 o 2.")
            return AgentResult(reply_text=" ".join(reply_lines))
    except CalendarNotAuthorized:
        state.last_intent = "needs_auth"
        session.commit()
        return AgentResult(reply_text=_auth_message())
    except OAuthConfigError:
        state.last_intent = "config_error"
        session.commit()
        return AgentResult(reply_text="Falta configurar Google Calendar.")

    plan_payload = {
        "type": "calendar_create",
        "payload": {
            "title": title,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "timezone": TIMEZONE.key,
        },
    }
    state.pending_action_json = plan_payload
    state.pending_question_json = None
    state.last_intent = "calendar_schedule"
    session.commit()

    return AgentResult(reply_text=_build_plan_text(plan_payload["payload"]))


def _handle_list_request(request: dict[str, Any]) -> AgentResult:
    day = request["day"]
    start_dt = datetime.combine(day, time(0, 0), tzinfo=TIMEZONE)
    end_dt = start_dt + timedelta(days=1)

    calendar_tool = CalendarTool()
    if not calendar_tool.has_token():
        return AgentResult(reply_text=_auth_message())

    try:
        events = calendar_tool.list_events(start_dt, end_dt)
    except CalendarNotAuthorized:
        return AgentResult(reply_text=_auth_message())
    except OAuthConfigError:
        return AgentResult(reply_text="Falta configurar Google Calendar.")

    if not events:
        return AgentResult(reply_text=f"No tenes eventos para {day.isoformat()}.")

    lines = [f"Eventos para {day.isoformat()}:"]
    for event in events:
        lines.append(_format_event_line(event))
    return AgentResult(reply_text=" ".join(lines))


def _handle_pending_question(
    session, state: ConversationState, normalized: str
) -> AgentResult | None:
    question = state.pending_question_json
    if not isinstance(question, dict):
        state.pending_question_json = None
        session.commit()
        return None

    q_type = question.get("type")
    if q_type == "duration_minutes":
        duration = _parse_int(normalized)
        if duration is None:
            return AgentResult(reply_text="Indica la duracion en minutos (30/60/90).")

        start_dt = _parse_iso_datetime(question.get("start_dt"))
        if start_dt is None:
            state.pending_question_json = None
            session.commit()
            return AgentResult(reply_text="Para que dia y hora?")

        request = {
            "title": question.get("title") or "Sin titulo",
            "start_dt": start_dt,
            "duration_minutes": duration,
        }
        state.pending_question_json = None
        session.commit()
        return _handle_schedule_request(session, state, request)

    if q_type == "start_time":
        start_dt = _parse_datetime(normalized)
        if start_dt is None:
            return AgentResult(reply_text="Para que dia y hora? (ej: manana 16)")

        duration = question.get("duration_minutes")
        if duration:
            request = {
                "title": question.get("title") or "Sin titulo",
                "start_dt": start_dt,
                "duration_minutes": duration,
            }
            state.pending_question_json = None
            session.commit()
            return _handle_schedule_request(session, state, request)

        state.pending_question_json = {
            "type": "duration_minutes",
            "title": question.get("title") or "Sin titulo",
            "start_dt": start_dt.isoformat(),
        }
        state.last_intent = "calendar_schedule"
        session.commit()
        return AgentResult(reply_text="Cuanto dura? 30/60/90")

    if q_type == "conflict_choice":
        choice = _parse_choice(normalized)
        options = question.get("options") or []
        if choice is None or choice >= len(options):
            return AgentResult(reply_text="Responde 1 o 2.")

        option = options[choice]
        plan_payload = {
            "type": "calendar_create",
            "payload": {
                "title": question.get("title") or "Sin titulo",
                "start": option.get("start"),
                "end": option.get("end"),
                "timezone": TIMEZONE.key,
            },
        }
        state.pending_question_json = None
        state.pending_action_json = plan_payload
        state.last_intent = "calendar_schedule"
        session.commit()
        return AgentResult(reply_text=_build_plan_text(plan_payload["payload"]))

    if q_type == "focus_hours":
        hours = _parse_int(normalized)
        if hours is None:
            return AgentResult(reply_text="Por cuantas horas?")
        _create_autonomy_rule(session, scope="global", mode="focus", hours=hours)
        state.pending_action_json = None
        state.pending_question_json = None
        state.last_intent = "focus_mode"
        session.commit()
        return AgentResult(reply_text=f"Modo foco activado por {hours} horas.")

    state.pending_question_json = None
    session.commit()
    return None


def _confirm_pending_action(session, state: ConversationState) -> AgentResult | None:
    pending = state.pending_action_json
    if not isinstance(pending, dict):
        state.pending_action_json = None
        session.commit()
        return None

    action_type = pending.get("type")
    if action_type != "calendar_create":
        state.pending_action_json = None
        session.commit()
        return None

    payload = pending.get("payload") or {}
    title = payload.get("title", "Sin titulo")
    start_dt = _parse_iso_datetime(payload.get("start"))
    end_dt = _parse_iso_datetime(payload.get("end"))
    if start_dt is None or end_dt is None:
        state.pending_action_json = None
        session.commit()
        return AgentResult(reply_text="No pude confirmar. Reintenta.")

    calendar_tool = CalendarTool()
    if not calendar_tool.has_token():
        state.last_intent = "needs_auth"
        session.commit()
        return AgentResult(reply_text=_auth_message())

    try:
        result = calendar_tool.create_event(title, start_dt, end_dt)
    except CalendarNotAuthorized:
        state.last_intent = "needs_auth"
        session.commit()
        return AgentResult(reply_text=_auth_message())
    except OAuthConfigError:
        state.last_intent = "config_error"
        session.commit()
        return AgentResult(reply_text="Falta configurar Google Calendar.")

    state.pending_action_json = None
    state.pending_question_json = None
    state.last_intent = "calendar_execute"
    session.commit()

    link = result.get("htmlLink")
    if link:
        return AgentResult(reply_text=f"Listo, evento creado. {link}")
    return AgentResult(reply_text="Listo, evento creado.")


def _handle_focus_commands(
    session, state: ConversationState, folded: str | None
) -> AgentResult | None:
    if not folded:
        return None

    if folded.startswith("modo foco") or folded.startswith("no me jodas"):
        hours = _parse_int(folded)
        if hours is None:
            state.pending_question_json = {"type": "focus_hours"}
            state.last_intent = "focus_mode"
            session.commit()
            return AgentResult(reply_text="Por cuantas horas?")

        _create_autonomy_rule(session, scope="global", mode="focus", hours=hours)
        state.pending_action_json = None
        state.pending_question_json = None
        state.last_intent = "focus_mode"
        session.commit()
        return AgentResult(reply_text=f"Modo foco activado por {hours} horas.")

    if "solo urgencias" in folded:
        _create_autonomy_rule(session, scope="global", mode="urgencies_only", hours=None)
        state.pending_action_json = None
        state.pending_question_json = None
        state.last_intent = "urgencies_only"
        session.commit()
        return AgentResult(reply_text="Listo, solo urgencias.")

    if folded in {"normal", "modo normal"}:
        _create_autonomy_rule(session, scope="global", mode="normal", hours=None)
        state.pending_action_json = None
        state.pending_question_json = None
        state.last_intent = "normal"
        session.commit()
        return AgentResult(reply_text="Modo normal activado.")

    return None


def _get_or_create_state(session, chat_id: str) -> ConversationState:
    state = session.get(ConversationState, chat_id)
    if state is None:
        state = ConversationState(chat_id=chat_id)
        session.add(state)
        session.flush()
    return state


def _create_autonomy_rule(session, scope: str, mode: str, hours: int | None) -> None:
    until_at = None
    if hours:
        until_at = datetime.now(timezone.utc) + timedelta(hours=hours)
    rule = AutonomyRule(scope=scope, mode=mode, until_at=until_at)
    session.add(rule)


def _parse_list_request(text: str) -> dict[str, Any] | None:
    folded = _fold_text(text)
    if "que tengo" not in folded and "que hay" not in folded:
        return None

    day = _parse_date(folded)
    if day is None:
        day = datetime.now(TIMEZONE).date()
    return {"day": day}


def _parse_schedule_request(text: str) -> dict[str, Any] | None:
    folded = _fold_text(text)
    if "agend" not in folded:
        return None

    title = _extract_title(text)
    start_dt = _parse_datetime(text)
    duration = _parse_duration_with_units(text)

    return {"title": title, "start_dt": start_dt, "duration_minutes": duration}


def _parse_datetime(text: str) -> datetime | None:
    folded = _fold_text(text)
    day = _parse_date(folded)
    if day is None:
        return None

    time_value = _parse_time(folded)
    if time_value is None:
        return None

    return datetime.combine(day, time_value, tzinfo=TIMEZONE)


def _parse_date(folded: str) -> date | None:
    now = datetime.now(TIMEZONE)
    if "manana" in folded:
        return (now + timedelta(days=1)).date()
    if "hoy" in folded:
        return now.date()

    match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", folded)
    if not match:
        return None

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_time(folded: str) -> time | None:
    cleaned = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", folded)
    for match in re.finditer(r"\b(\d{1,2})(?::(\d{2}))\b", cleaned):
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour=hour, minute=minute)

    for match in re.finditer(r"\b(\d{1,2})\b", cleaned):
        hour = int(match.group(1))
        if 0 <= hour <= 23:
            return time(hour=hour, minute=0)

    return None


def _parse_duration_with_units(text: str) -> int | None:
    folded = _fold_text(text)
    match = re.search(r"\b(\d{1,3})\s*(minutos|min|m)\b", folded)
    if not match:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"\b(\d{1,3})\b", text)
    if not match:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


def _parse_choice(text: str) -> int | None:
    match = re.search(r"\b([12])\b", text)
    if not match:
        return None
    return int(match.group(1)) - 1


def _extract_title(text: str) -> str:
    match = re.search(r"\bagend\w*\b\s*(?P<rest>.+)", text, flags=re.I)
    rest = match.group("rest") if match else text

    cleaned = re.sub(r"\b(hoy|manana)\b", "", rest, flags=re.I)
    cleaned = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", cleaned)
    cleaned = re.sub(r"\b\d{1,2}(:\d{2})?\b", "", cleaned)
    cleaned = re.sub(r"\b\d{1,3}\s*(minutos|min|m)\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bpor\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\ba\s+las\b", "", cleaned, flags=re.I)

    title = cleaned.strip()
    return title if title else "Sin titulo"


def _normalize_text(text: str | None) -> str | None:
    if not text:
        return None
    return text.strip()


def _fold_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower().strip()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _format_datetime(value: datetime) -> str:
    local_value = value.astimezone(TIMEZONE)
    return local_value.strftime("%Y-%m-%d %H:%M")


def _format_event_line(event: dict[str, Any]) -> str:
    summary = event.get("summary") or "Sin titulo"
    start_value = event.get("start")
    if start_value and "T" in start_value:
        parsed = _parse_iso_datetime(start_value)
        if parsed:
            return f"{parsed.astimezone(TIMEZONE).strftime('%H:%M')} {summary}"
    return f"Todo el dia: {summary}"


def _build_plan_text(payload: dict[str, Any]) -> str:
    title = payload.get("title", "Sin titulo")
    start_dt = _parse_iso_datetime(payload.get("start"))
    end_dt = _parse_iso_datetime(payload.get("end"))
    if start_dt and end_dt:
        duration = int((end_dt - start_dt).total_seconds() / 60)
        start_text = _format_datetime(start_dt)
        return (
            f"Voy a agendar '{title}' el {start_text} por {duration} min. "
            "Confirmas? (si/confirmo)"
        )
    return "Confirmas? (si/confirmo)"


def _find_alternatives(calendar_tool: CalendarTool, start_dt: datetime, duration: int) -> list[datetime]:
    alternatives: list[datetime] = []
    for offset in (30, 60, 90, 120):
        candidate = start_dt + timedelta(minutes=offset)
        end_dt = candidate + timedelta(minutes=duration)
        if calendar_tool.is_free(candidate, end_dt):
            alternatives.append(candidate)
        if len(alternatives) >= 2:
            break
    return alternatives


def _auth_message() -> str:
    base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    return f"Necesito autorizacion de Google Calendar. Abri {base_url}/auth/google/start"
