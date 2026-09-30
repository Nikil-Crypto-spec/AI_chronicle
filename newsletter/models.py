"""Pipeline data models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RawItem(BaseModel):
    """An article as collected from a source, before ranking."""

    source: str
    section: str = ""
    source_weight: float = 1.0
    title: str
    url: str
    abstract: str = ""
    published_at: Optional[datetime] = None
    guid: str = ""

    def canonical_key(self) -> str:
        """Stable key for dedupe / state. URL is the primary identity."""
        return self.url.split("?")[0].rstrip("/").lower()


class RankedItem(BaseModel):
    """A RawItem plus a relevance score and matched topic names."""

    item: RawItem
    score: float
    matched_topics: list[str] = Field(default_factory=list)


class SummarisedItem(BaseModel):
    """A ranked item with an LLM-produced (or fallback) summary."""

    ranked: RankedItem
    tldr: str
    why_it_matters: str = ""
    key_points: list[str] = Field(default_factory=list)
    used_fallback: bool = False
