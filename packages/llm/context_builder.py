from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import or_

from packages.db.models import AutonomyRule, MemoryFact
from packages.memory.service import MemoryRetriever
from packages.memory.tagger import extract_tags


@dataclass
class ContextSnapshot:
    prompt: str
    evidence_keys: set[str]
    autonomy_snapshot: dict


class ContextBuilder:
    def __init__(self, session) -> None:
        self.session = session

    def build(self, chat_id: str, user_text: str, intent_hint: str | None = None) -> ContextSnapshot:
        tags = extract_tags(user_text)
        retriever = MemoryRetriever(self.session)
        chunks = retriever.retrieve(user_text, tags=tags, chat_id=chat_id, limit=6)

        facts = self._fetch_facts(tags)
        evidence_keys = {fact.key.lower() for fact in facts}
        for chunk in chunks:
            evidence_keys.update(tag.lower() for tag in chunk.tags)

        autonomy_snapshot = _build_autonomy_snapshot(self.session)
        safety_rules = [
            "No compras ni pagos.",
            "No enviar mensajes a terceros.",
            "Confirmar acciones de riesgo alto.",
            "Usar evidencia antes de afirmar.",
        ]

        prompt_lines = [
            "Hechos:",
            *_format_facts(facts),
            "Memoria:",
            *_format_chunks(chunks),
            "Autonomia:",
            *_format_autonomy(autonomy_snapshot),
            "Reglas:",
            *safety_rules,
        ]

        if intent_hint:
            prompt_lines.append(f"Intento sugerido: {intent_hint}")

        prompt = _truncate_prompt("\n".join(prompt_lines), 1800)
        return ContextSnapshot(prompt=prompt, evidence_keys=evidence_keys, autonomy_snapshot=autonomy_snapshot)

    def _fetch_facts(self, tags: list[str]) -> list[MemoryFact]:
        query = (
            self.session.query(MemoryFact)
            .filter(MemoryFact.subject == "user", MemoryFact.confidence >= 70)
        )
        if tags:
            filters = [MemoryFact.key.ilike(f"%{tag}%") for tag in tags]
            query = query.filter(or_(*filters))
        return query.order_by(MemoryFact.updated_at.desc()).limit(10).all()


def _build_autonomy_snapshot(session) -> dict:
    now_utc = datetime.now(timezone.utc)
    global_rule = (
        session.query(AutonomyRule)
        .filter(AutonomyRule.scope == "global")
        .order_by(AutonomyRule.created_at.desc())
        .first()
    )
    if global_rule and global_rule.until_at and global_rule.until_at < now_utc:
        global_rule = None
    scopes = ["calendar_create", "message_reply", "tasks_manage"]
    scope_rules: dict[str, dict] = {}
    for scope in scopes:
        rule = (
            session.query(AutonomyRule)
            .filter(AutonomyRule.scope == scope)
            .order_by(AutonomyRule.created_at.desc())
            .first()
        )
        if rule and rule.until_at and rule.until_at < now_utc:
            scope_rules[scope] = {"mode": "off", "until_at": None}
        elif rule:
            scope_rules[scope] = {"mode": rule.mode, "until_at": rule.until_at.isoformat() if rule.until_at else None}
        else:
            scope_rules[scope] = {"mode": "off", "until_at": None}

    snapshot = {
        "global": {
            "mode": global_rule.mode if global_rule else "normal",
            "until_at": global_rule.until_at.isoformat() if global_rule and global_rule.until_at else None,
        },
        "scopes": scope_rules,
    }
    return snapshot


def _format_facts(facts: Iterable[MemoryFact]) -> list[str]:
    lines: list[str] = []
    for fact in facts:
        lines.append(f"- {fact.key}: {fact.value} (confianza {fact.confidence})")
    if not lines:
        lines.append("- sin datos")
    return lines


def _format_chunks(chunks) -> list[str]:
    lines: list[str] = []
    for chunk in chunks:
        content = chunk.content.strip().replace("\n", " ")
        if len(content) > 120:
            content = content[:117] + "..."
        tags = ", ".join(chunk.tags) if chunk.tags else "sin tags"
        lines.append(f"- [{chunk.source_type}] {content} (tags: {tags})")
    if not lines:
        lines.append("- sin datos")
    return lines


def _format_autonomy(snapshot: dict) -> list[str]:
    lines = [f"- global: {snapshot['global']['mode']}"]
    for scope, rule in snapshot.get("scopes", {}).items():
        lines.append(f"- {scope}: {rule.get('mode')}")
    return lines


def _truncate_prompt(prompt: str, max_chars: int) -> str:
    if len(prompt) <= max_chars:
        return prompt
    return prompt[: max_chars - 3] + "..."
