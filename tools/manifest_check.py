#!/usr/bin/env python3
"""Manifest reconciliation gate.

Turns ACTIVE_SURFACE_MANIFEST.yaml from documented intent into machine-enforced
invariants. Pure stdlib + PyYAML, no new dependencies, no edits to frozen
spine surfaces (dharma_swarm/spine/**, orchestrator.py, agent_runner.py,
runtime_state.py).

Five invariants enforced:

  1. manifest_parseable
     Manifest parses as YAML, has required top-level keys, schema_version
     is supported.

  2. routers_declared_and_wired
     Every manifest `api_routers[]` entry resolves to a module file that
     exists AND is `include_router`'d in api/main.py. Conversely, every
     router wired in api/main.py is declared in the manifest.

  3. agents_modules_exist
     Every `agents[].module`, `hot_path_modules[].module`, `loops[].module`,
     and `recursive_discovery_surfaces[].owner_module` points to a file
     that exists on disk.

  4. state_dir_paths_via_helper (advisory, budget-bounded)
     Counts raw `~/.dharma/...` string literals across Python sources.
     Compared against a budget; failures only when the count grows.

  5. evidence_receipt_uniqueness
     Exactly two `class EvidenceReceipt:` definitions exist
     (operator_core/closure_v0.py — production; spine/receipt.py — doctrine).
     No third definition may be introduced.

Exit codes: 0 on pass, 1 on violation. Use `--report` for human-readable
output without exit-code semantics. Use `--update-budget` to overwrite the
state_dir-literal budget after intentional reductions (e.g., PR-H4 storage
work).

Authority: external_worker_evidence_only. Doctrine-safe (no spine code
changes). Companion to docs/reports/modularity_and_future_proofing_audit_v1.md
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print(
        "manifest_check: PyYAML not available. Install with `pip install pyyaml`.",
        file=sys.stderr,
    )
    sys.exit(2)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = _REPO_ROOT / "ACTIVE_SURFACE_MANIFEST.yaml"
_API_MAIN = _REPO_ROOT / "api" / "main.py"
_DHARMA_PKG = _REPO_ROOT / "dharma_swarm"
_BUDGET_PATH = _REPO_ROOT / "tools" / "manifest_check_budgets.json"

# Supported manifest schema versions. Bump when intentional breaking changes.
_SUPPORTED_SCHEMA_VERSIONS = {2}

# The two canonical EvidenceReceipt definition sites. Any third site is a
# violation; missing either is also a violation.
_CANONICAL_RECEIPT_SITES = {
    "dharma_swarm/operator_core/closure_v0.py",  # proven, 53+ uses
    "dharma_swarm/spine/receipt.py",  # doctrine, OTel-aligned
}

# Regex for raw ~/.dharma literals in Python sources.
_DHARMA_LITERAL_RE = re.compile(r'["\']~/\.dharma\b')


# ─── Result types ────────────────────────────────────────────────────────────


@dataclass
class Violation:
    check: str
    severity: str  # "error" | "warn"
    message: str
    path: str | None = None


@dataclass
class CheckReport:
    violations: list[Violation] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def add(self, v: Violation) -> None:
        self.violations.append(v)

    def errors(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == "error"]

    def warns(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == "warn"]


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _module_path(module_str: str) -> Path:
    """Convert 'api.routers.health' or 'dharma_swarm/swarm.py' to a Path."""
    if module_str.endswith(".py") or "/" in module_str:
        return _REPO_ROOT / module_str
    return _REPO_ROOT / (module_str.replace(".", "/") + ".py")


def _load_manifest() -> tuple[dict[str, Any] | None, CheckReport]:
    report = CheckReport()
    if not _MANIFEST_PATH.exists():
        report.add(
            Violation(
                "manifest_parseable",
                "error",
                f"manifest not found at {_MANIFEST_PATH.relative_to(_REPO_ROOT)}",
            )
        )
        return None, report

    try:
        with _MANIFEST_PATH.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        report.add(
            Violation(
                "manifest_parseable",
                "error",
                f"manifest YAML parse error: {exc}",
                path=str(_MANIFEST_PATH.relative_to(_REPO_ROOT)),
            )
        )
        return None, report

    if not isinstance(data, dict):
        report.add(
            Violation(
                "manifest_parseable",
                "error",
                f"manifest root must be a mapping, got {type(data).__name__}",
            )
        )
        return None, report

    schema_version = data.get("schema_version")
    if schema_version not in _SUPPORTED_SCHEMA_VERSIONS:
        report.add(
            Violation(
                "manifest_parseable",
                "error",
                f"manifest schema_version={schema_version!r} not in supported "
                f"set {sorted(_SUPPORTED_SCHEMA_VERSIONS)}",
            )
        )
        return None, report

    return data, report


def _load_budgets() -> dict[str, int]:
    if not _BUDGET_PATH.exists():
        return {}
    try:
        with _BUDGET_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_budgets(budgets: dict[str, int]) -> None:
    with _BUDGET_PATH.open("w", encoding="utf-8") as fh:
        json.dump(budgets, fh, indent=2, sort_keys=True)
        fh.write("\n")


# ─── Check 2: routers_declared_and_wired ─────────────────────────────────────


def _extract_wired_routers(api_main: Path) -> set[str]:
    """Parse api/main.py and return the set of router module dotted paths
    that are include_router'd. Handles `from api.routers.X import router as Y`
    + `api_app.include_router(Y)`.
    """
    if not api_main.exists():
        return set()
    src = api_main.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()

    # Map alias -> source module (e.g., 'health_router' -> 'api.routers.health')
    alias_to_module: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("api.routers"):
                for alias in node.names:
                    if alias.name == "router":
                        alias_to_module[alias.asname or alias.name] = node.module
                    elif alias.name == "ws_router":
                        alias_to_module[alias.asname or alias.name] = node.module

    # Walk include_router() calls
    wired_modules: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            alias = node.args[0].id
            if alias in alias_to_module:
                wired_modules.add(alias_to_module[alias])

    return wired_modules


def check_routers(manifest: dict[str, Any], report: CheckReport) -> None:
    declared = manifest.get("api_routers", []) or []
    declared_modules = {entry.get("module") for entry in declared if entry.get("module")}
    wired_modules = _extract_wired_routers(_API_MAIN)

    # Declared but missing on disk
    for entry in declared:
        mod = entry.get("module")
        if not mod:
            continue
        path = _module_path(mod)
        if not path.exists():
            report.add(
                Violation(
                    "routers_declared_and_wired",
                    "error",
                    f"manifest declares router {entry.get('id', '?')!r} "
                    f"module={mod} but file does not exist",
                    path=str(path.relative_to(_REPO_ROOT)),
                )
            )

    # Declared but not wired in api/main.py
    for mod in declared_modules:
        if mod and mod not in wired_modules:
            report.add(
                Violation(
                    "routers_declared_and_wired",
                    "error",
                    f"manifest declares router module {mod} but it is not "
                    f"include_router'd in api/main.py",
                )
            )

    # Wired but not declared in manifest
    for mod in wired_modules:
        if mod not in declared_modules:
            report.add(
                Violation(
                    "routers_declared_and_wired",
                    "error",
                    f"api/main.py wires router {mod} but the manifest "
                    f"api_routers[] does not declare it",
                )
            )


# ─── Check 3: agents_modules_exist ───────────────────────────────────────────


def check_agent_modules(manifest: dict[str, Any], report: CheckReport) -> None:
    """All declared subsystem modules must exist on disk."""

    def _check_section(section_name: str, key: str) -> None:
        for entry in manifest.get(section_name, []) or []:
            mod = entry.get(key)
            if not mod:
                continue
            path = _REPO_ROOT / mod
            if not path.exists():
                report.add(
                    Violation(
                        "agents_modules_exist",
                        "error",
                        f"manifest {section_name}[{entry.get('id', '?')}] "
                        f"declares {key}={mod} but file does not exist",
                        path=mod,
                    )
                )

    _check_section("agents", "module")
    _check_section("hot_path_modules", "module")
    _check_section("loops", "module")
    _check_section("recursive_discovery_surfaces", "owner_module")


# ─── Check 4: state_dir_paths_via_helper (budget-bounded) ────────────────────


def count_dharma_literals() -> tuple[int, list[Path]]:
    """Count raw '~/.dharma/...' string literals in dharma_swarm/ Python.

    Excludes the helper module itself (dharma_swarm/daemon_config.py)
    which legitimately owns the canonical path.
    """
    count = 0
    offenders: list[Path] = []
    for py in _DHARMA_PKG.rglob("*.py"):
        rel = py.relative_to(_REPO_ROOT)
        # The helper itself is allowed to define the canonical path.
        if rel.name == "daemon_config.py":
            continue
        try:
            content = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hits = _DHARMA_LITERAL_RE.findall(content)
        if hits:
            count += len(hits)
            offenders.append(rel)
    return count, offenders


def check_state_dir_literals(report: CheckReport, budgets: dict[str, int]) -> int:
    """Advisory: count raw ~/.dharma literals. Fail only if count grew."""
    count, offenders = count_dharma_literals()
    budget = budgets.get("state_dir_literals", count)
    report.info.append(
        f"state_dir_paths_via_helper: literals={count}, budget={budget}, "
        f"offender files={len(offenders)}"
    )
    if count > budget:
        report.add(
            Violation(
                "state_dir_paths_via_helper",
                "error",
                f"raw ~/.dharma/... literals in dharma_swarm/*.py = {count}, "
                f"exceeds budget = {budget}. New code must route paths through "
                f"dharma_swarm.daemon_config helpers. Run with --update-budget "
                f"after intentional ratchet-up; reduce via PR-H4 storage work.",
            )
        )
    elif count < budget:
        report.info.append(
            f"state_dir_paths_via_helper: count={count} below budget={budget}. "
            f"Consider running --update-budget to ratchet down."
        )
    return count


# ─── Check 5: evidence_receipt_uniqueness ────────────────────────────────────


def check_receipt_uniqueness(report: CheckReport) -> None:
    """Exactly two `class EvidenceReceipt:` definitions may exist, at the
    two canonical sites. Any other site is a violation; missing either site
    is also a violation."""
    found_sites: set[str] = set()
    extra_sites: list[str] = []

    for py in _REPO_ROOT.rglob("*.py"):
        # Skip third-party / vendored / cache
        rel = py.relative_to(_REPO_ROOT)
        rel_str = str(rel)
        if rel_str.startswith((".git/", ".venv/", "venv/", "node_modules/")):
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        try:
            content = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # Cheap pre-filter
        if "EvidenceReceipt" not in content:
            continue
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "EvidenceReceipt":
                if rel_str in _CANONICAL_RECEIPT_SITES:
                    found_sites.add(rel_str)
                else:
                    extra_sites.append(rel_str)

    for missing in _CANONICAL_RECEIPT_SITES - found_sites:
        report.add(
            Violation(
                "evidence_receipt_uniqueness",
                "error",
                f"canonical EvidenceReceipt site {missing} no longer defines "
                f"`class EvidenceReceipt:`. If you intend to remove a canonical "
                f"site, edit tools/manifest_check.py _CANONICAL_RECEIPT_SITES "
                f"in the same PR.",
                path=missing,
            )
        )

    for extra in extra_sites:
        report.add(
            Violation(
                "evidence_receipt_uniqueness",
                "error",
                f"third EvidenceReceipt class defined at {extra}. The two "
                f"canonical definitions are {sorted(_CANONICAL_RECEIPT_SITES)}. "
                f"Adding a third receipt class fragments the truth surface. "
                f"Import from a canonical site or rename your class.",
                path=extra,
            )
        )


# ─── Orchestration ───────────────────────────────────────────────────────────


def run_all_checks(update_budget: bool = False) -> CheckReport:
    manifest, report = _load_manifest()
    if manifest is None:
        return report

    check_routers(manifest, report)
    check_agent_modules(manifest, report)
    check_receipt_uniqueness(report)

    budgets = _load_budgets()
    new_count = check_state_dir_literals(report, budgets)

    if update_budget:
        budgets["state_dir_literals"] = new_count
        _write_budgets(budgets)
        report.info.append(
            f"--update-budget: wrote state_dir_literals={new_count} to "
            f"{_BUDGET_PATH.relative_to(_REPO_ROOT)}"
        )

    return report


def format_report(report: CheckReport, verbose: bool = False) -> str:
    lines: list[str] = []
    errors = report.errors()
    warns = report.warns()

    if errors:
        lines.append(f"manifest-check: {len(errors)} error(s)")
        lines.append("")
        # Group by check
        by_check: dict[str, list[Violation]] = {}
        for v in errors:
            by_check.setdefault(v.check, []).append(v)
        for check_name in sorted(by_check):
            lines.append(f"  [{check_name}]")
            for v in by_check[check_name]:
                prefix = f"    {v.path}: " if v.path else "    "
                lines.append(f"{prefix}{v.message}")
            lines.append("")

    if warns:
        lines.append(f"manifest-check: {len(warns)} warning(s)")
        for v in warns:
            prefix = f"  {v.path}: " if v.path else "  "
            lines.append(f"{prefix}{v.message}")
        lines.append("")

    if verbose and report.info:
        lines.append("manifest-check info:")
        for msg in report.info:
            lines.append(f"  {msg}")
        lines.append("")

    if not errors and not warns:
        lines.append("manifest-check: all checks passed.")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile ACTIVE_SURFACE_MANIFEST.yaml against repository reality."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="CI mode: exit 1 on any error. Default if no other mode is set.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Human-readable summary; exit 0 regardless of findings.",
    )
    parser.add_argument(
        "--update-budget",
        action="store_true",
        help="Ratchet state_dir-literal budget to current count and exit 0.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Include info messages in output.",
    )
    args = parser.parse_args(argv)

    # Default mode is --check
    if not (args.check or args.report or args.update_budget):
        args.check = True

    report = run_all_checks(update_budget=args.update_budget)
    output = format_report(report, verbose=args.verbose or args.report)
    stream = sys.stderr if report.errors() else sys.stdout
    print(output, file=stream)

    if args.report or args.update_budget:
        return 0
    return 1 if report.errors() else 0


if __name__ == "__main__":
    sys.exit(main())
