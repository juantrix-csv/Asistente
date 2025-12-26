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
from packages.assistant_requests import (
    NeedsDetector,
    RequestPolicy,
    count_requests_asked_today,
    get_active_request,
    get_open_requests,
    mark_request_answered,
    mark_request_asked,
    mark_request_dismissed,
    upsert_fact,
)
from packages.db.database import SessionLocal
from packages.db.models import (
    AssistantRequest,
    AutonomyRule,
    Contact,
    ConversationState,
    Habit,
    MemoryFact,
    SystemConfig,
    ToolRun,
)
from packages.llm.client import LlmClient, load_llm_config
from packages.llm.context_builder import ContextBuilder
from packages.llm.supervisor import Supervisor
from packages.llm.tools_registry import execute_tool, get_tool_scope, get_tool_names
from packages.memory.service import MemoryRetriever
from packages.memory.tagger import extract_tags
from packages.habits.engine import HabitEngine, get_or_create_coaching_profile
from packages.habits.parsing import parse_habit_text
from packages.relations.contact_handler import send_contact_reply
from packages.relations.message_tools import send_message_and_store
from packages.relations.policy import ContactPolicy
from packages.relations.trust import TrustEngine

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
            result = _confirm_pending_action(session, state, chat_id)
            if result:
                return result

        request_answer = _handle_assistant_request_answer(session, chat_id, normalized, folded)
        if request_answer:
            return request_answer

        focus_result = _handle_focus_commands(session, state, folded)
        if focus_result:
            return focus_result

        contact_result = _handle_contact_commands(session, folded)
        if contact_result:
            return contact_result

        habit_result = _handle_habit_commands(session, folded, normalized)
        if habit_result:
            return habit_result

        if state.pending_question_json:
            pending_result = _handle_pending_question(session, state, normalized)
            if pending_result:
                return pending_result

        if state.pending_action_json and folded:
            return AgentResult(reply_text="Tenes un plan pendiente. Escribi confirmo o cancelar.")

        list_request = _parse_list_request(normalized)
        if list_request and _calendar_auth_missing():
            state.last_intent = "needs_auth"
            reply = _handle_calendar_auth_needed(session, chat_id)
            return AgentResult(reply_text=reply)
        if list_request:
            return _handle_list_request(session, chat_id, list_request)

        schedule_request = _parse_schedule_request(normalized)

        tags = extract_tags(normalized)
        memory_result = _handle_memory_request(
            session, normalized, folded, tags, chat_id, schedule_request
        )
        if memory_result:
            return memory_result

        if schedule_request:
            if schedule_request.get("start_dt") and schedule_request.get("duration_minutes"):
                if _calendar_auth_missing():
                    state.last_intent = "needs_auth"
                    reply = _handle_calendar_auth_needed(session, chat_id)
                    return AgentResult(reply_text=reply)
            return _handle_schedule_request(session, state, schedule_request, chat_id)

        llm_result = _handle_llm_planner(session, state, normalized, chat_id)
        if llm_result:
            return llm_result

        request_prompt = _maybe_ask_request(session, state, chat_id, normalized)
        if request_prompt:
            return AgentResult(reply_text=request_prompt)

    return AgentResult(reply_text="Recibi tu mensaje")


def _handle_schedule_request(
    session, state: ConversationState, request: dict[str, Any], chat_id: str
) -> AgentResult:
    title = request["title"]
    start_dt: datetime | None = request.get("start_dt")
    duration = request.get("duration_minutes")
    location = request.get("location")

    if start_dt is None:
        state.pending_question_json = {
            "type": "start_time",
            "title": title,
            "duration_minutes": duration,
            "location": location,
            "chat_id": chat_id,
        }
        state.last_intent = "calendar_schedule"
        session.commit()
        reply = "Para que dia y hora? (ej: manana 16)"
        if location:
            reply = f"{reply} Voy a usar {location}."
        return AgentResult(reply_text=reply)

    if duration is None:
        state.pending_question_json = {
            "type": "duration_minutes",
            "title": title,
            "start_dt": start_dt.isoformat(),
            "location": location,
            "chat_id": chat_id,
        }
        state.last_intent = "calendar_schedule"
        session.commit()
        reply = "Cuanto dura? 30/60/90"
        if location:
            reply = f"{reply} Voy a usar {location}."
        return AgentResult(reply_text=reply)

    calendar_tool = CalendarTool()
    if not calendar_tool.has_token():
        state.last_intent = "needs_auth"
        session.commit()
        return AgentResult(reply_text=_handle_calendar_auth_needed(session, chat_id))

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
                "chat_id": chat_id,
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
        return AgentResult(reply_text=_handle_calendar_auth_needed(session, chat_id))
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
            "location": location,
        },
    }
    state.pending_action_json = plan_payload
    state.pending_question_json = None
    state.last_intent = "calendar_schedule"
    session.commit()

    return AgentResult(reply_text=_build_plan_text(plan_payload["payload"]))


def _handle_list_request(session, chat_id: str, request: dict[str, Any]) -> AgentResult:
    day = request["day"]
    start_dt = datetime.combine(day, time(0, 0), tzinfo=TIMEZONE)
    end_dt = start_dt + timedelta(days=1)

    calendar_tool = CalendarTool()
    if not calendar_tool.has_token():
        return AgentResult(reply_text=_handle_calendar_auth_needed(session, chat_id))

    try:
        events = calendar_tool.list_events(start_dt, end_dt)
    except CalendarNotAuthorized:
        return AgentResult(reply_text=_handle_calendar_auth_needed(session, chat_id))
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
            "location": question.get("location"),
        }
        state.pending_question_json = None
        session.commit()
        return _handle_schedule_request(session, state, request, question.get("chat_id") or "")

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
                "location": question.get("location"),
            }
            state.pending_question_json = None
            session.commit()
            return _handle_schedule_request(session, state, request, question.get("chat_id") or "")

        state.pending_question_json = {
            "type": "duration_minutes",
            "title": question.get("title") or "Sin titulo",
            "start_dt": start_dt.isoformat(),
            "location": question.get("location"),
            "chat_id": question.get("chat_id"),
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
                "location": question.get("location"),
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

    if q_type == "autonomy_hours":
        hours = _parse_int(normalized)
        if hours is None:
            return AgentResult(reply_text="Por cuantas horas?")
        scope = question.get("scope") or "calendar_create"
        _create_autonomy_rule(session, scope=scope, mode="on", hours=hours)
        state.pending_action_json = None
        state.pending_question_json = None
        state.last_intent = "autonomy_on"
        session.commit()
        return AgentResult(reply_text=f"Autonomia activada para {scope} por {hours} horas.")

    state.pending_question_json = None
    session.commit()
    return None


def _handle_assistant_request_answer(
    session, chat_id: str, normalized: str, folded: str | None
) -> AgentResult | None:
    if not folded:
        return None

    request = get_active_request(session, chat_id)
    if request is None:
        return None

    now_local = datetime.now(TIMEZONE)
    if folded in {"omitir", "despues"}:
        mark_request_dismissed(session, request, now_local)
        session.commit()
        return AgentResult(reply_text="Listo, lo dejo para mas tarde.")

    if request.request_type == "authorize_calendar":
        mark_request_answered(session, request, now_local)
        session.commit()
        return AgentResult(reply_text=_auth_message())

    if request.key == "preferred_event_duration_minutes":
        minutes = _parse_int(normalized)
        if minutes is None:
            return AgentResult(reply_text="Necesito un numero de minutos (30/60/90).")
        upsert_fact(
            session,
            subject="user",
            key="preferred_event_duration_minutes",
            value=str(minutes),
            confidence=80,
            source_ref=f"request:{request.id}",
        )
        mark_request_answered(session, request, now_local)
        session.commit()
        return AgentResult(reply_text="Listo, lo guarde.")

    if request.key == "default_barbershop":
        upsert_fact(
            session,
            subject="user",
            key="default_barbershop",
            value=normalized,
            confidence=80,
            source_ref=f"request:{request.id}",
        )
        mark_request_answered(session, request, now_local)
        session.commit()
        return AgentResult(reply_text="Listo, lo guarde.")

    if request.key == "diet_store_address":
        upsert_fact(
            session,
            subject="user",
            key="diet_store_address",
            value=normalized,
            confidence=70,
            source_ref=f"request:{request.id}",
        )
        mark_request_answered(session, request, now_local)
        session.commit()
        return AgentResult(reply_text="Listo, lo guarde.")

    if request.key == "user_chat_id":
        upsert_fact(
            session,
            subject="user",
            key="user_chat_id",
            value=chat_id,
            confidence=90,
            source_ref=f"request:{request.id}",
        )
        mark_request_answered(session, request, now_local)
        session.commit()
        return AgentResult(reply_text="Listo, lo guarde.")

    mark_request_answered(session, request, now_local)
    session.commit()
    return AgentResult(reply_text="Listo, lo guarde.")


def _confirm_pending_action(
    session, state: ConversationState, chat_id: str
) -> AgentResult | None:
    pending = state.pending_action_json
    if not isinstance(pending, dict):
        state.pending_action_json = None
        session.commit()
        return None

    action_type = pending.get("type")
    if action_type == "message_send":
        payload = pending.get("payload") or {}
        contact_chat_id = payload.get("chat_id")
        thread_id = payload.get("thread_id")
        text = payload.get("text")
        if not contact_chat_id or not text:
            state.pending_action_json = None
            session.commit()
            return AgentResult(reply_text="No pude enviar el mensaje. Reintenta.")

        success = False
        if thread_id:
            outbound_kind = "question" if "?" in text else "info"
            success = send_contact_reply(thread_id, contact_chat_id, text, outbound_kind)
        else:
            _message_id, _response, error = send_message_and_store(contact_chat_id, text)
            success = error is None
        _log_tool_run(
            session,
            tool_name="message.send",
            status="success" if success else "error",
            input_json={"chat_id": contact_chat_id, "text": text},
            output_json={"sent": success},
            decision_source="user",
            requested_by="user",
            risk_level="medium",
            autonomy_snapshot={},
        )
        state.pending_action_json = None
        state.pending_question_json = None
        state.last_intent = "message_send"
        session.commit()
        if success:
            return AgentResult(reply_text="Listo, mensaje enviado.")
        return AgentResult(reply_text="No pude enviar el mensaje.")

    if action_type != "calendar_create":
        state.pending_action_json = None
        session.commit()
        return None

    payload = pending.get("payload") or {}
    title = payload.get("title", "Sin titulo")
    start_dt = _parse_iso_datetime(payload.get("start"))
    end_dt = _parse_iso_datetime(payload.get("end"))
    location = payload.get("location")
    notes = payload.get("notes")
    if start_dt is None or end_dt is None:
        state.pending_action_json = None
        session.commit()
        return AgentResult(reply_text="No pude confirmar. Reintenta.")

    calendar_tool = CalendarTool()
    if not calendar_tool.has_token():
        state.last_intent = "needs_auth"
        session.commit()
        return AgentResult(reply_text=_handle_calendar_auth_needed(session, chat_id))

    try:
        result = calendar_tool.create_event(title, start_dt, end_dt, location=location, notes=notes)
    except CalendarNotAuthorized:
        state.last_intent = "needs_auth"
        session.commit()
        return AgentResult(reply_text=_handle_calendar_auth_needed(session, chat_id))
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

    if folded.startswith("autonomia on"):
        scope = _parse_autonomy_scope(folded)
        if scope is None:
            return AgentResult(reply_text="Para que scope? calendario/mensajes/tareas")
        hours = _parse_int(folded)
        if hours is None:
            state.pending_question_json = {"type": "autonomy_hours", "scope": scope}
            state.last_intent = "autonomy_on"
            session.commit()
            return AgentResult(reply_text="Por cuantas horas?")
        _create_autonomy_rule(session, scope=scope, mode="on", hours=hours)
        state.pending_action_json = None
        state.pending_question_json = None
        state.last_intent = "autonomy_on"
        session.commit()
        return AgentResult(reply_text=f"Autonomia activada para {scope} por {hours} horas.")

    if folded.startswith("autonomia off"):
        scope = _parse_autonomy_scope(folded)
        if scope:
            _create_autonomy_rule(session, scope=scope, mode="off", hours=None)
            reply = f"Autonomia desactivada para {scope}."
        else:
            for scope_name in ("calendar_create", "message_reply", "tasks_manage"):
                _create_autonomy_rule(session, scope=scope_name, mode="off", hours=None)
            reply = "Autonomia desactivada para todos los scopes."
        state.pending_action_json = None
        state.pending_question_json = None
        state.last_intent = "autonomy_off"
        session.commit()
        return AgentResult(reply_text=reply)

    if "status autonomia" in folded:
        reply = _build_autonomy_status(session)
        state.pending_action_json = None
        state.pending_question_json = None
        state.last_intent = "autonomy_status"
        session.commit()
        return AgentResult(reply_text=reply)

    if "status proactivo" in folded:
        reply = _build_proactive_status(session)
        state.pending_action_json = None
        state.pending_question_json = None
        state.last_intent = "proactive_status"
        session.commit()
        return AgentResult(reply_text=reply)

    if folded.startswith("modo foco") or (
        folded.startswith("no me jodas") and "habitos" not in folded
    ):
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
    location = payload.get("location")
    if start_dt and end_dt:
        duration = int((end_dt - start_dt).total_seconds() / 60)
        start_text = _format_datetime(start_dt)
        location_text = f" en {location}" if location else ""
        return (
            f"Voy a agendar '{title}' el {start_text}{location_text} por {duration} min. "
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


def _handle_memory_request(
    session,
    normalized: str,
    folded: str | None,
    tags: list[str],
    chat_id: str,
    schedule_request: dict[str, Any] | None,
) -> AgentResult | None:
    if not folded or not tags:
        return None

    if "de siempre" in folded or "lugar de siempre" in folded:
        fact = _find_fact_for_tags(session, tags)
        if fact:
            if schedule_request is not None:
                schedule_request["location"] = fact.value
                return None
            return AgentResult(
                reply_text=(
                    f"Tengo registrado que el lugar de siempre es {fact.value}. "
                    "Queres que lo use?"
                )
            )
        now_local = datetime.now(TIMEZONE)
        detector = NeedsDetector(session)
        detector.scan(chat_id, now_local, user_text=normalized, intent_hint=None)
        request = _get_request_by_key(session, "missing_default_contact", "default_barbershop", chat_id)
        prompt = _ask_request_if_allowed(session, request, now_local)
        if prompt:
            return AgentResult(reply_text=prompt)
        session.commit()
        label = _tag_label(tags[0])
        return AgentResult(
            reply_text=f"Ok, cuando quieras decime el {label} de siempre."
        )

    if any(keyword in folded for keyword in ("recordas", "acordas", "tenes info", "tenes datos")):
        retriever = MemoryRetriever(session)
        chunks = retriever.retrieve(normalized, tags=tags, chat_id=chat_id, limit=5)
        if not chunks:
            return AgentResult(reply_text="No tengo info registrada sobre eso.")
        summary = " ".join(_format_chunk_summary(chunks))
        return AgentResult(reply_text=f"Tengo registrado: {summary}")

    return None


def _handle_contact_commands(
    session,
    folded: str | None,
) -> AgentResult | None:
    if not folded:
        return None

    match = re.match(r"^contacto\s+(.+?)\s+es\s+(proveedor|cliente|amigo|inner)\b", folded)
    if match:
        identifier = match.group(1).strip()
        label = match.group(2).strip()
        contact = _find_contact(session, identifier)
        if contact is None:
            return AgentResult(reply_text="No encontre ese contacto. Usa el chat_id.")
        TrustEngine().apply_label(contact, label)
        session.commit()
        return AgentResult(reply_text=f"Listo, {identifier} ahora es {label}.")

    match = re.match(r"^subi confianza\s+(.+?)\s+a\s+(\d{1,3})\b", folded)
    if match:
        identifier = match.group(1).strip()
        level = int(match.group(2))
        contact = _find_contact(session, identifier)
        if contact is None:
            return AgentResult(reply_text="No encontre ese contacto. Usa el chat_id.")
        TrustEngine().set_level(contact, level)
        session.commit()
        return AgentResult(reply_text=f"Confianza actualizada para {identifier}.")

    match = re.match(r"^auto[-\s]?reply\s+on\s+(.+)$", folded)
    if match:
        identifier = match.group(1).strip()
        contact = _find_contact(session, identifier)
        if contact is None:
            return AgentResult(reply_text="No encontre ese contacto. Usa el chat_id.")
        TrustEngine().set_auto_reply(contact, True)
        session.commit()
        return AgentResult(reply_text=f"Auto-reply activado para {identifier}.")

    match = re.match(r"^auto[-\s]?reply\s+off\s+(.+)$", folded)
    if match:
        identifier = match.group(1).strip()
        contact = _find_contact(session, identifier)
        if contact is None:
            return AgentResult(reply_text="No encontre ese contacto. Usa el chat_id.")
        TrustEngine().set_auto_reply(contact, False)
        session.commit()
        return AgentResult(reply_text=f"Auto-reply desactivado para {identifier}.")

    return None


def _handle_habit_commands(
    session,
    folded: str | None,
    normalized: str,
) -> AgentResult | None:
    if not folded:
        return None

    if folded == "mis habitos":
        engine = HabitEngine(session)
        habits = engine.list_habits(active_only=True)
        if not habits:
            return AgentResult(reply_text="No tenes habitos activos.")
        lines = ["Habitos activos:"]
        for habit in habits:
            lines.append(f"- {habit.name} ({_format_habit_schedule(habit)})")
        return AgentResult(reply_text="\n".join(lines))

    if folded == "estado habitos":
        engine = HabitEngine(session)
        summary = engine.daily_summary(datetime.now(TIMEZONE))
        done = ", ".join(summary["done"]) or "-"
        pending = ", ".join(summary["pending"]) or "-"
        streaks = ", ".join(summary["streaks"]) or "-"
        reply = (
            f"Hoy:\n- Cumplidos: {done}\n- Pendientes: {pending}\n- Rachas: {streaks}"
        )
        return AgentResult(reply_text=reply)

    if folded == "resumen habitos":
        engine = HabitEngine(session)
        lines = engine.weekly_report(datetime.now(TIMEZONE))
        if not lines:
            return AgentResult(reply_text="No tenes habitos registrados.")
        reply_lines = ["Resumen semanal:"]
        reply_lines.extend(f"- {line}" for line in lines)
        return AgentResult(reply_text="\n".join(reply_lines))

    if folded == "subi intensidad":
        profile = get_or_create_coaching_profile(session)
        profile.intensity = _shift_intensity(profile.intensity, direction="up")
        session.commit()
        return AgentResult(reply_text=f"Intensidad actual: {profile.intensity}.")

    if folded == "baja intensidad":
        profile = get_or_create_coaching_profile(session)
        profile.intensity = _shift_intensity(profile.intensity, direction="down")
        session.commit()
        return AgentResult(reply_text=f"Intensidad actual: {profile.intensity}.")

    if folded == "no me jodas con habitos hoy":
        end_of_day = datetime.combine(datetime.now(TIMEZONE).date(), time(23, 59), tzinfo=TIMEZONE)
        session.add(
            AutonomyRule(scope="habits", mode="off", until_at=end_of_day.astimezone(timezone.utc))
        )
        session.commit()
        return AgentResult(reply_text="Ok, hoy no te voy a insistir con habitos.")

    if folded.startswith("crear habito "):
        raw_name = _extract_after_words(normalized, 2)
        if not raw_name:
            return AgentResult(reply_text="Decime el nombre del habito.")
        schedule_info = parse_habit_text(raw_name)
        name = _clean_habit_name(raw_name)
        if not name:
            return AgentResult(reply_text="Decime el nombre del habito.")
        engine = HabitEngine(session)
        existing = engine.find_habits_by_name(name, active_only=False)
        if any(habit.name.lower() == name.lower() for habit in existing):
            return AgentResult(reply_text="Ese habito ya existe.")
        config = _get_or_create_config(session)
        min_version = _default_min_version(name)
        habit = engine.create_habit(
            name=name,
            description=None,
            schedule_type=str(schedule_info["schedule_type"]),
            target_per_week=schedule_info.get("target_per_week"),
            days_of_week=schedule_info.get("days_of_week"),
            window_start=config.strong_window_start,
            window_end=config.strong_window_end,
            min_version_text=min_version,
            priority=3,
            active=True,
        )
        session.commit()
        return AgentResult(reply_text=f"Listo, cree el habito: {habit.name}.")

    if folded.startswith("desactivar habito "):
        name = _extract_after_words(normalized, 2)
        habit, error = _resolve_habit(session, name)
        if error:
            return AgentResult(reply_text=error)
        habit.active = False
        session.commit()
        return AgentResult(reply_text=f"Habito desactivado: {habit.name}.")

    if folded.startswith("hecho "):
        name = _extract_after_words(normalized, 1)
        habit, error = _resolve_habit(session, name)
        if error:
            return AgentResult(reply_text=error)
        engine = HabitEngine(session)
        engine.log_done(habit.id, now=datetime.now(TIMEZONE))
        streak = engine.current_streak(habit.id, datetime.now(TIMEZONE))
        session.commit()
        return AgentResult(reply_text=f"Listo, registre {habit.name}. Racha: {streak}d.")

    if folded.startswith("no hoy "):
        name = _extract_after_words(normalized, 2)
        habit, error = _resolve_habit(session, name)
        if error:
            return AgentResult(reply_text=error)
        engine = HabitEngine(session)
        engine.log_skip(habit.id, now=datetime.now(TIMEZONE))
        session.commit()
        return AgentResult(reply_text=f"Ok, marcado como no hoy: {habit.name}.")

    return None


def _resolve_habit(session, name: str | None) -> tuple[Habit | None, str | None]:
    if not name:
        return None, "Decime el habito."
    engine = HabitEngine(session)
    matches = engine.find_habits_by_name(name)
    if not matches:
        return None, "No encontre ese habito."
    if len(matches) > 1:
        names = ", ".join(habit.name for habit in matches[:5])
        return None, f"Hay varios: {names}. Decime cual."
    return matches[0], None


def _extract_after_words(text: str, words: int) -> str | None:
    parts = text.split()
    if len(parts) <= words:
        return None
    return " ".join(parts[words:]).strip()


def _format_habit_schedule(habit) -> str:
    if habit.schedule_type == "weekly" and habit.target_per_week:
        return f"{habit.target_per_week} por semana"
    if habit.schedule_type == "scheduled" and habit.days_of_week:
        labels = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]
        days = ",".join(labels[idx] for idx in habit.days_of_week if idx < len(labels))
        return f"{days}"
    return "diario"


def _default_min_version(name: str) -> str:
    return f"{name} 5 min"


def _clean_habit_name(text: str) -> str:
    cleaned = re.sub(r"\b\d+\s*veces\s*por\s*semana\b", "", text, flags=re.I)
    cleaned = re.sub(
        r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo|lun|mar|mie|jue|vie|sab|dom)\b",
        "",
        cleaned,
        flags=re.I,
    )
    return " ".join(cleaned.split()).strip()


def _shift_intensity(value: str, direction: str) -> str:
    levels = ["low", "medium", "high"]
    current = value if value in levels else "medium"
    idx = levels.index(current)
    if direction == "up" and idx < len(levels) - 1:
        return levels[idx + 1]
    if direction == "down" and idx > 0:
        return levels[idx - 1]
    return current


def _find_contact(session, identifier: str) -> Contact | None:
    if "@" in identifier:
        return session.query(Contact).filter_by(chat_id=identifier).one_or_none()

    matches = (
        session.query(Contact)
        .filter(Contact.display_name.ilike(f"%{identifier}%"))
        .all()
    )
    if len(matches) == 1:
        return matches[0]
    return None


def _calendar_auth_missing() -> bool:
    try:
        return not CalendarTool().has_token()
    except Exception:
        return True


def _handle_calendar_auth_needed(session, chat_id: str) -> str:
    now_local = datetime.now(TIMEZONE)
    detector = NeedsDetector(session)
    detector.scan(chat_id, now_local, user_text="calendario", intent_hint={"calendar_intent": True})
    request = _get_request_by_key(session, "authorize_calendar", "calendar_auth", chat_id)
    prompt = _ask_request_if_allowed(session, request, now_local)
    if prompt:
        return prompt
    session.commit()
    return _auth_message()


def _maybe_ask_request(
    session,
    state: ConversationState,
    chat_id: str,
    normalized: str,
) -> str | None:
    if state.pending_action_json or state.pending_question_json:
        return None
    if get_active_request(session, chat_id):
        return None
    if _should_skip_request_prompt(normalized):
        now_local = datetime.now(TIMEZONE)
        detector = NeedsDetector(session)
        detector.scan(chat_id, now_local, user_text=normalized, intent_hint=None)
        session.commit()
        return None

    now_local = datetime.now(TIMEZONE)
    detector = NeedsDetector(session)
    detector.scan(chat_id, now_local, user_text=normalized, intent_hint=None)

    open_requests = get_open_requests(session, chat_id, limit=5)
    for request in open_requests:
        prompt = _ask_request_if_allowed(session, request, now_local)
        if prompt:
            return prompt

    session.commit()
    return None


def _should_skip_request_prompt(text: str) -> bool:
    folded = _fold_text(text)
    if not folded:
        return True
    greetings = {"hola", "buenas", "buen dia", "buenas tardes", "buenas noches", "ok"}
    if folded in greetings:
        return True
    return len(folded.split()) <= 1


def _ask_request_if_allowed(
    session, request, now_local: datetime
) -> str | None:
    if request is None:
        return None

    config = _get_or_create_config(session)
    autonomy_mode, _ = _get_autonomy_mode(session)
    day_start = datetime.combine(now_local.date(), time(0, 0), tzinfo=TIMEZONE)
    day_end = day_start + timedelta(days=1)
    asked_today = count_requests_asked_today(session, day_start, day_end)
    policy = RequestPolicy()
    if policy.should_ask(request, now_local, autonomy_mode, config, asked_today):
        mark_request_asked(session, request, now_local)
        session.commit()
        return request.prompt
    return None


def _get_request_by_key(session, request_type: str, key: str, chat_id: str):
    dedupe_key = f"{request_type}:{key}:{chat_id}"
    return session.query(AssistantRequest).filter_by(dedupe_key=dedupe_key).one_or_none()


def _find_fact_for_tags(session, tags: list[str]) -> MemoryFact | None:
    for tag in tags:
        if tag == "peluqueria":
            fact = (
                session.query(MemoryFact)
                .filter(
                    MemoryFact.subject == "user",
                    MemoryFact.key == "default_barbershop",
                    MemoryFact.confidence >= 70,
                )
                .one_or_none()
            )
            if fact:
                return fact
        for key in (f"{tag}_default", f"{tag}_lugar"):
            fact = (
                session.query(MemoryFact)
                .filter(
                    MemoryFact.subject == "user",
                    MemoryFact.key == key,
                    MemoryFact.confidence >= 70,
                )
                .one_or_none()
            )
            if fact:
                return fact
    return None


def _tag_label(tag: str) -> str:
    labels = {
        "peluqueria": "peluqueria",
        "fletes": "servicio de fletes",
        "camionetas": "camioneta",
        "ascend": "dietetica",
        "agenda": "agenda",
    }
    return labels.get(tag, tag)


def _format_chunk_summary(chunks) -> list[str]:
    summaries: list[str] = []
    for chunk in chunks:
        content = chunk.content.strip().replace("\n", " ")
        if len(content) > 120:
            content = content[:117] + "..."
        summaries.append(f"[{chunk.source_type}] {content}")
    return summaries


def _handle_llm_planner(
    session,
    state: ConversationState,
    user_text: str,
    chat_id: str,
) -> AgentResult | None:
    if not _should_use_llm(user_text):
        return None
    context = ContextBuilder(session).build(chat_id, user_text, intent_hint=None)
    config = _get_or_create_config(session)
    llm_client = LlmClient(load_llm_config(config))
    planner_output = llm_client.generate_structured(
        _build_llm_system_prompt(),
        user_text,
        context.prompt,
    )
    state.last_intent = planner_output.intent

    decision = Supervisor(
        context.autonomy_snapshot,
        context.evidence_keys,
        contact_policy=ContactPolicy(session),
    ).evaluate(planner_output, chat_id)

    if decision.requires_confirmation and decision.action:
        action = decision.action
        if action.tool == "calendar.create_event":
            payload = {
                "title": action.input.get("title"),
                "start": action.input.get("start"),
                "end": action.input.get("end"),
                "location": action.input.get("location"),
                "notes": action.input.get("notes"),
                "timezone": TIMEZONE.key,
            }
            state.pending_action_json = {"type": "calendar_create", "payload": payload}
            state.pending_question_json = None
            state.last_intent = "llm_plan"
            session.commit()
        if action.tool == "message.send":
            state.pending_action_json = {"type": "message_send", "payload": action.input}
            state.pending_question_json = None
            state.last_intent = "llm_plan"
            session.commit()
        return AgentResult(reply_text=decision.reply)

    if decision.action and not decision.requires_confirmation:
        action = decision.action
        tool_scope = get_tool_scope(action.tool) or "unknown"
        audit_context = {
            "decision_source": "supervisor",
            "requested_by": "llm",
            "risk_level": action.risk_level,
            "autonomy_mode_snapshot": context.autonomy_snapshot,
        }
        calendar_tool = CalendarTool(log_runs=False, audit_context=audit_context)
        thread_id = action.input.get("thread_id")
        message_sender = lambda dest_chat_id, text: (
            {"sent": send_contact_reply(thread_id, dest_chat_id, text, "info")}
            if thread_id
            else _send_and_return(dest_chat_id, text)
        )
        status = "success"
        output_json: dict[str, Any] | list = {}
        try:
            output_json = execute_tool(
                action.tool,
                action.input,
                calendar_tool=calendar_tool,
                message_sender=message_sender,
            )
        except Exception as exc:
            status = "error"
            output_json = {"error": exc.__class__.__name__}

        _log_tool_run(
            session,
            tool_name=action.tool,
            status=status,
            input_json=action.input,
            output_json=output_json,
            decision_source="supervisor",
            requested_by="llm",
            risk_level=action.risk_level,
            autonomy_snapshot=context.autonomy_snapshot,
        )

        reply = decision.reply or "Listo."
        if status != "success":
            reply = "No pude completar la accion."
        if action.tool == "calendar.create_event" and isinstance(output_json, dict):
            link = output_json.get("htmlLink")
            if link:
                reply = f"{reply} {link}"
        session.commit()
        return AgentResult(reply_text=reply)

    if decision.reply:
        session.commit()
        return AgentResult(reply_text=decision.reply)
    return None


def _send_and_return(chat_id: str, text: str) -> dict[str, Any]:
    message_id, response, error = send_message_and_store(chat_id, text)
    if error:
        return {"error": error}
    if response is None:
        return {"message_id": message_id}
    return response


def _should_use_llm(text: str) -> bool:
    folded = _fold_text(text)
    if not folded:
        return False
    greetings = {"hola", "buenas", "buen dia", "buenas tardes", "buenas noches"}
    if folded in greetings:
        return False
    if len(folded.split()) <= 1:
        return False
    keywords = (
        "agend",
        "agenda",
        "crear",
        "evento",
        "calendario",
        "recorda",
        "recordar",
        "turno",
        "necesito",
        "queres",
        "pod",
    )
    return any(keyword in folded for keyword in keywords)


def _log_tool_run(
    session,
    tool_name: str,
    status: str,
    input_json: dict[str, Any] | list,
    output_json: dict[str, Any] | list,
    decision_source: str,
    requested_by: str,
    risk_level: str,
    autonomy_snapshot: dict,
) -> None:
    run = ToolRun(
        tool_name=tool_name,
        status=status,
        input_json=input_json,
        output_json=output_json,
        decision_source=decision_source,
        requested_by=requested_by,
        risk_level=risk_level,
        autonomy_mode_snapshot=autonomy_snapshot,
    )
    session.add(run)
    session.commit()


def _build_llm_system_prompt() -> str:
    tool_list = ", ".join(sorted(get_tool_names()))
    return (
        "Sos un planner que responde SOLO JSON estricto. "
        "No agregues texto extra.\n"
        f"Herramientas permitidas: {tool_list}.\n"
        "Schema:\n"
        "{"
        "\"intent\": \"...\", "
        "\"reply\": \"...\", "
        "\"questions\": [\"...\"] , "
        "\"actions\": [{\"tool\":\"...\",\"input\":{},\"risk_level\":\"low|medium|high\",\"rationale\":\"...\",\"requires_confirmation\":false}], "
        "\"evidence_needed\": [\"...\"]"
        "}\n"
        "Reglas: max 1 pregunta, max 3 acciones. Usa evidencia si es necesaria."
    )


def _build_proactive_status(session) -> str:
    config = _get_or_create_config(session)
    mode, until_at = _get_autonomy_mode(session)
    mode_label = {
        "normal": "normal",
        "focus": "foco",
        "urgencies_only": "solo urgencias",
    }.get(mode, mode)

    parts = [f"Modo proactivo: {mode_label}.", f"Limite diario: {config.daily_proactive_limit}."]
    if mode == "focus" and until_at:
        remaining = until_at - datetime.now(timezone.utc)
        if remaining.total_seconds() > 0:
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            parts.append(f"Foco restante: {hours}h {minutes}m.")
    return " ".join(parts)


def _build_autonomy_status(session) -> str:
    now_utc = datetime.now(timezone.utc)
    scopes = ["calendar_create", "message_reply", "tasks_manage"]
    lines = []
    for scope in scopes:
        rule = (
            session.query(AutonomyRule)
            .filter(AutonomyRule.scope == scope)
            .order_by(AutonomyRule.created_at.desc())
            .first()
        )
        if rule and rule.until_at and rule.until_at < now_utc:
            status = "off"
            remaining = None
        elif rule:
            status = rule.mode
            remaining = rule.until_at
        else:
            status = "off"
            remaining = None
        if remaining:
            delta = remaining - now_utc
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            lines.append(f"{scope}: {status} ({hours}h {minutes}m)")
        else:
            lines.append(f"{scope}: {status}")
    return "Autonomia: " + ", ".join(lines)


def _parse_autonomy_scope(folded: str) -> str | None:
    if "calendario" in folded:
        return "calendar_create"
    if "mensaje" in folded or "mensajes" in folded:
        return "message_reply"
    if "tarea" in folded or "tareas" in folded:
        return "tasks_manage"
    return None


def _get_or_create_config(session) -> SystemConfig:
    config = session.query(SystemConfig).order_by(SystemConfig.id.asc()).first()
    if config:
        return config
    config = SystemConfig(
        quiet_hours_start=time(0, 0),
        quiet_hours_end=time(9, 30),
        strong_window_start=time(11, 0),
        strong_window_end=time(19, 0),
        daily_proactive_limit=5,
        maybe_cooldown_minutes=240,
        urgent_threshold=80,
        maybe_threshold=50,
        llm_provider="ollama",
        llm_base_url=os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
        llm_model_name="qwen2.5:7b-instruct-q4",
        llm_temperature=0.3,
        llm_max_tokens=512,
        llm_json_mode=True,
    )
    session.add(config)
    session.commit()
    return config


def _get_autonomy_mode(session) -> tuple[str, datetime | None]:
    rules = (
        session.query(AutonomyRule)
        .filter(AutonomyRule.scope == "global")
        .order_by(AutonomyRule.created_at.desc())
        .all()
    )
    now_utc = datetime.now(timezone.utc)
    for rule in rules:
        if rule.until_at and rule.until_at < now_utc:
            continue
        return rule.mode, rule.until_at
    return "normal", None
