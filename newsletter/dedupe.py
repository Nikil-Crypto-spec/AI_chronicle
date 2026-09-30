"""Cross-source deduplication: canonical URL + fuzzy title match."""

from __future__ import annotations

import logging
from urllib.parse import urlparse, urlunparse

from rapidfuzz import fuzz

from .models import RawItem

log = logging.getLogger(__name__)

_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "ref_src", "WT.mc_id", "_ga",
}

_FUZZY_THRESHOLD = 92


def _canonical_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        return url.lower().strip()
    cleaned = parsed._replace(query="", fragment="")
    out = urlunparse(cleaned).rstrip("/").lower()
    return out


def dedupe(items: list[RawItem]) -> list[RawItem]:
    """Drop duplicates by canonical URL, then by fuzzy title match (>=92)."""
    if not items:
        return []

    by_url: dict[str, RawItem] = {}
    for item in items:
        key = _canonical_url(item.url)
        existing = by_url.get(key)
        if existing is None:
            by_url[key] = item
            continue
        if len(item.abstract) > len(existing.abstract):
            by_url[key] = item

    url_unique = list(by_url.values())

    kept: list[RawItem] = []
    for item in url_unique:
        match_idx = -1
        for idx, prior in enumerate(kept):
            score = fuzz.token_set_ratio(item.title, prior.title)
            if score >= _FUZZY_THRESHOLD:
                match_idx = idx
                break
        if match_idx == -1:
            kept.append(item)
        else:
            prior = kept[match_idx]
            if len(item.abstract) > len(prior.abstract):
                kept[match_idx] = item

    dropped = len(items) - len(kept)
    if dropped:
        log.info("Dedupe: %d -> %d (%d duplicates removed)", len(items), len(kept), dropped)
    return kept
