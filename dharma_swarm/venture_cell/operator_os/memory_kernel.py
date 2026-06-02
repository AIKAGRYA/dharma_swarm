"""Read-through MemoryKernel index for the Operator OS projection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

DEFAULT_QUERY_TERMS = (
    "Polsia",
    "Cofounder",
    "VentureCell",
    "Operator OS",
    "Darshan",
    "external reader",
    "Go evidence receipt",
    "Chetana",
    "MemoryKernel",
)


@dataclass(frozen=True)
class MemoryKernelIndexEntry:
    """One readable wiki/staging atom reference."""

    tier: str
    path: str
    title: str
    excerpt: str
    matched_terms: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryKernelReadThroughIndex:
    """Bounded read-through index over existing Chetana/wiki roots."""

    status: str
    staged_count: int
    trusted_count: int
    quarantine_count: int
    truncated: bool
    source_roots: tuple[str, ...]
    entries: tuple[MemoryKernelIndexEntry, ...] = ()
    query_terms: tuple[str, ...] = DEFAULT_QUERY_TERMS

    @property
    def indexed_count(self) -> int:
        return len(self.entries)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["indexed_count"] = self.indexed_count
        return value


def build_memory_kernel_index(
    *,
    staging_root: Path,
    trusted_root: Path,
    quarantine_root: Path,
    max_scan: int = 5000,
    max_entries: int = 80,
    query_terms: Iterable[str] = DEFAULT_QUERY_TERMS,
) -> MemoryKernelReadThroughIndex:
    """Build a bounded read-only index without promoting or mutating atoms."""

    terms = tuple(
        dict.fromkeys(str(term).strip() for term in query_terms if str(term).strip())
    )
    roots = (
        ("staged", staging_root),
        ("trusted", trusted_root),
        ("quarantine", quarantine_root),
    )
    entries: list[MemoryKernelIndexEntry] = []
    counts = {"staged": 0, "trusted": 0, "quarantine": 0}
    truncated = False

    for tier, root in roots:
        count, tier_truncated, tier_entries = _scan_root(
            root=root,
            tier=tier,
            terms=terms,
            max_scan=max_scan,
            remaining=max(0, max_entries - len(entries)),
        )
        counts[tier] = count
        truncated = truncated or tier_truncated
        entries.extend(tier_entries)

    if not any(counts.values()):
        status = "empty"
    elif entries:
        status = "available_truncated" if truncated else "available"
    else:
        status = "count_only"

    return MemoryKernelReadThroughIndex(
        status=status,
        staged_count=counts["staged"],
        trusted_count=counts["trusted"],
        quarantine_count=counts["quarantine"],
        truncated=truncated,
        source_roots=tuple(str(root) for _, root in roots),
        entries=tuple(entries),
        query_terms=terms,
    )


def _scan_root(
    *,
    root: Path,
    tier: str,
    terms: tuple[str, ...],
    max_scan: int,
    remaining: int,
) -> tuple[int, bool, list[MemoryKernelIndexEntry]]:
    resolved = root.expanduser()
    if not resolved.exists():
        return 0, False, []

    entries: list[MemoryKernelIndexEntry] = []
    count = 0
    for path in sorted(resolved.rglob("*.md")):
        if not path.is_file():
            continue
        count += 1
        if remaining > 0:
            entry = _read_index_entry(path, tier=tier, terms=terms)
            if entry.matched_terms or len(entries) < min(remaining, 8):
                entries.append(entry)
                remaining -= 1
        if count >= max_scan:
            return count, True, entries
    return count, False, entries


def _read_index_entry(path: Path, *, tier: str, terms: tuple[str, ...]) -> MemoryKernelIndexEntry:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        text = ""
    title = (
        _first_title(text)
        or path.stem.replace("_", " ").replace("-", " ").strip()
        or path.name
    )
    sample = text[:4000]
    matched = tuple(
        term for term in terms if term.casefold() in f"{path} {sample}".casefold()
    )
    return MemoryKernelIndexEntry(
        tier=tier,
        path=str(path),
        title=title[:160],
        excerpt=_excerpt(sample),
        matched_terms=matched,
    )


def _first_title(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""


def _excerpt(text: str) -> str:
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("---")
    ]
    return " ".join(lines)[:360]
