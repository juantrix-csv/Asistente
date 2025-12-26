from __future__ import annotations

from typing import Any


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _get_path(payload: dict[str, Any], path: tuple[str, ...]) -> Any | None:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _first_value(payload: dict[str, Any], paths: list[tuple[str, ...]]) -> str | None:
    for path in paths:
        value = _get_path(payload, path)
        text_value = _coerce_text(value)
        if text_value:
            return text_value
    return None


def extract_message_fields(payload: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
    chat_id_paths = [
        ("payload", "chatId"),
        ("payload", "chat_id"),
        ("payload", "chat", "id"),
        ("payload", "message", "chatId"),
        ("payload", "message", "chat_id"),
        ("payload", "from"),
        ("payload", "chat"),
        ("chatId",),
        ("chat_id",),
        ("chat", "id"),
        ("from",),
        ("chat",),
    ]
    sender_id_paths = [
        ("payload", "author"),
        ("payload", "senderId"),
        ("payload", "sender_id"),
        ("payload", "sender", "id"),
        ("payload", "sender"),
        ("payload", "participant"),
        ("author",),
        ("senderId",),
        ("sender_id",),
        ("sender", "id"),
    ]
    text_paths = [
        ("payload", "body"),
        ("payload", "text"),
        ("payload", "message", "text"),
        ("payload", "message", "body"),
        ("payload", "message"),
        ("payload", "caption"),
        ("payload", "content"),
        ("message", "text"),
        ("message", "body"),
        ("text",),
        ("body",),
        ("message",),
    ]
    display_name_paths = [
        ("payload", "senderName"),
        ("payload", "pushName"),
        ("payload", "notifyName"),
        ("payload", "profileName"),
        ("payload", "fromName"),
        ("payload", "name"),
        ("senderName",),
        ("pushName",),
        ("notifyName",),
        ("profileName",),
        ("fromName",),
        ("name",),
    ]

    chat_id = _first_value(payload, chat_id_paths)
    sender_id = _first_value(payload, sender_id_paths)
    body = _first_value(payload, text_paths)
    display_name = _first_value(payload, display_name_paths)

    return chat_id, sender_id, body, display_name


def build_reply_text(body: str | None) -> str:
    if body:
        return f"Recibido: {body}"
    return "Recibi tu mensaje"