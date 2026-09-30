"""Render the SummarisedItems into a single HTML email body."""

from __future__ import annotations

from collections import OrderedDict
from datetime import date, datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import TEMPLATES_DIR
from .models import SummarisedItem


def _build_env(templates_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def build_subject(start: date, end: date, item_count: int) -> str:
    if start == end:
        window = start.strftime("%b %d, %Y")
    else:
        window = f"{start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}"
    return f"Weekly Science Digest - {window} ({item_count} items)"


def render(
    items: list[SummarisedItem],
    *,
    window_start: date,
    window_end: date,
    backend: str,
    runtime_s: float,
    templates_dir: Path | None = None,
) -> tuple[str, str]:
    """Return (subject, html_body)."""
    env = _build_env(templates_dir or TEMPLATES_DIR)
    template = env.get_template("newsletter.html.j2")

    grouped: "OrderedDict[str, dict]" = OrderedDict()
    for s in items:
        src = s.ranked.item.source
        bucket = grouped.setdefault(
            src, {"section": s.ranked.item.section, "entries": []}
        )
        bucket["entries"].append(s)

    subject = build_subject(window_start, window_end, len(items))
    date_range = (
        window_start.strftime("%b %d")
        + " - "
        + window_end.strftime("%b %d, %Y")
    )

    html = template.render(
        subject=subject,
        date_range=date_range,
        items=items,
        items_by_source=grouped,
        source_count=len(grouped),
        backend=backend,
        runtime_s=f"{runtime_s:.1f}",
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
    return subject, html
