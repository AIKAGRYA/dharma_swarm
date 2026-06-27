#!/usr/bin/env python3
"""Spec §4.2 / §9.1 deterministic Scoper.

Maps a git diff (``base_ref..head_ref``) to a changed surface and selects the
relevant audit prompts. The selection is fully deterministic: the same diff
always yields an identical ``scope.json``.

Selection rules:
  1. The sentinel set (TV-01, TV-08, APS-01, APS-02, RDR-10, GEF-02 per §9.1)
     is always added to the candidate set, regardless of the diff.
  2. Changed files are mapped to relevant prompts via a file-to-prompt mapping
     table. The matched prompts form the diff-mapped set, capped at
     ``diff_mapped_cap`` (default 5). Sentinels are additional to the cap.
  3. Every selected prompt is filtered by ``warrant.scope.councils[]`` — no
     prompt whose council is outside the warrant's council scope is selected.
  4. An empty diff selects only the sentinels (0 diff-mapped) and exits 0.

Output (``scope.json``):
  - ``sentinel_prompt_ids``: the 6 sentinel ids
  - ``diff_mapped_prompt_ids``: the capped diff-mapped ids (pre-filter)
  - ``selected_prompt_ids``: sentinels + diff-mapped, after council filter
  - ``council_paths``: prompt_id -> ported PROMPTS.md path
  - ``changed_files``: the diff file list
  - ``rationale``: per changed file, the prompt_ids it mapped to
  - ``warrant_councils`` + ``diff_mapped_cap`` for replay

Usage:
    python3 scripts/governance/loop/scoper.py --warrant <warrant.yaml> --output <scope.json> \\
        [--changed-files f1 f2 ...] [--repo-root <path>] [--diff-mapped-cap N]

When ``--changed-files`` is omitted (or empty), the scoper computes the diff
from git via ``git diff --name-only base_ref..head_ref`` inside ``--repo-root``.
Passing ``--changed-files`` explicitly makes the selection testable without a
live git ref pair.

Exit codes:
    0   scope.json written successfully
    2   warrant invalid / unreadable / hard error
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

from scripts.governance.loop.councils import resolve_prompt_path
from scripts.governance.loop.warrant import Warrant, WarrantValidationError

# --- sentinel set (spec §9.1) ---
SENTINEL_PROMPT_IDS: tuple[str, ...] = (
    "TV-01",
    "TV-08",
    "APS-01",
    "APS-02",
    "RDR-10",
    "GEF-02",
)

# prompt_id prefix -> council_id (matches the ported councils/ layout).
PROMPT_PREFIX_TO_COUNCIL: dict[str, str] = {
    "TV": "testing_verification",
    "AC": "architecture_complexity",
    "RDR": "runtime_distributed_reliability",
    "APS": "ai_slop_prompt_security",
    "GEF": "governance_evidence_fitness",
}

DEFAULT_DIFF_MAPPED_CAP = 5

# File-to-prompt mapping table. Each entry is (glob_pattern, [prompt_ids]).
# A changed file matches if it matches the glob (fnmatch over the relative
# path, with "**" treated as a multi-segment wildcard). Matched prompts are
# collected, deduped, sorted, and capped. Order does not affect the final
# selected set (sorting + cap is deterministic).
FILE_TO_PROMPTS: list[tuple[str, list[str]]] = [
    ("tests/**", ["TV-01", "TV-02", "TV-06", "TV-07"]),
    ("dharma_swarm/spine/**", ["TV-08", "RDR-01", "RDR-04"]),
    ("dharma_swarm/providers.py", ["RDR-06", "APS-09"]),
    ("dharma_swarm/provider_*.py", ["RDR-06"]),
    ("dharma_swarm/a2a/**", ["RDR-03", "APS-03"]),
    ("dharma_swarm/runtime_state.py", ["RDR-04"]),
    ("dharma_swarm/orchestrator.py", ["RDR-09", "AC-08"]),
    ("dharma_swarm/agent_runner.py", ["RDR-09", "AC-08"]),
    ("dharma_swarm/evolution.py", ["AC-07", "GEF-01"]),
    ("dharma_swarm/diversity_archive.py", ["GEF-01", "AC-07"]),
    ("dharma_swarm/memory_kernel/**", ["AC-09"]),
    ("dharma_swarm/council/**", ["AC-06"]),
    ("dharma_swarm/telos_gates.py", ["GEF-09"]),
    ("scripts/governance/hygiene/**", ["GEF-02", "GEF-08"]),
    ("scripts/governance/**", ["GEF-02"]),
    (".github/workflows/**", ["GEF-07", "GEF-02"]),
    ("docs/governance/**", ["GEF-06", "GEF-10"]),
    ("dharma_swarm/stigmergy.py", ["AC-09"]),
    ("dharma_swarm/handoff.py", ["AC-05"]),
    ("dharma_swarm/vsm_channels.py", ["AC-04"]),
    ("pyproject.toml", ["AC-10", "TV-09"]),
    ("dharma_swarm/**/*.py", ["AC-01", "AC-03"]),
]


def prompt_to_council(prompt_id: str) -> str | None:
    """Return the council_id for a prompt_id, or None if the prefix is unknown."""
    for prefix, council in PROMPT_PREFIX_TO_COUNCIL.items():
        if prompt_id.startswith(prefix + "-"):
            return council
    return None


def _match_glob(pattern: str, path: str) -> bool:
    """Match a path against a glob pattern using the stdlib ``fnmatch`` engine.

    ``fnmatch`` treats ``*`` as matching any run of characters (including path
    separators) and ``**`` identically, so ``tests/**`` matches
    ``tests/foo/bar.py`` and ``dharma_swarm/spine/**`` matches
    ``dharma_swarm/spine/routing.py``. Literal patterns (e.g.
    ``dharma_swarm/providers.py``) match exactly.

    ``fnmatchcase`` is used (not ``fnmatch``) for platform-independent,
    case-sensitive matching — deterministic across macOS/Linux.
    """
    return fnmatch.fnmatchcase(path, pattern)


def map_file_to_prompts(path: str) -> list[str]:
    """Return the sorted, deduped prompt_ids a changed file maps to."""
    matched: set[str] = set()
    for pattern, prompt_ids in FILE_TO_PROMPTS:
        if _match_glob(pattern, path):
            matched.update(prompt_ids)
    return sorted(matched)


def changed_files_from_git(base_ref: str, head_ref: str, repo_root: Path) -> list[str]:
    """Compute ``git diff --name-only base_ref..head_ref`` inside repo_root."""
    res = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}..{head_ref}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"git diff --name-only {base_ref}..{head_ref} failed (exit {res.returncode}): {res.stderr.strip()}"
        )
    return [line for line in res.stdout.splitlines() if line.strip()]


def select_prompts(
    changed_files: list[str],
    warrant_councils: list[str],
    diff_mapped_cap: int = DEFAULT_DIFF_MAPPED_CAP,
    repo_root: Path | None = None,
) -> dict:
    """Deterministically select prompts for a diff.

    Returns the scope.json dict (serializable). The selection is a pure
    function of (changed_files, warrant_councils, diff_mapped_cap) — no I/O
    other than optional council-path resolution against ``repo_root``.
    """
    root = repo_root or Path(__file__).resolve().parents[3]
    allowed = set(warrant_councils)

    # 1. sentinels (diff-independent candidates)
    sentinel_set = list(SENTINEL_PROMPT_IDS)

    # 2. diff-mapped prompts + per-file rationale (sorted by file for determinism)
    rationale: list[dict] = []
    matched: set[str] = set()
    for f in changed_files:
        pids = map_file_to_prompts(f)
        rationale.append({"file": f, "prompt_ids": pids})
        matched.update(pids)
    rationale.sort(key=lambda e: e["file"])

    diff_mapped_all = sorted(matched)
    diff_mapped_capped = diff_mapped_all[:diff_mapped_cap]

    # 3. council filter: drop any candidate whose council is not in warrant scope
    def _in_scope(pid: str) -> bool:
        council = prompt_to_council(pid)
        return council is not None and council in allowed

    sentinel_in_scope = [pid for pid in sentinel_set if _in_scope(pid)]
    diff_mapped_in_scope = [pid for pid in diff_mapped_capped if _in_scope(pid)]

    # selected = sentinels + diff-mapped, deduped, sorted (deterministic order)
    selected = sorted(set(sentinel_in_scope) | set(diff_mapped_in_scope))

    # 4. council paths for every selected prompt
    council_paths: dict[str, str] = {}
    for pid in selected:
        council = prompt_to_council(pid)
        if council is None:
            continue
        p = resolve_prompt_path(council, pid, repo_root=root)
        if p is not None:
            council_paths[pid] = str(p.relative_to(root)) if p.is_relative_to(root) else str(p)

    return {
        "sentinel_prompt_ids": sentinel_set,
        "diff_mapped_prompt_ids": diff_mapped_capped,
        "selected_prompt_ids": selected,
        "council_paths": council_paths,
        "changed_files": sorted(changed_files),
        "rationale": rationale,
        "warrant_councils": sorted(allowed),
        "diff_mapped_cap": diff_mapped_cap,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _emit_error(message: str) -> int:
    sys.stderr.write(message + "\n")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic git-diff to changed-surface to selected prompts (spec §9.1).",
    )
    parser.add_argument("--warrant", required=True, help="path to the warrant YAML file")
    parser.add_argument("--output", required=True, help="path to write scope.json")
    parser.add_argument(
        "--changed-files",
        nargs="*",
        default=None,
        help="explicit changed-file list (skips git diff); omit to compute from git",
    )
    parser.add_argument("--repo-root", default=None, help="repo root for git diff (default: worktree root)")
    parser.add_argument(
        "--diff-mapped-cap",
        type=int,
        default=DEFAULT_DIFF_MAPPED_CAP,
        help=f"cap on diff-mapped prompts (default {DEFAULT_DIFF_MAPPED_CAP}; sentinels additional)",
    )

    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root) if args.repo_root else Path(__file__).resolve().parents[3]

    # Load + validate the warrant (re-uses the warrant module).
    try:
        warrant = Warrant.from_yaml(Path(args.warrant))
    except WarrantValidationError as exc:
        return _emit_error(f"warrant validation failed: {exc}")

    scope_dict = warrant.scope
    base_ref = scope_dict.get("base_ref")
    head_ref = scope_dict.get("head_ref")
    councils = scope_dict.get("councils", [])
    if not isinstance(councils, list):
        return _emit_error("warrant.scope.councils must be a list")

    # Determine changed files: explicit list takes precedence; else git diff.
    if args.changed_files is None:
        if not base_ref or not head_ref:
            return _emit_error(
                "warrant.scope.base_ref/head_ref required when --changed-files is omitted"
            )
        try:
            changed_files = changed_files_from_git(base_ref, head_ref, repo_root)
        except RuntimeError as exc:
            return _emit_error(str(exc))
    else:
        changed_files = list(args.changed_files)

    scope = select_prompts(
        changed_files=changed_files,
        warrant_councils=councils,
        diff_mapped_cap=args.diff_mapped_cap,
        repo_root=repo_root,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scope, indent=2, sort_keys=True) + "\n")

    sys.stdout.write(
        f"scope: {len(scope['selected_prompt_ids'])} prompts "
        f"({len(scope['diff_mapped_prompt_ids'])} diff-mapped + "
        f"{len([p for p in scope['sentinel_prompt_ids'] if p in scope['selected_prompt_ids']])} sentinels) "
        f"-> {out_path}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
