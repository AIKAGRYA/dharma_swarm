"""Palantir Pilot — query packets and answer packet construction.

This module owns `build_query_packet`, `build_answer_packet`,
`build_answer_packet_from_query_packet`, and `record_query_packet_to_memory_plane`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from dharma_swarm.palantir_pilot_manifest import (
    AGENT_ID,
    CALLSIGN,
    DEFAULT_DHARMA_HOME,
    DISPLAY_NAME,
    QUERY_CONSUMER,
    _utc_now,
)
from dharma_swarm.palantir_pilot_index import (
    _load_latest_source_index,
    _query_observed_at,
    _query_terms,
    _stable_id,
    memory_plane_db_path,
    query_source_index,
    query_wiki_notes,
)

def build_query_packet(
    query: str,
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    limit: int = 10,
    family: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build an auditable local query packet for Palantir Pilot."""

    index_path, payload = _load_latest_source_index(dharma_home)
    return {
        "schema_version": "palantir_pilot.query_packet.v1",
        "agent": {"id": AGENT_ID, "callsign": CALLSIGN},
        "query": query,
        "observed_at": _utc_now(now),
        "source_boundary": (
            "Local search over source metadata, original wiki notes, and deep-card prose "
            "from robots-allowed public www.palantir.com pages; no private Palantir "
            "material and no Learn/course body storage."
        ),
        "latest_source_index": str(index_path) if index_path else "",
        "indexed_url_count": int(payload.get("url_count") or 0) if isinstance(payload, dict) else 0,
        "family_filter": family or "",
        "source_hits": query_source_index(
            query,
            dharma_home=dharma_home,
            limit=limit,
            family=family,
        ),
        "note_hits": query_wiki_notes(
            query,
            dharma_home=dharma_home,
            limit=min(limit, 5),
        ),
    }


def _answer_confidence(packet: dict[str, Any]) -> str:
    source_hits = packet.get("source_hits")
    note_hits = packet.get("note_hits")
    source_count = len(source_hits) if isinstance(source_hits, list) else 0
    note_count = len(note_hits) if isinstance(note_hits, list) else 0
    if source_count >= 2 and note_count >= 1:
        return "medium_public_source_grounded"
    if source_count or note_count:
        return "low_partial_public_source_grounding"
    return "insufficient_local_evidence"


def _answer_focus_terms(query: str) -> list[str]:
    stopwords = {
        "about",
        "after",
        "from",
        "into",
        "palantir",
        "please",
        "show",
        "that",
        "this",
        "what",
        "with",
    }
    terms = []
    for term in _query_terms(query):
        if term in stopwords or len(term) < 3:
            continue
        terms.append(term)
    return terms[:6]


def _top_families(packet: dict[str, Any]) -> list[str]:
    source_hits = packet.get("source_hits")
    counts: dict[str, int] = {}
    source_rows = source_hits if isinstance(source_hits, list) else []
    for item in source_rows:
        if not isinstance(item, dict):
            continue
        family = str(item.get("family") or "unknown")
        counts[family] = counts.get(family, 0) + 1
    return [
        family
        for family, _count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _first_sentence(text: str) -> str:
    collapsed = " ".join(text.split())
    for delimiter in (". ", "\n"):
        if delimiter in collapsed:
            return collapsed.split(delimiter, 1)[0].strip(" .") + "."
    return collapsed[:220]


def _is_answer_synthesis_note(path_text: str) -> bool:
    path = Path(path_text)
    name = path.name.lower()
    if name.startswith(("checkpoint-", "source-index-")):
        return False
    if name in {
        "source-card-index.md",
        "curriculum-index.md",
        "orientation-index.md",
        "query-cookbook.md",
        "query-smoke-latest.md",
    }:
        return False
    if any(part.lower() in {"logs", "raw"} for part in path.parts):
        return False
    return True


def _strip_markdown_noise(lines: list[str]) -> str:
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if kept:
                break
            continue
        if stripped.startswith(("#", "|", "```")):
            continue
        if stripped.lower().startswith(("observed:", "source index:", "indexed url count:", "boundary:")):
            continue
        kept.append(stripped.lstrip("- ").strip())
    return " ".join(kept).strip()


def _extract_note_answer_claim(path_text: str, fallback: str) -> str:
    path = Path(path_text)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return _first_sentence(fallback)

    preferred_sections = {
        "source summary",
        "working thesis",
        "working interpretation",
        "focus",
        "outcome",
        "learning stages",
        "practical orientation",
        "learn catalog handling",
        "allowed intake fields",
        "current status",
        "dharma swarm contribution",
        "content",
    }
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("## "):
            continue
        title = stripped[3:].strip().lower()
        if title not in preferred_sections:
            continue
        section_lines: list[str] = []
        for candidate in lines[index + 1 :]:
            if candidate.strip().startswith("## "):
                break
            section_lines.append(candidate)
        claim = _strip_markdown_noise(section_lines)
        if claim:
            return claim[:1400]
    return _first_sentence(fallback)


def build_answer_packet_from_query_packet(
    packet: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a conservative source-grounded answer from a Palantir query packet."""

    query = str(packet.get("query") or "")
    source_hits = packet.get("source_hits")
    note_hits = packet.get("note_hits")
    sources = [item for item in source_hits if isinstance(item, dict)] if isinstance(source_hits, list) else []
    notes = [item for item in note_hits if isinstance(item, dict)] if isinstance(note_hits, list) else []
    answer_notes = [
        item
        for item in notes
        if _is_answer_synthesis_note(str(item.get("path") or ""))
    ]
    focus_terms = _answer_focus_terms(query)
    families = _top_families(packet)
    confidence_packet = {**packet, "note_hits": answer_notes}
    confidence = _answer_confidence(confidence_packet)

    cited_note_claims: list[str] = []
    for item in answer_notes[:3]:
        snippet = str(item.get("snippet") or "").strip()
        path = str(item.get("path") or "")
        claim = _extract_note_answer_claim(path, snippet) if path or snippet else ""
        if claim:
            cited_note_claims.append(claim)

    answer_lines = [
        (
            "Palantir Pilot can answer this from the local public-source workspace, "
            "but only as public-source synthesis."
        )
    ]
    if focus_terms:
        answer_lines.append(f"Focus terms found: {', '.join(focus_terms)}.")
    if families:
        answer_lines.append(f"Strongest public source families: {', '.join(families)}.")
    if cited_note_claims:
        answer_lines.append("Relevant workspace synthesis: " + " ".join(cited_note_claims))
    elif sources:
        answer_lines.append(
            "The local index currently has URL-level public-source anchors, but no stronger local note summary for this query yet."
        )
    else:
        answer_lines.append(
            "The local Palantir Pilot workspace does not yet contain enough evidence to answer this query."
        )

    limitations = [
        "No official Palantir affiliation, certification, private tenant access, or insider knowledge is claimed.",
        "Source hits are public URL metadata unless a cited wiki note is present.",
        "Do not treat this as a substitute for authorized Palantir training, docs access, or tenant-specific guidance.",
    ]
    if any(term in query.lower() for term in ("learn", "course", "catalog", "training")):
        limitations.append(
            "learn.palantir.com/page/course-catalog remains manual-review/link-only under the observed 403 boundary."
        )

    return {
        "schema_version": "palantir_pilot.answer_packet.v1",
        "agent": {"id": AGENT_ID, "callsign": CALLSIGN, "label": DISPLAY_NAME},
        "query": query,
        "observed_at": _utc_now(now),
        "answer": " ".join(answer_lines),
        "confidence": confidence,
        "source_boundary": (
            "Public-source workspace synthesis over URL metadata, original wiki notes, and "
            "deep-card prose from robots-allowed public www.palantir.com pages; no private "
            "Palantir material and no Learn/course body storage."
        ),
        "source_citations": [
            {
                "url": str(item.get("url") or ""),
                "family": str(item.get("family") or ""),
                "lastmod": str(item.get("lastmod") or ""),
                "evidence_type": "public_url_metadata",
            }
            for item in sources[:5]
        ],
        "note_citations": [
            {
                "path": str(item.get("path") or ""),
                "snippet": str(item.get("snippet") or ""),
                "evidence_type": "original_wiki_note_snippet",
            }
            for item in answer_notes[:5]
        ],
        "limitations": limitations,
        "next_steps": [
            "Read cited public docs directly before using the answer for implementation decisions.",
            "Promote stronger summaries into the Palantir Pilot wiki after source-specific review.",
            "Keep Learn/course-catalog material manual-review only unless an allowed access path is established.",
        ],
        "query_packet": packet,
    }


def build_answer_packet(
    query: str,
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    limit: int = 10,
    family: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a Palantir Pilot answer packet from the local public workspace."""

    packet = build_query_packet(
        query,
        dharma_home=dharma_home,
        limit=limit,
        family=family,
        now=now,
    )
    return build_answer_packet_from_query_packet(packet, now=now)


def record_query_packet_to_memory_plane(
    packet: dict[str, Any],
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    db_path: Path | str | None = None,
    task_id: str | None = None,
    consumer: str = QUERY_CONSUMER,
) -> dict[str, Any]:
    """Record a Palantir Pilot query packet in the Memory Palace retrieval log."""

    from dharma_swarm.engine.hybrid_retriever import RetrievalHit
    from dharma_swarm.engine.knowledge_store import KnowledgeRecord
    from dharma_swarm.engine.retrieval_feedback import RetrievalFeedbackStore

    home = Path(dharma_home).expanduser()
    db = Path(db_path).expanduser() if db_path else memory_plane_db_path(home)
    created_at = _query_observed_at(packet)
    query = str(packet.get("query") or "")
    hits: list[RetrievalHit] = []

    source_hits = packet.get("source_hits")
    source_rows = source_hits if isinstance(source_hits, list) else []
    for item in source_rows:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        if not url:
            continue
        text = " ".join(
            part
            for part in (
                "Palantir public source URL",
                f"family={item.get('family', '')}",
                f"lastmod={item.get('lastmod', '')}",
                f"url={url}",
            )
            if part
        )
        record = KnowledgeRecord(
            text=text,
            metadata={
                "agent_id": AGENT_ID,
                "callsign": CALLSIGN,
                "source_kind": "palantir_pilot_source_catalog",
                "source_path": url,
                "source_ref": str(packet.get("latest_source_index") or ""),
                "family": str(item.get("family") or ""),
                "boundary": "public URL metadata only",
            },
            record_id=_stable_id("palantir_source", url),
            created_at=created_at,
        )
        hits.append(
            RetrievalHit(
                record=record,
                score=float(item.get("score") or 0),
                evidence={"hit_kind": "source_index", "packet_schema": packet.get("schema_version")},
            )
        )

    note_hits = packet.get("note_hits")
    note_rows = note_hits if isinstance(note_hits, list) else []
    for item in note_rows:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        snippet = str(item.get("snippet") or "")
        if not path and not snippet:
            continue
        record = KnowledgeRecord(
            text=snippet or path,
            metadata={
                "agent_id": AGENT_ID,
                "callsign": CALLSIGN,
                "source_kind": "palantir_pilot_wiki",
                "source_path": path,
                "source_ref": Path(path).name if path else "",
                "boundary": "original wiki note snippet only",
            },
            record_id=_stable_id("palantir_note", path or snippet),
            created_at=created_at,
        )
        hits.append(
            RetrievalHit(
                record=record,
                score=float(item.get("score") or 0),
                evidence={"hit_kind": "wiki_note", "packet_schema": packet.get("schema_version")},
            )
        )

    store = RetrievalFeedbackStore(db)
    effective_task_id = task_id or f"{CALLSIGN}:{_stable_id('query', query)}"
    logged = store.log_hits(
        query,
        hits,
        consumer=consumer,
        task_id=effective_task_id,
    )
    stats = store.stats()
    return {
        "schema_version": "palantir_pilot.database_query_receipt.v1",
        "agent": {"id": AGENT_ID, "callsign": CALLSIGN},
        "observed_at": _utc_now(),
        "db_path": str(db),
        "consumer": consumer,
        "query": query,
        "task_id": effective_task_id,
        "logged_hit_count": logged,
        "retrieval_log_rows": stats["retrieval_log"],
        "storage_boundary": "query text, result metadata, and short snippets only",
    }


