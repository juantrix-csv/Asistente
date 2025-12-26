from datetime import datetime, time
from zoneinfo import ZoneInfo

from packages.agent_core.core import handle_incoming_message
from packages.db.database import SessionLocal
from packages.db.models import Habit, HabitLog, HabitNudge, ProactiveEvent, SystemConfig
from apps.worker.app.proactive import run_proactive_tick

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


class _FakeCalendarTool:
    def list_events(self, time_min, time_max):
        return []


def _seed_habit(window_start: time, window_end: time, priority: int = 3) -> Habit:
    with SessionLocal() as session:
        habit = Habit(
            name="Caminar",
            description=None,
            schedule_type="daily",
            target_per_week=None,
            days_of_week=None,
            window_start=window_start,
            window_end=window_end,
            min_version_text="Caminar 5 min",
            priority=priority,
            active=True,
        )
        session.add(habit)
        session.commit()
        return habit


def test_habit_nudge_sent(monkeypatch) -> None:
    monkeypatch.setenv("USER_CHAT_ID", "123@c.us")
    monkeypatch.setenv("HABIT_NUDGE_USE_LLM", "0")
    now = datetime(2025, 1, 3, 12, 0, tzinfo=TIMEZONE)
    _seed_habit(window_start=time(11, 0), window_end=time(12, 30))

    sent = {}

    def fake_send(self, chat_id: str, text: str) -> dict:
        sent["chat_id"] = chat_id
        sent["text"] = text
        return {"messageId": "fake"}

    monkeypatch.setattr(
        "apps.api.app.services.waha_client.WahaClient.send_text", fake_send
    )

    run_proactive_tick(now=now, calendar_tool=_FakeCalendarTool())

    assert sent["chat_id"] == "123@c.us"
    assert "Caminar" in sent["text"]

    with SessionLocal() as session:
        event = session.query(ProactiveEvent).filter_by(trigger_type="habit_window").one()
        assert event.decision == "sent"
        nudge = session.query(HabitNudge).one()
        assert nudge.decision == "sent"


def test_habit_reply_creates_log() -> None:
    _seed_habit(window_start=time(9, 0), window_end=time(20, 0))

    reply = handle_incoming_message(
        chat_id="user@c.us",
        sender_id="user@c.us",
        text="hecho caminar",
        sender_name="User",
        raw_payload={},
    )
    assert "registre" in reply.reply_text.lower()

    with SessionLocal() as session:
        log = session.query(HabitLog).one()
        assert log.status == "done"


def test_habit_quiet_hours_digest(monkeypatch) -> None:
    monkeypatch.setenv("USER_CHAT_ID", "123@c.us")
    monkeypatch.setenv("HABIT_NUDGE_USE_LLM", "0")
    now = datetime(2025, 1, 4, 8, 0, tzinfo=TIMEZONE)
    _seed_habit(window_start=time(7, 0), window_end=time(8, 30))

    sent = {}

    def fake_send(self, chat_id: str, text: str) -> dict:
        sent["chat_id"] = chat_id
        sent["text"] = text
        return {"messageId": "fake"}

    monkeypatch.setattr(
        "apps.api.app.services.waha_client.WahaClient.send_text", fake_send
    )

    run_proactive_tick(now=now, calendar_tool=_FakeCalendarTool())

    assert sent == {}

    with SessionLocal() as session:
        event = session.query(ProactiveEvent).filter_by(trigger_type="habit_window").one()
        assert event.decision == "digested"


def test_habit_rate_limit_digest(monkeypatch) -> None:
    monkeypatch.setenv("USER_CHAT_ID", "123@c.us")
    monkeypatch.setenv("HABIT_NUDGE_USE_LLM", "0")
    now = datetime(2025, 1, 5, 12, 0, tzinfo=TIMEZONE)
    _seed_habit(window_start=time(11, 0), window_end=time(12, 30))

    with SessionLocal() as session:
        config = SystemConfig(
            quiet_hours_start=time(0, 0),
            quiet_hours_end=time(9, 30),
            strong_window_start=time(11, 0),
            strong_window_end=time(19, 0),
            daily_proactive_limit=0,
            maybe_cooldown_minutes=240,
            urgent_threshold=80,
            maybe_threshold=50,
            llm_provider="ollama",
            llm_base_url="http://localhost:11434",
            llm_model_name="qwen2.5:7b-instruct-q4",
            llm_temperature=0.3,
            llm_max_tokens=512,
            llm_json_mode=True,
        )
        session.add(config)
        session.commit()

    sent = {}

    def fake_send(self, chat_id: str, text: str) -> dict:
        sent["chat_id"] = chat_id
        sent["text"] = text
        return {"messageId": "fake"}

    monkeypatch.setattr(
        "apps.api.app.services.waha_client.WahaClient.send_text", fake_send
    )

    run_proactive_tick(now=now, calendar_tool=_FakeCalendarTool())

    assert sent == {}

    with SessionLocal() as session:
        event = session.query(ProactiveEvent).filter_by(trigger_type="habit_window").one()
        assert event.decision == "digested"
