"""Collector base class."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import SourceConfig
from ..models import RawItem


class Collector(ABC):
    """Pulls items from one configured source."""

    def __init__(self, source: SourceConfig) -> None:
        self.source = source

    @abstractmethod
    def collect(self) -> list[RawItem]:
        """Return raw items. Implementations should never raise on transient
        network errors; they should log and return an empty list instead."""
        raise NotImplementedError
