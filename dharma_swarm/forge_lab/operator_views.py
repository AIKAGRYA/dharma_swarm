"""Truthful read-only views over the existing RSI Lab state artifacts."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.campaign_control import list_campaigns
from dharma_swarm.forge_lab.grader_runtime import swebench_runtime_readiness
from dharma_swarm.forge_lab.provider_selftest import validate_provider_receipt
from dharma_swarm.forge_lab.source_guard import execution_source_status
from dharma_swarm.forge_lab.state_io import (
    dharma_home,
    forge_state_root,
    provider_selftest_root,
    read_jsonl,
    safe_json,
)
from dharma_swarm.forge_lab.version import PACKAGE_VERSION, source_commit

DOCTOR_SCHEMA = "rsi_lab.doctor.v1"
RECONCILE_SCHEMA = "rsi_lab.reconciliation_report.v1"


def _parse_time(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _latest_provider_receipt() -> tuple[dict[str, Any] | None, Path | None]:
    root = provider_selftest_root()
    if not root.is_dir():
        return None, None
    for path in sorted(root.glob("*provider_selftest.json"), reverse=True):
        payload = safe_json(path)
        if payload is not None:
            return payload, path
    return None, None


def provider_readiness(*, ttl_seconds: int = 3600) -> dict[str, Any]:
    payload, path = _latest_provider_receipt()
    validation_failures = (
        validate_provider_receipt(payload, path=path)
        if payload is not None and path is not None
        else []
    )
    policy = (payload or {}).get("policy")
    policy = policy if isinstance(policy, dict) else {}
    source = policy.get("source") if isinstance(policy.get("source"), dict) else {}
    source_matches = bool(
        source.get("commit") == source_commit()
        and source.get("package_version") == PACKAGE_VERSION
        and source.get("tree_state") == "clean"
    )
    checked = _parse_time((payload or {}).get("checked_at"))
    age: float | None = None
    if checked is not None:
        age = (datetime.now(timezone.utc) - checked).total_seconds()
    routes = int((payload or {}).get("independent_route_count") or 0)
    live = bool((payload or {}).get("live"))
    callable_count = int((payload or {}).get("callable_count") or 0)
    fresh = age is not None and 0 <= age <= ttl_seconds
    ready = bool(
        payload
        and not validation_failures
        and source_matches
        and payload.get("ok")
        and live
        and callable_count > 0
        and routes >= 2
        and fresh
    )
    reasons: list[str] = []
    if payload is None:
        reasons.append("live_provider_receipt_missing")
    else:
        reasons.extend(f"provider_receipt_{reason}" for reason in validation_failures)
        if not source_matches:
            reasons.append("provider_receipt_source_not_current_clean_release")
        if not live:
            reasons.append("latest_provider_receipt_not_live")
        if callable_count == 0:
            reasons.append("zero_callable_routes")
        if routes < 2:
            reasons.append(f"independent_routes:{routes}/2")
        if not fresh:
            reasons.append("provider_receipt_stale_or_unparseable")
        if not payload.get("ok"):
            reasons.append("provider_selftest_failed")
    return {
        "ready": ready,
        "receipt": str(path) if path else None,
        "live": live,
        "callable_count": callable_count,
        "independent_route_count": routes,
        "age_seconds": round(age, 3) if age is not None else None,
        "ttl_seconds": ttl_seconds,
        "reasons": reasons,
        "receipt_validation_failures": validation_failures,
    }


def _read_crontab_markers() -> dict[str, Any]:
    override = os.environ.get("RSI_LAB_CRONTAB_TEXT")
    if override is not None:
        text, available = override, True
    else:
        try:
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
                env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            )
            text, available = result.stdout or "", result.returncode in {0, 1}
        except (OSError, subprocess.SubprocessError):
            text, available = "", False
    active = [
        line
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return {
        "available": available,
        "legacy_key_refresh_entries": sum("rsi-keys-refresh" in line for line in active),
        "current_main_state_entries": sum("current-main/state/rsi_runs" in line for line in active),
        "versioned_refresh_entries": sum(
            "rsi-provider-refresh" in line
            and "rsi-provider-refresh-install" not in line
            for line in active
        ),
    }


def _probe_exists(path: Path, uninspectable: list[str]) -> bool:
    """Fail-closed existence probe for host paths the runner may not read.

    On a non-root Linux host ``Path.exists()`` under /root raises
    PermissionError (pathlib only suppresses OSError from 3.14); a read-only
    doctor view must record that as evidence, never crash.
    """

    try:
        return path.exists()
    except OSError as exc:
        uninspectable.append(f"legacy_control_path_uninspectable:{path}({type(exc).__name__})")
        return False


def legacy_control_status() -> dict[str, Any]:
    base = Path(os.environ.get("RSI_LAB_ROOT", "/root/rsi-lab"))
    legacy_bin = Path(os.environ.get("RSI_LAB_LEGACY_BIN", base / "bin"))
    cron = _read_crontab_markers()
    legacy_script = legacy_bin / "rsi-keys-refresh"
    uninspectable: list[str] = []
    split_paths = [
        base / "current-main" / "state" / "rsi_runs",
        base / "current-main" / "state" / ".dharma" / "keys_status.json",
    ]
    legacy_receipt_paths = [
        base / "current-main" / "state" / ".dharma" / "keys_status.json",
        base / "state" / ".dharma" / "keys_status.json",
    ]
    alias_projection_paths: list[str] = []
    present_receipts: list[str] = []
    for path in legacy_receipt_paths:
        payload = safe_json(path)
        if payload is None:
            continue
        present_receipts.append(str(path))
        rows = payload.get("rows")
        if not isinstance(rows, list):
            continue
        by_name = {
            str(row.get("name") or "").strip().lower(): row
            for row in rows
            if isinstance(row, dict)
        }
        kimi = by_name.get("kimi")
        moonshot = by_name.get("moonshot")
        if kimi and moonshot:
            kimi_signature = (kimi.get("glyph"), kimi.get("status"))
            moonshot_signature = (moonshot.get("glyph"), moonshot.get("status"))
            if kimi_signature == moonshot_signature:
                alias_projection_paths.append(str(path))

    retirement_hazards: list[str] = []
    legacy_script_present = _probe_exists(legacy_script, uninspectable)
    if legacy_script_present:
        retirement_hazards.append("legacy_rsi_keys_refresh_present")
    if cron["legacy_key_refresh_entries"]:
        retirement_hazards.append("legacy_rsi_keys_refresh_cron_active")
    if cron["current_main_state_entries"]:
        retirement_hazards.append("legacy_cron_logs_to_current_main_state")
    present_split = [
        str(path) for path in split_paths if _probe_exists(path, uninspectable)
    ]
    if present_split:
        retirement_hazards.append("legacy_provider_state_split_present")
    if present_receipts:
        retirement_hazards.append("legacy_keys_status_receipt_present")
    if alias_projection_paths:
        retirement_hazards.append("kimi_moonshot_same_probe_projection_detected")

    automation_hazards: list[str] = []
    if not cron["available"]:
        automation_hazards.append("provider_refresh_crontab_unreadable")
    elif cron["versioned_refresh_entries"] != 1:
        automation_hazards.append(
            f"versioned_provider_refresh_entries:{cron['versioned_refresh_entries']}/1"
        )
    hazards = uninspectable + retirement_hazards + automation_hazards
    return {
        "ready": not hazards,
        "legacy_script_present": legacy_script_present,
        "cron": cron,
        "state_split_paths_present": present_split,
        "legacy_receipt_paths_present": present_receipts,
        "same_probe_projection_paths": alias_projection_paths,
        "hazards": hazards,
        "retirement_required": bool(retirement_hazards),
        "replacement": "rsi-provider-refresh",
        "replacement_installer": "rsi-provider-refresh-install",
    }


def state_anchor_status() -> dict[str, Any]:
    home = dharma_home()
    state_text = os.environ.get("RSI_LAB_STATE", "").strip()
    expected = (
        (Path(state_text).expanduser() / ".dharma").resolve(strict=False)
        if state_text
        else home
    )
    reasons: list[str] = []
    if home != expected:
        reasons.append("DHARMA_HOME_not_anchored_under_RSI_LAB_STATE")
    if not state_text:
        reasons.append("RSI_LAB_STATE_not_exported")
    return {
        "ready": not reasons,
        "dharma_home": str(home),
        "rsi_lab_state": state_text or None,
        "expected_dharma_home": str(expected),
        "reasons": reasons,
    }


def grader_readiness() -> dict[str, Any]:
    mode = os.environ.get("RSI_LAB_GRADER_MODE", "").strip()
    docker = shutil.which("docker")
    daemon_reachable = False
    daemon_error: str | None = None
    if mode == "official-swebench-docker" and docker is not None:
        docker_env = {
            key: value
            for key in ("PATH", "HOME", "DOCKER_HOST", "DOCKER_CONTEXT")
            if (value := os.environ.get(key))
        }
        try:
            result = subprocess.run(
                [docker, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
                env=docker_env,
            )
            daemon_reachable = result.returncode == 0 and bool(result.stdout.strip())
            if not daemon_reachable:
                daemon_error = "docker_info_failed"
        except (OSError, subprocess.SubprocessError):
            daemon_error = "docker_info_unavailable"
    runtime = swebench_runtime_readiness()
    sdk_reachable, sdk_error = (
        _docker_sdk_status()
        if mode == "official-swebench-docker"
        else (False, None)
    )
    ready = (
        mode == "official-swebench-docker"
        and docker is not None
        and daemon_reachable
        and sdk_reachable
        and runtime["ready"]
    )
    reasons: list[str] = []
    if mode != "official-swebench-docker":
        reasons.append("RSI_LAB_GRADER_MODE_not_official_swebench_docker")
    if docker is None:
        reasons.append("docker_unavailable")
    elif mode == "official-swebench-docker" and not daemon_reachable:
        reasons.append(daemon_error or "docker_daemon_unreachable")
    if mode == "official-swebench-docker" and not sdk_reachable:
        reasons.append(sdk_error or "docker_sdk_daemon_unreachable")
    reasons.extend(runtime["reasons"])
    # PR-suite host pytest is intentionally not accepted as isolated grading.
    return {
        "ready": ready,
        "mode": mode or None,
        "docker": docker,
        "docker_daemon_reachable": daemon_reachable,
        "docker_sdk_daemon_reachable": sdk_reachable,
        "docker_sdk_error": sdk_error,
        "swebench_runtime": runtime,
        "candidate_network_disabled": True,
        "host_environment_forwarded": False,
        "pr_suite_host_grading_allowed": False,
        "reasons": reasons,
    }


def _docker_sdk_status() -> tuple[bool, str | None]:
    """Ping through the same docker.from_env path used by the grader."""

    client: Any | None = None
    try:
        import docker as docker_sdk

        client = docker_sdk.from_env(timeout=10)
        return bool(client.ping()), None
    except Exception as exc:
        return False, f"docker_sdk_{type(exc).__name__}"
    finally:
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                print(
                    f"[readiness] docker client close failed: {type(exc).__name__}",
                    file=sys.stderr,
                )


def taskbed_readiness() -> dict[str, Any]:
    """Read-only proof that the anchored ledger can supply one EXPLORE task."""

    from dharma_swarm.forge_lab.taskpack_ops import taskpack_status

    canonical = taskpack_status()
    reasons = list(canonical.get("reasons") or [])
    if reasons == ["taskbed_missing"]:
        reasons = ["anchored_taskbed_missing_or_unsafe"]
    return {
        "ready": bool(canonical.get("ready")),
        "path": canonical.get("taskbed_db"),
        "eligible_explore_tasks": canonical.get("eligible_explore_task_count", 0),
        "next_explore_task_id": canonical.get("next_explore_task_id"),
        "required": 1,
        "read_only": True,
        "reasons": reasons,
        "canonical_status": canonical,
    }


def doctor() -> dict[str, Any]:
    checks = {
        "source": execution_source_status(),
        "state_anchor": state_anchor_status(),
        "providers": provider_readiness(),
        "grader": grader_readiness(),
        "taskbed": taskbed_readiness(),
        "legacy_controls": legacy_control_status(),
    }
    return {
        "schema": DOCTOR_SCHEMA,
        "ok": all(bool(check.get("ready")) for check in checks.values()),
        "checks": checks,
        "campaigns": list_campaigns(),
    }


def reconcile() -> dict[str, Any]:
    campaigns = list_campaigns()["campaigns"]
    findings: list[dict[str, Any]] = []
    active = safe_json(forge_state_root() / "active_campaign.json")
    if active and str(active.get("state")) not in {"COMPLETED", "FAILED", "PAUSED"}:
        campaign_id = str(active.get("campaign_id") or "")
        row = next((item for item in campaigns if item["campaign_id"] == campaign_id), None)
        if row is None:
            findings.append({"code": "ACTIVE_CAMPAIGN_MISSING_RUN", "campaign": campaign_id})
        elif row.get("state") != active.get("state"):
            findings.append(
                {
                    "code": "ACTIVE_CAMPAIGN_STATE_DRIFT",
                    "campaign": campaign_id,
                    "active_state": active.get("state"),
                    "event_state": row.get("state"),
                }
            )
    for row in campaigns:
        if row["state"] in {"COMPLETED", "FAILED"} and row["attempt_count"] and row["event_count"] == 0:
            findings.append({"code": "TERMINAL_CAMPAIGN_WITHOUT_EVENTS", "campaign": row["campaign_id"]})
    legacy = legacy_control_status()
    for hazard in legacy["hazards"]:
        findings.append({"code": "LEGACY_CONTROL_DRIFT", "detail": hazard})
    return {
        "schema": RECONCILE_SCHEMA,
        "ok": not findings,
        "read_only": True,
        "findings": findings,
        "campaign_count": len(campaigns),
    }


def list_workers() -> dict[str, Any]:
    root = forge_state_root() / "workers"
    rows = [payload for path in sorted(root.glob("*.json")) if (payload := safe_json(path))]
    return {"workers": rows, "count": len(rows), "read_only": True}


def list_alerts() -> dict[str, Any]:
    root = forge_state_root() / "alerts"
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = safe_json(path)
        if payload:
            rows.append(payload)
    for path in sorted(root.glob("*.jsonl")):
        rows.extend(read_jsonl(path))
    rows.sort(key=lambda row: str(row.get("at") or row.get("created_at") or ""), reverse=True)
    return {"alerts": rows, "count": len(rows), "read_only": True}


def inspect_archive(candidate: str | None = None) -> dict[str, Any]:
    root = Path(
        os.environ.get(
            "RSILAB_EVOLUTION_ARCHIVE_ROOT",
            dharma_home() / "evolution_archive" / "agent_evolution",
        )
    )
    if candidate and not candidate.startswith("cand_"):
        raise ValueError("candidate must use the cand_ content-addressed identifier")
    experiments: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    if root.is_dir():
        for directory in sorted(root.iterdir(), key=lambda path: path.name, reverse=True):
            if not directory.is_dir():
                continue
            manifest = safe_json(directory / "run_manifest.json") or {}
            closeout = safe_json(directory / "closeout.json") or {}
            experiments.append(
                {
                    "experiment_id": closeout.get("experiment_id")
                    or manifest.get("experiment_id")
                    or directory.name,
                    "closeout_state": closeout.get("closeout_state"),
                    "path": str(directory),
                }
            )
            if candidate:
                for row in read_jsonl(directory / "archive.jsonl"):
                    if row.get("candidate_id") == candidate or row.get("id") == candidate:
                        matches.append({"experiment": directory.name, "candidate": row})
    return {
        "archive_root": str(root),
        "candidate": candidate,
        "matches": matches,
        "experiments": experiments[:50] if candidate is None else [],
        "count": len(matches) if candidate else len(experiments),
        "read_only": True,
    }


__all__ = [
    "doctor",
    "grader_readiness",
    "inspect_archive",
    "legacy_control_status",
    "list_alerts",
    "list_workers",
    "provider_readiness",
    "reconcile",
    "state_anchor_status",
    "swebench_runtime_readiness",
    "taskbed_readiness",
]
