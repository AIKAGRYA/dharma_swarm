"""grimp adapter — Python circular-dependency / SCC detection.

Uses grimp (https://grimp.readthedocs.io) to build the import graph
and Tarjan's SCC to find non-trivial strongly-connected components.
Each SCC = one circular dependency cycle.

Findings emitted in STRUCTURE family. Confidence calibrated by
cycle size: bigger cycles = harder to break = higher confidence
they're real architectural debt vs incidental.

Validates SOVEREIGN_MANIFEST §A7's claim of 9 cycles in dharma_swarm.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from dharma_swarm.slop.adapters.base import empty_result, normalize_path
from dharma_swarm.slop.models import (
    DetectorFamily,
    DetectorResult,
    Finding,
    Severity,
)

TOOL = "grimp"
FAMILY = DetectorFamily.STRUCTURE


def _detect_python_packages(paths: list[Path], repo_root: Path) -> list[str]:
    """Return distinct top-level Python package names rooted at repo_root."""
    pkgs: set[str] = set()
    for p in paths:
        if not p.suffix == ".py":
            continue
        try:
            rel = p.resolve().relative_to(repo_root.resolve())
        except ValueError:
            continue
        parts = rel.parts
        if not parts:
            continue
        first = parts[0]
        if (repo_root / first / "__init__.py").is_file():
            pkgs.add(first)
    return sorted(pkgs)


def _tarjan_scc(adj: dict[str, set[str]]) -> list[list[str]]:
    """Tarjan's SCC; returns only non-trivial (size >= 2) components."""
    index_counter = [0]
    stack: list[str] = []
    lowlinks: dict[str, int] = {}
    index: dict[str, int] = {}
    on_stack: dict[str, bool] = defaultdict(bool)
    sccs: list[list[str]] = []

    def strongconnect(node: str) -> None:
        index[node] = index_counter[0]
        lowlinks[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack[node] = True
        for successor in adj.get(node, ()):
            if successor not in index:
                strongconnect(successor)
                lowlinks[node] = min(lowlinks[node], lowlinks[successor])
            elif on_stack[successor]:
                lowlinks[node] = min(lowlinks[node], index[successor])
        if lowlinks[node] == index[node]:
            component: list[str] = []
            while True:
                successor = stack.pop()
                on_stack[successor] = False
                component.append(successor)
                if successor == node:
                    break
            if len(component) > 1:
                sccs.append(component)

    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
    for node in list(adj.keys()):
        if node not in index:
            strongconnect(node)
    return sccs


def _severity_for(scc_size: int) -> Severity:
    if scc_size >= 5:
        return Severity.HIGH
    if scc_size >= 3:
        return Severity.MEDIUM
    return Severity.LOW


def _confidence_for(scc_size: int) -> float:
    return min(0.92, 0.55 + 0.08 * scc_size)


def _module_to_path(module: str, repo_root: Path) -> str:
    rel = Path(*module.split(".")).with_suffix(".py")
    if (repo_root / rel).is_file():
        return str(rel)
    init_rel = Path(*module.split(".")) / "__init__.py"
    if (repo_root / init_rel).is_file():
        return str(init_rel)
    return str(rel)


def run_grimp(
    paths: Iterable[Path],
    *,
    repo_root: Path | None = None,
    timeout: float = 60.0,
) -> DetectorResult:
    repo_root = repo_root or Path.cwd()
    paths_list = list(paths)
    if not paths_list:
        return empty_result(TOOL, FAMILY, "no paths supplied")
    packages = _detect_python_packages(paths_list, repo_root)
    if not packages:
        return empty_result(TOOL, FAMILY, "no Python package roots found in scope")

    try:
        import grimp
    except ImportError:
        return empty_result(TOOL, FAMILY, "grimp not installed (pip install grimp)")

    import time
    start = time.perf_counter()
    all_findings: list[Finding] = []
    last_error: str | None = None

    for package in packages:
        try:
            graph = grimp.build_graph(package, include_external_packages=False)
        except Exception as exc:
            last_error = f"grimp.build_graph({package!r}) failed: {exc}"
            continue
        adj: dict[str, set[str]] = {
            m: set(graph.find_modules_directly_imported_by(m)) for m in graph.modules
        }
        sccs = _tarjan_scc(adj)
        for scc in sccs:
            members = sorted(scc)
            evidence_summary = ", ".join(
                m.removeprefix(f"{package}.") for m in members
            )
            severity = _severity_for(len(members))
            confidence = _confidence_for(len(members))
            for module in members:
                all_findings.append(
                    Finding(
                        tool=TOOL,
                        family=FAMILY,
                        issue_type="circular_dependency",
                        path=_module_to_path(module, repo_root),
                        line=None,
                        symbol=module,
                        severity=severity,
                        confidence=confidence,
                        evidence=f"SCC ({len(members)} modules): {evidence_summary}",
                        suggested_action=(
                            "Extract shared logic into a neutral module; do NOT introduce "
                            "new abstractions just to break the cycle (per SUBAGENT 4 discipline)"
                        ),
                    )
                )

    duration = time.perf_counter() - start
    if duration > timeout:
        last_error = (last_error or "") + f"; exceeded soft timeout {timeout}s"
    return DetectorResult(
        tool=TOOL,
        family=FAMILY,
        findings=all_findings,
        duration_sec=duration,
        exit_code=0,
        error=last_error,
    )


__all__ = ["FAMILY", "TOOL", "run_grimp"]
