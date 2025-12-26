from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

from packages.db.models import SystemConfig
from packages.llm.schema import PlannerOutput, fallback_output

logger = logging.getLogger(__name__)

MODEL_NAME = "qwen2.5:7b-instruct-q4"


@dataclass
class LlmConfig:
    provider: str
    base_url: str
    model_name: str
    temperature: float
    max_tokens: int
    json_mode: bool


class LlmClient:
    def __init__(self, config: LlmConfig) -> None:
        self.config = config

    def generate_structured(
        self, system_prompt: str, user_input: str, context: str
    ) -> PlannerOutput:
        if self.config.provider != "ollama":
            return fallback_output()

        payload = {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _build_user_prompt(user_input, context)},
            ],
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }
        if self.config.json_mode:
            payload["format"] = "json"

        try:
            response = httpx.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            parsed = json.loads(content)
            return PlannerOutput.parse_obj(parsed)
        except Exception as exc:
            logger.warning("LLM generate failed: %s", exc.__class__.__name__)
            return fallback_output()


def load_llm_config(config: SystemConfig) -> LlmConfig:
    return LlmConfig(
        provider=config.llm_provider,
        base_url=config.llm_base_url,
        model_name=MODEL_NAME,
        temperature=_clamp_temperature(float(config.llm_temperature)),
        max_tokens=int(config.llm_max_tokens),
        json_mode=bool(config.llm_json_mode),
    )


def _build_user_prompt(user_input: str, context: str) -> str:
    return f"Usuario: {user_input}\n\nContexto:\n{context}"


def _clamp_temperature(value: float) -> float:
    if value < 0.2:
        return 0.2
    if value > 0.5:
        return 0.5
    return value
