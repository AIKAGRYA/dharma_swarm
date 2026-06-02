"""Read-through MemoryKernel index for the Operator OS projection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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

MEMORY_KERNEL_EVAL_QUERIES = (
    "Polsia Cofounder VentureCell Operator OS",
    "Darshan external reader gate Go evidence receipt",
    "Go evidence receipt source_url event_uid accepted",
    "Cofounder Canvas Library Plan Execute publishing",
    "Chetana wiki memory kernel staged trusted quarantine",
    "VentureCell autonomy ladder external action approval",
)

EVAL_QUERY_TERMS = tuple(
    dict.fromkeys(
        (
            *DEFAULT_QUERY_TERMS,
            "source_url",
            "event_uid",
            "accepted",
            "Canvas",
            "Library",
            "Plan",
            "Execute",
            "publishing",
            "wiki",
            "staged",
            "trusted",
            "quarantine",
            "autonomy ladder",
            "external action approval",
        )
    )
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
class MemoryKernelQueryResult:
    """Deterministic recall result over the read-through index."""

    query: str
    status: str
    matches: tuple[MemoryKernelIndexEntry, ...] = ()
    missing_terms: tuple[str, ...] = ()
    tier_counts: dict[str, int] = field(default_factory=dict)
    truncated: bool = False
    source_roots: tuple[str, ...] = ()
    trusted_promotion_claimed: bool = False
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["matches"] = [match.to_dict() for match in self.matches]
        return value


@dataclass(frozen=True)
class MemoryKernelQueryEval:
    """Pass/fail eval wrapper for one MemoryKernel query."""

    query: str
    passed: bool
    status: str
    matched_count: int
    tier_counts: dict[str, int] = field(default_factory=dict)
    missing_terms: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    trusted_promotion_claimed: bool = False
    notes: tuple[str, ...] = ()

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
    query_terms: tuple[str, ...] = EVAL_QUERY_TERMS

    @property
    def indexed_count(self) -> int:
        return len(self.entries)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["indexed_count"] = self.indexed_count
        return value

    def query(
        self,
        query: str,
        *,
        max_results: int = 5,
        trusted_only: bool = False,
    ) -> MemoryKernelQueryResult:
        """Evaluate one agent recall query without mutating Chetana state."""

        return query_memory_kernel_index(
            self,
            query,
            max_results=max_results,
            trusted_only=trusted_only,
        )


def build_memory_kernel_index(
    *,
    staging_root: Path,
    trusted_root: Path,
    quarantine_root: Path,
    supplemental_staging_roots: Iterable[Path] = (),
    max_scan: int = 5000,
    max_entries: int = 80,
    query_terms: Iterable[str] = EVAL_QUERY_TERMS,
) -> MemoryKernelReadThroughIndex:
    """Build a bounded read-only index without promoting or mutating atoms."""

    terms = tuple(
        dict.fromkeys(str(term).strip() for term in query_terms if str(term).strip())
    )
    supplemental_roots = tuple(
        Path(root).expanduser()
        for root in supplemental_staging_roots
        if str(root).strip()
    )
    roots = (
        ("trusted", trusted_root),
        ("staged", staging_root),
        *(("staged", root) for root in supplemental_roots),
        ("quarantine", quarantine_root),
    )
    budgets = _root_budgets(len(roots), max_entries)
    entries: list[MemoryKernelIndexEntry] = []
    counts = {"staged": 0, "trusted": 0, "quarantine": 0}
    truncated = False

    for index, (tier, root) in enumerate(roots):
        count, tier_truncated, tier_entries = _scan_root(
            root=root,
            tier=tier,
            terms=terms,
            max_scan=max_scan,
            remaining=budgets[index],
        )
        counts[tier] += count
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


def query_memory_kernel_index(
    index: MemoryKernelReadThroughIndex,
    query: str,
    *,
    max_results: int = 5,
    trusted_only: bool = False,
) -> MemoryKernelQueryResult:
    """Run a deterministic query over indexed entries with provenance intact."""

    query_text = query.strip()
    folded_query = query_text.casefold()
    tokens = _query_tokens(query_text)
    scored: list[tuple[int, int, str, MemoryKernelIndexEntry]] = []
    candidate_matches: list[MemoryKernelIndexEntry] = []

    for entry in index.entries:
        haystack = _entry_haystack(entry)
        token_hits = tuple(token for token in tokens if token in haystack)
        configured_hits = tuple(
            term
            for term in index.query_terms
            if term.casefold() in folded_query and term.casefold() in haystack
        )
        if not token_hits and not configured_hits:
            continue
        candidate_matches.append(entry)
        if trusted_only and entry.tier != "trusted":
            continue
        score = (
            len(token_hits) * 4
            + len(configured_hits) * 2
            + _tier_priority(entry.tier)
        )
        scored.append((-score, _tier_sort_order(entry.tier), entry.path, entry))

    matches = tuple(row[3] for row in sorted(scored)[: max(0, max_results)])
    matched_haystacks = " ".join(_entry_haystack(entry) for entry in matches)
    missing_terms = tuple(token for token in tokens if token not in matched_haystacks)
    tier_counts = {
        tier: sum(1 for entry in matches if entry.tier == tier)
        for tier in ("trusted", "staged", "quarantine")
    }
    notes: list[str] = []
    if index.truncated:
        notes.append("index_scan_truncated")
    if trusted_only:
        notes.append("trusted_only_query")
    if candidate_matches and trusted_only and not matches:
        status = "trusted_missing"
        notes.append("only_untrusted_matches_available")
    elif matches:
        status = "available_truncated" if index.truncated else "available"
    elif not index.entries:
        status = "index_empty"
    else:
        status = "missing"

    return MemoryKernelQueryResult(
        query=query_text,
        status=status,
        matches=matches,
        missing_terms=missing_terms,
        tier_counts=tier_counts,
        truncated=index.truncated,
        source_roots=index.source_roots,
        trusted_promotion_claimed=False,
        notes=tuple(notes),
    )


def evaluate_memory_kernel_queries(
    index: MemoryKernelReadThroughIndex,
    queries: Iterable[str] = MEMORY_KERNEL_EVAL_QUERIES,
    *,
    max_results: int = 3,
) -> tuple[MemoryKernelQueryEval, ...]:
    """Evaluate the program-kernel query prompts against one read-through index."""

    evals: list[MemoryKernelQueryEval] = []
    for query in tuple(queries):
        result = query_memory_kernel_index(index, query, max_results=max_results)
        source_refs = tuple(match.path for match in result.matches if match.path)
        valid_tiers = all(
            match.tier in {"trusted", "staged", "quarantine"}
            for match in result.matches
        )
        passed = bool(
            result.matches
            and valid_tiers
            and source_refs
            and not result.missing_terms
            and not result.trusted_promotion_claimed
        )
        notes = list(result.notes)
        if not result.matches:
            notes.append("no_query_match")
        if result.missing_terms:
            notes.append("query_terms_missing")
        evals.append(
            MemoryKernelQueryEval(
                query=query,
                passed=passed,
                status=result.status,
                matched_count=len(result.matches),
                tier_counts=result.tier_counts,
                missing_terms=result.missing_terms,
                source_refs=source_refs,
                trusted_promotion_claimed=result.trusted_promotion_claimed,
                notes=tuple(dict.fromkeys(notes)),
            )
        )
    return tuple(evals)


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

    matched_entries: list[MemoryKernelIndexEntry] = []
    fallback_entries: list[MemoryKernelIndexEntry] = []
    count = 0
    for path in sorted(resolved.rglob("*.md")):
        if not path.is_file():
            continue
        count += 1
        entry = _read_index_entry(path, tier=tier, terms=terms)
        if entry.matched_terms:
            matched_entries.append(entry)
        elif len(fallback_entries) < min(remaining, 8):
            fallback_entries.append(entry)
        if count >= max_scan:
            return count, True, _select_entries(matched_entries, fallback_entries, remaining)
    return count, False, _select_entries(matched_entries, fallback_entries, remaining)


def _root_budgets(root_count: int, max_entries: int) -> tuple[int, ...]:
    if root_count <= 0:
        return ()
    if max_entries <= 0:
        return tuple(0 for _ in range(root_count))
    base = max_entries // root_count
    remainder = max_entries % root_count
    return tuple(base + (1 if index < remainder else 0) for index in range(root_count))


def _select_entries(
    matched_entries: list[MemoryKernelIndexEntry],
    fallback_entries: list[MemoryKernelIndexEntry],
    remaining: int,
) -> list[MemoryKernelIndexEntry]:
    if remaining <= 0:
        return []
    ranked = sorted(
        matched_entries,
        key=lambda entry: (-len(entry.matched_terms), entry.path),
    )
    selected = ranked[:remaining]
    if len(selected) < remaining:
        selected.extend(fallback_entries[: remaining - len(selected)])
    return selected


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


def _query_tokens(query: str) -> tuple[str, ...]:
    raw = []
    current: list[str] = []
    for char in query.casefold():
        if char.isalnum():
            current.append(char)
        elif current:
            raw.append("".join(current))
            current = []
    if current:
        raw.append("".join(current))
    stop_words = {"and", "for", "the", "with", "what", "why", "how", "can"}
    return tuple(
        dict.fromkeys(
            token for token in raw if token not in stop_words and len(token) >= 2
        )
    )


def _entry_haystack(entry: MemoryKernelIndexEntry) -> str:
    return " ".join(
        (
            entry.tier,
            entry.path,
            entry.title,
            entry.excerpt,
            " ".join(entry.matched_terms),
        )
    ).casefold()


def _tier_priority(tier: str) -> int:
    return {"trusted": 3, "staged": 2, "quarantine": 1}.get(tier, 0)


def _tier_sort_order(tier: str) -> int:
    return {"trusted": 0, "staged": 1, "quarantine": 2}.get(tier, 3)
