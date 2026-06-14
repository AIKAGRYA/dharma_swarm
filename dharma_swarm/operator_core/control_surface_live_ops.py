"""Live ops census adapter for the Control Surface Projector."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.control_surface_models import (
    ControlSurfaceRow,
    _utc_now_iso,
)
from dharma_swarm.operator_core.live_ops_census_contract import (
    census_payload_freshness,
    default_output_path,
    validate_census_payload,
)

logger = logging.getLogger(__name__)

_DAEMON_SPINE_RUNTIME_PROOFS = {
    "spine_enabled_self_report",
    "daemon_default_receipt_proven",
    "daemon_default_spine_receipt_proven",
}
_DASHBOARD_API_PROBE_BOUND_STATES = {"ok", "not_checked"}
_DASHBOARD_ROWS_PROBE_URL = "http://127.0.0.1:8420/api/control-surface/rows"
_LIVE_OPS_CENSUS_CACHE_MAX_AGE_SECONDS = 300.0


def _append_gap(gap_codes: list[str], code: str) -> None:
    if code and code not in gap_codes:
        gap_codes.append(code)


def _runtime_receipt_head_evidence_source(head: dict[str, Any]) -> str:
    clean = head.get("active_head_side_effect_key_clean")
    clean_text = "unknown" if clean is None else str(bool(clean)).lower()
    fresh = head.get("latest_fresh")
    fresh_text = "unknown" if fresh is None else str(bool(fresh)).lower()
    age = head.get("latest_age_hours")
    age_text = "unknown" if age is None else str(age)
    max_age = head.get("latest_max_age_hours")
    max_age_text = "unknown" if max_age is None else str(max_age)
    latest = str(head.get("latest_created_at") or "unknown")
    total = str(head.get("runtime_receipts_total") or 0)
    window_parts: list[str] = []
    for row in head.get("windows") or []:
        if not isinstance(row, dict):
            continue
        minutes = row.get("window_minutes")
        missing = row.get("missing_side_effect_key")
        window_total = row.get("total")
        window_parts.append(f"{minutes}m:{missing}/{window_total}")
    windows = ",".join(window_parts) if window_parts else "none"
    return (
        "runtime_receipt_active_head "
        f"clean={clean_text}; fresh={fresh_text}; "
        f"age_hours={age_text}; max_age_hours={max_age_text}; "
        f"total={total}; latest={latest}; windows={windows}"
    )


def _runtime_receipt_coverage_evidence_source(coverage: dict[str, Any]) -> str:
    percent = coverage.get("latest_major_task_receipts_provider_model_percent")
    percent_text = "unknown" if percent is None else str(percent)
    proof_percent = coverage.get(
        "latest_major_task_receipts_provider_model_provenance_percent"
    )
    proof_percent_text = "unknown" if proof_percent is None else str(proof_percent)
    latest_sample = str(coverage.get("latest_sample_size") or 0)
    provider_model = str(coverage.get("latest_with_provider_model_payload") or 0)
    provider_model_proof = str(coverage.get("latest_with_provider_model_provenance") or 0)
    provider_model_accounted = str(
        coverage.get("latest_with_provider_model_accounted") or 0
    )
    terminal_sample = str(coverage.get("latest_terminal_sample_size") or 0)
    terminal_provider_model = str(
        coverage.get("latest_terminal_with_provider_model_payload") or 0
    )
    terminal_provider_model_proof = str(
        coverage.get("latest_terminal_with_provider_model_provenance") or 0
    )
    terminal_provider_model_accounted = str(
        coverage.get("latest_terminal_with_provider_model_accounted") or 0
    )
    pending = str(coverage.get("latest_provider_model_pending_execution") or 0)
    provider = str(coverage.get("latest_with_provider_payload") or 0)
    model = str(coverage.get("latest_with_model_payload") or 0)
    major_total = str(coverage.get("major_task_receipts_total") or 0)
    available = str(bool(coverage.get("coverage_report_available"))).lower()
    terminal_percent = coverage.get(
        "latest_terminal_major_task_receipts_provider_model_percent"
    )
    terminal_percent_text = "unknown" if terminal_percent is None else str(terminal_percent)
    terminal_proof_percent = coverage.get(
        "latest_terminal_major_task_receipts_provider_model_provenance_percent"
    )
    terminal_proof_percent_text = (
        "unknown" if terminal_proof_percent is None else str(terminal_proof_percent)
    )
    accounted_percent = coverage.get(
        "latest_major_task_receipts_provider_model_accounted_percent"
    )
    accounted_percent_text = (
        "unknown" if accounted_percent is None else str(accounted_percent)
    )
    terminal_accounted_percent = coverage.get(
        "latest_terminal_major_task_receipts_provider_model_accounted_percent"
    )
    terminal_accounted_percent_text = (
        "unknown"
        if terminal_accounted_percent is None
        else str(terminal_accounted_percent)
    )
    class_breakdown = coverage.get("latest_provider_model_payload_class_breakdown")
    class_text = ""
    if isinstance(class_breakdown, dict) and class_breakdown:
        class_text = "; classes=" + "|".join(
            f"{key}={value}"
            for key, value in sorted(
                (str(key), value) for key, value in class_breakdown.items()
            )
        )
    gap_groups = [
        group
        for group in coverage.get("active_head_gap_producer_groups") or []
        if isinstance(group, dict)
    ]
    gap_text = ""
    if gap_groups:
        gap_parts: list[str] = []
        for group in gap_groups[:3]:
            gap_parts.append(
                f"{group.get('window_minutes')}m:"
                f"{group.get('receipt_type')}/"
                f"{group.get('producer_source')}/"
                f"{group.get('producer_failure_code')}"
                f"={group.get('missing_side_effect_key')}"
            )
        gap_text = "; active_head_gap_producers=" + "|".join(gap_parts)
    provider_model_gap_groups = [
        group
        for group in coverage.get("latest_provider_model_unproven_producer_groups") or []
        if isinstance(group, dict)
    ]
    provider_model_gap_text = ""
    if provider_model_gap_groups:
        parts: list[str] = []
        for group in provider_model_gap_groups[:3]:
            parts.append(
                f"{group.get('receipt_type')}/"
                f"{group.get('provider_model_payload_class')}/"
                f"{group.get('producer_source')}/"
                f"{group.get('producer_failure_code')}"
                f"={group.get('missing_provider_model_provenance')}"
            )
        provider_model_gap_text = "; provider_model_gap_producers=" + "|".join(parts)
    return (
        "runtime_receipt_provider_model "
        f"available={available}; latest={provider_model}/{latest_sample}; "
        f"proof={provider_model_proof}/{latest_sample}; "
        f"accounted={provider_model_accounted}/{latest_sample}; "
        f"provider={provider}/{latest_sample}; model={model}/{latest_sample}; "
        f"percent={percent_text}; proof_percent={proof_percent_text}; "
        f"accounted_percent={accounted_percent_text}; "
        f"terminal={terminal_provider_model}/{terminal_sample}; "
        f"terminal_percent={terminal_percent_text}; "
        f"terminal_proof={terminal_provider_model_proof}/{terminal_sample}; "
        f"terminal_proof_percent={terminal_proof_percent_text}; "
        f"terminal_accounted={terminal_provider_model_accounted}/{terminal_sample}; "
        f"terminal_accounted_percent={terminal_accounted_percent_text}; "
        f"pending={pending}; "
        f"major_total={major_total}"
        f"{class_text}"
        f"{gap_text}"
        f"{provider_model_gap_text}"
    )


def _runtime_receipt_coverage_status(coverage: dict[str, Any]) -> str:
    if not coverage.get("coverage_report_available"):
        return "unproven"
    if coverage.get("provider_model_latest_complete") is True:
        return "present"
    return "unproven"


def _process_source_state_evidence_source(process_source: dict[str, Any]) -> str:
    state = str(process_source.get("state") or "unknown")
    starts: list[str] = []
    for row in process_source.get("process_starts") or []:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("pid") or "")
        started_at = str(row.get("started_at") or "")
        if pid and started_at:
            starts.append(f"{pid}@{started_at}")
    start_text = ",".join(starts) if starts else "none"
    newest_source = str(process_source.get("newest_source_mtime") or "unknown")

    newer_files: list[str] = []
    for row in process_source.get("source_newer_files") or []:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        mtime = str(row.get("mtime") or "")
        if path and mtime:
            newer_files.append(f"{path}@{mtime}")
    if len(newer_files) > 3:
        newer_text = ",".join(newer_files[:3]) + f",+{len(newer_files) - 3} more"
    else:
        newer_text = ",".join(newer_files) if newer_files else "none"

    return (
        "process_source_state "
        f"state={state}; starts={start_text}; "
        f"newest_source={newest_source}; newer_files={newer_text}"
    )


def _process_source_state_status(process_source: dict[str, Any]) -> str:
    state = str(process_source.get("state") or "")
    if state == "process_started_after_sources":
        return "present"
    if state == "source_changed_after_process_start":
        return "degraded"
    if state == "no_process":
        return "missing"
    return "unproven"


def _nats_ack_tier_evidence_source(ack_tier_state: dict[str, Any]) -> str:
    live_probe = (
        ack_tier_state.get("live_probe")
        if isinstance(ack_tier_state.get("live_probe"), dict)
        else {}
    )
    hot_contact = (
        ack_tier_state.get("hot_contact")
        if isinstance(ack_tier_state.get("hot_contact"), dict)
        else {}
    )
    live_tier = str(live_probe.get("ack_tier") or "unknown")
    live_verified = str(bool(live_probe.get("ack_verified"))).lower()
    live_age = str(live_probe.get("age_hours") if live_probe.get("age_hours") is not None else "unknown")
    hot_tier = str(hot_contact.get("ack_tier") or "unknown")
    hot_age = str(hot_contact.get("age_hours") if hot_contact.get("age_hours") is not None else "unknown")
    hot_ready = str(bool(ack_tier_state.get("operator_hot_contact_ready"))).lower()
    max_age = str(ack_tier_state.get("operator_hot_contact_max_age_hours") or "unknown")
    return (
        "nats_ack_tier_state "
        f"live_probe={live_tier}; live_verified={live_verified}; "
        f"live_age_hours={live_age}; hot_contact={hot_tier}; "
        f"hot_age_hours={hot_age}; hot_max_age_hours={max_age}; "
        f"ready={hot_ready}"
    )


def _nats_ack_tier_evidence_status(ack_tier_state: dict[str, Any]) -> str:
    if ack_tier_state.get("operator_hot_contact_ready") is True:
        return "present"
    live_probe = (
        ack_tier_state.get("live_probe")
        if isinstance(ack_tier_state.get("live_probe"), dict)
        else {}
    )
    if live_probe.get("ack_verified"):
        return "degraded"
    return "unproven"


def _a2a_bridge_state_evidence_source(bridge_state: dict[str, Any]) -> str:
    process_live = str(bool(bridge_state.get("process_live"))).lower()
    tmux_live = str(bool(bridge_state.get("tmux_session_live"))).lower()
    heartbeat_exists = bool(bridge_state.get("heartbeat_exists"))
    heartbeat_fresh = bridge_state.get("heartbeat_fresh")
    if heartbeat_fresh is True:
        heartbeat_state = "fresh"
    elif heartbeat_exists:
        heartbeat_state = "stale"
    else:
        heartbeat_state = "missing"
    heartbeat_age = bridge_state.get("heartbeat_age_hours")
    heartbeat_age_text = (
        str(heartbeat_age) if heartbeat_age is not None else "unknown"
    )
    consumer_probe = (
        bridge_state.get("consumer_probe")
        if isinstance(bridge_state.get("consumer_probe"), dict)
        else {}
    )
    consumer_state = str(consumer_probe.get("state") or "unknown")
    pending = str(consumer_probe.get("num_pending") or 0)
    ack_pending = str(consumer_probe.get("num_ack_pending") or 0)
    lifecycle = (
        bridge_state.get("a2a_lifecycle")
        if isinstance(bridge_state.get("a2a_lifecycle"), dict)
        else {}
    )
    sent = str(lifecycle.get("sent") or "unknown")
    handler_ack = str(lifecycle.get("handler_ack") or "unknown")
    domain_receipt = str(lifecycle.get("domain_receipt") or "unknown")
    semantic_reply = str(bool(bridge_state.get("semantic_reply_claim"))).lower()
    peer_model_processed = str(
        bool(bridge_state.get("peer_model_processed_claim"))
    ).lower()
    completed = str(lifecycle.get("completed") == "completed").lower()
    return (
        "a2a_bridge_state "
        f"process_live={process_live}; tmux_live={tmux_live}; "
        f"heartbeat={heartbeat_state}; "
        f"heartbeat_age_hours={heartbeat_age_text}; "
        f"consumer={consumer_state}; pending={pending}; "
        f"ack_pending={ack_pending}; sent={sent}; "
        f"handler_ack={handler_ack}; domain_receipt={domain_receipt}; "
        f"semantic_reply={semantic_reply}; "
        f"peer_model_processed={peer_model_processed}; completed={completed}"
    )


def _a2a_bridge_state_evidence_status(bridge_state: dict[str, Any]) -> str:
    live = bool(bridge_state.get("process_live")) or bool(
        bridge_state.get("tmux_session_live")
    )
    heartbeat_fresh = bridge_state.get("heartbeat_fresh") is True
    consumer_probe = (
        bridge_state.get("consumer_probe")
        if isinstance(bridge_state.get("consumer_probe"), dict)
        else {}
    )
    consumer_inspectable = consumer_probe.get("state") == "consumer_inspectable"
    if live and heartbeat_fresh and consumer_inspectable:
        return "present"
    if bridge_state.get("heartbeat_exists") or consumer_inspectable:
        return "degraded"
    return "unproven"


def _ds_goal_cli_state_evidence_source(ds_goal_state: dict[str, Any]) -> str:
    default_target = (
        ds_goal_state.get("default_wrapper_target")
        if isinstance(ds_goal_state.get("default_wrapper_target"), dict)
        else {}
    )
    hardening = (
        ds_goal_state.get("target_sync_receipt_hardening")
        if isinstance(ds_goal_state.get("target_sync_receipt_hardening"), dict)
        else {}
    )
    preflight = (
        ds_goal_state.get("longrun_preflight_gate")
        if isinstance(ds_goal_state.get("longrun_preflight_gate"), dict)
        else {}
    )
    decision = (
        ds_goal_state.get("convergence_decision_packet")
        if isinstance(ds_goal_state.get("convergence_decision_packet"), dict)
        else {}
    )
    target_repo = str(ds_goal_state.get("target_repo") or "unknown")
    current_repo = str(ds_goal_state.get("current_repo") or "unknown")
    matches_current = str(
        bool(ds_goal_state.get("target_matches_current_repo"))
    ).lower()
    default_target_repo = str(default_target.get("target_repo") or "unknown")
    hardening_state = str(hardening.get("state") or "unknown")
    preflight_status = str(preflight.get("status") or "unknown")
    approval_required = str(
        bool(
            decision.get("operator_approval_required")
            or preflight.get("operator_convergence_required")
        )
    ).lower()
    safe_pin = str(ds_goal_state.get("safe_current_checkout_invocation") or "unknown")
    return (
        "ds_goal_cli_state "
        f"target_repo={target_repo}; current_repo={current_repo}; "
        f"matches_current={matches_current}; default_target={default_target_repo}; "
        f"hardening={hardening_state}; preflight={preflight_status}; "
        f"operator_approval_required={approval_required}; safe_pin={safe_pin}"
    )


def _ds_goal_cli_state_evidence_status(ds_goal_state: dict[str, Any]) -> str:
    hardening = (
        ds_goal_state.get("target_sync_receipt_hardening")
        if isinstance(ds_goal_state.get("target_sync_receipt_hardening"), dict)
        else {}
    )
    preflight = (
        ds_goal_state.get("longrun_preflight_gate")
        if isinstance(ds_goal_state.get("longrun_preflight_gate"), dict)
        else {}
    )
    target_matches = ds_goal_state.get("target_matches_current_repo") is True
    hardening_ready = hardening.get("state") == "sync_receipt_side_effect_keys_hardened"
    preflight_passed = preflight.get("passed") is True
    if target_matches and hardening_ready and preflight_passed:
        return "present"
    if ds_goal_state.get("safe_current_checkout_invocation"):
        return "degraded"
    return "unproven"


def _dashboard_probe_evidence_status(probe_state: str) -> str:
    if probe_state == "ok":
        return "present"
    if probe_state == "not_checked":
        return "skipped"
    return "unproven"


def _self_probe_skipped_http_probes() -> dict[str, dict[str, Any]]:
    return {
        "dashboard_control_surface_rows": {
            "url": _DASHBOARD_ROWS_PROBE_URL,
            "state": "not_checked",
            "evidence": (
                "skipped inside control-surface row projection to avoid "
                "recursive dashboard rows self-probe"
            ),
        }
    }


def _live_ops_census_payload(repo_root: Path | None = None) -> dict[str, Any]:
    """Load or build the read-only live ops census."""
    root = repo_root or Path.cwd()
    try:
        output = Path(default_output_path())
        if output.exists():
            age = datetime.now(timezone.utc).timestamp() - output.stat().st_mtime
            if age <= _LIVE_OPS_CENSUS_CACHE_MAX_AGE_SECONDS:
                payload = json.loads(output.read_text(encoding="utf-8"))
                validation_errors = validate_census_payload(payload)
                freshness = census_payload_freshness(
                    payload,
                    max_age_hours=_LIVE_OPS_CENSUS_CACHE_MAX_AGE_SECONDS / 3600.0,
                )
                payload_is_fresh = str(freshness.get("state") or "") == "fresh"
                if not validation_errors and payload_is_fresh:
                    return payload
                if not payload_is_fresh:
                    logger.debug("live ops census cache generated_at is stale")
                elif validation_errors:
                    logger.debug(
                        "live ops census cache invalid: %s",
                        "; ".join(validation_errors),
                    )
    except (OSError, json.JSONDecodeError, ImportError):
        logger.debug("live ops census cache unreadable", exc_info=True)

    try:
        from scripts.runtime.live_ops_census import build_live_ops_census

        return build_live_ops_census(
            repo_root=root,
            run_probes=True,
            http_probes=_self_probe_skipped_http_probes(),
        )
    except Exception as exc:
        logger.warning("live ops census adapter failed: %s", exc)
        return {
            "schema_version": "live_ops_census.v1",
            "generated_at": _utc_now_iso(),
            "surfaces": [
                {
                    "id": "adapter.error",
                    "label": "Live ops census adapter",
                    "class": "substrate",
                    "status": "unknown",
                    "desired_state": "live",
                    "priority": "p0",
                    "evidence": [f"adapter error: {exc}"],
                    "authority_refs": ["scripts/runtime/live_ops_census.py"],
                    "human_authority_required": True,
                    "next_action": "inspect live ops census adapter",
                    "raw": {},
                }
            ],
        }


def _live_ops_coherence(surface: dict[str, Any]) -> str:
    sid = str(surface.get("id") or "unknown")
    status = str(surface.get("status") or "unknown")
    priority = str(surface.get("priority") or "unknown")
    raw = surface.get("raw") if isinstance(surface.get("raw"), dict) else {}
    proof_gaps = surface.get("proof_gaps")
    if (
        status == "live"
        and isinstance(proof_gaps, list)
        and any(str(item) for item in proof_gaps)
    ):
        return "partial"
    dashboard_probe = (
        raw.get("control_surface_rows_probe")
        if isinstance(raw.get("control_surface_rows_probe"), dict)
        else {}
    )
    dashboard_probe_state = str(dashboard_probe.get("state") or "")
    dispatch_launch = raw.get("dispatch_launch") if isinstance(raw, dict) else {}
    launch_state = (
        str(dispatch_launch.get("state") or "")
        if isinstance(dispatch_launch, dict)
        else ""
    )
    running_proof = str(raw.get("running_dispatch_proof") or "") if isinstance(raw, dict) else ""
    if sid == "substrate.dharma_daemon" and status == "live":
        if launch_state and launch_state != "spine_enabled_launch_spec":
            return "drifted"
        if running_proof not in _DAEMON_SPINE_RUNTIME_PROOFS:
            return "partial"
    if sid == "dashboard.local" and status == "live":
        if (
            dashboard_probe_state
            and dashboard_probe_state not in _DASHBOARD_API_PROBE_BOUND_STATES
        ):
            return "partial"
    if status == "live":
        return "bound"
    if status in {"blocked", "stale"}:
        return "drifted"
    if status == "stopped":
        return "drifted" if priority == "p0" else "partial"
    if status == "unknown":
        return "unknown"
    return "partial"


def _rows_from_live_ops_census(
    payload: dict[str, Any],
    repo_root: Path | None = None,
) -> list[ControlSurfaceRow]:
    root = repo_root or Path.cwd()
    rows: list[ControlSurfaceRow] = []
    for surface in payload.get("surfaces", []):
        sid = str(surface.get("id") or "unknown")
        status = str(surface.get("status") or "unknown")
        gap_codes = [f"live_ops_status:{status}"]
        raw = surface.get("raw") if isinstance(surface.get("raw"), dict) else {}
        for proof_gap in surface.get("proof_gaps") or []:
            proof_gap_code = str(proof_gap)
            _append_gap(gap_codes, proof_gap_code)
        if status != "live":
            _append_gap(gap_codes, "live_ops_not_live")
        if surface.get("human_authority_required"):
            _append_gap(gap_codes, "human_authority_required")
        if surface.get("vps_candidate"):
            _append_gap(gap_codes, "vps_candidate")
        if surface.get("class") == "heavy":
            _append_gap(gap_codes, "heavy_local_load")
        if sid == "dashboard.local":
            dashboard_probe = (
                raw.get("control_surface_rows_probe")
                if isinstance(raw.get("control_surface_rows_probe"), dict)
                else {}
            )
            dashboard_probe_state = str(dashboard_probe.get("state") or "")
            if (
                dashboard_probe_state
                and dashboard_probe_state not in _DASHBOARD_API_PROBE_BOUND_STATES
            ):
                _append_gap(gap_codes, "dashboard_control_surface_rows_unproven")
        if sid == "substrate.dharma_daemon":
            dispatch_launch = raw.get("dispatch_launch") if isinstance(raw, dict) else {}
            launch_state = (
                str(dispatch_launch.get("state") or "")
                if isinstance(dispatch_launch, dict)
                else ""
            )
            running_proof = (
                str(raw.get("running_dispatch_proof") or "")
                if isinstance(raw, dict)
                else ""
            )
            if launch_state != "spine_enabled_launch_spec":
                _append_gap(gap_codes, "daemon_launch_not_spine_enabled")
            if running_proof not in _DAEMON_SPINE_RUNTIME_PROOFS:
                _append_gap(gap_codes, "daemon_dispatch_runtime_unproven")

        row = ControlSurfaceRow(
            id=f"live_ops.{sid}",
            kind="fleet",
            label=str(surface.get("label") or sid),
            authority_role="observed_authority",
            declared_state=str(surface.get("desired_state") or ""),
            desired_state=str(surface.get("desired_state") or ""),
            observed_state=status,
            coherence_state=_live_ops_coherence(surface),
            priority=str(surface.get("priority") or "unknown"),
            owner_module="scripts/runtime/live_ops_census.py",
            truth_owner="live_ops_census",
            freshness=str(surface.get("freshness") or payload.get("generated_at") or ""),
            gap_codes=gap_codes,
            next_action=str(surface.get("next_action") or ""),
            raw=surface,
        )
        row.add_source_ref("file", "scripts/runtime/live_ops_census.py", exists=True)
        for ref in surface.get("authority_refs", []):
            ref_str = str(ref)
            if not ref_str:
                continue
            ref_path = Path(ref_str)
            if ref_path.is_absolute():
                row.add_source_ref("config", ref_str, exists=ref_path.exists())
            else:
                row.add_source_ref("file", ref_str, exists=(root / ref_str).exists())
        for ev in surface.get("evidence", []):
            ev_str = str(ev)
            if ev_str:
                row.add_evidence(
                    "process",
                    ev_str,
                    status=status,
                    provenance_chain=["live_ops_census", sid],
                )
        for proof_gap in surface.get("proof_gaps") or []:
            proof_gap_code = str(proof_gap)
            if proof_gap_code:
                row.add_evidence(
                    "process",
                    f"proof_gap={proof_gap_code}",
                    status="degraded" if proof_gap_code.endswith("_slow") else "unproven",
                    provenance_chain=["live_ops_census", sid, "proof_gaps"],
                )
        process_source = (
            raw.get("process_source_state")
            if isinstance(raw.get("process_source_state"), dict)
            else {}
        )
        if process_source:
            row.add_evidence(
                "process",
                _process_source_state_evidence_source(process_source),
                status=_process_source_state_status(process_source),
                raw_content=json.dumps(process_source, sort_keys=True),
                provenance_chain=["live_ops_census", sid, "process_source_state"],
            )
        if surface.get("pids"):
            row.add_evidence(
                "process",
                f"pids={','.join(str(pid) for pid in surface.get('pids', []))}",
                status="present",
                provenance_chain=["live_ops_census", sid, "process_snapshot"],
            )
        if surface.get("port"):
            port_status = "present" if surface.get("port_listening") else "missing"
            row.add_evidence(
                "process",
                f"port:{surface.get('port')}",
                status=port_status,
                provenance_chain=["live_ops_census", sid, "port_snapshot"],
            )
        if sid == "substrate.dharma_daemon":
            dispatch_launch = raw.get("dispatch_launch") if isinstance(raw, dict) else {}
            launch_state = (
                str(dispatch_launch.get("state") or "unknown")
                if isinstance(dispatch_launch, dict)
                else "unknown"
            )
            running_proof = (
                str(raw.get("running_dispatch_proof") or "unknown")
                if isinstance(raw, dict)
                else "unknown"
            )
            row.add_evidence(
                "process",
                f"daemon_dispatch launch={launch_state}; running={running_proof}",
                status=(
                    "present"
                    if running_proof in _DAEMON_SPINE_RUNTIME_PROOFS
                    else "unproven"
                ),
                provenance_chain=["live_ops_census", sid, "dispatch_state"],
            )
            receipt_head = (
                raw.get("runtime_receipt_active_head")
                if isinstance(raw.get("runtime_receipt_active_head"), dict)
                else {}
            )
            if receipt_head:
                clean = receipt_head.get("active_head_side_effect_key_clean")
                fresh = receipt_head.get("latest_fresh")
                row.add_evidence(
                    "db_probe",
                    _runtime_receipt_head_evidence_source(receipt_head),
                    status=(
                        "present" if clean is True and fresh is not False else "unproven"
                    ),
                    provenance_chain=[
                        "live_ops_census",
                        sid,
                        "runtime_receipt_active_head",
                    ],
                )
            receipt_coverage = (
                raw.get("runtime_receipt_coverage")
                if isinstance(raw.get("runtime_receipt_coverage"), dict)
                else {}
            )
            if receipt_coverage:
                row.add_evidence(
                    "db_probe",
                    _runtime_receipt_coverage_evidence_source(receipt_coverage),
                    status=_runtime_receipt_coverage_status(receipt_coverage),
                    raw_content=json.dumps(receipt_coverage, sort_keys=True),
                    provenance_chain=[
                        "live_ops_census",
                        sid,
                        "runtime_receipt_coverage",
                    ],
                )
        if sid == "dashboard.local":
            dashboard_probe = (
                raw.get("control_surface_rows_probe")
                if isinstance(raw.get("control_surface_rows_probe"), dict)
                else {}
            )
            dashboard_probe_state = str(dashboard_probe.get("state") or "unknown")
            row.add_evidence(
                "process",
                f"dashboard_control_surface_rows={dashboard_probe_state}",
                status=_dashboard_probe_evidence_status(dashboard_probe_state),
                provenance_chain=["live_ops_census", sid, "control_surface_rows_probe"],
            )
        if sid == "evidence.nats_receipts":
            ack_tier_state = (
                raw.get("ack_tier_state")
                if isinstance(raw.get("ack_tier_state"), dict)
                else {}
            )
            if ack_tier_state:
                row.add_evidence(
                    "go_receipt",
                    _nats_ack_tier_evidence_source(ack_tier_state),
                    status=_nats_ack_tier_evidence_status(ack_tier_state),
                    raw_content=json.dumps(ack_tier_state, sort_keys=True),
                    provenance_chain=["live_ops_census", sid, "ack_tier_state"],
                )
        if sid == "transport.a2a_bridge" and raw:
            row.add_evidence(
                "process",
                _a2a_bridge_state_evidence_source(raw),
                status=_a2a_bridge_state_evidence_status(raw),
                raw_content=json.dumps(raw, sort_keys=True),
                provenance_chain=["live_ops_census", sid, "a2a_bridge_state"],
            )
        if sid == "cli.ds_goal" and raw:
            row.add_evidence(
                "process",
                _ds_goal_cli_state_evidence_source(raw),
                status=_ds_goal_cli_state_evidence_status(raw),
                raw_content=json.dumps(raw, sort_keys=True),
                provenance_chain=["live_ops_census", sid, "ds_goal_cli_state"],
            )
        rows.append(row)
    return rows


def _live_ops_census_rows(repo_root: Path | None = None) -> list[ControlSurfaceRow]:
    return _rows_from_live_ops_census(_live_ops_census_payload(repo_root), repo_root)
