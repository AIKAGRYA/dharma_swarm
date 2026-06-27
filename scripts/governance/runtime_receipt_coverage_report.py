#!/usr/bin/env python3
"""Read-only runtime receipt coverage report.

This verifier measures the 70 -> 75 hardening gate without mutating
``runtime.db``. It treats ``delegation_runs.receipt_json`` as projection/cache
evidence and ``runtime_receipts`` + ``idempotency_records`` as the canonical
runtime receipt/idempotency layer.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dharma_swarm.operator_core.live_ops_census_contract import (  # noqa: E402
    census_payload_freshness,
    default_output_path,
    validate_census_payload,
)

DEFAULT_DB = Path(os.environ.get("DHARMA_RUNTIME_DB", "/Users/dhyana/.dharma/state/runtime.db"))
REQUIRED_TABLES = (
    "delegation_runs",
    "runtime_receipts",
    "idempotency_records",
    "execution_identities",
    "task_claims",
    "artifact_records",
)
CORE_RECEIPT_FIELDS = (
    "run_id",
    "task_id",
    "trace_id",
    "correlation_id",
    "agent_id",
    "idempotency_key",
    "side_effect_key",
)
MAJOR_TASK_RECEIPT_TYPES = ("a2a_task", "delegation_run")
PRODUCER_METADATA_HINT_KEYS = (
    "source",
    "failure_code",
    "error",
    "runtime_db_path",
    "topology",
    "max_retries",
    "claim_timeout_seconds",
    "runner",
    "task",
    "context_bundle_status",
)
RECENT_WINDOW_MINUTES = (5, 15, 60)
FIELD_GAP_ACTIVE_WINDOW_MINUTES = 60
FIELD_GAP_RECENT_WINDOW_MINUTES = 24 * 60
PROVIDER_MODEL_PROBE_SOURCE_PREFIXES = (
    "runtime_lifecycle_receipt_probe",
)
LEGACY_PROVIDER_MODEL_PROBE_MISSION_PREFIXES = (
    "runtime-spine-provider-model-proof",
    "runtime-spine-provider-model-source-proof",
    "runtime-spine-orchestrator-provider-model-source-proof",
)
PROVIDER_SERVED_FIELD_KEYS = (
    "actual_served_provider",
    "served_provider",
    "actual_provider",
    "provider_served",
)
MODEL_SERVED_FIELD_KEYS = (
    "actual_served_model",
    "served_model",
    "actual_model",
    "model_served",
)
PROVIDER_SELECTED_OR_AMBIGUOUS_FIELD_KEYS = (
    "selected_provider",
    "provider_selected",
    "provider",
)
MODEL_SELECTED_OR_AMBIGUOUS_FIELD_KEYS = (
    "selected_model",
    "model_selected",
    "selected_model_hint",
    "model",
)
RUNTIME_PROVIDER_ACTUAL_SERVED_TRUTH_SOURCE = "runtime_provider.actual_served"
PROVIDER_FAILED_BEFORE_SERVE_TRUTH_SOURCES = (
    "agent_runner.provider_chain_failure",
)
PROVIDER_MODEL_PROVENANCE_CLASSES = (
    "served_field",
    "failed_before_serve",
    "no_provider_execution",
)
NO_PROVIDER_EXECUTION_TRUTH_SOURCES = (
    "runtime_control.no_provider_execution",
    "runtime_lifecycle.claim_timeout_no_provider_execution",
    "runtime_lifecycle.dispatch_dropoff_no_provider_execution",
    "living_agent_kernel.no_provider_execution",
    "ds_goal.no_provider_execution",
    "agent_runner.no_provider_execution",
    "holon_orchestrate.no_provider_execution",
    "opportunity_dispatcher.no_provider_execution",
)
PRE_WORKER_NO_PROVIDER_FAILURE_CODES = (
    "claim_timeout",
    "dispatch_dropoff",
)
NO_PROVIDER_RUNTIME_ACTIONS = (
    "kernel_wake",
    "ds_goal.kernel_wake",
)
DS_GOAL_RUN_ID_PREFIX = "run_ds_goal_"
DS_GOAL_SESSION_PREFIX = "ds_goal:"
DS_GOAL_INFERRED_SOURCE = "ds_goal_cli"
DS_GOAL_INFERRED_SIDE_EFFECT_FAILURE_CODE = "sync_receipt_side_effect_key_missing"
DS_GOAL_INFERRED_PROVIDER_MODEL_FAILURE_CODE = "provider_model_provenance_missing"
DS_GOAL_INFERRED_TOPOLOGY = "cli_goal_run"
FIELD_GAP_ACTION_PROOF_EVIDENCE: dict[str, dict[str, Any]] = {
    "repair_installed_ds_goal_wrapper_or_pin_invocations": {
        "status": "pin_mitigation_and_fail_closed_prevention_recorded_default_still_broken",
        "proof_scope": "isolated_temp_state",
        "proof_run_id": "run_ds_goal_1979d8f50609e82a7941be5f",
        "proof_db": "<temp ds-goal split-brain proof db>",
        "evidence_ref": (
            "docs/governance/ACTIVE_TRACK.yaml:"
            "post_70_ds_goal_prevention_receipt_scanner"
        ),
        "prevention_receipt_root": (
            "/private/tmp/ds-goal-preflight-block-proof-20260614T2245JST/state"
        ),
        "prevention_evidence": (
            "valid_preflight_block=1; "
            "runtime_db_absent_under_state_root; kernel_store_absent"
        ),
        "remaining_action": (
            "operator-approved wrapper convergence, target hardening, or explicit "
            "quarantine plus fresh default receipt proof"
        ),
    },
    "repair_or_quarantine_orchestrator_error_receipts": {
        "status": "fresh_scoped_proof_recorded",
        "proof_scope": "isolated_temp_db",
        "proof_run_id": "run-orchestrator-fanout-error-proof",
        "proof_db": (
            "/private/tmp/orchestrator-fanout-error-proof-20260614T1112Z/"
            "state/runtime.db"
        ),
        "evidence_ref": (
            "reports/governance/runtime_spine_hardening_progress_2026-06-14.md:"
            "orchestrator fan-out execution-error fresh proof"
        ),
        "remaining_action": (
            "historical execution_error debt still needs repair or operator-approved "
            "quarantine"
        ),
    },
    "inspect_orchestrator_fanout_success_receipt_fields": {
        "status": "fresh_scoped_proof_recorded",
        "proof_scope": "isolated_temp_db",
        "proof_run_id": "run-orchestrator-fanout-success-proof-rerun",
        "proof_db": (
            "/private/tmp/orchestrator-fanout-success-proof-rerun-20260614T1100Z/"
            "state/runtime.db"
        ),
        "evidence_ref": (
            "reports/governance/runtime_spine_hardening_progress_2026-06-14.md:"
            "orchestrator fan_out success fresh field proof"
        ),
        "remaining_action": (
            "historical fanout_success debt still needs repair or operator-approved "
            "quarantine"
        ),
    },
    "quarantine_fixture_debt_or_exclude_from_production_gate": {
        "status": "candidate_policy_recorded_not_applied",
        "proof_scope": "report_policy",
        "proof_run_id": "<not_applicable>",
        "proof_db": "<global report>",
        "evidence_ref": (
            "runtime_receipt_coverage_report.py fixture_quarantine_policy; "
            "tests/conftest.py isolation evidence"
        ),
        "remaining_action": (
            "operator quarantine acceptance plus proof fixture-shaped rows cannot "
            "recur in live runtime"
        ),
    },
    "prove_fresh_dropoff_clean_then_quarantine_historical_debt": {
        "status": "fresh_scoped_proof_recorded",
        "proof_scope": "isolated_temp_db",
        "proof_run_id": "run-dropoff-no-provider-proof",
        "proof_db": "/private/tmp/runtime-spine-dropoff-no-provider-proof/runtime.db",
        "evidence_ref": (
            "reports/governance/runtime_spine_hardening_progress_2026-06-14.md:"
            "runtime-lifecycle dropoff accounting"
        ),
        "remaining_action": (
            "historical dispatch_dropoff debt still needs repair or operator-approved "
            "quarantine"
        ),
    },
    "prove_fresh_claim_timeout_clean_then_quarantine_historical_debt": {
        "status": "fresh_scoped_proof_recorded",
        "proof_scope": "isolated_temp_db",
        "proof_run_id": "run-claim-timeout-no-provider-proof",
        "proof_db": "/private/tmp/runtime-spine-claim-timeout-no-provider-proof/runtime.db",
        "evidence_ref": (
            "reports/governance/runtime_spine_hardening_progress_2026-06-14.md:"
            "runtime-lifecycle claim-timeout cli proof"
        ),
        "remaining_action": (
            "historical claim_timeout debt still needs repair or operator-approved "
            "quarantine"
        ),
    },
    "prove_fresh_long_timeout_clean_then_quarantine_historical_debt": {
        "status": "fresh_scoped_proof_recorded",
        "proof_scope": "isolated_temp_db",
        "proof_run_id": "run-long-timeout-proof",
        "proof_db": "/private/tmp/runtime-lifecycle-long-timeout-proof/state/runtime.db",
        "evidence_ref": (
            "reports/governance/runtime_spine_hardening_progress_2026-06-14.md:"
            "long timeout fresh field proof"
        ),
        "remaining_action": (
            "historical long_timeout debt still needs repair or operator-approved "
            "quarantine"
        ),
    },
}


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"{db_path.expanduser().resolve().as_uri()}?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    db.row_factory = sqlite3.Row
    return db


def _table_exists(db: sqlite3.Connection, table: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _count(
    db: sqlite3.Connection,
    table: str,
    where: str = "1=1",
    params: tuple[Any, ...] = (),
) -> int:
    return int(db.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0])


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _safe_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"_parse_error": True}
    return parsed if isinstance(parsed, dict) else {"_non_object_payload": parsed}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if value == "":
            continue
        if value == [] or value == {}:
            continue
        return value
    return ""


def _metadata_hints(*payloads: dict[str, Any]) -> dict[str, Any]:
    hints: dict[str, Any] = {}
    for key in PRODUCER_METADATA_HINT_KEYS:
        value = _first_present(*(payload.get(key) for payload in payloads))
        if value != "":
            hints[key] = value
    return hints


def _identifier_shape(agent_id: str | None, task_id: str | None) -> str:
    agent = str(agent_id or "")
    task = str(task_id or "")
    fixture_agent = bool(re.fullmatch(r"a\d+", agent))
    fixture_task = bool(re.fullmatch(r"t\d+", task)) or task == "t-ready"
    if fixture_agent or fixture_task:
        return "fixture_shaped"
    return "ordinary"


def _is_ds_goal_receipt_identity(run_id: Any, session_id: Any) -> bool:
    run = str(run_id or "")
    session = str(session_id or "")
    return run.startswith(DS_GOAL_RUN_ID_PREFIX) or session.startswith(DS_GOAL_SESSION_PREFIX)


def _side_effect_gap_producer_context(
    *,
    run_id: Any,
    session_id: Any,
    delegation_failure_code: Any,
    hints: dict[str, Any],
    inferred_failure_code: str = DS_GOAL_INFERRED_SIDE_EFFECT_FAILURE_CODE,
) -> dict[str, Any]:
    metadata_hints = dict(hints)
    source = _first_present(hints.get("source"), "")
    failure_code = _first_present(delegation_failure_code, hints.get("failure_code"))
    topology = _first_present(hints.get("topology"), "")
    if _is_ds_goal_receipt_identity(run_id, session_id):
        if not source:
            source = DS_GOAL_INFERRED_SOURCE
            metadata_hints["inferred_source"] = source
        if not failure_code:
            failure_code = inferred_failure_code
            metadata_hints["inferred_failure_code"] = failure_code
        if not topology:
            topology = DS_GOAL_INFERRED_TOPOLOGY
            metadata_hints["inferred_topology"] = topology
        if "inferred_source" in metadata_hints:
            metadata_hints["inferred_from"] = "ds_goal_runtime_identity"
    return {
        "producer_source": source,
        "producer_failure_code": failure_code,
        "topology": topology,
        "metadata_hints": metadata_hints,
    }


def _trim_text(value: Any, limit: int = 96) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _parse_created_at(raw: str | None) -> datetime | None:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _created_at_cutoff(anchor: str, minutes: int) -> str | None:
    parsed = _parse_created_at(anchor)
    if parsed is None:
        return None
    return (parsed - timedelta(minutes=max(0, minutes))).isoformat()


def _payload_has_mission(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("mission_id")
        or payload.get("mission")
        or payload.get("missionId")
        or payload.get("mission")
    )


def _payload_has_artifact_ref(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("artifact_refs")
        or payload.get("artifact_ref")
        or payload.get("artifact_id")
        or payload.get("artifactId")
        or payload.get("artifacts")
    )


def _payload_has_provider(payload: dict[str, Any]) -> bool:
    return bool(
        _payload_has_any(payload, PROVIDER_SERVED_FIELD_KEYS)
        or _payload_has_any(payload, PROVIDER_SELECTED_OR_AMBIGUOUS_FIELD_KEYS)
    )


def _payload_has_model(payload: dict[str, Any]) -> bool:
    return bool(
        _payload_has_any(payload, MODEL_SERVED_FIELD_KEYS)
        or _payload_has_any(payload, MODEL_SELECTED_OR_AMBIGUOUS_FIELD_KEYS)
    )


def _payload_has_any(payload: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(_first_present(payload.get(key)) != "" for key in keys)


def _provider_model_truth_source(payload: dict[str, Any]) -> str:
    return str(
        _first_present(
            payload.get("provider_model_truth_source"),
            payload.get("route_truth_source"),
        )
    ).strip()


def _provider_model_payload_class(payload: dict[str, Any]) -> str:
    if _payload_declares_no_provider_execution(payload):
        return "no_provider_execution"
    if _payload_declares_provider_failed_before_serve(payload):
        return "failed_before_serve"
    has_provider = _payload_has_provider(payload)
    has_model = _payload_has_model(payload)
    if not has_provider and not has_model:
        return "missing"
    if not has_provider:
        return "missing_provider"
    if not has_model:
        return "missing_model"

    truth_source = _provider_model_truth_source(payload)
    source_lower = truth_source.lower()
    if any(
        source_lower.startswith(prefix)
        for prefix in PROVIDER_MODEL_PROBE_SOURCE_PREFIXES
    ):
        return "probe_selected"
    if _payload_declares_legacy_provider_model_probe(payload):
        return "legacy_probe_selected_unmarked"
    has_served_provider_model = _payload_has_any(
        payload,
        PROVIDER_SERVED_FIELD_KEYS,
    ) and _payload_has_any(payload, MODEL_SERVED_FIELD_KEYS)
    if (
        has_served_provider_model
        and truth_source == RUNTIME_PROVIDER_ACTUAL_SERVED_TRUTH_SOURCE
    ):
        return "served_field"
    if has_served_provider_model:
        return "served_field_unproven_source"
    if truth_source:
        return "source_marked_non_probe"
    return "selected_or_ambiguous_unmarked"


def _payload_declares_legacy_provider_model_probe(payload: dict[str, Any]) -> bool:
    mission_id = str(payload.get("mission_id") or "").strip()
    if not mission_id:
        return False
    return any(
        mission_id.startswith(prefix)
        for prefix in LEGACY_PROVIDER_MODEL_PROBE_MISSION_PREFIXES
    )


def _payload_declares_no_provider_execution(payload: dict[str, Any]) -> bool:
    raw_provider_execution = payload.get("provider_execution")
    provider_execution_false = raw_provider_execution is False or str(
        raw_provider_execution
    ).strip().lower() in {"false", "0", "no"}
    if not provider_execution_false:
        return False
    truth_source = _provider_model_truth_source(payload)
    if truth_source not in NO_PROVIDER_EXECUTION_TRUTH_SOURCES:
        return False
    return bool(
        str(
            payload.get("no_provider_model_reason")
            or payload.get("provider_model_applicability")
            or ""
        ).strip()
    )


def _payload_declares_provider_failed_before_serve(payload: dict[str, Any]) -> bool:
    raw_provider_execution = payload.get("provider_execution")
    provider_execution_true = raw_provider_execution is True or str(
        raw_provider_execution
    ).strip().lower() in {"true", "1", "yes"}
    if not provider_execution_true:
        return False
    truth_source = _provider_model_truth_source(payload)
    if truth_source not in PROVIDER_FAILED_BEFORE_SERVE_TRUTH_SOURCES:
        return False
    has_selected_provider_model = _payload_has_any(
        payload,
        PROVIDER_SELECTED_OR_AMBIGUOUS_FIELD_KEYS,
    ) and _payload_has_any(payload, MODEL_SELECTED_OR_AMBIGUOUS_FIELD_KEYS)
    has_served_provider_model = _payload_has_any(
        payload,
        PROVIDER_SERVED_FIELD_KEYS,
    ) and _payload_has_any(payload, MODEL_SERVED_FIELD_KEYS)
    if not has_selected_provider_model or has_served_provider_model:
        return False
    applicability = str(payload.get("provider_model_applicability") or "").strip()
    reason = str(payload.get("provider_model_missing_reason") or "").strip()
    return bool(
        applicability in {"failed_before_serve", "actual_served_unproven"}
        and reason
        in {
            "provider_chain_failed_before_actual_served_response",
            "attempted_route_selected_without_actual_served_runtime_evidence",
        }
    )


def _payload_declares_pending_provider_execution(payload: dict[str, Any]) -> bool:
    raw_provider_execution = str(payload.get("provider_execution") or "").strip().lower()
    if raw_provider_execution != "pending":
        return False
    truth_source = _provider_model_truth_source(payload)
    if truth_source != "runtime_lifecycle.provider_execution_pending":
        return False
    return bool(
        str(
            payload.get("provider_model_pending_reason")
            or payload.get("provider_model_applicability")
            or ""
        ).strip()
    )


def _is_terminal_receipt_status(status: Any) -> bool:
    normalized = str(status or "").strip().lower()
    if not normalized:
        return False
    return normalized not in {
        "accepted",
        "assigned",
        "claimed",
        "created",
        "in_progress",
        "pending",
        "queued",
        "running",
        "started",
        "submitted",
    }


def _payload_has_provider_model_provenance(payload: dict[str, Any]) -> bool:
    return _provider_model_payload_class(payload) in PROVIDER_MODEL_PROVENANCE_CLASSES


def _producer_context_declares_no_provider_execution(
    producer_context: dict[str, Any] | None,
) -> bool:
    if not producer_context:
        return False
    failure_code = str(producer_context.get("producer_failure_code") or "").strip()
    return failure_code in PRE_WORKER_NO_PROVIDER_FAILURE_CODES


def _payload_declares_no_provider_runtime_action(payload: dict[str, Any]) -> bool:
    action = str(_first_present(payload.get("action"), payload.get("operation"))).strip()
    return action in NO_PROVIDER_RUNTIME_ACTIONS


def _receipt_key(row: dict[str, Any]) -> tuple[str, str]:
    run_id = str(row.get("run_id") or "").strip()
    task_id = str(row.get("task_id") or "").strip()
    return (run_id, task_id)


def _no_provider_context_keys(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for row in rows:
        key = _receipt_key(row)
        if not all(key):
            continue
        payload = _safe_json(row.get("payload_json"))
        if _payload_declares_no_provider_execution(
            payload
        ) or _payload_declares_no_provider_runtime_action(payload):
            keys.add(key)
    return keys


def _provider_model_payload_class_for_status(
    payload: dict[str, Any],
    status: Any,
    producer_context: dict[str, Any] | None = None,
    sibling_no_provider_execution: bool = False,
) -> str:
    payload_class = _provider_model_payload_class(payload)
    if payload_class == "no_provider_execution":
        return payload_class
    if _payload_declares_pending_provider_execution(payload):
        return "pending_execution"
    if _is_terminal_receipt_status(status):
        if (
            payload_class == "missing"
            and (
                sibling_no_provider_execution
                or _producer_context_declares_no_provider_execution(producer_context)
            )
        ):
            return "no_provider_execution"
        return payload_class
    return "pending_execution"


def _producer_context_for_receipt(
    row: dict[str, Any],
    payload: dict[str, Any],
    *,
    inferred_failure_code: str = DS_GOAL_INFERRED_PROVIDER_MODEL_FAILURE_CODE,
) -> dict[str, Any]:
    delegation_metadata = _safe_json(row.get("delegation_metadata_json"))
    return _side_effect_gap_producer_context(
        run_id=row.get("run_id"),
        session_id=_first_present(
            payload.get("session_id"),
            payload.get("runtime_session_id"),
            payload.get("correlation_id"),
            row.get("delegation_session_id"),
        ),
        delegation_failure_code=_first_present(
            payload.get("delegation_failure_code"),
            payload.get("failure_code"),
            row.get("delegation_failure_code"),
        ),
        hints=_metadata_hints(payload, delegation_metadata),
        inferred_failure_code=inferred_failure_code,
    )


def _provider_model_unproven_producer_groups(
    latest_major: list[dict[str, Any]],
    no_provider_context_keys: set[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
    context_keys = no_provider_context_keys or set()
    for row in latest_major:
        payload = _safe_json(row.get("payload_json"))
        producer_context = _producer_context_for_receipt(row, payload)
        provider_model_class = _provider_model_payload_class_for_status(
            payload,
            row.get("status"),
            producer_context,
            _receipt_key(row) in context_keys,
        )
        if (
            provider_model_class in PROVIDER_MODEL_PROVENANCE_CLASSES
            or _payload_has_provider_model_provenance(payload)
        ):
            continue
        truth_source = (
            "<pending>"
            if provider_model_class == "pending_execution"
            else _provider_model_truth_source(payload) or "<blank>"
        )
        producer_source = producer_context.get("producer_source") or "<unknown>"
        producer_failure = producer_context.get("producer_failure_code") or "<none>"
        topology = producer_context.get("topology") or "<blank>"
        key = (
            str(row.get("receipt_type") or ""),
            provider_model_class,
            producer_source,
            producer_failure,
            topology,
            truth_source,
        )
        group = groups.setdefault(
            key,
            {
                "receipt_type": str(row.get("receipt_type") or ""),
                "provider_model_payload_class": provider_model_class,
                "provider_model_truth_source": truth_source,
                "producer_source": producer_source,
                "producer_failure_code": producer_failure,
                "topology": topology,
                "missing_provider_model_provenance": 0,
                "latest_created_at": str(row.get("created_at") or ""),
                "sample_agent_id": str(row.get("agent_id") or ""),
                "sample_task_id": str(row.get("task_id") or ""),
                "sample_run_id": str(row.get("run_id") or ""),
            },
        )
        group["missing_provider_model_provenance"] += 1
    return sorted(
        groups.values(),
        key=lambda item: (
            -int(item["missing_provider_model_provenance"]),
            item["receipt_type"],
            item["provider_model_payload_class"],
            item["producer_source"],
            item["producer_failure_code"],
            item["topology"],
        ),
    )[:10]


def _payload_has_explicit_absence(payload: dict[str, Any], field: str) -> bool:
    missing = payload.get("missing_machine_fields") or []
    if isinstance(missing, list) and field in {str(item) for item in missing}:
        return True
    reason_key = f"no_{field}_reason"
    return bool(payload.get(reason_key))


def _field_coverage(
    db: sqlite3.Connection,
    table: str,
    fields: tuple[str, ...],
    *,
    where: str = "1=1",
    params: tuple[Any, ...] = (),
) -> dict[str, dict[str, Any]]:
    total = _count(db, table, where, params)
    coverage: dict[str, dict[str, Any]] = {}
    for field in fields:
        filled = _count(
            db,
            table,
            f"({where}) AND {field} IS NOT NULL AND {field} != ''",
            params,
        )
        coverage[field] = {
            "filled": filled,
            "total": total,
            "percent": _percent(filled, total),
            "missing": max(total - filled, 0),
        }
    return coverage


def _major_task_receipt_filter() -> str:
    quoted = ", ".join(f"'{item}'" for item in MAJOR_TASK_RECEIPT_TYPES)
    return f"receipt_type IN ({quoted})"


def _with_run_scope(
    where: str,
    run_id: str,
    *,
    alias: str = "",
) -> tuple[str, tuple[str, ...]]:
    clean_run_id = str(run_id or "").strip()
    if not clean_run_id:
        return where, ()
    column = f"{alias}.run_id" if alias else "run_id"
    return f"({where}) AND {column} = ?", (clean_run_id,)


def _with_receipt_scope(
    where: str,
    *,
    run_id: str = "",
    since_created_at: str = "",
    alias: str = "",
) -> tuple[str, tuple[str, ...]]:
    scoped_where = where
    params: list[str] = []
    clean_run_id = str(run_id or "").strip()
    if clean_run_id:
        column = f"{alias}.run_id" if alias else "run_id"
        scoped_where = f"({scoped_where}) AND {column} = ?"
        params.append(clean_run_id)
    clean_since = str(since_created_at or "").strip()
    if clean_since:
        column = f"{alias}.created_at" if alias else "created_at"
        scoped_where = f"({scoped_where}) AND {column} >= ?"
        params.append(clean_since)
    return scoped_where, tuple(params)


def _scope_mode(run_id: str, since_created_at: str) -> str:
    has_run_id = bool(str(run_id or "").strip())
    has_since = bool(str(since_created_at or "").strip())
    if has_run_id and has_since:
        return "run_id+since_created_at"
    if has_run_id:
        return "run_id"
    if has_since:
        return "since_created_at"
    return "all"


def _major_type_breakdown(
    db: sqlite3.Connection,
    *,
    where: str,
    params: tuple[Any, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in db.execute(
        f"""
        SELECT
          rr.receipt_type AS receipt_type,
          COUNT(DISTINCT rr.receipt_id) AS total,
          COUNT(DISTINCT CASE
            WHEN rr.idempotency_key != '' AND rr.side_effect_key != ''
            THEN rr.receipt_id END
          ) AS with_idempotency_fields,
          COUNT(DISTINCT CASE
            WHEN ir.idempotency_key IS NOT NULL
            THEN rr.receipt_id END
          ) AS with_matching_idempotency_record,
          COUNT(DISTINCT CASE
            WHEN ar.artifact_id IS NOT NULL
            THEN rr.receipt_id END
          ) AS with_artifact_record
        FROM runtime_receipts rr
        LEFT JOIN idempotency_records ir
          ON rr.idempotency_key = ir.idempotency_key
         AND rr.side_effect_key = ir.side_effect_key
         AND rr.idempotency_key != ''
         AND rr.side_effect_key != ''
        LEFT JOIN artifact_records ar
          ON (rr.run_id != '' AND rr.run_id = ar.run_id)
          OR (rr.task_id != '' AND rr.task_id = ar.task_id)
        WHERE {where}
        GROUP BY rr.receipt_type
        ORDER BY total DESC, rr.receipt_type ASC
        """,
        params,
    ):
        data = dict(row)
        total = int(data["total"])
        with_matching_idempotency_record = int(data["with_matching_idempotency_record"])
        with_artifact_record = int(data["with_artifact_record"])
        data.update(
            total=total,
            with_idempotency_fields=int(data["with_idempotency_fields"]),
            with_matching_idempotency_record=with_matching_idempotency_record,
            with_artifact_record=with_artifact_record,
            idempotency_gap=max(total - with_matching_idempotency_record, 0),
            artifact_record_gap=max(total - with_artifact_record, 0),
        )
        rows.append(data)
    return rows


def _field_gap_freshness_class(
    latest_created_at: str,
    *,
    anchor_created_at: str,
) -> tuple[str, int | None]:
    latest = _parse_created_at(latest_created_at)
    anchor = _parse_created_at(anchor_created_at)
    if latest is None or anchor is None:
        return "unknown", None
    age_minutes = int(max(0, (anchor - latest).total_seconds() // 60))
    if latest > anchor:
        return "future_clock_skew", age_minutes
    if age_minutes <= FIELD_GAP_ACTIVE_WINDOW_MINUTES:
        return "active_head_60m", age_minutes
    if age_minutes <= FIELD_GAP_RECENT_WINDOW_MINUTES:
        return "recent_historical_24h", age_minutes
    return "older_historical", age_minutes


def _field_gap_recommended_action(group: dict[str, Any]) -> str:
    source = str(group.get("producer_source") or "")
    failure = str(group.get("producer_failure_code") or "")
    topology = str(group.get("topology") or "")
    shape = str(group.get("identifier_shape") or "")
    if source == DS_GOAL_INFERRED_SOURCE:
        return "repair_installed_ds_goal_wrapper_or_pin_invocations"
    if shape == "fixture_shaped":
        return "quarantine_fixture_debt_or_exclude_from_production_gate"
    if source == "orchestrator" and failure == "execution_error":
        return "repair_or_quarantine_orchestrator_error_receipts"
    if source == "orchestrator" and failure == "dispatch_dropoff":
        return "prove_fresh_dropoff_clean_then_quarantine_historical_debt"
    if source == "orchestrator" and failure == "claim_timeout":
        return "prove_fresh_claim_timeout_clean_then_quarantine_historical_debt"
    if source == "orchestrator" and failure == "long_timeout":
        return "prove_fresh_long_timeout_clean_then_quarantine_historical_debt"
    if source == "orchestrator" and failure == "<none>" and topology == "fan_out":
        return "inspect_orchestrator_fanout_success_receipt_fields"
    return "inspect_producer_and_assign_owner"


def _field_gap_action_policy(action: str) -> dict[str, Any]:
    policies = {
        "repair_installed_ds_goal_wrapper_or_pin_invocations": {
            "short_label": "ds_goal_wrapper",
            "owner_surface": "cli.ds_goal",
            "disposition": "active_head_repair_required",
            "operator_decision_required": True,
            "required_evidence": [
                "operator-approved wrapper target convergence or enforced audited-checkout pin",
                "fresh ds-goal task_claim/delegation_run receipts carry side_effect_key",
                "active-head side_effect_key windows are clean after the change",
            ],
        },
        "repair_or_quarantine_orchestrator_error_receipts": {
            "short_label": "orchestrator_error",
            "owner_surface": "orchestrator",
            "disposition": "repair_or_historical_quarantine_required",
            "operator_decision_required": True,
            "required_evidence": [
                "fresh orchestrator execution-error receipts carry idempotency, mission, and artifact truth",
                "historical execution-error debt is repaired or explicitly quarantined",
                "runtime_receipt_coverage_report records the residual historical policy",
            ],
        },
        "inspect_orchestrator_fanout_success_receipt_fields": {
            "short_label": "fanout_success",
            "owner_surface": "orchestrator.fan_out",
            "disposition": "producer_repair_required",
            "operator_decision_required": False,
            "required_evidence": [
                "fan-out success path stamps mission and idempotency fields before lifecycle writes",
                "fresh fan-out success proof joins idempotency_records",
                "fresh fan-out success proof carries artifact evidence or explicit no-artifact reason",
            ],
        },
        "quarantine_fixture_debt_or_exclude_from_production_gate": {
            "short_label": "fixture_quarantine",
            "owner_surface": "test_fixtures",
            "disposition": "quarantine_candidate",
            "operator_decision_required": True,
            "required_evidence": [
                "fixture-shaped rows are proven non-production and cannot recur in live runtime",
                "test/runtime DB isolation remains enforced",
                "production gate documents the quarantine boundary without hiding live debt",
            ],
        },
        "prove_fresh_dropoff_clean_then_quarantine_historical_debt": {
            "short_label": "dropoff_fresh_proof",
            "owner_surface": "orchestrator.dispatch_dropoff",
            "disposition": "fresh_proof_then_historical_quarantine",
            "operator_decision_required": True,
            "required_evidence": [
                "fresh dispatch_dropoff proof carries idempotency, mission, and no-artifact truth",
                "fresh non-fixture dropoff windows stay clean",
                "older dropoff debt is quarantined only after fresh proof is clean",
            ],
        },
        "prove_fresh_claim_timeout_clean_then_quarantine_historical_debt": {
            "short_label": "claim_timeout_proof",
            "owner_surface": "orchestrator.claim_timeout",
            "disposition": "fresh_proof_then_historical_quarantine",
            "operator_decision_required": True,
            "required_evidence": [
                "fresh claim_timeout proof carries idempotency, mission, and no-artifact truth",
                "fresh non-fixture claim_timeout windows stay clean",
                "older claim_timeout debt is quarantined only after fresh proof is clean",
            ],
        },
        "prove_fresh_long_timeout_clean_then_quarantine_historical_debt": {
            "short_label": "long_timeout_proof",
            "owner_surface": "orchestrator.long_timeout",
            "disposition": "fresh_proof_then_historical_quarantine",
            "operator_decision_required": True,
            "required_evidence": [
                "fresh long_timeout proof carries idempotency, mission, and no-artifact truth",
                "fresh non-fixture long_timeout windows stay clean",
                "older long_timeout debt is quarantined only after fresh proof is clean",
            ],
        },
        "inspect_producer_and_assign_owner": {
            "short_label": "assign_owner",
            "owner_surface": "unassigned_runtime_producer",
            "disposition": "owner_assignment_required",
            "operator_decision_required": False,
            "required_evidence": [
                "producer source is assigned to a concrete runtime owner",
                "owner adds repair or quarantine proof for future receipts",
            ],
        },
    }
    return policies.get(action, policies["inspect_producer_and_assign_owner"])


def _field_gap_action_proof_evidence(action: str) -> dict[str, Any]:
    evidence = FIELD_GAP_ACTION_PROOF_EVIDENCE.get(action)
    if evidence is None:
        return {
            "status": "fresh_proof_not_recorded",
            "proof_scope": "<unknown>",
            "proof_run_id": "<missing>",
            "proof_db": "<missing>",
            "evidence_ref": "<missing>",
            "remaining_action": "assign owner and record fresh proof before score movement",
            "score_effect": "no_score_change_until_required_evidence_passes",
        }
    result = dict(evidence)
    result["score_effect"] = "no_score_change_until_global_gate_passes"
    return result


def _field_gap_action_priority(action: str, active_head_missing: int) -> int:
    if action == "repair_installed_ds_goal_wrapper_or_pin_invocations":
        return 1
    if active_head_missing > 0:
        return 2
    priorities = {
        "repair_or_quarantine_orchestrator_error_receipts": 3,
        "inspect_orchestrator_fanout_success_receipt_fields": 4,
        "quarantine_fixture_debt_or_exclude_from_production_gate": 5,
        "prove_fresh_dropoff_clean_then_quarantine_historical_debt": 6,
        "prove_fresh_claim_timeout_clean_then_quarantine_historical_debt": 6,
        "prove_fresh_long_timeout_clean_then_quarantine_historical_debt": 6,
        "inspect_producer_and_assign_owner": 7,
    }
    return priorities.get(action, 9)


def _increment_summary_count(
    summary: dict[str, Any],
    section: str,
    key: Any,
    amount: int,
) -> None:
    bucket = summary.setdefault(section, {})
    bucket_key = str(key or "<unknown>")
    bucket[bucket_key] = int(bucket.get(bucket_key) or 0) + amount


def _field_gap_group_summary(groups: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "group_count": len(groups),
        "total_missing": 0,
        "active_head_missing": 0,
        "recent_historical_missing": 0,
        "older_historical_missing": 0,
        "unknown_freshness_missing": 0,
        "future_clock_skew_missing": 0,
        "quarantine_candidate_missing": 0,
        "by_freshness_class": {},
        "by_recommended_action": {},
        "by_gap_type": {},
        "by_receipt_type": {},
        "by_producer_source": {},
    }
    for group in groups:
        missing = int(group.get("missing") or 0)
        if missing <= 0:
            continue
        freshness = str(group.get("freshness_class") or "unknown")
        action = str(group.get("recommended_action") or "inspect_producer_and_assign_owner")
        summary["total_missing"] = int(summary["total_missing"]) + missing
        _increment_summary_count(summary, "by_freshness_class", freshness, missing)
        _increment_summary_count(summary, "by_recommended_action", action, missing)
        _increment_summary_count(summary, "by_gap_type", group.get("gap_type"), missing)
        _increment_summary_count(summary, "by_receipt_type", group.get("receipt_type"), missing)
        _increment_summary_count(
            summary,
            "by_producer_source",
            group.get("producer_source"),
            missing,
        )
        if freshness == "active_head_60m":
            summary["active_head_missing"] = int(summary["active_head_missing"]) + missing
        elif freshness == "recent_historical_24h":
            summary["recent_historical_missing"] = (
                int(summary["recent_historical_missing"]) + missing
            )
        elif freshness == "older_historical":
            summary["older_historical_missing"] = (
                int(summary["older_historical_missing"]) + missing
            )
        elif freshness == "future_clock_skew":
            summary["future_clock_skew_missing"] = (
                int(summary["future_clock_skew_missing"]) + missing
            )
        else:
            summary["unknown_freshness_missing"] = (
                int(summary["unknown_freshness_missing"]) + missing
            )
        if "quarantine" in action:
            summary["quarantine_candidate_missing"] = (
                int(summary["quarantine_candidate_missing"]) + missing
            )
    return summary


def _field_gap_action_queue(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: dict[str, dict[str, Any]] = {}
    for group in groups:
        missing = int(group.get("missing") or 0)
        if missing <= 0:
            continue
        action = str(group.get("recommended_action") or "inspect_producer_and_assign_owner")
        item = actions.setdefault(
            action,
            {
                "action": action,
                "missing": 0,
                "group_count": 0,
                "active_head_missing": 0,
                "recent_historical_missing": 0,
                "older_historical_missing": 0,
                "by_freshness_class": {},
                "by_gap_type": {},
                "by_producer_source": {},
                "top_group": {},
            },
        )
        item["missing"] = int(item["missing"]) + missing
        item["group_count"] = int(item["group_count"]) + 1
        freshness = str(group.get("freshness_class") or "unknown")
        _increment_summary_count(item, "by_freshness_class", freshness, missing)
        _increment_summary_count(item, "by_gap_type", group.get("gap_type"), missing)
        _increment_summary_count(item, "by_producer_source", group.get("producer_source"), missing)
        if freshness == "active_head_60m":
            item["active_head_missing"] = int(item["active_head_missing"]) + missing
        elif freshness == "recent_historical_24h":
            item["recent_historical_missing"] = (
                int(item["recent_historical_missing"]) + missing
            )
        elif freshness == "older_historical":
            item["older_historical_missing"] = int(item["older_historical_missing"]) + missing
        top_group = item.get("top_group") if isinstance(item.get("top_group"), dict) else {}
        if missing > int(top_group.get("missing") or 0):
            item["top_group"] = {
                "gap_type": group.get("gap_type"),
                "receipt_type": group.get("receipt_type"),
                "producer_source": group.get("producer_source"),
                "producer_failure_code": group.get("producer_failure_code"),
                "topology": group.get("topology"),
                "identifier_shape": group.get("identifier_shape"),
                "missing": missing,
                "freshness_class": freshness,
                "latest_created_at": group.get("latest_created_at"),
                "sample_agent_id": group.get("sample_agent_id"),
                "sample_task_id": group.get("sample_task_id"),
            }
    queue: list[dict[str, Any]] = []
    for action, item in actions.items():
        policy = _field_gap_action_policy(action)
        item.update(policy)
        item["priority"] = _field_gap_action_priority(
            action,
            int(item.get("active_head_missing") or 0),
        )
        item["score_effect"] = "no_score_change_until_required_evidence_passes"
        item["fresh_proof"] = _field_gap_action_proof_evidence(action)
        queue.append(item)
    return sorted(
        queue,
        key=lambda item: (
            int(item.get("priority") or 99),
            -int(item.get("active_head_missing") or 0),
            -int(item.get("missing") or 0),
            str(item.get("action") or ""),
        ),
    )


def _test_runtime_db_isolation_evidence() -> dict[str, Any]:
    path = _REPO_ROOT / "tests" / "conftest.py"
    evidence: dict[str, Any] = {
        "path": "tests/conftest.py",
        "present": path.exists(),
        "redirects_dharma_runtime_db": False,
        "redirects_dgc_ledger_dir": False,
        "patches_default_runtime_db": False,
        "enforced": False,
    }
    if not path.exists():
        return evidence
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return evidence
    evidence["redirects_dharma_runtime_db"] = "DHARMA_RUNTIME_DB" in text
    evidence["redirects_dgc_ledger_dir"] = "DGC_LEDGER_DIR" in text
    evidence["patches_default_runtime_db"] = (
        "dharma_swarm.runtime_state.DEFAULT_RUNTIME_DB" in text
    )
    evidence["enforced"] = bool(
        evidence["redirects_dharma_runtime_db"]
        and evidence["redirects_dgc_ledger_dir"]
        and evidence["patches_default_runtime_db"]
    )
    return evidence


def _fixture_quarantine_policy(groups: list[dict[str, Any]]) -> dict[str, Any]:
    fixture_groups = [
        group for group in groups if str(group.get("identifier_shape") or "") == "fixture_shaped"
    ]
    candidate_missing = sum(int(group.get("missing") or 0) for group in fixture_groups)
    isolation = _test_runtime_db_isolation_evidence()
    policy = _field_gap_action_policy("quarantine_fixture_debt_or_exclude_from_production_gate")
    summary = _field_gap_group_summary(fixture_groups)
    active_head_missing = int(summary.get("active_head_missing") or 0)
    blockers: list[str] = []
    if candidate_missing > 0:
        blockers.append("fixture-shaped debt is only a candidate and is not excluded")
        blockers.append("explicit operator quarantine acceptance is not recorded")
    if active_head_missing > 0:
        blockers.append("fixture-shaped rows appear in active-head windows")
    if candidate_missing > 0 and not bool(isolation.get("enforced")):
        blockers.append("test runtime DB isolation evidence is incomplete")
    status = "no_fixture_candidates"
    if candidate_missing > 0:
        status = "candidate_not_applied"
    return {
        "status": status,
        "applies_to_score_gate": False,
        "candidate_missing": candidate_missing,
        "candidate_group_count": len(fixture_groups),
        "active_head_missing": active_head_missing,
        "recent_historical_missing": summary.get("recent_historical_missing", 0),
        "older_historical_missing": summary.get("older_historical_missing", 0),
        "by_freshness_class": summary.get("by_freshness_class", {}),
        "by_gap_type": summary.get("by_gap_type", {}),
        "top_group": fixture_groups[0] if fixture_groups else {},
        "test_runtime_db_isolation": isolation,
        "eligible_after_operator_decision": bool(
            candidate_missing > 0
            and active_head_missing == 0
            and bool(isolation.get("enforced"))
        ),
        "operator_decision_required": candidate_missing > 0,
        "owner_surface": policy["owner_surface"],
        "required_evidence": policy["required_evidence"],
        "blockers": blockers,
    }


def _major_field_gap_producer_groups(
    rows: list[dict[str, Any]],
    *,
    anchor_created_at: str = "",
    limit: int | None = 15,
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        payload = _safe_json(row.get("payload_json"))
        gap_types: list[str] = []
        if not int(row.get("has_idempotency_record") or 0):
            gap_types.append("idempotency_record")
        if not _payload_has_mission(payload):
            gap_types.append("mission_payload")
        if (
            not int(row.get("has_artifact_record") or 0)
            and not _payload_has_artifact_ref(payload)
            and not _payload_has_explicit_absence(payload, "artifact_refs")
        ):
            gap_types.append("artifact_evidence")
        if not gap_types:
            continue

        producer_context = _producer_context_for_receipt(
            row,
            payload,
            inferred_failure_code=DS_GOAL_INFERRED_SIDE_EFFECT_FAILURE_CODE,
        )
        producer_source = producer_context.get("producer_source") or "<unknown>"
        producer_failure = producer_context.get("producer_failure_code") or "<none>"
        topology = producer_context.get("topology") or "<blank>"
        identifier_shape = _identifier_shape(row.get("agent_id"), row.get("task_id"))
        for gap_type in gap_types:
            key = (
                gap_type,
                str(row.get("receipt_type") or ""),
                producer_source,
                producer_failure,
                topology,
                identifier_shape,
            )
            group = groups.setdefault(
                key,
                {
                    "gap_type": gap_type,
                    "receipt_type": str(row.get("receipt_type") or ""),
                    "producer_source": producer_source,
                    "producer_failure_code": producer_failure,
                    "topology": topology,
                    "identifier_shape": identifier_shape,
                    "missing": 0,
                    "latest_created_at": str(row.get("created_at") or ""),
                    "sample_agent_id": str(row.get("agent_id") or ""),
                    "sample_task_id": str(row.get("task_id") or ""),
                    "sample_run_id": str(row.get("run_id") or ""),
                },
            )
            group["missing"] += 1
            if str(row.get("created_at") or "") > str(group.get("latest_created_at") or ""):
                group["latest_created_at"] = str(row.get("created_at") or "")
                group["sample_agent_id"] = str(row.get("agent_id") or "")
                group["sample_task_id"] = str(row.get("task_id") or "")
                group["sample_run_id"] = str(row.get("run_id") or "")

    sorted_groups = sorted(
        groups.values(),
        key=lambda item: (
            -int(item["missing"]),
            item["gap_type"],
            item["receipt_type"],
            item["producer_source"],
            item["producer_failure_code"],
            item["topology"],
            item["identifier_shape"],
        ),
    )
    if limit is not None:
        sorted_groups = sorted_groups[: max(1, limit)]
    for group in sorted_groups:
        freshness, age_minutes = _field_gap_freshness_class(
            str(group.get("latest_created_at") or ""),
            anchor_created_at=anchor_created_at,
        )
        group["freshness_class"] = freshness
        group["age_minutes_from_head"] = age_minutes
        group["recommended_action"] = _field_gap_recommended_action(group)
    return sorted_groups


def _top_missing_side_effect_groups(
    db: sqlite3.Connection,
    *,
    where: str,
    params: tuple[Any, ...],
    limit: int = 10,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in db.execute(
            f"""
            SELECT
              receipt_type,
              agent_id,
              COUNT(*) AS total,
              SUM(CASE
                WHEN side_effect_key IS NULL OR side_effect_key = ''
                THEN 1 ELSE 0 END
              ) AS missing_side_effect_key
            FROM runtime_receipts
            WHERE {where}
            GROUP BY receipt_type, agent_id
            HAVING missing_side_effect_key > 0
            ORDER BY missing_side_effect_key DESC, total DESC, receipt_type ASC, agent_id ASC
            LIMIT ?
            """,
            (*params, max(1, limit)),
        )
    ]


def _side_effect_key_gap_by_type(
    db: sqlite3.Connection,
    *,
    where: str,
    params: tuple[Any, ...],
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in db.execute(
            f"""
            SELECT
              receipt_type,
              COUNT(*) AS total,
              SUM(CASE
                WHEN side_effect_key IS NULL OR side_effect_key = ''
                THEN 1 ELSE 0 END
              ) AS missing_side_effect_key
            FROM runtime_receipts
            WHERE {where}
            GROUP BY receipt_type
            HAVING missing_side_effect_key > 0
            ORDER BY missing_side_effect_key DESC, total DESC, receipt_type ASC
            """,
            params,
        )
    ]


def _latest_side_effect_key_gap_sample(
    db: sqlite3.Connection,
    *,
    where: str,
    params: tuple[Any, ...],
    limit: int = 10,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in db.execute(
            f"""
            SELECT
              receipt_id,
              receipt_type,
              run_id,
              task_id,
              agent_id,
              status,
              created_at
            FROM runtime_receipts
            WHERE ({where})
              AND (side_effect_key IS NULL OR side_effect_key = '')
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (*params, max(1, limit)),
        )
    ]


def _latest_side_effect_key_gap_diagnostics(
    db: sqlite3.Connection,
    *,
    where: str,
    params: tuple[Any, ...],
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in db.execute(
        f"""
        SELECT
          rr.receipt_id,
          rr.receipt_type,
          rr.run_id,
          rr.task_id,
          rr.agent_id,
          rr.status,
          rr.created_at,
          dr.session_id AS delegation_session_id,
          dr.claim_id AS delegation_claim_id,
          dr.status AS delegation_status,
          dr.failure_code AS delegation_failure_code,
          dr.metadata_json AS delegation_metadata_json,
          (
            SELECT tc.claim_id
            FROM task_claims tc
            WHERE (dr.claim_id != '' AND tc.claim_id = dr.claim_id)
               OR (rr.task_id != '' AND tc.task_id = rr.task_id
                   AND rr.agent_id != '' AND tc.agent_id = rr.agent_id)
            ORDER BY tc.claimed_at DESC
            LIMIT 1
          ) AS task_claim_id,
          (
            SELECT tc.session_id
            FROM task_claims tc
            WHERE (dr.claim_id != '' AND tc.claim_id = dr.claim_id)
               OR (rr.task_id != '' AND tc.task_id = rr.task_id
                   AND rr.agent_id != '' AND tc.agent_id = rr.agent_id)
            ORDER BY tc.claimed_at DESC
            LIMIT 1
          ) AS task_claim_session_id,
          (
            SELECT tc.status
            FROM task_claims tc
            WHERE (dr.claim_id != '' AND tc.claim_id = dr.claim_id)
               OR (rr.task_id != '' AND tc.task_id = rr.task_id
                   AND rr.agent_id != '' AND tc.agent_id = rr.agent_id)
            ORDER BY tc.claimed_at DESC
            LIMIT 1
          ) AS task_claim_status,
          (
            SELECT tc.metadata_json
            FROM task_claims tc
            WHERE (dr.claim_id != '' AND tc.claim_id = dr.claim_id)
               OR (rr.task_id != '' AND tc.task_id = rr.task_id
                   AND rr.agent_id != '' AND tc.agent_id = rr.agent_id)
            ORDER BY tc.claimed_at DESC
            LIMIT 1
          ) AS task_claim_metadata_json
        FROM runtime_receipts rr
        LEFT JOIN delegation_runs dr
          ON rr.run_id != '' AND rr.run_id = dr.run_id
        WHERE ({where})
          AND (rr.side_effect_key IS NULL OR rr.side_effect_key = '')
        ORDER BY rr.created_at DESC, rr.receipt_id DESC
        LIMIT ?
        """,
        (*params, max(1, limit)),
    ):
        data = dict(row)
        delegation_metadata = _safe_json(data.pop("delegation_metadata_json", ""))
        claim_metadata = _safe_json(data.pop("task_claim_metadata_json", ""))
        hints = _metadata_hints(delegation_metadata, claim_metadata)
        data["identifier_shape"] = _identifier_shape(data.get("agent_id"), data.get("task_id"))
        data["session_id"] = _first_present(
            data.pop("delegation_session_id", ""),
            data.pop("task_claim_session_id", ""),
        )
        data["claim_id"] = _first_present(
            data.pop("delegation_claim_id", ""),
            data.pop("task_claim_id", ""),
        )
        producer_context = _side_effect_gap_producer_context(
            run_id=data.get("run_id"),
            session_id=data.get("session_id"),
            delegation_failure_code=data.get("delegation_failure_code"),
            hints=hints,
        )
        data["producer_source"] = producer_context["producer_source"]
        data["producer_failure_code"] = producer_context["producer_failure_code"]
        data["producer_error"] = _first_present(hints.get("error"), "")
        data["runtime_db_path"] = _first_present(hints.get("runtime_db_path"), "")
        data["topology"] = producer_context["topology"]
        data["metadata_hints"] = producer_context["metadata_hints"]
        rows.append(data)
    return rows


def _side_effect_key_gap_producer_groups(
    db: sqlite3.Connection,
    *,
    where: str,
    params: tuple[Any, ...],
    limit: int = 10,
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for row in db.execute(
        f"""
        SELECT
          rr.receipt_id,
          rr.receipt_type,
          rr.run_id,
          rr.task_id,
          rr.agent_id,
          rr.status,
          rr.created_at,
          dr.session_id AS delegation_session_id,
          dr.failure_code AS delegation_failure_code,
          dr.metadata_json AS delegation_metadata_json,
          (
            SELECT tc.session_id
            FROM task_claims tc
            WHERE (dr.claim_id != '' AND tc.claim_id = dr.claim_id)
               OR (rr.task_id != '' AND tc.task_id = rr.task_id
                   AND rr.agent_id != '' AND tc.agent_id = rr.agent_id)
            ORDER BY tc.claimed_at DESC
            LIMIT 1
          ) AS task_claim_session_id,
          (
            SELECT tc.metadata_json
            FROM task_claims tc
            WHERE (dr.claim_id != '' AND tc.claim_id = dr.claim_id)
               OR (rr.task_id != '' AND tc.task_id = rr.task_id
                   AND rr.agent_id != '' AND tc.agent_id = rr.agent_id)
            ORDER BY tc.claimed_at DESC
            LIMIT 1
          ) AS task_claim_metadata_json
        FROM runtime_receipts rr
        LEFT JOIN delegation_runs dr
          ON rr.run_id != '' AND rr.run_id = dr.run_id
        WHERE ({where})
          AND (rr.side_effect_key IS NULL OR rr.side_effect_key = '')
        """,
        params,
    ):
        data = dict(row)
        delegation_metadata = _safe_json(data.pop("delegation_metadata_json", ""))
        claim_metadata = _safe_json(data.pop("task_claim_metadata_json", ""))
        hints = _metadata_hints(delegation_metadata, claim_metadata)
        session_id = _first_present(
            data.pop("delegation_session_id", ""),
            data.pop("task_claim_session_id", ""),
        )
        producer_context = _side_effect_gap_producer_context(
            run_id=data.get("run_id"),
            session_id=session_id,
            delegation_failure_code=data.get("delegation_failure_code"),
            hints=hints,
        )
        producer_source = str(_first_present(producer_context["producer_source"], "<unknown>"))
        producer_failure_code = str(
            _first_present(producer_context["producer_failure_code"], "<none>")
        )
        topology = str(_first_present(producer_context["topology"], "<blank>"))
        identifier_shape = _identifier_shape(data.get("agent_id"), data.get("task_id"))
        key = (
            str(data["receipt_type"]),
            producer_source,
            producer_failure_code,
            topology,
            identifier_shape,
        )
        group = groups.setdefault(
            key,
            {
                "receipt_type": data["receipt_type"],
                "producer_source": producer_source,
                "producer_failure_code": producer_failure_code,
                "topology": topology,
                "identifier_shape": identifier_shape,
                "missing_side_effect_key": 0,
                "latest_created_at": "",
                "sample_run_id": "",
                "sample_task_id": "",
                "sample_agent_id": "",
                "sample_status": "",
            },
        )
        group["missing_side_effect_key"] += 1
        if str(data["created_at"]) > str(group["latest_created_at"]):
            group.update(
                latest_created_at=data["created_at"],
                sample_run_id=data["run_id"],
                sample_task_id=data["task_id"],
                sample_agent_id=data["agent_id"],
                sample_status=data["status"],
            )
    return sorted(
        groups.values(),
        key=lambda item: (
            -int(item["missing_side_effect_key"]),
            str(item["receipt_type"]),
            str(item["producer_source"]),
            str(item["producer_failure_code"]),
            str(item["topology"]),
            str(item["identifier_shape"]),
        ),
    )[: max(1, limit)]


def _side_effect_key_gap_recent_windows(
    db: sqlite3.Connection,
    *,
    where: str,
    params: tuple[Any, ...],
    anchor_created_at: str,
    windows_minutes: tuple[int, ...] = RECENT_WINDOW_MINUTES,
) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    if not anchor_created_at:
        return windows
    for minutes in windows_minutes:
        cutoff = _created_at_cutoff(anchor_created_at, minutes)
        if cutoff is None:
            continue
        window_where = f"({where}) AND rr.created_at >= ?"
        window_params = (*params, cutoff)
        total = int(
            db.execute(
                f"SELECT COUNT(*) FROM runtime_receipts rr WHERE {window_where}",
                window_params,
            ).fetchone()[0]
        )
        missing = int(
            db.execute(
                f"""
                SELECT COUNT(*)
                FROM runtime_receipts rr
                WHERE {window_where}
                  AND (rr.side_effect_key IS NULL OR rr.side_effect_key = '')
                """,
                window_params,
            ).fetchone()[0]
        )
        windows.append(
            {
                "window_minutes": minutes,
                "anchor_created_at": anchor_created_at,
                "cutoff_created_at": cutoff,
                "total": total,
                "missing_side_effect_key": missing,
                "missing_side_effect_key_percent": _percent(missing, total),
                "top_gap_producer_groups": _side_effect_key_gap_producer_groups(
                    db,
                    where=window_where,
                    params=window_params,
                    limit=3,
                ),
            }
        )
    return windows


def _active_head_side_effect_key_gate(windows: list[dict[str, Any]]) -> dict[str, Any]:
    if not windows:
        return {
            "gate": "active_head_side_effect_key_clean",
            "passed": False,
            "reason": "no recent receipt windows available",
            "windows_evaluated": [],
            "blocked_windows": [],
            "widest_window": {},
        }
    blocked_windows = [
        {
            "window_minutes": row["window_minutes"],
            "total": row["total"],
            "missing_side_effect_key": row["missing_side_effect_key"],
            "missing_side_effect_key_percent": row["missing_side_effect_key_percent"],
        }
        for row in windows
        if int(row.get("total", 0)) <= 0 or int(row.get("missing_side_effect_key", 0)) > 0
    ]
    widest = max(windows, key=lambda row: int(row["window_minutes"]))
    return {
        "gate": "active_head_side_effect_key_clean",
        "passed": not blocked_windows,
        "reason": (
            "recent DB-head windows have complete side_effect_key coverage"
            if not blocked_windows
            else "recent DB-head windows still contain blank side_effect_key receipts"
        ),
        "windows_evaluated": [row["window_minutes"] for row in windows],
        "blocked_windows": blocked_windows,
        "widest_window": {
            "window_minutes": widest["window_minutes"],
            "anchor_created_at": widest["anchor_created_at"],
            "total": widest["total"],
            "missing_side_effect_key": widest["missing_side_effect_key"],
            "missing_side_effect_key_percent": widest["missing_side_effect_key_percent"],
        },
    }


def _gate_status(passed: bool) -> str:
    return "pass" if passed else "fail"


def _runtime_field_gap_evidence(field_coverage: dict[str, Any]) -> str:
    missing = []
    for field, data in field_coverage.items():
        if not isinstance(data, dict):
            continue
        count = int(data.get("missing") or 0)
        if count > 0:
            missing.append(f"{field}:{count}")
    if missing:
        return "missing=" + "|".join(missing[:8])
    return f"missing=0 across {len(field_coverage)} runtime fields"


def _active_head_window_evidence(windows: list[dict[str, Any]]) -> str:
    parts = []
    for row in windows:
        if not isinstance(row, dict):
            continue
        parts.append(
            f"{row.get('window_minutes')}m="
            f"{int(row.get('missing_side_effect_key') or 0)}/"
            f"{int(row.get('total') or 0)}"
        )
    return "|".join(parts) if parts else "no_recent_windows"


def _gate_component(
    *,
    component_id: str,
    short_label: str,
    passed: bool,
    scope: str,
    required: str,
    evidence: str,
    blocker: str,
) -> dict[str, Any]:
    return {
        "id": component_id,
        "short_label": short_label,
        "passed": bool(passed),
        "status": _gate_status(bool(passed)),
        "scope": scope,
        "required": required,
        "evidence": evidence,
        "blocker": "" if passed else blocker,
    }


def _ds_goal_gap_context_present(
    side_effect_groups: list[dict[str, Any]],
    provider_model_groups: list[dict[str, Any]],
    side_effect_diagnostics: list[dict[str, Any]] | None = None,
) -> bool:
    rows = [*side_effect_groups, *provider_model_groups, *(side_effect_diagnostics or [])]
    return any(str(row.get("producer_source") or "") == DS_GOAL_INFERRED_SOURCE for row in rows)


def _live_census_ds_goal_context() -> dict[str, Any]:
    path = default_output_path()
    if not path.exists():
        return {
            "available": False,
            "state": "receipt_missing",
            "receipt": str(path),
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "state": "receipt_unreadable",
            "receipt": str(path),
            "evidence": str(exc),
        }
    validation_errors = validate_census_payload(payload)
    if validation_errors:
        return {
            "available": False,
            "state": "receipt_invalid",
            "receipt": str(path),
            "generated_at": str(payload.get("generated_at") or ""),
            "evidence": "; ".join(validation_errors),
        }
    surfaces = payload.get("surfaces") if isinstance(payload.get("surfaces"), list) else []
    surface = next(
        (
            item
            for item in surfaces
            if isinstance(item, dict)
            and str(item.get("id") or item.get("surface_id") or "") == "cli.ds_goal"
        ),
        {},
    )
    if not surface:
        return {
            "available": False,
            "state": "surface_missing",
            "receipt": str(path),
            "generated_at": str(payload.get("generated_at") or ""),
        }
    raw = surface.get("raw") if isinstance(surface.get("raw"), dict) else {}
    contract = (
        raw.get("installed_wrapper_contract")
        if isinstance(raw.get("installed_wrapper_contract"), dict)
        else {}
    )
    default_target = (
        raw.get("default_wrapper_target")
        if isinstance(raw.get("default_wrapper_target"), dict)
        else {}
    )
    hardening = (
        raw.get("target_sync_receipt_hardening")
        if isinstance(raw.get("target_sync_receipt_hardening"), dict)
        else {}
    )
    decision_packet = (
        raw.get("convergence_decision_packet")
        if isinstance(raw.get("convergence_decision_packet"), dict)
        else {}
    )
    preflight = (
        raw.get("longrun_preflight_gate")
        if isinstance(raw.get("longrun_preflight_gate"), dict)
        else {}
    )
    return {
        "available": True,
        "state": "bound",
        "receipt": str(path),
        "generated_at": str(payload.get("generated_at") or ""),
        "freshness": census_payload_freshness(payload),
        "status": str(surface.get("status") or ""),
        "proof_gaps": [str(item) for item in surface.get("proof_gaps") or []],
        "target_repo": str(raw.get("target_repo") or ""),
        "target_resolution_source": str(raw.get("target_resolution_source") or ""),
        "target_matches_current_repo": raw.get("target_matches_current_repo"),
        "default_target_repo": str(default_target.get("target_repo") or ""),
        "default_target_resolution_source": str(
            default_target.get("target_resolution_source") or ""
        ),
        "safe_current_checkout_invocation": str(
            raw.get("safe_current_checkout_invocation") or ""
        ),
        "target_sync_receipt_hardening_state": str(hardening.get("state") or ""),
        "wrapper_sha256": str(contract.get("wrapper_sha256") or ""),
        "dharma_swarm_repo_pin_supported": contract.get(
            "dharma_swarm_repo_pin_supported"
        ),
        "longrun_preflight_status": str(preflight.get("status") or ""),
        "longrun_preflight_allowed": preflight.get("longrun_start_allowed"),
        "convergence_decision_packet": decision_packet,
    }


def _ds_goal_cli_context_blockers(ds_goal_context: dict[str, Any]) -> list[str]:
    if not ds_goal_context:
        return []
    if not ds_goal_context.get("available"):
        return [
            "ds-goal CLI owner evidence is unavailable while ds-goal is an active runtime gap producer"
        ]

    blockers: list[str] = []
    proof_gaps = {
        str(item) for item in ds_goal_context.get("proof_gaps") or [] if str(item)
    }
    target_mismatch = (
        ds_goal_context.get("target_matches_current_repo") is False
        or "ds_goal_cli_target_repo_mismatch" in proof_gaps
    )
    if target_mismatch:
        blockers.append(
            "installed ds-goal wrapper default target does not match the audited checkout"
        )

    hardening_state = str(
        ds_goal_context.get("target_sync_receipt_hardening_state") or ""
    )
    target_lacks_hardening = (
        hardening_state == "sync_receipt_side_effect_keys_missing"
        or "ds_goal_cli_target_lacks_sync_side_effect_hardening" in proof_gaps
    )
    if target_lacks_hardening:
        blockers.append(
            "installed ds-goal wrapper target lacks sync side-effect-key hardening"
        )
    return blockers


def _summary_count_text(counts: Any) -> str:
    if not isinstance(counts, dict) or not counts:
        return "<none>"
    return "|".join(
        f"{key}={value}"
        for key, value in sorted(
            ((str(key), int(value or 0)) for key, value in counts.items()),
            key=lambda item: item[0],
        )
    )


def build_report(
    db_path: Path = DEFAULT_DB,
    *,
    latest_limit: int = 500,
    run_id: str = "",
    since_created_at: str = "",
) -> dict[str, Any]:
    scoped_run_id = str(run_id or "").strip()
    scoped_since_created_at = str(since_created_at or "").strip()
    db_path = db_path.expanduser()
    report: dict[str, Any] = {
        "report": "runtime_receipt_coverage_report",
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "scope": {
            "run_id": scoped_run_id,
            "since_created_at": scoped_since_created_at,
            "mode": _scope_mode(scoped_run_id, scoped_since_created_at),
        },
        "summary": {
            "readable": False,
            "required_tables_present": False,
            "score_gate_70_to_75": False,
        },
    }
    if not db_path.exists():
        report["error"] = "runtime db missing"
        return report

    try:
        db = _connect_readonly(db_path)
    except sqlite3.Error as exc:
        report["error"] = f"unable to open runtime db read-only: {exc}"
        return report

    with db:
        tables = {table: _table_exists(db, table) for table in REQUIRED_TABLES}
        missing_tables = [table for table, exists in tables.items() if not exists]
        report["tables"] = tables
        report["missing_tables"] = missing_tables
        report["summary"]["readable"] = True
        report["summary"]["required_tables_present"] = not missing_tables
        if missing_tables:
            report["error"] = "required runtime tables missing"
            return report

        counts = {table: _count(db, table) for table in REQUIRED_TABLES}
        receipt_scope, receipt_params = _with_receipt_scope(
            "1=1",
            run_id=scoped_run_id,
            since_created_at=scoped_since_created_at,
        )
        if scoped_since_created_at:
            delegation_scope = (
                "run_id IN ("
                f"SELECT DISTINCT run_id FROM runtime_receipts WHERE {receipt_scope}"
                " AND run_id != ''"
                ")"
            )
            delegation_params = receipt_params
        else:
            delegation_scope, delegation_params = _with_run_scope("1=1", scoped_run_id)
        rr_major_filter, rr_major_params = _with_receipt_scope(
            _major_task_receipt_filter(),
            run_id=scoped_run_id,
            since_created_at=scoped_since_created_at,
            alias="rr",
        )
        rr_receipt_scope, rr_receipt_params = _with_receipt_scope(
            "1=1",
            run_id=scoped_run_id,
            since_created_at=scoped_since_created_at,
            alias="rr",
        )
        major_filter, major_params = _with_receipt_scope(
            _major_task_receipt_filter(),
            run_id=scoped_run_id,
            since_created_at=scoped_since_created_at,
        )
        delegation_with_receipt_json = _count(
            db,
            "delegation_runs",
            f"({delegation_scope}) AND receipt_json IS NOT NULL AND receipt_json != ''",
            delegation_params,
        )
        delegation_with_artifact_ref = _count(
            db,
            "delegation_runs",
            f"({delegation_scope}) AND current_artifact_id IS NOT NULL AND current_artifact_id != ''",
            delegation_params,
        )
        delegation_with_metadata_mission = 0
        for row in db.execute(
            f"SELECT metadata_json FROM delegation_runs WHERE {delegation_scope}",
            delegation_params,
        ):
            if _payload_has_mission(_safe_json(row["metadata_json"])):
                delegation_with_metadata_mission += 1

        runtime_field_coverage = _field_coverage(
            db,
            "runtime_receipts",
            CORE_RECEIPT_FIELDS,
            where=receipt_scope,
            params=receipt_params,
        )
        scoped_receipt_total = _count(db, "runtime_receipts", receipt_scope, receipt_params)
        scoped_delegation_total = _count(db, "delegation_runs", delegation_scope, delegation_params)
        major_total = _count(db, "runtime_receipts", major_filter, major_params)
        major_with_idempotency_fields = _count(
            db,
            "runtime_receipts",
            f"{major_filter} AND idempotency_key != '' AND side_effect_key != ''",
            major_params,
        )
        major_with_matching_idempotency = int(
            db.execute(
                f"""
                SELECT COUNT(*)
                FROM runtime_receipts rr
                JOIN idempotency_records ir
                  ON rr.idempotency_key = ir.idempotency_key
                 AND rr.side_effect_key = ir.side_effect_key
                WHERE {rr_major_filter}
                  AND rr.idempotency_key != ''
                  AND rr.side_effect_key != ''
                """,
                rr_major_params,
            ).fetchone()[0]
        )
        major_with_artifact_record = int(
            db.execute(
                f"""
                SELECT COUNT(DISTINCT rr.receipt_id)
                FROM runtime_receipts rr
                JOIN artifact_records ar
                  ON (rr.run_id != '' AND rr.run_id = ar.run_id)
                  OR (rr.task_id != '' AND rr.task_id = ar.task_id)
                WHERE {rr_major_filter}
                """,
                rr_major_params,
            ).fetchone()[0]
        )

        type_status = [
            dict(row)
            for row in db.execute(
                f"""
                SELECT receipt_type, status, COUNT(*) AS n
                FROM runtime_receipts
                WHERE {receipt_scope}
                GROUP BY receipt_type, status
                ORDER BY n DESC, receipt_type ASC, status ASC
                LIMIT 50
                """,
                receipt_params,
            )
        ]
        latest_rows = [
            dict(row)
            for row in db.execute(
                f"""
                SELECT receipt_id, receipt_type, run_id, task_id, trace_id,
                       correlation_id, agent_id, idempotency_key, side_effect_key,
                       status, payload_json, created_at
                FROM runtime_receipts
                WHERE {receipt_scope}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*receipt_params, max(1, latest_limit)),
            )
        ]
        no_provider_context_keys = _no_provider_context_keys(latest_rows)
        latest_major = [row for row in latest_rows if row["receipt_type"] in MAJOR_TASK_RECEIPT_TYPES]
        latest_payload_parse_errors = 0
        latest_major_with_mission = 0
        latest_major_with_artifact_payload = 0
        latest_major_with_explicit_no_artifact = 0
        latest_major_with_provider = 0
        latest_major_with_model = 0
        latest_major_with_provider_model = 0
        latest_major_with_provider_model_provenance = 0
        latest_major_with_provider_model_accounted = 0
        latest_terminal_major_total = 0
        latest_terminal_major_with_provider = 0
        latest_terminal_major_with_model = 0
        latest_terminal_major_with_provider_model = 0
        latest_terminal_major_with_provider_model_provenance = 0
        latest_terminal_major_with_provider_model_accounted = 0
        latest_provider_model_class_breakdown: dict[str, int] = {}
        latest_terminal_provider_model_class_breakdown: dict[str, int] = {}
        latest_provider_model_unproven_sample: list[dict[str, Any]] = []
        latest_terminal_provider_model_unproven_sample: list[dict[str, Any]] = []
        latest_provider_model_pending_execution = 0
        latest_major_status_breakdown: dict[str, int] = {}
        latest_with_ds_goal_preflight_payload = 0
        latest_ds_goal_preflight_status_breakdown: dict[str, int] = {}
        latest_ds_goal_preflight_sample: list[dict[str, Any]] = []
        for row in latest_major:
            payload = _safe_json(row.get("payload_json"))
            status = str(row.get("status") or "").strip()
            status_key = status or "<blank>"
            latest_major_status_breakdown[status_key] = (
                latest_major_status_breakdown.get(status_key, 0) + 1
            )
            ds_goal_preflight = payload.get("ds_goal_longrun_preflight")
            if isinstance(ds_goal_preflight, dict):
                latest_with_ds_goal_preflight_payload += 1
                preflight_status = str(ds_goal_preflight.get("status") or "<blank>")
                latest_ds_goal_preflight_status_breakdown[preflight_status] = (
                    latest_ds_goal_preflight_status_breakdown.get(
                        preflight_status,
                        0,
                    )
                    + 1
                )
                if len(latest_ds_goal_preflight_sample) < 5:
                    latest_ds_goal_preflight_sample.append(
                        {
                            "receipt_id": row.get("receipt_id", ""),
                            "receipt_type": row.get("receipt_type", ""),
                            "run_id": row.get("run_id", ""),
                            "task_id": row.get("task_id", ""),
                            "preflight_status": preflight_status,
                            "preflight_passed": ds_goal_preflight.get("passed")
                            is True,
                            "default_target_repo": str(
                                ds_goal_preflight.get("default_target_repo") or ""
                            ),
                            "repo_pin_source": str(
                                ds_goal_preflight.get("repo_pin_source") or ""
                            ),
                            "score_effect": str(
                                ds_goal_preflight.get("score_effect") or ""
                            ),
                        }
                    )
            is_terminal = _is_terminal_receipt_status(status)
            if not is_terminal:
                latest_provider_model_pending_execution += 1
            latest_payload_parse_errors += int(bool(payload.get("_parse_error")))
            latest_major_with_mission += int(_payload_has_mission(payload))
            latest_major_with_artifact_payload += int(_payload_has_artifact_ref(payload))
            latest_major_with_explicit_no_artifact += int(
                _payload_has_explicit_absence(payload, "artifact_refs")
            )
            has_provider = _payload_has_provider(payload)
            has_model = _payload_has_model(payload)
            latest_major_with_provider += int(has_provider)
            latest_major_with_model += int(has_model)
            latest_major_with_provider_model += int(has_provider and has_model)
            producer_context = _producer_context_for_receipt(row, payload)
            provider_model_class = _provider_model_payload_class_for_status(
                payload,
                status,
                producer_context,
                _receipt_key(row) in no_provider_context_keys,
            )
            latest_provider_model_class_breakdown[provider_model_class] = (
                latest_provider_model_class_breakdown.get(provider_model_class, 0) + 1
            )
            has_provenance = (
                provider_model_class in PROVIDER_MODEL_PROVENANCE_CLASSES
                or _payload_has_provider_model_provenance(payload)
                or (
                    provider_model_class == "pending_execution"
                    and _payload_declares_pending_provider_execution(payload)
                )
            )
            latest_major_with_provider_model_provenance += int(has_provenance)
            latest_major_with_provider_model_accounted += int(has_provenance)
            if is_terminal:
                latest_terminal_major_total += 1
                latest_terminal_major_with_provider += int(has_provider)
                latest_terminal_major_with_model += int(has_model)
                latest_terminal_major_with_provider_model += int(has_provider and has_model)
                latest_terminal_major_with_provider_model_provenance += int(has_provenance)
                latest_terminal_major_with_provider_model_accounted += int(
                    has_provenance
                )
                latest_terminal_provider_model_class_breakdown[
                    provider_model_class
                ] = (
                    latest_terminal_provider_model_class_breakdown.get(
                        provider_model_class,
                        0,
                    )
                    + 1
                )
            if not has_provenance and len(latest_provider_model_unproven_sample) < 10:
                sample = {
                    "receipt_id": row.get("receipt_id", ""),
                    "receipt_type": row.get("receipt_type", ""),
                    "run_id": row.get("run_id", ""),
                    "task_id": row.get("task_id", ""),
                    "agent_id": row.get("agent_id", ""),
                    "created_at": row.get("created_at", ""),
                    "provider_model_payload_class": provider_model_class,
                    "provider_model_truth_source": (
                        "<pending>"
                        if provider_model_class == "pending_execution"
                        else _provider_model_truth_source(payload)
                    ),
                    "has_provider_payload": has_provider,
                    "has_model_payload": has_model,
                }
                if producer_context["producer_source"]:
                    sample["receipt_producer_source"] = producer_context["producer_source"]
                    sample["receipt_producer_failure_code"] = (
                        producer_context["producer_failure_code"]
                    )
                    sample["receipt_producer_topology"] = producer_context["topology"]
                latest_provider_model_unproven_sample.append(sample)
                if is_terminal and len(latest_terminal_provider_model_unproven_sample) < 10:
                    latest_terminal_provider_model_unproven_sample.append(sample)

        latest_provider_model_unproven_producer_groups = (
            _provider_model_unproven_producer_groups(
                latest_major,
                no_provider_context_keys,
            )
        )
        latest_terminal_major = [
            row for row in latest_major if _is_terminal_receipt_status(row.get("status"))
        ]
        latest_terminal_provider_model_unproven_producer_groups = (
            _provider_model_unproven_producer_groups(
                latest_terminal_major,
                no_provider_context_keys,
            )
        )
        latest_sample = [
            {key: value for key, value in row.items() if key != "payload_json"}
            for row in latest_rows[:10]
        ]
        latest_created_at = latest_rows[0]["created_at"] if latest_rows else ""
        major_type_breakdown = _major_type_breakdown(
            db,
            where=rr_major_filter,
            params=rr_major_params,
        )
        major_field_gap_rows = [
            dict(row)
            for row in db.execute(
                f"""
                SELECT
                  rr.receipt_id,
                  rr.receipt_type,
                  rr.run_id,
                  rr.task_id,
                  rr.trace_id,
                  rr.correlation_id,
                  rr.agent_id,
                  rr.idempotency_key,
                  rr.side_effect_key,
                  rr.status,
                  rr.payload_json,
                  rr.created_at,
                  dr.session_id AS delegation_session_id,
                  dr.failure_code AS delegation_failure_code,
                  dr.metadata_json AS delegation_metadata_json,
                  EXISTS(
                    SELECT 1
                    FROM idempotency_records ir
                    WHERE rr.idempotency_key != ''
                      AND rr.side_effect_key != ''
                      AND rr.idempotency_key = ir.idempotency_key
                      AND rr.side_effect_key = ir.side_effect_key
                  ) AS has_idempotency_record,
                  EXISTS(
                    SELECT 1
                    FROM artifact_records ar
                    WHERE (rr.run_id != '' AND rr.run_id = ar.run_id)
                       OR (rr.task_id != '' AND rr.task_id = ar.task_id)
                  ) AS has_artifact_record
                FROM runtime_receipts rr
                LEFT JOIN delegation_runs dr
                  ON rr.run_id != ''
                 AND rr.run_id = dr.run_id
                WHERE {rr_major_filter}
                ORDER BY rr.created_at DESC
                """,
                rr_major_params,
            )
        ]
        all_major_field_gap_producer_groups = _major_field_gap_producer_groups(
            major_field_gap_rows,
            anchor_created_at=latest_created_at,
            limit=None,
        )
        major_field_gap_producer_groups = all_major_field_gap_producer_groups[:15]
        major_field_gap_summary = _field_gap_group_summary(
            all_major_field_gap_producer_groups
        )
        major_field_gap_action_queue = _field_gap_action_queue(
            all_major_field_gap_producer_groups
        )
        fixture_quarantine_policy = _fixture_quarantine_policy(
            all_major_field_gap_producer_groups
        )
        side_effect_key_gap_by_type = _side_effect_key_gap_by_type(
            db,
            where=receipt_scope,
            params=receipt_params,
        )
        latest_side_effect_key_gap_sample = _latest_side_effect_key_gap_sample(
            db,
            where=receipt_scope,
            params=receipt_params,
        )
        latest_side_effect_key_gap_diagnostics = _latest_side_effect_key_gap_diagnostics(
            db,
            where=rr_receipt_scope,
            params=rr_receipt_params,
        )
        side_effect_key_gap_producer_groups = _side_effect_key_gap_producer_groups(
            db,
            where=rr_receipt_scope,
            params=rr_receipt_params,
        )
        ds_goal_cli_context = (
            _live_census_ds_goal_context()
            if _ds_goal_gap_context_present(
                side_effect_key_gap_producer_groups,
                latest_provider_model_unproven_producer_groups,
                latest_side_effect_key_gap_diagnostics,
            )
            else {}
        )
        recent_side_effect_key_gap_windows = _side_effect_key_gap_recent_windows(
            db,
            where=rr_receipt_scope,
            params=rr_receipt_params,
            anchor_created_at=latest_created_at,
        )
        active_head_side_effect_key_gate = _active_head_side_effect_key_gate(
            recent_side_effect_key_gap_windows
        )
        top_missing_side_effect_groups = _top_missing_side_effect_groups(
            db,
            where=major_filter,
            params=major_params,
        )

        idempotency_match_ok = (
            major_total > 0
            and major_with_idempotency_fields == major_total
            and major_with_matching_idempotency == major_total
        )
        mission_ok = major_total > 0 and latest_major_with_mission == len(latest_major)
        artifact_ok = (
            major_total > 0
            and (
                major_with_artifact_record == major_total
                or latest_major_with_artifact_payload + latest_major_with_explicit_no_artifact
                == len(latest_major)
            )
        )
        provider_model_ok = (
            major_total > 0
            and latest_major_with_provider_model == len(latest_major)
        )
        provider_model_provenance_ok = (
            major_total > 0
            and latest_major_with_provider_model_provenance == len(latest_major)
        )
        provider_model_accounted_ok = (
            major_total > 0
            and latest_major_with_provider_model_accounted == len(latest_major)
        )
        terminal_provider_model_ok = (
            latest_terminal_major_total > 0
            and latest_terminal_major_with_provider_model == latest_terminal_major_total
        )
        terminal_provider_model_provenance_ok = (
            latest_terminal_major_total > 0
            and latest_terminal_major_with_provider_model_provenance
            == latest_terminal_major_total
        )
        terminal_provider_model_accounted_ok = (
            latest_terminal_major_total > 0
            and latest_terminal_major_with_provider_model_accounted
            == latest_terminal_major_total
        )
        core_fields_ok = all(item["missing"] == 0 for item in runtime_field_coverage.values())
        score_gate_70_to_75 = bool(core_fields_ok and idempotency_match_ok and mission_ok and artifact_ok)
        latest_artifact_or_no_artifact = (
            latest_major_with_artifact_payload + latest_major_with_explicit_no_artifact
        )
        gate_70_to_75_components = [
            _gate_component(
                component_id="core_runtime_receipt_fields",
                short_label="core",
                passed=core_fields_ok,
                scope="score_gate",
                required="all runtime_receipts core identity/idempotency fields are filled",
                evidence=_runtime_field_gap_evidence(runtime_field_coverage),
                blocker=(
                    "runtime_receipts have missing core identity/idempotency fields"
                ),
            ),
            _gate_component(
                component_id="major_idempotency_join",
                short_label="idempotency",
                passed=idempotency_match_ok,
                scope="score_gate",
                required=(
                    "all major task receipts have idempotency fields and join "
                    "idempotency_records"
                ),
                evidence=(
                    f"matching_idempotency={major_with_matching_idempotency}/"
                    f"{major_total}; fields={major_with_idempotency_fields}/{major_total}"
                ),
                blocker=(
                    "major task receipts do not all join to idempotency_records"
                ),
            ),
            _gate_component(
                component_id="latest_major_mission_payload",
                short_label="mission",
                passed=mission_ok,
                scope="score_gate",
                required="latest major task receipts carry mission_id-like payloads",
                evidence=f"latest_mission={latest_major_with_mission}/{len(latest_major)}",
                blocker=(
                    "latest major task receipts do not all carry mission_id-like payloads"
                ),
            ),
            _gate_component(
                component_id="artifact_or_explicit_no_artifact",
                short_label="artifact",
                passed=artifact_ok,
                scope="score_gate",
                required=(
                    "major task receipts join artifact_records or latest receipts "
                    "carry artifact evidence / explicit no-artifact reasons"
                ),
                evidence=(
                    f"artifact_record={major_with_artifact_record}/{major_total}; "
                    f"latest_artifact_or_no_artifact={latest_artifact_or_no_artifact}/"
                    f"{len(latest_major)}"
                ),
                blocker=(
                    "major task receipts do not all join to artifact_records or "
                    "explicit no-artifact reasons"
                ),
            ),
            _gate_component(
                component_id="active_head_side_effect_key",
                short_label="active_head",
                passed=bool(active_head_side_effect_key_gate["passed"]),
                scope="strict_runtime_blocker",
                required="recent DB-head runtime receipts have side_effect_key coverage",
                evidence=_active_head_window_evidence(recent_side_effect_key_gap_windows),
                blocker=str(active_head_side_effect_key_gate["reason"]),
            ),
        ]

        report.update(
            counts=counts,
            delegation_runs={
                "scoped_total": scoped_delegation_total,
                "with_receipt_json": delegation_with_receipt_json,
                "receipt_json_percent": _percent(delegation_with_receipt_json, scoped_delegation_total),
                "with_current_artifact_id": delegation_with_artifact_ref,
                "current_artifact_id_percent": _percent(
                    delegation_with_artifact_ref,
                    scoped_delegation_total,
                ),
                "with_mission_in_metadata": delegation_with_metadata_mission,
                "mission_metadata_percent": _percent(
                    delegation_with_metadata_mission,
                    scoped_delegation_total,
                ),
            },
            runtime_receipts={
                "scoped_total": scoped_receipt_total,
                "field_coverage": runtime_field_coverage,
                "type_status": type_status,
                "latest_sample": latest_sample,
                "side_effect_key_gap_by_type": side_effect_key_gap_by_type,
                "latest_side_effect_key_gap_sample": latest_side_effect_key_gap_sample,
                "latest_side_effect_key_gap_diagnostics": (
                    latest_side_effect_key_gap_diagnostics
                ),
                "side_effect_key_gap_producer_groups": side_effect_key_gap_producer_groups,
                "recent_side_effect_key_gap_windows": recent_side_effect_key_gap_windows,
                "active_head_side_effect_key_gate": active_head_side_effect_key_gate,
            },
            major_task_receipts={
                "types": list(MAJOR_TASK_RECEIPT_TYPES),
                "total": major_total,
                "with_idempotency_fields": major_with_idempotency_fields,
                "with_matching_idempotency_record": major_with_matching_idempotency,
                "with_artifact_record": major_with_artifact_record,
                "latest_sample_size": len(latest_major),
                "latest_with_mission_payload": latest_major_with_mission,
                "latest_with_artifact_payload": latest_major_with_artifact_payload,
                "latest_with_explicit_no_artifact_reason": latest_major_with_explicit_no_artifact,
                "latest_with_provider_payload": latest_major_with_provider,
                "latest_with_model_payload": latest_major_with_model,
                "latest_with_provider_model_payload": latest_major_with_provider_model,
                "latest_with_provider_model_provenance": (
                    latest_major_with_provider_model_provenance
                ),
                "latest_with_provider_model_accounted": (
                    latest_major_with_provider_model_accounted
                ),
                "latest_provider_model_pending_execution": (
                    latest_provider_model_pending_execution
                ),
                "latest_major_status_breakdown": latest_major_status_breakdown,
                "latest_with_ds_goal_preflight_payload": (
                    latest_with_ds_goal_preflight_payload
                ),
                "latest_ds_goal_preflight_status_breakdown": (
                    latest_ds_goal_preflight_status_breakdown
                ),
                "latest_ds_goal_preflight_sample": latest_ds_goal_preflight_sample,
                "latest_terminal_sample_size": latest_terminal_major_total,
                "latest_terminal_with_provider_payload": (
                    latest_terminal_major_with_provider
                ),
                "latest_terminal_with_model_payload": latest_terminal_major_with_model,
                "latest_terminal_with_provider_model_payload": (
                    latest_terminal_major_with_provider_model
                ),
                "latest_terminal_with_provider_model_provenance": (
                    latest_terminal_major_with_provider_model_provenance
                ),
                "latest_terminal_with_provider_model_accounted": (
                    latest_terminal_major_with_provider_model_accounted
                ),
                "latest_provider_model_payload_class_breakdown": (
                    latest_provider_model_class_breakdown
                ),
                "latest_terminal_provider_model_payload_class_breakdown": (
                    latest_terminal_provider_model_class_breakdown
                ),
                "latest_provider_model_unproven_sample": (
                    latest_provider_model_unproven_sample
                ),
                "latest_terminal_provider_model_unproven_sample": (
                    latest_terminal_provider_model_unproven_sample
                ),
                "latest_provider_model_unproven_producer_groups": (
                    latest_provider_model_unproven_producer_groups
                ),
                "latest_terminal_provider_model_unproven_producer_groups": (
                    latest_terminal_provider_model_unproven_producer_groups
                ),
                "latest_payload_parse_errors": latest_payload_parse_errors,
                "type_breakdown": major_type_breakdown,
                "field_gap_producer_groups": major_field_gap_producer_groups,
                "field_gap_summary": major_field_gap_summary,
                "field_gap_action_queue": major_field_gap_action_queue,
                "fixture_quarantine_policy": fixture_quarantine_policy,
                "top_missing_side_effect_groups": top_missing_side_effect_groups,
            },
            runtime_surfaces={
                "cli.ds_goal": ds_goal_cli_context,
            },
            gate_70_to_75_components=gate_70_to_75_components,
        )
        report["summary"].update(
            runtime_receipts_total=scoped_receipt_total,
            latest_runtime_receipt_created_at=latest_created_at,
            delegation_receipt_json_percent=report["delegation_runs"]["receipt_json_percent"],
            major_task_receipts_total=major_total,
            major_task_receipts_idempotency_percent=_percent(
                major_with_matching_idempotency,
                major_total,
            ),
            major_task_receipts_artifact_record_percent=_percent(
                major_with_artifact_record,
                major_total,
            ),
            latest_major_task_receipts_mission_percent=_percent(
                latest_major_with_mission,
                len(latest_major),
            ),
            latest_major_task_receipts_artifact_payload_percent=_percent(
                latest_major_with_artifact_payload + latest_major_with_explicit_no_artifact,
                len(latest_major),
            ),
            latest_major_task_receipts_provider_model_percent=_percent(
                latest_major_with_provider_model,
                len(latest_major),
            ),
            latest_major_task_receipts_provider_model_provenance_percent=_percent(
                latest_major_with_provider_model_provenance,
                len(latest_major),
            ),
            latest_major_task_receipts_provider_model_accounted_percent=_percent(
                latest_major_with_provider_model_accounted,
                len(latest_major),
            ),
            latest_major_task_receipts_pending_execution=(
                latest_provider_model_pending_execution
            ),
            latest_terminal_major_task_receipts_total=latest_terminal_major_total,
            latest_terminal_major_task_receipts_provider_model_percent=_percent(
                latest_terminal_major_with_provider_model,
                latest_terminal_major_total,
            ),
            latest_terminal_major_task_receipts_provider_model_provenance_percent=_percent(
                latest_terminal_major_with_provider_model_provenance,
                latest_terminal_major_total,
            ),
            latest_terminal_major_task_receipts_provider_model_accounted_percent=_percent(
                latest_terminal_major_with_provider_model_accounted,
                latest_terminal_major_total,
            ),
            core_runtime_receipt_fields_complete=core_fields_ok,
            idempotency_match_complete=idempotency_match_ok,
            mission_coverage_complete=mission_ok,
            artifact_coverage_complete=artifact_ok,
            provider_model_coverage_complete=provider_model_ok,
            provider_model_provenance_complete=provider_model_provenance_ok,
            provider_model_accounted_complete=provider_model_accounted_ok,
            terminal_provider_model_coverage_complete=terminal_provider_model_ok,
            terminal_provider_model_provenance_complete=(
                terminal_provider_model_provenance_ok
            ),
            terminal_provider_model_accounted_complete=(
                terminal_provider_model_accounted_ok
            ),
            active_head_side_effect_key_clean=active_head_side_effect_key_gate["passed"],
            score_gate_70_to_75=score_gate_70_to_75,
            gate_70_to_75_components=gate_70_to_75_components,
        )
        blockers = []
        production_readiness_blockers = []
        if major_total <= 0:
            blockers.append("no major task receipts found for selected scope")
        if major_total > 0 and not core_fields_ok:
            blockers.append("runtime_receipts have missing core identity/idempotency fields")
        if major_total > 0 and not idempotency_match_ok:
            blockers.append("major task receipts do not all join to idempotency_records")
        if major_total > 0 and not mission_ok:
            blockers.append("latest major task receipts do not all carry mission_id-like payloads")
        if major_total > 0 and not artifact_ok:
            blockers.append("major task receipts do not all join to artifact_records or explicit no-artifact reasons")
        if major_total > 0 and not provider_model_accounted_ok and not provider_model_ok:
            production_readiness_blockers.append(
                "latest major task receipts do not all carry provider/model payloads"
            )
        if (
            major_total > 0
            and not provider_model_accounted_ok
            and not provider_model_provenance_ok
        ):
            production_readiness_blockers.append(
                "latest major task receipts do not all carry provider/model provenance beyond probe-selected metadata"
            )
        production_readiness_blockers.extend(
            _ds_goal_cli_context_blockers(ds_goal_cli_context)
        )
        if not active_head_side_effect_key_gate["passed"]:
            blockers.append(active_head_side_effect_key_gate["reason"])
        report["summary"]["blockers"] = blockers
        report["summary"]["production_readiness_blockers"] = production_readiness_blockers
        return report


def _print_text(report: dict[str, Any]) -> None:
    print("=" * 88)
    print("RUNTIME RECEIPT COVERAGE REPORT")
    print("=" * 88)
    print()
    if report.get("error"):
        print(f"ERROR: {report['error']}")
        return
    summary = report["summary"]
    print(f"DB:                                {report['db_path']}")
    scope = report.get("scope", {})
    if scope.get("run_id"):
        print(f"Run scope:                         {scope['run_id']}")
    if scope.get("since_created_at"):
        print(f"Fresh since:                       {scope['since_created_at']}")
    print(f"Runtime receipts:                  {summary['runtime_receipts_total']}")
    print(f"Delegation receipt_json fill:       {summary['delegation_receipt_json_percent']}%")
    print(f"Major task receipts:               {summary['major_task_receipts_total']}")
    print(f"Major receipt idempotency join:     {summary['major_task_receipts_idempotency_percent']}%")
    print(f"Major receipt artifact record join: {summary['major_task_receipts_artifact_record_percent']}%")
    print(f"Latest major mission payload:       {summary['latest_major_task_receipts_mission_percent']}%")
    print(f"Latest major artifact payload:      {summary['latest_major_task_receipts_artifact_payload_percent']}%")
    print(f"Latest major provider/model:        {summary['latest_major_task_receipts_provider_model_percent']}%")
    print(
        "Latest major provider/model proof:  "
        f"{summary['latest_major_task_receipts_provider_model_provenance_percent']}%"
    )
    print(
        "Latest major provider/model accounted: "
        f"{summary['latest_major_task_receipts_provider_model_accounted_percent']}%"
    )
    print(
        "Latest terminal provider/model:     "
        f"{summary['latest_terminal_major_task_receipts_provider_model_percent']}%"
        f" ({summary['latest_terminal_major_task_receipts_total']} terminal,"
        f" {summary['latest_major_task_receipts_pending_execution']} pending)"
    )
    print(
        "Latest terminal provider/model proof:"
        f" {summary['latest_terminal_major_task_receipts_provider_model_provenance_percent']}%"
    )
    print(
        "Latest terminal provider/model accounted:"
        f" {summary['latest_terminal_major_task_receipts_provider_model_accounted_percent']}%"
    )
    print(
        "Active head side_effect_key clean: "
        f"{'PASS' if summary.get('active_head_side_effect_key_clean') else 'FAIL'}"
    )
    print(f"70->75 score gate:                 {'PASS' if summary['score_gate_70_to_75'] else 'FAIL'}")
    gate_components = [
        item
        for item in summary.get("gate_70_to_75_components") or []
        if isinstance(item, dict)
    ]
    if gate_components:
        print("70->75 gate components:")
        for item in gate_components:
            print(
                "  "
                f"{item.get('short_label') or item.get('id'):<12} "
                f"{str(item.get('status') or 'unknown').upper():<4} "
                f"scope={item.get('scope') or '<unknown>'}; "
                f"evidence={item.get('evidence') or '<none>'}"
            )
            if item.get("blocker"):
                print(f"    blocker={item['blocker']}")
    print()
    print("Runtime receipt field coverage:")
    for field, data in report["runtime_receipts"]["field_coverage"].items():
        print(f"  {field:<18} {data['filled']:>6}/{data['total']:<6} {data['percent']:>6}%")
    print()
    side_effect_gap_by_type = report["runtime_receipts"].get("side_effect_key_gap_by_type") or []
    if side_effect_gap_by_type:
        print("Runtime side_effect_key gaps by receipt type:")
        for row in side_effect_gap_by_type:
            print(
                "  "
                f"{row['receipt_type']:<16}"
                f" missing={row['missing_side_effect_key']:<6}"
                f" total={row['total']}"
            )
        print()
    latest_side_effect_gap_sample = (
        report["runtime_receipts"].get("latest_side_effect_key_gap_sample") or []
    )
    if latest_side_effect_gap_sample:
        print("Latest side_effect_key gap sample:")
        for row in latest_side_effect_gap_sample:
            print(
                "  "
                f"{row['created_at']} "
                f"{row['receipt_type']} "
                f"status={row['status']} "
                f"agent={row['agent_id']} "
                f"task={row['task_id']} "
                f"run={row['run_id']}"
            )
        print()
    latest_side_effect_gap_diagnostics = (
        report["runtime_receipts"].get("latest_side_effect_key_gap_diagnostics") or []
    )
    if latest_side_effect_gap_diagnostics:
        print("Latest side_effect_key gap diagnostics:")
        for row in latest_side_effect_gap_diagnostics:
            detail = [
                f"source={row.get('producer_source') or '<unknown>'}",
                f"failure={row.get('producer_failure_code') or '<none>'}",
                f"shape={row.get('identifier_shape') or '<unknown>'}",
                f"session={row.get('session_id') or '<blank>'}",
            ]
            if row.get("topology"):
                detail.append(f"topology={row['topology']}")
            if row.get("runtime_db_path"):
                detail.append(f"db={row['runtime_db_path']}")
            print(
                "  "
                f"{row['created_at']} "
                f"{row['receipt_type']} "
                f"status={row['status']} "
                f"agent={row['agent_id']} "
                f"task={row['task_id']} "
                f"run={row['run_id']} "
                + " ".join(detail)
            )
            if row.get("producer_error"):
                print(f"    error={_trim_text(row['producer_error'])}")
        print()
    side_effect_gap_producer_groups = (
        report["runtime_receipts"].get("side_effect_key_gap_producer_groups") or []
    )
    if side_effect_gap_producer_groups:
        print("Top side_effect_key gap producer groups:")
        for row in side_effect_gap_producer_groups:
            print(
                "  "
                f"{row['receipt_type']:<16}"
                f" source={row['producer_source']:<14}"
                f" failure={row['producer_failure_code']:<18}"
                f" topology={row['topology']:<10}"
                f" shape={row['identifier_shape']:<14}"
                f" missing={row['missing_side_effect_key']:<5}"
                f" latest={row['latest_created_at']} "
                f" sample={row['sample_agent_id']}/{row['sample_task_id']}"
            )
        print()
    recent_windows = report["runtime_receipts"].get("recent_side_effect_key_gap_windows") or []
    if recent_windows:
        print("Recent side_effect_key gap windows:")
        for row in recent_windows:
            print(
                "  "
                f"last_{row['window_minutes']}m "
                f"anchor={row['anchor_created_at']} "
                f"missing={row['missing_side_effect_key']}/{row['total']} "
                f"({row['missing_side_effect_key_percent']}%)"
            )
            for group in row.get("top_gap_producer_groups") or []:
                print(
                    "    "
                    f"{group['receipt_type']:<16}"
                    f" source={group['producer_source']:<14}"
                    f" failure={group['producer_failure_code']:<18}"
                    f" topology={group['topology']:<10}"
                    f" shape={group['identifier_shape']:<14}"
                    f" missing={group['missing_side_effect_key']:<5}"
                    f" sample={group['sample_agent_id']}/{group['sample_task_id']}"
                )
        print()
    ds_goal_context = (
        report.get("runtime_surfaces", {}).get("cli.ds_goal")
        if isinstance(report.get("runtime_surfaces"), dict)
        else {}
    )
    if ds_goal_context:
        print("ds-goal CLI owner evidence:")
        if not ds_goal_context.get("available"):
            print(
                "  "
                f"state={ds_goal_context.get('state') or '<unknown>'}; "
                f"receipt={ds_goal_context.get('receipt') or '<missing>'}; "
                f"evidence={ds_goal_context.get('evidence') or '<none>'}"
            )
        else:
            sha = str(ds_goal_context.get("wrapper_sha256") or "")
            freshness = ds_goal_context.get("freshness")
            freshness_state = (
                freshness.get("state")
                if isinstance(freshness, dict)
                else "<unknown>"
            )
            print(
                "  "
                f"status={ds_goal_context.get('status') or '<unknown>'}; "
                f"freshness={freshness_state}; "
                f"proof_gaps={','.join(ds_goal_context.get('proof_gaps') or [])}"
            )
            print(
                "  "
                f"target={ds_goal_context.get('target_repo') or '<blank>'}; "
                f"source={ds_goal_context.get('target_resolution_source') or '<blank>'}; "
                f"matches_current={str(ds_goal_context.get('target_matches_current_repo')).lower()}; "
                f"default={ds_goal_context.get('default_target_repo') or '<blank>'}; "
                f"default_source={ds_goal_context.get('default_target_resolution_source') or '<blank>'}"
            )
            print(
                "  "
                f"wrapper_sha256={(sha[:12] if sha else '<missing>')}; "
                f"pin={str(ds_goal_context.get('dharma_swarm_repo_pin_supported')).lower()}; "
                f"hardening={ds_goal_context.get('target_sync_receipt_hardening_state') or '<unknown>'}; "
                f"preflight={ds_goal_context.get('longrun_preflight_status') or '<unknown>'}; "
                f"safe={ds_goal_context.get('safe_current_checkout_invocation') or '<none>'}"
            )
            decision_packet = (
                ds_goal_context.get("convergence_decision_packet")
                if isinstance(ds_goal_context.get("convergence_decision_packet"), dict)
                else {}
            )
            if decision_packet:
                option_ids = [
                    str(item.get("id") or "")
                    for item in decision_packet.get("operator_decision_options") or []
                    if isinstance(item, dict) and item.get("id")
                ]
                forbidden = [
                    str(item)
                    for item in decision_packet.get("forbidden_without_operator_approval")
                    or []
                    if str(item)
                ]
                print(
                    "  "
                    f"convergence_decision={decision_packet.get('approval_state') or '<unknown>'}; "
                    f"score_effect={decision_packet.get('score_effect') or '<unknown>'}"
                )
                if option_ids:
                    print("  " f"operator_options={'|'.join(option_ids)}")
                if forbidden:
                    print("  " f"forbidden_without_approval={'|'.join(forbidden)}")
        print()
    type_breakdown = report["major_task_receipts"].get("type_breakdown") or []
    if type_breakdown:
        print("Major task blocker breakdown:")
        for row in type_breakdown:
            print(
                "  "
                f"{row['receipt_type']:<16}"
                f" total={row['total']:<5}"
                f" idempotency_gap={row['idempotency_gap']:<5}"
                f" artifact_gap={row['artifact_record_gap']:<5}"
            )
        print()
    field_gap_groups = (
        report["major_task_receipts"].get("field_gap_producer_groups") or []
    )
    if field_gap_groups:
        print("Major task field gap producer groups:")
        for row in field_gap_groups:
            print(
                "  "
                f"{row['gap_type']:<22}"
                f" {row['receipt_type']:<16}"
                f" source={row['producer_source']:<14}"
                f" failure={row['producer_failure_code']:<18}"
                f" topology={row['topology']:<10}"
                f" shape={row['identifier_shape']:<14}"
                f" missing={row['missing']:<5}"
                f" latest={row['latest_created_at']:<32}"
                f" freshness={row.get('freshness_class') or '<unknown>'}"
                f" age_head_min={row.get('age_minutes_from_head')}"
                f" action={row.get('recommended_action') or '<unknown>'}"
                f" sample={row['sample_agent_id']}/{row['sample_task_id']}"
            )
        print()
    field_gap_summary = report["major_task_receipts"].get("field_gap_summary") or {}
    if int(field_gap_summary.get("total_missing") or 0) > 0:
        print("Major task field gap summary:")
        print(
            "  "
            f"total_missing={field_gap_summary.get('total_missing')}; "
            f"groups={field_gap_summary.get('group_count')}; "
            f"active_head_missing={field_gap_summary.get('active_head_missing')}; "
            f"recent_historical_missing={field_gap_summary.get('recent_historical_missing')}; "
            f"older_historical_missing={field_gap_summary.get('older_historical_missing')}; "
            f"quarantine_candidate_missing={field_gap_summary.get('quarantine_candidate_missing')}"
        )
        print(
            "  "
            f"freshness={_summary_count_text(field_gap_summary.get('by_freshness_class'))}"
        )
        print(
            "  "
            f"actions={_summary_count_text(field_gap_summary.get('by_recommended_action'))}"
        )
        print(
            "  "
            f"gap_types={_summary_count_text(field_gap_summary.get('by_gap_type'))}"
        )
        print(
            "  "
            f"producer_sources={_summary_count_text(field_gap_summary.get('by_producer_source'))}"
        )
        print()
    field_gap_action_queue = (
        report["major_task_receipts"].get("field_gap_action_queue") or []
    )
    if field_gap_action_queue:
        print("Major task field gap action queue:")
        for row in field_gap_action_queue:
            top_group = (
                row.get("top_group") if isinstance(row.get("top_group"), dict) else {}
            )
            print(
                "  "
                f"priority={row.get('priority')} "
                f"label={row.get('short_label')} "
                f"action={row.get('action')} "
                f"owner={row.get('owner_surface')} "
                f"missing={row.get('missing')} "
                f"groups={row.get('group_count')} "
                f"active_head={row.get('active_head_missing')} "
                f"operator_decision={str(row.get('operator_decision_required')).lower()} "
                f"disposition={row.get('disposition')}"
            )
            print(
                "    "
                f"freshness={_summary_count_text(row.get('by_freshness_class'))}; "
                f"gap_types={_summary_count_text(row.get('by_gap_type'))}; "
                f"producer_sources={_summary_count_text(row.get('by_producer_source'))}"
            )
            if top_group:
                print(
                    "    "
                    f"top_group={top_group.get('gap_type')}/"
                    f"{top_group.get('receipt_type')}/"
                    f"{top_group.get('producer_source')}/"
                    f"{top_group.get('producer_failure_code')}/"
                    f"{top_group.get('topology')}"
                    f"={top_group.get('missing')}@"
                    f"{top_group.get('freshness_class')}"
                )
            fresh_proof = (
                row.get("fresh_proof")
                if isinstance(row.get("fresh_proof"), dict)
                else {}
            )
            if fresh_proof:
                print(
                    "    "
                    f"fresh_proof=status={fresh_proof.get('status')}; "
                    f"scope={fresh_proof.get('proof_scope')}; "
                    f"run={fresh_proof.get('proof_run_id')}; "
                    f"db={fresh_proof.get('proof_db')}"
                )
                print(
                    "    "
                    f"fresh_proof_remaining={fresh_proof.get('remaining_action')}; "
                    f"ref={fresh_proof.get('evidence_ref')}"
                )
                prevention_evidence = str(
                    fresh_proof.get("prevention_evidence") or ""
                )
                if prevention_evidence:
                    print(
                        "    "
                        f"prevention_evidence={prevention_evidence}; "
                        f"root={fresh_proof.get('prevention_receipt_root')}"
                    )
            required_evidence = [
                str(item) for item in row.get("required_evidence") or [] if str(item)
            ]
            if required_evidence:
                print("    required_evidence=" + " | ".join(required_evidence))
        print()
    fixture_quarantine = (
        report["major_task_receipts"].get("fixture_quarantine_policy") or {}
    )
    if int(fixture_quarantine.get("candidate_missing") or 0) > 0:
        isolation = fixture_quarantine.get("test_runtime_db_isolation") or {}
        print("Fixture quarantine policy:")
        print(
            "  "
            f"status={fixture_quarantine.get('status')} "
            f"candidate_missing={fixture_quarantine.get('candidate_missing')} "
            f"groups={fixture_quarantine.get('candidate_group_count')} "
            f"active_head={fixture_quarantine.get('active_head_missing')} "
            f"recent={fixture_quarantine.get('recent_historical_missing')} "
            f"older={fixture_quarantine.get('older_historical_missing')} "
            f"eligible_after_operator_decision="
            f"{str(fixture_quarantine.get('eligible_after_operator_decision')).lower()} "
            f"applies_to_score_gate="
            f"{str(fixture_quarantine.get('applies_to_score_gate')).lower()}"
        )
        print(
            "  "
            f"test_isolation_enforced={str(isolation.get('enforced')).lower()} "
            f"path={isolation.get('path')}"
        )
        blockers = [
            str(item) for item in fixture_quarantine.get("blockers") or [] if str(item)
        ]
        if blockers:
            print("  blockers=" + " | ".join(blockers))
        print()
    provider_model_breakdown = (
        report["major_task_receipts"].get("latest_provider_model_payload_class_breakdown") or {}
    )
    if provider_model_breakdown:
        print("Latest provider/model payload classes:")
        for key, count in sorted(provider_model_breakdown.items()):
            print(f"  {key:<32} {count}")
        print()
    terminal_provider_model_breakdown = (
        report["major_task_receipts"].get(
            "latest_terminal_provider_model_payload_class_breakdown"
        )
        or {}
    )
    if terminal_provider_model_breakdown:
        print("Latest terminal provider/model payload classes:")
        for key, count in sorted(terminal_provider_model_breakdown.items()):
            print(f"  {key:<32} {count}")
        print()
    status_breakdown = report["major_task_receipts"].get("latest_major_status_breakdown") or {}
    if status_breakdown:
        print("Latest major receipt status classes:")
        for key, count in sorted(status_breakdown.items()):
            print(f"  {key:<32} {count}")
        print()
    ds_goal_preflight_count = int(
        report["major_task_receipts"].get("latest_with_ds_goal_preflight_payload") or 0
    )
    if ds_goal_preflight_count:
        print("Latest ds-goal preflight receipt payloads:")
        print(
            "  "
            f"{ds_goal_preflight_count}/"
            f"{report['major_task_receipts'].get('latest_sample_size') or 0}"
        )
        for key, count in sorted(
            (
                report["major_task_receipts"].get(
                    "latest_ds_goal_preflight_status_breakdown"
                )
                or {}
            ).items()
        ):
            print(f"  {key:<40} {count}")
        for row in (
            report["major_task_receipts"].get("latest_ds_goal_preflight_sample")
            or []
        ):
            print(
                "  sample "
                f"{row.get('receipt_type')}/{row.get('receipt_id')} "
                f"status={row.get('preflight_status')} "
                f"passed={str(row.get('preflight_passed')).lower()} "
                f"default={row.get('default_target_repo')} "
                f"pin={row.get('repo_pin_source')} "
                f"score_effect={row.get('score_effect')}"
            )
        print()
    provider_model_unproven_groups = (
        report["major_task_receipts"].get("latest_provider_model_unproven_producer_groups")
        or []
    )
    if provider_model_unproven_groups:
        print("Latest provider/model unproven producer groups:")
        for row in provider_model_unproven_groups:
            print(
                "  "
                f"{row['receipt_type']:<16}"
                f" class={row['provider_model_payload_class']:<28}"
                f" source={row['producer_source']:<14}"
                f" failure={row['producer_failure_code']:<36}"
                f" topology={row['topology']:<12}"
                f" missing={row['missing_provider_model_provenance']:<5}"
                f" sample={row['sample_agent_id']}/{row['sample_task_id']}"
            )
        print()
    terminal_provider_model_unproven_groups = (
        report["major_task_receipts"].get(
            "latest_terminal_provider_model_unproven_producer_groups"
        )
        or []
    )
    if terminal_provider_model_unproven_groups:
        print("Latest terminal provider/model unproven producer groups:")
        for row in terminal_provider_model_unproven_groups:
            print(
                "  "
                f"{row['receipt_type']:<16}"
                f" class={row['provider_model_payload_class']:<28}"
                f" source={row['producer_source']:<14}"
                f" failure={row['producer_failure_code']:<36}"
                f" topology={row['topology']:<12}"
                f" missing={row['missing_provider_model_provenance']:<5}"
                f" sample={row['sample_agent_id']}/{row['sample_task_id']}"
            )
        print()
    provider_model_unproven_sample = (
        report["major_task_receipts"].get("latest_provider_model_unproven_sample") or []
    )
    if provider_model_unproven_sample:
        print("Latest unproven provider/model provenance sample:")
        for row in provider_model_unproven_sample:
            producer = str(row.get("receipt_producer_source") or "")
            producer_text = (
                " "
                f"producer={producer}/"
                f"{row.get('receipt_producer_failure_code') or '<none>'}/"
                f"{row.get('receipt_producer_topology') or '<blank>'}"
                if producer
                else ""
            )
            print(
                "  "
                f"{row['created_at']} "
                f"{row['receipt_type']} "
                f"class={row['provider_model_payload_class']} "
                f"source={row.get('provider_model_truth_source') or '<blank>'} "
                f"agent={row['agent_id']} "
                f"task={row['task_id']} "
                f"run={row['run_id']}"
                f"{producer_text}"
            )
        print()
    missing_groups = report["major_task_receipts"].get("top_missing_side_effect_groups") or []
    if missing_groups:
        print("Top major side_effect_key gaps:")
        for row in missing_groups:
            agent_id = row.get("agent_id") or "<blank>"
            print(
                "  "
                f"{row['receipt_type']:<16}"
                f" agent={agent_id:<18}"
                f" missing={row['missing_side_effect_key']:<5}"
                f" total={row['total']}"
            )
        print()
    if summary["blockers"]:
        print("Blockers:")
        for blocker in summary["blockers"]:
            print(f"  - {blocker}")
    production_readiness_blockers = summary.get("production_readiness_blockers") or []
    if production_readiness_blockers:
        print()
        print("Production-readiness blockers:")
        for blocker in production_readiness_blockers:
            print(f"  - {blocker}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="runtime.db path")
    parser.add_argument("--latest-limit", type=int, default=500)
    parser.add_argument(
        "--run-id",
        default="",
        help="scope coverage metrics to one runtime run_id while keeping table presence checks global",
    )
    parser.add_argument(
        "--since-created-at",
        default="",
        help=(
            "scope runtime receipt coverage metrics to receipts with created_at >= this "
            "timestamp while keeping table presence and raw table counts global"
        ),
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero unless the conservative 70->75 coverage gate passes",
    )
    args = parser.parse_args()

    report = build_report(
        args.db,
        latest_limit=args.latest_limit,
        run_id=args.run_id,
        since_created_at=args.since_created_at,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text(report)
    if args.strict and not report["summary"].get("score_gate_70_to_75", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
