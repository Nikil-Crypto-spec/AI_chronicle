"""Summarisation: prompt -> LLM -> structured SummarisedItem (with fallback)."""

from __future__ import annotations

import json
import logging
import re
import textwrap
from typing import Optional

from .config import PromptsFile
from .llm.base import LLMClient
from .models import RankedItem, SummarisedItem

log = logging.getLogger(__name__)

_MAX_BODY_CHARS = 4000


def _truncate(text: str, limit: int = _MAX_BODY_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "..."


def _extract_json(raw: str) -> Optional[dict]:
    """Tolerate models that wrap JSON in code fences or add preamble."""
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _fallback(ranked: RankedItem) -> SummarisedItem:
    item = ranked.item
    abstract = (item.abstract or "").strip() or "(No abstract available.)"
    tldr = textwrap.shorten(abstract, width=240, placeholder="...")
    return SummarisedItem(
        ranked=ranked,
        tldr=tldr,
        why_it_matters="",
        key_points=[],
        used_fallback=True,
    )


def summarise_one(
    ranked: RankedItem,
    body_text: str,
    llm: LLMClient,
    prompts: PromptsFile,
    *,
    max_retries: int = 1,
) -> SummarisedItem:
    item = ranked.item
    body = body_text.strip() or item.abstract.strip()
    if not body:
        log.info("No body text for %s; using fallback summary.", item.url)
        return _fallback(ranked)

    user_prompt = prompts.user.format(
        title=item.title,
        source=item.source,
        published=item.published_at.isoformat() if item.published_at else "unknown",
        url=item.url,
        body=_truncate(body),
    )

    attempt = 0
    while attempt <= max_retries:
        try:
            raw = llm.complete(prompts.system, user_prompt, json_mode=True)
        except Exception as exc:
            log.warning(
                "LLM call failed for %s on attempt %d: %s", item.url, attempt + 1, exc
            )
            attempt += 1
            continue

        parsed = _extract_json(raw)
        if parsed is None:
            log.warning(
                "LLM returned non-JSON for %s on attempt %d (len=%d)",
                item.url, attempt + 1, len(raw),
            )
            attempt += 1
            continue

        tldr = (parsed.get("tldr") or "").strip()
        why = (parsed.get("why_it_matters") or "").strip()
        key_points_raw = parsed.get("key_points") or []
        key_points = [str(p).strip() for p in key_points_raw if str(p).strip()]
        if not tldr:
            log.warning("LLM JSON missing tldr for %s; retrying.", item.url)
            attempt += 1
            continue

        return SummarisedItem(
            ranked=ranked,
            tldr=tldr,
            why_it_matters=why,
            key_points=key_points[:4],
            used_fallback=False,
        )

    log.info("Falling back to abstract for %s after retries.", item.url)
    return _fallback(ranked)


def summarise_all(
    ranked_items: list[RankedItem],
    bodies: dict[str, str],
    llm: LLMClient,
    prompts: PromptsFile,
) -> list[SummarisedItem]:
    out: list[SummarisedItem] = []
    for r in ranked_items:
        body = bodies.get(r.item.url, "")
        out.append(summarise_one(r, body, llm, prompts))
    fallback_count = sum(1 for s in out if s.used_fallback)
    log.info(
        "Summarised %d items (%d fallback, %d via LLM)",
        len(out),
        fallback_count,
        len(out) - fallback_count,
    )
    return out
