from datetime import datetime, time
from zoneinfo import ZoneInfo

from packages.db.database import SessionLocal
from packages.db.models import CoachingProfile, Habit, HabitNudge
from packages.habits.engine import HabitEngine, STATUS_DONE, STATUS_SKIPPED
from packages.habits.selector import NudgeStrategySelector

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


def test_habit_due_today_daily() -> None:
    now = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
    with SessionLocal() as session:
        engine = HabitEngine(session)
        engine.create_habit(
            name="Caminar",
            description=None,
            schedule_type="daily",
            target_per_week=None,
            days_of_week=None,
            window_start=time(9, 0),
            window_end=time(20, 0),
            min_version_text="Caminar 5 min",
            priority=3,
        )
        session.commit()

        due = engine.habits_due_today(now)
        assert len(due) == 1
        assert due[0].name == "Caminar"


def test_strategy_selector_avoids_repeat() -> None:
    profile = CoachingProfile(intensity="low", style="formal", what_works=None)
    habit = Habit(
        name="Leer",
        description=None,
        schedule_type="daily",
        target_per_week=None,
        days_of_week=None,
        window_start=time(9, 0),
        window_end=time(20, 0),
        min_version_text="Leer 5 min",
        priority=3,
        active=True,
    )
    last_nudge = HabitNudge(
        habit_id=1,
        ts=datetime(2025, 1, 1, 10, 0, tzinfo=TIMEZONE),
        strategy="micro_action",
        score=60,
        decision="sent",
        message_text="x",
    )
    choice = NudgeStrategySelector(profile).select(habit, last_nudge)
    assert choice.strategy == "frictionless"


def test_log_done_and_skip() -> None:
    now = datetime(2025, 1, 2, 12, 0, tzinfo=TIMEZONE)
    with SessionLocal() as session:
        engine = HabitEngine(session)
        habit = engine.create_habit(
            name="Escribir",
            description=None,
            schedule_type="daily",
            target_per_week=None,
            days_of_week=None,
            window_start=time(9, 0),
            window_end=time(20, 0),
            min_version_text="Escribir 5 min",
            priority=3,
        )
        engine.log_done(habit.id, now=now)
        log = engine.habit_status_today(habit.id, today=now.date())
        assert log is not None
        assert log.status == STATUS_DONE

        habit2 = engine.create_habit(
            name="Ordenar",
            description=None,
            schedule_type="daily",
            target_per_week=None,
            days_of_week=None,
            window_start=time(9, 0),
            window_end=time(20, 0),
            min_version_text="Ordenar 5 min",
            priority=2,
        )
        engine.log_skip(habit2.id, now=now)
        log2 = engine.habit_status_today(habit2.id, today=now.date())
        assert log2 is not None
        assert log2.status == STATUS_SKIPPED
