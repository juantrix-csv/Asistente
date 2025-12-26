from __future__ import annotations

import re
import unicodedata
from typing import Any

from apps.api.app.services.waha_client import WahaClient
from packages.db.database import SessionLocal
from packages.db.models import MessageRaw


def build_reply_draft(incoming_text: str, contact_name: str | None) -> str:
    name = contact_name or "Hola"
    folded = _fold(incoming_text)
    if _mentions_price(folded):
        return f"{name}, gracias por consultar. Te paso el precio en breve."
    if _mentions_schedule(folded):
        return f"{name}, gracias. Estoy revisando horarios y te confirmo en breve."
    if "direccion" in folded:
        return f"{name}, recibido. Te confirmo la direccion en breve."
    return f"{name}, recibido. Lo reviso y te confirmo en breve."


def send_message_and_store(chat_id: str, text: str) -> tuple[int, dict[str, Any] | None, str | None]:
    client = WahaClient()
    response_payload: dict[str, Any] | None = None
    error: str | None = None

    try:
        response_payload = client.send_text(chat_id, text)
    except Exception as exc:  # pragma: no cover - best-effort logging
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
        return outbound.id, response_payload, error


def _mentions_price(folded: str) -> bool:
    return any(word in folded for word in ("precio", "presupuesto", "cotizacion"))


def _mentions_schedule(folded: str) -> bool:
    return any(word in folded for word in ("horario", "turno", "disponibilidad", "cuando"))


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text.lower()).strip()
