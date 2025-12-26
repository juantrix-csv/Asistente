from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from packages.llm.schema import PlannerOutput, PlannedAction
from packages.llm.tools_registry import get_tool_scope, validate_tool_input


@dataclass
class SupervisorDecision:
    reply: str
    action: PlannedAction | None
    requires_confirmation: bool
    reason: str


class Supervisor:
    def __init__(self, autonomy_snapshot: dict, evidence_keys: Iterable[str]) -> None:
        self.autonomy_snapshot = autonomy_snapshot
        self.evidence_keys = {key.lower() for key in evidence_keys}

    def evaluate(self, output: PlannerOutput, chat_id: str) -> SupervisorDecision:
        if output.questions:
            return SupervisorDecision(
                reply=output.questions[0],
                action=None,
                requires_confirmation=False,
                reason="planner_question",
            )

        if not output.actions:
            reply = output.reply or "Entendido."
            return SupervisorDecision(
                reply=reply,
                action=None,
                requires_confirmation=False,
                reason="no_action",
            )

        action = output.actions[0]
        tool_scope = get_tool_scope(action.tool)
        if tool_scope is None:
            return SupervisorDecision(
                reply="No puedo ejecutar esa accion.",
                action=None,
                requires_confirmation=False,
                reason="tool_not_allowed",
            )

        missing = validate_tool_input(action.tool, action.input)
        if missing:
            question = output.questions[0] if output.questions else "Necesito mas detalles."
            return SupervisorDecision(
                reply=question,
                action=None,
                requires_confirmation=False,
                reason="missing_input",
            )

        missing_evidence = _missing_evidence(output.evidence_needed, self.evidence_keys)
        if missing_evidence:
            question = output.questions[0] if output.questions else "Necesito confirmar ese dato."
            return SupervisorDecision(
                reply=question,
                action=None,
                requires_confirmation=False,
                reason="missing_evidence",
            )

        if action.risk_level == "high":
            return SupervisorDecision(
                reply=output.reply or "Necesito confirmacion.",
                action=action,
                requires_confirmation=True,
                reason="high_risk",
            )

        if action.requires_confirmation:
            return SupervisorDecision(
                reply=output.reply or "Necesito confirmacion.",
                action=action,
                requires_confirmation=True,
                reason="requires_confirmation",
            )

        if action.risk_level == "medium":
            if not _autonomy_enabled(self.autonomy_snapshot, tool_scope):
                return SupervisorDecision(
                    reply=output.reply or "Necesito confirmacion.",
                    action=action,
                    requires_confirmation=True,
                    reason="autonomy_off",
                )

        return SupervisorDecision(
            reply=output.reply or "Listo.",
            action=action,
            requires_confirmation=False,
            reason="approved",
        )


def _autonomy_enabled(snapshot: dict, scope: str) -> bool:
    scope_data = snapshot.get("scopes", {}).get(scope, {})
    mode = scope_data.get("mode", "off")
    until_at = scope_data.get("until_at")
    if mode != "on":
        return False
    if until_at:
        try:
            until_dt = datetime.fromisoformat(until_at)
        except ValueError:
            return False
        return until_dt > datetime.now(timezone.utc)
    return True


def _missing_evidence(evidence_needed: list[str], evidence_keys: set[str]) -> list[str]:
    missing = []
    for item in evidence_needed:
        lowered = item.lower()
        if lowered not in evidence_keys:
            missing.append(item)
    return missing
