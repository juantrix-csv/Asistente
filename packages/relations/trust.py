from __future__ import annotations

from dataclasses import dataclass

from packages.db.models import Contact, ConversationEvent, ConversationThread

TRUST_LEVELS = {
    "unknown": 20,
    "client": 60,
    "provider": 60,
    "friend": 70,
    "inner": 90,
}


@dataclass
class TrustResult:
    label: str
    level: int


class TrustEngine:
    def apply_label(self, contact: Contact, label: str) -> TrustResult:
        label = _normalize_label(label)
        level = TRUST_LEVELS.get(label, contact.trust_level)
        contact.trust_label = label
        contact.trust_level = max(contact.trust_level, level)
        return TrustResult(label=contact.trust_label, level=contact.trust_level)

    def set_level(self, contact: Contact, level: int) -> TrustResult:
        contact.trust_level = max(0, min(level, 100))
        return TrustResult(label=contact.trust_label, level=contact.trust_level)

    def set_auto_reply(self, contact: Contact, enabled: bool) -> None:
        contact.allow_auto_reply = enabled

    def should_suggest_upgrade(self, session, contact_id: int) -> bool:
        events = (
            session.query(ConversationEvent)
            .join(ConversationThread, ConversationEvent.thread_id == ConversationThread.id)
            .filter(ConversationThread.contact_id == contact_id)
            .count()
        )
        contact = session.query(Contact).filter_by(id=contact_id).one_or_none()
        if not contact:
            return False
        return events >= 20 and contact.trust_level < 60


def _normalize_label(label: str) -> str:
    lowered = label.lower()
    if lowered == "proveedor":
        return "provider"
    if lowered == "cliente":
        return "client"
    if lowered == "amigo":
        return "friend"
    return lowered
