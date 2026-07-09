"""Candidate fusion/ranking for the governed retrieval engine.

Split out of ``memory_retrieval.py`` (Rule 10 module-line-budget
decomposition). ``_fuse_candidates`` had no dependency on
``GovernedRetrievalEngine`` instance state (no ``self`` usage), so it moves
here as a plain function; ``GovernedRetrievalEngine._fuse_candidates``
delegates to it. Nothing outside ``memory_retrieval.py`` should call this
directly.
"""

from __future__ import annotations

from typing import Any

from dharma_swarm.memory_kernel_retrieval.scoring_terms import (
    _content_for_candidate,
    _explicit_anchor_terms,
    _identifier_like_query,
    _is_noisy_vector_only_candidate,
    _query_term_doc_freq,
    _rare_query_terms,
    _row_similarity,
    _scoring_terms,
    _tail_intent_terms,
    _term_stat_slots,
    _token_overlap_from_terms,
    _weighted_token_overlap_from_terms,
)
from dharma_swarm.memory_kernel_retrieval.sidecar_matching import (
    _identity_match_score,
    _source_match_score,
    _title_match_score,
)
from dharma_swarm.memory_kernel_retrieval.types import RetrievalCandidate


def fuse_candidates(
    *,
    query_text: str,
    vector_results: list[dict[str, Any]],
    fts_results: list[dict[str, Any]],
    top_k: int,
    min_score: float,
    include_content: bool,
) -> list[RetrievalCandidate]:
    slots: dict[str, dict[str, Any]] = {}
    rrf_k = 60.0
    channel_weights = {"vector": 0.45, "fts": 0.55}
    ideal_score = sum(weight / (rrf_k + 1.0) for weight in channel_weights.values())
    exact_needle = query_text.strip().lower()
    query_terms = _scoring_terms(query_text)
    anchor_terms = _explicit_anchor_terms(query_text)
    tail_terms = _tail_intent_terms(query_text)

    for channel, rows in (("vector", vector_results), ("fts", fts_results)):
        for rank, row in enumerate(rows, start=1):
            doc_id = str(row.get("id", ""))
            if not doc_id:
                continue
            channel_similarity = _row_similarity(row)
            if channel == "vector" and channel_similarity <= 0.0:
                continue
            slot = slots.setdefault(
                doc_id,
                {
                    "row": row,
                    "rrf": 0.0,
                    "channels": [],
                    "channel_scores": {},
                    "exact_match": False,
                    "token_overlap": 0.0,
                    "weighted_token_overlap": 0.0,
                    "rare_query_term_coverage": 0.0,
                    "discriminator_coverage": 0.0,
                    "identity_match": 0.0,
                    "source_match": 0.0,
                    "title_match": 0.0,
                    "candidate_terms": set(),
                },
            )
            slot["rrf"] += channel_weights[channel] / (rrf_k + float(rank))
            slot["channels"].append(channel)
            slot["channel_scores"][channel] = round(channel_similarity, 4)
            candidate_terms = _scoring_terms(f"{row.get('content', '')} {row.get('source', '')}")
            slot["candidate_terms"].update(candidate_terms)
            overlap = _token_overlap_from_terms(query_terms, candidate_terms)
            slot["token_overlap"] = max(float(slot["token_overlap"]), overlap)
            identity_match = _identity_match_score(query_terms, row)
            slot["identity_match"] = max(float(slot["identity_match"]), identity_match)
            source_match = _source_match_score(query_terms, row)
            slot["source_match"] = max(float(slot["source_match"]), source_match)
            title_match = _title_match_score(query_terms, row)
            slot["title_match"] = max(float(slot["title_match"]), title_match)
            if exact_needle and (
                exact_needle in str(row.get("content", "")).lower()
                or exact_needle in str(row.get("source", "")).lower()
            ):
                slot["exact_match"] = True
            if channel == "fts":
                slot["row"] = row

    term_stat_slots = _term_stat_slots(slots.values())
    term_doc_freq = _query_term_doc_freq(query_terms, term_stat_slots)
    rare_query_terms = _rare_query_terms(term_doc_freq)
    candidate_count = len(term_stat_slots)

    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for doc_id, slot in slots.items():
        channels = tuple(dict.fromkeys(slot.get("channels", [])))
        overlap_score = float(slot.get("token_overlap", 0.0))
        weighted_overlap = _weighted_token_overlap_from_terms(
            query_terms,
            slot.get("candidate_terms", set()),
            term_doc_freq,
            candidate_count,
        )
        slot["weighted_token_overlap"] = weighted_overlap
        rare_coverage = _token_overlap_from_terms(
            rare_query_terms,
            slot.get("candidate_terms", set()),
        )
        slot["rare_query_term_coverage"] = rare_coverage
        discriminator_terms = anchor_terms or tail_terms
        discriminator_coverage = max(
            rare_coverage,
            _token_overlap_from_terms(
                discriminator_terms,
                slot.get("candidate_terms", set()),
            ),
        )
        slot["discriminator_coverage"] = discriminator_coverage
        identity_match = float(slot.get("identity_match", 0.0))
        source_match = float(slot.get("source_match", 0.0))
        title_match = float(slot.get("title_match", 0.0))
        if channels == ("vector",) and overlap_score <= 0.0:
            continue
        if channels == ("fts",) and _identifier_like_query(query_text) and not slot.get("exact_match"):
            identifier_support = max(identity_match, source_match, title_match)
            if identifier_support < 0.5:
                continue
        required_fts_overlap = 0.5 if len(query_terms) >= 5 and not anchor_terms else 0.3
        if channels == ("fts",) and not slot.get("exact_match") and overlap_score < required_fts_overlap:
            continue
        if channels == ("vector",) and _is_noisy_vector_only_candidate(
            slot["row"],
            query_text=query_text,
            token_overlap=overlap_score,
            exact_match=bool(slot.get("exact_match")),
        ):
            continue
        rrf_score = min(1.0, float(slot["rrf"]) / ideal_score) if ideal_score else 0.0
        score = (
            (rrf_score * 0.38)
            + (weighted_overlap * 0.30)
            + (discriminator_coverage * 0.17)
            + (identity_match * 0.18)
            + (source_match * 0.12)
            + (title_match * 0.12)
        )
        if slot.get("exact_match"):
            score = min(1.0, score + 0.5)
        if score >= min_score:
            ranked.append((score, doc_id, slot))
    ranked.sort(key=lambda item: item[0], reverse=True)

    out: list[RetrievalCandidate] = []
    for rank, (score, doc_id, slot) in enumerate(ranked[: max(0, top_k)], start=1):
        row = slot["row"]
        content, warnings = _content_for_candidate(str(row.get("content", "")), include_content)
        metadata = dict(row.get("metadata") or {})
        metadata["retrieval_channel_scores"] = dict(slot["channel_scores"])
        metadata["retrieval_token_overlap"] = round(float(slot.get("token_overlap", 0.0)), 4)
        metadata["retrieval_weighted_token_overlap"] = round(
            float(slot.get("weighted_token_overlap", 0.0)),
            4,
        )
        metadata["retrieval_rare_query_term_coverage"] = round(
            float(slot.get("rare_query_term_coverage", 0.0)),
            4,
        )
        metadata["retrieval_discriminator_coverage"] = round(
            float(slot.get("discriminator_coverage", 0.0)),
            4,
        )
        metadata["retrieval_identity_match"] = round(
            float(slot.get("identity_match", 0.0)),
            4,
        )
        metadata["retrieval_source_match"] = round(
            float(slot.get("source_match", 0.0)),
            4,
        )
        metadata["retrieval_title_match"] = round(
            float(slot.get("title_match", 0.0)),
            4,
        )
        out.append(
            RetrievalCandidate(
                doc_id=doc_id,
                rank=rank,
                score=round(score, 4),
                source=str(row.get("source", "")),
                layer=str(row.get("layer", "")),
                channels=tuple(dict.fromkeys(slot["channels"])),
                content=content,
                event_time=row.get("event_time"),
                ingestion_time=row.get("ingestion_time"),
                metadata=metadata,
                warnings=warnings,
            )
        )
    return out
