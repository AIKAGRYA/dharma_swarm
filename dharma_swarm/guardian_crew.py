"""Guardian Crew — a tiny crew of powerful coding agents on a cron cycle.

These agents run continuously in the background, checking for:
    - Interface mismatches (wrong types, missing methods, broken call chains)
    - Dead loops (cybernetic loops declared in CYBERNETIC_LOOP_MAP.md but not running)
    - Broken connections (imports that fail, modules that exist in config but not on disk)
    - Model routing failures (providers returning 403/billing/timeout at high rates)
    - Memory write path failures (KnowledgeStore, MemoryPalace, evolution archive)
    - New code that breaks existing contracts (post-commit regression detection)

The crew has three specialist agents:

    AUDITOR: Interface contract verifier
        - Parses every Python file for calls to external modules
        - Checks that method signatures match the actual callee definition
        - Detects new mismatches introduced since the last clean commit
        - Writes findings to ~/.dharma/guardian/interface_audit.md

    LOOP_WATCHER: Cybernetic loop health monitor
        - Checks that all 13 loops in orchestrate_live are producing output
        - Reads signal_bus, message_bus, evolution archive for signs of life
        - Detects silent failures (loop running but producing zero events)
        - Writes findings to ~/.dharma/guardian/loop_health.md

    ROUTER_PROBE: Model routing health checker
        - Tests each provider in CANONICAL_SEED_ORDER with a minimal ping
        - Measures p50/p99 latency, error rate, circuit-breaker status
        - Identifies dead providers before they waste agent budgets
        - Writes findings to ~/.dharma/guardian/router_health.md

Combined output -> ~/.dharma/guardian/GUARDIAN_REPORT.md (overwritten each cycle)
GitHub issue created when severity >= BLOCKER and no open issue exists for that mismatch.

Cycle: every 4 hours (configurable via GUARDIAN_INTERVAL_SECONDS env var).

Usage::

    # One-shot
    python -m dharma_swarm.guardian_crew

    # As a background task in orchestrate_live (wired at end of task_factories)
    await guardian_crew.start_guardian_loop(state_dir=STATE_DIR)

Future-proofing design:
    - Each check is a standalone async function. Adding a new check = one function.
    - Results are structured dicts. The report synthesizer works regardless of check count.
    - Severity levels: BLOCKER, DEGRADED, WARNING, OK.
      BLOCKER: creates a GitHub issue + emits algedonic signal to S5.
      DEGRADED: writes to report, logs warning.
      WARNING: writes to report only.
      OK: not written (keeps report short).
    - The crew is self-documenting: the report always describes what was checked,
      what passed, and what failed. It can be read by any future agent to understand
      the current health state.
"""

from __future__ import annotations

import ast
import asyncio
import importlib
import json
import logging
import os
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.consistency_guard import run_task_consistency_guard
from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.guardian_runtime_checks import (
    run_guardian_warning_checks,
    runtime_context_bundle_injection_findings,
    runtime_context_status_counts,
    runtime_rows_missing_context,
)

logger = logging.getLogger(__name__)

_GUARDIAN_INTERVAL = int(os.environ.get("GUARDIAN_INTERVAL_SECONDS", "14400"))  # 4 hours


def _default_src_root() -> Path:
    """Return the package tree loaded by this running Guardian process."""
    return Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------

@dataclass
class GuardianFinding:
    severity: str          # BLOCKER | DEGRADED | WARNING | OK
    check: str             # which check found this
    title: str             # short title
    detail: str            # full explanation
    file: str = ""         # relevant file
    line: int = 0          # relevant line
    fix_hint: str = ""     # concrete 1-line fix suggestion


# ---------------------------------------------------------------------------
# AUDITOR: Interface contract verification
# ---------------------------------------------------------------------------

# These are the call patterns we actively track.
# Format: (caller_file, method_or_attr, correct_name_or_signature, severity)
_KNOWN_CONTRACTS: list[tuple[str, str, str, str]] = [
    # New modules introduced by recent commits
    ("archaeology_ingestion.py", "palace.recall", "PalaceQuery(text=..., max_results=...)", "BLOCKER"),
    ("dgm_loop.py", "DarwinEngine", "archive_path only — no _provider attr", "DEGRADED"),
    ("gnani_lodestone.py", "TelosGraph.get_by_name", "must exist on TelosGraph", "DEGRADED"),
    ("gnani_lodestone.py", "ConceptGraph.get_node", "must exist on ConceptGraph", "DEGRADED"),
    ("gnani_lodestone.py", "TaskBoard.get_by_title", "must exist on TaskBoard", "DEGRADED"),
    # Existing known contracts
    ("orchestrate_live.py", "PersistentAgent(role=..., provider_type=...)", "AgentRole enum + ProviderType enum", "BLOCKER"),
    ("swarm.py", "_classify_failure", "private method coupling to orchestrator", "DEGRADED"),
    ("swarm.py", "samvara.current_power", "needs None guard before .value", "DEGRADED"),
]

# Methods that must exist on their respective classes.
#
# IMPORTANT: do NOT list ``__init__`` here. ``__init__`` is auto-synthesized
# by ``@dataclass``, by ``pydantic.BaseModel``, by ``attrs``, and by Python
# itself (object.__init__ always exists). An AST-walk check that hunts for
# an explicit FunctionDef named ``__init__`` is therefore meaningless and
# was the direct cause of the ``[GUARDIAN] PalaceQuery.__init__() missing``
# duplicate-issue storm (issues #222-#511, ~70+ false BLOCKERs). The contract
# you actually want to assert lives in the keyword-argument signature, not
# the existence of the symbol. Add real signature checks via a dedicated
# helper if needed; do NOT add ``__init__`` rows here.
_METHOD_EXISTENCE_CHECKS: list[tuple[str, str, str, str]] = [
    # (module, class_name, method_name, severity)
    ("dharma_swarm.memory_palace", "MemoryPalace", "recall", "BLOCKER"),
    ("dharma_swarm.memory_palace", "MemoryPalace", "ingest", "BLOCKER"),
    ("dharma_swarm.evolution", "DarwinEngine", "auto_evolve", "BLOCKER"),
    ("dharma_swarm.evolution", "DarwinEngine", "apply_diff_and_test", "BLOCKER"),
    ("dharma_swarm.archaeology_ingestion", "ArchaeologyIngestionDaemon", "run_once", "BLOCKER"),
    ("dharma_swarm.dgm_loop", "DGMLoop", "run_one_generation", "BLOCKER"),
    ("dharma_swarm.world_actions", "WorldActionResult", "to_json", "BLOCKER"),
    ("dharma_swarm.gnani_lodestone", "GnaniLodestone", "seed_all", "BLOCKER"),
    ("dharma_swarm.telos_gates", "TelosGatekeeper", "check", "BLOCKER"),
    ("dharma_swarm.stigmergy", "StigmergyStore", "leave_mark", "BLOCKER"),
    ("dharma_swarm.task_board", "TaskBoard", "get_by_title", "BLOCKER"),
    ("dharma_swarm.telos_graph", "TelosGraph", "get_by_name", "BLOCKER"),
]

# Import chains that must succeed
_IMPORT_CHECKS: list[tuple[str, str]] = [
    ("dharma_swarm.world_actions", "BLOCKER"),
    ("dharma_swarm.dgm_loop", "BLOCKER"),
    ("dharma_swarm.archaeology_ingestion", "BLOCKER"),
    ("dharma_swarm.gnani_lodestone", "BLOCKER"),
    ("dharma_swarm.memory_palace", "BLOCKER"),
    ("dharma_swarm.evolution", "BLOCKER"),
    ("dharma_swarm.telos_gates", "BLOCKER"),
    ("dharma_swarm.stigmergy", "BLOCKER"),
    ("dharma_swarm.autonomous_agent", "BLOCKER"),
    ("dharma_swarm.orchestrate_live", "BLOCKER"),
]


_SYNTAX_SCAN_EXCLUDE_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "build",
        "dist",
        "node_modules",
    }
)


def _iter_python_sources(src_root: Path) -> list[Path]:
    """Return package Python sources, including nested subpackages."""
    if not src_root.exists():
        return []
    sources: list[Path] = []
    for py_file in src_root.rglob("*.py"):
        if any(part in _SYNTAX_SCAN_EXCLUDE_DIRS for part in py_file.parts):
            continue
        sources.append(py_file)
    return sorted(sources)


def _module_source_candidates(module_name: str, src_root: Path) -> list[Path]:
    """Return source-file candidates for a package module.

    Guardian usually receives ``src_root`` as the repo's ``dharma_swarm/``
    directory, but live daemons have historically run from stale worktree paths.
    Resolve through importlib as a fallback so a bad root does not create false
    BLOCKER issues for modules that are importable in the active environment.
    """
    module_path = module_name.replace(".", "/")
    candidates = [
        src_root / (module_path.replace("dharma_swarm/", "") + ".py"),
        src_root / (module_path + ".py"),
    ]
    try:
        spec = importlib.util.find_spec(module_name)
    except Exception:
        spec = None
    origin = getattr(spec, "origin", None) if spec is not None else None
    if origin and origin not in {"built-in", "namespace"}:
        candidates.append(Path(origin))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _has_pydantic_base(class_node: ast.ClassDef) -> bool:
    """Return True if ``class_node`` inherits from ``BaseModel`` / ``pydantic.BaseModel``.

    Pydantic synthesizes ``__init__`` from declared fields, exactly like
    ``@dataclass``. AST cannot resolve the MRO, so we match by base-class
    name only. False positives here are harmless — they only suppress an
    AUDITOR:method_exists finding that was already meaningless.
    """
    for base in class_node.bases:
        target = base.func if isinstance(base, ast.Call) else base
        if isinstance(target, ast.Name) and target.id in {"BaseModel", "PydanticBaseModel"}:
            return True
        if isinstance(target, ast.Attribute) and target.attr in {"BaseModel", "PydanticBaseModel"}:
            return True
    return False


def _has_attrs_decorator(class_node: ast.ClassDef) -> bool:
    """Return True if ``class_node`` is decorated with ``@attr.s`` / ``@attrs.define``.

    Both ``attr`` and ``attrs`` synthesize ``__init__``.
    """
    for dec in class_node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name) and target.id in {"define", "frozen", "mutable", "attrs"}:
            return True
        if isinstance(target, ast.Attribute) and target.attr in {
            "s", "define", "frozen", "mutable", "attrs", "attributes",
        }:
            return True
    return False


def _has_synthesized_init(class_node: ast.ClassDef) -> bool:
    """Umbrella: any framework that auto-generates ``__init__``.

    Centralizes the "this class has a real __init__ even though the AST
    shows no FunctionDef named __init__" decision. Add new frameworks here
    rather than scattering checks through ``run_auditor``.
    """
    return (
        _has_dataclass_decorator(class_node)
        or _has_pydantic_base(class_node)
        or _has_attrs_decorator(class_node)
    )


def _has_dataclass_decorator(class_node: ast.ClassDef) -> bool:
    """Return True if ``class_node`` is decorated with ``@dataclass``.

    Accepts ``@dataclass``, ``@dataclasses.dataclass``, ``@dataclass(...)``,
    and ``@dataclasses.dataclass(...)``. The dataclass machinery synthesizes
    ``__init__`` at decoration time, so the AUDITOR:method_exists AST walk
    must treat these classes as having an implicit ``__init__``.
    """
    for dec in class_node.decorator_list:
        # Unwrap dataclass(...) → look at the call target
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name) and target.id == "dataclass":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "dataclass":
            return True
    return False


async def run_auditor(src_root: Path) -> list[GuardianFinding]:
    """AUDITOR: Check import chains, method existence, and known contract violations."""
    findings: list[GuardianFinding] = []

    # 1. Import checks
    for module_name, severity in _IMPORT_CHECKS:
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                findings.append(GuardianFinding(
                    severity=severity,
                    check="AUDITOR:import",
                    title=f"Module not found: {module_name}",
                    detail=f"importlib.find_spec returned None for {module_name}",
                    file=module_name.replace('.', '/') + '.py',
                    fix_hint=f"Ensure {module_name.split('.')[-1]}.py exists in dharma_swarm/",
                ))
        except Exception as exc:
            findings.append(GuardianFinding(
                severity=severity,
                check="AUDITOR:import",
                title=f"Import error: {module_name}",
                detail=str(exc),
                file=module_name.replace('.', '/') + '.py',
            ))

    # 2. Method existence checks (parse AST, don't import)
    for module_name, class_name, method_name, severity in _METHOD_EXISTENCE_CHECKS:
        candidates = _module_source_candidates(module_name, src_root)
        found_file = next((p for p in candidates if p.exists()), None)
        if found_file is None:
            # Stale-worktree guard: a daemon pointed at a stale or incomplete
            # ``src_root`` will see every module as missing and file BLOCKERs
            # for files that exist on main. That is a daemon-deployment bug,
            # not a code bug. Downgrade to WARNING so it never reaches
            # ``_create_issue_if_needed``. See issues #20-#511 (PalaceQuery)
            # and the 10 ``File not found for ...`` siblings closed alongside
            # PR #520. The legitimate ``module is genuinely missing on main``
            # signal is still surfaced via the syntax-scan pass below and the
            # import-existence pass above.
            findings.append(GuardianFinding(
                severity="WARNING",
                check="AUDITOR:method_exists",
                title=f"File not found for {module_name}",
                detail=(
                    f"Tried: {[str(c) for c in candidates]}. If this fires on a "
                    "deployed daemon, restart it from a fresh checkout; the live "
                    "src_root is stale."
                ),
            ))
            continue

        try:
            tree = ast.parse(found_file.read_text(encoding="utf-8"))
            class_node = next(
                (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == class_name),
                None,
            )
            if class_node is None:
                # Same stale-worktree concern: AST may be from a stale file
                # in which the class was renamed/added later. The import-check
                # pass already covers "module legitimately broken". Downgrade.
                findings.append(GuardianFinding(
                    severity="WARNING",
                    check="AUDITOR:method_exists",
                    title=f"Class {class_name} not found in {found_file.name}",
                    detail=f"Module {module_name} exists but class {class_name} is missing",
                    file=found_file.name,
                    fix_hint=f"Add class {class_name} to {found_file.name}",
                ))
                continue

            method_exists = any(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method_name
                for n in ast.walk(class_node)
            )
            # Dataclasses get __init__ synthesized at decoration time.
            # @dataclass, @dataclasses.dataclass, and @dataclass(...) calls
            # all qualify. Without this branch, every dataclass on the
            # checklist is flagged as missing __init__ (false positive that
            # produced 29+ duplicate GUARDIAN issues, e.g. #325-#353).
            if method_name == "__init__" and not method_exists:
                if _has_synthesized_init(class_node):
                    method_exists = True
            if not method_exists:
                # Defense in depth: NEVER emit a BLOCKER for a missing
                # ``__init__``. Every Python class inherits ``object.__init__``,
                # and frameworks (dataclass, pydantic, attrs) synthesize one
                # we cannot detect via AST alone. Downgrade to WARNING so it
                # cannot reach ``_create_issue_if_needed`` and spam GitHub.
                # See issues #222-#511 for the storm this prevents.
                effective_severity = (
                    "WARNING" if method_name == "__init__" else severity
                )
                findings.append(GuardianFinding(
                    severity=effective_severity,
                    check="AUDITOR:method_exists",
                    title=f"{class_name}.{method_name}() missing in {found_file.name}",
                    detail=f"Class {class_name} exists but method {method_name} is not defined",
                    file=found_file.name,
                    fix_hint=f"Add `def {method_name}(self, ...)` to {class_name}",
                ))
        except SyntaxError as exc:
            findings.append(GuardianFinding(
                severity="BLOCKER",
                check="AUDITOR:syntax",
                title=f"Syntax error: {found_file.name}",
                detail=f"Line {exc.lineno}: {exc.msg}",
                file=found_file.name,
                line=exc.lineno or 0,
                fix_hint=f"Fix syntax at line {exc.lineno}",
            ))

    # 3. Scan all Python files for syntax errors (catches nested-package regressions)
    for py_file in _iter_python_sources(src_root):
        try:
            relative_file = str(py_file.relative_to(src_root.parent))
        except ValueError:
            relative_file = str(py_file)
        try:
            ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            findings.append(GuardianFinding(
                severity="BLOCKER",
                check="AUDITOR:syntax",
                title=f"Syntax error: {relative_file}",
                detail=f"Line {exc.lineno}: {exc.msg}",
                file=relative_file,
                line=exc.lineno or 0,
                fix_hint=f"Fix syntax error at line {exc.lineno}",
            ))

    return findings


# ---------------------------------------------------------------------------
# LOOP_WATCHER: Cybernetic loop health monitor
# ---------------------------------------------------------------------------

# Expected loops and their heartbeat signals
_EXPECTED_LOOPS = [
    ("evolution", "evolution archive", lambda d: (d / "evolution" / "archive.jsonl").exists()),
    ("stigmergy", "stigmergy marks", lambda d: (d / "stigmergy" / "marks.jsonl").exists()),
    ("telos", "telos objectives", lambda d: (d / "telos" / "objectives.jsonl").exists()),
    ("memory", "memory palace db", lambda d: (d / "memory" / "palace.db").exists() or (d / "memory" / "palace").exists()),
    ("gnani", "gnani seeded flag", lambda d: (d / "meta" / "gnani_seeded").exists()),
    ("archaeology", "lessons learned", lambda d: (d / "meta" / "lessons_learned.md").exists()),
    ("sub_swarms", "sub_swarm specs dir", lambda d: True),  # optional — OK if not yet created
]

# Loops that should be producing fresh output (check mtime)
_FRESHNESS_CHECKS = [
    # (description, path_lambda, max_age_hours)
    ("evolution archive", lambda d: d / "evolution" / "archive.jsonl", 24),
    ("stigmergy marks", lambda d: d / "stigmergy" / "marks.jsonl", 24),
    ("telos objectives", lambda d: d / "telos" / "objectives.jsonl", 72),
]


async def run_loop_watcher(state_dir: Path) -> list[GuardianFinding]:
    """LOOP_WATCHER: Check all cybernetic loops are alive and producing output."""
    findings: list[GuardianFinding] = []
    now = time.time()

    # 1. Existence checks
    for loop_name, artifact_name, check_fn in _EXPECTED_LOOPS:
        try:
            exists = check_fn(state_dir)
            if not exists:
                findings.append(GuardianFinding(
                    severity="WARNING",
                    check="LOOP_WATCHER:existence",
                    title=f"Loop artifact missing: {loop_name} ({artifact_name})",
                    detail=f"Expected artifact for {loop_name} loop not found in {state_dir}",
                    fix_hint=f"Run `dgc orchestrate-live` to boot the {loop_name} loop",
                ))
        except Exception as exc:
            logger.debug("Loop existence check failed for %s: %s", loop_name, exc)

    # 2. Freshness checks
    for description, path_fn, max_age_hours in _FRESHNESS_CHECKS:
        try:
            path = path_fn(state_dir)
            if path.exists():
                age_hours = (now - path.stat().st_mtime) / 3600
                if age_hours > max_age_hours:
                    findings.append(GuardianFinding(
                        severity="DEGRADED",
                        check="LOOP_WATCHER:freshness",
                        title=f"Stale loop output: {description}",
                        detail=(
                            f"{path.name} last modified {age_hours:.1f}h ago "
                            f"(threshold: {max_age_hours}h). "
                            f"The {description} loop may not be running."
                        ),
                        file=str(path),
                        fix_hint=f"Check if the {description} loop is active; restart if needed.",
                    ))
        except Exception as exc:
            logger.debug("Freshness check failed for %s: %s", description, exc)

    # 3. Evolution archive entry count check
    archive_path = state_dir / "evolution" / "archive.jsonl"
    if archive_path.exists():
        try:
            lines = [l for l in archive_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            applied = sum(1 for l in lines if '"applied"' in l)
            total = len(lines)
            if total > 0 and applied == 0:
                findings.append(GuardianFinding(
                    severity="DEGRADED",
                    check="LOOP_WATCHER:evolution_quality",
                    title="Evolution archive: zero applied entries",
                    detail=(
                        f"Archive has {total} entries but 0 have status='applied'. "
                        f"Evolution is running in shadow mode or all diffs are being rejected. "
                        f"Live mutation now requires a Forge verify_promotion packet."
                    ),
                    file=str(archive_path),
                    fix_hint="Use forge_v2.verify_promotion with signed receipts and an operator lease.",
                ))
        except Exception as exc:
            logger.debug("Evolution archive check failed: %s", exc)

    return findings


# ---------------------------------------------------------------------------
# LEDGER_WATCHER: Structured runtime row-count monitor
# ---------------------------------------------------------------------------

_STRUCTURED_RUNTIME_TABLES = ("task_claims", "delegation_runs", "artifact_records")
_STRUCTURED_RUNTIME_TABLE_TIMESTAMPS = {
    "task_claims": "claimed_at",
    "delegation_runs": "started_at",
    "artifact_records": "created_at",
}


def _runtime_db_candidates(state_dir: Path) -> list[Path]:
    """Return state-local runtime DB candidates without consulting Path.home()."""
    return [
        state_dir / "state" / "runtime.db",
        state_dir / "runtime.db",
    ]


def _runtime_table_count(db: sqlite3.Connection, table: str) -> int:
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if exists is None:
        return 0
    row = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0] if row else 0)


def _runtime_table_count_since(
    db: sqlite3.Connection,
    table: str,
    timestamp_column: str,
    since_iso: str,
) -> int:
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if exists is None:
        return 0
    columns = {
        str(row[1])
        for row in db.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if timestamp_column not in columns:
        return 0
    row = db.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {timestamp_column} >= ?",
        (since_iso,),
    ).fetchone()
    return int(row[0] if row else 0)


async def run_ledger_watcher(
    state_dir: Path,
    *,
    now: datetime | None = None,
) -> list[GuardianFinding]:
    """LEDGER_WATCHER: detect event growth with empty structured runtime tables."""
    findings: list[GuardianFinding] = []
    runtime_db = next((path for path in _runtime_db_candidates(state_dir) if path.exists()), None)
    if runtime_db is None:
        return findings

    resolved_now = now or datetime.now(timezone.utc)
    since_iso = (resolved_now - timedelta(hours=24)).isoformat()
    try:
        with sqlite3.connect(f"file:{runtime_db}?mode=ro", uri=True) as db:
            counts = {
                "session_events": _runtime_table_count(db, "session_events"),
                **{
                    table: _runtime_table_count(db, table)
                    for table in _STRUCTURED_RUNTIME_TABLES
                },
            }
            recent_counts = {
                "session_events": _runtime_table_count_since(
                    db,
                    "session_events",
                    "created_at",
                    since_iso,
                ),
                **{
                    table: _runtime_table_count_since(
                        db,
                        table,
                        _STRUCTURED_RUNTIME_TABLE_TIMESTAMPS[table],
                        since_iso,
                    )
                    for table in _STRUCTURED_RUNTIME_TABLES
                },
            }
            missing_context_counts = {
                "task_claims": runtime_rows_missing_context(
                    db,
                    "task_claims",
                    "claimed_at",
                    since_iso,
                ),
                "delegation_runs": runtime_rows_missing_context(
                    db,
                    "delegation_runs",
                    "started_at",
                    since_iso,
                ),
            }
            context_injection_findings = runtime_context_bundle_injection_findings(
                db,
                since_iso,
            )
            context_status_counts = runtime_context_status_counts(db, since_iso)
            from dharma_swarm.operator_brief.watchdog import (
                check_operator_brief_output,
                check_operator_brief_trace_coverage,
            )
            ob_findings = check_operator_brief_output(db, str(runtime_db))
            ob_findings.extend(
                check_operator_brief_trace_coverage(db, str(runtime_db))
            )
    except sqlite3.Error as exc:
        return [
            GuardianFinding(
                severity="WARNING",
                check="LEDGER_WATCHER:runtime_db",
                title="Runtime DB could not be read",
                detail=f"Failed to read structured runtime counts from {runtime_db}: {exc}",
                file=str(runtime_db),
                fix_hint="Verify runtime.db is a readable RuntimeStateStore SQLite database.",
            )
        ]

    session_events = counts["session_events"]
    structured_zero = all(counts[table] == 0 for table in _STRUCTURED_RUNTIME_TABLES)
    if structured_zero and session_events > 100:
        severity = "BLOCKER" if session_events > 1000 else "DEGRADED"
        threshold = "> 1000" if severity == "BLOCKER" else "> 100"
        findings.append(
            GuardianFinding(
                severity=severity,
                check="LEDGER_WATCHER:structured_runtime_counts",
                title="Session events are growing while structured runtime tables are empty",
                detail=(
                    f"{runtime_db} has session_events={session_events}, "
                    f"task_claims={counts['task_claims']}, "
                    f"delegation_runs={counts['delegation_runs']}, "
                    f"artifact_records={counts['artifact_records']}. "
                    f"Threshold {threshold} was crossed with all structured producer "
                    "tables empty, so lifecycle state is not inspectable from the "
                    "canonical RuntimeStateStore tables."
                ),
                file=str(runtime_db),
                fix_hint=(
                    "Wire existing RuntimeStateStore producers for task claims, "
                    "delegation runs, and artifacts; do not create a new ledger."
                ),
            )
        )
        return findings

    recent_session_events = recent_counts["session_events"]
    recent_structured_zero = all(
        recent_counts[table] == 0 for table in _STRUCTURED_RUNTIME_TABLES
    )
    if recent_session_events > 0 and recent_structured_zero:
        findings.append(
            GuardianFinding(
                severity="WARNING",
                check="LEDGER_WATCHER:delta_window",
                title="Session events grew in 24h while structured runtime rows did not",
                detail=(
                    f"{runtime_db} has 24h deltas: "
                    f"session_events={recent_session_events}, "
                    f"task_claims={recent_counts['task_claims']}, "
                    f"delegation_runs={recent_counts['delegation_runs']}, "
                    f"artifact_records={recent_counts['artifact_records']}. "
                    "Recent runtime activity is not producing structured "
                    "RuntimeStateStore rows."
                ),
                file=str(runtime_db),
                fix_hint=(
                    "Check existing RuntimeStateStore producers for recent task "
                    "claims, delegation runs, and artifacts."
                ),
            )
        )
    missing_context_total = sum(missing_context_counts.values())
    if missing_context_total > 0:
        findings.append(
            GuardianFinding(
                severity="WARNING",
                check="LEDGER_WATCHER:missing_context_bundle",
                title="Recent runtime claims or runs have no persisted context bundle",
                detail=(
                    f"{runtime_db} has recent rows without matching context_bundles: "
                    f"task_claims={missing_context_counts['task_claims']}, "
                    f"delegation_runs={missing_context_counts['delegation_runs']}. "
                    "Canonical action is occurring without a persisted pre-action "
                    "context bundle linked by metadata, run_id, or task/session."
                ),
                file=str(runtime_db),
                fix_hint=(
                    "Attach context_bundle_id during Orchestrator dispatch and ensure "
                    "AgentRunner consumes the persisted bundle before action."
                ),
            )
        )
    if context_injection_findings:
        examples = ", ".join(
            f"{bundle_id}:{'|'.join(items)}"
            for bundle_id, items in context_injection_findings[:5]
        )
        findings.append(
            GuardianFinding(
                severity="DEGRADED",
                check="LEDGER_WATCHER:context_bundle_injection",
                title="Recent context bundles contain prompt-injection signatures",
                detail=(
                    f"{runtime_db} has {len(context_injection_findings)} recent "
                    "context_bundles whose rendered_text matches injection scanner "
                    f"rules. Examples: {examples}. Persisted pre-action context is "
                    "load-bearing and must be treated as untrusted evidence before "
                    "AgentRunner prompt injection."
                ),
                file=str(runtime_db),
                fix_hint=(
                    "Sanitize or block suspicious persisted context before prompt "
                    "construction; keep Runtime Context Bundle text fenced as evidence."
                ),
            )
        )
    context_status_total = sum(context_status_counts.values())
    if context_status_total > 0:
        severity = (
            "BLOCKER"
            if context_status_total >= 20
            else "DEGRADED"
            if context_status_total >= 5
            else "WARNING"
        )
        breakdown = ", ".join(
            f"{status}={count}" for status, count in sorted(context_status_counts.items())
        )
        findings.append(
            GuardianFinding(
                severity=severity,
                check="LEDGER_WATCHER:context_bundle_status",
                title="Recent runtime rows record context bundle compile failures",
                detail=(
                    f"{runtime_db} has recent task/run rows with unhealthy "
                    f"context_bundle_status values: {breakdown}. Canonical action "
                    "is falling back from pre-action context compilation."
                ),
                file=str(runtime_db),
                fix_hint=(
                    "Inspect Orchestrator context_bundle_failed session events and "
                    "RuntimeStateStore availability before hard-gating dispatch."
                ),
            )
        )
    findings.extend(ob_findings)
    return findings


# ---------------------------------------------------------------------------
# ROUTER_PROBE: Model routing health checker
# ---------------------------------------------------------------------------

# Providers to probe (in priority order from CANONICAL_SEED_ORDER)
_PROVIDERS_TO_PROBE = [
    ("anthropic", "claude-sonnet-4-20250514", "ANTHROPIC_API_KEY"),
    ("openrouter", "openai/gpt-4o-mini", "OPENROUTER_API_KEY"),
    ("groq", "llama3-8b-8192", "GROQ_API_KEY"),
    ("ollama_cloud", "llama3.1:8b", None),  # no key needed
]

_CIRCUIT_BREAKER_SIGNALS = ["403", "billing", "exhausted", "access_denied", "payment"]


async def run_router_probe(state_dir: Path) -> list[GuardianFinding]:
    """ROUTER_PROBE: Check model routing health — dead providers, circuit breakers."""
    findings: list[GuardianFinding] = []

    # Check circuit breaker state file
    cb_path = state_dir / "meta" / "circuit_breakers.json"
    if cb_path.exists():
        try:
            cb_data = json.loads(cb_path.read_text(encoding="utf-8"))
            for provider, state in cb_data.items():
                is_open = state.get("is_open", False)
                trip_count = state.get("trip_count", 0)
                reason = state.get("reason", "")
                if is_open:
                    severity = "BLOCKER" if any(s in reason.lower() for s in _CIRCUIT_BREAKER_SIGNALS) else "DEGRADED"
                    findings.append(GuardianFinding(
                        severity=severity,
                        check="ROUTER_PROBE:circuit_breaker",
                        title=f"Circuit breaker OPEN: {provider}",
                        detail=f"Provider {provider} circuit breaker is open. Trips: {trip_count}. Reason: {reason}",
                        fix_hint=f"Check API key for {provider}; delete circuit_breakers.json to reset.",
                    ))
        except Exception as exc:
            logger.debug("Circuit breaker check failed: %s", exc)

    # Check for dead provider patterns in logs
    log_dir = state_dir.parent / ".dharma" / "logs" if (state_dir.parent / ".dharma").exists() else state_dir / "logs"
    if not log_dir.exists():
        log_dir = dharma_state_dir() / "logs"

    if log_dir.exists():
        try:
            # Scan last 1000 lines of the most recent log for dead provider signals
            log_files = sorted(log_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
            if log_files:
                recent_log = log_files[0]
                lines = recent_log.read_text(encoding="utf-8", errors="ignore").splitlines()[-1000:]
                provider_errors: dict[str, int] = {}
                for line in lines:
                    for provider, _, _ in _PROVIDERS_TO_PROBE:
                        if provider in line.lower():
                            for signal in _CIRCUIT_BREAKER_SIGNALS:
                                if signal in line.lower():
                                    provider_errors[provider] = provider_errors.get(provider, 0) + 1

                for provider, count in provider_errors.items():
                    if count >= 3:
                        findings.append(GuardianFinding(
                            severity="DEGRADED",
                            check="ROUTER_PROBE:log_errors",
                            title=f"Repeated errors: {provider} ({count} in last 1000 log lines)",
                            detail=f"Provider {provider} appears {count} times in error patterns. Possible dead provider.",
                            fix_hint=f"Check {provider} API key and quota; consider moving it lower in CANONICAL_SEED_ORDER.",
                        ))
        except Exception as exc:
            logger.debug("Log scan failed: %s", exc)

    # Check env vars for configured providers
    for provider, model, env_key in _PROVIDERS_TO_PROBE:
        if env_key and not os.environ.get(env_key):
            findings.append(GuardianFinding(
                severity="WARNING",
                check="ROUTER_PROBE:missing_key",
                title=f"Missing API key: {provider} ({env_key})",
                detail=f"Provider {provider} (model: {model}) requires {env_key} but it is not set.",
                fix_hint=f"Add {env_key}=... to ~/.dharma/.env or ~/dharma_swarm/.env",
            ))

    return findings


# ---------------------------------------------------------------------------
# Report synthesizer
# ---------------------------------------------------------------------------

def _severity_rank(s: str) -> int:
    return {"BLOCKER": 0, "DEGRADED": 1, "WARNING": 2, "OK": 3}.get(s, 4)


def synthesize_report(
    auditor_findings: list[GuardianFinding],
    loop_findings: list[GuardianFinding],
    router_findings: list[GuardianFinding],
    generated_at: str,
    src_root: Path,
    ledger_findings: list[GuardianFinding] | None = None,
    warning_findings: list[GuardianFinding] | None = None,
    consistency_findings: list[GuardianFinding] | None = None,
    room_findings: list[GuardianFinding] | None = None,
) -> str:
    ledger_findings = ledger_findings or []
    warning_findings = warning_findings or []
    consistency_findings = consistency_findings or []
    room_findings = room_findings or []
    all_findings = (
        auditor_findings
        + loop_findings
        + router_findings
        + ledger_findings
        + warning_findings
        + consistency_findings
        + room_findings
    )
    all_findings.sort(key=lambda f: _severity_rank(f.severity))

    blockers = [f for f in all_findings if f.severity == "BLOCKER"]
    degraded = [f for f in all_findings if f.severity == "DEGRADED"]
    warnings = [f for f in all_findings if f.severity == "WARNING"]

    lines = [
        "# GUARDIAN CREW REPORT",
        f"*Generated: {generated_at}*",
        f"*Src root: {src_root}*",
        "",
        "## Summary",
        f"| Severity | Count |",
        f"|----------|-------|",
        f"| BLOCKER  | {len(blockers)} |",
        f"| DEGRADED | {len(degraded)} |",
        f"| WARNING  | {len(warnings)} |",
        f"| TOTAL    | {len(all_findings)} |",
        "",
    ]

    def _section(title: str, findings: list[GuardianFinding]) -> list[str]:
        if not findings:
            return [f"## {title}", "*None.*", ""]
        out = [f"## {title}"]
        for i, f in enumerate(findings, 1):
            out += [
                f"### {i}. {f.title}",
                f"**Check:** `{f.check}` | **File:** `{f.file or 'N/A'}`" +
                (f" line {f.line}" if f.line else ""),
                "",
                f.detail,
                "",
            ]
            if f.fix_hint:
                out += [f"**Fix:** {f.fix_hint}", ""]
        return out

    lines += _section("BLOCKERs", blockers)
    lines += _section("DEGRADED", degraded)
    lines += _section("WARNINGs", warnings)

    lines += [
        "## Checked By",
        "- **AUDITOR**: Import chains, method existence, syntax errors across all modules",
        "- **LOOP_WATCHER**: Cybernetic loop artifact existence + freshness + evolution quality",
        "- **LEDGER_WATCHER**: RuntimeStateStore row counts for session events and structured producers",
        "- **GUARDIAN_WARNINGS**: Repo report freshness and registered .dharma top-level directories",
        "- **CONSISTENCY_GUARD**: Task-claim lifecycle cross-store consistency (NEW-05)",
        "- **ROUTER_PROBE**: Circuit breaker state, log error patterns, missing API keys",
        "- **ROOM_WATCHER**: Fractal room budget, kill/spinout condition health",
        "",
        "---",
        "*Guardian Crew runs every 4 hours. Report overwrites previous. "
        "BLOCKERs trigger GitHub issues via world_actions.github_create_issue().*",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GitHub issue creation for BLOCKERs
# ---------------------------------------------------------------------------

# Maximum number of open issues with the same normalized title that Guardian will
# tolerate before refusing to file more. Prevents runaway loops where a broken
# check fires the same false positive every cycle (see #222-#387 dataclass
# explosion). Setting this to 1 means "never file a second duplicate."
_MAX_OPEN_DUPLICATES = 1


def _normalize_title_for_dedup(title: str) -> str:
    """Normalize an issue title for duplicate detection.

    Strips the ``[GUARDIAN] `` prefix if present, lowercases, and collapses
    whitespace. Lets us treat ``[GUARDIAN] X`` and ``X`` as the same issue.
    """
    stripped = title.strip()
    if stripped.startswith("[GUARDIAN]"):
        stripped = stripped[len("[GUARDIAN]"):].strip()
    return " ".join(stripped.lower().split())


def _list_open_guardian_issues(repo: str) -> list[dict[str, Any]]:
    """Return all open GUARDIAN-labeled (by title prefix) issues for the repo.

    Uses ``gh issue list`` with no search filter and exact-title-matching in
    Python. The previous implementation used ``--search "<title> in:title"``
    which silently failed for titles containing parentheses, dunders, and
    dots — the exact shape every AUDITOR:method_exists finding produces.
    That broken search returned zero hits for issues that were already open,
    causing the 70+ duplicate explosion documented in #222-#387.
    """
    try:
        proc = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                repo,
                "--state",
                "open",
                "--json",
                "number,title",
                "--limit",
                "500",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    try:
        issues = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(issues, list):
        return []
    return [i for i in issues if isinstance(i, dict) and i.get("title", "").startswith("[GUARDIAN]")]


def _count_open_duplicates(repo: str, title: str) -> int:
    """Count open issues whose normalized title matches ``title``."""
    target = _normalize_title_for_dedup(title)
    if not target:
        return 0
    return sum(
        1 for issue in _list_open_guardian_issues(repo)
        if _normalize_title_for_dedup(issue.get("title", "")) == target
    )


def _github_issue_already_open(repo: str, title: str) -> bool:
    """Best-effort remote dedupe for Guardian issues.

    The local ``issues_created.json`` file is host-local. When Guardian runs from
    another machine or a rebuilt state dir, it can otherwise reopen the same
    BLOCKER every cycle. Uses exact-title-match in Python rather than the
    GitHub search ``in:title`` qualifier, which silently fails on titles
    containing ``()``, ``__``, and ``.``.
    """
    return _count_open_duplicates(repo, title) >= 1


def _list_open_prs(repo: str) -> list[dict[str, Any]]:
    """Return open pull requests with title and body. Best-effort, returns []
    on any failure (network, auth, etc.).
    """
    try:
        proc = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                repo,
                "--state",
                "open",
                "--json",
                "number,title,body",
                "--limit",
                "100",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    try:
        prs = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(prs, list):
        return []
    return [p for p in prs if isinstance(p, dict)]


def _finding_signature(finding: GuardianFinding) -> str:
    """Extract a short signature from a finding suitable for PR-body matching.

    For AUDITOR:method_exists findings titled
    ``PalaceQuery.__init__() missing in memory_palace.py``, returns
    ``PalaceQuery.__init__``. Falls back to the first 60 chars of the title.
    """
    title = finding.title or ""
    # Pattern: "<Class>.<method>() missing in <file>" -> "<Class>.<method>"
    if "() missing in" in title:
        return title.split("() missing in", 1)[0].strip()
    return title[:60].strip()


def _open_pr_addresses_finding(repo: str, finding: GuardianFinding) -> bool:
    """Return True if any open PR title or body mentions the finding signature.

    Prevents Guardian from re-filing issues for bugs that are already in a
    pull request awaiting review. Combined with the open-issue dedup, this
    means: "if a fix is in flight OR a duplicate issue exists, do not file."
    """
    signature = _finding_signature(finding)
    if not signature or len(signature) < 4:
        return False
    sig_lower = signature.lower()
    for pr in _list_open_prs(repo):
        haystack = ((pr.get("title") or "") + " \n" + (pr.get("body") or "")).lower()
        if sig_lower in haystack:
            return True
    return False


async def _create_issue_if_needed(finding: GuardianFinding, repo: str, state_dir: Path) -> bool:
    """Create a GitHub issue for a BLOCKER finding if one doesn't already exist."""
    # Check dedup registry
    issues_log = state_dir / "guardian" / "issues_created.json"
    issues_log.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, str] = {}
    if issues_log.exists():
        try:
            existing = json.loads(issues_log.read_text(encoding="utf-8"))
        except Exception:
            pass

    issue_key = f"{finding.check}:{finding.title[:80]}"
    if issue_key in existing:
        logger.debug("Issue already created for: %s", issue_key)
        return False

    remote_title = f"[GUARDIAN] {finding.title}"

    # Gate 1: open-issue duplicate check (exact title match)
    open_dupe_count = _count_open_duplicates(repo, remote_title)
    if open_dupe_count >= _MAX_OPEN_DUPLICATES:
        existing[issue_key] = "remote-open"
        issues_log.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        logger.info(
            "Guardian: skipping issue creation for '%s' (%d open duplicate(s) already, max=%d)",
            remote_title, open_dupe_count, _MAX_OPEN_DUPLICATES,
        )
        return False

    # Gate 2: open-PR awareness (skip if a fix is already in flight)
    if _open_pr_addresses_finding(repo, finding):
        existing[issue_key] = "pr-in-flight"
        issues_log.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        logger.info(
            "Guardian: skipping issue creation for '%s' (open PR addresses it)",
            remote_title,
        )
        return False

    try:
        from dharma_swarm.world_actions import github_create_issue

        body = (
            f"**Guardian Crew — Automatic BLOCKER Detection**\n\n"
            f"**Check:** `{finding.check}`\n"
            f"**File:** `{finding.file}`" + (f" (line {finding.line})" if finding.line else "") + "\n\n"
            f"**Detail:**\n{finding.detail}\n\n"
            f"**Suggested Fix:**\n{finding.fix_hint or 'See detail above.'}\n\n"
            f"---\n*Auto-generated by Guardian Crew at {datetime.now(timezone.utc).isoformat()}*"
        )
        result = github_create_issue(repo=repo, title=remote_title, body=body)
        if result.success:
            existing[issue_key] = result.url or "created"
            issues_log.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            logger.info("Guardian: created GitHub issue for '%s'", finding.title)
            return True
        else:
            logger.warning("Guardian: GitHub issue creation failed: %s", result.message)
    except Exception as exc:
        logger.debug("Issue creation failed (non-fatal): %s", exc)

    return False


async def run_guardian_cycle(
    src_root: Path | None = None,
    state_dir: Path | None = None,
    github_repo: str = "AmitabhainArunachala/dharma_swarm",
    create_issues: bool = True,
    room_registry: Any | None = None,
) -> dict[str, Any]:
    """Run one full guardian cycle: audit + loop_watch + router_probe + report.

    Returns:
        Dict with finding counts, report path, and issue creation results.
    """
    src_root = src_root or _default_src_root()
    state_dir = state_dir or dharma_state_dir()
    generated_at = datetime.now(timezone.utc).isoformat()

    logger.info("Guardian Crew: starting cycle (src=%s)", src_root)

    from dharma_swarm.fractal.room_health import run_room_health_watcher

    # Run all Guardian checks in parallel.
    (
        auditor_findings,
        loop_findings,
        router_findings,
        ledger_findings,
        warning_findings,
        consistency_findings,
        room_findings,
    ) = await asyncio.gather(
        run_auditor(src_root),
        run_loop_watcher(state_dir),
        run_router_probe(state_dir),
        run_ledger_watcher(state_dir),
        run_guardian_warning_checks(src_root, state_dir),
        run_task_consistency_guard(state_dir),
        run_room_health_watcher(room_registry),
        return_exceptions=False,
    )

    # Synthesize report
    report = synthesize_report(
        auditor_findings=auditor_findings,
        loop_findings=loop_findings,
        router_findings=router_findings,
        generated_at=generated_at,
        src_root=src_root,
        ledger_findings=ledger_findings,
        warning_findings=warning_findings,
        consistency_findings=consistency_findings,
        room_findings=room_findings,
    )

    # Write report to disk
    report_dir = state_dir / "guardian"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "GUARDIAN_REPORT.md"
    report_path.write_text(report, encoding="utf-8")

    # Create GitHub issues for BLOCKERs
    issues_created = 0
    all_findings = (
        auditor_findings
        + loop_findings
        + router_findings
        + ledger_findings
        + warning_findings
        + consistency_findings
        + room_findings
    )
    blockers = [f for f in all_findings if f.severity == "BLOCKER"]

    if create_issues and blockers:
        for finding in blockers[:5]:  # cap at 5 issues per cycle
            created = await _create_issue_if_needed(finding, github_repo, state_dir)
            if created:
                issues_created += 1

    result = {
        "generated_at": generated_at,
        "blockers": len(blockers),
        "degraded": len([f for f in all_findings if f.severity == "DEGRADED"]),
        "warnings": len([f for f in all_findings if f.severity == "WARNING"]),
        "total_findings": len(all_findings),
        "issues_created": issues_created,
        "report_path": str(report_path),
    }

    logger.info(
        "Guardian Crew cycle complete: %d blockers, %d degraded, %d warnings, %d issues created",
        result["blockers"], result["degraded"], result["warnings"], result["issues_created"],
    )
    return result


# ---------------------------------------------------------------------------
# Orchestrate_live integration
# ---------------------------------------------------------------------------

async def start_guardian_loop(
    src_root: Path | None = None,
    state_dir: Path | None = None,
    github_repo: str = "AmitabhainArunachala/dharma_swarm",
    interval_seconds: int = _GUARDIAN_INTERVAL,
    shutdown_event: asyncio.Event | None = None,
    room_registry: Any | None = None,
) -> None:
    """Run the guardian crew in a continuous loop (called from orchestrate_live).

    Runs immediately at boot, then every interval_seconds (default 4 hours).
    """
    logger.info("Guardian Crew: starting loop (interval=%ds)", interval_seconds)
    _shutdown = shutdown_event or asyncio.Event()

    async def _run_cycle_once() -> None:
        await asyncio.wait_for(
            run_guardian_cycle(src_root=src_root, state_dir=state_dir, github_repo=github_repo, room_registry=room_registry),
            timeout=300.0,
        )

    # Boot-time run
    try:
        await _run_cycle_once()
    except asyncio.TimeoutError:
        logger.warning("Guardian Crew: boot-time cycle timed out (300s)")
    except Exception as exc:
        logger.warning("Guardian Crew: boot-time cycle failed (non-fatal): %s", exc)

    # Recurring loop
    while not _shutdown.is_set():
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=float(interval_seconds))
            break
        except asyncio.TimeoutError:
            pass
        if _shutdown.is_set():
            break
        try:
            await _run_cycle_once()
        except asyncio.TimeoutError:
            logger.warning("Guardian Crew: cycle timed out (300s)")
        except Exception as exc:
            logger.warning("Guardian Crew: cycle failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    result = await run_guardian_cycle()
    print(json.dumps(result, indent=2))

    # Print the report to stdout
    report_path = Path(result["report_path"])
    if report_path.exists():
        print("\n" + report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    asyncio.run(_main())
