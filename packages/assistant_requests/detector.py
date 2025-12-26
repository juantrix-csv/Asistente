from __future__ import annotations

from datetime import datetime
import os
import re
import unicodedata
from typing import Any

from packages.agent_core.tools.calendar_tool import CalendarTool
from packages.db.models import AssistantRequest, MemoryFact, MessageRaw
from packages.assistant_requests.service import create_or_reopen_request, mark_request_answered


class NeedsDetector:
    def __init__(self, session) -> None:
        self.session = session

    def scan(
        self,
        chat_id: str,
        now: datetime,
        user_text: str | None = None,
        intent_hint: dict[str, Any] | None = None,
    ) -> list[AssistantRequest]:
        folded = _fold_text(user_text or "")
        requests: list[AssistantRequest] = []

        calendar_intent = _is_calendar_intent(folded, intent_hint)
        if calendar_intent:
            requests.extend(self._rule_calendar_auth(chat_id, now))

        if _mentions_peluqueria_de_siempre(folded):
            request = self._rule_default_barbershop(chat_id, now)
            if request:
                requests.append(request)

        if calendar_intent:
            request = self._rule_preferred_duration(chat_id, now)
            if request:
                requests.append(request)

        if _mentions_dietetica_for_schedule(folded):
            request = self._rule_dietetica_address(chat_id, now)
            if request:
                requests.append(request)

        request = self._rule_missing_chat_id(chat_id, now)
        if request:
            requests.append(request)

        return requests

    def _rule_calendar_auth(self, chat_id: str, now: datetime) -> list[AssistantRequest]:
        tool = CalendarTool()
        if tool.has_token():
            self._close_request_if_exists("authorize_calendar", "calendar_auth", chat_id, now)
            return []

        prompt = _build_calendar_auth_prompt()
        request = create_or_reopen_request(
            self.session,
            request_type="authorize_calendar",
            key="calendar_auth",
            prompt=prompt,
            context={"chat_id": chat_id},
            priority=90,
            now=now,
            reopen_if_answered=True,
        )
        return [request]

    def _rule_default_barbershop(self, chat_id: str, now: datetime) -> AssistantRequest | None:
        if _has_fact(self.session, "default_barbershop"):
            self._close_request_if_exists(
                "missing_default_contact", "default_barbershop", chat_id, now
            )
            return None
        prompt = (
            "Para ayudarte con la peluqueria de siempre, me falta el nombre o numero. "
            "Cual es? (podes responder 'omitir')"
        )
        return create_or_reopen_request(
            self.session,
            request_type="missing_default_contact",
            key="default_barbershop",
            prompt=prompt,
            context={"chat_id": chat_id},
            priority=75,
            now=now,
        )

    def _rule_preferred_duration(self, chat_id: str, now: datetime) -> AssistantRequest | None:
        if _has_fact(self.session, "preferred_event_duration_minutes"):
            self._close_request_if_exists(
                "missing_preference", "preferred_event_duration_minutes", chat_id, now
            )
            return None

        duration_prompts = (
            self.session.query(MessageRaw)
            .filter(
                MessageRaw.chat_id == chat_id,
                MessageRaw.direction == "outbound",
                MessageRaw.body.ilike("%Cuanto dura%"),
            )
            .count()
        )
        if duration_prompts < 3:
            return None

        prompt = (
            "Para agilizar tus agendas, cual es tu duracion preferida en minutos? "
            "(30/60/90). (podes responder 'omitir')"
        )
        return create_or_reopen_request(
            self.session,
            request_type="missing_preference",
            key="preferred_event_duration_minutes",
            prompt=prompt,
            context={"chat_id": chat_id},
            priority=60,
            now=now,
        )

    def _rule_dietetica_address(self, chat_id: str, now: datetime) -> AssistantRequest | None:
        if _has_fact(self.session, "diet_store_address"):
            self._close_request_if_exists("missing_address", "diet_store_address", chat_id, now)
            return None

        prompt = (
            "Para ayudarte con tu dietetica, me falta la direccion. "
            "Cual es? (podes responder 'omitir')"
        )
        return create_or_reopen_request(
            self.session,
            request_type="missing_address",
            key="diet_store_address",
            prompt=prompt,
            context={"chat_id": chat_id, "low_priority": True},
            priority=30,
            now=now,
        )

    def _rule_missing_chat_id(self, chat_id: str, now: datetime) -> AssistantRequest | None:
        if os.getenv("USER_CHAT_ID"):
            self._close_request_if_exists("missing_preference", "user_chat_id", chat_id, now)
            return None
        if _has_fact(self.session, "user_chat_id"):
            self._close_request_if_exists("missing_preference", "user_chat_id", chat_id, now)
            return None

        prompt = (
            "Para enviarte proactivos y resumen, queres usar este chat como principal? "
            "(podes responder 'omitir')"
        )
        return create_or_reopen_request(
            self.session,
            request_type="missing_preference",
            key="user_chat_id",
            prompt=prompt,
            context={"chat_id": chat_id},
            priority=55,
            now=now,
        )

    def _close_request_if_exists(
        self, request_type: str, key: str, chat_id: str, now: datetime
    ) -> None:
        dedupe_key = f"{request_type}:{key}:{chat_id}"
        request = (
            self.session.query(AssistantRequest)
            .filter(AssistantRequest.dedupe_key == dedupe_key)
            .one_or_none()
        )
        if request and request.status in {"open", "asked"}:
            mark_request_answered(self.session, request, now)


def _has_fact(session, key: str) -> bool:
    return (
        session.query(MemoryFact)
        .filter(
            MemoryFact.subject == "user",
            MemoryFact.key == key,
            MemoryFact.confidence >= 70,
        )
        .first()
        is not None
    )


def _build_calendar_auth_prompt() -> str:
    base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    return (
        "Para agendar en tu calendario necesito autorizacion. "
        f"Lo habilitas ahora? Abri {base_url}/auth/google/start "
        "(podes responder 'omitir')"
    )


def _is_calendar_intent(folded: str, intent_hint: dict[str, Any] | None) -> bool:
    if intent_hint and intent_hint.get("calendar_intent"):
        return True
    keywords = ("agend", "agenda", "evento", "calendario", "turno", "que tengo", "que hay")
    return any(keyword in folded for keyword in keywords)


def _mentions_peluqueria_de_siempre(folded: str) -> bool:
    if "peluquer" not in folded:
        return False
    return "de siempre" in folded or "lugar de siempre" in folded


def _mentions_dietetica_for_schedule(folded: str) -> bool:
    if "dietetica" not in folded and "ascend" not in folded:
        return False
    keywords = ("agend", "agenda", "bloque", "rutina", "turno")
    return any(keyword in folded for keyword in keywords)


def _fold_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text.lower()).strip()
