"""LLM client protocol used by the summariser."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Minimal completion interface. Implementations should be thread-safe to
    construct but are called sequentially by the pipeline."""

    name: str

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = True,
        temperature: float = 0.2,
        max_tokens: int = 600,
    ) -> str:
        """Return the assistant's text response. May raise on transport errors;
        the caller is expected to catch and decide whether to retry / fallback.
        """
        ...
