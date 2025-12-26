from __future__ import annotations

from packages.db.models import CoachingProfile, Habit
from packages.llm.text_client import TextLlmClient


def build_nudge_message(
    habit: Habit,
    strategy: str,
    profile: CoachingProfile,
    llm_client: TextLlmClient | None = None,
) -> str:
    base_message = _template_message(habit, strategy, profile)
    if llm_client is None:
        return base_message
    system_prompt = (
        "Sos una secretaria profesional con empuje. "
        "Redacta un recordatorio breve (max 2 frases) sin juzgar ni manipular. "
        "No des consejos medicos ni psicologicos. "
        "Devuelve solo el mensaje final, sin markdown extra."
    )
    min_version = habit.min_version_text or habit.name
    user_prompt = (
        f"Habito: {habit.name}\n"
        f"Estrategia: {strategy}\n"
        f"Version minima: {min_version}\n"
        f"Estilo: {profile.style}\n"
        "Incluir una pregunta corta al final."
    )
    rewritten = llm_client.generate_text(system_prompt, user_prompt)
    if not rewritten:
        return base_message
    return rewritten.strip()


def _template_message(habit: Habit, strategy: str, profile: CoachingProfile) -> str:
    min_version = habit.min_version_text or habit.name
    tone = (profile.style or "formal").lower()
    prefix = _tone_prefix(tone)
    if strategy == "micro_action":
        return f"{prefix}Hacemos la version minima: {min_version}? Queres que lo marque como hecho?"
    if strategy == "frictionless":
        return f"{prefix}Plan rapido: {min_version}. Te lo marco cuando lo hagas?"
    if strategy == "reframe":
        return f"{prefix}Un paso chico mantiene el habito: {min_version}. Lo hacemos ahora?"
    if strategy == "contract":
        return f"{prefix}Te propongo un acuerdo: {min_version} y listo por hoy. Te sirve?"
    if strategy == "humor":
        return f"{prefix}Modo express: {min_version}. Dos minutos y seguimos, te va?"
    return f"{prefix}Recordatorio: {habit.name}. Queres hacerlo ahora?"


def _tone_prefix(style: str) -> str:
    if style == "directo":
        return ""
    if style == "humor":
        return "Mini desafio: "
    return "Buen dia. "
