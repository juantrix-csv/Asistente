from __future__ import annotations

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)


class WahaClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        retries: int | None = None,
        session: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("WAHA_BASE_URL") or "http://waha:3000").rstrip(
            "/"
        )
        self.api_key = api_key or os.getenv("WAHA_API_KEY")
        self.timeout = timeout or float(os.getenv("WAHA_TIMEOUT", "5"))
        self.retries = retries if retries is not None else int(os.getenv("WAHA_RETRIES", "2"))
        self.session = session or "default"

    def send_text(self, chat_id: str, text: str) -> dict:
        url = f"{self.base_url}/api/sendText"
        payload = {"chatId": chat_id, "text": text, "session": self.session}
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        for attempt in range(self.retries + 1):
            try:
                response = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                try:
                    return response.json()
                except ValueError:
                    return {"status_code": response.status_code, "text": response.text}
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                logger.warning(
                    "WAHA send_text failed (attempt %s/%s): %s",
                    attempt + 1,
                    self.retries + 1,
                    exc.__class__.__name__,
                )
                if attempt >= self.retries:
                    raise
                time.sleep(0.3 * (attempt + 1))

        return {"status": "unknown"}
