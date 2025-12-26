from datetime import datetime

from packages.agent_core.core import handle_incoming_message
from packages.db.database import SessionLocal
from packages.db.models import ConversationState, ToolRun
from packages.llm.schema import PlannedAction, PlannerOutput


def test_llm_executes_calendar_action(monkeypatch) -> None:
    start = datetime(2025, 1, 1, 10, 0).isoformat()
    end = datetime(2025, 1, 1, 11, 0).isoformat()
    planner_output = PlannerOutput(
        intent="calendar_create",
        reply="Evento creado.",
        questions=[],
        actions=[
            PlannedAction(
                tool="calendar.create_event",
                input={"title": "Reunion", "start": start, "end": end},
                risk_level="low",
                rationale="pedido usuario",
                requires_confirmation=False,
            )
        ],
        evidence_needed=[],
    )

    monkeypatch.setattr(
        "packages.agent_core.core.LlmClient.generate_structured",
        lambda self, system_prompt, user_input, context: planner_output,
    )
    monkeypatch.setattr(
        "packages.agent_core.core.execute_tool",
        lambda tool_name, tool_input, calendar_tool=None, message_sender=None: {
            "htmlLink": "http://example.com"
        },
    )

    reply = handle_incoming_message(
        chat_id="chat-1",
        sender_id="sender-1",
        text="crear evento manana",
        sender_name="Juan",
        raw_payload={},
    )

    assert "http://example.com" in reply.reply_text

    with SessionLocal() as session:
        run = session.query(ToolRun).one()
        assert run.decision_source == "supervisor"
        assert run.requested_by == "llm"


def test_llm_requires_confirmation_sets_pending(monkeypatch) -> None:
    start = datetime(2025, 1, 1, 10, 0).isoformat()
    end = datetime(2025, 1, 1, 11, 0).isoformat()
    planner_output = PlannerOutput(
        intent="calendar_create",
        reply="Necesito confirmacion.",
        questions=[],
        actions=[
            PlannedAction(
                tool="calendar.create_event",
                input={"title": "Reunion", "start": start, "end": end},
                risk_level="high",
                rationale="pedido",
                requires_confirmation=False,
            )
        ],
        evidence_needed=[],
    )

    monkeypatch.setattr(
        "packages.agent_core.core.LlmClient.generate_structured",
        lambda self, system_prompt, user_input, context: planner_output,
    )

    reply = handle_incoming_message(
        chat_id="chat-2",
        sender_id="sender-2",
        text="crear evento manana",
        sender_name="Juan",
        raw_payload={},
    )

    assert "confirmacion" in reply.reply_text.lower()

    with SessionLocal() as session:
        state = session.get(ConversationState, "chat-2")
        assert state.pending_action_json is not None
