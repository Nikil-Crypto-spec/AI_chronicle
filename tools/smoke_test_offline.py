"""Offline smoke test: exercises the full pipeline without network.

Builds synthetic RawItems in-memory, pushes them through dedupe -> rank ->
summarise (with a stub LLM that raises so we hit the abstract fallback) ->
format -> sender (dry-run). Exits non-zero if the rendered HTML is missing
expected content.

Run:
    .\.venv\Scripts\python.exe tools\smoke_test_offline.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newsletter.config import load_prompts, load_topics
from newsletter.dedupe import dedupe
from newsletter.formatter import render
from newsletter.logging_setup import setup_logging
from newsletter.models import RawItem
from newsletter.ranking import rank
from newsletter.sender import write_to_disk
from newsletter.summariser import summarise_all


class StubFailingLLM:
    """Always raises so the summariser is forced down the fallback path."""

    name = "stub-failing"

    def complete(self, system, user, *, json_mode=True, temperature=0.2, max_tokens=600):
        raise RuntimeError("stub LLM: simulated failure to exercise fallback path")


def build_fixtures() -> list[RawItem]:
    now = datetime.now(timezone.utc)
    return [
        RawItem(
            source="nature", section="Nature (research)", source_weight=1.2,
            title="Foundation models accelerate protein structure prediction",
            url="https://www.nature.com/articles/test-aaaa",
            abstract=(
                "Researchers report a new deep learning approach combining a "
                "large language model with AlphaFold-style refinement, "
                "yielding state-of-the-art accuracy on protein structure "
                "prediction. The method generalises across diverse protein "
                "families and runs in under a minute per target on a single "
                "GPU. Results suggest a path to routine high-throughput "
                "structural genomics in computational biology pipelines."
            ),
            published_at=now - timedelta(days=1),
            guid="aaaa",
        ),
        RawItem(
            source="science", section="Science (AAAS)", source_weight=1.1,
            title="Solar cell efficiency record set by tandem perovskite design",
            url="https://www.science.org/article/test-bbbb",
            abstract=(
                "A new tandem perovskite/silicon solar cell achieves a "
                "certified efficiency of 33.4%, advancing renewable energy "
                "and climate decarbonisation goals."
            ),
            published_at=now - timedelta(days=2),
            guid="bbbb",
        ),
        RawItem(
            source="arxiv-cs-lg", section="arXiv cs.LG", source_weight=0.9,
            title="A duplicate-looking title about foundation models for proteins",
            url="https://www.nature.com/articles/test-aaaa?utm_source=mirror",
            abstract="Mirrored copy from a different aggregator.",
            published_at=now - timedelta(days=1),
            guid="dup",
        ),
        RawItem(
            source="elife", section="eLife (recent)", source_weight=1.0,
            title="Single-cell genomics reveals novel CRISPR off-target patterns",
            url="https://elifesciences.org/articles/test-cccc",
            abstract=(
                "Using single-cell genomics combined with high-coverage "
                "sequencing, the authors map CRISPR off-target activity "
                "across cell types in computational biology workflows."
            ),
            published_at=now - timedelta(days=3),
            guid="cccc",
        ),
    ]


def main() -> int:
    setup_logging()
    topics = load_topics()
    prompts = load_prompts()

    items = build_fixtures()
    deduped = dedupe(items)
    assert len(deduped) == 3, f"dedupe should drop the mirrored duplicate (got {len(deduped)})"

    ranked = rank(deduped, topics, max_items=10)
    assert ranked, "ranking returned nothing"
    assert ranked[0].score > 0, "top item should have positive score given keywords"

    summarised = summarise_all(ranked, bodies={}, llm=StubFailingLLM(), prompts=prompts)
    assert all(s.used_fallback for s in summarised), \
        "with a failing LLM, every item should hit the fallback path"
    assert all(s.tldr for s in summarised), "fallback must still produce a tldr"

    started = datetime.now(timezone.utc) - timedelta(days=7)
    finished = datetime.now(timezone.utc)
    subject, html = render(
        summarised,
        window_start=started.date(),
        window_end=finished.date(),
        backend="stub-failing",
        runtime_s=0.1,
    )
    assert "Weekly Science Digest" in subject
    assert "Foundation models accelerate" in html
    assert "Single-cell genomics" in html
    assert "stub-failing" in html

    path = write_to_disk(subject, html)
    assert path.exists() and path.stat().st_size > 1000, "rendered HTML should be non-trivial"

    print(f"OK: smoke test passed. Wrote {path} ({path.stat().st_size} bytes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
