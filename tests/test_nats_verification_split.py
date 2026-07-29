"""Executable contract for hermetic versus live-host NATS verification."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET_HEADER = re.compile(r"^([^#\s][^:]*)\s*:(.*)$")
LIVE_SCRIPTS = {
    "scripts/governance/check_nats_live_production_evidence.py",
    "scripts/governance/run_nats_live_production_matrix.py",
}


def _make_database() -> dict[str, tuple[set[str], str]]:
    completed = subprocess.run(
        ["make", "-qp", "governance-all"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    # GNU Make returns 1 under -q when a phony target would be rebuilt. Its
    # printed database is still the authoritative resolved dependency graph.
    assert completed.returncode in {0, 1}, completed.stderr
    targets: dict[str, tuple[set[str], str]] = {}
    for block in completed.stdout.split("\n\n"):
        lines = block.splitlines()
        if not lines:
            continue
        match = TARGET_HEADER.match(lines[0])
        if match is None or "%" in match.group(1):
            continue
        dependencies = {
            token
            for token in match.group(2).split()
            if token != "|" and not token.startswith("$")
        }
        recipe = "\n".join(line[1:] for line in lines if line.startswith("\t"))
        for target in match.group(1).split():
            targets[target] = (dependencies, recipe)
    return targets


def _reachable(targets: dict[str, tuple[set[str], str]], root: str) -> set[str]:
    seen: set[str] = set()
    pending = [root]
    while pending:
        target = pending.pop()
        if target in seen:
            continue
        seen.add(target)
        pending.extend(targets.get(target, (set(), ""))[0] - seen)
    return seen


def test_governance_all_resolves_only_the_hermetic_nats_lane() -> None:
    targets = _make_database()
    reachable = _reachable(targets, "governance-all")

    assert "nats-substrate-contract" in reachable
    assert "nats-live-production-matrix" not in reachable
    reachable_recipes = "\n".join(targets.get(target, (set(), ""))[1] for target in reachable)
    for script in LIVE_SCRIPTS:
        assert script not in reachable_recipes


def test_live_matrix_is_an_explicit_host_typed_lane() -> None:
    targets = _make_database()
    recipe = targets["nats-live-production-matrix"][1]

    assert "scripts/governance/run_nats_live_production_matrix.py" in recipe
    assert "--host-mode" in recipe
    assert "DHARMA_NATS_HOST_MODE" in recipe
