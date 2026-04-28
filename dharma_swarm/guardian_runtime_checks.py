"""Read-only Guardian runtime warning checks.

This module keeps repo/state warning probes out of ``guardian_crew.py`` so the
main Guardian module remains an orchestrator and report synthesizer.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GuardianRuntimeFinding:
    severity: str
    check: str
    title: str
    detail: str
    file: str = ""
    line: int = 0
    fix_hint: str = ""


_REGISTERED_DHARMA_TOP_LEVEL_DIRS = frozenset(
    {
        "a2a",
        "agent_memory",
        "agent_runs",
        "agents",
        "ai_reciprocity_ledger",
        "alerts",
        "api",
        "assurance",
        "autonomous_cleanup",
        "build_loop",
        "checkpoints",
        "constitution",
        "conversation_log",
        "conversations",
        "corpus",
        "cron",
        "dashboard",
        "db",
        "distilled",
        "env",
        "events",
        "evolution",
        "ginko",
        "graphs",
        "guardian",
        "interrupts",
        "jikoku",
        "jk",
        "logs",
        "memory",
        "merge",
        "meta",
        "models",
        "onboarding",
        "overnight",
        "pulse",
        "reading_program",
        "reflexion",
        "replication",
        "router",
        "scouts",
        "shared",
        "state",
        "stigmergy",
        "subconscious",
        "tasks",
        "telos",
        "terminal_supervisor",
        "terminal_tui",
        "trajectories",
        "verify",
        "witness",
        "workspace",
        "world_model",
    }
)


def _repo_root_from_src_root(src_root: Path) -> Path:
    if src_root.name == "dharma_swarm" and (src_root / "__init__.py").exists():
        return src_root.parent
    return src_root


async def run_guardian_warning_checks(
    src_root: Path,
    state_dir: Path,
    *,
    now: datetime | None = None,
) -> list[GuardianRuntimeFinding]:
    """Read-only warnings for stale repo reports and unregistered state dirs."""
    findings: list[GuardianRuntimeFinding] = []
    resolved_now = now or datetime.now(timezone.utc)
    repo_root = _repo_root_from_src_root(src_root)
    repo_report = repo_root / "GUARDIAN_REPORT.md"

    if repo_report.exists():
        age_seconds = resolved_now.timestamp() - repo_report.stat().st_mtime
        if age_seconds > 24 * 3600:
            age_hours = age_seconds / 3600
            findings.append(
                GuardianRuntimeFinding(
                    severity="WARNING",
                    check="GUARDIAN_WARNINGS:stale_repo_report",
                    title="Repo-root GUARDIAN_REPORT.md is stale",
                    detail=(
                        f"{repo_report} is {age_hours:.1f}h old "
                        "(threshold: 24h). Guardian output may not reflect "
                        "current repository health."
                    ),
                    file=str(repo_report),
                    fix_hint="Run a fresh Guardian cycle before relying on repo-root report state.",
                )
            )

    if state_dir.exists():
        unregistered = [
            child.name
            for child in sorted(state_dir.iterdir())
            if child.is_dir()
            and not child.name.startswith(".")
            and child.name not in _REGISTERED_DHARMA_TOP_LEVEL_DIRS
        ]
        if unregistered:
            names = ", ".join(unregistered)
            findings.append(
                GuardianRuntimeFinding(
                    severity="WARNING",
                    check="GUARDIAN_WARNINGS:unregistered_state_dir",
                    title="Unregistered top-level .dharma state directory",
                    detail=(
                        f"{state_dir} contains unregistered top-level "
                        f"directories: {names}. New state roots should be "
                        "registered before becoming durable runtime surface area."
                    ),
                    file=str(state_dir),
                    fix_hint=(
                        "Either route writes through an existing registered state "
                        "directory or add the directory to Guardian's registered "
                        ".dharma top-level set with tests."
                    ),
                )
            )

    return findings


def runtime_context_bundle_injection_findings(
    db: sqlite3.Connection,
    since_iso: str,
    *,
    limit: int = 20,
) -> list[tuple[str, list[str]]]:
    """Return recent context bundles whose rendered text looks injectable."""
    existing = {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "context_bundles" not in existing:
        return []
    columns = {
        str(row[1])
        for row in db.execute("PRAGMA table_info(context_bundles)").fetchall()
    }
    if not {"bundle_id", "rendered_text", "created_at"} <= columns:
        return []

    try:
        from dharma_swarm.injection_scanner import scan_content
    except Exception:
        logger.debug("Injection scanner unavailable for context bundle audit", exc_info=True)
        return []

    rows = db.execute(
        "SELECT bundle_id, rendered_text, metadata_json FROM context_bundles "
        "WHERE created_at >= ? ORDER BY created_at DESC LIMIT ?",
        (since_iso, int(limit)),
    ).fetchall()
    findings: list[tuple[str, list[str]]] = []
    for bundle_id, rendered_text, metadata_json in rows:
        metadata = _json_load(metadata_json, {})
        context_scan = metadata.get("context_scan")
        if isinstance(context_scan, dict) and context_scan.get("status") == "blocked":
            scan_findings = context_scan.get("findings")
            findings.append(
                (
                    str(bundle_id),
                    [str(item) for item in scan_findings]
                    if isinstance(scan_findings, list)
                    else ["blocked"],
                )
            )
            continue
        result = scan_content(
            str(rendered_text or ""),
            f"context_bundle:{bundle_id}",
        )
        if not result.is_clean:
            findings.append((str(bundle_id), list(result.findings)))
    return findings


def runtime_rows_missing_context(
    db: sqlite3.Connection,
    table: str,
    timestamp_column: str,
    since_iso: str,
) -> int:
    """Count recent task/run rows with no matching context bundle."""
    existing = _runtime_table_names(db)
    if table not in existing or "context_bundles" not in existing:
        return 0
    if timestamp_column not in _runtime_table_columns(db, table):
        return 0

    metadata_bundle = (
        "CASE WHEN json_valid(t.metadata_json) "
        "THEN COALESCE(json_extract(t.metadata_json, '$.context_bundle_id'), '') "
        "ELSE '' END"
    )
    if table == "delegation_runs":
        join_clause = (
            f"cb.bundle_id = {metadata_bundle} "
            "OR (t.run_id != '' AND cb.run_id = t.run_id) "
            "OR (t.session_id != '' AND t.task_id != '' "
            "AND cb.session_id = t.session_id AND cb.task_id = t.task_id)"
        )
    elif table == "task_claims":
        join_clause = (
            f"cb.bundle_id = {metadata_bundle} "
            "OR (t.session_id != '' AND t.task_id != '' "
            "AND cb.session_id = t.session_id AND cb.task_id = t.task_id)"
        )
    else:
        return 0

    row = db.execute(
        f"SELECT COUNT(*) FROM {table} t "
        f"LEFT JOIN context_bundles cb ON {join_clause} "
        f"WHERE t.{timestamp_column} >= ? "
        "AND t.status IN ('claimed', 'running', 'completed', 'failed') "
        "AND cb.bundle_id IS NULL",
        (since_iso,),
    ).fetchone()
    return int(row[0] if row else 0)


def runtime_context_status_counts(
    db: sqlite3.Connection,
    since_iso: str,
) -> dict[str, int]:
    """Count recent lifecycle rows whose context bundle status is unhealthy."""
    unhealthy = {"failed", "missing_runtime_state", "missing_task"}
    counts: dict[str, int] = {}
    for table, timestamp_column in (
        ("task_claims", "claimed_at"),
        ("delegation_runs", "started_at"),
    ):
        if table not in _runtime_table_names(db):
            continue
        columns = _runtime_table_columns(db, table)
        if timestamp_column not in columns or "metadata_json" not in columns:
            continue
        rows = db.execute(
            f"SELECT metadata_json FROM {table} WHERE {timestamp_column} >= ?",
            (since_iso,),
        ).fetchall()
        for (metadata_json,) in rows:
            metadata = _json_load(metadata_json, {})
            if not isinstance(metadata, dict):
                continue
            status = str(metadata.get("context_bundle_status") or "")
            if status in unhealthy:
                counts[status] = counts.get(status, 0) + 1
    return counts


def _runtime_table_names(db: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


def _runtime_table_columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in db.execute(f"PRAGMA table_info({table})").fetchall()}


def _json_load(raw: object, default: object) -> object:
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except Exception:
            return default
    return default
