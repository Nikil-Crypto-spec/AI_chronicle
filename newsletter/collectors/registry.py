"""Pick a collector implementation for a source config."""

from __future__ import annotations

from ..config import SourceConfig
from .base import Collector
from .html import HTMLCollector
from .rss import RSSCollector

_REGISTRY: dict[str, type[Collector]] = {
    "rss": RSSCollector,
    "html": HTMLCollector,
}


def build_collector(source: SourceConfig) -> Collector:
    cls = _REGISTRY.get(source.kind)
    if cls is None:
        raise ValueError(f"Unknown collector kind '{source.kind}' for source '{source.name}'.")
    return cls(source)
