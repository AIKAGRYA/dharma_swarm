"""Module metabolism report — warn-only repo-integrity evidence for PTR.

Emits a JSON artifact and optional text summary describing per-module
capsule health. Feeds PTR as ``repo_integrity`` evidence only. Does NOT
block commits, modify pre-commit hooks, change the Makefile, or expand
Rule 10.

Reference: docs/governance/MODULE_METABOLISM_STRATEGY.md §10

Usage:
    python3 scripts/governance/module_metabolism_report.py
    python3 scripts/governance/module_metabolism_report.py --json-out report.json
    python3 scripts/governance/module_metabolism_report.py --text-out report.txt
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent / "dharma_swarm"

# Target taxonomy from MODULE_METABOLISM_STRATEGY.md §7
PACKAGE_FAMILIES: dict[str, list[str]] = {
    "core": [
        "models", "config", "identity", "base_provider", "signal_bus",
        "handoff", "contracts",
    ],
    "governance": [
        "dharma_kernel", "telos_gate", "policy_compiler", "shakti",
        "ptr", "ptr_loop", "dharma_attractor", "telos",
        "decision", "certified_lanes", "dharma",
    ],
    "runtime": [
        "runtime_state", "task_board", "artifact_store", "session_store",
        "runtime", "cron", "overnight", "sandbox", "docker_sandbox",
    ],
    "operator_core": [
        "operator_brief", "operator_core", "operator", "permissions",
    ],
    "surfaces": [
        "dgc_cli", "tui", "terminal", "api", "splash",
        "a2a", "conversation",
    ],
    "providers": [
        "providers", "provider_policy", "runtime_provider",
        "smart_router", "swarm_router", "router_v1",
        "model", "claude", "codex",
    ],
    "orchestration": [
        "swarm", "orchestrator", "orchestrate_live", "agent_runner",
        "dispatch", "task_execution", "persistent_agent", "conductors",
        "auto", "roaming", "agent", "workflow", "mission",
        "task", "sleep", "adaptive",
    ],
    "knowledge": [
        "context", "memory", "retrieval", "semantic", "palace",
        "organism_memory", "organism", "concept", "scout",
        "knowledge", "skill", "world", "review",
    ],
    "ontology": [
        "ontology", "ontology_hub", "ontology_registry", "telic_seam",
        "chetana", "provenance", "lineage", "correlation",
    ],
    "evolution": [
        "evolution", "meta_evolution", "jikoku", "dse_integration",
        "landscape", "darwin", "selector", "diversity_archive",
        "fitness", "experiment", "archive",
    ],
    "domains": [
        "ginko", "gaia", "cascade", "economic", "ecosystem",
        "subconscious", "self", "transcendence", "opportunity",
        "jk", "kaizen", "field", "graph", "quality",
    ],
    "assurance": [
        "xray", "scanner", "verify", "integrity", "capsule",
        "guardian", "consistency_guard", "bridge", "telemetry",
    ],
    "intelligence": [
        "thinkodynamic", "smart_seed", "coalgebra", "info_geometry",
        "build_engine", "foreman", "custodian",
    ],
}


# Subdirectory → family mapping for modules inside subpackages
_SUBDIR_FAMILIES: dict[str, str] = {
    "operator_core": "operator_core",
    "operator_brief": "operator_core",
    "assurance": "assurance",
    "auto_grade": "intelligence",
    "auto_research": "intelligence",
    "contracts": "core",
    "a2a": "surfaces",
    "terminal_adapters": "surfaces",
    "terminal_routing": "surfaces",
    "tui": "surfaces",
    "verify": "assurance",
}


def _family_for_module(module_name: str, rel_path: str = "") -> str:
    """Classify a module into its taxonomy family.

    Uses both the module stem and the relative path from dharma_swarm/.
    """
    stem = module_name.replace(".py", "")

    # Check subdirectory first
    if rel_path:
        parts = rel_path.replace("dharma_swarm/", "").split("/")
        if len(parts) > 1:
            subdir = parts[0]
            if subdir in _SUBDIR_FAMILIES:
                return _SUBDIR_FAMILIES[subdir]

    # Check prefix-based family
    for family, prefixes in PACKAGE_FAMILIES.items():
        for prefix in prefixes:
            if stem == prefix or stem.startswith(prefix + "_"):
                return family
    return "unclassified"


def _count_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except Exception:
        return 0


def _parse_module(path: Path) -> dict[str, Any]:
    """Extract static metrics from a single Python module."""
    source = path.read_text(encoding="utf-8", errors="replace")
    loc = len(source.splitlines())
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {
            "path": str(path.relative_to(PACKAGE_ROOT.parent)),
            "loc": loc,
            "parse_error": True,
        }

    classes = 0
    functions = 0
    public_api = 0
    imports_from_package: set[str] = set()
    has_type_checking_block = False
    write_surface_hits = 0

    # Detect write-surface patterns
    write_patterns = {
        "sqlite", "connect(", ".execute(", "open(", "write_text(",
        "write_bytes(", "jsonl", ".json", "Path(",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes += 1
            if not node.name.startswith("_"):
                public_api += 1
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            functions += 1
            if not node.name.startswith("_"):
                public_api += 1
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("dharma_swarm."):
                imported = node.module.split(".")[1]
                imports_from_package.add(imported)
        elif isinstance(node, ast.If):
            # Detect TYPE_CHECKING guard
            if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                has_type_checking_block = True

    # Rough write-surface detection
    source_lower = source.lower()
    for pattern in write_patterns:
        if pattern in source_lower:
            write_surface_hits += 1

    return {
        "path": str(path.relative_to(PACKAGE_ROOT.parent)),
        "loc": loc,
        "classes": classes,
        "functions": functions,
        "public_api": public_api,
        "imports_from_package": sorted(imports_from_package),
        "import_count_outbound": len(imports_from_package),
        "has_type_checking_block": has_type_checking_block,
        "write_surface_hits": write_surface_hits,
        "parse_error": False,
    }


def _build_import_graph(modules: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Build inbound import map: target -> set of importers."""
    inbound: dict[str, set[str]] = defaultdict(set)
    for mod in modules:
        stem = Path(mod["path"]).stem
        for dep in mod.get("imports_from_package", []):
            inbound[dep].add(stem)
    return dict(inbound)


def _detect_cycles(modules: list[dict[str, Any]]) -> list[list[str]]:
    """Detect import cycles using DFS."""
    graph: dict[str, set[str]] = defaultdict(set)
    all_stems = set()
    for mod in modules:
        stem = Path(mod["path"]).stem
        all_stems.add(stem)
        for dep in mod.get("imports_from_package", []):
            graph[stem].add(dep)

    cycles: list[list[str]] = []
    visited: set[str] = set()
    path: list[str] = []
    path_set: set[str] = set()

    def dfs(node: str) -> None:
        if node in path_set:
            idx = path.index(node)
            cycle = path[idx:] + [node]
            cycles.append(cycle)
            return
        if node in visited:
            return
        visited.add(node)
        path.append(node)
        path_set.add(node)
        for neighbor in sorted(graph.get(node, [])):
            if neighbor in all_stems:
                dfs(neighbor)
        path.pop()
        path_set.remove(node)

    for node in sorted(all_stems):
        dfs(node)

    # Deduplicate
    seen: set[tuple[str, ...]] = set()
    unique: list[list[str]] = []
    for c in cycles:
        key = tuple(sorted(c[:-1]))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def _find_test_references(module_stem: str, tests_dir: Path) -> int:
    """Count test files that reference this module."""
    if not tests_dir.exists():
        return 0
    count = 0
    for test_file in tests_dir.glob("test_*.py"):
        try:
            content = test_file.read_text(encoding="utf-8", errors="replace")
            if module_stem in content:
                count += 1
        except Exception:
            pass
    return count


def _suggest_action(mod: dict[str, Any], inbound_count: int, cycle_member: bool) -> str:
    """Suggest a metabolism action for a module."""
    loc = mod.get("loc", 0)
    if loc > 3000:
        return "split-review"
    if loc > 1000:
        return "split-review"
    if inbound_count == 0 and mod.get("test_references", 0) == 0:
        return "archive-review"
    if cycle_member:
        return "facade"
    if mod.get("write_surface_hits", 0) >= 4:
        return "merge-review"
    return "keep"


def _confidence_flags(mod: dict[str, Any], inbound_count: int) -> list[str]:
    """Generate confidence flags for the module."""
    flags = []
    if inbound_count == 0:
        flags.append("entrypoint_possible")
    if mod.get("test_references", 0) == 0:
        flags.append("test_signal_missing")
    if mod.get("write_surface_hits", 0) >= 3:
        flags.append("write_surface")
    if inbound_count >= 10:
        flags.append("core_hub")
    return flags


def generate_report(package_root: Path | None = None) -> dict[str, Any]:
    """Generate the full metabolism report as a dict."""
    root = package_root or PACKAGE_ROOT
    tests_dir = root.parent / "tests"

    # Collect all Python modules
    py_files = sorted(root.rglob("*.py"))
    modules: list[dict[str, Any]] = []
    for f in py_files:
        if f.name == "__init__.py":
            continue
        if "__pycache__" in str(f):
            continue
        mod = _parse_module(f)
        mod["family"] = _family_for_module(f.stem, mod["path"])
        mod["test_references"] = _find_test_references(f.stem, tests_dir)
        modules.append(mod)

    # Build import graph
    inbound = _build_import_graph(modules)
    cycle_list = _detect_cycles(modules)
    cycle_members = set()
    for cycle in cycle_list:
        for m in cycle:
            cycle_members.add(m)

    # Enrich modules with graph metrics
    for mod in modules:
        stem = Path(mod["path"]).stem
        mod["import_count_inbound"] = len(inbound.get(stem, set()))
        mod["cycle_member"] = stem in cycle_members
        mod["suggested_action"] = _suggest_action(
            mod, mod["import_count_inbound"], mod["cycle_member"],
        )
        mod["confidence_flags"] = _confidence_flags(mod, mod["import_count_inbound"])

    # Aggregate stats
    total_loc = sum(m.get("loc", 0) for m in modules)
    root_modules = [m for m in modules if "/" not in str(Path(m["path"]).parent).replace("dharma_swarm", "").strip("/")]
    family_counts: dict[str, int] = defaultdict(int)
    for m in modules:
        family_counts[m["family"]] += 1

    report = {
        "meta": {
            "tool": "module_metabolism_report",
            "version": "0.1.0",
            "package_root": str(root),
            "strategy_ref": "docs/governance/MODULE_METABOLISM_STRATEGY.md",
        },
        "summary": {
            "total_modules": len(modules),
            "total_loc": total_loc,
            "root_level_modules": len([
                m for m in modules
                if m["path"].count("/") == 1  # dharma_swarm/foo.py
            ]),
            "over_500_loc": len([m for m in modules if m.get("loc", 0) > 500]),
            "over_1000_loc": len([m for m in modules if m.get("loc", 0) > 1000]),
            "over_3000_loc": len([m for m in modules if m.get("loc", 0) > 3000]),
            "import_cycles": len(cycle_list),
            "no_inbound_imports": len([
                m for m in modules if m.get("import_count_inbound", 0) == 0
            ]),
            "no_test_references": len([
                m for m in modules if m.get("test_references", 0) == 0
            ]),
            "parse_errors": len([m for m in modules if m.get("parse_error")]),
        },
        "family_distribution": dict(sorted(family_counts.items())),
        "action_distribution": {
            action: len([m for m in modules if m.get("suggested_action") == action])
            for action in ["keep", "split-review", "merge-review", "facade", "archive-review"]
        },
        "cycles": [" -> ".join(c) for c in cycle_list],
        "modules": modules,
    }
    return report


def format_text(report: dict[str, Any]) -> str:
    """Format report as human-readable text."""
    lines: list[str] = []
    s = report["summary"]
    lines.append("=" * 72)
    lines.append("MODULE METABOLISM REPORT")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"Total modules: {s['total_modules']}")
    lines.append(f"Total LOC: {s['total_loc']:,}")
    lines.append(f"Root-level modules: {s['root_level_modules']}")
    lines.append(f"Over 500 LOC: {s['over_500_loc']}")
    lines.append(f"Over 1000 LOC: {s['over_1000_loc']}")
    lines.append(f"Over 3000 LOC: {s['over_3000_loc']}")
    lines.append(f"Import cycles: {s['import_cycles']}")
    lines.append(f"No inbound imports: {s['no_inbound_imports']}")
    lines.append(f"No test references: {s['no_test_references']}")
    lines.append(f"Parse errors: {s['parse_errors']}")
    lines.append("")

    lines.append("--- Family Distribution ---")
    for family, count in report.get("family_distribution", {}).items():
        lines.append(f"  {family}: {count}")
    lines.append("")

    lines.append("--- Action Distribution ---")
    for action, count in report.get("action_distribution", {}).items():
        if count > 0:
            lines.append(f"  {action}: {count}")
    lines.append("")

    if report.get("cycles"):
        lines.append("--- Import Cycles ---")
        for cycle in report["cycles"]:
            lines.append(f"  {cycle}")
        lines.append("")

    # Modules needing attention (not 'keep')
    attention = [
        m for m in report.get("modules", [])
        if m.get("suggested_action") != "keep"
    ]
    if attention:
        lines.append("--- Modules Needing Attention ---")
        for m in sorted(attention, key=lambda x: -x.get("loc", 0)):
            flags = ", ".join(m.get("confidence_flags", [])) or "none"
            lines.append(
                f"  {m['path']} ({m.get('loc', 0)} LOC) "
                f"-> {m.get('suggested_action')} [{flags}]"
            )
        lines.append("")

    lines.append("=" * 72)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Module metabolism report — warn-only repo-integrity evidence",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        help="Write JSON report to this path",
    )
    parser.add_argument(
        "--text-out",
        type=str,
        default=None,
        help="Write text report to this path",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout output",
    )
    args = parser.parse_args()

    report = generate_report()

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(report, indent=2, default=str) + "\n",
        )

    text = format_text(report)
    if args.text_out:
        Path(args.text_out).write_text(text + "\n")

    if not args.quiet:
        print(text)


if __name__ == "__main__":
    main()
