"""Hot-path acknowledgment guard.

Edits to runtime-critical files require an explicit acknowledgment env var
or commit-message tag stating that gitnexus_impact / blast-radius was checked.
The intent is to make CLAUDE.md's "Architect's Gate" enforced rather than
cultural — a sand-trap that forces the operator to pause on hot paths.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

# Files whose every edit triggers the hot-path requirement. Derived from
# INTERFACE_MISMATCH_MAP authorship + CLAUDE.md's wiki + GitNexus discipline.
HOTPATH_FILES: frozenset[str] = frozenset({
    # Runtime core
    "dharma_swarm/swarm.py",
    "dharma_swarm/orchestrate_live.py",
    "dharma_swarm/orchestrator.py",
    "dharma_swarm/agent_runner.py",
    "dharma_swarm/persistent_agent.py",
    "dharma_swarm/providers.py",
    "dharma_swarm/frontier_council.py",
    "dharma_swarm/dgc_cli.py",
    # Governance / kernel
    "dharma_swarm/dharma_kernel.py",
    "dharma_swarm/telos_gates.py",
    "dharma_swarm/evolution.py",
    # Organism architecture (RED-TEAM ADD: CLAUDE.md names these as core abstractions
    # but they were missing from the pre-v1 list; adversarial agent could edit
    # organism.py / cascade.py without any ack)
    "dharma_swarm/organism.py",
    "dharma_swarm/cascade.py",
    "dharma_swarm/strange_loop.py",
    "dharma_swarm/stigmergy.py",
    "dharma_swarm/catalytic_graph.py",
    "dharma_swarm/vsm_channels.py",
    # archive.py owns the live MAP-Elites grid (diversity_archive.py retired to
    # a shim 2026-07-02, organism-rewire D6a).
    "dharma_swarm/archive.py",
})

ACK_TAG = "[impact-checked]"
ACK_ENV = "DHARMA_UPLIFT_ACK"
ACK_ENV_VALUE = "impact-checked"


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


def _read_commit_message(repo_root: Path, msg_file: str | None) -> str:
    if msg_file:
        return Path(msg_file).read_text(errors="replace")
    candidate = repo_root / ".git" / "COMMIT_EDITMSG"
    if candidate.exists():
        return candidate.read_text(errors="replace")
    return ""


def check_hotpath_acknowledged(
    repo_root: Path | None = None,
    *,
    commit_msg_file: str | None = None,
) -> tuple[bool, str]:
    """Refuse hot-path edits without explicit impact-checked acknowledgment."""
    repo_root = repo_root or Path.cwd()
    staged = _staged_files(repo_root)
    touched = sorted(set(staged) & HOTPATH_FILES)

    if not touched:
        return True, "no hot-path files staged"

    commit_msg = _read_commit_message(repo_root, commit_msg_file)
    if ACK_TAG in commit_msg:
        return True, f"hot-path edit acknowledged via tag: {touched}"

    if os.environ.get(ACK_ENV, "").strip().lower() == ACK_ENV_VALUE.lower():
        return True, f"hot-path edit acknowledged via env: {touched}"

    return False, (
        "HOT-PATH ACK GUARD blocked the commit.\n"
        f"  Hot-path files staged: {touched}\n"
        f"  Required: include '{ACK_TAG}' in the commit message,\n"
        f"    or set {ACK_ENV}={ACK_ENV_VALUE}.\n"
        "  Before acknowledging, run gitnexus_impact on each modified symbol\n"
        "    (CLAUDE.md mandates this — Architect's Gate)."
    )
