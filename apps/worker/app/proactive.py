from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import logging
import math
import os
import unicodedata
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from apps.api.app.services.waha_client import WahaClient
from packages.agent_core.tools.calendar_tool import CalendarNotAuthorized, CalendarTool
from packages.agent_core.tools.google_oauth import OAuthConfigError
from packages.db.database import SessionLocal
from packages.db.models import (
    AssistantRequest,
    AutonomyRule,
    Contact,
    ConversationThread,
    Digest,
    Habit,
    HabitLog,
    HabitNudge,
    MemoryFact,
    ProactiveEvent,
    SystemConfig,
    Task,
)
from packages.habits.engine import HabitEngine, get_or_create_coaching_profile, record_nudge_sent
from packages.habits.nudges import build_nudge_message
from packages.habits.selector import NudgeStrategySelector
from packages.llm.client import load_llm_config
from packages.llm.text_client import TextLlmClient

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")
LOOKAHEAD_MINUTES = 120
TASK_DUE_SOON_MINUTES = 120
TASK_HIGH_PRIORITY = 3
REQUEST_DIGEST_MIN_PRIORITY = 70
THREAD_WAITING_HOURS = 3
HABIT_WINDOW_GRACE_MINUTES = 60
HABIT_STREAK_DAYS = 2
HABIT_PRIORITY_HIGH = 4

DEFAULT_CONFIG = {
    "quiet_hours_start": time(0, 0),
    "quiet_hours_end": time(9, 30),
    "strong_window_start": time(11, 0),
    "strong_window_end": time(19, 0),
    "daily_proactive_limit": 5,
    "maybe_cooldown_minutes": 240,
    "urgent_threshold": 80,
    "maybe_threshold": 50,
    "llm_provider": "ollama",
    "llm_base_url": os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
    "llm_model_name": "qwen2.5:7b-instruct-q4",
    "llm_temperature": 0.3,
    "llm_max_tokens": 512,
    "llm_json_mode": True,
}


@dataclass
class Candidate:
    trigger_type: str
    entity_id: str
    title: str
    score: int
    priority: int | None
    dedupe_key: str
    message: str
    strategy: str | None = None


@dataclass
class Decision:
    decision: str
    reason: str | None
    score: int


def run_proactive_tick(
    now: datetime | None = None,
    calendar_tool: CalendarTool | None = None,
    waha_client: WahaClient | None = None,
    llm_client: TextLlmClient | None = None,
    session_factory=SessionLocal,
) -> int:
    current_time = _ensure_timezone(now or datetime.now(TIMEZONE))
    tool = calendar_tool or CalendarTool()
    sent_count = 0

    with session_factory() as session:
        config = _get_or_create_config(session)
        autonomy_mode, _ = _get_autonomy_mode(session, current_time)
        chat_id = _resolve_chat_id(session)
        sent_today = _count_sent_today(session, current_time)

        candidates = []
        candidates.extend(_calendar_candidates(tool, current_time))
        candidates.extend(_task_candidates(session, current_time))
        candidates.extend(_thread_waiting_candidates(session, current_time))
        candidates.extend(_habit_candidates(session, current_time, config, llm_client))
        candidates.sort(key=lambda item: item.score, reverse=True)

        for candidate in candidates:
            if _has_dedupe(session, candidate.dedupe_key):
                continue

            in_cooldown = _sent_recently(
                session,
                candidate.trigger_type,
                current_time,
                config.maybe_cooldown_minutes,
            )
            decision = decide(
                candidate,
                current_time,
                config,
                autonomy_mode,
                sent_today,
                in_cooldown,
            )

            if candidate.trigger_type.startswith("habit_"):
                if _habits_autonomy_off(session, current_time):
                    decision = Decision("suppressed", "habits_off", decision.score)

            if decision.decision == "sent":
                if not chat_id:
                    _record_event(
                        session,
                        candidate,
                        decision="suppressed",
                        reason="no_contact",
                        sent_at=None,
                        created_at=current_time,
                    )
                    continue

                client = waha_client or WahaClient()
                try:
                    client.send_text(chat_id, candidate.message)
                except Exception as exc:
                    logger.warning("WAHA send_text failed: %s", exc.__class__.__name__)
                    _record_event(
                        session,
                        candidate,
                        decision="suppressed",
                        reason="send_failed",
                        sent_at=None,
                        created_at=current_time,
                    )
                    continue

                _record_event(
                    session,
                    candidate,
                    decision="sent",
                    reason=decision.reason,
                    sent_at=current_time,
                    created_at=current_time,
                )
                _record_habit_nudge(session, candidate, decision.decision, current_time)
                sent_today += 1
                sent_count += 1
                continue

            _record_event(
                session,
                candidate,
                decision=decision.decision,
                reason=decision.reason,
                sent_at=None,
                created_at=current_time,
            )
            _record_habit_nudge(session, candidate, decision.decision, current_time)

    return sent_count


def run_daily_digest(
    now: datetime | None = None,
    calendar_tool: CalendarTool | None = None,
    waha_client: WahaClient | None = None,
    session_factory=SessionLocal,
) -> int:
    current_time = _ensure_timezone(now or datetime.now(TIMEZONE))
    day = current_time.date()

    with session_factory() as session:
        existing = session.execute(select(Digest).where(Digest.day == day)).scalar_one_or_none()
        if existing and existing.sent_at is not None:
            return 0

        day_start = datetime.combine(day, time(0, 0), tzinfo=TIMEZONE)
        day_end = day_start + timedelta(days=1)
        events = (
            session.query(ProactiveEvent)
            .filter(
                ProactiveEvent.decision == "digested",
                ProactiveEvent.created_at >= day_start,
                ProactiveEvent.created_at < day_end,
            )
            .order_by(ProactiveEvent.created_at.asc())
            .all()
        )

        chat_id = _resolve_chat_id(session)
        if not chat_id:
            return 0

        request_lines = _build_request_digest_lines(session, chat_id)
        habit_lines = _build_habit_digest_lines(session, current_time)
        if not events and not request_lines and not habit_lines:
            return 0

        lines = _build_digest_lines(session, events, day_start, day_end, calendar_tool)
        content = _format_digest_message(lines, request_lines, habit_lines)

        client = waha_client or WahaClient()
        sent_at = None
        try:
            client.send_text(chat_id, content)
            sent_at = current_time
        except Exception as exc:
            logger.warning("WAHA digest send failed: %s", exc.__class__.__name__)

        if existing:
            existing.content = content
            existing.sent_at = sent_at
        else:
            session.add(Digest(day=day, content=content, sent_at=sent_at))
        session.commit()

    return 1


def decide(
    candidate: Candidate,
    now_local: datetime,
    config: SystemConfig,
    autonomy_mode: str,
    sent_today: int,
    in_cooldown: bool,
) -> Decision:
    score = candidate.score
    local_time = now_local.astimezone(TIMEZONE).time()

    if _in_quiet_hours(local_time, config) and score < config.urgent_threshold:
        return Decision("digested", "quiet_hours", score)

    if autonomy_mode in {"focus", "urgencies_only"} and score < config.urgent_threshold:
        return Decision("digested", "autonomy_mode", score)

    if score < config.maybe_threshold:
        return Decision("digested", "below_threshold", score)

    if score >= config.urgent_threshold:
        decision = Decision("sent", "urgent", score)
    else:
        if not _in_strong_window(local_time, config):
            return Decision("digested", "outside_strong_window", score)
        if in_cooldown:
            return Decision("digested", "cooldown", score)
        decision = Decision("sent", "maybe", score)

    if decision.decision == "sent" and sent_today >= config.daily_proactive_limit:
        return Decision("digested", "rate_limit", score)

    return decision


def _calendar_candidates(calendar_tool: CalendarTool, now: datetime) -> list[Candidate]:
    time_max = now + timedelta(minutes=LOOKAHEAD_MINUTES)
    try:
        events = calendar_tool.list_events(now, time_max)
    except (CalendarNotAuthorized, OAuthConfigError) as exc:
        logger.warning("Calendar unavailable: %s", exc.__class__.__name__)
        return []
    except Exception as exc:  # pragma: no cover - best-effort logging
        logger.warning("Calendar list failed: %s", exc.__class__.__name__)
        return []

    candidates: list[Candidate] = []
    for event in events:
        candidate = _build_calendar_candidate(event, now)
        if candidate:
            candidates.append(candidate)
    return candidates


def _build_calendar_candidate(event: dict[str, object], now: datetime) -> Candidate | None:
    event_id = str(event.get("id") or "")
    if not event_id:
        return None

    start_value = _parse_event_start(event.get("start"))
    if start_value is None:
        return None

    delta_minutes = (start_value.astimezone(TIMEZONE) - now).total_seconds() / 60
    if delta_minutes <= 0 or delta_minutes > 60:
        return None

    window, score = _calendar_window_score(delta_minutes)
    if window is None:
        return None

    title = str(event.get("summary") or "Sin titulo")
    folded = _fold_text(title)
    if "cliente" in folded or "flete" in folded:
        score += 10

    location = event.get("location")
    if not location:
        score += 5

    minutes_to_start = max(0, math.ceil(delta_minutes))
    message = (
        f"En {minutes_to_start} min tenes: *{title}*.\n"
        "Queres que revise algo o te recuerde mas tarde?"
    )

    dedupe_key = f"calendar:{event_id}:{window}"
    return Candidate(
        trigger_type="calendar_upcoming",
        entity_id=event_id,
        title=title,
        score=score,
        priority=None,
        dedupe_key=dedupe_key,
        message=message,
    )


def _calendar_window_score(delta_minutes: float) -> tuple[str | None, int]:
    if delta_minutes <= 10:
        return "tminus10", 90
    if delta_minutes <= 30:
        return "tminus30", 80
    if delta_minutes <= 60:
        return "tminus60", 70
    return None, 0


def _task_candidates(session, now: datetime) -> list[Candidate]:
    today = now.date()
    tasks = (
        session.query(Task)
        .filter(Task.due_date == today, Task.status != "done")
        .all()
    )
    candidates: list[Candidate] = []
    for task in tasks:
        score = 55
        if task.priority is not None and task.priority >= TASK_HIGH_PRIORITY:
            score += 15
        if task.due_at:
            due_at = _ensure_timezone(task.due_at)
            if timedelta(0) < (due_at - now) <= timedelta(minutes=TASK_DUE_SOON_MINUTES):
                score += 20

        title = task.title
        message = (
            f"Hoy vence: *{title}*. "
            "Queres que lo agende como bloque de 30 min?"
        )
        candidates.append(
            Candidate(
                trigger_type="task_due_today",
                entity_id=str(task.id),
                title=title,
                score=score,
                priority=task.priority,
                dedupe_key=f"task:{task.id}:due_today",
                message=message,
            )
        )

    return candidates


def _habit_candidates(
    session,
    now: datetime,
    config: SystemConfig,
    llm_client: TextLlmClient | None = None,
) -> list[Candidate]:
    engine = HabitEngine(session)
    habits = engine.list_habits(active_only=True)
    if not habits:
        return []
    if llm_client is None and os.getenv("HABIT_NUDGE_USE_LLM", "1") == "1":
        llm_client = TextLlmClient(load_llm_config(config))
    profile = get_or_create_coaching_profile(session)
    selector = NudgeStrategySelector(profile)
    candidates: list[Candidate] = []
    today = now.date()

    for habit in habits:
        if engine.habit_status_today(habit.id, today):
            continue
        if not engine.is_due_today(habit, now):
            continue

        trigger_type, trigger_bonus = _habit_trigger(habit, session, now)
        if not trigger_type:
            continue

        last_nudge = (
            session.query(HabitNudge)
            .filter(HabitNudge.habit_id == habit.id)
            .order_by(HabitNudge.ts.desc())
            .first()
        )
        choice = selector.select(habit, last_nudge)
        score = min(95, choice.score + trigger_bonus)

        message = build_nudge_message(habit, choice.strategy, profile, llm_client)
        dedupe_key = f"habit:{habit.id}:{trigger_type}:{today.isoformat()}"
        candidates.append(
            Candidate(
                trigger_type=trigger_type,
                entity_id=str(habit.id),
                title=habit.name,
                score=score,
                priority=habit.priority,
                dedupe_key=dedupe_key,
                message=message,
                strategy=choice.strategy,
            )
        )

    return candidates


def _habit_trigger(
    habit: Habit,
    session,
    now: datetime,
) -> tuple[str | None, int]:
    if habit.priority and habit.priority >= HABIT_PRIORITY_HIGH:
        last_done = _last_done_date(session, habit.id)
        if last_done is None or (now.date() - last_done).days >= HABIT_STREAK_DAYS:
            return "habit_streak_risk", 10

    if habit.schedule_type == "weekly" and habit.target_per_week:
        if _weekly_target_in_risk(session, habit, now):
            return "habit_weekly_risk", 5

    if _window_closing(habit, now):
        return "habit_window", 0

    return None, 0


def _window_closing(habit: Habit, now: datetime) -> bool:
    window_end = datetime.combine(now.date(), habit.window_end, tzinfo=TIMEZONE)
    window_start = datetime.combine(now.date(), habit.window_start, tzinfo=TIMEZONE)
    if now < window_start or now > window_end:
        return False
    remaining = window_end - now
    return remaining <= timedelta(minutes=HABIT_WINDOW_GRACE_MINUTES)


def _last_done_date(session, habit_id: int) -> date | None:
    log = (
        session.query(HabitLog)
        .filter(HabitLog.habit_id == habit_id, HabitLog.status.in_(["done", "partial"]))
        .order_by(HabitLog.date.desc())
        .first()
    )
    return log.date if log else None


def _weekly_target_in_risk(session, habit: Habit, now: datetime) -> bool:
    week_start = now.date() - timedelta(days=now.date().weekday())
    week_end = week_start + timedelta(days=7)
    done_count = (
        session.query(HabitLog)
        .filter(
            HabitLog.habit_id == habit.id,
            HabitLog.date >= week_start,
            HabitLog.date < week_end,
            HabitLog.status.in_(["done", "partial"]),
        )
        .count()
    )
    remaining_days = (week_end - now.date()).days
    remaining_possible = max(0, remaining_days)
    return habit.target_per_week > done_count + remaining_possible


def _thread_waiting_candidates(session, now: datetime) -> list[Candidate]:
    threshold = now - timedelta(hours=THREAD_WAITING_HOURS)
    threads = (
        session.query(ConversationThread, Contact)
        .join(Contact, ConversationThread.contact_id == Contact.id)
        .filter(
            ConversationThread.status == "waiting_me",
            ConversationThread.last_message_at <= threshold,
            Contact.trust_label.in_(["client", "provider", "cliente", "proveedor"]),
        )
        .all()
    )
    candidates: list[Candidate] = []
    for thread, contact in threads:
        contact_name = contact.display_name or contact.chat_id
        summary = thread.last_summary or "sin resumen"
        dedupe_key = f"thread_waiting_me:{thread.id}:{thread.last_message_at.isoformat()}"
        message = (
            f"Tenes pendiente responder a {contact_name}: {summary}. "
            "Queres que redacte respuesta?"
        )
        candidates.append(
            Candidate(
                trigger_type="thread_waiting_me",
                entity_id=str(thread.id),
                title=contact_name,
                score=80,
                priority=None,
                dedupe_key=dedupe_key,
                message=message,
            )
        )
    return candidates


def _build_digest_lines(
    session,
    events: Iterable[ProactiveEvent],
    day_start: datetime,
    day_end: datetime,
    calendar_tool: CalendarTool | None = None,
) -> list[str]:
    calendar_map = _calendar_digest_map(calendar_tool, day_start, day_end)
    task_ids: list[int] = []
    thread_ids: list[int] = []
    for event in events:
        if event.trigger_type != "task_due_today" or not event.entity_id:
            pass
        else:
            try:
                task_ids.append(int(event.entity_id))
            except ValueError:
                pass
        if event.trigger_type == "thread_waiting_me" and event.entity_id:
            try:
                thread_ids.append(int(event.entity_id))
            except ValueError:
                pass
    task_map = {}
    if task_ids:
        rows = session.query(Task).filter(Task.id.in_(task_ids)).all()
        task_map = {task.id: task.title for task in rows}

    thread_map: dict[int, str] = {}
    if thread_ids:
        rows = (
            session.query(ConversationThread, Contact)
            .join(Contact, ConversationThread.contact_id == Contact.id)
            .filter(ConversationThread.id.in_(thread_ids))
            .all()
        )
        for thread, contact in rows:
            name = contact.display_name or contact.chat_id
            summary = thread.last_summary or "sin resumen"
            thread_map[thread.id] = f"Pendiente: {name} ({summary})"

    lines: list[str] = []
    for event in events:
        if event.trigger_type.startswith("habit_"):
            continue
        if event.trigger_type == "calendar_upcoming":
            label = calendar_map.get(event.entity_id or "", f"Evento: {event.entity_id}")
        elif event.trigger_type == "task_due_today":
            title = None
            if event.entity_id:
                try:
                    title = task_map.get(int(event.entity_id))
                except ValueError:
                    title = None
            label = f"Tarea: {title or event.entity_id}"
        elif event.trigger_type == "thread_waiting_me":
            label = "Pendiente: conversacion"
            if event.entity_id:
                try:
                    label = thread_map.get(int(event.entity_id), label)
                except ValueError:
                    pass
        else:
            label = f"{event.trigger_type}: {event.entity_id}"
        lines.append(label)
    return lines


def _calendar_digest_map(
    calendar_tool: CalendarTool | None, day_start: datetime, day_end: datetime
) -> dict[str, str]:
    tool = calendar_tool or CalendarTool()
    try:
        events = tool.list_events(day_start, day_end)
    except Exception as exc:
        logger.warning("Calendar digest list failed: %s", exc.__class__.__name__)
        return {}

    mapping: dict[str, str] = {}
    for event in events:
        event_id = event.get("id")
        if not event_id:
            continue
        title = event.get("summary") or "Sin titulo"
        start_value = _parse_event_start(event.get("start"))
        if start_value and "T" in str(event.get("start")):
            time_label = start_value.astimezone(TIMEZONE).strftime("%H:%M")
            mapping[str(event_id)] = f"Evento: {title} ({time_label})"
        else:
            mapping[str(event_id)] = f"Evento: {title} (todo el dia)"
    return mapping


def _format_digest_message(
    lines: list[str], request_lines: list[str], habit_lines: list[str]
) -> str:
    visible = lines[:10]
    message_lines = ["Resumen de hoy:"]
    for line in visible:
        message_lines.append(f"- {line}")
    remaining = len(lines) - len(visible)
    if remaining > 0:
        message_lines.append(f"y {remaining} mas")
    if request_lines:
        message_lines.append("Para mejorar:")
        for line in request_lines:
            message_lines.append(f"- {line}")
    if habit_lines:
        message_lines.append("Habitos:")
        for line in habit_lines[:5]:
            message_lines.append(f"- {line}")
    return "\n".join(message_lines)


def _build_request_digest_lines(session, chat_id: str) -> list[str]:
    requests = (
        session.query(AssistantRequest)
        .filter(
            AssistantRequest.status == "open",
            AssistantRequest.priority >= REQUEST_DIGEST_MIN_PRIORITY,
            AssistantRequest.context["chat_id"].astext == chat_id,
        )
        .order_by(AssistantRequest.priority.desc(), AssistantRequest.created_at.asc())
        .limit(3)
        .all()
    )
    lines: list[str] = []
    for request in requests:
        line = _request_digest_label(request)
        if line:
            lines.append(line)
    return lines


def _build_habit_digest_lines(session, now: datetime) -> list[str]:
    engine = HabitEngine(session)
    if not engine.list_habits(active_only=True):
        return []
    summary = engine.daily_summary(now)
    done = ", ".join(summary["done"]) or "-"
    pending = ", ".join(summary["pending"]) or "-"
    streaks = ", ".join(summary["streaks"]) or "-"
    lines = [
        f"Cumplidos: {done}",
        f"Pendientes: {pending}",
        f"Rachas: {streaks}",
    ]
    return lines[:5]


def _request_digest_label(request: AssistantRequest) -> str:
    key = request.key
    labels = {
        "calendar_auth": "Falta autorizar Google Calendar.",
        "default_barbershop": "Falta definir la peluqueria de siempre.",
        "preferred_event_duration_minutes": "Falta definir la duracion preferida.",
        "diet_store_address": "Falta la direccion de tu dietetica.",
        "user_chat_id": "Falta definir el chat principal para proactivos.",
    }
    label = labels.get(key)
    if label:
        return label
    prompt = (request.prompt or "").split("?")[0].strip()
    return prompt or f"Falta: {key}"


def _get_or_create_config(session) -> SystemConfig:
    config = session.query(SystemConfig).order_by(SystemConfig.id.asc()).first()
    if config:
        return config

    config = SystemConfig(**DEFAULT_CONFIG)
    session.add(config)
    session.commit()
    return config


def _get_autonomy_mode(session, now_local: datetime) -> tuple[str, datetime | None]:
    rules = (
        session.query(AutonomyRule)
        .filter(AutonomyRule.scope == "global")
        .order_by(AutonomyRule.created_at.desc())
        .all()
    )
    now_utc = now_local.astimezone(timezone.utc)
    for rule in rules:
        if rule.until_at and rule.until_at < now_utc:
            continue
        return rule.mode, rule.until_at
    return "normal", None


def _resolve_chat_id(session) -> str | None:
    explicit = os.getenv("USER_CHAT_ID") or os.getenv("PROACTIVE_CHAT_ID")
    if explicit:
        return explicit
    fact = (
        session.query(MemoryFact)
        .filter(
            MemoryFact.subject == "user",
            MemoryFact.key == "user_chat_id",
            MemoryFact.confidence >= 70,
        )
        .one_or_none()
    )
    if fact:
        return fact.value
    contact = session.query(Contact).order_by(Contact.created_at.desc()).first()
    if contact is None:
        return None
    return contact.chat_id


def _count_sent_today(session, now_local: datetime) -> int:
    day_start = datetime.combine(now_local.date(), time(0, 0), tzinfo=TIMEZONE)
    day_end = day_start + timedelta(days=1)
    return (
        session.query(ProactiveEvent)
        .filter(
            ProactiveEvent.sent_at >= day_start,
            ProactiveEvent.sent_at < day_end,
        )
        .count()
    )


def _sent_recently(
    session, trigger_type: str, now_local: datetime, cooldown_minutes: int
) -> bool:
    since = now_local - timedelta(minutes=cooldown_minutes)
    return (
        session.query(ProactiveEvent)
        .filter(
            ProactiveEvent.trigger_type == trigger_type,
            ProactiveEvent.decision == "sent",
            ProactiveEvent.sent_at >= since,
        )
        .first()
        is not None
    )


def _has_dedupe(session, dedupe_key: str) -> bool:
    return session.query(ProactiveEvent.id).filter_by(dedupe_key=dedupe_key).first() is not None


def _record_event(
    session,
    candidate: Candidate,
    decision: str,
    reason: str | None,
    sent_at: datetime | None,
    created_at: datetime | None,
) -> None:
    record = ProactiveEvent(
        trigger_type=candidate.trigger_type,
        dedupe_key=candidate.dedupe_key,
        entity_id=candidate.entity_id,
        priority=candidate.priority,
        score=candidate.score,
        decision=decision,
        reason=reason,
        sent_at=sent_at,
        created_at=created_at,
    )
    session.add(record)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()


def _record_habit_nudge(
    session,
    candidate: Candidate,
    decision: str,
    now: datetime,
) -> None:
    if not candidate.trigger_type.startswith("habit_"):
        return
    if not candidate.strategy:
        strategy = "micro_action"
    else:
        strategy = candidate.strategy
    try:
        habit_id = int(candidate.entity_id)
    except ValueError:
        return
    record = HabitNudge(
        habit_id=habit_id,
        ts=now,
        strategy=strategy,
        score=candidate.score,
        decision=decision,
        message_text=candidate.message,
    )
    session.add(record)
    if decision == "sent":
        record_nudge_sent(session, strategy)
    session.commit()


def _in_quiet_hours(local_time: time, config: SystemConfig) -> bool:
    return config.quiet_hours_start <= local_time < config.quiet_hours_end


def _in_strong_window(local_time: time, config: SystemConfig) -> bool:
    return config.strong_window_start <= local_time < config.strong_window_end


def _habits_autonomy_off(session, now_local: datetime) -> bool:
    rules = (
        session.query(AutonomyRule)
        .filter(AutonomyRule.scope == "habits")
        .order_by(AutonomyRule.created_at.desc())
        .all()
    )
    now_utc = now_local.astimezone(timezone.utc)
    for rule in rules:
        if rule.until_at and rule.until_at < now_utc:
            continue
        return rule.mode != "on"
    return False


def _parse_event_start(value: object | None) -> datetime | None:
    if not value:
        return None
    value_str = str(value)
    if "T" not in value_str:
        try:
            day = date.fromisoformat(value_str)
        except ValueError:
            return None
        return datetime.combine(day, time(0, 0), tzinfo=TIMEZONE)

    value_str = value_str.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value_str)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=TIMEZONE)
    return parsed


def _fold_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower().strip()


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=TIMEZONE)
    return value.astimezone(TIMEZONE)
