from datetime import datetime, timedelta, timezone

from apps.worker.app import proactive as proactive_module
from apps.worker.app.proactive import (
    TIMEZONE,
    Candidate,
    decide,
    run_daily_digest,
    run_proactive_tick,
)
from packages.agent_core.core import handle_incoming_message
from packages.db.database import SessionLocal
from packages.db.models import AutonomyRule, ProactiveEvent, SystemConfig, Task


class _FakeCalendarTool:
    def __init__(self, events):
        self._events = events

    def list_events(self, time_min, time_max):
        return self._events


def _make_event(event_id: str, title: str, start: datetime, location: str | None = None) -> dict:
    payload = {
        "id": event_id,
        "summary": title,
        "start": start.isoformat(),
        "end": start.isoformat(),
    }
    if location is not None:
        payload["location"] = location
    return payload


def _make_config() -> SystemConfig:
    return SystemConfig(**proactive_module.DEFAULT_CONFIG)


def test_decide_quiet_hours_digest() -> None:
    now = datetime(2025, 1, 1, 8, 0, tzinfo=TIMEZONE)
    candidate = Candidate(
        trigger_type="calendar_upcoming",
        entity_id="evt-1",
        title="Reunion",
        score=70,
        priority=None,
        dedupe_key="calendar:evt-1:tminus60",
        message="msg",
    )
    decision = decide(candidate, now, _make_config(), "normal", 0, False)
    assert decision.decision == "digested"
    assert decision.reason == "quiet_hours"


def test_decide_focus_digest() -> None:
    now = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
    candidate = Candidate(
        trigger_type="calendar_upcoming",
        entity_id="evt-2",
        title="Reunion",
        score=70,
        priority=None,
        dedupe_key="calendar:evt-2:tminus60",
        message="msg",
    )
    decision = decide(candidate, now, _make_config(), "focus", 0, False)
    assert decision.decision == "digested"
    assert decision.reason == "autonomy_mode"


def test_decide_cooldown_digest() -> None:
    now = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
    candidate = Candidate(
        trigger_type="calendar_upcoming",
        entity_id="evt-3",
        title="Reunion",
        score=70,
        priority=None,
        dedupe_key="calendar:evt-3:tminus60",
        message="msg",
    )
    decision = decide(candidate, now, _make_config(), "normal", 0, True)
    assert decision.decision == "digested"
    assert decision.reason == "cooldown"


def test_decide_rate_limit_digest() -> None:
    now = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
    candidate = Candidate(
        trigger_type="calendar_upcoming",
        entity_id="evt-4",
        title="Reunion",
        score=90,
        priority=None,
        dedupe_key="calendar:evt-4:tminus10",
        message="msg",
    )
    config = _make_config()
    decision = decide(candidate, now, config, "normal", config.daily_proactive_limit, False)
    assert decision.decision == "digested"
    assert decision.reason == "rate_limit"


def test_worker_sends_calendar_maybe(monkeypatch) -> None:
    monkeypatch.setenv("USER_CHAT_ID", "123@c.us")
    now = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
    start = now + timedelta(minutes=50)
    fake_tool = _FakeCalendarTool([_make_event("evt-5", "Reunion", start, location="Oficina")])

    sent = {}

    def fake_send(self, chat_id: str, text: str) -> dict:
        sent["chat_id"] = chat_id
        sent["text"] = text
        return {"messageId": "fake"}

    monkeypatch.setattr(
        "apps.api.app.services.waha_client.WahaClient.send_text", fake_send
    )

    run_proactive_tick(now=now, calendar_tool=fake_tool)

    assert sent["chat_id"] == "123@c.us"
    assert "Reunion" in sent["text"]

    with SessionLocal() as session:
        record = session.query(ProactiveEvent).filter_by(entity_id="evt-5").one()
        assert record.decision == "sent"


def test_worker_digests_task_and_sends_digest(monkeypatch) -> None:
    monkeypatch.setenv("USER_CHAT_ID", "123@c.us")
    now = datetime(2025, 1, 1, 20, 0, tzinfo=TIMEZONE)
    task = Task(
        title="Enviar presupuesto",
        status="open",
        due_date=now.date(),
        due_at=None,
        priority=1,
    )
    with SessionLocal() as session:
        session.add(task)
        session.commit()

    fake_tool = _FakeCalendarTool([])
    run_proactive_tick(now=now, calendar_tool=fake_tool)

    with SessionLocal() as session:
        record = session.query(ProactiveEvent).filter_by(entity_id=str(task.id)).one()
        assert record.decision == "digested"

    sent = {}

    def fake_send(self, chat_id: str, text: str) -> dict:
        sent["chat_id"] = chat_id
        sent["text"] = text
        return {"messageId": "fake"}

    monkeypatch.setattr(
        "apps.api.app.services.waha_client.WahaClient.send_text", fake_send
    )

    digest_time = datetime(2025, 1, 1, 21, 0, tzinfo=TIMEZONE)
    run_daily_digest(now=digest_time, calendar_tool=fake_tool)

    assert "Resumen de hoy" in sent["text"]
    assert "Tarea: Enviar presupuesto" in sent["text"]


def test_focus_command_affects_decisions(monkeypatch) -> None:
    monkeypatch.setenv("USER_CHAT_ID", "123@c.us")
    now = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
    start = now + timedelta(minutes=50)
    fake_tool = _FakeCalendarTool([_make_event("evt-6", "Reunion", start, location="Oficina")])
    monkeypatch.setattr(
        "apps.api.app.services.waha_client.WahaClient.send_text",
        lambda self, chat_id, text: {"messageId": "fake"},
    )

    handle_incoming_message(
        chat_id="chat-1",
        sender_id="sender-1",
        text="modo foco 2 horas",
        sender_name="Juan",
        raw_payload={},
    )

    with SessionLocal() as session:
        rule = session.query(AutonomyRule).filter_by(mode="focus").one()
        assert rule.until_at is not None
        rule.until_at = now.astimezone(timezone.utc) + timedelta(hours=2)
        session.commit()

    run_proactive_tick(now=now, calendar_tool=fake_tool)

    with SessionLocal() as session:
        record = session.query(ProactiveEvent).filter_by(entity_id="evt-6").one()
        assert record.decision == "digested"


def test_status_proactivo_command() -> None:
    reply = handle_incoming_message(
        chat_id="chat-2",
        sender_id="sender-2",
        text="status proactivo",
        sender_name="Juan",
        raw_payload={},
    )

    assert "Modo proactivo" in reply.reply_text
    assert "Limite diario" in reply.reply_text
