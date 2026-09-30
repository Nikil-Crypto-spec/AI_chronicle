"""Pick an LLM backend based on settings or an explicit override."""

from __future__ import annotations

import logging
from typing import Literal

from ..config import Settings
from .base import LLMClient
from .copilot import CopilotLLM
from .local import LocalLLM

log = logging.getLogger(__name__)

Backend = Literal["local", "copilot"]


def build_llm(settings: Settings, override: Backend | None = None) -> LLMClient:
    backend: Backend = override or settings.llm_backend  # type: ignore[assignment]

    if backend == "local":
        log.info(
            "LLM backend: local (Ollama at %s, model=%s)",
            settings.ollama_base_url,
            settings.ollama_model,
        )
        return LocalLLM(settings.ollama_base_url, settings.ollama_model)

    if backend == "copilot":
        log.info(
            "LLM backend: copilot (Azure OpenAI deployment=%s)",
            settings.copilot_deployment,
        )
        return CopilotLLM(
            endpoint=settings.copilot_endpoint,
            api_key=settings.copilot_api_key,
            deployment=settings.copilot_deployment,
            api_version=settings.copilot_api_version,
        )

    raise ValueError(f"Unknown LLM backend: {backend!r}")
