"""Deterministic wiki maintenance after chetana promotion."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import staging as staging_mod
from .provenance import parse_frontmatter
from .wiki_log import append_wiki_log


CONTRADICTION_MARKERS = ("contradict", "conflict", "supersede", "disagree")


@dataclass
class CrossUpdateResult:
    atom_path: Path
    index_path: Path
    backlinks_updated: list[Path] = field(default_factory=list)
    missing_related: list[str] = field(default_factory=list)
    contradictions_flagged: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def cross_update_trusted(atom_path: Path, *, append_log: bool = True) -> CrossUpdateResult:
    """Update index/backlinks/contradiction ledger for one trusted atom."""
    atom_path = Path(atom_path).expanduser().resolve()
    schema, body = parse_frontmatter(atom_path.read_text(encoding="utf-8"), source_path=str(atom_path))
    if schema is None:
        raise ValueError(f"{atom_path} has no chetana frontmatter")

    wiki_root = staging_mod.WIKI_ROOT
    index_path = wiki_root / "index.md"
    result = CrossUpdateResult(atom_path=atom_path, index_path=index_path)

    _upsert_index_entry(index_path, atom_path, schema.title, schema.atom_id)
    for related in schema.related:
        related_path = staging_mod.trusted_path_for(related, root=staging_mod.TRUSTED_DEFAULT)
        if not related_path.exists():
            result.missing_related.append(related)
            continue
        _append_unique_line(
            related_path,
            "## Backlinks",
            f"- {_wiki_link(atom_path, schema.title, wiki_root)}",
        )
        result.backlinks_updated.append(related_path)

    if any(marker in body.lower() for marker in CONTRADICTION_MARKERS):
        ledger = wiki_root / "contradictions.md"
        _append_unique_line(
            ledger,
            "## Flagged During Cross-Update",
            f"- {_wiki_link(atom_path, schema.title, wiki_root)}",
            title="# Contradictions",
        )
        result.contradictions_flagged.append(ledger)

    if append_log:
        log_path = append_wiki_log(
            operation="cross-update",
            title=schema.title,
            atom_path=atom_path,
            atom_id=schema.atom_id,
        )
        result.notes.append(f"log appended -> {log_path}")
    return result


def cross_update_summary(result: CrossUpdateResult) -> str:
    return "\n".join(
        [
            "# chetana cross-update",
            f"- atom: {result.atom_path}",
            f"- index: {result.index_path}",
            f"- backlinks_updated: {len(result.backlinks_updated)}",
            f"- missing_related: {len(result.missing_related)}",
            f"- contradictions_flagged: {len(result.contradictions_flagged)}",
        ]
    )


def _upsert_index_entry(index_path: Path, atom_path: Path, title: str, atom_id: str) -> None:
    line = f"- {_wiki_link(atom_path, title, staging_mod.WIKI_ROOT)} — atom_id={atom_id}"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    if not index_path.exists():
        index_path.write_text("# Index\n\n## Concepts\n\n", encoding="utf-8")
    lines = index_path.read_text(encoding="utf-8").splitlines()
    link_key = _wiki_link(atom_path, title, staging_mod.WIKI_ROOT).split("|", 1)[0]
    replaced = False
    for idx, existing in enumerate(lines):
        if existing.startswith("- [[") and link_key in existing:
            lines[idx] = line
            replaced = True
            break
    if not replaced:
        if "## Concepts" not in lines:
            lines.extend(["", "## Concepts"])
        lines.append(line)
    index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _append_unique_line(path: Path, section: str, line: str, *, title: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else (title or f"# {path.stem}") + "\n"
    if line in text:
        return
    if section not in text:
        text = text.rstrip() + f"\n\n{section}\n"
    text = text.rstrip() + f"\n{line}\n"
    path.write_text(text, encoding="utf-8")


def _wiki_link(path: Path, title: str, wiki_root: Path) -> str:
    try:
        rel = path.relative_to(wiki_root).with_suffix("")
    except ValueError:
        rel = path.with_suffix("")
    return f"[[{rel.as_posix()}|{title}]]"
