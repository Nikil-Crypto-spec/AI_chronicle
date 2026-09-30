"""Copilot backend = Azure OpenAI deployment in your Microsoft tenant.

The official `openai` client supports Azure OpenAI via `AzureOpenAI`. That is
what we use here. If your "Copilot" turns out to be a different Microsoft
endpoint, replace this class - the rest of the pipeline only depends on the
`LLMClient` protocol.
"""

from __future__ import annotations

import logging

from openai import AzureOpenAI

log = logging.getLogger(__name__)


class CopilotLLM:
    name = "copilot-azure-openai"

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str = "2024-06-01",
    ) -> None:
        if not endpoint or not api_key:
            raise ValueError(
                "CopilotLLM requires COPILOT_ENDPOINT and COPILOT_API_KEY in the environment."
            )
        self.deployment = deployment
        self._client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = True,
        temperature: float = 0.2,
        max_tokens: int = 600,
    ) -> str:
        kwargs: dict = {
            "model": self.deployment,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        return (choice.message.content or "").strip()
