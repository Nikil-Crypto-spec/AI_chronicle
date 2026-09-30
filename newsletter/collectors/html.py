"""HTML homepage collector.

This is intentionally generic: it scrapes <article> / <h2 a> / <h3 a> blocks
on the configured homepage URL and treats each as an item with title + link.

For sources without an RSS feed, this is a starting point; tune per-source
selectors here if a particular publisher needs special handling.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..config import Settings
from ..models import RawItem
from ..ssl_compat import build_httpx_client
from .base import Collector

log = logging.getLogger(__name__)

_USER_AGENT = (
    "newsletter-generator/0.1 (+local; respects robots.txt; contact: local user)"
)


class HTMLCollector(Collector):
    def collect(self) -> list[RawItem]:
        log.info("HTML fetch: %s (%s)", self.source.name, self.source.url)
        client = build_httpx_client(
            Settings(),
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html,*/*"},
        )
        try:
            with client:
                resp = client.get(self.source.url)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("HTML fetch failed for %s: %s", self.source.name, exc)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        seen: set[str] = set()
        items: list[RawItem] = []

        candidates = soup.select("article a[href], h1 a[href], h2 a[href], h3 a[href]")
        for anchor in candidates:
            href = anchor.get("href", "").strip()
            title = anchor.get_text(" ", strip=True)
            if not href or not title or len(title) < 12:
                continue
            url = urljoin(self.source.url, href)
            if url in seen:
                continue
            seen.add(url)

            abstract = ""
            container = anchor.find_parent(["article", "li", "div"])
            if container is not None:
                p = container.find("p")
                if p is not None:
                    abstract = p.get_text(" ", strip=True)

            items.append(
                RawItem(
                    source=self.source.name,
                    section=self.source.section,
                    source_weight=self.source.weight,
                    title=title,
                    url=url,
                    abstract=abstract,
                    published_at=None,
                    guid=url,
                )
            )

        log.info("HTML %s: %d items", self.source.name, len(items))
        return items
