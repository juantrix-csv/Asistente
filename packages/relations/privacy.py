from __future__ import annotations

from packages.db.models import PrivacyRule

DEFAULT_RULES = {
    "no_share_address": "No compartir direcciones personales sin confirmacion.",
    "no_share_payment": "No compartir datos de pago sin confirmacion.",
}


def get_privacy_rules(session) -> dict[str, bool]:
    _ensure_rules(session)
    rows = session.query(PrivacyRule).all()
    return {row.rule_name: row.enabled for row in rows}


def _ensure_rules(session) -> None:
    existing = {row.rule_name for row in session.query(PrivacyRule.rule_name).all()}
    for name, description in DEFAULT_RULES.items():
        if name in existing:
            continue
        session.add(PrivacyRule(rule_name=name, description=description, enabled=True))
    session.flush()
