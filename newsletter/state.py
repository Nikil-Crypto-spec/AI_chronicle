"""SQLite-backed run state: seen URLs and run history."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from .config import STATE_DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_urls (
    canonical_key TEXT PRIMARY KEY,
    url           TEXT NOT NULL,
    title         TEXT NOT NULL,
    source        TEXT NOT NULL,
    sent_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at     TEXT NOT NULL,
    finished_at    TEXT NOT NULL,
    backend        TEXT NOT NULL,
    items_collected INTEGER NOT NULL,
    items_sent     INTEGER NOT NULL,
    dry_run        INTEGER NOT NULL,
    notes          TEXT
);
"""


class State:
    """Thin wrapper around a SQLite file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or STATE_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        finally:
            cur.close()

    def known_keys(self) -> set[str]:
        with self.cursor() as cur:
            cur.execute("SELECT canonical_key FROM seen_urls")
            return {row[0] for row in cur.fetchall()}

    def mark_seen(
        self, items: Iterable[tuple[str, str, str, str]]
    ) -> int:
        """Insert (canonical_key, url, title, source) rows; ignore duplicates."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        rows = [(k, u, t, s, now) for (k, u, t, s) in items]
        if not rows:
            return 0
        with self.cursor() as cur:
            cur.executemany(
                "INSERT OR IGNORE INTO seen_urls "
                "(canonical_key, url, title, source, sent_at) "
                "VALUES (?, ?, ?, ?, ?)",
                rows,
            )
            return cur.rowcount

    def record_run(
        self,
        *,
        started_at: datetime,
        finished_at: datetime,
        backend: str,
        items_collected: int,
        items_sent: int,
        dry_run: bool,
        notes: str = "",
    ) -> None:
        with self.cursor() as cur:
            cur.execute(
                "INSERT INTO run_history "
                "(started_at, finished_at, backend, items_collected, "
                " items_sent, dry_run, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    started_at.isoformat(timespec="seconds"),
                    finished_at.isoformat(timespec="seconds"),
                    backend,
                    items_collected,
                    items_sent,
                    1 if dry_run else 0,
                    notes,
                ),
            )

    def close(self) -> None:
        self._conn.close()
