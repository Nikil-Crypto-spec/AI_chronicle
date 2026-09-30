"""Polite full-text fetch for items whose abstract is too thin to summarise."""

from __future__ import annotations

import logging
import time

import httpx
from bs4 import BeautifulSoup
from readability import Document

from .config import Settings
from .ssl_compat import build_httpx_client

log = logging.getLogger(__name__)

_USER_AGENT = (
    "newsletter-generator/0.1 (+local; respects robots.txt; contact: local user)"
)
_MIN_ABSTRACT_CHARS = 400
_POLITE_DELAY_S = 1.5
_MAX_BODY_CHARS = 6000


def needs_enrichment(abstract: str) -> bool:
    return len((abstract or "").strip()) < _MIN_ABSTRACT_CHARS


def fetch_body(url: str) -> str:
    """Fetch the article URL and return clean main-text. Empty string on failure."""
    client = build_httpx_client(
        Settings(),
        timeout=20.0,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT, "Accept": "text/html,*/*"},
    )
    try:
        with client:
            resp = client.get(url)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.debug("Full-text fetch failed for %s: %s", url, exc)
        return ""

    try:
        doc = Document(resp.text)
        summary_html = doc.summary(html_partial=True)
        text = BeautifulSoup(summary_html, "lxml").get_text(" ", strip=True)
    except Exception as exc:
        log.debug("Readability extract failed for %s: %s", url, exc)
        return ""

    return text[:_MAX_BODY_CHARS]


def enrich_many(urls: list[str]) -> dict[str, str]:
    """Fetch bodies for the given URLs sequentially with a polite delay."""
    out: dict[str, str] = {}
    for i, url in enumerate(urls):
        if i > 0:
            time.sleep(_POLITE_DELAY_S)
        out[url] = fetch_body(url)
    return out
