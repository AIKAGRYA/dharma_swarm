"""Memory Census Engine — reproducible surface inventory.

Walks the dharma_swarm + Claude Code + ~/.dharma + ~/.smriti substrates,
emits one structured `MemorySurface` record per durable persistence surface,
writes JSONL to ``~/.dharma/meta/memory_census/<iso>.jsonl``.

Designed as the ground-truth side of an inventory pipeline: this module
*measures*, the companion plan *classifies*. Heuristic fields are suffixed
``_hint`` so callers can distinguish measurement from inference.

Usage:
    python -m dharma_swarm.memory_census scan
    python -m dharma_swarm.memory_census scan --roots dharma_swarm ~/.dharma
    python -m dharma_swarm.memory_census diff <prior.jsonl> <current.jsonl>

Read-only: this module never deletes, migrates, or rewrites any surface
it scans. The single write it performs is the JSONL output of its own
scan, owned and gated like any other ~/.dharma writer (see
docs/governance/STATE_DIR_OWNERS.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

CENSUS_VERSION = 1

# Reconciliation tags — every prior claim about this surface gets one of:
RECONCILIATION_TAGS = ("verified", "probable", "stale", "false", "needs_owner")

# Substrate kinds we recognize. ``other`` is the catch-all.
KNOWN_SUBSTRATES = (
    "python_module",
    "jsonl",
    "sqlite",
    "markdown",
    "json",
    "parquet",
    "directory",
    "log",
    "other",
)

# Heuristic class buckets (Codex's taxonomy, with `_hint` suffix to make
# clear these are inferred, not measured).
KNOWN_CLASSES = (
    "write_authority",
    "projection",
    "distiller",
    "agent_local",
    "human_curated",
    "external_mcp",
    "dormant_promise",
    "diagnostic",
    "unknown",
)


@dataclass(frozen=True)
class MemorySurface:
    """One durable memory surface in the ecosystem.

    Fields without ``_hint`` are measured. Fields with ``_hint`` are
    heuristic and may be wrong — they are inputs to the classification
    step, not its output.
    """

    surface_id: str
    path: str
    substrate: str
    size_bytes: int
    last_modified: str
    owner_module_hint: str | None
    in_state_dir_owners: bool
    in_semgrep_allowlist: bool
    write_call_sites: list[str] = field(default_factory=list)
    read_call_sites: list[str] = field(default_factory=list)
    class_hint: str = "unknown"
    risk_hint: str = "low"
    reconciliation_tag: str = "needs_owner"
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stable surface_id
# ---------------------------------------------------------------------------


def _surface_id(path: str) -> str:
    """Deterministic 16-char id derived from the absolute path string."""
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Substrate detection
# ---------------------------------------------------------------------------

_SUFFIX_TO_SUBSTRATE = {
    ".py": "python_module",
    ".jsonl": "jsonl",
    ".db": "sqlite",
    ".sqlite": "sqlite",
    ".sqlite3": "sqlite",
    ".md": "markdown",
    ".json": "json",
    ".parquet": "parquet",
    ".log": "log",
}


def _detect_substrate(path: Path) -> str:
    if path.is_dir():
        return "directory"
    suffix = path.suffix.lower()
    return _SUFFIX_TO_SUBSTRATE.get(suffix, "other")


# ---------------------------------------------------------------------------
# Size measurement
# ---------------------------------------------------------------------------


def _size_bytes(path: Path) -> int:
    """File size for files; recursive du for directories."""
    try:
        if path.is_file():
            return path.stat().st_size
        if path.is_dir():
            total = 0
            for sub in path.rglob("*"):
                try:
                    if sub.is_file():
                        total += sub.stat().st_size
                except (OSError, PermissionError):
                    continue
            return total
    except (OSError, PermissionError):
        pass
    return 0


def _last_modified(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (OSError, PermissionError):
        return ""


# ---------------------------------------------------------------------------
# Governance lookup
# ---------------------------------------------------------------------------


def _load_state_dir_owners(repo_root: Path) -> set[str]:
    """Return the set of owner-module paths documented in STATE_DIR_OWNERS.md.

    Parses lines that contain a backtick-quoted module path beginning with
    ``dharma_swarm/``. Tolerates absent file (returns empty set).
    """
    doc = repo_root / "docs" / "governance" / "STATE_DIR_OWNERS.md"
    if not doc.exists():
        return set()
    owners: set[str] = set()
    for line in doc.read_text(encoding="utf-8").splitlines():
        for match in re.findall(r"`(dharma_swarm/[\w./_-]+\.py)`", line):
            owners.add(match)
    return owners


def _load_semgrep_allowlist(repo_root: Path) -> set[str]:
    """Return the set of paths in the semgrep dharma-anti-slop allowlist."""
    yml = repo_root / ".semgrep" / "dharma-anti-slop.yml"
    if not yml.exists():
        return set()
    paths: set[str] = set()
    for line in yml.read_text(encoding="utf-8").splitlines():
        match = re.search(r'-\s+"(dharma_swarm/[\w./_-]+\.py)"', line)
        if match:
            paths.add(match.group(1))
    return paths


# ---------------------------------------------------------------------------
# Owner module hint via grep
# ---------------------------------------------------------------------------

_DHARMA_PATH_PATTERN = re.compile(r'Path\.home\(\)\s*/\s*"\.dharma"')


def _find_dharma_writers(repo_root: Path) -> dict[str, str]:
    """Return a map of ``rel/path/under/.dharma`` → ``owner.py`` for every
    Python file in the repo that references ``Path.home() / ".dharma" / ...``.

    The mapping is best-effort: it picks the first python module that
    references each ~/.dharma sub-path. Multi-owner cases get whichever
    file scans first; a follow-up classifier should disambiguate.
    """
    writers: dict[str, str] = {}
    pkg_root = repo_root / "dharma_swarm"
    if not pkg_root.exists():
        return writers
    for py in pkg_root.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not _DHARMA_PATH_PATTERN.search(text):
            continue
        rel_owner = str(py.relative_to(repo_root))
        # Extract the literal path tail from each reference: each line is roughly
        # ``Path.home() / ".dharma" / "stigmergy" / "marks.jsonl"``
        for match in re.finditer(
            r'Path\.home\(\)\s*/\s*"\.dharma"((?:\s*/\s*"[^"]+")+)', text
        ):
            tail = "/".join(re.findall(r'"([^"]+)"', match.group(1)))
            writers.setdefault(tail, rel_owner)
    return writers


# ---------------------------------------------------------------------------
# Classifier (heuristic — _hint fields)
# ---------------------------------------------------------------------------

_PYTHON_CLASS_HINTS = (
    (re.compile(r"class\s+\w*Store\b"), "write_authority"),
    (re.compile(r"class\s+\w*Ledger\b"), "write_authority"),
    (re.compile(r"class\s+\w*Registry\b"), "write_authority"),
    (re.compile(r"class\s+\w*Index\b"), "projection"),
    (re.compile(r"class\s+\w*Retriever\b"), "projection"),
    (re.compile(r"class\s+\w*Cache\b"), "projection"),
    (re.compile(r"class\s+\w*Memory\b"), "agent_local"),
    (re.compile(r"\bdef\s+decay\b|\bdef\s+revive\b|\bdef\s+prune\b"), "distiller"),
)


def _classify_python(text: str) -> str:
    for pattern, label in _PYTHON_CLASS_HINTS:
        if pattern.search(text):
            return label
    return "unknown"


def _risk_for(surface: MemorySurface) -> str:
    """Crude risk: critical if huge+ungoverned, low if governed+small."""
    gb = surface.size_bytes / (1024**3)
    if gb >= 50 and not surface.in_state_dir_owners:
        return "critical"
    if gb >= 10 and not surface.in_state_dir_owners:
        return "high"
    if surface.size_bytes >= 100 * 1024**2 and not surface.in_state_dir_owners:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Surface candidate generators
# ---------------------------------------------------------------------------

# Patterns that suggest a Python file is a memory module.
_MEMORY_FILENAME_TOKENS = (
    "memory", "store", "ledger", "archive", "log", "journal", "cache",
    "buffer", "history", "registry", "recorder", "recall", "remember",
    "replay", "episode", "stigmergy", "trace", "witness", "digest",
    "ledger", "vector_store", "graph", "lattice", "palace",
)


def _is_python_memory_candidate(path: Path) -> bool:
    name = path.name.lower()
    if not name.endswith(".py"):
        return False
    return any(tok in name for tok in _MEMORY_FILENAME_TOKENS)


# Top-level subdirs of ~/.dharma to enumerate as surfaces (each child file
# or top-level dir becomes its own surface).
_DHARMA_SURFACE_GLOBS = (
    "*.jsonl",
    "*.json",
    "*.db",
    "*.md",
    "*.canvas",
    "**/marks.jsonl",
    "**/archive.jsonl",
    "**/experiments.jsonl",
    "**/meta_archive.jsonl",
    "**/witness_*.jsonl",
    "**/_pending.jsonl",
    "**/mutations.jsonl",
)


def _walk_dharma_surfaces(dharma_root: Path) -> Iterator[Path]:
    """Yield ~/.dharma surfaces: top-level files + per-stream dirs."""
    if not dharma_root.exists():
        return
    seen: set[Path] = set()
    # Top-level files
    for entry in dharma_root.iterdir():
        if entry.is_file() and entry not in seen:
            seen.add(entry)
            yield entry
    # Each top-level subdir is itself a surface (treat directory as one)
    for entry in dharma_root.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            seen.add(entry)
            yield entry
    # Plus any deep JSONL/SQLite/Parquet/Canvas files we want individual rows for
    for pattern in _DHARMA_SURFACE_GLOBS:
        for match in dharma_root.glob(pattern):
            if match not in seen:
                seen.add(match)
                yield match


def _walk_python_memory_modules(
    pkg_root: Path,
    *,
    extra_owners: Iterable[str] = (),
) -> Iterator[Path]:
    """Walk Python memory modules.

    A file is included if either (a) the filename matches a memory-token
    heuristic, or (b) the file appears as a known ``~/.dharma/`` writer.
    The (b) path catches modules whose names don't match memory tokens
    but whose semantics make them memory authorities (e.g.
    ``register_disciplines.py``).
    """
    if not pkg_root.exists():
        return
    extra_set = {str(o) for o in extra_owners}
    repo_root = pkg_root.parent
    for py in pkg_root.rglob("*.py"):
        if _is_python_memory_candidate(py):
            yield py
            continue
        try:
            rel = str(py.relative_to(repo_root))
        except ValueError:
            continue
        if rel in extra_set:
            yield py


def _walk_human_curated(claude_root: Path) -> Iterator[Path]:
    """Cabinet, agent-memory, projects/<this>/memory."""
    candidates = [
        claude_root / "cabinet",
        claude_root / "agent-memory",
        claude_root / "projects" / "-Users-dhyana" / "memory",
        claude_root / "homunculus",
    ]
    for c in candidates:
        if c.exists():
            yield c


def _walk_smriti(smriti_root: Path) -> Iterator[Path]:
    if smriti_root.exists():
        yield smriti_root


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------


def _make_surface(
    path: Path,
    *,
    repo_root: Path,
    state_dir_owners: set[str],
    semgrep_allowlist: set[str],
    dharma_writers: dict[str, str],
) -> MemorySurface:
    """Construct a MemorySurface from a candidate path."""
    abs_path = str(path.resolve())
    substrate = _detect_substrate(path)
    notes: list[str] = []
    owner_hint: str | None = None
    in_owners = False
    in_allowlist = False
    class_hint = "unknown"
    write_calls: list[str] = []
    read_calls: list[str] = []

    if substrate == "python_module":
        rel = ""
        try:
            rel = str(path.relative_to(repo_root))
        except ValueError:
            rel = abs_path
        owner_hint = rel
        in_owners = rel in state_dir_owners
        in_allowlist = rel in semgrep_allowlist
        try:
            text = path.read_text(encoding="utf-8")
            class_hint = _classify_python(text)
        except (OSError, UnicodeDecodeError):
            class_hint = "unknown"
            notes.append("could_not_read_python_source")

    elif str(path).startswith(str(Path.home() / ".dharma")):
        # ~/.dharma surface — cross-reference the writer map
        rel_under = str(path.relative_to(Path.home() / ".dharma"))
        owner_hint = dharma_writers.get(rel_under)
        if owner_hint is None:
            # Try parent (e.g. witness/ matches a writer that produces witness/witness_*.jsonl)
            parent_rel = str(path.parent.relative_to(Path.home() / ".dharma"))
            owner_hint = dharma_writers.get(parent_rel)
            if owner_hint is None:
                notes.append("owner_unresolved")
        in_owners = owner_hint in state_dir_owners if owner_hint else False
        in_allowlist = owner_hint in semgrep_allowlist if owner_hint else False
        class_hint = "write_authority" if owner_hint else "unknown"

    elif str(path).startswith(str(Path.home() / ".claude")):
        # Cabinet / agent-memory / projects → human-curated
        class_hint = "human_curated"
        owner_hint = None  # by design — human-curated has no Python owner
        notes.append("human_curated_no_module_owner")

    elif str(path).startswith(str(Path.home() / ".smriti")):
        class_hint = "agent_local"
        owner_hint = None
        notes.append("smriti_managed_via_skill")

    surface = MemorySurface(
        surface_id=_surface_id(abs_path),
        path=abs_path,
        substrate=substrate,
        size_bytes=_size_bytes(path),
        last_modified=_last_modified(path),
        owner_module_hint=owner_hint,
        in_state_dir_owners=in_owners,
        in_semgrep_allowlist=in_allowlist,
        class_hint=class_hint,
        write_call_sites=write_calls,
        read_call_sites=read_calls,
        notes=notes,
        reconciliation_tag="needs_owner" if class_hint == "unknown" or not in_owners else "probable",
    )
    # Risk depends on size+governance; recompute now that base fields are set
    return MemorySurface(**{**asdict(surface), "risk_hint": _risk_for(surface)})


def scan(
    *,
    repo_root: Path | None = None,
    home: Path | None = None,
) -> list[MemorySurface]:
    """Walk all candidate substrates and return a list of MemorySurface records.

    No I/O outside reads. Caller chooses where to persist the result.
    """
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    home = home or Path.home()

    state_dir_owners = _load_state_dir_owners(repo_root)
    semgrep_allowlist = _load_semgrep_allowlist(repo_root)
    dharma_writers = _find_dharma_writers(repo_root)

    surfaces: list[MemorySurface] = []
    seen: set[str] = set()

    sources: list[Iterable[Path]] = [
        _walk_python_memory_modules(
            repo_root / "dharma_swarm",
            extra_owners=set(dharma_writers.values())
            | state_dir_owners
            | semgrep_allowlist,
        ),
        _walk_dharma_surfaces(home / ".dharma"),
        _walk_human_curated(home / ".claude"),
        _walk_smriti(home / ".smriti"),
    ]

    for source in sources:
        for path in source:
            abs_path = str(path.resolve())
            if abs_path in seen:
                continue
            seen.add(abs_path)
            try:
                surfaces.append(
                    _make_surface(
                        path,
                        repo_root=repo_root,
                        state_dir_owners=state_dir_owners,
                        semgrep_allowlist=semgrep_allowlist,
                        dharma_writers=dharma_writers,
                    )
                )
            except Exception as exc:  # noqa: BLE001 — never abort census on a single surface
                surfaces.append(
                    MemorySurface(
                        surface_id=_surface_id(abs_path),
                        path=abs_path,
                        substrate="other",
                        size_bytes=0,
                        last_modified="",
                        owner_module_hint=None,
                        in_state_dir_owners=False,
                        in_semgrep_allowlist=False,
                        notes=[f"scan_error: {exc!r}"],
                        reconciliation_tag="needs_owner",
                    )
                )
    return surfaces


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_jsonl(surfaces: list[MemorySurface], output_path: Path) -> Path:
    """Write surfaces as JSONL, one row per surface, sorted by surface_id."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    surfaces_sorted = sorted(surfaces, key=lambda s: s.surface_id)
    with output_path.open("w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "_meta": {
                        "census_version": CENSUS_VERSION,
                        "scanned_at": datetime.now(timezone.utc).isoformat(),
                        "surface_count": len(surfaces_sorted),
                    }
                }
            )
            + "\n"
        )
        for s in surfaces_sorted:
            f.write(json.dumps(asdict(s), default=str) + "\n")
    return output_path


def default_output_path(home: Path | None = None) -> Path:
    home = home or Path.home()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return home / ".dharma" / "meta" / "memory_census" / f"{stamp}.jsonl"


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def diff_runs(prior_path: Path, current_path: Path) -> dict[str, list[str]]:
    """Return added / removed / changed_size surface_ids between two runs."""
    def _load(path: Path) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if "surface_id" in row:
                out[row["surface_id"]] = row
        return out

    prior = _load(prior_path)
    current = _load(current_path)
    added = sorted(set(current) - set(prior))
    removed = sorted(set(prior) - set(current))
    changed_size = sorted(
        sid for sid in (set(prior) & set(current))
        if prior[sid].get("size_bytes") != current[sid].get("size_bytes")
    )
    return {"added": added, "removed": removed, "changed_size": changed_size}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_scan(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    home = Path(args.home).resolve() if args.home else None
    surfaces = scan(repo_root=repo_root, home=home)
    output = Path(args.output).resolve() if args.output else default_output_path(home)
    write_jsonl(surfaces, output)
    by_class: dict[str, int] = {}
    by_risk: dict[str, int] = {}
    ungoverned = 0
    for s in surfaces:
        by_class[s.class_hint] = by_class.get(s.class_hint, 0) + 1
        by_risk[s.risk_hint] = by_risk.get(s.risk_hint, 0) + 1
        if not s.in_state_dir_owners and not s.in_semgrep_allowlist:
            ungoverned += 1
    print(f"surfaces: {len(surfaces)}")
    print(f"by class_hint: {dict(sorted(by_class.items()))}")
    print(f"by risk_hint: {dict(sorted(by_risk.items()))}")
    print(f"ungoverned: {ungoverned}")
    print(f"output: {output}")
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    result = diff_runs(Path(args.prior).resolve(), Path(args.current).resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="memory_census")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Scan substrates, emit JSONL census.")
    p_scan.add_argument("--repo-root", default=None)
    p_scan.add_argument("--home", default=None)
    p_scan.add_argument("--output", default=None)
    p_scan.set_defaults(func=_cmd_scan)

    p_diff = sub.add_parser("diff", help="Compare two prior census runs.")
    p_diff.add_argument("prior")
    p_diff.add_argument("current")
    p_diff.set_defaults(func=_cmd_diff)

    ns = parser.parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    sys.exit(main())
