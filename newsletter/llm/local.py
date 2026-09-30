"""Local LLM via Ollama's HTTP API."""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


class LocalLLM:
    """Client for an Ollama server (POST /api/chat)."""

    name = "local-ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.Client(timeout=timeout)

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = True,
        temperature: float = 0.2,
        max_tokens: int = 600,
    ) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if json_mode:
            payload["format"] = "json"

        url = f"{self.base_url}/api/chat"
        log.debug("Ollama request to %s (model=%s)", url, self.model)
        resp = self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        message = data.get("message") or {}
        return (message.get("content") or "").strip()

    def close(self) -> None:
        self._client.close()
