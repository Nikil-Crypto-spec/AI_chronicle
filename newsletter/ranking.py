"""Relevance ranking: keyword tier (always on) + optional embedding tier."""

from __future__ import annotations

import logging
import re

from .config import TopicConfig, TopicsFile
from .models import RankedItem, RawItem

log = logging.getLogger(__name__)


def _word_boundary_count(haystack: str, needle: str) -> int:
    pattern = r"\b" + re.escape(needle) + r"\b"
    return len(re.findall(pattern, haystack, flags=re.IGNORECASE))


def _phrase_count(haystack: str, needle: str) -> int:
    return haystack.lower().count(needle.lower())


def _score_topic(topic: TopicConfig, text: str) -> tuple[float, bool]:
    """Return (score_contribution, matched)."""
    hits = 0
    for kw in topic.keywords:
        hits += _word_boundary_count(text, kw)
    for ph in topic.phrases:
        hits += _phrase_count(text, ph) * 2  # phrases are stronger signal
    if hits == 0:
        return 0.0, False
    contribution = topic.weight * (1.0 + 0.5 * (hits - 1))
    return contribution, True


def keyword_score(item: RawItem, topics: TopicsFile) -> tuple[float, list[str]]:
    text = f"{item.title}\n{item.abstract}"
    score = 0.0
    matched: list[str] = []
    for topic in topics.topics:
        contrib, hit = _score_topic(topic, text)
        if hit:
            matched.append(topic.name)
            score += contrib

    if topics.penalties.keywords:
        penalty_hits = sum(
            _word_boundary_count(text, kw) for kw in topics.penalties.keywords
        )
        if penalty_hits:
            score -= topics.penalties.weight * penalty_hits

    score *= item.source_weight
    return score, matched


def _embedding_rerank(items: list[RankedItem], topics: TopicsFile) -> list[RankedItem]:
    """Optional second-pass rerank using sentence-transformers if available.

    Adds a similarity bonus to each item's score based on cosine similarity
    between (title + abstract) and the concatenated topic seed sentences.
    """
    seeds = [s for t in topics.topics for s in t.seed_sentences]
    if not seeds:
        return items
    try:
        from sentence_transformers import SentenceTransformer, util  # type: ignore
    except ImportError:
        log.warning(
            "RANKING_USE_EMBEDDINGS=true but sentence-transformers not installed; "
            "install the 'embeddings' extra. Skipping rerank."
        )
        return items

    log.info("Embedding rerank: encoding %d seeds and %d items", len(seeds), len(items))
    model = SentenceTransformer("all-MiniLM-L6-v2")
    seed_emb = model.encode(seeds, convert_to_tensor=True, normalize_embeddings=True)
    texts = [f"{r.item.title}. {r.item.abstract}" for r in items]
    item_emb = model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)
    sims = util.cos_sim(item_emb, seed_emb).max(dim=1).values.tolist()
    rescored: list[RankedItem] = []
    for r, sim in zip(items, sims):
        bonus = float(sim)
        rescored.append(
            RankedItem(item=r.item, score=r.score + bonus, matched_topics=r.matched_topics)
        )
    return rescored


def rank(
    items: list[RawItem],
    topics: TopicsFile,
    *,
    use_embeddings: bool = False,
    max_items: int | None = None,
) -> list[RankedItem]:
    """Score, sort, and optionally trim to top `max_items`."""
    scored: list[RankedItem] = []
    for item in items:
        score, matched = keyword_score(item, topics)
        scored.append(RankedItem(item=item, score=score, matched_topics=matched))

    if use_embeddings:
        scored = _embedding_rerank(scored, topics)

    scored.sort(key=lambda r: r.score, reverse=True)
    if max_items is not None:
        scored = scored[:max_items]

    log.info(
        "Ranked %d items, top score=%.3f, kept=%d",
        len(items),
        scored[0].score if scored else 0.0,
        len(scored),
    )
    return scored
