from packages.llm.schema import PlannedAction, PlannerOutput
from packages.llm.supervisor import Supervisor


def test_supervisor_high_risk_requires_confirmation() -> None:
    output = PlannerOutput(
        intent="calendar_create",
        reply="Necesito confirmar.",
        questions=[],
        actions=[
            PlannedAction(
                tool="calendar.create_event",
                input={"title": "Reunion", "start": "2025-01-01T10:00:00", "end": "2025-01-01T11:00:00"},
                risk_level="high",
                rationale="alto",
                requires_confirmation=False,
            )
        ],
        evidence_needed=[],
    )
    supervisor = Supervisor({"scopes": {"calendar_create": {"mode": "on"}}}, evidence_keys=[])
    decision = supervisor.evaluate(output, "chat-1")
    assert decision.requires_confirmation is True


def test_supervisor_medium_requires_autonomy() -> None:
    output = PlannerOutput(
        intent="calendar_create",
        reply="Ok",
        questions=[],
        actions=[
            PlannedAction(
                tool="calendar.create_event",
                input={"title": "Reunion", "start": "2025-01-01T10:00:00", "end": "2025-01-01T11:00:00"},
                risk_level="medium",
                rationale="medio",
                requires_confirmation=False,
            )
        ],
        evidence_needed=[],
    )
    supervisor = Supervisor({"scopes": {"calendar_create": {"mode": "off"}}}, evidence_keys=[])
    decision = supervisor.evaluate(output, "chat-1")
    assert decision.requires_confirmation is True


def test_supervisor_evidence_gate() -> None:
    output = PlannerOutput(
        intent="calendar_create",
        reply="Ok",
        questions=["Cual es el lugar?"],
        actions=[
            PlannedAction(
                tool="calendar.create_event",
                input={"title": "Reunion", "start": "2025-01-01T10:00:00", "end": "2025-01-01T11:00:00"},
                risk_level="low",
                rationale="bajo",
                requires_confirmation=False,
            )
        ],
        evidence_needed=["peluqueria_default"],
    )
    supervisor = Supervisor({"scopes": {"calendar_create": {"mode": "on"}}}, evidence_keys=[])
    decision = supervisor.evaluate(output, "chat-1")
    assert decision.action is None
    assert "Cual es" in decision.reply
