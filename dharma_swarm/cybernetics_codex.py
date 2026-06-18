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

try:  # pragma: no cover - exercised by repo runtime; tests run with PyYAML.
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_DIR = Path.home() / ".dharma"

AGENT_ID = "cybernetics_codex"
CALLSIGN = "cybernetics-codex"
SCHEMA_VERSION = "cybernetics_codex.audit.v2"
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
        "one_wire": one_wire,
        "evolution_archive": archive,
        "loop_statuses": build_loop_statuses(runtime, one_wire, archive),
        "verifier_commands": VERIFIER_COMMANDS,
        "closure_rule": (
            "A loop is closed only when sense -> interpret -> constrain -> act -> "
            "adapt all fire on real data, every transition emits a receipt to its "
            "owner surface, and a fresh agent can replay an automated check."
        ),
        "loop1_acceptance_rule": (
            "A2A-surface rows may legitimately leave delegation_runs.receipt_json "
            "empty; the production truth this audit requires is actual served "
            "provider/model on delegation metadata or runtime_receipts, with no "
            "dispatch_dropoff in the audited scope."
        ),
        "next_build_packet": [
            "Run a bounded DHARMA_SPINE_DISPATCH=1 batch and audit it with --since from the batch start timestamp.",
            "Cross-check served provider/model truth in runtime DB, witness logs, and orient output.",
            "Add One Wire archive-fitness guard tests before enabling Loops 12/13.",
            "Regenerate the loop map from a live projection instead of hand-editing stale prose.",
        ],
    }


def build_external_worker_registration(
    *,
    dharma_home: Path | str | None = None,
    repo_root: Path | str = REPO_ROOT,
):
    """Construct the Stage-1 registration record for the steward.

    This is intentionally local metadata only: it creates a discoverable dock,
    external registration, A2A card, and onboarding receipt when passed to the
    registration desk. It does not start a daemon or bind a provider.
    """
    from dharma_swarm.external_agent_registration import (
        AutonomyPolicy,
        ExternalAgentAuthority,
        ExternalAgentStatus,
        ExternalRoamingWorker,
        WorkspacePolicy,
        external_agent_sandbox_root,
    )

    home = Path(dharma_home) if dharma_home else DEFAULT_STATE_DIR
    repo = Path(repo_root)
    return ExternalRoamingWorker(
        agent_uid=AGENT_ID,
        callsign=CALLSIGN,
        display_name="Cybernetics Codex Steward",
        harness="codex",
        model_identity="codex",
        department="cybernetics",
        role="closure_ledger_steward",
        squad_id="loop_closure",
        team_id="dharma_swarm",
        endpoint="pending://manual",
        mailbox=f"nats://{NATS_SUBJECT}",
        authority=ExternalAgentAuthority.EXTERNAL_WORKER_EVIDENCE_ONLY,
        autonomy_policy=AutonomyPolicy(
            mode="manual",
            requires_approval=True,
            explicit_task_assignment_required=True,
        ),
        workspace_policy=WorkspacePolicy(
            sandbox_root=str(external_agent_sandbox_root(home) / AGENT_ID),
            repo_writes_allowed=False,
            canonical_dharma_dir_writes_allowed=False,
        ),
        memory_namespace=f"agent:{AGENT_ID}",
        trace_identity=f"trace:{AGENT_ID}",
        status=ExternalAgentStatus.REGISTERED,
        is_returning_historical_embodiment=False,
        notes=(
            "Read-only cybernetic loop closure steward. Evidence-only: audits "
            "loop closure claims, One Wire invariants, provider health receipts, "
            "and VSM/cybernetic stewardship surfaces. No provider calls, source "
            "writes, dispatch, PR approval, spend, or live external account action."
        ),
        registration_source="cybernetics_codex_registration",
        capabilities=(
            "cybernetic_loop_audit",
            "closure_ledger",
            "vsm_mapping",
            "one_wire_guardian_review",
            "receipt_integrity",
            "context_engineering",
        ),
        metadata={
            "repo_home": str(repo / REPO_AGENT_HOME),
            "seed_path": str(repo / SEED_FILE),
            "soul_file": str(repo / SOUL_FILE),
            "context_engineering_desk": str(repo / CONTEXT_ENGINEERING_FILE),
            "charter": str(repo / "docs/ops/CYBERNETICS_CODEX.md"),
            "manifest_agent_id": AGENT_ID,
            "a2a_route": A2A_INBOX_ROUTE,
            "nats_subject": NATS_SUBJECT,
            "nats_runtime_status": "declared_not_started",
            "a2a_transport_status": "card_registered_only_after_onboarding",
            "authority_boundary": "external_worker_evidence_only",
            "no_provider_calls": True,
            "no_autonomous_dispatch": True,
            "one_wire_invariant": (
                "internal artifacts never touch archive fitness; only "
                "countersigned external acted receipts above quorum do"
            ),
        },
    )


def read_runtime_summary(db_path: Path, *, since: str | None = None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": str(db_path),
        "exists": db_path.exists(),
        "read_ok": False,
        "scope": {"since": since},
        "tables": {},
        "delegation_runs": {},
        "failure_codes": [],
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
            summary["failure_codes"] = [
                dict(r)
                for r in conn.execute(
                    f"""
                    select
                      failure_code,
                      count(*) as count,
                      max(coalesce(completed_at, started_at)) as last_seen
                    from delegation_runs
                    {_and_where(where_sql, "status='failed'")}
                    group by failure_code
                    order by count desc
                    limit 12
                    """,
                    where_args,
                ).fetchall()
            ]
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


def _served_provider_truth_summary(
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
) -> dict[str, Any]:
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
            "unique_runs_with_served_provider_model": 0,
            "latest_truth_receipt": None,
            "sample": None,
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
            truth = (
                _extract_served_provider_truth(_loads_json(row["metadata_json"]))
                or _extract_served_provider_truth(_loads_json(row["receipt_json"]))
            )
            if truth:
                out["delegation_runs"]["rows_with_served_provider_model"] += 1
                if status == "completed":
                    out["delegation_runs"]["completed_with_served_provider_model"] += 1
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
                truth_runs.add(str(row["run_id"]))
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
        out["runtime_receipts"]["unique_runs_with_served_provider_model"] = len(truth_runs)

    return out


def read_one_wire_summary(state_dir: Path) -> dict[str, Any]:
    path = state_dir / "forge_measurement_guardian" / "cycle-003-fitness-quorum-guard.json"
    out: dict[str, Any] = {
        "guardian_receipt": str(path),
        "exists": path.exists(),
        "required_confirmed": 5,
        "required_domains": 3,
        "eligible": False,
        "fitness_authority_granted": False,
    }
    if not path.exists():
        out["blocker"] = "guardian quorum receipt missing"
        return out
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        out["blocker"] = f"guardian receipt unreadable: {type(exc).__name__}"
        return out

    out["payload_keys"] = sorted(payload)[:20]
    authority = payload.get("authority_result") if isinstance(payload, dict) else {}
    threshold = payload.get("threshold_guard") if isinstance(payload, dict) else {}
    if isinstance(authority, dict):
        out["confirmed"] = authority.get("confirmed_receipt_count", out.get("confirmed", 0))
        out["domains"] = authority.get("domain_count", out.get("domains", 0))
        out["eligible"] = authority.get("eligible_to_set_archive_fitness", out.get("eligible", False))
        out["archive_fitness_changed"] = authority.get(
            "archive_fitness_changed",
            out.get("archive_fitness_changed", False),
        )
        out["fitness_authority_granted"] = authority.get(
            "fitness_authority_granted",
            out.get("fitness_authority_granted", False),
        )
    if isinstance(threshold, dict):
        out["required_confirmed"] = threshold.get(
            "required_confirmed_receipts",
            out["required_confirmed"],
        )
        out["required_domains"] = threshold.get(
            "required_distinct_domains",
            out["required_domains"],
        )
        out["confirmed"] = threshold.get("observed_confirmed_receipts", out.get("confirmed", 0))
        out["domains"] = threshold.get("observed_distinct_domains", out.get("domains", 0))
        out["observed_domains"] = threshold.get("observed_domains", [])
    for key in ("confirmed", "domains", "eligible", "archive_fitness_changed", "fitness_authority_granted"):
        if key in payload:
            out[key] = payload[key]
    confirmed = int(out.get("confirmed") or 0)
    domains = int(out.get("domains") or 0)
    required_confirmed = int(out.get("required_confirmed") or 5)
    required_domains = int(out.get("required_domains") or 3)
    eligible = (
        bool(out.get("eligible"))
        and bool(out.get("fitness_authority_granted"))
        and confirmed >= required_confirmed
        and domains >= required_domains
    )
    out["eligible"] = eligible
    if not eligible:
        out["blocker"] = (
            f"guardian quorum below threshold: "
            f"N={confirmed}/{required_confirmed}, M={domains}/{required_domains}"
        )
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
    failure_counts = {
        str(r.get("failure_code")): int(r.get("count") or 0)
        for r in runtime.get("failure_codes") or []
    }
    one_wire_eligible = bool(one_wire.get("eligible"))
    archive_risk = int(archive.get("positive_internal_fitness_risk") or 0)

    for number, loop_id, label in LOOPS:
        status = "UNKNOWN"
        blocker = "no fresh closure packet inspected by cybernetics_codex"
        evidence: list[str] = []

        if number == 1:
            evidence = [
                "runtime.delegation_runs",
                "runtime.runtime_receipts",
                "runtime.provider_truth",
                "runtime.failure_codes",
            ]
            if total_runs == 0:
                status = "UNKNOWN"
                blocker = "no delegation runs found"
            elif failure_counts.get("dispatch_dropoff", 0):
                status = "PARTIAL"
                blocker = (
                    f"activity exists ({completed}/{total_runs} completed), but "
                    f"dispatch_dropoff={failure_counts.get('dispatch_dropoff', 0)}; "
                    f"served_provider_truth completed={completed_with_truth}/{completed}, "
                    f"runtime_receipts={runtime_receipt_truth_rows}. "
                    "receipt_json is orchestrator-surface only, not an A2A closure requirement"
                )
            elif completed == 0:
                status = "PARTIAL"
                blocker = "runtime activity exists, but no completed delegation runs in scope"
            elif completed_with_truth == 0 and runtime_receipt_truth_rows == 0:
                status = "PARTIAL"
                blocker = (
                    f"{completed}/{total_runs} runs completed, but no actual "
                    "served_provider/served_model truth was found on delegation "
                    "metadata or runtime_receipts"
                )
            else:
                status = "NEEDS_ADVERSARIAL_REVIEW"
                blocker = (
                    f"served provider/model truth exists "
                    f"(delegation completed={completed_with_truth}/{completed}, "
                    f"runtime_receipts={runtime_receipt_truth_rows}); still needs "
                    "bounded spine-dispatch replay proving tick N changes tick N+1"
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
        })
    return rows


def format_markdown(report: dict[str, Any]) -> str:
    """Render a compact human-readable audit packet."""
    lines = [
        "# cybernetics_codex Audit",
        "",
        f"- observed_at: `{report['observed_at']}`",
        f"- mode: `{report['agent']['mode']}`",
        f"- manifest_registered: `{report['manifest_registration'].get('registered')}`",
        f"- loop_track_found: `{report['active_track'].get('loop_track_found')}`",
        f"- seed_registered: `{report['seed_registration'].get('registered')}`",
        f"- live_registration: `{report['live_registration'].get('registered')}`",
        f"- nats_runtime_status: `{report['live_registration'].get('nats_runtime_status')}`",
        "",
        "## Runtime",
        "",
    ]
    runtime = report["runtime"]
    delegation = runtime.get("delegation_runs") or {}
    receipt = runtime.get("receipt_json") or {}
    provider_truth = runtime.get("provider_truth") or {}
    delegation_truth = provider_truth.get("delegation_runs") or {}
    runtime_receipt_truth = provider_truth.get("runtime_receipts") or {}
    lines.extend([
        f"- runtime_db: `{runtime.get('path')}`",
        f"- read_ok: `{runtime.get('read_ok')}`",
        f"- scope_since: `{(runtime.get('scope') or {}).get('since')}`",
        f"- delegation_runs: `{delegation.get('total', 0)}` total, "
        f"`{delegation.get('completed', 0)}` completed, "
        f"`{delegation.get('failed', 0)}` failed",
        f"- receipt_json: `{receipt.get('rows_with_receipt_json', 0)}` rows "
        "`(orchestrator surface; A2A empty is success)`",
        f"- served_provider_truth: delegation completed "
        f"`{delegation_truth.get('completed_with_served_provider_model', 0)}/"
        f"{delegation_truth.get('completed', 0)}`, runtime_receipts "
        f"`{runtime_receipt_truth.get('rows_with_served_provider_model', 0)}` rows",
        "",
        "## Loop Statuses",
        "",
        "| # | Loop | Verdict | Blocker |",
        "|---|---|---|---|",
    ])
    for row in report["loop_statuses"]:
        lines.append(
            f"| {row['number']} | {row['label']} | {row['verdict']} | "
            f"{str(row['blocker']).replace('|', '/')} |"
        )
    lines.extend([
        "",
        "## Verifier Commands",
        "",
        *[f"- `{cmd}`" for cmd in report["verifier_commands"]],
        "",
    ])
    return "\n".join(lines)


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
