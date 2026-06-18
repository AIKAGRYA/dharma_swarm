#!/usr/bin/env python3
"""Counter definitions for the one-way quality ratchet (see ratchet.py).

This module owns WHAT the ratchet measures; ratchet.py owns the algebra
(compare, tighten) and persistence. Each counter returns a Reading: one
non-negative integer plus the evidence lines behind it, so the gate can
always show its work (``ratchet.py --explain NAME``).

Measurement failure is never a number: a counter that cannot measure
(missing owner file, unparseable source, missing tool) raises
BrokenCounter, and the engine turns that into a blocking exit — silence
here would let regressions through unmeasured.

Stdlib-only on purpose: governance gates must run before, and regardless
of, virtualenv state — the rule this directory already follows. The one
exception is the ruff counter, which shells out to the repo's pinned ruff
binary and is BROKEN when that binary is absent.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable

_GOVERNANCE_DIR = Path(__file__).resolve().parents[1]
if str(_GOVERNANCE_DIR) not in sys.path:
    sys.path.insert(0, str(_GOVERNANCE_DIR))

import assurance_boundary  # noqa: E402  (sibling governance module)

_SKIP_DIR_NAMES = {".git", ".venv", "node_modules", "__pycache__"}


class Direction(StrEnum):
    """Which way a counter is allowed to move."""

    DOWN = "down"  # value may only fall (debt counters)
    UP = "up"  # value may only rise (asset counters)


class BrokenCounter(RuntimeError):
    """A counter could not produce a trustworthy number."""


@dataclass(frozen=True, slots=True)
class Reading:
    """One measured value plus the human-readable evidence behind it.

    ``evidence`` is one line per contributing item; it is for --explain
    output only and never part of the pass/fail decision.
    """

    value: int
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Counter:
    """A named repo-wide quantity with a permitted direction of travel."""

    name: str
    direction: Direction
    end_target: int
    definition: str
    measure: Callable[[Path], Reading]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _python_files(root: Path) -> list[Path]:
    """Every .py file under ``root``, skipping vendored/derived trees."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIR_NAMES)
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                found.append(Path(dirpath) / filename)
    return found


def _line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def _parse_or_broken(path: Path, repo_root: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        raise BrokenCounter(f"cannot parse {path.relative_to(repo_root)}: {exc}") from exc


def _rel(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


# ---------------------------------------------------------------------------
# Measurements
# ---------------------------------------------------------------------------


def measure_ruff_undefined_or_redefined(repo_root: Path) -> Reading:
    ruff = repo_root / ".venv" / "bin" / "ruff"
    ruff_cmd = str(ruff) if ruff.exists() else shutil.which("ruff")
    if ruff_cmd is None:
        raise BrokenCounter("ruff binary not found (.venv/bin/ruff or PATH)")
    targets = [d for d in ("dharma_swarm", "api", "scripts", "tests") if (repo_root / d).is_dir()]
    try:
        result = subprocess.run(
            # --ignore-noqa: a `# noqa` comment must not be able to hide a
            # new undefined name from the ratchet — suppression is a review
            # conversation, not a counter bypass.
            [
                ruff_cmd, "check", "--select", "F821,F811", "--ignore-noqa",
                "--output-format", "json", *targets,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise BrokenCounter(f"ruff did not produce a result: {exc}") from exc
    # ruff exits 0 (clean) or 1 (findings); anything else is a tool failure.
    if result.returncode not in (0, 1):
        raise BrokenCounter(f"ruff failed (exit {result.returncode}): {result.stderr.strip()[:200]}")
    try:
        findings = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise BrokenCounter(f"ruff emitted unparseable JSON: {exc}") from exc
    evidence = tuple(
        f"{Path(f['filename']).resolve().relative_to(repo_root).as_posix()}:"
        f"{f['location']['row']} {f['code']} {f['message']}"
        for f in findings
    )
    return Reading(value=len(findings), evidence=evidence)


def measure_modules_over_500_lines(repo_root: Path) -> Reading:
    over: list[tuple[int, str]] = []
    for path in _python_files(repo_root / "dharma_swarm"):
        lines = _line_count(path)
        if lines > 500:
            over.append((lines, _rel(path, repo_root)))
    over.sort(reverse=True)
    return Reading(value=len(over), evidence=tuple(f"{lines:5d} {rel}" for lines, rel in over))


def measure_largest_module_lines(repo_root: Path) -> Reading:
    largest, largest_rel = 0, "<none>"
    for path in _python_files(repo_root / "dharma_swarm"):
        lines = _line_count(path)
        if lines > largest:
            largest, largest_rel = lines, _rel(path, repo_root)
    return Reading(value=largest, evidence=(f"{largest:5d} {largest_rel}",))


_SWALLOWABLE = {"Exception", "BaseException"}


def _handler_swallows(handler: ast.ExceptHandler) -> bool:
    """True for ``except [Exception/BaseException/bare]: pass`` exactly."""
    if not (len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass)):
        return False
    kind = handler.type
    if kind is None:
        return True
    if isinstance(kind, ast.Name):
        return kind.id in _SWALLOWABLE
    if isinstance(kind, ast.Tuple):
        return any(isinstance(e, ast.Name) and e.id in _SWALLOWABLE for e in kind.elts)
    return False


def measure_silent_exception_swallows(repo_root: Path) -> Reading:
    evidence: list[str] = []
    for sub in ("dharma_swarm", "scripts"):
        for path in _python_files(repo_root / sub):
            tree = _parse_or_broken(path, repo_root)
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and _handler_swallows(node):
                    evidence.append(f"{_rel(path, repo_root)}:{node.lineno}")
    return Reading(value=len(evidence), evidence=tuple(sorted(evidence)))


def measure_spine_bypass_entries(repo_root: Path) -> Reading:
    owner = repo_root / "scripts" / "governance" / "spine_bypass_report.py"
    if not owner.exists():
        raise BrokenCounter(f"owner file missing: {_rel(owner, repo_root)}")
    tree = _parse_or_broken(owner, repo_root)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {t.id for t in targets if isinstance(t, ast.Name)}
            if "_INTENTIONAL_BYPASS" in names and isinstance(node.value, ast.Dict):
                keys = node.value.keys
                evidence = tuple(
                    ast.unparse(key) if key is not None else "**unpacked**" for key in keys
                )
                return Reading(value=len(keys), evidence=evidence)
    raise BrokenCounter("_INTENTIONAL_BYPASS dict literal not found in spine_bypass_report.py")


def measure_property_test_files(repo_root: Path) -> Reading:
    directory = repo_root / "tests" / "properties"
    if not directory.is_dir():
        raise BrokenCounter("tests/properties directory missing")
    files = sorted(directory.glob("test_*.py"))
    return Reading(value=len(files), evidence=tuple(_rel(p, repo_root) for p in files))


def _boundary_report(repo_root: Path) -> "assurance_boundary.BoundaryReport":
    try:
        return assurance_boundary.run_boundary(repo_root)
    except assurance_boundary.BrokenBoundary as exc:
        raise BrokenCounter(str(exc)) from exc


def _boundary_measured(repo_root: Path, contract: str) -> Reading:
    violations = _boundary_report(repo_root).measured[contract]
    return Reading(value=len(violations), evidence=tuple(v.render() for v in violations))


def measure_boundary_unfrozen_records(repo_root: Path) -> Reading:
    return _boundary_measured(repo_root, "AB-01")


def measure_boundary_unwitnessed_swallows(repo_root: Path) -> Reading:
    return _boundary_measured(repo_root, "AB-02")


def measure_boundary_unsupervised_spawns(repo_root: Path) -> Reading:
    return _boundary_measured(repo_root, "AB-03")


def measure_boundary_contract_violations(repo_root: Path) -> Reading:
    violations = _boundary_report(repo_root).hold_at_zero
    return Reading(value=len(violations), evidence=tuple(v.render() for v in violations))


def measure_hygiene_patterns_enforced_or_resolved(repo_root: Path) -> Reading:
    directory = repo_root / "docs" / "governance" / "hygiene" / "patterns"
    if not directory.is_dir():
        raise BrokenCounter("docs/governance/hygiene/patterns directory missing")
    evidence: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            pattern = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BrokenCounter(f"unparseable pattern {_rel(path, repo_root)}: {exc}") from exc
        stage = pattern.get("stage")
        if stage in ("enforced", "resolved"):
            evidence.append(f"{pattern.get('id', path.stem)} ({stage})")
    return Reading(value=len(evidence), evidence=tuple(evidence))


COUNTERS: tuple[Counter, ...] = (
    Counter(
        name="ruff_undefined_or_redefined",
        direction=Direction.DOWN,
        end_target=0,
        definition=(
            "ruff F821 (undefined name) + F811 (redefinition) findings across "
            "dharma_swarm, api, scripts, tests — names that do not bind are "
            "code that has never been run."
        ),
        measure=measure_ruff_undefined_or_redefined,
    ),
    Counter(
        name="modules_over_500_lines",
        direction=Direction.DOWN,
        end_target=0,
        definition=(
            "Python modules under dharma_swarm/ exceeding the repo's 500-line "
            "budget (CLAUDE.md law; SOVEREIGN_MANIFEST axiom A5: no god objects)."
        ),
        measure=measure_modules_over_500_lines,
    ),
    Counter(
        name="largest_module_lines",
        direction=Direction.DOWN,
        end_target=500,
        definition=(
            "Line count of the single largest module under dharma_swarm/ — "
            "the god-object high-water mark must never rise."
        ),
        measure=measure_largest_module_lines,
    ),
    Counter(
        name="silent_exception_swallows",
        direction=Direction.DOWN,
        end_target=0,
        definition=(
            "`except [Exception|bare]: pass` sites in dharma_swarm/ and scripts/ "
            "— errors silenced without witness (ahimsa: no silent harm)."
        ),
        measure=measure_silent_exception_swallows,
    ),
    Counter(
        name="spine_bypass_entries",
        direction=Direction.DOWN,
        end_target=0,
        definition=(
            "Entries in _INTENTIONAL_BYPASS in scripts/governance/"
            "spine_bypass_report.py — dispatch paths that dodge invoke_agent(). "
            "Draining them is spine-adoption track work; this counter only "
            "forbids growth."
        ),
        measure=measure_spine_bypass_entries,
    ),
    Counter(
        name="property_test_files",
        direction=Direction.UP,
        end_target=20,
        definition=(
            "Property-based test files under tests/properties/ — generated "
            "invariants, the strongest test form the repo has."
        ),
        measure=measure_property_test_files,
    ),
    Counter(
        name="hygiene_patterns_enforced_or_resolved",
        direction=Direction.UP,
        end_target=70,
        definition=(
            "Hygiene patterns at stage enforced or resolved — the lifecycle's "
            "forward motion. Promotions may not be silently undone."
        ),
        measure=measure_hygiene_patterns_enforced_or_resolved,
    ),
    # -- assurance boundary (scripts/governance/assurance_boundary.py) ----
    # Contract violations measured inside the V0 boundary (spine,
    # memory_kernel, a2a, runtime_state, runtime_provider). The boundary
    # gate states the contracts; the ratchet banks the drain.
    Counter(
        name="boundary_unfrozen_records",
        direction=Direction.DOWN,
        end_target=0,
        definition=(
            "AB-01: boundary record/receipt dataclasses that are not frozen "
            "or lack schema_version — provenance must be structured data."
        ),
        measure=measure_boundary_unfrozen_records,
    ),
    Counter(
        name="boundary_unwitnessed_swallows",
        direction=Direction.DOWN,
        end_target=0,
        definition=(
            "AB-02: broad except handlers inside the boundary that continue "
            "without re-raise, escalation, or a witness call (the 92% rule)."
        ),
        measure=measure_boundary_unwitnessed_swallows,
    ),
    Counter(
        name="boundary_unsupervised_spawns",
        direction=Direction.DOWN,
        end_target=0,
        definition=(
            "AB-03: fire-and-forget asyncio task spawns inside the boundary — "
            "a discarded Task handle makes failure unobservable. At zero; "
            "must stay there."
        ),
        measure=measure_boundary_unsupervised_spawns,
    ),
    Counter(
        name="boundary_contract_violations",
        direction=Direction.DOWN,
        end_target=0,
        definition=(
            "AB-04 + AB-05 hold-at-zero contract violations: direct provider "
            "imports outside the canonical door, and correlation-spine layers "
            "whose declared receipt class does not resolve. Known debt: the "
            "request_response layer's A2ATaskReceipt is declared but defined "
            "nowhere (reconciliation-track drain)."
        ),
        measure=measure_boundary_contract_violations,
    ),
)
