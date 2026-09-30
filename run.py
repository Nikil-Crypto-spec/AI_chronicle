"""Single entry point for the weekly newsletter pipeline.

Usage:
    python run.py [--since 7] [--max-items 12] [--llm local|copilot] [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from newsletter.collectors.registry import build_collector
from newsletter.config import (
    Settings,
    load_prompts,
    load_sources,
    load_topics,
)
from newsletter.dedupe import dedupe
from newsletter.formatter import render
from newsletter.fulltext import enrich_many, needs_enrichment
from newsletter.llm.factory import build_llm
from newsletter.logging_setup import setup_logging
from newsletter.models import RawItem
from newsletter.ranking import rank
from newsletter.sender import send_email, write_to_disk
from newsletter.ssl_compat import apply_ssl_config
from newsletter.state import State
from newsletter.summariser import summarise_all

log = logging.getLogger("newsletter.run")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Weekly scientific newsletter generator")
    p.add_argument("--since", type=int, default=None,
                   help="Look back this many days (default: SINCE_DAYS env var or 7)")
    p.add_argument("--max-items", type=int, default=None,
                   help="Cap on items in the newsletter (default: MAX_ITEMS env var or 12)")
    p.add_argument("--llm", choices=("local", "copilot"), default=None,
                   help="Override LLM_BACKEND")
    p.add_argument("--dry-run", action="store_true",
                   help="Write HTML to out/ instead of sending email")
    p.add_argument("--no-enrich", action="store_true",
                   help="Skip full-text fetching even when abstracts are short")
    p.add_argument("--no-state", action="store_true",
                   help="Ignore seen_urls (don't filter, don't persist)")
    p.add_argument("--sources-file", type=Path, default=None,
                   help="Override path to sources.yaml (useful for smoke tests)")
    return p.parse_args(argv)


def _fresh(item: RawItem, cutoff: datetime) -> bool:
    """Keep items with no date (assume fresh) or published_at >= cutoff."""
    if item.published_at is None:
        return True
    return item.published_at >= cutoff


def _collect_all(sources) -> list[RawItem]:
    out: list[RawItem] = []
    for source in sources:
        if not source.enabled:
            log.info("Skipping disabled source: %s", source.name)
            continue
        try:
            collector = build_collector(source)
            out.extend(collector.collect())
        except Exception as exc:
            log.exception("Collector crashed for %s: %s", source.name, exc)
    return out


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = _parse_args(argv)
    started = datetime.now(timezone.utc)

    settings = Settings()
    apply_ssl_config(settings)
    sources = load_sources(args.sources_file)
    topics = load_topics()
    prompts = load_prompts()

    since_days = args.since if args.since is not None else settings.since_days
    max_items = args.max_items if args.max_items is not None else settings.max_items
    cutoff = started - timedelta(days=since_days)
    log.info(
        "Run start: since=%dd cutoff=%s max_items=%d dry_run=%s",
        since_days, cutoff.date().isoformat(), max_items, args.dry_run,
    )

    state = State() if not args.no_state else None
    known_keys = state.known_keys() if state else set()
    if known_keys:
        log.info("State: %d previously-seen URLs will be filtered out.", len(known_keys))

    raw_items = _collect_all(sources)
    log.info("Collected %d raw items across %d sources.", len(raw_items), len(sources))

    fresh_items = [
        i for i in raw_items
        if _fresh(i, cutoff) and i.canonical_key() not in known_keys
    ]
    log.info("After freshness + seen-URL filter: %d items.", len(fresh_items))

    deduped = dedupe(fresh_items)

    ranked = rank(
        deduped,
        topics,
        use_embeddings=settings.ranking_use_embeddings,
        max_items=max_items,
    )

    if not ranked:
        log.warning("No items survived ranking; nothing to send.")
        if state:
            state.record_run(
                started_at=started, finished_at=datetime.now(timezone.utc),
                backend=args.llm or settings.llm_backend,
                items_collected=len(raw_items), items_sent=0,
                dry_run=args.dry_run, notes="no items after ranking",
            )
            state.close()
        return 0

    bodies: dict[str, str] = {}
    if not args.no_enrich:
        to_enrich = [r.item.url for r in ranked if needs_enrichment(r.item.abstract)]
        if to_enrich:
            log.info("Enriching %d items with full-text fetch...", len(to_enrich))
            bodies = enrich_many(to_enrich)

    llm = build_llm(settings, override=args.llm)
    summarised = summarise_all(ranked, bodies, llm, prompts)

    finished = datetime.now(timezone.utc)
    runtime_s = (finished - started).total_seconds()

    subject, html = render(
        summarised,
        window_start=cutoff.date(),
        window_end=started.date(),
        backend=llm.name,
        runtime_s=runtime_s,
    )

    if args.dry_run:
        write_to_disk(subject, html)
    else:
        try:
            send_email(subject, html, settings)
        except Exception as exc:
            log.exception("Email send failed: %s. Falling back to disk.", exc)
            write_to_disk(subject, html)
            if state:
                state.record_run(
                    started_at=started, finished_at=finished,
                    backend=llm.name,
                    items_collected=len(raw_items),
                    items_sent=0,
                    dry_run=True,
                    notes=f"send failed: {exc}",
                )
                state.close()
            return 2

    if state and not args.dry_run:
        rows = [
            (s.ranked.item.canonical_key(), s.ranked.item.url,
             s.ranked.item.title, s.ranked.item.source)
            for s in summarised
        ]
        state.mark_seen(rows)
        state.record_run(
            started_at=started, finished_at=finished,
            backend=llm.name,
            items_collected=len(raw_items),
            items_sent=len(summarised),
            dry_run=False,
        )

    if state:
        state.close()

    log.info(
        "Run done: %d items sent, runtime %.1fs, backend=%s.",
        len(summarised), runtime_s, llm.name,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
