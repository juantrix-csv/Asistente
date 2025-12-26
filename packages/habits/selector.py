from __future__ import annotations

from dataclasses import dataclass

from packages.db.models import CoachingProfile, Habit, HabitNudge


ALLOWED_BY_INTENSITY = {
    "low": ("micro_action", "frictionless"),
    "medium": ("micro_action", "frictionless", "reframe"),
    "high": ("micro_action", "frictionless", "reframe", "contract", "humor"),
}


@dataclass(frozen=True)
class StrategyChoice:
    strategy: str
    score: int


class NudgeStrategySelector:
    def __init__(self, profile: CoachingProfile) -> None:
        self.profile = profile

    def select(self, habit: Habit, last_nudge: HabitNudge | None) -> StrategyChoice:
        intensity = (self.profile.intensity or "medium").lower()
        allowed = list(ALLOWED_BY_INTENSITY.get(intensity, ALLOWED_BY_INTENSITY["medium"]))
        last_strategy = last_nudge.strategy if last_nudge else None
        if last_strategy in allowed and len(allowed) > 1:
            allowed.remove(last_strategy)

        base_score = 50 + max(1, min(habit.priority, 5)) * 5
        best_strategy = allowed[0]
        best_score = base_score + self._adjust_for_what_works(best_strategy)

        for strategy in allowed[1:]:
            score = base_score + self._adjust_for_what_works(strategy)
            if score > best_score:
                best_score = score
                best_strategy = strategy

        best_score = max(40, min(95, best_score))
        return StrategyChoice(strategy=best_strategy, score=best_score)

    def _adjust_for_what_works(self, strategy: str) -> int:
        data = self.profile.what_works or {}
        strategies = data.get("strategies") or {}
        entry = strategies.get(strategy) or {}
        sent = int(entry.get("sent", 0))
        done = int(entry.get("done_after", 0))
        if sent < 3:
            return 0
        success_rate = done / max(sent, 1)
        if success_rate >= 0.6:
            return 5
        if success_rate <= 0.3:
            return -5
        return 0
