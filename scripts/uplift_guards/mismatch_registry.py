"""INTERFACE_MISMATCH_MAP as an executable registry.

Reads docs/interface_mismatches.yaml — the machine-readable form of
INTERFACE_MISMATCH_MAP.md — and exposes a check that fails the commit
when a staged change touches a caller/callee pair flagged BLOCKER with
status=open.

This is the doc→code coupling: an entry can move from `open` to
`resolved` only when its pinned regression test passes.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - PyYAML is a project dep already
    yaml = None  # type: ignore

REGISTRY_REL_PATH = "docs/interface_mismatches.yaml"


def _local_path_candidates(ref: str) -> set[str]:
    """Return repo path candidates for a mismatch caller/callee reference."""
    base = ref.split(":", 1)[0] if ":" in ref else ref
    candidates = {base}
    if "/" not in base and base.startswith("dharma_swarm."):
        parts = base.split(".")
        for end in range(len(parts), 1, -1):
            candidates.add("/".join(parts[:end]) + ".py")
    return candidates


@dataclass(frozen=True)
class Mismatch:
    id: str
    severity: str
    status: str
    caller: str
    callee: str
    summary: str
    fixed_in: str = ""
    test_path: str = ""

    @property
    def is_open(self) -> bool:
        return self.status.lower() == "open"

    @property
    def caller_path(self) -> str:
        return self.caller.split(":", 1)[0] if ":" in self.caller else self.caller

    @property
    def callee_path(self) -> str:
        return self.callee.split(":", 1)[0] if ":" in self.callee else self.callee

    @property
    def path_candidates(self) -> set[str]:
        return _local_path_candidates(self.caller) | _local_path_candidates(self.callee)


@dataclass
class MismatchRegistry:
    entries: list[Mismatch] = field(default_factory=list)

    def open_blockers(self) -> list[Mismatch]:
        return [m for m in self.entries if m.is_open and m.severity.upper() == "BLOCKER"]

    def open_degraded(self) -> list[Mismatch]:
        return [m for m in self.entries if m.is_open and m.severity.upper() == "DEGRADED"]

    def matching_paths(self, paths: Iterable[str]) -> list[Mismatch]:
        path_set = set(paths)
        hits: list[Mismatch] = []
        for m in self.entries:
            if m.path_candidates & path_set:
                hits.append(m)
        return hits


def load_mismatch_registry(repo_root: Path | None = None) -> MismatchRegistry:
    repo_root = repo_root or Path.cwd()
    registry_path = repo_root / REGISTRY_REL_PATH
    if not registry_path.exists() or yaml is None:
        return MismatchRegistry(entries=[])
    raw = yaml.safe_load(registry_path.read_text()) or {}
    entries_raw = raw.get("entries", []) if isinstance(raw, dict) else []
    entries: list[Mismatch] = []
    for item in entries_raw:
        try:
            entries.append(
                Mismatch(
                    id=str(item["id"]),
                    severity=str(item.get("severity", "DEGRADED")),
                    status=str(item.get("status", "open")),
                    caller=str(item.get("caller", "")),
                    callee=str(item.get("callee", "")),
                    summary=str(item.get("summary", "")),
                    fixed_in=str(item.get("fixed_in", "")),
                    test_path=str(item.get("test_path", "")),
                )
            )
        except (KeyError, TypeError):
            continue
    return MismatchRegistry(entries=entries)


def _staged_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def check_mismatch_adjacency(
    repo_root: Path | None = None,
) -> tuple[bool, str]:
    """Refuse commits that touch a caller/callee in an open BLOCKER mismatch."""
    import os
    repo_root = repo_root or Path.cwd()
    if os.environ.get("DHARMA_SKIP_MISMATCH_GUARD", "").strip() == "1":
        return True, "mismatch adjacency skipped by DHARMA_SKIP_MISMATCH_GUARD=1"
    registry_path = repo_root / REGISTRY_REL_PATH
    if not registry_path.exists():
        return (
            False,
            f"MISMATCH REGISTRY MISSING: {REGISTRY_REL_PATH} does not exist.\n"
            "  Restore it from git, or recreate it from INTERFACE_MISMATCH_MAP.md, then run:\n"
            "    make mismatch-check\n"
            "  To skip: DHARMA_SKIP_MISMATCH_GUARD=1",
        )
    if yaml is None:
        return (
            False,
            "MISMATCH REGISTRY UNREADABLE: PyYAML not installed.\n"
            "  Install: pip install pyyaml",
        )
    registry = load_mismatch_registry(repo_root)
    if not registry.entries:
        return (
            False,
            f"MISMATCH REGISTRY EMPTY: {REGISTRY_REL_PATH} has no entries.\n"
            "  Populate it from INTERFACE_MISMATCH_MAP.md, then run:\n"
            "    make mismatch-check",
        )

    staged = _staged_files(repo_root)
    if not staged:
        return True, "no staged files"

    hits = registry.matching_paths(staged)
    open_hits = [m for m in hits if m.is_open and m.severity.upper() == "BLOCKER"]

    if not open_hits:
        if hits:
            ids = ", ".join(sorted({m.id for m in hits}))
            return True, f"touches mismatch entries (none open BLOCKER): {ids}"
        return True, "no mismatch adjacency"

    lines = [
        "MISMATCH ADJACENCY GUARD blocked the commit.",
        "  Staged files touch caller/callee of open BLOCKER mismatches:",
    ]
    for m in open_hits:
        lines.append(f"    {m.id} ({m.severity}): {m.caller}  →  {m.callee}")
        lines.append(f"      {m.summary}")
        if m.test_path:
            lines.append(f"      Pinned test: {m.test_path}")
    lines.append(
        "  Either resolve the mismatch (mark status=resolved + ensure pinned test passes),"
    )
    lines.append("    or split this commit so the mismatch caller/callee aren't touched.")
    return False, "\n".join(lines)
