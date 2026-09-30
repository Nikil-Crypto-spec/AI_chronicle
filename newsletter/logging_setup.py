"""Logging setup: rich console + rotating file handler."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

from .config import LOGS_DIR


def setup_logging(level: int = logging.INFO, log_file: Path | None = None) -> logging.Logger:
    """Configure root logging once. Safe to call multiple times."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = log_file or (LOGS_DIR / "run.log")

    root = logging.getLogger()
    if getattr(root, "_newsletter_configured", False):
        return root

    root.setLevel(level)
    root.handlers.clear()

    console = RichHandler(
        rich_tracebacks=True,
        show_path=False,
        markup=False,
        log_time_format="[%H:%M:%S]",
    )
    console.setLevel(level)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    root._newsletter_configured = True  # type: ignore[attr-defined]
    return root
