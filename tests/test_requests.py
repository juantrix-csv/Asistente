from datetime import datetime

from apps.worker.app import proactive as proactive_module
from apps.worker.app.proactive import TIMEZONE, run_daily_digest
from packages.agent_core.core import handle_incoming_message
from packages.assistant_requests.detector import NeedsDetector
from packages.assistant_requests.policy import RequestPolicy
from packages.assistant_requests.service import create_or_reopen_request, mark_request_asked
from packages.db.database import SessionLocal
from packages.db.models import AssistantRequest, MemoryFact, ProactiveEvent, SystemConfig


def _make_config() -> SystemConfig:
    return SystemConfig(**proactive_module.DEFAULT_CONFIG)


def test_needs_detector_calendar_auth_request(monkeypatch) -> None:
    monkeypatch.setattr(
        "packages.assistant_requests.detector.CalendarTool.has_token",
        lambda self: False,
    )
    now = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
    with SessionLocal() as session:
        detector = NeedsDetector(session)
        detector.scan(chat_id="chat-1", now=now, user_text="agendar turno", intent_hint=None)
        session.commit()

        request = (
            session.query(AssistantRequest)
            .filter_by(request_type="authorize_calendar")
            .one()
        )
        assert request.status == "open"


def test_needs_detector_default_barbershop_request() -> None:
    now = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
    with SessionLocal() as session:
        detector = NeedsDetector(session)
        detector.scan(
            chat_id="chat-2",
            now=now,
            user_text="Quiero turno en la peluqueria de siempre",
            intent_hint=None,
        )
        session.commit()

        request = (
            session.query(AssistantRequest)
            .filter_by(request_type="missing_default_contact")
            .one()
        )
        assert request.key == "default_barbershop"


def test_needs_detector_dedupe(monkeypatch) -> None:
    monkeypatch.setattr(
        "packages.assistant_requests.detector.CalendarTool.has_token",
        lambda self: True,
    )
    now = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
    with SessionLocal() as session:
        detector = NeedsDetector(session)
        detector.scan(
            chat_id="chat-3",
            now=now,
            user_text="Peluqueria de siempre",
            intent_hint=None,
        )
        detector.scan(
            chat_id="chat-3",
            now=now,
            user_text="Peluqueria de siempre",
            intent_hint=None,
        )
        session.commit()

        count = session.query(AssistantRequest).count()
        assert count == 1


def test_request_policy_quiet_hours() -> None:
    policy = RequestPolicy()
    config = _make_config()
    request = AssistantRequest(
        request_type="missing_preference",
        key="preferred_event_duration_minutes",
        prompt="x",
        context={"chat_id": "chat-4"},
        priority=60,
        status="open",
        dedupe_key="missing_preference:preferred_event_duration_minutes:chat-4",
    )
    now = datetime(2025, 1, 1, 8, 0, tzinfo=TIMEZONE)
    assert policy.should_ask(request, now, "normal", config, asked_today=0) is False


def test_request_policy_daily_limit() -> None:
    policy = RequestPolicy()
    config = _make_config()
    request = AssistantRequest(
        request_type="missing_preference",
        key="preferred_event_duration_minutes",
        prompt="x",
        context={"chat_id": "chat-5"},
        priority=60,
        status="open",
        dedupe_key="missing_preference:preferred_event_duration_minutes:chat-5",
    )
    now = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
    assert policy.should_ask(request, now, "normal", config, asked_today=1) is False


def test_request_policy_focus_suppresses() -> None:
    policy = RequestPolicy()
    config = _make_config()
    request = AssistantRequest(
        request_type="missing_preference",
        key="preferred_event_duration_minutes",
        prompt="x",
        context={"chat_id": "chat-6"},
        priority=60,
        status="open",
        dedupe_key="missing_preference:preferred_event_duration_minutes:chat-6",
    )
    now = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
    assert policy.should_ask(request, now, "focus", config, asked_today=0) is False


def test_request_policy_urgencies_only_suppresses() -> None:
    policy = RequestPolicy()
    config = _make_config()
    request = AssistantRequest(
        request_type="missing_preference",
        key="preferred_event_duration_minutes",
        prompt="x",
        context={"chat_id": "chat-6b"},
        priority=60,
        status="open",
        dedupe_key="missing_preference:preferred_event_duration_minutes:chat-6b",
    )
    now = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
    assert policy.should_ask(request, now, "urgencies_only", config, asked_today=0) is False


def test_request_policy_high_priority_outside_window() -> None:
    policy = RequestPolicy()
    config = _make_config()
    request = AssistantRequest(
        request_type="authorize_calendar",
        key="calendar_auth",
        prompt="x",
        context={"chat_id": "chat-7"},
        priority=90,
        status="open",
        dedupe_key="authorize_calendar:calendar_auth:chat-7",
    )
    now = datetime(2025, 1, 1, 20, 0, tzinfo=TIMEZONE)
    assert policy.should_ask(request, now, "normal", config, asked_today=0) is True


def test_request_answer_creates_fact() -> None:
    now = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
    with SessionLocal() as session:
        request = create_or_reopen_request(
            session,
            request_type="missing_default_contact",
            key="default_barbershop",
            prompt="x",
            context={"chat_id": "chat-8"},
            priority=75,
            now=now,
        )
        mark_request_asked(session, request, now)
        session.commit()

    reply = handle_incoming_message(
        chat_id="chat-8",
        sender_id="sender-1",
        text="Peluqueria del centro",
        sender_name="Juan",
        raw_payload={},
    )
    assert "Listo" in reply.reply_text

    with SessionLocal() as session:
        fact = (
            session.query(MemoryFact)
            .filter_by(subject="user", key="default_barbershop")
            .one()
        )
        assert fact.value == "Peluqueria del centro"
        request = session.query(AssistantRequest).filter_by(key="default_barbershop").one()
        assert request.status == "answered"


def test_digest_includes_requests(monkeypatch) -> None:
    monkeypatch.setenv("USER_CHAT_ID", "123@c.us")
    now = datetime(2025, 1, 1, 20, 0, tzinfo=TIMEZONE)
    with SessionLocal() as session:
        session.add(
            ProactiveEvent(
                trigger_type="task_due_today",
                dedupe_key="task:1:due_today",
                entity_id="1",
                priority=None,
                score=55,
                decision="digested",
                reason="below_threshold",
                sent_at=None,
                created_at=now,
            )
        )
        session.add(
            AssistantRequest(
                request_type="missing_default_contact",
                key="default_barbershop",
                prompt="x",
                context={"chat_id": "123@c.us"},
                priority=90,
                status="open",
                dedupe_key="missing_default_contact:default_barbershop:123@c.us",
            )
        )
        session.commit()

    sent = {}

    def fake_send(self, chat_id: str, text: str) -> dict:
        sent["chat_id"] = chat_id
        sent["text"] = text
        return {"messageId": "fake"}

    monkeypatch.setattr(
        "apps.api.app.services.waha_client.WahaClient.send_text", fake_send
    )

    digest_time = datetime(2025, 1, 1, 21, 0, tzinfo=TIMEZONE)
    run_daily_digest(now=digest_time, calendar_tool=None)

    assert "Para mejorar" in sent["text"]
    assert "peluqueria de siempre" in sent["text"]
