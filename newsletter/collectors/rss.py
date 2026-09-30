"""RSS / Atom collector via feedparser."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
from bs4 import BeautifulSoup

from ..models import RawItem
from .base import Collector

log = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    if not text:
        return ""
    if "<" not in text:
        return text.strip()
    return BeautifulSoup(text, "lxml").get_text(" ", strip=True)


def _parse_date(entry: dict) -> datetime | None:
    """Best-effort extraction of a tz-aware UTC datetime from a feed entry."""
    for key in ("published_parsed", "updated_parsed"):
        struct = entry.get(key)
        if struct:
            try:
                return datetime(*struct[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    for key in ("published", "updated"):
        raw = entry.get(key)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (TypeError, ValueError):
                pass
    return None


class RSSCollector(Collector):
    def collect(self) -> list[RawItem]:
        log.info("RSS fetch: %s (%s)", self.source.name, self.source.url)
        try:
            parsed = feedparser.parse(self.source.url)
        except Exception as exc:  # feedparser is very forgiving but be safe
            log.warning("RSS fetch failed for %s: %s", self.source.name, exc)
            return []

        if parsed.bozo and not parsed.entries:
            log.warning(
                "RSS fetch returned no entries for %s (bozo=%s)",
                self.source.name,
                getattr(parsed, "bozo_exception", "unknown"),
            )
            return []

        items: list[RawItem] = []
        for entry in parsed.entries:
            title = _strip_html(entry.get("title", "")).strip()
            url = entry.get("link", "").strip()
            if not title or not url:
                continue
            abstract = _strip_html(entry.get("summary", ""))
            if not abstract:
                content_list = entry.get("content") or []
                if content_list:
                    abstract = _strip_html(content_list[0].get("value", ""))
            items.append(
                RawItem(
                    source=self.source.name,
                    section=self.source.section,
                    source_weight=self.source.weight,
                    title=title,
                    url=url,
                    abstract=abstract,
                    published_at=_parse_date(entry),
                    guid=entry.get("id") or entry.get("guid") or "",
                )
            )
        log.info("RSS %s: %d entries", self.source.name, len(items))
        return items
