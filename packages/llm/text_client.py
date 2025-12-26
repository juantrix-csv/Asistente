from __future__ import annotations

import logging

import httpx

from packages.llm.client import LlmConfig

logger = logging.getLogger(__name__)


class TextLlmClient:
    def __init__(self, config: LlmConfig) -> None:
        self.config = config

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        if self.config.provider != "ollama":
            return ""
        payload = {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }
        try:
            response = httpx.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return str(data.get("message", {}).get("content", "")).strip()
        except Exception as exc:
            logger.warning("LLM text generate failed: %s", exc.__class__.__name__)
            return ""
