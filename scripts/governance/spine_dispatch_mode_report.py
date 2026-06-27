#!/usr/bin/env python3
"""Runtime-spine dispatch mode report.

This is a read-only governance verifier for the hardening gate:

    65 -> 70: orchestrator and A2A live ingress have proven default spine or
    explicitly marked legacy paths.

It does not claim that legacy paths are fixed. It makes their current dispatch
mode machine-checkable so the active track cannot drift into fake-green spine
adoption language.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import plistlib
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ORCHESTRATOR = _REPO_ROOT / "dharma_swarm" / "orchestrator.py"
_THINKODYNAMIC_DIRECTOR = _REPO_ROOT / "dharma_swarm" / "thinkodynamic_director.py"
_BYPASS_REPORT = _REPO_ROOT / "scripts" / "governance" / "spine_bypass_report.py"
_REPO_LAUNCH_PLIST = _REPO_ROOT / "com.dharma.swarm.plist"
_USER_LAUNCH_PLIST = Path.home() / "Library" / "LaunchAgents" / "com.dharma.swarm.plist"
_DAEMON_HEALTH_URL = "http://127.0.0.1:7433/health"
_LIVE_OPS_CENSUS_CONTRACT = (
    _REPO_ROOT / "dharma_swarm" / "operator_core" / "live_ops_census_contract.py"
)
_DIRECT_RUN_TASK_FILES = (
    _THINKODYNAMIC_DIRECTOR,
    _REPO_ROOT / "scripts" / "live_claude_code.py",
    _REPO_ROOT / "scripts" / "live_fanout.py",
    _REPO_ROOT / "scripts" / "live_genome_test.py",
    _REPO_ROOT / "scripts" / "live_test.py",
)


@dataclass(frozen=True)
class DispatchModeEntry:
    surface: str
    file: str
    line: int | None
    mode: str
    default_path: str
    activation: str
    current_state: str
    owner: str
    evidence: str
    verification: str
    risk: str


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def _line_number(path: Path, needle: str) -> int | None:
    try:
        for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if needle in line:
                return idx
    except OSError:
        return None
    return None


def _load_bypass_report() -> Any:
    spec = importlib.util.spec_from_file_location("spine_bypass_report", _BYPASS_REPORT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {_BYPASS_REPORT}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_live_ops_census_contract() -> Any | None:
    spec = importlib.util.spec_from_file_location(
        "live_ops_census_contract",
        _LIVE_OPS_CENSUS_CONTRACT,
    )
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod


def _census_receipt_path() -> Path | None:
    mod = _load_live_ops_census_contract()
    if mod is None:
        return None
    if hasattr(mod, "default_output_path"):
        return Path(mod.default_output_path())
    return Path(mod.DEFAULT_OUTPUT)


def _validate_live_census_payload(payload: Any) -> list[str]:
    mod = _load_live_ops_census_contract()
    if mod is not None and hasattr(mod, "validate_census_payload"):
        return [str(error) for error in mod.validate_census_payload(payload)]
    if not isinstance(payload, dict):
        return ["live ops census receipt root is not a JSON object"]
    return []


def _live_census_freshness(payload: Any) -> dict[str, Any]:
    mod = _load_live_ops_census_contract()
    if mod is not None and hasattr(mod, "census_payload_freshness"):
        result = mod.census_payload_freshness(payload)
        return result if isinstance(result, dict) else {}
    return {
        "state": "unknown",
        "age_minutes": None,
        "evidence": "live ops census freshness helper unavailable",
    }


def _launch_uses_repo_module(command: str, repo_root: Path) -> bool:
    repo_text = str(repo_root)
    return "-m dharma_swarm.dgc_cli orchestrate-live" in command and (
        f"PYTHONPATH={repo_text}" in command
        or "PYTHONPATH=." in command
        or f"cd {repo_text}" in command
        or ".venv/bin/python" in command
    )


def _launch_uses_ambient_dgc(command: str) -> bool:
    return re.search(r"(^|[\s/])dgc\s+orchestrate-live\b", command) is not None


def _inspect_launch_plist(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": _rel(path),
        "exists": path.exists(),
        "state": "launch_spec_missing",
        "command": "",
        "env": {},
        "evidence": "plist not found",
    }
    if not path.exists():
        return result

    try:
        with path.open("rb") as handle:
            data = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as exc:
        result.update(
            state="launch_spec_unreadable",
            evidence=f"unable to parse launch plist: {exc}",
        )
        return result

    args = data.get("ProgramArguments") or []
    env_vars = data.get("EnvironmentVariables") or {}
    command = " ".join(str(arg) for arg in args)
    env_value = str(env_vars.get("DHARMA_SPINE_DISPATCH", ""))
    command_mentions_flag = "DHARMA_SPINE_DISPATCH" in command
    spine_enabled = env_value == "1" or "DHARMA_SPINE_DISPATCH=1" in command
    repo_module_invocation = _launch_uses_repo_module(command, _REPO_ROOT)
    ambient_dgc_invocation = _launch_uses_ambient_dgc(command)

    if spine_enabled and repo_module_invocation:
        state = "spine_enabled_launch_spec"
        evidence = (
            "launch spec declares DHARMA_SPINE_DISPATCH=1 and invokes "
            "repo-pinned dharma_swarm.dgc_cli module"
        )
    elif spine_enabled and ambient_dgc_invocation:
        state = "ambient_dgc_spine_launch_spec"
        evidence = (
            "launch spec declares DHARMA_SPINE_DISPATCH=1 but invokes ambient "
            "dgc console script instead of the repo-pinned module"
        )
    elif spine_enabled:
        state = "unblessed_spine_launch_spec"
        evidence = (
            "launch spec declares DHARMA_SPINE_DISPATCH=1 but command is not "
            "repo-pinned to this checkout"
        )
    elif env_value or command_mentions_flag:
        state = "explicit_non_spine_launch_spec"
        evidence = "launch spec mentions DHARMA_SPINE_DISPATCH but does not set it to 1"
    else:
        state = "legacy_default_launch_spec"
        evidence = "launch spec does not set DHARMA_SPINE_DISPATCH"

    result.update(
        state=state,
        command=command,
        env=env_vars,
        evidence=evidence,
        repo_module_invocation=repo_module_invocation,
        ambient_dgc_invocation=ambient_dgc_invocation,
    )
    return result


def _fetch_json(url: str, *, timeout_seconds: float = 1.5) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read(65536)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("health response JSON is not an object")
        return int(response.status), payload


def _daemon_health_self_report(
    *,
    url: str = _DAEMON_HEALTH_URL,
    timeout_seconds: float = 1.5,
    probe: bool = False,
) -> dict[str, Any]:
    if not probe:
        return {
            "url": url,
            "state": "not_checked",
            "evidence": "live daemon health probe disabled for pure report build",
        }
    try:
        status, payload = _fetch_json(url, timeout_seconds=timeout_seconds)
    except TimeoutError as exc:
        return {
            "url": url,
            "state": "timeout",
            "evidence": f"timed out after {timeout_seconds}s: {exc}",
        }
    except urllib.error.URLError as exc:
        return {
            "url": url,
            "state": "unreachable",
            "evidence": str(exc.reason),
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "url": url,
            "state": "unreadable",
            "evidence": str(exc),
        }

    runtime_dispatch = payload.get("runtime_dispatch")
    if not isinstance(runtime_dispatch, dict):
        return {
            "url": url,
            "http_status": status,
            "state": "missing_runtime_dispatch",
            "evidence": "health JSON did not include runtime_dispatch",
        }

    enabled = runtime_dispatch.get("spine_dispatch_enabled")
    if enabled is True:
        state = "spine_enabled_self_report"
    elif enabled is False:
        state = "legacy_self_report"
    else:
        state = "ambiguous_runtime_dispatch"

    return {
        "url": url,
        "http_status": status,
        "state": state,
        "runtime_dispatch": {
            "spine_dispatch_enabled": enabled,
            "dispatch_mode": runtime_dispatch.get("dispatch_mode"),
            "env_key_present": runtime_dispatch.get("env_key_present"),
            "source": runtime_dispatch.get("source"),
        },
        "evidence": "daemon /health returned non-secret runtime_dispatch block",
    }


def _compact_runtime_receipt_head(head: dict[str, Any]) -> dict[str, Any]:
    windows: list[dict[str, Any]] = []
    for row in head.get("windows") or []:
        if not isinstance(row, dict):
            continue
        windows.append(
            {
                "window_minutes": row.get("window_minutes"),
                "total": row.get("total"),
                "missing_side_effect_key": row.get("missing_side_effect_key"),
                "missing_side_effect_key_percent": row.get(
                    "missing_side_effect_key_percent"
                ),
            }
        )
    return {
        "active_head_side_effect_key_clean": head.get(
            "active_head_side_effect_key_clean"
        ),
        "runtime_receipts_total": head.get("runtime_receipts_total"),
        "latest_created_at": head.get("latest_created_at"),
        "latest_age_hours": head.get("latest_age_hours"),
        "latest_max_age_hours": head.get("latest_max_age_hours"),
        "latest_fresh": head.get("latest_fresh"),
        "windows": windows,
    }


def _format_runtime_receipt_head(head: dict[str, Any]) -> str:
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
        window_parts.append(
            f"{row.get('window_minutes')}m:"
            f"{row.get('missing_side_effect_key')}/{row.get('total')}"
        )
    windows = ",".join(window_parts) if window_parts else "none"
    return (
        f"clean={clean_text}; fresh={fresh_text}; "
        f"age_hours={age_text}; max_age_hours={max_age_text}; "
        f"total={total}; latest={latest}; windows={windows}"
    )


def _compact_runtime_receipt_coverage(coverage: dict[str, Any]) -> dict[str, Any]:
    return {
        "coverage_report_available": coverage.get("coverage_report_available"),
        "runtime_receipts_total": coverage.get("runtime_receipts_total"),
        "major_task_receipts_total": coverage.get("major_task_receipts_total"),
        "latest_sample_size": coverage.get("latest_sample_size"),
        "latest_with_provider_payload": coverage.get("latest_with_provider_payload"),
        "latest_with_model_payload": coverage.get("latest_with_model_payload"),
        "latest_with_provider_model_payload": coverage.get(
            "latest_with_provider_model_payload"
        ),
        "latest_with_provider_model_provenance": coverage.get(
            "latest_with_provider_model_provenance"
        ),
        "latest_with_provider_model_accounted": coverage.get(
            "latest_with_provider_model_accounted"
        ),
        "latest_provider_model_pending_execution": coverage.get(
            "latest_provider_model_pending_execution"
        ),
        "latest_terminal_sample_size": coverage.get("latest_terminal_sample_size"),
        "latest_terminal_with_provider_model_payload": coverage.get(
            "latest_terminal_with_provider_model_payload"
        ),
        "latest_terminal_with_provider_model_provenance": coverage.get(
            "latest_terminal_with_provider_model_provenance"
        ),
        "latest_terminal_with_provider_model_accounted": coverage.get(
            "latest_terminal_with_provider_model_accounted"
        ),
        "latest_major_task_receipts_provider_model_percent": coverage.get(
            "latest_major_task_receipts_provider_model_percent"
        ),
        "latest_major_task_receipts_provider_model_provenance_percent": coverage.get(
            "latest_major_task_receipts_provider_model_provenance_percent"
        ),
        "latest_major_task_receipts_provider_model_accounted_percent": coverage.get(
            "latest_major_task_receipts_provider_model_accounted_percent"
        ),
        "latest_terminal_major_task_receipts_provider_model_percent": coverage.get(
            "latest_terminal_major_task_receipts_provider_model_percent"
        ),
        "latest_terminal_major_task_receipts_provider_model_provenance_percent": (
            coverage.get("latest_terminal_major_task_receipts_provider_model_provenance_percent")
        ),
        "latest_terminal_major_task_receipts_provider_model_accounted_percent": (
            coverage.get("latest_terminal_major_task_receipts_provider_model_accounted_percent")
        ),
        "provider_model_payload_complete": coverage.get(
            "provider_model_payload_complete"
        ),
        "provider_model_provenance_complete": coverage.get(
            "provider_model_provenance_complete"
        ),
        "provider_model_accounted_complete": coverage.get(
            "provider_model_accounted_complete"
        ),
        "terminal_provider_model_payload_complete": coverage.get(
            "terminal_provider_model_payload_complete"
        ),
        "terminal_provider_model_provenance_complete": coverage.get(
            "terminal_provider_model_provenance_complete"
        ),
        "terminal_provider_model_accounted_complete": coverage.get(
            "terminal_provider_model_accounted_complete"
        ),
        "provider_model_latest_complete": coverage.get(
            "provider_model_latest_complete"
        ),
        "production_readiness_blockers": coverage.get(
            "production_readiness_blockers"
        )
        or [],
        "active_head_gap_producer_groups": coverage.get(
            "active_head_gap_producer_groups"
        )
        or [],
        "field_gap_producer_groups": coverage.get("field_gap_producer_groups") or [],
        "field_gap_summary": coverage.get("field_gap_summary") or {},
        "field_gap_action_queue": coverage.get("field_gap_action_queue") or [],
        "gate_70_to_75_components": coverage.get("gate_70_to_75_components") or [],
        "latest_provider_model_unproven_producer_groups": coverage.get(
            "latest_provider_model_unproven_producer_groups"
        )
        or [],
        "latest_provider_model_payload_class_breakdown": coverage.get(
            "latest_provider_model_payload_class_breakdown"
        )
        or {},
        "latest_terminal_provider_model_payload_class_breakdown": coverage.get(
            "latest_terminal_provider_model_payload_class_breakdown"
        )
        or {},
    }


def _provider_model_class_text(coverage: dict[str, Any]) -> str:
    breakdown = coverage.get("latest_provider_model_payload_class_breakdown")
    if not isinstance(breakdown, dict) or not breakdown:
        return ""
    parts = [
        f"{key}={value}"
        for key, value in sorted((str(key), value) for key, value in breakdown.items())
    ]
    return "; classes=" + "|".join(parts)


def _field_gap_summary_text(coverage: dict[str, Any]) -> str:
    summary = coverage.get("field_gap_summary")
    if not isinstance(summary, dict):
        return ""
    total = int(summary.get("total_missing") or 0)
    if total <= 0:
        return ""
    freshness = summary.get("by_freshness_class")
    freshness_counts = freshness if isinstance(freshness, dict) else {}
    parts = [f"total:{total}"]
    for key in (
        "active_head_60m",
        "recent_historical_24h",
        "older_historical",
        "unknown",
        "future_clock_skew",
    ):
        count = int(freshness_counts.get(key) or 0)
        if count > 0:
            parts.append(f"{key}:{count}")
    quarantine_count = int(summary.get("quarantine_candidate_missing") or 0)
    if quarantine_count > 0:
        parts.append(f"quarantine_candidate:{quarantine_count}")
    return "; field_gap_summary=" + "|".join(parts)


def _field_gap_actions_text(coverage: dict[str, Any]) -> str:
    queue = [
        item
        for item in coverage.get("field_gap_action_queue") or []
        if isinstance(item, dict)
    ]
    if not queue:
        return ""
    parts = []
    for item in queue[:7]:
        label = item.get("short_label") or item.get("action") or "unknown"
        parts.append(f"{label}:{int(item.get('missing') or 0)}")
    return "; field_gap_actions=" + "|".join(parts)


def _compact_fresh_proof_status(status: Any) -> str:
    status_text = str(status or "")
    statuses = {
        "fresh_scoped_proof_recorded": "fresh",
        "pin_mitigation_proof_recorded_default_still_broken": (
            "pin_proved_default_dirty"
        ),
        "candidate_policy_recorded_not_applied": "policy_candidate",
        "fresh_proof_not_recorded": "missing",
    }
    return statuses.get(status_text, status_text)


def _field_gap_proofs_text(coverage: dict[str, Any]) -> str:
    queue = [
        item
        for item in coverage.get("field_gap_action_queue") or []
        if isinstance(item, dict)
    ]
    if not queue:
        return ""
    parts = []
    for item in queue[:7]:
        fresh_proof = (
            item.get("fresh_proof")
            if isinstance(item.get("fresh_proof"), dict)
            else {}
        )
        status = _compact_fresh_proof_status(fresh_proof.get("status"))
        if not status:
            continue
        label = item.get("short_label") or item.get("action") or "unknown"
        parts.append(f"{label}:{status}")
    if not parts:
        return ""
    return "; field_gap_proofs=" + "|".join(parts)


def _gate_70_to_75_text(coverage: dict[str, Any]) -> str:
    components = [
        item
        for item in coverage.get("gate_70_to_75_components") or []
        if isinstance(item, dict)
    ]
    if not components:
        return ""
    parts = []
    for item in components[:5]:
        label = item.get("short_label") or item.get("id") or "unknown"
        status = item.get("status")
        if not status:
            status = "pass" if item.get("passed") else "fail"
        parts.append(f"{label}:{status}")
    return "; gate_70_75=" + "|".join(parts)


def _format_runtime_receipt_coverage(coverage: dict[str, Any]) -> str:
    available = str(bool(coverage.get("coverage_report_available"))).lower()
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
    complete = coverage.get("provider_model_latest_complete")
    complete_text = "unknown" if complete is None else str(bool(complete)).lower()
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
    blockers = [
        str(blocker)
        for blocker in coverage.get("production_readiness_blockers") or []
        if str(blocker)
    ]
    blocker_text = "; readiness_blockers=" + "|".join(blockers) if blockers else ""
    gap_groups = [
        group
        for group in coverage.get("active_head_gap_producer_groups") or []
        if isinstance(group, dict)
    ]
    gap_text = ""
    if gap_groups:
        parts = []
        for group in gap_groups[:3]:
            parts.append(
                f"{group.get('window_minutes')}m:"
                f"{group.get('receipt_type')}/"
                f"{group.get('producer_source')}/"
                f"{group.get('producer_failure_code')}"
                f"={group.get('missing_side_effect_key')}"
            )
        gap_text = "; active_head_gap_producers=" + "|".join(parts)
    provider_model_gap_groups = [
        group
        for group in coverage.get("latest_provider_model_unproven_producer_groups") or []
        if isinstance(group, dict)
    ]
    provider_model_gap_text = ""
    if provider_model_gap_groups:
        parts = []
        for group in provider_model_gap_groups[:3]:
            parts.append(
                f"{group.get('receipt_type')}/"
                f"{group.get('provider_model_payload_class')}/"
                f"{group.get('producer_source')}/"
                f"{group.get('producer_failure_code')}"
                f"={group.get('missing_provider_model_provenance')}"
            )
        provider_model_gap_text = "; provider_model_gap_producers=" + "|".join(parts)
    field_gap_groups = [
        group
        for group in coverage.get("field_gap_producer_groups") or []
        if isinstance(group, dict)
    ]
    field_gap_text = ""
    if field_gap_groups:
        parts = []
        for group in field_gap_groups[:3]:
            freshness = group.get("freshness_class") or "unknown"
            parts.append(
                f"{group.get('gap_type')}/"
                f"{group.get('receipt_type')}/"
                f"{group.get('producer_source')}/"
                f"{group.get('producer_failure_code')}/"
                f"{group.get('topology')}"
                f"={group.get('missing')}@{freshness}"
            )
        field_gap_text = "; field_gap_producers=" + "|".join(parts)
    return (
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
        f"complete={complete_text}; "
        f"major_total={major_total}"
        f"{_provider_model_class_text(coverage)}"
        f"{blocker_text}"
        f"{gap_text}"
        f"{provider_model_gap_text}"
        f"{field_gap_text}"
        f"{_field_gap_summary_text(coverage)}"
        f"{_field_gap_actions_text(coverage)}"
        f"{_field_gap_proofs_text(coverage)}"
        f"{_gate_70_to_75_text(coverage)}"
    )


def _compact_ds_goal_wrapper_contract(raw: dict[str, Any]) -> dict[str, Any]:
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
    decision = (
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
        "target_repo": str(raw.get("target_repo") or ""),
        "target_resolution_source": str(raw.get("target_resolution_source") or ""),
        "target_matches_current_repo": raw.get("target_matches_current_repo"),
        "default_target_repo": str(default_target.get("target_repo") or ""),
        "default_target_resolution_source": str(
            default_target.get("target_resolution_source") or ""
        ),
        "wrapper_sha256": str(contract.get("wrapper_sha256") or ""),
        "dharma_swarm_repo_pin_supported": contract.get(
            "dharma_swarm_repo_pin_supported"
        ),
        "dharma_swarm_main_preference_declared": contract.get(
            "dharma_swarm_main_preference_declared"
        ),
        "dharma_swarm_fallback_declared": contract.get(
            "dharma_swarm_fallback_declared"
        ),
        "execs_autonomy_spine": contract.get("execs_autonomy_spine"),
        "target_sync_receipt_hardening_state": str(hardening.get("state") or ""),
        "safe_current_checkout_invocation": str(
            raw.get("safe_current_checkout_invocation") or ""
        ),
        "convergence_decision_state": str(decision.get("approval_state") or ""),
        "longrun_preflight_status": str(preflight.get("status") or ""),
    }


def _format_ds_goal_wrapper_contract(contract: dict[str, Any]) -> str:
    if not contract:
        return ""
    sha = str(contract.get("wrapper_sha256") or "")
    sha_label = sha[:12] if sha else "<missing>"
    safe = str(contract.get("safe_current_checkout_invocation") or "")
    safe_text = (
        f"; safe={safe}"
        if safe and contract.get("target_matches_current_repo") is False
        else ""
    )
    decision = str(contract.get("convergence_decision_state") or "")
    decision_text = f"; decision={decision}" if decision else ""
    preflight = str(contract.get("longrun_preflight_status") or "")
    preflight_text = f"; preflight={preflight}" if preflight else ""
    return (
        f"target={contract.get('target_repo') or '<blank>'}; "
        f"source={contract.get('target_resolution_source') or '<blank>'}; "
        f"matches_current={str(contract.get('target_matches_current_repo')).lower()}; "
        f"default={contract.get('default_target_repo') or '<blank>'}; "
        f"default_source={contract.get('default_target_resolution_source') or '<blank>'}; "
        f"wrapper_sha256={sha_label}; "
        f"pin={str(contract.get('dharma_swarm_repo_pin_supported')).lower()}; "
        f"main={str(contract.get('dharma_swarm_main_preference_declared')).lower()}; "
        f"fallback={str(contract.get('dharma_swarm_fallback_declared')).lower()}; "
        f"autonomy_spine={str(contract.get('execs_autonomy_spine')).lower()}; "
        f"hardening={contract.get('target_sync_receipt_hardening_state') or '<unknown>'}"
        f"{decision_text}"
        f"{preflight_text}"
        f"{safe_text}"
    )


def _invalid_live_census(path: Path, evidence: str) -> dict[str, Any]:
    return {
        "state": "receipt_invalid",
        "receipt": str(path),
        "generated_at": "",
        "proof_gap_surfaces": [],
        "source_stale_surfaces": [],
        "evidence": evidence,
        "freshness": {},
    }


def _stale_live_census(
    path: Path,
    *,
    generated_at: str,
    freshness: dict[str, Any],
) -> dict[str, Any]:
    evidence = str(freshness.get("evidence") or "live ops census receipt is stale")
    age = freshness.get("age_minutes")
    if age is not None:
        evidence = f"{evidence}; age_minutes={age}"
    return {
        "state": "receipt_stale",
        "receipt": str(path),
        "generated_at": generated_at,
        "proof_gap_surfaces": [],
        "source_stale_surfaces": [],
        "evidence": evidence,
        "freshness": freshness,
    }


def _live_census_summary() -> dict[str, Any]:
    path = _census_receipt_path()
    if path is None:
        return {
            "state": "census_owner_unavailable",
            "receipt": "",
            "generated_at": "",
            "proof_gap_surfaces": [],
            "source_stale_surfaces": [],
            "evidence": "unable to import scripts/runtime/live_ops_census.py",
            "freshness": {},
        }
    if not path.exists():
        return {
            "state": "receipt_missing",
            "receipt": str(path),
            "generated_at": "",
            "proof_gap_surfaces": [],
            "source_stale_surfaces": [],
            "evidence": "live ops census receipt is missing",
            "freshness": {},
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "state": "receipt_unreadable",
            "receipt": str(path),
            "generated_at": "",
            "proof_gap_surfaces": [],
            "source_stale_surfaces": [],
            "evidence": f"unable to read live ops census receipt: {exc}",
            "freshness": {},
        }

    validation_errors = _validate_live_census_payload(payload)
    if validation_errors:
        return _invalid_live_census(path, "; ".join(validation_errors))

    generated_at = str(payload.get("generated_at") or "")
    freshness = _live_census_freshness(payload)
    if str(freshness.get("state") or "") == "stale":
        return _stale_live_census(
            path,
            generated_at=generated_at,
            freshness=freshness,
        )
    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, list):
        return _invalid_live_census(
            path,
            "live ops census receipt surfaces is missing or not a list",
        )

    proof_gap_surfaces: list[dict[str, Any]] = []
    source_stale_surfaces: list[dict[str, Any]] = []
    for surface in surfaces:
        if not isinstance(surface, dict):
            continue
        proof_gaps = [
            str(item)
            for item in surface.get("proof_gaps") or []
            if str(item)
        ]
        if not proof_gaps:
            continue
        raw = surface.get("raw") if isinstance(surface.get("raw"), dict) else {}
        process_source = (
            raw.get("process_source_state")
            if isinstance(raw.get("process_source_state"), dict)
            else {}
        )
        row = {
            "id": str(surface.get("id") or surface.get("surface_id") or ""),
            "label": str(surface.get("label") or ""),
            "status": str(surface.get("status") or ""),
            "proof_gaps": proof_gaps,
            "pids": [str(pid) for pid in surface.get("pids") or []],
            "process_source_state": process_source,
        }
        receipt_head = (
            raw.get("runtime_receipt_active_head")
            if isinstance(raw.get("runtime_receipt_active_head"), dict)
            else {}
        )
        if receipt_head:
            row["runtime_receipt_active_head"] = _compact_runtime_receipt_head(receipt_head)
        receipt_coverage = (
            raw.get("runtime_receipt_coverage")
            if isinstance(raw.get("runtime_receipt_coverage"), dict)
            else {}
        )
        if receipt_coverage:
            row["runtime_receipt_coverage"] = _compact_runtime_receipt_coverage(
                receipt_coverage
            )
        if row["id"] == "cli.ds_goal":
            row["ds_goal_wrapper_contract"] = _compact_ds_goal_wrapper_contract(raw)
        proof_gap_surfaces.append(row)
        if any(gap.endswith("_source_stale") for gap in proof_gaps):
            source_stale_surfaces.append(row)

    state = "proof_gaps_present" if proof_gap_surfaces else "bound"
    return {
        "state": state,
        "receipt": str(path),
        "generated_at": generated_at,
        "proof_gap_surfaces": proof_gap_surfaces,
        "source_stale_surfaces": source_stale_surfaces,
        "evidence": (
            "live ops census projects runtime proof gaps"
            if proof_gap_surfaces
            else "live ops census has no proof-gap surfaces"
        ),
        "freshness": freshness,
    }


def _orchestrator_entry(env: Mapping[str, str]) -> DispatchModeEntry:
    try:
        text = _ORCHESTRATOR.read_text(encoding="utf-8")
    except OSError as exc:
        return DispatchModeEntry(
            surface="orchestrator",
            file=_rel(_ORCHESTRATOR),
            line=None,
            mode="ambiguous",
            default_path="unknown",
            activation="unknown",
            current_state="orchestrator_source_unreadable",
            owner="runtime-truth-spine-adoption-2026-06",
            evidence=f"unable to read orchestrator source: {exc}",
            verification="python3 scripts/governance/spine_dispatch_mode_report.py --strict",
            risk="high",
        )

    required = [
        "async def _run_task_via_spine",
        "invoke_agent",
        "DHARMA_SPINE_DISPATCH",
        "runner.run_task(task)",
    ]
    missing = [needle for needle in required if needle not in text]
    current_state = (
        "spine_enabled_in_current_process"
        if env.get("DHARMA_SPINE_DISPATCH") == "1"
        else "legacy_default_in_current_process"
    )
    if missing:
        mode = "ambiguous"
        default_path = "unknown"
        activation = "missing required source marker(s): " + ", ".join(missing)
        risk = "high"
    else:
        mode = "spine_opt_in_legacy_default"
        default_path = "direct runner.run_task unless DHARMA_SPINE_DISPATCH=1"
        activation = "set DHARMA_SPINE_DISPATCH=1 to route through invoke_agent"
        risk = "medium"

    return DispatchModeEntry(
        surface="orchestrator",
        file=_rel(_ORCHESTRATOR),
        line=_line_number(_ORCHESTRATOR, 'os.environ.get("DHARMA_SPINE_DISPATCH")'),
        mode=mode,
        default_path=default_path,
        activation=activation,
        current_state=current_state,
        owner="runtime-truth-spine-adoption-2026-06",
        evidence="_execute_task branches on DHARMA_SPINE_DISPATCH before runner.run_task",
        verification="tests/test_orchestrator_spine_dispatch.py",
        risk=risk,
    )


def _launch_entry(primary_plist: dict[str, Any]) -> DispatchModeEntry:
    state = str(primary_plist["state"])
    risk = (
        "medium"
        if state
        in {
            "legacy_default_launch_spec",
            "ambient_dgc_spine_launch_spec",
            "unblessed_spine_launch_spec",
        }
        else "low"
    )
    if state in {"launch_spec_missing", "launch_spec_unreadable"}:
        risk = "high"

    return DispatchModeEntry(
        surface="orchestrator.persistent-daemon",
        file=str(primary_plist["file"]),
        line=None,
        mode=state,
        default_path=(
            "launchd dgc orchestrate-live inherits legacy orchestrator default"
            if state == "legacy_default_launch_spec"
            else "launchd invokes ambient dgc console script, not this checkout"
            if state == "ambient_dgc_spine_launch_spec"
            else "launch spec is spine-enabled but not repo-pinned"
            if state == "unblessed_spine_launch_spec"
            else "launch spec declares an explicit dispatch mode"
        ),
        activation="LaunchAgent EnvironmentVariables or command string",
        current_state=state,
        owner="runtime-truth-spine-adoption-2026-06",
        evidence=str(primary_plist["evidence"]),
        verification="plutil -p ~/Library/LaunchAgents/com.dharma.swarm.plist",
        risk=risk,
    )


def _a2a_entries() -> list[DispatchModeEntry]:
    bypass_report = _load_bypass_report()
    entries: list[DispatchModeEntry] = []
    for bypass in bypass_report._scan_production_submits():
        if bypass.classification == "spine-adopted":
            mode = "spine_native_adapter"
            default_path = "submit_via_spine invokes invoke_agent around A2AServer.submit"
            current_state = "spine_available_for_explicit_call"
            risk = "low"
        elif bypass.classification == "intentional":
            mode = "legacy_quarantined"
            default_path = "direct A2AServer.submit legacy path"
            current_state = "legacy_path_explicitly_quarantined"
            risk = "medium"
        elif bypass.classification == "non-production":
            mode = "non_production"
            default_path = "not a live production dispatch path"
            current_state = "excluded_from_live_ingress"
            risk = "low"
        else:
            mode = "unknown_dispatch_mode"
            default_path = "unknown"
            current_state = "unknown"
            risk = "high"

        entries.append(
            DispatchModeEntry(
                surface=f"a2a.{bypass.classification}",
                file=bypass.file,
                line=bypass.line,
                mode=mode,
                default_path=default_path,
                activation=(
                    getattr(bypass, "migration_target", "")
                    if bypass.classification == "intentional"
                    else getattr(bypass, "reason", "")
                ),
                current_state=current_state,
                owner=getattr(bypass, "owner", ""),
                evidence=getattr(bypass, "reason", ""),
                verification=getattr(bypass, "verification", ""),
                risk=risk,
            )
        )
    return entries


def _direct_runner_entries() -> list[DispatchModeEntry]:
    entries: list[DispatchModeEntry] = []
    for path in _DIRECT_RUN_TASK_FILES:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for idx, line in enumerate(lines, 1):
            has_direct_run_task = ".run_task(" in line
            has_manual_spine_wrapper = "run_manual_agent_runner_via_spine(" in line
            if not has_direct_run_task and not has_manual_spine_wrapper:
                continue
            rel_path = _rel(path)
            if path == _THINKODYNAMIC_DIRECTOR:
                if not has_direct_run_task:
                    continue
                context = "\n".join(lines[max(0, idx - 90):idx + 70])
                if "_run_named_swarm_runner_via_spine" in context and "invoke_agent" in context:
                    mode = "spine_wrapped_direct_runner"
                    default_path = "named swarm runner is called inside invoke_agent"
                    current_state = "wrapped_by_runtime_spine"
                    activation = "director named-runner execution traverses invoke_agent"
                    risk = "low"
                else:
                    mode = "legacy_direct_runner"
                    default_path = "named swarm runner calls AgentRunner.run_task directly"
                    current_state = "not_wrapped_by_runtime_spine"
                    activation = "migrate named-runner execution through invoke_agent or quarantine with receipts"
                    risk = "medium"
            else:
                if has_manual_spine_wrapper:
                    mode = "manual_live_spine_wrapped"
                    default_path = "manual script calls AgentRunner through invoke_agent helper"
                    current_state = "manual_operator_script_spine_wrapped_not_default_daemon"
                    activation = "manual integration script; still excluded from daemon readiness"
                    risk = "low"
                else:
                    mode = "manual_live_script"
                    default_path = "manual script calls AgentRunner.run_task directly"
                    current_state = "manual_operator_script_not_default_daemon"
                    activation = "manual integration script; exclude from daemon readiness until wrapped or marked non-production"
                    risk = "low"
            entries.append(
                DispatchModeEntry(
                    surface=f"agent_runner.{mode}",
                    file=rel_path,
                    line=idx,
                    mode=mode,
                    default_path=default_path,
                    activation=activation,
                    current_state=current_state,
                    owner="runtime-truth-spine-adoption-2026-06",
                    evidence=line.strip(),
                    verification="python3 scripts/governance/spine_dispatch_mode_report.py --strict",
                    risk=risk,
                )
            )
    return entries


def build_report(
    *,
    repo_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    probe_daemon_health: bool = False,
    daemon_health_url: str = _DAEMON_HEALTH_URL,
    daemon_health_timeout_seconds: float = 1.5,
) -> dict[str, Any]:
    if repo_root is not None and repo_root.resolve() != _REPO_ROOT:
        raise ValueError("repo_root override is not supported; run this from dharma_swarm")
    current_env = os.environ if env is None else env

    launch_specs = [
        _inspect_launch_plist(_USER_LAUNCH_PLIST),
        _inspect_launch_plist(_REPO_LAUNCH_PLIST),
    ]
    primary_launch = next((item for item in launch_specs if item["exists"]), launch_specs[0])

    entries = [_orchestrator_entry(current_env), _launch_entry(primary_launch)]
    entries.extend(_a2a_entries())
    entries.extend(_direct_runner_entries())

    mode_counts = Counter(entry.mode for entry in entries)
    a2a_unknown = mode_counts.get("unknown_dispatch_mode", 0)
    a2a_legacy_quarantined = mode_counts.get("legacy_quarantined", 0)
    a2a_spine_native = mode_counts.get("spine_native_adapter", 0)
    agent_runner_legacy_direct = mode_counts.get("legacy_direct_runner", 0)
    agent_runner_spine_wrapped = mode_counts.get("spine_wrapped_direct_runner", 0)
    agent_runner_manual_scripts = mode_counts.get("manual_live_script", 0)
    agent_runner_manual_spine_wrapped = mode_counts.get("manual_live_spine_wrapped", 0)
    intentional_quarantine_complete = all(
        entry.owner and entry.verification and entry.current_state == "legacy_path_explicitly_quarantined"
        for entry in entries
        if entry.mode == "legacy_quarantined"
    )
    orchestrator_mode = entries[0].mode
    persistent_daemon = entries[1].mode
    explicit_modes = (
        orchestrator_mode != "ambiguous"
        and persistent_daemon == "spine_enabled_launch_spec"
        and a2a_unknown == 0
        and intentional_quarantine_complete
    )
    production_direct_runner_clear = agent_runner_legacy_direct == 0
    manual_direct_runner_clear = agent_runner_manual_scripts == 0
    score_gate_65_to_70 = explicit_modes and production_direct_runner_clear
    daemon_health = _daemon_health_self_report(
        url=daemon_health_url,
        timeout_seconds=daemon_health_timeout_seconds,
        probe=probe_daemon_health,
    )
    live_census = _live_census_summary()

    return {
        "report": "spine_dispatch_mode_report",
        "repo": str(_REPO_ROOT),
        "summary": {
            "orchestrator_mode": orchestrator_mode,
            "orchestrator_current_process": entries[0].current_state,
            "orchestrator_persistent_daemon": persistent_daemon,
            "a2a_spine_native": a2a_spine_native,
            "a2a_legacy_quarantined": a2a_legacy_quarantined,
            "a2a_unknown": a2a_unknown,
            "agent_runner_legacy_direct": agent_runner_legacy_direct,
            "agent_runner_spine_wrapped": agent_runner_spine_wrapped,
            "agent_runner_manual_scripts": agent_runner_manual_scripts,
            "agent_runner_manual_spine_wrapped": agent_runner_manual_spine_wrapped,
            "production_direct_runner_clear": production_direct_runner_clear,
            "manual_direct_runner_clear": manual_direct_runner_clear,
            "intentional_quarantine_complete": intentional_quarantine_complete,
            "explicit_modes": explicit_modes,
            "daemon_health_self_report": daemon_health["state"],
            "live_census_state": live_census["state"],
            "live_census_proof_gap_surfaces": len(live_census["proof_gap_surfaces"]),
            "live_census_source_stale_surfaces": len(live_census["source_stale_surfaces"]),
            "score_gate_65_to_70": score_gate_65_to_70,
        },
        "daemon_health": daemon_health,
        "live_census": live_census,
        "launch_specs": launch_specs,
        "entries": [asdict(entry) for entry in entries],
    }


def _print_text(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("=" * 88)
    print("RUNTIME SPINE DISPATCH MODE REPORT")
    print("=" * 88)
    print()
    print(f"Orchestrator mode:              {summary['orchestrator_mode']}")
    print(f"Current process state:          {summary['orchestrator_current_process']}")
    print(f"Persistent daemon launch state: {summary['orchestrator_persistent_daemon']}")
    print(f"Daemon health self-report:      {summary['daemon_health_self_report']}")
    print(f"Live census state:             {summary['live_census_state']}")
    print(f"Live census proof-gap surfaces:{summary['live_census_proof_gap_surfaces']:>7}")
    print(f"Live source-stale surfaces:    {summary['live_census_source_stale_surfaces']:>7}")
    print(f"A2A spine-native adapters:      {summary['a2a_spine_native']}")
    print(f"A2A legacy-quarantined paths:   {summary['a2a_legacy_quarantined']}")
    print(f"A2A unknown paths:              {summary['a2a_unknown']}")
    print(f"AgentRunner legacy direct paths:{summary['agent_runner_legacy_direct']:>7}")
    print(f"AgentRunner spine-wrapped paths:{summary['agent_runner_spine_wrapped']:>7}")
    print(f"AgentRunner manual live scripts:{summary['agent_runner_manual_scripts']:>7}")
    print(f"Manual live spine-wrapped:      {summary['agent_runner_manual_spine_wrapped']:>7}")
    print(
        "Production direct-runner clear: "
        f"{'yes' if summary['production_direct_runner_clear'] else 'no'}"
    )
    print(
        "Manual direct-runner clear:     "
        f"{'yes' if summary['manual_direct_runner_clear'] else 'no'}"
    )
    print(f"65->70 score gate:              {'PASS' if summary['score_gate_65_to_70'] else 'FAIL'}")
    print()
    print(
        f"{'Surface':<34} {'Mode':<30} {'State':<38} "
        f"{'Risk':<7} {'File:Line'}"
    )
    print("-" * 140)
    for entry in report["entries"]:
        line = entry["line"]
        location = entry["file"] if line is None else f"{entry['file']}:{line}"
        print(
            f"{entry['surface']:<34} {entry['mode']:<30} "
            f"{entry['current_state']:<38} {entry['risk']:<7} {location}"
        )
    live_census = report.get("live_census") or {}
    proof_gap_surfaces = live_census.get("proof_gap_surfaces") or []
    if proof_gap_surfaces:
        print()
        print("Live census proof gaps:")
        for surface in proof_gap_surfaces:
            gaps = ",".join(surface.get("proof_gaps") or [])
            pids = ",".join(surface.get("pids") or []) or "none"
            process_source = surface.get("process_source_state")
            source_state = (
                process_source.get("state", "unknown")
                if isinstance(process_source, dict)
                else "unknown"
            )
            print(
                f"  {surface.get('id', 'unknown')}: status={surface.get('status', '')}; "
                f"pids={pids}; source_state={source_state}; proof_gaps={gaps}"
            )
            receipt_head = surface.get("runtime_receipt_active_head")
            if isinstance(receipt_head, dict) and receipt_head:
                print(
                    "    runtime_receipt_active_head: "
                    f"{_format_runtime_receipt_head(receipt_head)}"
                )
            receipt_coverage = surface.get("runtime_receipt_coverage")
            if isinstance(receipt_coverage, dict) and receipt_coverage:
                print(
                    "    runtime_receipt_coverage: "
                    f"{_format_runtime_receipt_coverage(receipt_coverage)}"
                )
            ds_goal_contract = surface.get("ds_goal_wrapper_contract")
            if isinstance(ds_goal_contract, dict) and ds_goal_contract:
                print(
                    "    ds_goal_wrapper: "
                    f"{_format_ds_goal_wrapper_contract(ds_goal_contract)}"
                )
    print()
    if summary["score_gate_65_to_70"]:
        print(
            "PASS: dispatch modes are explicit. This proves current truth only; "
            "legacy-quarantined paths still need migration before production readiness."
        )
    else:
        print(
            "FAIL: at least one production dispatch mode is unknown/unowned, "
            "or a production direct AgentRunner path is unwrapped."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero unless the 65->70 explicit-mode gate passes",
    )
    args = parser.parse_args()

    report = build_report(probe_daemon_health=True)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text(report)

    if args.strict and not report["summary"]["score_gate_65_to_70"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
