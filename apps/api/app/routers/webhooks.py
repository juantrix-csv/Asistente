from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks

from apps.api.app.services.waha_client import WahaClient
from apps.api.app.services.webhook_service import extract_message_fields
from packages.agent_core.core import handle_incoming_message
from packages.db.database import SessionLocal
from packages.db.models import Contact, MemoryFact, MessageRaw
from packages.relations.contact_handler import handle_contact_inbound, send_contact_reply

logger = logging.getLogger(__name__)

router = APIRouter()


def _upsert_contact(session, chat_id: str, display_name: str | None) -> None:
    contact = session.query(Contact).filter_by(chat_id=chat_id).one_or_none()
    if contact is None:
        contact = Contact(chat_id=chat_id, display_name=display_name)
        session.add(contact)
        contact.last_interaction_at = datetime.now(timezone.utc)
        return

    if display_name and contact.display_name != display_name:
        contact.display_name = display_name
    contact.last_interaction_at = datetime.now(timezone.utc)


def _resolve_user_chat_id(session) -> str | None:
    explicit = os.getenv("USER_CHAT_ID")
    if explicit:
        return explicit
    fact = (
        session.query(MemoryFact)
        .filter(
            MemoryFact.subject == "user",
            MemoryFact.key == "user_chat_id",
            MemoryFact.confidence >= 70,
        )
        .one_or_none()
    )
    if fact:
        return fact.value
    return None


def _send_reply_and_store(chat_id: str, text: str) -> None:
    client = WahaClient()
    response_payload: dict[str, Any] | None = None
    error: str | None = None

    try:
        response_payload = client.send_text(chat_id, text)
    except Exception as exc:  # pragma: no cover - best-effort logging
        logger.warning("WAHA send_text failed: %s", exc.__class__.__name__)
        error = str(exc)

    raw_payload: dict[str, Any] = {
        "request": {"chatId": chat_id, "text": text},
        "response": response_payload,
    }
    if error:
        raw_payload["error"] = error

    with SessionLocal() as session:
        outbound = MessageRaw(
            direction="outbound",
            platform="whatsapp",
            chat_id=chat_id,
            sender_id=None,
            body=text,
            raw_payload=raw_payload,
        )
        session.add(outbound)
        session.commit()


@router.post("/webhooks/waha")
def waha_webhook(payload: dict[str, Any], background_tasks: BackgroundTasks) -> dict:
    chat_id, sender_id, body, display_name = extract_message_fields(payload)
    resolved_chat_id = chat_id or "unknown"
    message_body = body or ""

    with SessionLocal() as session:
        inbound = MessageRaw(
            direction="inbound",
            platform="whatsapp",
            chat_id=resolved_chat_id,
            sender_id=sender_id,
            body=message_body,
            raw_payload=payload,
        )
        session.add(inbound)

        if chat_id:
            _upsert_contact(session, chat_id, display_name)
        session.commit()

    if not chat_id:
        logger.warning("WAHA webhook missing chat_id")
        return {"status": "ok"}

    with SessionLocal() as session:
        user_chat_id = _resolve_user_chat_id(session)
        is_contact_message = user_chat_id is not None and chat_id != user_chat_id
        inbound_id = inbound.id
        now = datetime.now(timezone.utc)

    if is_contact_message:
        with SessionLocal() as session:
            result = handle_contact_inbound(
                session=session,
                chat_id=chat_id,
                message_raw_id=inbound_id,
                body=message_body,
                display_name=display_name,
                user_chat_id=user_chat_id,
                now=now,
            )
            session.commit()

        if result.auto_reply_chat_id and result.auto_reply_text and result.thread_id:
            background_tasks.add_task(
                send_contact_reply,
                result.thread_id,
                result.auto_reply_chat_id,
                result.auto_reply_text,
                result.outbound_kind or "info",
                {
                    "decision_source": "supervisor",
                    "requested_by": "worker",
                    "risk_level": "medium",
                    "autonomy_mode_snapshot": {},
                },
            )

        if result.notify_user_chat_id and result.notify_user_text:
            background_tasks.add_task(
                _send_reply_and_store,
                result.notify_user_chat_id,
                result.notify_user_text,
            )
        return {"status": "ok"}

    agent_result = handle_incoming_message(
        chat_id=chat_id,
        sender_id=sender_id,
        text=body,
        sender_name=display_name,
        raw_payload=payload,
    )
    reply_text = agent_result.reply_text
    background_tasks.add_task(_send_reply_and_store, chat_id, reply_text)

    return {"status": "ok"}
