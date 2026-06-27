"""Palantir Pilot query, indexing, and answer helpers."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.palantir_pilot_manifest import (
    AGENT_ID,
    CALLSIGN,
    DATABASE_SOURCE_KINDS,
    DEFAULT_DHARMA_HOME,
    DISPLAY_NAME,
    QUERY_CONSUMER,
    WIKI_HOME,
    WIKI_SOURCE_DIR,
    _utc_now,
    latest_source_index_path,
    memory_plane_db_path,
)


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    current: list[str] = []
    for char in query.lower():
        if char.isalnum():
            current.append(char)
        elif current:
            term = "".join(current)
            if len(term) > 1:
                terms.append(term)
            current = []
    if current:
        term = "".join(current)
        if len(term) > 1:
            terms.append(term)
    return terms


def _score_text(text: str, terms: list[str]) -> int:
    haystack = text.lower()
    return sum(haystack.count(term) for term in terms)


def _score_wiki_note(path: Path, text: str, terms: list[str]) -> int:
    path_text = " ".join([path.name, path.stem, " ".join(path.parts[-5:])])
    score = _score_text(text, terms) + (_score_text(path_text, terms) * 8)
    term_set = set(terms)
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    product_map_query = bool({"product", "family", "families", "compare", "map", "maps"} & term_set)
    named_family_terms = {"foundry", "aip", "ontology", "osdk", "api", "apollo", "gotham", "defense", "learn"}
    broad_product_map_query = product_map_query and len(term_set & named_family_terms) >= 3
    if name.startswith("titanium-"):
        titanium_terms = {
            "bench",
            "blocked",
            "boundary",
            "claim",
            "claims",
            "compare",
            "corpus",
            "debt",
            "dharma",
            "evaluation",
            "expert",
            "exhausted",
            "family",
            "first",
            "gap",
            "gaps",
            "hard",
            "map",
            "maps",
            "mastery",
            "model",
            "operating",
            "principles",
            "product",
            "qa",
            "ratchet",
            "synthesis",
            "swarm",
            "titanium",
            "transfer",
            "unjustified",
            "weak",
        }
        overlap = term_set & titanium_terms
        if overlap:
            score += 900 + (120 * len(overlap))
        if {"first", "principles", "model", "operating"} & term_set and "first-principles" in name:
            score += 1200
        if {"product", "family", "families", "compare", "map", "maps"} & term_set and "product-family" in name:
            score += 1200
            if broad_product_map_query:
                score += 4200
        if {"dharma", "swarm", "transfer", "patterns"} & term_set and "dharma-swarm-application" in name:
            score += 1200
        if {"gap", "gaps", "blocked", "weak", "unjustified", "claims"} & term_set and "gap-ledger" in name:
            score += 1200
        if {"qa", "question", "questions", "expert", "bench", "hard"} & term_set and "expert-qa" in name:
            score += 1200
        if {"corpus", "coverage", "indexed"} & term_set and "corpus-map" in name:
            score += 1200
        if {"next", "synthesis", "debt", "exhausted", "canonical"} & term_set and "synthesis-debt" in name:
            score += 3600
    if {"contribution", "packet"} & term_set and "contributions" in parts:
        score += 2400
    if {"dharma", "swarm", "aip", "governance", "observability", "model"} & term_set and "contributions" in parts:
        score += 1600
    if {"evaluation", "eval"} & term_set and "evals" in parts:
        score += 60
    if "playbook" in term_set and "playbooks" in parts:
        score += 40
    if {"learn", "course", "catalog"} & term_set and path.name == "learn-course-catalog-intake.md":
        score += 1200 if broad_product_map_query else 5200
    if "checkpoint" in term_set:
        if path.name.startswith("checkpoint-"):
            path_lower = path.name.lower()
            score += 6000
            score += sum(2000 for term in term_set if term in path_lower)
        elif path.name in {"source-card-index.md", "query-cookbook.md", "query-smoke-latest.md"}:
            score = max(1, score // 4)
    elif path.name in {"source-card-index.md", "curriculum-index.md", "orientation-index.md", "query-cookbook.md", "query-smoke-latest.md"}:
        score = max(1, score // 12)
    return score


def _load_latest_source_index(dharma_home: Path | str = DEFAULT_DHARMA_HOME) -> tuple[Path | None, dict[str, Any]]:
    path = latest_source_index_path(dharma_home)
    if path is None:
        return None, {}
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path, {}


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _query_observed_at(packet: dict[str, Any]) -> datetime:
    raw = str(packet.get("observed_at") or "")
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        return datetime.fromisoformat(raw).astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _wiki_markdown_paths(dharma_home: Path | str = DEFAULT_DHARMA_HOME) -> list[Path]:
    home = Path(dharma_home).expanduser()
    paths: list[Path] = []
    wiki_home = home / WIKI_HOME
    if wiki_home.exists():
        paths.append(wiki_home)
    source_dir = home / WIKI_SOURCE_DIR
    if source_dir.exists():
        paths.extend(
            sorted(
                path
                for path in source_dir.rglob("*.md")
                if path.is_file() and "source-cards-archive" not in path.parts
            )
        )
    deduped: dict[str, Path] = {str(path): path for path in paths}
    return [deduped[key] for key in sorted(deduped)]


def _prune_stale_palantir_wiki_documents(db_path: Path, active_paths: set[str]) -> int:
    from dharma_swarm.engine.event_memory import ensure_memory_plane_schema_sync

    with sqlite3.connect(str(db_path)) as db:
        ensure_memory_plane_schema_sync(db)
        rows = db.execute(
            "SELECT doc_id, source_path FROM source_documents WHERE source_kind = ?",
            ("palantir_pilot_wiki",),
        ).fetchall()
        stale_doc_ids = [
            str(doc_id)
            for doc_id, source_path in rows
            if str(source_path) not in active_paths
            or "source-cards-archive" in Path(str(source_path)).parts
        ]
        for doc_id in stale_doc_ids:
            db.execute("DELETE FROM source_chunks WHERE doc_id = ?", (doc_id,))
            db.execute("DELETE FROM source_documents WHERE doc_id = ?", (doc_id,))
        db.commit()
    return len(stale_doc_ids)


def _catalog_documents_from_source_index(
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    batch_size: int = 75,
) -> list[tuple[str, str, str, dict[str, Any]]]:
    index_path, payload = _load_latest_source_index(dharma_home)
    rows_raw = payload.get("urls")
    rows = [row for row in rows_raw if isinstance(row, dict)] if isinstance(rows_raw, list) else []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        family = str(row.get("family") or "unknown")
        grouped.setdefault(family, []).append(row)

    documents: list[tuple[str, str, str, dict[str, Any]]] = []
    for family in sorted(grouped):
        family_rows = sorted(grouped[family], key=lambda row: str(row.get("loc") or ""))
        lines = [
            f"# Palantir Pilot Source Catalog - {family}",
            "",
            f"Source index: `{index_path or ''}`",
            f"URL count: {len(family_rows)}",
            "",
            "Boundary: public sitemap metadata only. This catalog stores URLs and metadata, not Palantir page bodies or course material.",
            "",
        ]
        size = max(1, batch_size)
        for batch_number, start in enumerate(range(0, len(family_rows), size), start=1):
            end = min(start + size, len(family_rows))
            lines.extend([f"## URLs {start + 1}-{end}", ""])
            for row in family_rows[start:end]:
                lines.append(
                    "- {url} | lastmod={lastmod} | changefreq={changefreq} | sitemap={sitemap}".format(
                        url=str(row.get("loc") or ""),
                        lastmod=str(row.get("lastmod") or ""),
                        changefreq=str(row.get("changefreq") or ""),
                        sitemap=str(row.get("sitemap") or ""),
                    )
                )
            lines.append("")
        metadata = {
            "agent_id": AGENT_ID,
            "callsign": CALLSIGN,
            "family": family,
            "source_index": str(index_path) if index_path else "",
            "url_count": len(family_rows),
            "boundary": "public sitemap metadata only",
        }
        documents.append(
            (
                family,
                f"palantir-pilot/source-catalog/{family}.md",
                "\n".join(lines),
                metadata,
            )
        )
    return documents


def index_workspace_to_memory_plane(
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    db_path: Path | str | None = None,
    source_url_batch_size: int = 75,
) -> dict[str, Any]:
    """Index Palantir Pilot wiki notes and source URL catalogs into Memory Palace.

    The indexed source catalog contains sitemap URL metadata only. It never
    stores Palantir page bodies, Learn course content, videos, labs, or private
    tenant material.
    """

    from dharma_swarm.engine.unified_index import UnifiedIndex

    home = Path(dharma_home).expanduser()
    db = Path(db_path).expanduser() if db_path else memory_plane_db_path(home)
    index = UnifiedIndex(db)

    wiki_paths = _wiki_markdown_paths(home)
    pruned_wiki_documents = _prune_stale_palantir_wiki_documents(
        db,
        {str(path) for path in wiki_paths},
    )
    wiki_documents = 0
    for path in wiki_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        index.index_document(
            "palantir_pilot_wiki",
            str(path),
            text,
            {
                "agent_id": AGENT_ID,
                "callsign": CALLSIGN,
                "source_role": "palantir_pilot_wiki_note",
                "boundary": "original notes and source-grounded summaries only",
            },
        )
        wiki_documents += 1

    source_catalog_documents = 0
    source_urls = 0
    for _family, source_path, text, metadata in _catalog_documents_from_source_index(
        dharma_home=home,
        batch_size=source_url_batch_size,
    ):
        index.index_document(
            "palantir_pilot_source_catalog",
            source_path,
            text,
            metadata,
        )
        source_catalog_documents += 1
        source_urls += int(metadata.get("url_count") or 0)

    return {
        "schema_version": "palantir_pilot.memory_plane_index_receipt.v1",
        "agent": {"id": AGENT_ID, "callsign": CALLSIGN},
        "observed_at": _utc_now(),
        "db_path": str(db),
        "wiki_documents_indexed": wiki_documents,
        "source_catalog_documents_indexed": source_catalog_documents,
        "source_urls_indexed": source_urls,
        "pruned_wiki_documents": pruned_wiki_documents,
        "source_kinds": list(DATABASE_SOURCE_KINDS),
        "storage_boundary": "URLs, metadata, original wiki notes, and summaries only; no full page/course mirroring",
        "index_stats": index.stats(),
    }


def query_source_index(
    query: str,
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    limit: int = 10,
    family: str | None = None,
) -> list[dict[str, Any]]:
    """Search the URL/metadata-only source index.

    The result intentionally contains source metadata only. It never reads or
    returns Palantir page bodies.
    """

    terms = _query_terms(query)
    if not terms:
        return []
    _path, payload = _load_latest_source_index(dharma_home)
    rows = payload.get("urls")
    if not isinstance(rows, list):
        return []

    hits: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_family = str(row.get("family") or "")
        if family and row_family != family:
            continue
        searchable = " ".join(
            str(row.get(key) or "")
            for key in ("loc", "family", "sitemap", "lastmod", "changefreq")
        )
        score = _score_text(searchable, terms)
        if score <= 0:
            continue
        hits.append(
            {
                "score": score,
                "url": str(row.get("loc") or ""),
                "family": row_family,
                "lastmod": str(row.get("lastmod") or ""),
                "sitemap": str(row.get("sitemap") or ""),
            }
        )

    hits.sort(key=lambda item: (-int(item["score"]), item["family"], item["url"]))
    return hits[: max(0, limit)]


def _snippet(text: str, terms: list[str], *, max_chars: int = 260) -> str:
    collapsed = " ".join(text.split())
    lower = collapsed.lower()
    start = 0
    positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
    if positions:
        start = max(0, min(positions) - 80)
    end = min(len(collapsed), start + max_chars)
    prefix = "..." if start else ""
    suffix = "..." if end < len(collapsed) else ""
    return f"{prefix}{collapsed[start:end]}{suffix}"


def query_wiki_notes(
    query: str,
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search Palantir Pilot markdown notes and return short snippets."""

    terms = _query_terms(query)
    if not terms:
        return []
    candidates = _wiki_markdown_paths(dharma_home)

    hits: list[dict[str, Any]] = []
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        score = _score_wiki_note(path, text, terms)
        if score <= 0:
            continue
        hits.append(
            {
                "score": score,
                "path": str(path),
                "snippet": _snippet(text, terms),
            }
        )
    hits.sort(key=lambda item: (-int(item["score"]), item["path"]))
    return hits[: max(0, limit)]


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
            "Local search over source metadata and original wiki notes only; "
            "no private Palantir material and no full page/course body storage."
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
            "Public-source workspace synthesis over URL metadata and original wiki notes only; "
            "no private Palantir material and no full page/course body storage."
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


__all__ = [
    "build_answer_packet",
    "build_answer_packet_from_query_packet",
    "build_query_packet",
    "index_workspace_to_memory_plane",
    "query_source_index",
    "query_wiki_notes",
    "record_query_packet_to_memory_plane",
    "_load_latest_source_index",
]
