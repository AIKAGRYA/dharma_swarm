#!/usr/bin/env python3
"""Backfill source-of-truth memory files into the vector projection.

This is deliberately not a blind fallback-embedding copy.  The historical
fallback table may contain stale or zero vectors, so this importer reads the
small canonical memory surfaces, creates fresh vector rows, and records a
resumable state file keyed by source digest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import struct
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.vector_store import VectorStore


TEXT_FILE_SUFFIXES = (
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".py",
)
EXCLUDED_TEXT_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "site-packages",
    "vendor",
}


@dataclass(frozen=True)
class SourceDocument:
    uid: str
    source: str
    content: str
    layer: str
    metadata: dict[str, Any]
    digest: str


@dataclass(frozen=True)
class MemorySourceBackfillReceipt:
    state_dir: str
    memory_jsonl_paths: tuple[str, ...]
    agents_context_paths: tuple[str, ...]
    text_file_paths: tuple[str, ...]
    candidate_rows: int
    selected_rows: int
    inserted_rows: int
    invalidated_rows: int
    skipped_rows: int
    dry_run: bool
    elapsed_ms: float
    state_path: str
    inserted_doc_ids: tuple[int, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def load_memory_jsonl(path: Path) -> list[SourceDocument]:
    docs: list[SourceDocument] = []
    if not path.exists():
        return docs
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        doc = _memory_record_to_doc(record, path=path, line_no=line_no, raw_line=line)
        if doc is not None:
            docs.append(doc)
    return docs


def load_agents_context(path: Path) -> list[SourceDocument]:
    docs: list[SourceDocument] = []
    if not path.exists():
        return docs

    context_title = ""
    current_date = ""
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("<") or line.startswith("</"):
            continue
        if line.startswith("# ["):
            context_title = line.lstrip("# ").strip()
            continue
        if line.startswith("### "):
            current_date = line.removeprefix("### ").strip()
            continue
        if line.startswith(("#", "Legend:", "Format:", "Fetch details:", "Stats:", "Access ")):
            continue

        match = re.match(r"^(?P<id>S?\d+)\s+(?P<body>.+)$", line)
        if not match:
            continue

        obs_id = match.group("id")
        body = _clean_agents_body(match.group("body"))
        if not body:
            continue
        content = "\n".join(
            part
            for part in (
                f"Claude memory context observation: {obs_id}",
                f"Context: {context_title}" if context_title else "",
                f"Date group: {current_date}" if current_date else "",
                f"Observation: {body}",
                f"Source file: {path}",
            )
            if part
        )
        metadata = {
            "importer": "vector_store_backfill_memory_sources",
            "source_file": str(path),
            "line_no": line_no,
            "observation_id": obs_id,
            "context_title": context_title,
            "date_group": current_date,
            "source_kind": "agents_context",
        }
        source_key = f"{path}:{obs_id}:{body}"
        source = _compact_source("agents_context", f"{path.name}:{obs_id}:{body}")
        docs.append(_source_doc(source_key, source, content, "memory_context", metadata))
    return docs


def load_text_file(path: Path) -> list[SourceDocument]:
    if not path.exists() or not path.is_file():
        return []
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="utf-8", errors="replace")
    content = content.strip()
    if not content:
        return []
    metadata = {
        "importer": "vector_store_backfill_memory_sources",
        "source_file": str(path),
        "source_kind": "text_file",
    }
    source = _compact_source("text_file", str(path))
    return [_source_doc(str(path), source, content, "source_file", metadata)]


def discover_text_files(
    roots: Iterable[Path],
    *,
    max_files: int = 256,
    max_bytes: int = 512 * 1024,
) -> tuple[Path, ...]:
    """Find a bounded, deterministic source-file corpus under local roots."""

    if max_files <= 0:
        return ()
    candidates: dict[str, Path] = {}
    for root in roots:
        root = Path(root).expanduser()
        if root.is_file():
            if _is_indexable_text_file(root, max_bytes=max_bytes):
                candidates[str(root.resolve())] = root
            continue
        if not root.exists() or not root.is_dir():
            continue
        for current, dirs, files in os.walk(root):
            dirs[:] = [
                dirname
                for dirname in dirs
                if dirname not in EXCLUDED_TEXT_DIRS and not dirname.endswith(".egg-info")
            ]
            current_path = Path(current)
            for filename in files:
                path = current_path / filename
                if _is_indexable_text_file(path, max_bytes=max_bytes):
                    candidates[str(path.resolve())] = path

    ordered = sorted(
        candidates.values(),
        key=lambda path: (-_text_file_priority(path), len(str(path)), str(path)),
    )
    return tuple(ordered[:max_files])


def backfill_memory_sources(
    *,
    state_dir: Path,
    memory_jsonl_paths: Iterable[Path],
    agents_context_paths: Iterable[Path],
    text_file_paths: Iterable[Path] = (),
    state_path: Path | None = None,
    dim: int = 128,
    limit: int | None = None,
    dry_run: bool = False,
) -> MemorySourceBackfillReceipt:
    started = time.perf_counter()
    state_dir = Path(state_dir).expanduser()
    state_path = Path(state_path or state_dir / "vector_memory_sources_backfill_state.json").expanduser()
    memory_paths = tuple(Path(path).expanduser() for path in memory_jsonl_paths)
    agents_paths = tuple(Path(path).expanduser() for path in agents_context_paths)
    text_paths = tuple(Path(path).expanduser() for path in text_file_paths)

    warnings: list[str] = []
    docs: list[SourceDocument] = []
    for path in memory_paths:
        docs.extend(load_memory_jsonl(path))
        if not path.exists():
            warnings.append(f"missing_memory_jsonl:{path}")
    for path in agents_paths:
        docs.extend(load_agents_context(path))
        if not path.exists():
            warnings.append(f"missing_agents_context:{path}")
    for path in text_paths:
        docs.extend(load_text_file(path))
        if not path.exists():
            warnings.append(f"missing_text_file:{path}")

    state = _read_state(state_path)
    pending = [doc for doc in docs if state.get(doc.uid) != doc.digest]
    skipped = len(docs) - len(pending)
    if limit is not None:
        pending = pending[: max(0, limit)]

    if dry_run or not pending:
        return MemorySourceBackfillReceipt(
            state_dir=str(state_dir),
            memory_jsonl_paths=tuple(str(path) for path in memory_paths),
            agents_context_paths=tuple(str(path) for path in agents_paths),
            text_file_paths=tuple(str(path) for path in text_paths),
            candidate_rows=len(docs),
            selected_rows=len(pending),
            inserted_rows=0,
            invalidated_rows=0,
            skipped_rows=skipped,
            dry_run=dry_run,
            elapsed_ms=_elapsed_ms(started),
            state_path=str(state_path),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    state_dir.mkdir(parents=True, exist_ok=True)
    store = VectorStore(state_dir=state_dir, dim=dim)
    contents = [doc.content for doc in pending]
    try:
        store._embedder.fit_add(contents)
        embeddings = store._embedder.embed(contents)
    except Exception as exc:
        warnings.append(f"embedding_failed:{type(exc).__name__}")
        embeddings = [[0.0] * dim for _ in pending]

    inserted_ids, invalidated_rows = _insert_documents(store, pending, embeddings, dim=dim)
    for doc in pending[: len(inserted_ids)]:
        state[doc.uid] = doc.digest
    _write_state(state_path, state)

    return MemorySourceBackfillReceipt(
        state_dir=str(state_dir),
        memory_jsonl_paths=tuple(str(path) for path in memory_paths),
        agents_context_paths=tuple(str(path) for path in agents_paths),
        text_file_paths=tuple(str(path) for path in text_paths),
        candidate_rows=len(docs),
        selected_rows=len(pending),
        inserted_rows=len(inserted_ids),
        invalidated_rows=invalidated_rows,
        skipped_rows=skipped,
        dry_run=False,
        elapsed_ms=_elapsed_ms(started),
        state_path=str(state_path),
        inserted_doc_ids=tuple(inserted_ids),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _memory_record_to_doc(
    record: dict[str, Any],
    *,
    path: Path,
    line_no: int,
    raw_line: str,
) -> SourceDocument | None:
    record_type = str(record.get("type") or "").strip()
    if record_type == "entity":
        name = str(record.get("name") or "").strip()
        if not name:
            return None
        entity_type = str(record.get("entityType") or "").strip()
        observations = [str(item) for item in record.get("observations") or [] if str(item).strip()]
        content = "\n".join(
            [
                f"Memory graph entity: {name}",
                f"Entity type: {entity_type}" if entity_type else "Entity type: unknown",
                "Observations:",
                *[f"- {item}" for item in observations],
            ]
        )
        metadata = {
            "importer": "vector_store_backfill_memory_sources",
            "source_file": str(path),
            "line_no": line_no,
            "record_type": record_type,
            "entity_name": name,
            "entity_type": entity_type,
            "source_kind": "memory_jsonl",
        }
        source = _compact_source("memory_graph", name)
        return _source_doc(f"{path}:{line_no}:{raw_line}", source, content, "memory_graph", metadata)

    if record_type == "relation":
        from_name = str(record.get("from") or "").strip()
        to_name = str(record.get("to") or "").strip()
        relation_type = str(record.get("relationType") or "").strip()
        if not from_name or not to_name:
            return None
        content = (
            "Memory graph relation: "
            f"{from_name} --{relation_type or 'related_to'}--> {to_name}"
        )
        metadata = {
            "importer": "vector_store_backfill_memory_sources",
            "source_file": str(path),
            "line_no": line_no,
            "record_type": record_type,
            "from": from_name,
            "to": to_name,
            "relation_type": relation_type,
            "source_kind": "memory_jsonl",
        }
        source = _compact_source("memory_relation", f"{from_name}:{relation_type}:{to_name}")
        return _source_doc(f"{path}:{line_no}:{raw_line}", source, content, "memory_graph", metadata)

    return None


def _insert_documents(
    store: VectorStore,
    docs: list[SourceDocument],
    embeddings: list[list[float]],
    *,
    dim: int,
) -> tuple[list[int], int]:
    conn = store._connect()
    now_iso = datetime.now(timezone.utc).isoformat()
    inserted_ids: list[int] = []
    invalidated_rows = 0
    try:
        has_vec0 = store._has_vec0(conn)
        if not has_vec0:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vec_embeddings_fallback (
                    rowid INTEGER PRIMARY KEY,
                    embedding BLOB
                )
                """
            )

        for doc, embedding in zip(docs, embeddings, strict=False):
            invalidated_rows += _invalidate_active_source_rows(conn, doc, now_iso)
            cursor = conn.execute(
                """
                INSERT INTO vec_documents
                    (content, source, layer, metadata_json, event_time, ingestion_time, confidence)
                VALUES (?, ?, ?, ?, ?, ?, 1.0)
                """,
                (
                    doc.content,
                    doc.source,
                    doc.layer,
                    json.dumps(doc.metadata, sort_keys=True),
                    now_iso,
                    now_iso,
                ),
            )
            doc_id = int(cursor.lastrowid or 0)
            if doc_id <= 0:
                continue
            packed = _pack_embedding(embedding, dim)
            if has_vec0:
                conn.execute(
                    "INSERT INTO vec_embeddings(rowid, embedding) VALUES (?, ?)",
                    (doc_id, packed),
                )
            else:
                conn.execute(
                    "INSERT INTO vec_embeddings_fallback(rowid, embedding) VALUES (?, ?)",
                    (doc_id, packed),
                )
            inserted_ids.append(doc_id)

        conn.commit()
        return inserted_ids, invalidated_rows
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def _invalidate_active_source_rows(
    conn: sqlite3.Connection,
    doc: SourceDocument,
    now_iso: str,
) -> int:
    """Expire prior active rows for the same stable source identity."""

    patch = json.dumps(
        {
            "invalidated_at": now_iso,
            "invalidated_by": "vector_store_backfill_memory_sources",
            "invalidated_reason": "source_uid_replaced",
            "replacement_source_digest": doc.digest,
        },
        sort_keys=True,
    )
    cursor = conn.execute(
        """
        UPDATE vec_documents
        SET valid_until = ?,
            metadata_json = json_patch(
                CASE
                    WHEN json_valid(metadata_json) THEN metadata_json
                    ELSE '{}'
                END,
                ?
            )
        WHERE valid_until IS NULL
          AND json_valid(metadata_json)
          AND json_extract(metadata_json, '$.source_uid') = ?
        """,
        (now_iso, patch, doc.uid),
    )
    return max(0, int(cursor.rowcount or 0))


def _source_doc(source_key: str, source: str, content: str, layer: str, metadata: dict[str, Any]) -> SourceDocument:
    digest = _sha256(content)
    uid = _sha256(source_key)
    return SourceDocument(
        uid=uid,
        source=source,
        content=content,
        layer=layer,
        metadata={**metadata, "source_digest": digest, "source_uid": uid},
        digest=digest,
    )


def _compact_source(prefix: str, key: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.:-]+", "-", key).strip("-").lower()
    clean = clean[:96].strip("-") or "record"
    return f"{prefix}:{clean}:{_sha256(key)[:12]}"


def _clean_agents_body(body: str) -> str:
    body = body.strip()
    body = re.sub(r'^"\s+', "", body)
    body = re.sub(r"^[^\w\[]+\s*", "", body)
    return body.strip()


def _pack_embedding(embedding: list[float], dim: int) -> bytes:
    values = list(embedding[:dim])
    if len(values) < dim:
        values.extend([0.0] * (dim - len(values)))
    return struct.pack(f"{dim}f", *values)


def _is_indexable_text_file(path: Path, *, max_bytes: int) -> bool:
    if path.suffix.lower() not in TEXT_FILE_SUFFIXES:
        return False
    try:
        if max_bytes > 0 and path.stat().st_size > max_bytes:
            return False
    except OSError:
        return False
    return True


def _text_file_priority(path: Path) -> int:
    lower = str(path).lower()
    name = path.name.lower()
    score = 0
    if name in {"agents.md", "claude.md", "readme.md"}:
        score += 100
    if "/.dharma/knowledge/wiki/" in lower:
        score += 90
    if "/docs/" in lower:
        score += 80
    if "/docs/missions/" in lower:
        score += 20
    if "/reports/governance/" in lower:
        score += 65
    elif "/reports/" in lower:
        score += 15
    if "/dharma_swarm/" in lower and path.suffix.lower() == ".py":
        score += 55
    if "/scripts/" in lower:
        score += 45
    if "/tests/" in lower:
        score += 30
    if path.suffix.lower() in {".md", ".txt"}:
        score += 10
    return score


def _read_state(path: Path) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return {str(key): str(value) for key, value in payload.items()}
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"  Resume state {path} unreadable ({type(exc).__name__}); starting fresh.",
            file=sys.stderr,
        )
        return {}
    return {}


def _write_state(path: Path, state: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 3)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=dharma_state_dir())
    parser.add_argument(
        "--memory-jsonl",
        action="append",
        type=Path,
        default=[],
        help="Memory JSONL source. Defaults to ~/.dharma/memory/memory.jsonl.",
    )
    parser.add_argument(
        "--agents-context",
        action="append",
        type=Path,
        default=[],
        help="AGENTS.md/claude-mem context source. Defaults to ~/AGENTS.md and ./AGENTS.md when present.",
    )
    parser.add_argument(
        "--text-file",
        action="append",
        type=Path,
        default=[],
        help="Arbitrary UTF-8 text/JSON/Markdown source file to import as one source_file row.",
    )
    parser.add_argument(
        "--text-file-root",
        action="append",
        type=Path,
        default=[],
        help="Directory or file root to discover bounded source_file rows from.",
    )
    parser.add_argument("--max-text-files", type=int, default=256)
    parser.add_argument("--max-text-file-bytes", type=int, default=512 * 1024)
    parser.add_argument("--state-path", type=Path)
    parser.add_argument("--dim", type=int, default=128)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--receipt-path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    memory_paths = args.memory_jsonl or [Path.home() / ".dharma/memory/memory.jsonl"]
    agents_paths = args.agents_context or [
        path for path in (Path.home() / "AGENTS.md", Path.cwd() / "AGENTS.md") if path.exists()
    ]
    discovered_text_paths = discover_text_files(
        args.text_file_root,
        max_files=args.max_text_files,
        max_bytes=args.max_text_file_bytes,
    )
    text_paths = tuple(dict.fromkeys([*args.text_file, *discovered_text_paths]))
    receipt = backfill_memory_sources(
        state_dir=args.state_dir,
        memory_jsonl_paths=memory_paths,
        agents_context_paths=agents_paths,
        text_file_paths=text_paths,
        state_path=args.state_path,
        dim=args.dim,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    payload = receipt.to_json()
    if args.receipt_path:
        args.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        args.receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            "memory source backfill: "
            f"selected={receipt.selected_rows} inserted={receipt.inserted_rows} "
            f"invalidated={receipt.invalidated_rows} "
            f"skipped={receipt.skipped_rows} elapsed_ms={receipt.elapsed_ms}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
