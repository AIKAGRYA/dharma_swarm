#!/usr/bin/env python3
"""Spine ownership guard — composes into uplift_guards/run_pre_commit.py.

Replaces tools/spine_check.py (PR A) with a guard registered in the existing
fail-closed pre-commit composition. The repo doesn't need more guards; it
needs guard convergence.

Doctrine:
    Receipts may differ by closure layer. Correlation identity must not.
    Each closure layer may have its own canonical receipt.
    Cross-layer identity continuity is the global invariant.

This guard enforces three invariants on the correlation spine:

  1. Spine importable — dharma_swarm.spine exports the canonical types
     (EvidenceReceipt, RoutingDecision, invoke_agent).

  2. New sqlite/aiosqlite importers under dharma_swarm/spine/ declare their
     role with a `# spine: <role>` comment, where role is one of:
       canonical-store | derived-view | plugin-sink |
       cache | legacy-mirror | migration-mirror | exempt

     Files outside dharma_swarm/spine/ are grandfathered (per PR A);
     future PRs shrink this set as each module declares its role.

  3. Allow-list-at-zero (spine-adoption item 4, drained 2026-07-03) —
     the dispatch bypass allowlist stays at the governed ratchet baseline
     (docs/governance/hygiene/ratchet_baselines.json:spine_bypass_entries,
     currently 0), and NO unknown/unclassified `.submit()` site may exist.
     The only sanctioned relief is a PR that visibly raises the ratchet
     baseline with review (ORGANISM_REWIRE_DOCTRINE_2026-07-02 §1) — this
     guard reads that baseline rather than owning a second number.

Module size is NOT checked here — Rule 10 (check_module_budget.py) owns
module size. Adding a size check here would be governance substrate drift.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

_SPINE_DECL_RE = re.compile(r"^#\s*spine:\s*\S+", re.MULTILINE)
_SQLITE_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+(?:sqlite3|aiosqlite)|from\s+(?:sqlite3|aiosqlite)\s+import)",
    re.MULTILINE,
)

_VALID_ROLES = {
    "canonical-store",
    "derived-view",
    "plugin-sink",
    "cache",
    "legacy-mirror",
    "migration-mirror",
    "exempt",
    # Legacy free-form roles from PR A; kept valid for backward compat:
    "writes",
    "reads",
}


def _is_grandfathered(rel: Path) -> bool:
    """Files outside dharma_swarm/spine/ are grandfathered in PR A.5.

    Future PRs (B+) shrink this list as each module declares its
    relation to EvidenceReceipt.
    """
    if str(rel).startswith("dharma_swarm/spine/"):
        return False
    return True


def _check_sqlite_declarations(repo_root: Path) -> list[str]:
    failures: list[str] = []
    pkg = repo_root / "dharma_swarm"

    for root, _dirs, files in os.walk(pkg):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = Path(root) / fname
            rel = fpath.relative_to(repo_root)

            try:
                content = fpath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            if not _SQLITE_IMPORT_RE.search(content):
                continue
            if _SPINE_DECL_RE.search(content):
                continue
            if _is_grandfathered(rel):
                continue

            failures.append(
                f"{rel} imports sqlite3/aiosqlite but has no '# spine: <role>' "
                f"declaration. Add one of: canonical-store | derived-view | "
                f"plugin-sink | cache | legacy-mirror | migration-mirror | exempt"
            )

    return failures


def _check_spine_importable(repo_root: Path) -> list[str]:
    """Verify spine modules parse and export expected symbols."""
    failures: list[str] = []
    script = (
        "import sys, types, os\n"
        "root = os.environ['REPO_ROOT']\n"
        "sys.path.insert(0, root)\n"
        "sys.modules.setdefault('dharma_swarm', types.ModuleType('dharma_swarm'))\n"
        "sys.modules['dharma_swarm'].__path__ = [os.path.join(root, 'dharma_swarm')]\n"
        "sp = types.ModuleType('dharma_swarm.spine')\n"
        "sp.__path__ = [os.path.join(root, 'dharma_swarm', 'spine')]\n"
        "sys.modules['dharma_swarm.spine'] = sp\n"
        "from dharma_swarm.spine import receipt, routing, invoke\n"
        "assert hasattr(receipt, 'EvidenceReceipt'), 'missing EvidenceReceipt'\n"
        "assert hasattr(routing, 'RoutingDecision'), 'missing RoutingDecision'\n"
        "assert hasattr(invoke, 'invoke_agent'), 'missing invoke_agent'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, "REPO_ROOT": str(repo_root)},
    )
    if result.returncode != 0:
        err = result.stderr.strip().split("\n")[-1] if result.stderr else "unknown"
        failures.append(f"cannot import dharma_swarm.spine: {err}")
    return failures


def _check_bypass_allowlist_at_zero(repo_root: Path) -> list[str]:
    """Invariant 3: dispatch bypass allowlist held at the ratchet baseline.

    Runs the bypass scan owned by scripts/governance/spine_bypass_report.py
    and fails when (a) any `.submit()` site is unknown/unclassified, or
    (b) the intentional allowlist exceeds the `spine_bypass_entries`
    ratchet baseline. The baseline file is the single governed number;
    raising it (with review) is the only sanctioned relief path.
    """
    import importlib.util
    import json as _json

    failures: list[str] = []

    report_path = repo_root / "scripts" / "governance" / "spine_bypass_report.py"
    baseline_path = (
        repo_root / "docs" / "governance" / "hygiene" / "ratchet_baselines.json"
    )
    if not report_path.exists():
        return [f"bypass scan owner missing: {report_path.relative_to(repo_root)}"]

    try:
        baseline = int(
            _json.loads(baseline_path.read_text(encoding="utf-8"))["counters"][
                "spine_bypass_entries"
            ]
        )
    except Exception as exc:
        return [f"cannot read spine_bypass_entries ratchet baseline: {exc}"]

    spec = importlib.util.spec_from_file_location("spine_bypass_report", report_path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        entries = mod._scan_production_submits()
    except Exception as exc:
        return [f"bypass scan failed to run: {exc}"]

    unknown = [e for e in entries if e.classification == "unknown"]
    if unknown:
        failures.append(
            f"{len(unknown)} unclassified dispatch bypass site(s): "
            + ", ".join(f"{e.file}:{e.line}" for e in unknown)
        )

    intentional = len(mod._INTENTIONAL_BYPASS)
    if intentional > baseline:
        failures.append(
            f"intentional bypass allowlist has {intentional} entr(y/ies) but the "
            f"spine_bypass_entries ratchet baseline is {baseline}. Migrate the "
            f"site through submit_task_via_spine(), or raise the baseline in "
            f"docs/governance/hygiene/ratchet_baselines.json as a reviewed, "
            f"visible governance act."
        )

    return failures


def check_spine_ownership(repo_root: Path, **_kwargs) -> tuple[bool, str]:
    """Composable guard entry point for run_pre_commit.py GUARDS list.

    Returns (passed, message). Same shape as the other 7 uplift guards.
    """
    failures: list[str] = []
    failures.extend(_check_spine_importable(repo_root))
    failures.extend(_check_sqlite_declarations(repo_root))
    failures.extend(_check_bypass_allowlist_at_zero(repo_root))

    if failures:
        first = failures[0]
        return (
            False,
            f"SPINE OWNERSHIP GUARD: {len(failures)} failure(s). First: {first}",
        )
    return True, (
        "spine ownership clear (importable + all sqlite users declared "
        "+ bypass allowlist at baseline)"
    )


def main() -> int:
    """CLI entry point for `make spine-check` convenience alias only.

    The real integration point is uplift_guards/run_pre_commit.py.
    """
    repo_root = Path(__file__).resolve().parents[2]
    ok, msg = check_spine_ownership(repo_root)
    if ok:
        print(f"spine-check: {msg}")
        return 0
    print(f"spine-check: {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
