"""Read-only cybernetics_codex steward projection.

This module is the first bounded incarnation of the persistent
``cybernetics_codex`` role. It does not dispatch work, call providers, mutate
runtime state, weaken gates, or write archive fitness. It projects existing
owners into a closure-ledger packet a fresh agent can verify.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.archive import read_one_wire_fitness_authority
from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.loop_closure_quarantine import (
    LIVE_ROW_PREDICATE,
    has_quarantine_columns,
    quarantined_failure_counts,
)

try:  # pragma: no cover - exercised by repo runtime; tests run with PyYAML.
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_DIR = dharma_state_dir()

AGENT_ID = "cybernetics_codex"
CALLSIGN = "cybernetics-codex"
SCHEMA_VERSION = "cybernetics_codex.audit.v3"
LOOP1_BOUNDED_REPLAY_GLOB = "reports/loop_closure/cybernetics_codex/*loop1*_spine_dispatch.json"
# General per-loop closure receipts for the cascade (loops 2..11). Each proves
# its OWN sense->interpret->constrain->act->adapt cycle on real data, mirroring
# the Loop 1 bounded-replay pattern but loop-agnostic. The audit VERIFIES the
# structural evidence (see _evaluate_loop_closure_replay); it never trusts a
# bare "closed" boolean carried by the receipt itself.
LOOP_CLOSURE_REPLAY_GLOB = "reports/loop_closure/cybernetics_codex/*loop{number}_*closure.json"
LOOP_CLOSURE_TRANSITIONS = ("sense", "interpret", "constrain", "act", "adapt")
REPO_AGENT_HOME = Path("docs/agents/cybernetics_codex")
SEED_FILE = REPO_AGENT_HOME / "agent.seed.yaml"
SOUL_FILE = REPO_AGENT_HOME / "SOUL.md"
CONTEXT_ENGINEERING_FILE = REPO_AGENT_HOME / "CONTEXT_ENGINEERING.md"
A2A_INBOX_ROUTE = "agent-inbox"
NATS_SUBJECT = "dharma.agent.cybernetics_codex.inbox"

OWNED_SURFACES = [
    "docs/ops/CYBERNETICS_CODEX.md",
    "docs/agents/cybernetics_codex/**",
    "dharma_swarm/cybernetics_codex.py",
    "scripts/governance/cybernetics_codex_audit.py",
    "scripts/governance/register_cybernetics_codex.py",
    "tests/test_cybernetics_codex.py",
    "reports/loop_closure/cybernetics_codex/**",
    "/Users/dhyana/cybernetics_codex_note.md",
]

FORBIDDEN_ACTIONS = [
    "read or write provider secrets outside the declared key owner",
    "spend money or touch live external accounts",
    "weaken AHIMSA/SATYA/telos gates",
    "mutate archive fitness or mark One Wire quorum as satisfied",
    "dispatch agents or tasks without an explicit operator/build warrant",
    "claim production closure from smoke tests, demos, or prose handoffs",
    "edit hot-path files without an active track warrant and independent review",
]

VERIFIER_COMMANDS = [
    "make onboard",
    "make orient",
    ".venv/bin/dgc status",
    ".venv/bin/dgc loop-status",
    "bash scripts/runtime/codex_toolbelt_status.sh",
    "python3 scripts/governance/cybernetics_codex_audit.py --json",
    "python3 scripts/governance/register_cybernetics_codex.py --dry-run",
    "pytest -q tests/test_cybernetics_codex.py tests/test_manifest_health.py",
]

SERVED_PROVIDER_KEYS = ("actual_served_provider", "served_provider", "provider")
SERVED_MODEL_KEYS = ("actual_served_model", "served_model", "model")
NON_PROVIDER_VALUES = {"", "none", "null", "unknown", "orchestrator"}
SQLITE_IN_CHUNK_SIZE = 500

LOOPS = [
    (1, "swarm_task_loop", "Swarm Task Loop"),
    (2, "organism_heartbeat", "Organism Heartbeat"),
    (3, "evolution_loop", "Evolution Loop / DarwinEngine"),
    (4, "consolidation_memory", "Consolidation Loop / Memory"),
    (5, "zeitgeist_scanner", "Zeitgeist Scanner"),
    (6, "witness_auditor", "Witness Auditor"),
    (7, "training_flywheel", "Training Flywheel"),
    (8, "recognition_eigenform", "Recognition Loop / eigenform"),
    (9, "conductors", "Conductors"),
    (10, "context_agent", "Context Agent"),
    (11, "replication_monitor", "Replication Monitor"),
    (12, "self_improvement", "Self-Improvement"),
    (13, "free_evolution_grind", "Free Evolution Grind"),
]

VERDICT_TIERS = {
    "HARNESS_PROVEN": (
        "A bounded replay/regression harness proves the loop can execute "
        "sense -> interpret -> constrain -> act -> adapt, but the evidence may "
        "be scratch or manufactured by the harness and is not production-live "
        "closure."
    ),
    "CLOSED_LIVE": (
        "The loop is proven from its declared live owner surface, with no "
        "scratch-only or self-seeded evidence standing in for production state."
    ),
}

LIVE_OWNER_SURFACE_CRITERIA = {
    1: (
        "runtime.delegation_runs/runtime_receipts in the audited daemon scope "
        "show real completed provider work, zero dispatch_dropoff, and a later "
        "routing/adaptation read caused by that work"
    ),
    2: (
        "standing organism pulse/algedonic owner surface shows a non-scratch "
        "daemon cycle whose adaptive state is consumed by a later daemon cycle"
    ),
    3: (
        "live DarwinEngine/evolution archive owner surface shows a governed "
        "non-scratch proposal outcome consumed by a later predictor/archive "
        "selection without internal fitness contamination"
    ),
    4: (
        "live memory owner surface shows external/completed work, not the "
        "closure script itself, consolidated and consumed by later context"
    ),
    5: (
        "live zeitgeist/environment owner surface shows non-synthetic external "
        "signals changing a later gate/priority decision"
    ),
    6: (
        "live witness/runtime receipt owner surface shows production completions "
        "audited and governance marks consumed by downstream routing"
    ),
    7: (
        "live trajectory owner surface contains non-synthetic recent trajectories "
        "that the flywheel scores and persists into later strategy selection"
    ),
    8: (
        "live recognition/context owner surface shows non-scratch loop-history "
        "receipts generating a seed later consumed by an agent context build"
    ),
    9: (
        "live conductor/cron owner surface shows production scheduler state "
        "changed by observed signals and suppressing/altering a later tick"
    ),
    10: (
        "live context-package owner surface shows production memory inputs "
        "changing a served context package later read by an agent"
    ),
    11: (
        "live replication owner surface shows a real proposal materialized into "
        "roster/probation state and observed by a later monitor cycle"
    ),
    12: "One Wire quorum N>=5, M>=3, and explicit archive-fitness authority",
    13: "One Wire quorum N>=5, M>=3, and explicit archive-fitness authority",
}


def build_audit(
    *,
    repo_root: Path | str = REPO_ROOT,
    state_dir: Path | str = DEFAULT_STATE_DIR,
    runtime_db: Path | str | None = None,
    since: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a read-only cybernetic closure-ledger packet."""
    repo = Path(repo_root)
    state = Path(state_dir)
    db_path = Path(runtime_db) if runtime_db else state / "state" / "runtime.db"
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    runtime = read_runtime_summary(db_path, since=since)
    one_wire = read_one_wire_summary(state)
    archive = read_archive_summary(state)
    manifest = read_manifest_registration(repo)
    active_track = read_active_track_summary(repo)
    seed = read_seed_summary(repo)
    live_registration = read_live_registration_summary(state)
    bounded_replays = read_bounded_replays_summary(repo)
    bounded_replays.update(read_loop_closure_replays(repo))

    return {
        "schema_version": SCHEMA_VERSION,
        "agent": {
            "id": AGENT_ID,
            "callsign": CALLSIGN,
            "label": "Cybernetics Codex Steward",
            "mode": "read_only_verifier",
            "vsm_role": "S3*/S5 steward for cybernetic closure claims",
            "repo_agent_home": str(repo / REPO_AGENT_HOME),
            "owned_surfaces": OWNED_SURFACES,
            "forbidden_actions": FORBIDDEN_ACTIONS,
        },
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "repo_root": str(repo),
        "state_dir": str(state),
        "manifest_registration": manifest,
        "active_track": active_track,
        "seed_registration": seed,
        "live_registration": live_registration,
        "runtime": runtime,
        "bounded_replays": bounded_replays,
        "one_wire": one_wire,
        "evolution_archive": archive,
        "loop_statuses": build_loop_statuses(
            runtime,
            one_wire,
            archive,
            bounded_replays=bounded_replays,
        ),
        "verdict_tiers": VERDICT_TIERS,
        "live_owner_surface_criteria": {
            f"loop{number}": criterion
            for number, criterion in LIVE_OWNER_SURFACE_CRITERIA.items()
        },
        "verifier_commands": VERIFIER_COMMANDS,
        "closure_rule": (
            "A production-live loop is closed only when sense -> interpret -> "
            "constrain -> act -> adapt all fire on live owner-surface data, "
            "every transition emits a receipt to that owner surface, and a "
            "fresh agent can replay an automated check. Scratch or self-seeded "
            "bounded replays are HARNESS_PROVEN, not CLOSED_LIVE."
        ),
        "loop1_acceptance_rule": (
            "A2A-surface rows may legitimately leave delegation_runs.receipt_json "
            "empty; the production truth this audit requires is actual served "
            "provider/model on delegation metadata or runtime_receipts, with no "
            "dispatch_dropoff in the audited scope."
        ),
        "next_build_packet": [
            "Keep Loop 1 bounded replay green; drain or quarantine historical dispatch_dropoff rows (scripts/runtime/dispatch_dropoff_quarantine.py, receipted) before any standing all-history daemon-clean claim.",
            "Promote HARNESS_PROVEN loops to CLOSED_LIVE only after one live-owner-surface criterion passes per loop.",
            "Add an audit mode that can re-execute replay commands or record why re-execution was skipped.",
            "Add One Wire archive-fitness guard tests before enabling Loops 12/13.",
            "Regenerate the loop map from a live projection instead of hand-editing stale prose.",
        ],
    }

def read_runtime_summary(db_path: Path, *, since: str | None = None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": str(db_path),
        "exists": db_path.exists(),
        "read_ok": False,
        "scope": {"since": since},
        "tables": {},
        "delegation_runs": {},
        "failure_codes": [],
        "quarantine": {},
        "receipt_json": {},
        "provider_truth": {},
    }
    if not db_path.exists():
        summary["error"] = "runtime DB missing"
        return summary

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        summary["error"] = f"open failed: {type(exc).__name__}: {exc}"
        return summary

    try:
        summary["read_ok"] = True
        for table in (
            "delegation_runs",
            "runtime_receipts",
            "routing_decisions",
            "provider_attempts",
            "model_routing_outcomes",
            "external_outcomes",
        ):
            summary["tables"][table] = _table_summary(conn, table)

        if _table_exists(conn, "delegation_runs"):
            where_sql, where_args = _time_scope_sql(
                conn,
                "delegation_runs",
                "coalesce(completed_at, started_at)",
                since,
            )
            row = conn.execute(
                f"""
                select
                  count(*) as total,
                  sum(status='completed') as completed,
                  sum(status='failed') as failed,
                  sum(status='running') as running,
                  sum(status='claimed') as claimed,
                  min(started_at) as first_started,
                  max(coalesce(completed_at, started_at)) as last_seen
                from delegation_runs
                {where_sql}
                """
                ,
                where_args,
            ).fetchone()
            summary["delegation_runs"] = dict(row or {})
            # Live failure counts EXCLUDE quarantined-historical rows (marker
            # columns owned by loop_closure_quarantine — no new store) while the
            # quarantined tally is reported SEPARATELY below, never hidden.
            quarantine_supported = has_quarantine_columns(conn)
            live_failed = "status='failed'"
            if quarantine_supported:
                live_failed = f"{live_failed} and {LIVE_ROW_PREDICATE}"
            summary["failure_codes"] = [
                dict(r)
                for r in conn.execute(
                    f"""
                    select
                      failure_code,
                      count(*) as count,
                      max(coalesce(completed_at, started_at)) as last_seen
                    from delegation_runs
                    {_and_where(where_sql, live_failed)}
                    group by failure_code
                    order by count desc
                    limit 12
                    """,
                    where_args,
                ).fetchall()
            ]
            quarantined_codes = quarantined_failure_counts(conn, where_sql, where_args)
            summary["quarantine"] = {
                "supported": quarantine_supported,
                "failure_codes_quarantined": quarantined_codes,
                "failed_rows_quarantined": sum(
                    int(r.get("count") or 0) for r in quarantined_codes
                ),
                "dispatch_dropoff_quarantined": next(
                    (
                        int(r.get("count") or 0)
                        for r in quarantined_codes
                        if str(r.get("failure_code")) == "dispatch_dropoff"
                    ),
                    0,
                ),
            }
            if _column_exists(conn, "delegation_runs", "receipt_json"):
                receipt_row = conn.execute(
                    f"""
                    select
                      count(*) as total,
                      sum(receipt_json is not null and length(receipt_json)>2) as rows_with_receipt_json,
                      max(case
                        when receipt_json is not null and length(receipt_json)>2
                        then coalesce(completed_at, started_at)
                      end) as latest_receipt_run
                    from delegation_runs
                    {where_sql}
                    """,
                    where_args,
                ).fetchone()
                summary["receipt_json"] = dict(receipt_row or {})
            else:
                summary["receipt_json"] = {
                    "total": int(summary["delegation_runs"].get("total") or 0),
                    "rows_with_receipt_json": 0,
                    "latest_receipt_run": None,
                    "surface": "missing_column",
                }
            summary["receipt_json"]["surface"] = "orchestrator"
            summary["receipt_json"]["a2a_empty_is_success"] = True

        summary["provider_truth"] = _served_provider_truth_summary(conn, since=since)
    except sqlite3.Error as exc:
        summary["read_ok"] = False
        summary["error"] = f"query failed: {type(exc).__name__}: {exc}"
    finally:
        conn.close()
    return summary


def read_bounded_replays_summary(repo_root: Path) -> dict[str, Any]:
    """Read bounded replay proof reports owned by the Cybernetics Codex lane."""
    out: dict[str, Any] = {
        "loop1": {
            "exists": False,
            "closed": False,
            "path": None,
            "blocker": "no bounded Loop 1 replay report found",
        }
    }
    reports = sorted(
        repo_root.glob(LOOP1_BOUNDED_REPLAY_GLOB),
        key=lambda path: path.stat().st_mtime if path.exists() else 0.0,
        reverse=True,
    )
    if not reports:
        return out

    report_path = reports[0]
    loop1 = out["loop1"]
    loop1["exists"] = True
    loop1["path"] = str(report_path)
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        loop1["blocker"] = f"bounded replay report unreadable: {type(exc).__name__}: {exc}"
        return out

    served_truth = data.get("served_provider_truth") or {}
    evidence_receipts = data.get("evidence_receipts") or {}
    tasks_requested = int(data.get("tasks_requested") or 0)
    tasks_completed = int(data.get("tasks_completed") or 0)
    dispatch_dropoffs = int(data.get("dispatch_dropoffs") or 0)
    tick_errors = data.get("tick_errors") or []
    completed_with_truth = int(served_truth.get("completed_runs_with_truth") or 0)
    receipt_truth = int(served_truth.get("delegation_receipts_with_truth") or 0)
    receipt_statuses = [str(status) for status in evidence_receipts.values()]
    closed = (
        tasks_requested > 0
        and tasks_completed == tasks_requested
        and dispatch_dropoffs == 0
        and not tick_errors
        and bool(receipt_statuses)
        and all(status == "ok" for status in receipt_statuses)
        and completed_with_truth >= tasks_completed
    )
    loop1.update(
        {
            "closed": closed,
            "harness_proven": closed,
            "closed_live": False,
            "tasks_requested": tasks_requested,
            "tasks_completed": tasks_completed,
            "tasks_failed": int(data.get("tasks_failed") or 0),
            "dispatch_dropoffs": dispatch_dropoffs,
            "tick_errors": len(tick_errors),
            "evidence_receipts": len(receipt_statuses),
            "evidence_receipts_ok": sum(1 for status in receipt_statuses if status == "ok"),
            "completed_runs_with_truth": completed_with_truth,
            "delegation_receipts_with_truth": receipt_truth,
            "served_provider_sample": served_truth.get("sample"),
            "state_dir": data.get("state_dir"),
            "provider": data.get("provider"),
            "model": data.get("model"),
            "spine_dispatch": data.get("spine_dispatch"),
            "read_only_boot": data.get("read_only_boot"),
            "ollama_force_local": data.get("ollama_force_local"),
            "blocker": "" if closed else "bounded replay did not satisfy strict Loop 1 closure predicate",
        }
    )
    return out


def _evaluate_loop_closure_replay(data: dict[str, Any]) -> dict[str, Any]:
    """Honest, loop-agnostic harness criterion for a cascade loop's replay.

    Harness-proven only when the receipt proves, structurally, that the loop ran
    the full cybernetic cycle on bounded replay data:
      - cycles ran on real data (cycles > 0 and real_data true),
      - every sense/interpret/constrain/act/adapt transition emitted a receipt,
      - the adapt transition produced a real before != after change that fed the
        next cycle (adapt_proof.fed_forward true), and
      - no tick errors.
    The boolean is COMPUTED here from the evidence; a receipt's own "closed" field
    is never trusted (FORBIDDEN_ACTIONS: claim closure from smoke tests/prose).
    It still does not imply CLOSED_LIVE; live closure requires the declared owner
    surface criterion for that loop.
    """
    transitions = data.get("transitions_receipted") or {}
    adapt = data.get("adapt_proof") or {}
    cycles = int(data.get("cycles") or 0)
    tick_errors = data.get("tick_errors") or []
    transitions_ok = all(bool(transitions.get(t)) for t in LOOP_CLOSURE_TRANSITIONS)
    adapt_real = (
        bool(adapt)
        and bool(adapt.get("fed_forward"))
        and adapt.get("before") != adapt.get("after")
    )
    harness_proven = (
        cycles > 0
        and bool(data.get("real_data"))
        and transitions_ok
        and adapt_real
        and not tick_errors
    )
    return {
        "exists": True,
        "closed": harness_proven,
        "harness_proven": harness_proven,
        "closed_live": False,
        "cycles": cycles,
        "transitions_ok": transitions_ok,
        "adapt_real": adapt_real,
        "tick_errors": len(tick_errors),
        "adapt_proof": adapt or None,
        "blocker": (
            "" if harness_proven
            else "general loop closure replay did not satisfy the strict cascade criterion"
        ),
    }


def read_loop_closure_replays(repo_root: Path) -> dict[str, Any]:
    """Project per-loop (2..11) closure replays from the loop-closure surface.

    Mirrors read_bounded_replays_summary but loop-agnostic. Loops with no receipt
    return exists=False/closed=False, so the audit's existing PARTIAL logic still
    governs them — this only ever ADDS a CLOSED verdict for a loop that ships a
    strict, structurally-verified replay.
    """
    out: dict[str, Any] = {}
    for number, loop_id, _label in LOOPS:
        if number in (1, 12, 13):
            continue
        key = f"loop{number}"
        glob = LOOP_CLOSURE_REPLAY_GLOB.format(number=number)
        reports = sorted(
            repo_root.glob(glob),
            key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
            reverse=True,
        )
        if not reports:
            out[key] = {
                "exists": False,
                "closed": False,
                "path": None,
                "blocker": f"no bounded closure replay report found for loop {number}",
            }
            continue
        path = reports[0]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            out[key] = {
                "exists": True,
                "closed": False,
                "path": str(path),
                "blocker": f"closure replay unreadable: {type(exc).__name__}: {exc}",
            }
            continue
        evaluated = _evaluate_loop_closure_replay(data)
        evaluated["path"] = str(path)
        evaluated["loop_id"] = data.get("loop_id") or loop_id
        out[key] = evaluated
    return out


def _served_provider_truth_summary(
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
) -> dict[str, Any]:
    truth_run_ids: set[str] = set()
    truth_run_timestamps: dict[str, str] = {}
    completed_run_ids: set[str] = set()
    out: dict[str, Any] = {
        "definition": (
            "Counts rows carrying actual served provider/model truth. "
            "A2A runtime_receipts are canonical even when receipt_json is empty."
        ),
        "delegation_runs": {
            "total": 0,
            "completed": 0,
            "rows_with_served_provider_model": 0,
            "completed_with_served_provider_model": 0,
            "latest_truth_run": None,
            "sample": None,
        },
        "runtime_receipts": {
            "total": 0,
            "rows_with_served_provider_model": 0,
            "completed_rows_with_served_provider_model": 0,
            "unique_runs_with_served_provider_model": 0,
            "unique_completed_runs_with_served_provider_model": 0,
            "latest_truth_receipt": None,
            "latest_completed_truth_receipt": None,
            "sample": None,
            "completed_sample": None,
        },
    }

    if _table_exists(conn, "delegation_runs"):
        columns = _table_columns(conn, "delegation_runs")
        select_cols = [
            "run_id",
            "status",
            "coalesce(completed_at, started_at) as observed_at",
        ]
        if "metadata_json" in columns:
            select_cols.append("metadata_json")
        else:
            select_cols.append("'{}' as metadata_json")
        if "receipt_json" in columns:
            select_cols.append("receipt_json")
        else:
            select_cols.append("null as receipt_json")
        where_sql, where_args = _time_scope_sql(
            conn,
            "delegation_runs",
            "coalesce(completed_at, started_at)",
            since,
        )
        for row in conn.execute(
            f"select {', '.join(select_cols)} from delegation_runs {where_sql}",
            where_args,
        ):
            out["delegation_runs"]["total"] += 1
            status = str(row["status"] or "")
            if status == "completed":
                out["delegation_runs"]["completed"] += 1
                if row["run_id"]:
                    completed_run_ids.add(str(row["run_id"]))
            truth = (
                _extract_served_provider_truth(_loads_json(row["metadata_json"]))
                or _extract_served_provider_truth(_loads_json(row["receipt_json"]))
            )
            if truth:
                out["delegation_runs"]["rows_with_served_provider_model"] += 1
                if status == "completed":
                    out["delegation_runs"]["completed_with_served_provider_model"] += 1
                    if row["run_id"]:
                        run_id = str(row["run_id"])
                        truth_run_ids.add(run_id)
                        _record_truth_timestamp(
                            truth_run_timestamps,
                            run_id=run_id,
                            observed_at=row["observed_at"],
                        )
                observed_at = row["observed_at"]
                if (
                    observed_at
                    and (
                        out["delegation_runs"]["latest_truth_run"] is None
                        or str(observed_at) > str(out["delegation_runs"]["latest_truth_run"])
                    )
                ):
                    out["delegation_runs"]["latest_truth_run"] = observed_at
                    out["delegation_runs"]["sample"] = {
                        "run_id": row["run_id"],
                        **truth,
                    }

    if _table_exists(conn, "runtime_receipts"):
        columns = _table_columns(conn, "runtime_receipts")
        select_cols = ["receipt_id"]
        select_cols.append("run_id" if "run_id" in columns else "'' as run_id")
        select_cols.append("created_at" if "created_at" in columns else "null as created_at")
        select_cols.append("payload_json" if "payload_json" in columns else "'{}' as payload_json")
        where_sql, where_args = _time_scope_sql(conn, "runtime_receipts", "created_at", since)
        truth_runs: set[str] = set()
        completed_truth_runs: set[str] = set()
        for row in conn.execute(
            f"select {', '.join(select_cols)} from runtime_receipts {where_sql}",
            where_args,
        ):
            out["runtime_receipts"]["total"] += 1
            truth = _extract_served_provider_truth(_loads_json(row["payload_json"]))
            if not truth:
                continue
            out["runtime_receipts"]["rows_with_served_provider_model"] += 1
            if row["run_id"]:
                run_id = str(row["run_id"])
                truth_runs.add(run_id)
                if run_id in completed_run_ids:
                    completed_truth_runs.add(run_id)
                    out["runtime_receipts"]["completed_rows_with_served_provider_model"] += 1
                    _record_truth_timestamp(
                        truth_run_timestamps,
                        run_id=run_id,
                        observed_at=row["created_at"],
                    )
            observed_at = row["created_at"]
            if (
                observed_at
                and (
                    out["runtime_receipts"]["latest_truth_receipt"] is None
                    or str(observed_at) > str(out["runtime_receipts"]["latest_truth_receipt"])
                )
            ):
                out["runtime_receipts"]["latest_truth_receipt"] = observed_at
                out["runtime_receipts"]["sample"] = {
                    "receipt_id": row["receipt_id"],
                    "run_id": row["run_id"],
                    **truth,
                }
            if row["run_id"] and str(row["run_id"]) in completed_run_ids:
                if (
                    observed_at
                    and (
                        out["runtime_receipts"]["latest_completed_truth_receipt"] is None
                        or str(observed_at) > str(
                            out["runtime_receipts"]["latest_completed_truth_receipt"]
                        )
                    )
                ):
                    out["runtime_receipts"]["latest_completed_truth_receipt"] = observed_at
                    out["runtime_receipts"]["completed_sample"] = {
                        "receipt_id": row["receipt_id"],
                        "run_id": row["run_id"],
                        **truth,
                    }
        out["runtime_receipts"]["unique_runs_with_served_provider_model"] = len(truth_runs)
        out["runtime_receipts"]["unique_completed_runs_with_served_provider_model"] = len(
            completed_truth_runs
        )
        truth_run_ids.update(completed_truth_runs)

    latest_truth = max(
        (
            str(value)
            for value in (
                out["delegation_runs"]["latest_truth_run"],
                out["runtime_receipts"]["latest_completed_truth_receipt"],
            )
            if value
        ),
        default=None,
    )
    out["routing_adaptation"] = _routing_adaptation_after_truth_summary(
        conn,
        latest_truth=latest_truth,
        truth_run_ids=truth_run_ids,
        truth_timestamps_by_run_id=truth_run_timestamps,
    )
    return out


def _record_truth_timestamp(
    timestamps: dict[str, str],
    *,
    run_id: str,
    observed_at: Any,
) -> None:
    if not run_id or not observed_at:
        return
    observed = str(observed_at)
    previous = timestamps.get(run_id)
    if previous is None or observed > previous:
        timestamps[run_id] = observed


def _timestamp_column(conn: sqlite3.Connection, table: str) -> str | None:
    columns = _table_columns(conn, table)
    for column in ("created_at", "updated_at", "recorded_at", "completed_at", "started_at"):
        if column in columns:
            return column
    return None


def _routing_adaptation_after_truth_summary(
    conn: sqlite3.Connection,
    *,
    latest_truth: str | None,
    truth_run_ids: set[str],
    truth_timestamps_by_run_id: dict[str, str] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "latest_served_truth": latest_truth,
        "truth_run_ids_sample": sorted(truth_run_ids)[:20],
        "truth_run_timestamps_sample": dict(
            sorted((truth_timestamps_by_run_id or {}).items())[:20]
        ),
        "has_later_causal_read": False,
        "tables": {},
    }
    for table in ("routing_decisions", "model_routing_outcomes", "external_outcomes"):
        if not _table_exists(conn, table):
            out["tables"][table] = {
                "exists": False,
                "rows": 0,
                "rows_after_served_truth": 0,
                "correlated_rows_after_served_truth": 0,
            }
            continue
        timestamp_column = _timestamp_column(conn, table)
        rows = int(conn.execute(f"select count(*) from {table}").fetchone()[0] or 0)
        latest = (
            conn.execute(f"select max({timestamp_column}) from {table}").fetchone()[0]
            if timestamp_column
            else None
        )
        rows_after_truth = 0
        correlated_after_truth = 0
        if latest_truth and timestamp_column:
            rows_after_truth = int(
                conn.execute(
                    f"select count(*) from {table} where {timestamp_column} > ?",
                    (latest_truth,),
                ).fetchone()[0]
                or 0
            )
            columns = _table_columns(conn, table)
            if "run_id" in columns and truth_run_ids:
                correlated_after_truth = _count_correlated_rows_after_truth(
                    conn,
                    table=table,
                    timestamp_column=timestamp_column,
                    latest_truth=latest_truth,
                    truth_run_ids=truth_run_ids,
                    truth_timestamps_by_run_id=truth_timestamps_by_run_id,
                )
        out["tables"][table] = {
            "exists": True,
            "rows": rows,
            "timestamp_column": timestamp_column,
            "latest": latest,
            "rows_after_served_truth": rows_after_truth,
            "correlated_rows_after_served_truth": correlated_after_truth,
        }
        if correlated_after_truth > 0:
            out["has_later_causal_read"] = True
    return out


def _count_correlated_rows_after_truth(
    conn: sqlite3.Connection,
    *,
    table: str,
    timestamp_column: str,
    latest_truth: str,
    truth_run_ids: set[str],
    truth_timestamps_by_run_id: dict[str, str] | None = None,
) -> int:
    if truth_timestamps_by_run_id:
        total = 0
        for run_id, served_truth_at in truth_timestamps_by_run_id.items():
            if run_id not in truth_run_ids:
                continue
            total += int(
                conn.execute(
                    (
                        f"select count(*) from {table} "
                        f"where {timestamp_column} > ? and run_id = ?"
                    ),
                    (served_truth_at, run_id),
                ).fetchone()[0]
                or 0
            )
        return total

    total = 0
    ordered = sorted(truth_run_ids)
    for offset in range(0, len(ordered), SQLITE_IN_CHUNK_SIZE):
        chunk = ordered[offset : offset + SQLITE_IN_CHUNK_SIZE]
        placeholders = ",".join("?" for _ in chunk)
        total += int(
            conn.execute(
                (
                    f"select count(*) from {table} "
                    f"where {timestamp_column} > ? and run_id in ({placeholders})"
                ),
                (latest_truth, *chunk),
            ).fetchone()[0]
            or 0
        )
    return total


def read_one_wire_summary(state_dir: Path) -> dict[str, Any]:
    authority = read_one_wire_fitness_authority(state_dir)
    out: dict[str, Any] = {
        "guardian_receipt": str(authority.receipt_path),
        "exists": authority.exists,
        "required_confirmed": authority.required_confirmed,
        "required_domains": authority.required_domains,
        "confirmed": authority.confirmed,
        "domains": authority.domains,
        "eligible": authority.allowed,
        "eligible_to_set_archive_fitness": authority.eligible_to_set_archive_fitness,
        "fitness_authority_granted": authority.fitness_authority_granted,
        "archive_fitness_changed": authority.archive_fitness_changed,
    }
    if authority.blocker:
        out["blocker"] = authority.blocker
    if not authority.exists:
        return out
    try:
        payload = json.loads(authority.receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        out["blocker"] = f"guardian receipt unreadable: {type(exc).__name__}"
        return out

    if not isinstance(payload, dict):
        return out
    out["payload_keys"] = sorted(payload)[:20]
    threshold = payload.get("threshold_guard") if isinstance(payload, dict) else {}
    if isinstance(threshold, dict):
        out["observed_domains"] = threshold.get("observed_domains", [])
    return out


def read_archive_summary(state_dir: Path) -> dict[str, Any]:
    path = state_dir / "evolution" / "archive.jsonl"
    out: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "entries": 0,
        "positive_internal_fitness_risk": 0,
        "external_authority_markers": 0,
        "latest_timestamp": None,
    }
    if not path.exists():
        return out

    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                out["entries"] += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = _first_present(row, ("timestamp", "created_at", "completed_at", "updated_at"))
                if ts and (out["latest_timestamp"] is None or str(ts) > str(out["latest_timestamp"])):
                    out["latest_timestamp"] = ts
                if _has_positive_internal_fitness(row):
                    out["positive_internal_fitness_risk"] += 1
                if _has_external_authority_marker(row):
                    out["external_authority_markers"] += 1
    except OSError as exc:
        out["error"] = f"archive unreadable: {type(exc).__name__}: {exc}"
    return out


def read_manifest_registration(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "ACTIVE_SURFACE_MANIFEST.yaml"
    out: dict[str, Any] = {"path": str(path), "exists": path.exists(), "registered": False}
    data = _read_yaml(path)
    if not isinstance(data, dict):
        return out
    for agent in data.get("agents") or []:
        if isinstance(agent, dict) and agent.get("id") == AGENT_ID:
            out.update({
                "registered": True,
                "status": agent.get("status"),
                "module": agent.get("module"),
                "health_check_ids": agent.get("health_check_ids") or [],
                "priority": agent.get("priority"),
            })
            break
    return out


def read_active_track_summary(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "docs" / "governance" / "ACTIVE_TRACK.yaml"
    out: dict[str, Any] = {"path": str(path), "exists": path.exists(), "loop_track_found": False}
    data = _read_yaml(path)
    if not isinstance(data, dict):
        return out
    for track in data.get("active_tracks") or []:
        if isinstance(track, dict) and track.get("id") == "loop-closure-2026-06":
            criteria = [
                c.get("id")
                for c in track.get("completion_criteria") or []
                if isinstance(c, dict)
            ]
            out.update({
                "loop_track_found": True,
                "status": track.get("status"),
                "owned_surfaces": track.get("owned_surfaces") or [],
                "cybernetics_codex_criteria": [
                    c for c in criteria if str(c).startswith("cybernetics_codex")
                ],
            })
            break
    return out


def read_seed_summary(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SEED_FILE
    required = {
        "seed": path,
        "soul": repo_root / SOUL_FILE,
        "memory": repo_root / REPO_AGENT_HOME / "MEMORY.md",
        "protocols": repo_root / REPO_AGENT_HOME / "PROTOCOLS.md",
        "wake_context": repo_root / REPO_AGENT_HOME / "WAKE_CONTEXT.md",
        "context_engineering": repo_root / CONTEXT_ENGINEERING_FILE,
        "receipts_readme": repo_root / REPO_AGENT_HOME / "receipts" / "README.md",
    }
    out: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "required_files": {name: str(file) for name, file in required.items()},
        "missing_files": [
            name for name, file in required.items() if not file.exists()
        ],
        "read_ok": False,
        "registered": False,
    }
    data = _read_yaml(path)
    if not isinstance(data, dict):
        return out
    out.update({
        "read_ok": True,
        "agent_uid": data.get("agent_uid"),
        "callsign": data.get("callsign"),
        "authority": data.get("authority"),
        "a2a_route": ((data.get("mailbox") or {}).get("route")),
        "nats_subject": ((data.get("mailbox") or {}).get("nats_subject")),
        "nats_runtime_status": (
            (data.get("mailbox") or {}).get("runtime_status")
        ),
        "registered": data.get("agent_uid") == AGENT_ID
        and data.get("callsign") == CALLSIGN
        and not out["missing_files"],
    })
    return out


def read_live_registration_summary(state_dir: Path) -> dict[str, Any]:
    external_path = state_dir / "external_agents" / AGENT_ID / "registration.json"
    dock_path = state_dir / "agents" / AGENT_ID / "living_agent.json"
    card_path = state_dir / "a2a" / "cards" / f"{CALLSIGN}.json"
    last_receipt_path = state_dir / "agents" / AGENT_ID / "last_receipt.json"
    paths = {
        "external_registration": external_path,
        "living_agent": dock_path,
        "a2a_card": card_path,
        "last_onboarding_receipt": last_receipt_path,
    }
    out: dict[str, Any] = {
        "state_dir": str(state_dir),
        "paths": {name: str(path) for name, path in paths.items()},
        "exists": {name: path.exists() for name, path in paths.items()},
        "registered": False,
        "nats_runtime_status": "not_started",
    }
    external = _read_json_file(external_path)
    dock = _read_json_file(dock_path)
    card = _read_json_file(card_path)
    receipt = _read_json_file(last_receipt_path)

    if isinstance(external, dict):
        out["authority"] = external.get("authority")
        out["mailbox"] = external.get("mailbox")
        out["registration_source"] = external.get("registration_source")
        out["external_updated_at"] = external.get("updated_at")
        out["nats_subject"] = (external.get("metadata") or {}).get("nats_subject")
        out["nats_runtime_status"] = (
            (external.get("metadata") or {}).get("nats_runtime_status")
            or out["nats_runtime_status"]
        )
    if isinstance(dock, dict):
        out["dock_status"] = dock.get("status")
        out["dock_updated_at"] = dock.get("updated_at")
        out["memory_namespace"] = dock.get("memory_namespace")
    if isinstance(card, dict):
        out["a2a_endpoint"] = card.get("endpoint")
        out["a2a_status"] = card.get("status")
    if isinstance(receipt, dict):
        out["last_receipt_id"] = receipt.get("receipt_id")
        out["last_receipt_path"] = receipt.get("receipt_path")
        out["last_receipt_created_at"] = receipt.get("created_at")

    missing = [name for name, exists in out["exists"].items() if not exists]
    out["missing"] = missing
    out["registered"] = not missing
    if missing:
        out["blocker"] = "missing registration surfaces: " + ", ".join(missing)
    elif out.get("authority") != "external_worker_evidence_only":
        out["blocker"] = f"unexpected authority: {out.get('authority')}"
        out["registered"] = False
    elif out.get("nats_subject") != NATS_SUBJECT or out.get("mailbox") != f"nats://{NATS_SUBJECT}":
        out["blocker"] = (
            "live registration route drift: expected "
            f"{A2A_INBOX_ROUTE}/{NATS_SUBJECT}, got "
            f"{out.get('mailbox') or out.get('nats_subject')}"
        )
        out["registered"] = False
    return out


def build_loop_statuses(
    runtime: dict[str, Any],
    one_wire: dict[str, Any],
    archive: dict[str, Any],
    *,
    bounded_replays: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    delegation = runtime.get("delegation_runs") or {}
    total_runs = int(delegation.get("total") or 0)
    completed = int(delegation.get("completed") or 0)
    provider_truth = runtime.get("provider_truth") or {}
    delegation_truth = provider_truth.get("delegation_runs") or {}
    runtime_receipt_truth = provider_truth.get("runtime_receipts") or {}
    completed_with_truth = int(
        delegation_truth.get("completed_with_served_provider_model") or 0
    )
    runtime_receipt_truth_rows = int(
        runtime_receipt_truth.get("rows_with_served_provider_model") or 0
    )
    runtime_receipt_completed_truth_rows = int(
        runtime_receipt_truth.get("completed_rows_with_served_provider_model") or 0
    )
    routing_adaptation = provider_truth.get("routing_adaptation") or {}
    loop1_has_later_routing = _has_later_correlated_routing_adaptation(
        routing_adaptation
    )
    failure_counts = {
        str(r.get("failure_code")): int(r.get("count") or 0)
        for r in runtime.get("failure_codes") or []
    }
    quarantined_dropoffs = int(
        (runtime.get("quarantine") or {}).get("dispatch_dropoff_quarantined") or 0
    )
    one_wire_eligible = bool(one_wire.get("eligible"))
    archive_risk = int(archive.get("positive_internal_fitness_risk") or 0)
    loop1_replay = ((bounded_replays or {}).get("loop1") or {})
    loop1_harness_proven = bool(loop1_replay.get("harness_proven") or loop1_replay.get("closed"))
    loop1_closed_live = (
        loop1_harness_proven
        and total_runs > 0
        and completed > 0
        and failure_counts.get("dispatch_dropoff", 0) == 0
        and (completed_with_truth > 0 or runtime_receipt_completed_truth_rows > 0)
        and loop1_has_later_routing
    )

    for number, loop_id, label in LOOPS:
        status = "UNKNOWN"
        blocker = "no fresh closure packet inspected by cybernetics_codex"
        evidence: list[str] = []

        # Cascade loops (2..11): a strict, structurally-verified closure replay
        # proves the harness. It does not close the live loop unless the
        # declared owner-surface criterion also passes.
        general_replay = (bounded_replays or {}).get(f"loop{number}") or {}
        replay_harness_proven = bool(
            general_replay.get("harness_proven") or general_replay.get("closed")
        )
        if number not in (1, 12, 13) and replay_harness_proven:
            rows.append({
                "number": number,
                "id": loop_id,
                "label": label,
                "verdict": "HARNESS_PROVEN",
                "evidence": [f"bounded_replays.loop{number}"],
                "blocker": (
                    f"bounded closure replay proves the loop {number} harness "
                    f"(cycles={general_replay.get('cycles')}, all transitions "
                    "receipted, adapt change fed the next cycle); not CLOSED_LIVE "
                    "until live owner-surface criterion passes"
                ),
                "live_owner_surface_criterion": LIVE_OWNER_SURFACE_CRITERIA[number],
            })
            continue

        if number == 1:
            evidence = [
                "runtime.delegation_runs",
                "runtime.runtime_receipts",
                "runtime.provider_truth",
                "runtime.failure_codes",
            ]
            if loop1_harness_proven:
                evidence.append("bounded_replays.loop1")
            if loop1_has_later_routing:
                evidence.append("runtime.provider_truth.routing_adaptation")
            if total_runs == 0:
                status = "UNKNOWN"
                blocker = "no delegation runs found"
            elif loop1_closed_live:
                status = "CLOSED_LIVE"
                blocker = (
                    "audited runtime scope has served provider/model truth, "
                    "zero dispatch_dropoff, a later correlated routing/adaptation "
                    "read, and the Loop 1 replay proves current dispatch receipts"
                )
            elif loop1_harness_proven:
                missing: list[str] = []
                if failure_counts.get("dispatch_dropoff", 0):
                    missing.append(
                        f"dispatch_dropoff={failure_counts.get('dispatch_dropoff', 0)}"
                    )
                if completed == 0:
                    missing.append("no completed delegation runs in runtime scope")
                if completed_with_truth == 0 and runtime_receipt_completed_truth_rows == 0:
                    missing.append("no served provider/model truth from completed work")
                if not loop1_has_later_routing:
                    missing.append(
                        "no later correlated routing/adaptation read after served-provider truth"
                    )
                status = "HARNESS_PROVEN"
                blocker = (
                    "bounded replay proves current Loop 1 harness "
                    f"({loop1_replay.get('tasks_completed')}/"
                    f"{loop1_replay.get('tasks_requested')} completed, "
                    f"dispatch_dropoff={loop1_replay.get('dispatch_dropoffs')}, "
                    f"evidence_receipts_ok={loop1_replay.get('evidence_receipts_ok')}, "
                    f"served_provider_truth="
                    f"{loop1_replay.get('completed_runs_with_truth')}); "
                    "not CLOSED_LIVE: "
                    + "; ".join(missing or ["live owner-surface criterion not fully met"])
                )
            elif failure_counts.get("dispatch_dropoff", 0):
                status = "PARTIAL"
                blocker = (
                    f"activity exists ({completed}/{total_runs} completed), but "
                    f"dispatch_dropoff={failure_counts.get('dispatch_dropoff', 0)}; "
                    f"served_provider_truth completed={completed_with_truth}/{completed}, "
                    f"runtime_receipts_completed={runtime_receipt_completed_truth_rows}/"
                    f"{runtime_receipt_truth_rows}. "
                    "receipt_json is orchestrator-surface only, not an A2A closure requirement"
                )
            elif completed == 0:
                status = "PARTIAL"
                blocker = "runtime activity exists, but no completed delegation runs in scope"
            elif completed_with_truth == 0 and runtime_receipt_completed_truth_rows == 0:
                status = "PARTIAL"
                if runtime_receipt_truth_rows:
                    blocker = (
                        f"{completed}/{total_runs} runs completed; runtime_receipts "
                        f"had {runtime_receipt_truth_rows} served_provider/served_model "
                        "row(s), but none joined to completed delegation work"
                    )
                else:
                    blocker = (
                        f"{completed}/{total_runs} runs completed, but no actual "
                        "served_provider/served_model truth was found on completed "
                        "delegation metadata or runtime_receipts"
                    )
            else:
                status = "NEEDS_ADVERSARIAL_REVIEW"
                blocker = (
                    f"served provider/model truth exists "
                    f"(delegation completed={completed_with_truth}/{completed}, "
                    f"runtime_receipts_completed={runtime_receipt_completed_truth_rows}/"
                    f"{runtime_receipt_truth_rows}); still needs "
                    "bounded spine-dispatch replay proving tick N changes tick N+1"
                )
            if quarantined_dropoffs:
                # Never hide the quarantined-historical tally: the live count
                # above excludes these rows, but the claim stays honest only if
                # the audit reports them alongside it.
                blocker += (
                    f"; dispatch_dropoff_quarantined_historical={quarantined_dropoffs} "
                    "(excluded from live count; rows remain auditable in delegation_runs)"
                )
        elif number in {12, 13}:
            evidence = ["one_wire.guardian_receipt", "evolution_archive"]
            if not one_wire_eligible:
                status = "BLOCKED"
                blocker = str(one_wire.get("blocker") or "One Wire quorum not eligible")
            elif archive_risk:
                status = "BLOCKED"
                blocker = f"archive has {archive_risk} positive internal-fitness risk rows"
            else:
                status = "PARTIAL"
                blocker = "One Wire eligible but mutation/apply boundary still needs proof"
        elif number in {3, 7, 8} and archive.get("exists"):
            status = "PARTIAL"
            blocker = "activity exists, but adaptation/fitness authority is not closure-proven"
            evidence = ["evolution_archive"]
        elif number in {6} and runtime.get("tables", {}).get("runtime_receipts", {}).get("rows", 0):
            status = "PARTIAL"
            blocker = "audit/receipt activity exists, but current Loop 1 production tie-in not proven"
            evidence = ["runtime.runtime_receipts"]
        elif total_runs > 0:
            status = "PARTIAL"
            blocker = "runtime substrate is active, but this loop lacks a dedicated closure receipt"
            evidence = ["runtime.delegation_runs"]

        rows.append({
            "number": number,
            "id": loop_id,
            "label": label,
            "verdict": status,
            "evidence": evidence,
            "blocker": blocker,
            "live_owner_surface_criterion": LIVE_OWNER_SURFACE_CRITERIA[number],
        })
    return rows


def _has_later_correlated_routing_adaptation(
    routing_adaptation: dict[str, Any],
) -> bool:
    tables = routing_adaptation.get("tables") or {}
    for table_summary in tables.values():
        if not isinstance(table_summary, dict):
            continue
        if int(table_summary.get("correlated_rows_after_served_truth") or 0) > 0:
            return True
    return False


def _table_summary(conn: sqlite3.Connection, table: str) -> dict[str, Any]:
    if not _table_exists(conn, table):
        return {"exists": False, "rows": 0, "latest": None}
    latest = None
    for col in ("created_at", "started_at", "completed_at", "updated_at"):
        if _column_exists(conn, table, col):
            latest = conn.execute(f"select max({col}) from {table}").fetchone()[0]
            break
    rows = conn.execute(f"select count(*) from {table}").fetchone()[0]
    return {"exists": True, "rows": rows, "latest": latest}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "select 1 from sqlite_master where type='table' and name=?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"pragma table_info({table})"))


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info({table})")}


def _time_scope_sql(
    conn: sqlite3.Connection,
    table: str,
    expression: str,
    since: str | None,
) -> tuple[str, tuple[str, ...]]:
    if not since:
        return "", ()
    column_names = _table_columns(conn, table)
    needed = {"created_at"} if expression == "created_at" else {"started_at", "completed_at"}
    if not needed.intersection(column_names):
        return "", ()
    return f"where {expression} >= ?", (since,)


def _and_where(where_sql: str, predicate: str) -> str:
    if where_sql.strip():
        return f"{where_sql} and {predicate}"
    return f"where {predicate}"


def _loads_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _extract_served_provider_truth(value: Any) -> dict[str, str] | None:
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            provider = _first_text_key(current, SERVED_PROVIDER_KEYS)
            model = _first_text_key(current, SERVED_MODEL_KEYS)
            if provider and model and provider.casefold() not in NON_PROVIDER_VALUES:
                return {"served_provider": provider, "served_model": model}
            for nested in current.values():
                if isinstance(nested, (dict, list)):
                    stack.append(nested)
        elif isinstance(current, list):
            stack.extend(item for item in current if isinstance(item, (dict, list)))
    return None


def _first_text_key(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _read_yaml(path: Path) -> Any:
    if not path.exists() or yaml is None:
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if row.get(key):
            return row[key]
    return None


def _has_positive_internal_fitness(row: dict[str, Any]) -> bool:
    fitness = row.get("fitness")
    if not isinstance(fitness, dict):
        return False
    correctness = float(fitness.get("correctness") or 0.0)
    if correctness != 0.0:
        return False
    for key in ("dharmic_alignment", "economic_value", "efficiency", "safety"):
        try:
            if float(fitness.get(key) or 0.0) > 0.0:
                return not _has_external_authority_marker(row)
        except (TypeError, ValueError):
            continue
    return False


def _has_external_authority_marker(row: dict[str, Any]) -> bool:
    blob = json.dumps(row, sort_keys=True)
    markers = (
        '"fitness_authority_granted": true',
        '"external_confirmed": true',
        '"external_acted_receipt"',
        '"one_wire"',
        '"quorum"',
    )
    return any(marker in blob for marker in markers)
