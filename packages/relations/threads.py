from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from packages.db.models import ConversationEvent, ConversationThread


@dataclass
class ThreadUpdate:
    thread: ConversationThread
    event: ConversationEvent


class ThreadManager:
    def __init__(self, session) -> None:
        self.session = session

    def get_or_create_thread(self, contact_id: int, channel: str = "whatsapp") -> ConversationThread:
        thread = (
            self.session.query(ConversationThread)
            .filter(
                ConversationThread.contact_id == contact_id,
                ConversationThread.status != "closed",
            )
            .order_by(ConversationThread.updated_at.desc())
            .first()
        )
        if thread:
            return thread

        thread = ConversationThread(
            contact_id=contact_id,
            channel=channel,
            status="open",
        )
        self.session.add(thread)
        self.session.flush()
        return thread

    def record_inbound(
        self,
        thread: ConversationThread,
        message_raw_id: int,
        text: str,
        now: datetime,
        kind: str,
    ) -> ThreadUpdate:
        event = ConversationEvent(
            thread_id=thread.id,
            direction="inbound",
            message_raw_id=message_raw_id,
            kind=kind,
            extracted=None,
        )
        self.session.add(event)
        thread.last_message_at = now
        thread.last_summary = _summarize(text)
        thread.status = _status_after_inbound(thread.status, kind)
        return ThreadUpdate(thread=thread, event=event)

    def record_outbound(
        self,
        thread: ConversationThread,
        message_raw_id: int,
        text: str,
        now: datetime,
        kind: str,
    ) -> ThreadUpdate:
        event = ConversationEvent(
            thread_id=thread.id,
            direction="outbound",
            message_raw_id=message_raw_id,
            kind=kind,
            extracted=None,
        )
        self.session.add(event)
        thread.last_message_at = now
        thread.last_summary = _summarize(text)
        thread.status = _status_after_outbound(thread.status, kind)
        return ThreadUpdate(thread=thread, event=event)

    def close_thread(self, thread: ConversationThread) -> None:
        thread.status = "closed"


def _status_after_inbound(current: str, kind: str) -> str:
    if kind == "question":
        return "waiting_me"
    if kind == "closing":
        return "closed"
    if current == "waiting_them":
        return "open"
    return current or "open"


def _status_after_outbound(current: str, kind: str) -> str:
    if kind == "question":
        return "waiting_them"
    if kind == "closing":
        return "closed"
    if current == "waiting_me":
        return "open"
    return current or "open"


def _summarize(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if len(cleaned) > 140:
        return cleaned[:137] + "..."
    return cleaned
