"""chetana.ingest — capture raw → staged atom.

Sources:
    session   — Claude Code JSONL transcript (one session = many staged atoms)
    webclip   — Obsidian Web Clipper markdown drop in inbox
    pdf       — file processed via Microsoft MarkItDown MCP
    note      — plain text/markdown handed in directly
    voice     — voice memo transcribed (placeholder; routes to MarkItDown)
    synthesis — agent-generated content (carries agent_id provenance)

Every ingest produces a StagedAtom on disk with proper frontmatter, NO provenance
(provenance is only added on promote). The atom_id is fresh; the source is the
original raw input.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .extractors import extract_via_markitdown, extract_webclip
from .provenance import (
    AtomSource,
    AtomType,
    FrontmatterSchema,
    PARAClass,
    SourceKind,
    default_stale_after,
    new_atom_id,
    now_iso,
)
from .staging import write_staged
from .stigmergy_emit import emit_mark
from .wiki_log import append_wiki_log

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    atoms: list[Path]
    staged_count: int
    skipped_count: int
    notes: list[str]


def ingest(
    *,
    source: str | Path,
    source_kind: SourceKind,
    title: str | None = None,
    atom_type: AtomType = "atomic",
    para_class: PARAClass | None = None,
    confidence: float = 0.5,
    captured_by: str = "chetana.ingest",
    tags: list[str] | None = None,
    related: list[str] | None = None,
) -> IngestResult:
    """Ingest a source into one or more staged atoms.

    For session JSONL: one staged atom per substantive turn.
    For all other kinds: one staged atom per call.
    """
    notes: list[str] = []
    atoms: list[Path] = []

    if source_kind == "session":
        atoms = _ingest_session(
            Path(source),
            title=title,
            captured_by=captured_by,
            tags=tags or [],
            related=related or [],
            confidence=confidence,
            para_class=para_class,
            notes=notes,
        )
    else:
        atom = _ingest_simple(
            source=source,
            source_kind=source_kind,
            title=title or _infer_title(source, source_kind),
            atom_type=atom_type,
            para_class=para_class,
            confidence=confidence,
            captured_by=captured_by,
            tags=tags or [],
            related=related or [],
        )
        atoms = [atom]

    result = IngestResult(
        atoms=atoms,
        staged_count=len(atoms),
        skipped_count=0,
        notes=notes,
    )

    # Best-effort stigmergy emit — once per ingest, not per atom.
    emit_mark(
        action="chetana.ingest",
        content=f"{source_kind} | {len(result.atoms)} atoms staged",
        connections=["chetana", "ingest", source_kind],
        salience=0.4,
    )
    try:
        append_wiki_log(
            operation="ingest",
            title=title or _infer_title(source, source_kind),
            atom_path=result.atoms[0] if result.atoms else None,
            atom_id=None,
        )
    except OSError as e:
        result.notes.append(f"log append failed: {e}")

    return result


def _ingest_simple(
    *,
    source: str | Path,
    source_kind: SourceKind,
    title: str,
    atom_type: AtomType,
    para_class: PARAClass | None,
    confidence: float,
    captured_by: str,
    tags: list[str],
    related: list[str],
) -> Path:
    body, src_path, title, tags = _load_simple_source(source, source_kind, title, tags)

    schema = FrontmatterSchema(
        title=title,
        atom_id=new_atom_id(),
        type=atom_type,
        para_class=para_class,
        confidence=confidence,
        source=[
            AtomSource(
                kind=source_kind,
                path=src_path,
                span=None,
                captured=now_iso(),
                captured_by=captured_by,
            )
        ],
        provenance=None,
        stale_after=default_stale_after(),
        related=related,
        tags=tags,
    )
    return write_staged(schema, body)


def _load_simple_source(
    source: str | Path,
    source_kind: SourceKind,
    title: str,
    tags: list[str],
) -> tuple[str, str, str, list[str]]:
    if isinstance(source, Path):
        if source_kind == "webclip":
            clip = extract_webclip(source)
            merged_tags = list(dict.fromkeys(tags + clip.tags))
            return clip.body, clip.source_url or str(source.resolve()), clip.title or title, merged_tags
        if source_kind in ("pdf", "document", "voice"):
            converted = extract_via_markitdown(source)
            if not converted.ok:
                raise RuntimeError(converted.error or "markitdown extraction failed")
            return converted.body, converted.source_path, title, tags
        return source.read_text(encoding="utf-8"), str(source.resolve()), title, tags
    return source, "<inline>", title, tags


def _ingest_session(
    jsonl_path: Path,
    *,
    title: str | None,
    captured_by: str,
    tags: list[str],
    related: list[str],
    confidence: float,
    para_class: PARAClass | None,
    notes: list[str],
) -> list[Path]:
    """Parse a Claude Code JSONL transcript into staged atoms.

    Heuristic: each user turn that produces a substantive assistant turn becomes
    one staged atom whose body is the assistant text (minus tool-use blocks).
    Trivial turns (yes/no, single-word) are skipped.
    """
    if not jsonl_path.exists():
        notes.append(f"session file missing: {jsonl_path}")
        return []

    atoms: list[Path] = []
    last_user_text = ""
    turn_idx = 0

    for line_idx, line in enumerate(jsonl_path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue

        kind = row.get("type") or row.get("role")
        text = _extract_text(row)
        if not text:
            continue

        if kind in ("user", "human"):
            last_user_text = text
            continue
        if kind not in ("assistant", "ai"):
            continue
        if len(text) < 80:
            continue
        turn_idx += 1
        slug_title = title or _summarize(last_user_text or text, max_chars=80)
        schema = FrontmatterSchema(
            title=f"{slug_title} — turn {turn_idx}",
            atom_id=new_atom_id(),
            type="atomic",
            para_class=para_class,
            confidence=confidence,
            source=[
                AtomSource(
                    kind="session",
                    path=str(jsonl_path.resolve()),
                    span=f"line:{line_idx}",
                    captured=now_iso(),
                    captured_by=captured_by,
                )
            ],
            provenance=None,
            stale_after=default_stale_after(),
            related=related,
            tags=tags + ["session-extract"],
        )
        body_md = (
            f"## Source turn\n\n> {last_user_text[:600]}\n\n## Assistant content\n\n{text}\n"
        )
        atoms.append(write_staged(schema, body_md))

    notes.append(f"session ingested: {len(atoms)} staged atoms from {jsonl_path}")
    return atoms


def _extract_text(row: dict[str, Any]) -> str:
    """Pull text content out of a session row, skipping tool blocks.

    Claude Code JSONL structure: ``row["message"]["content"]`` holds the
    actual payload (str for user prompts, list of content-blocks for
    assistant turns).  We try that path first, then fall back to legacy
    top-level ``content`` / ``message`` keys for non-CC formats.
    """
    # --- Primary path: CC JSONL nests content inside row.message ---
    msg = row.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
    else:
        # Legacy / non-CC: top-level content or treat message itself as content
        content = row.get("content") or msg

    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict) and "text" in content:
        return str(content["text"]).strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in ("text", "output_text") and item.get("text"):
                    parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(p.strip() for p in parts if p.strip()).strip()
    return ""


def _summarize(text: str, *, max_chars: int = 80) -> str:
    s = " ".join(text.split())
    return s[: max_chars - 1] + "…" if len(s) > max_chars else s


def _infer_title(source: str | Path, kind: SourceKind) -> str:
    if isinstance(source, Path):
        return source.stem.replace("-", " ").replace("_", " ").title()
    head = source.strip().split("\n", 1)[0]
    head = head.lstrip("# ").strip()
    return head[:120] if head else f"{kind} atom"
