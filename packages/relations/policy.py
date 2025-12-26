from __future__ import annotations

from datetime import datetime, timezone

from packages.db.models import AutonomyRule, Contact
from packages.relations.privacy import get_privacy_rules
from packages.relations.safety import MessageSafetyClassifier


class ContactPolicy:
    def __init__(self, session) -> None:
        self.session = session
        self.classifier = MessageSafetyClassifier()

    def allow_auto_send(self, chat_id: str, message_text: str) -> tuple[bool, str]:
        contact = self._find_contact(chat_id)
        if contact is None:
            return False, "unknown_contact"
        label = (contact.trust_label or "unknown").lower()
        if label == "proveedor":
            label = "provider"
        elif label == "cliente":
            label = "client"
        elif label == "amigo":
            label = "friend"
        if label not in {"provider", "client"}:
            return False, "untrusted_label"
        if contact.trust_level < 60:
            return False, "low_trust"
        if not contact.allow_auto_reply:
            return False, "auto_reply_off"

        privacy_rules = get_privacy_rules(self.session)
        safety = self.classifier.classify(message_text, privacy_rules)
        if safety.category == "sensitive":
            return False, "sensitive"
        if not safety.operational:
            return False, "not_operational"

        return True, "ok"

    def autonomy_enabled(self, scope: str) -> bool:
        rule = (
            self.session.query(AutonomyRule)
            .filter(AutonomyRule.scope == scope)
            .order_by(AutonomyRule.created_at.desc())
            .first()
        )
        if not rule or rule.mode != "on":
            return False
        if rule.until_at:
            return rule.until_at > datetime.now(timezone.utc)
        return True

    def _find_contact(self, chat_id: str) -> Contact | None:
        return self.session.query(Contact).filter_by(chat_id=chat_id).one_or_none()
