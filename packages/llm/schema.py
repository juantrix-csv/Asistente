from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, validator

from packages.llm.tools_registry import get_tool_names


class PlannedAction(BaseModel):
    tool: str
    input: dict[str, Any]
    risk_level: Literal["low", "medium", "high"]
    rationale: str
    requires_confirmation: bool

    @validator("tool")
    def validate_tool(cls, value: str) -> str:
        allowed = get_tool_names()
        if value not in allowed:
            raise ValueError("Unknown tool")
        return value


class PlannerOutput(BaseModel):
    intent: str
    reply: str
    questions: list[str] = []
    actions: list[PlannedAction] = []
    evidence_needed: list[str] = []

    @validator("questions")
    def validate_questions(cls, value: list[str]) -> list[str]:
        if len(value) > 1:
            raise ValueError("Only one question is allowed")
        return value

    @validator("actions")
    def validate_actions(cls, value: list[PlannedAction]) -> list[PlannedAction]:
        if len(value) > 3:
            raise ValueError("Too many actions")
        return value


def fallback_output() -> PlannerOutput:
    return PlannerOutput(
        intent="ask_clarifying_question",
        reply="Necesito un poco mas de detalle.",
        questions=["Podrias aclarar que queres hacer?"],
        actions=[],
        evidence_needed=[],
    )
