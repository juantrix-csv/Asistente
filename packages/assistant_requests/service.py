from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from packages.db.models import AssistantRequest, AssistantRequestEvent, MemoryFact


def build_dedupe_key(request_type: str, key: str, chat_id: str) -> str:
    return f"{request_type}:{key}:{chat_id}"


def get_active_request(session, chat_id: str) -> AssistantRequest | None:
    return (
        session.query(AssistantRequest)
        .filter(
            AssistantRequest.status == "asked",
            AssistantRequest.context["chat_id"].astext == chat_id,
        )
        .order_by(AssistantRequest.asked_at.desc())
        .first()
    )


def get_open_requests(session, chat_id: str, limit: int = 3) -> list[AssistantRequest]:
    return (
        session.query(AssistantRequest)
        .filter(
            AssistantRequest.status == "open",
            AssistantRequest.context["chat_id"].astext == chat_id,
        )
        .order_by(AssistantRequest.priority.desc(), AssistantRequest.created_at.asc())
        .limit(limit)
        .all()
    )


def count_requests_asked_today(session, day_start: datetime, day_end: datetime) -> int:
    return (
        session.query(AssistantRequest)
        .filter(
            AssistantRequest.asked_at >= day_start,
            AssistantRequest.asked_at < day_end,
        )
        .count()
    )


def create_or_reopen_request(
    session,
    request_type: str,
    key: str,
    prompt: str,
    context: dict[str, Any] | None,
    priority: int,
    now: datetime,
    reopen_if_answered: bool = False,
) -> AssistantRequest:
    chat_id = str((context or {}).get("chat_id") or "unknown")
    dedupe_key = build_dedupe_key(request_type, key, chat_id)
    existing = session.query(AssistantRequest).filter_by(dedupe_key=dedupe_key).one_or_none()

    if existing:
        existing.prompt = prompt
        existing.priority = priority
        if context is not None:
            existing.context = context

        if existing.status == "dismissed":
            dismissed_until = _get_dismissed_until(existing)
            if dismissed_until and dismissed_until > now:
                return existing
            _reopen_request(existing, session, now)
        elif existing.status == "answered" and reopen_if_answered:
            _reopen_request(existing, session, now)
        return existing

    request = AssistantRequest(
        request_type=request_type,
        key=key,
        prompt=prompt,
        context=context or {},
        priority=priority,
        status="open",
        dedupe_key=dedupe_key,
        asked_at=None,
        answered_at=None,
    )
    session.add(request)
    session.flush()
    _log_request_event(session, request.id, "created", {})
    return request


def mark_request_asked(session, request: AssistantRequest, now: datetime) -> None:
    request.status = "asked"
    request.asked_at = now
    _log_request_event(session, request.id, "asked", {})


def mark_request_answered(session, request: AssistantRequest, now: datetime) -> None:
    request.status = "answered"
    request.answered_at = now
    _log_request_event(session, request.id, "answered", {})


def mark_request_dismissed(
    session, request: AssistantRequest, now: datetime, suppress_days: int = 30
) -> None:
    request.status = "dismissed"
    request.answered_at = now
    context = request.context or {}
    context["dismissed_until"] = (now + timedelta(days=suppress_days)).isoformat()
    request.context = context
    _log_request_event(session, request.id, "dismissed", {"suppress_days": suppress_days})


def upsert_fact(
    session,
    subject: str,
    key: str,
    value: str,
    confidence: int,
    source_ref: str | None,
) -> MemoryFact:
    fact = (
        session.query(MemoryFact)
        .filter(MemoryFact.subject == subject, MemoryFact.key == key)
        .one_or_none()
    )
    if fact is None:
        fact = MemoryFact(
            subject=subject,
            key=key,
            value=value,
            confidence=confidence,
            source_ref=source_ref,
        )
        session.add(fact)
        return fact

    fact.value = value
    fact.confidence = confidence
    fact.source_ref = source_ref
    return fact


def _reopen_request(request: AssistantRequest, session, now: datetime) -> None:
    request.status = "open"
    request.asked_at = None
    request.answered_at = None
    _log_request_event(session, request.id, "reopened", {"ts": now.isoformat()})


def _get_dismissed_until(request: AssistantRequest) -> datetime | None:
    context = request.context or {}
    dismissed_until = context.get("dismissed_until")
    if not dismissed_until:
        return None
    try:
        return datetime.fromisoformat(dismissed_until)
    except ValueError:
        return None


def _log_request_event(
    session, request_id: int, event_type: str, metadata: dict[str, Any]
) -> None:
    event = AssistantRequestEvent(
        request_id=request_id,
        event_type=event_type,
        metadata=metadata or {},
    )
    session.add(event)
