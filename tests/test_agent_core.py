import packages.agent_core.core as core
from packages.agent_core.core import handle_incoming_message
from packages.db.database import SessionLocal
from packages.db.models import AutonomyRule, ConversationState


def test_agent_asks_duration() -> None:
    result = handle_incoming_message(
        chat_id="chat-1",
        sender_id="sender-1",
        text="agendame reunion manana 16",
        sender_name="Juan",
        raw_payload={},
    )

    assert "Cuanto dura" in result.reply_text

    with SessionLocal() as session:
        state = session.get(ConversationState, "chat-1")
        assert state is not None
        assert state.pending_question_json["type"] == "duration_minutes"


def test_agent_plan_confirm_execute(monkeypatch) -> None:
    monkeypatch.setattr(core.CalendarTool, "has_token", lambda self: True)
    monkeypatch.setattr(core.CalendarTool, "is_free", lambda self, start, end: True)

    created: dict[str, str] = {}

    def fake_create(self, title, start, end, location=None, notes=None):
        created["title"] = title
        return {"event_id": "evt-1", "htmlLink": "http://example.com"}

    monkeypatch.setattr(core.CalendarTool, "create_event", fake_create)

    result = handle_incoming_message(
        chat_id="chat-2",
        sender_id="sender-2",
        text="agendame reunion manana 16 por 60 min",
        sender_name="Juan",
        raw_payload={},
    )

    assert "Confirmas" in result.reply_text

    confirm = handle_incoming_message(
        chat_id="chat-2",
        sender_id="sender-2",
        text="confirmo",
        sender_name="Juan",
        raw_payload={},
    )

    assert "evento creado" in confirm.reply_text
    assert created["title"] == "reunion"

    with SessionLocal() as session:
        state = session.get(ConversationState, "chat-2")
        assert state is not None
        assert state.pending_action_json is None


def test_agent_cancel_clears_state(monkeypatch) -> None:
    monkeypatch.setattr(core.CalendarTool, "has_token", lambda self: True)
    monkeypatch.setattr(core.CalendarTool, "is_free", lambda self, start, end: True)

    handle_incoming_message(
        chat_id="chat-3",
        sender_id="sender-3",
        text="agendame reunion manana 16 por 60 min",
        sender_name="Juan",
        raw_payload={},
    )

    cancelled = handle_incoming_message(
        chat_id="chat-3",
        sender_id="sender-3",
        text="cancelar",
        sender_name="Juan",
        raw_payload={},
    )

    assert "cancelado" in cancelled.reply_text

    with SessionLocal() as session:
        state = session.get(ConversationState, "chat-3")
        assert state is not None
        assert state.pending_action_json is None
        assert state.pending_question_json is None


def test_agent_focus_mode_sets_rule() -> None:
    result = handle_incoming_message(
        chat_id="chat-4",
        sender_id="sender-4",
        text="modo foco 2 horas",
        sender_name="Juan",
        raw_payload={},
    )

    assert "Modo foco" in result.reply_text

    with SessionLocal() as session:
        rule = session.query(AutonomyRule).filter_by(mode="focus").one()
        assert rule.scope == "global"
        assert rule.until_at is not None


def test_autonomy_on_for_calendar() -> None:
    result = handle_incoming_message(
        chat_id="chat-6",
        sender_id="sender-6",
        text="autonomia on 2 horas para calendario",
        sender_name="Juan",
        raw_payload={},
    )

    assert "Autonomia activada" in result.reply_text

    with SessionLocal() as session:
        rule = (
            session.query(AutonomyRule)
            .filter_by(scope="calendar_create", mode="on")
            .one()
        )
        assert rule.until_at is not None


def test_autonomy_status() -> None:
    result = handle_incoming_message(
        chat_id="chat-7",
        sender_id="sender-7",
        text="status autonomia",
        sender_name="Juan",
        raw_payload={},
    )

    assert "Autonomia" in result.reply_text


def test_agent_conflict_proposes_alternatives(monkeypatch) -> None:
    monkeypatch.setattr(core.CalendarTool, "has_token", lambda self: True)

    calls: list[datetime] = []

    def fake_is_free(self, start, end):
        calls.append(start)
        return len(calls) > 1

    monkeypatch.setattr(core.CalendarTool, "is_free", fake_is_free)

    result = handle_incoming_message(
        chat_id="chat-5",
        sender_id="sender-5",
        text="agendame reunion manana 16 por 60 min",
        sender_name="Juan",
        raw_payload={},
    )

    assert "Opciones" in result.reply_text

    with SessionLocal() as session:
        state = session.get(ConversationState, "chat-5")
        assert state is not None
        assert state.pending_question_json["type"] == "conflict_choice"
        assert len(state.pending_question_json["options"]) == 2
