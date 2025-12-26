from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from packages.db.models import CoachingProfile, Habit, HabitLog, HabitNudge

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")

STATUS_DONE = "done"
STATUS_SKIPPED = "skipped"
STATUS_PARTIAL = "partial"

SUCCESS_STATUSES = {STATUS_DONE, STATUS_PARTIAL}


def get_or_create_coaching_profile(session) -> CoachingProfile:
    profile = session.query(CoachingProfile).order_by(CoachingProfile.id.asc()).first()
    if profile:
        return profile
    profile = CoachingProfile(intensity="medium", style="formal")
    session.add(profile)
    session.flush()
    return profile


class HabitEngine:
    def __init__(self, session) -> None:
        self.session = session

    def create_habit(
        self,
        name: str,
        description: str | None,
        schedule_type: str,
        target_per_week: int | None,
        days_of_week: list[int] | None,
        window_start: time,
        window_end: time,
        min_version_text: str,
        priority: int,
        active: bool = True,
    ) -> Habit:
        habit = Habit(
            name=name,
            description=description,
            schedule_type=schedule_type,
            target_per_week=target_per_week,
            days_of_week=days_of_week,
            window_start=window_start,
            window_end=window_end,
            min_version_text=min_version_text,
            priority=priority,
            active=active,
        )
        self.session.add(habit)
        self.session.flush()
        return habit

    def list_habits(self, active_only: bool = True) -> list[Habit]:
        query = self.session.query(Habit)
        if active_only:
            query = query.filter(Habit.active.is_(True))
        return query.order_by(Habit.created_at.asc()).all()

    def find_habits_by_name(self, query_text: str, active_only: bool = True) -> list[Habit]:
        query = self.session.query(Habit).filter(Habit.name.ilike(f"%{query_text}%"))
        if active_only:
            query = query.filter(Habit.active.is_(True))
        return query.order_by(Habit.created_at.asc()).all()

    def habit_status_today(self, habit_id: int, today: date | None = None) -> HabitLog | None:
        target_date = today or datetime.now(TIMEZONE).date()
        return (
            self.session.query(HabitLog)
            .filter(HabitLog.habit_id == habit_id, HabitLog.date == target_date)
            .one_or_none()
        )

    def habits_due_today(self, now: datetime) -> list[Habit]:
        today = now.date()
        habits = self.list_habits(active_only=True)
        due: list[Habit] = []
        for habit in habits:
            if self.habit_status_today(habit.id, today):
                continue
            if self.is_due_today(habit, now):
                due.append(habit)
        return due

    def log_done(self, habit_id: int, now: datetime | None = None, note: str | None = None) -> HabitLog:
        current = _ensure_local(now or datetime.now(TIMEZONE))
        log, was_success = self._upsert_log(habit_id, current.date(), STATUS_DONE, note)
        if not was_success:
            _record_nudge_success(self.session, habit_id, current)
        return log

    def log_skip(self, habit_id: int, now: datetime | None = None, note: str | None = None) -> HabitLog:
        current = _ensure_local(now or datetime.now(TIMEZONE))
        log, _was_success = self._upsert_log(habit_id, current.date(), STATUS_SKIPPED, note)
        return log

    def log_partial(
        self, habit_id: int, now: datetime | None = None, note: str | None = None
    ) -> HabitLog:
        current = _ensure_local(now or datetime.now(TIMEZONE))
        log, was_success = self._upsert_log(habit_id, current.date(), STATUS_PARTIAL, note)
        if not was_success:
            _record_nudge_success(self.session, habit_id, current)
        return log

    def daily_summary(self, now: datetime) -> dict[str, list[str]]:
        current = _ensure_local(now)
        done: list[str] = []
        pending: list[str] = []
        streaks: list[str] = []
        for habit in self.list_habits(active_only=True):
            log = self.habit_status_today(habit.id, current.date())
            if log and log.status in SUCCESS_STATUSES:
                done.append(habit.name)
            elif self.is_due_today(habit, current):
                pending.append(habit.name)
            streak = self.current_streak(habit.id, current)
            if streak >= 2:
                streaks.append(f"{habit.name} {streak}d")
        return {"done": done, "pending": pending, "streaks": streaks}

    def weekly_report(self, now: datetime) -> list[str]:
        current = _ensure_local(now)
        week_start, week_end = _week_bounds(current.date())
        habits = self.list_habits(active_only=True)
        lines: list[str] = []
        for habit in habits:
            done_count = (
                self.session.query(HabitLog)
                .filter(
                    HabitLog.habit_id == habit.id,
                    HabitLog.date >= week_start,
                    HabitLog.date < week_end,
                    HabitLog.status.in_(SUCCESS_STATUSES),
                )
                .count()
            )
            streak = self.current_streak(habit.id, current)
            target = habit.target_per_week
            target_label = f"{done_count}/{target}" if target else str(done_count)
            lines.append(f"{habit.name}: {target_label}, racha {streak}d")
        return lines

    def current_streak(self, habit_id: int, now: datetime) -> int:
        current = _ensure_local(now)
        day_cursor = current.date()
        streak = 0
        while True:
            log = (
                self.session.query(HabitLog)
                .filter(HabitLog.habit_id == habit_id, HabitLog.date == day_cursor)
                .one_or_none()
            )
            if log and log.status in SUCCESS_STATUSES:
                streak += 1
                day_cursor -= timedelta(days=1)
                continue
            break
        return streak

    def is_due_today(self, habit: Habit, now: datetime) -> bool:
        current_date = now.date()
        if habit.schedule_type == "daily":
            return True
        if habit.schedule_type == "scheduled":
            if not habit.days_of_week:
                return True
            return current_date.weekday() in habit.days_of_week
        if habit.schedule_type == "weekly":
            if habit.target_per_week is None:
                return True
            week_start, week_end = _week_bounds(current_date)
            done_count = (
                self.session.query(HabitLog)
                .filter(
                    HabitLog.habit_id == habit.id,
                    HabitLog.date >= week_start,
                    HabitLog.date < week_end,
                    HabitLog.status.in_(SUCCESS_STATUSES),
                )
                .count()
            )
            return done_count < habit.target_per_week
        return False

    def _upsert_log(
        self, habit_id: int, target_date: date, status: str, note: str | None
    ) -> tuple[HabitLog, bool]:
        log = (
            self.session.query(HabitLog)
            .filter(HabitLog.habit_id == habit_id, HabitLog.date == target_date)
            .one_or_none()
        )
        if log:
            was_success = log.status in SUCCESS_STATUSES
            log.status = status
            log.note = note
            return log, was_success
        log = HabitLog(habit_id=habit_id, date=target_date, status=status, note=note)
        self.session.add(log)
        self.session.flush()
        return log, False


def record_nudge_sent(session, strategy: str) -> None:
    profile = get_or_create_coaching_profile(session)
    _update_strategy_stats(profile, strategy, sent_inc=1)


def _record_nudge_success(session, habit_id: int, now: datetime) -> None:
    day_start = datetime.combine(now.date(), time(0, 0), tzinfo=TIMEZONE)
    nudge = (
        session.query(HabitNudge)
        .filter(
            HabitNudge.habit_id == habit_id,
            HabitNudge.decision == "sent",
            HabitNudge.ts >= day_start,
        )
        .order_by(HabitNudge.ts.desc())
        .first()
    )
    if not nudge:
        return
    profile = get_or_create_coaching_profile(session)
    _update_strategy_stats(profile, nudge.strategy, done_inc=1)


def _update_strategy_stats(
    profile: CoachingProfile, strategy: str, sent_inc: int = 0, done_inc: int = 0
) -> None:
    data = profile.what_works or {}
    strategies = data.get("strategies") or {}
    entry = strategies.get(strategy) or {"sent": 0, "done_after": 0}
    entry["sent"] = max(0, int(entry.get("sent", 0)) + sent_inc)
    entry["done_after"] = max(0, int(entry.get("done_after", 0)) + done_inc)
    strategies[strategy] = entry
    data["strategies"] = strategies
    profile.what_works = data


def _week_bounds(today: date) -> tuple[date, date]:
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    return week_start, week_end


def _ensure_local(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=TIMEZONE)
    return value.astimezone(TIMEZONE)
