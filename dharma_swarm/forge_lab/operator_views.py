"""Truthful read-only views over the existing RSI Lab state artifacts."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.campaign_control import list_campaigns
from dharma_swarm.forge_lab.provider_selftest import validate_provider_receipt
from dharma_swarm.forge_lab.source_guard import execution_source_status
from dharma_swarm.forge_lab.state_io import (
    content_digest,
    dharma_home,
    forge_state_root,
    provider_selftest_root,
    read_jsonl,
    safe_json,
    validate_safe_id,
)
from dharma_swarm.forge_lab.version import PACKAGE_VERSION, source_commit
from dharma_swarm.forge_lab.safety_control import halt_status
from dharma_swarm.forge_lab.unattended_budget import budget_status
from dharma_swarm.forge_lab.unattended_lease import lease_status
from dharma_swarm.forge_lab.unattended_receipts import UnattendedError

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
        observed_age = (datetime.now(timezone.utc) - checked).total_seconds()
        age = observed_age if observed_age >= 0 else None
    routes = int((payload or {}).get("independent_route_count") or 0)
    live = bool((payload or {}).get("live"))
    callable_count = int((payload or {}).get("callable_count") or 0)
    admission_count = int((payload or {}).get("admission_eligible_count") or 0)
    fresh = age is not None and age <= ttl_seconds
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
        elif admission_count == 0:
            reasons.append("zero_priced_budget_eligible_routes")
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
        "admission_eligible_count": admission_count,
        "independent_route_count": routes,
        "rows": list((payload or {}).get("rows") or []) if ready else [],
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


def legacy_control_status() -> dict[str, Any]:
    base = Path(os.environ.get("RSI_LAB_ROOT", "/root/rsi-lab"))
    legacy_bin = Path(os.environ.get("RSI_LAB_LEGACY_BIN", base / "bin"))
    cron = _read_crontab_markers()
    legacy_script = legacy_bin / "rsi-keys-refresh"
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
    if legacy_script.exists():
        retirement_hazards.append("legacy_rsi_keys_refresh_present")
    if cron["legacy_key_refresh_entries"]:
        retirement_hazards.append("legacy_rsi_keys_refresh_cron_active")
    if cron["current_main_state_entries"]:
        retirement_hazards.append("legacy_cron_logs_to_current_main_state")
    present_split = [str(path) for path in split_paths if path.exists()]
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
    hazards = retirement_hazards + automation_hazards
    return {
        "ready": not hazards,
        "legacy_script_present": legacy_script.exists(),
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
    ready = (
        mode == "official-swebench-docker"
        and docker is not None
        and daemon_reachable
    )
    reasons: list[str] = []
    if mode != "official-swebench-docker":
        reasons.append("RSI_LAB_GRADER_MODE_not_official_swebench_docker")
    if docker is None:
        reasons.append("docker_unavailable")
    elif mode == "official-swebench-docker" and not daemon_reachable:
        reasons.append(daemon_error or "docker_daemon_unreachable")
    # PR-suite host pytest is intentionally not accepted as isolated grading.
    return {
        "ready": ready,
        "mode": mode or None,
        "docker": docker,
        "docker_daemon_reachable": daemon_reachable,
        "candidate_network_disabled": True,
        "host_environment_forwarded": False,
        "pr_suite_host_grading_allowed": False,
        "reasons": reasons,
    }


def taskbed_readiness() -> dict[str, Any]:
    """Read-only proof that the anchored ledger can supply one EXPLORE task."""

    from dharma_swarm.forge_v1.forge_v2.pr_suite_grader import is_pr_suite_task_id

    path = dharma_home() / "forge_v1" / "taskbed.db"
    reasons: list[str] = []
    eligible_ids: list[str] = []
    eligible_bindings: dict[str, dict[str, Any]] = {}
    rejected: dict[str, int] = {}
    if path.is_symlink() or not path.is_file():
        reasons.append("anchored_taskbed_missing_or_unsafe")
    else:
        try:
            uri = f"{path.resolve().as_uri()}?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=2) as connection:
                rows = connection.execute(
                    """
                    SELECT task.task_id, task.task_json, task.provenance_json,
                           task.source, task.taskbed
                      FROM taskbed_tasks task
                     WHERE task.active=1
                       AND NOT EXISTS (
                         SELECT 1 FROM taskbed_allocations prior
                          WHERE prior.task_id=task.task_id
                            AND prior.split='confirm'
                       )
                     ORDER BY task.created_at ASC,
                              task.first_seen_at ASC,
                              task.task_id ASC
                    """
                ).fetchall()
                for row in rows:
                    task_id = str(row[0])
                    if is_pr_suite_task_id(task_id):
                        rejected["pr_suite_not_official_swebench"] = rejected.get(
                            "pr_suite_not_official_swebench", 0
                        ) + 1
                        continue
                    try:
                        task = json.loads(str(row[1]))
                        provenance = json.loads(str(row[2]))
                    except (TypeError, json.JSONDecodeError):
                        rejected["task_or_provenance_malformed"] = rejected.get(
                            "task_or_provenance_malformed", 0
                        ) + 1
                        continue
                    task_digest = str(task.get("task_digest") or "")
                    unsigned_task = {
                        key: value
                        for key, value in task.items()
                        if key not in {"task_digest", "provenance", "sealed_provenance"}
                    }
                    manifest_shaped_task = {
                        key: value
                        for key, value in task.items()
                        if key not in {"provenance", "sealed_provenance"}
                    }
                    request_id = str(provenance.get("import_request_id") or "")
                    try:
                        request_id = validate_safe_id(request_id, field="import_request_id")
                    except ValueError:
                        request_id = ""
                    receipt_path = (
                        dharma_home()
                        / "forge_lab"
                        / "taskpacks"
                        / "import_receipts"
                        / f"{request_id}.json"
                    )
                    receipt = safe_json(receipt_path) if request_id else None
                    receipt_unsigned = (
                        {key: value for key, value in receipt.items() if key != "receipt_digest"}
                        if receipt
                        else {}
                    )
                    taskpack_binding = False
                    try:
                        from dharma_swarm.forge_lab.taskpack import (
                            TaskpackError,
                            _inspect_local_image,
                            _revalidate_official_content,
                            load_taskpack,
                        )

                        taskpack_digest = str(provenance.get("taskpack_digest") or "")
                        manifest_path = (
                            dharma_home()
                            / "forge_lab"
                            / "taskpacks"
                            / taskpack_digest.removeprefix("sha256:")
                            / "manifest.json"
                        )
                        manifest = load_taskpack(manifest_path)
                        manifest_tasks = {
                            str(item.get("instance_id") or ""): item
                            for item in manifest["content"]["tasks"]
                        }
                        manifest_task = manifest_tasks.get(task_id)
                        official_revalidation_digest = _revalidate_official_content(
                            manifest["content"]
                        )
                        import_plan = {
                            "schema": "rsi_lab.taskpack_import_plan.v1",
                            "taskpack_digest": taskpack_digest,
                            "manifest_path": str(manifest_path),
                            "taskbed_db": str(path),
                            "task_ids": [
                                item["instance_id"]
                                for item in manifest["content"]["tasks"]
                            ],
                            "registration_api": (
                                "dharma_swarm.forge_v1.forge_v2.taskbed_ledger.register_task"
                            ),
                            "direct_sqlite_edits": False,
                            "official_revalidation_digest": official_revalidation_digest,
                        }
                        registration = next(
                            (
                                item
                                for item in (receipt or {}).get("registered", [])
                                if isinstance(item, dict) and item.get("task_id") == task_id
                            ),
                            None,
                        )
                        current_image = _inspect_local_image(str(task.get("image_key") or ""))
                        taskpack_binding = bool(
                            manifest["taskpack_digest"] == taskpack_digest
                            and manifest["manifest_path"] == str(manifest_path)
                            and provenance.get("manifest_path") == str(manifest_path)
                            and manifest["content"].get("official_eligible") is True
                            and manifest_task == manifest_shaped_task
                            and receipt
                            and receipt.get("manifest_path") == str(manifest_path)
                            and receipt.get("receipt_path") == str(receipt_path)
                            and receipt.get("request_id") == request_id
                            and receipt.get("plan_digest") == content_digest(import_plan)
                            and receipt.get("taskbed_db") == str(path)
                            and receipt.get("registration_api")
                            == import_plan["registration_api"]
                            and receipt.get("direct_sqlite_edits") is False
                            and receipt.get("official_revalidation_digest")
                            == official_revalidation_digest
                            and registration
                            and registration.get("task_digest") == task_digest
                            and registration.get("stored_task_digest") == content_digest(task)
                            and current_image.get("local_image_id") == task.get("local_image_id")
                            and current_image.get("local_image_repo_digests")
                            == task.get("local_image_repo_digests")
                        )
                    except (OSError, TaskpackError, TypeError, ValueError):
                        taskpack_binding = False
                    official = bool(
                        row[3] == "official_swebench_verified_taskpack"
                        and row[4] == "official_swebench_verified_shadow"
                        and task.get("source_kind") == "official_swebench_verified"
                        and task.get("official_harness_required") is True
                        and task.get("candidate_network_disabled") is True
                        and task.get("official_eligible") is True
                        and str(task.get("image_key") or "").startswith("swebench/sweb.eval.")
                        and task_digest == content_digest(unsigned_task)
                        and provenance.get("task_digest") == task_digest
                        and task.get("provenance") == provenance
                        and task.get("sealed_provenance") == provenance
                        and taskpack_binding
                        and receipt
                        and receipt.get("schema") == "rsi_lab.taskpack_import_receipt.v1"
                        and receipt.get("taskpack_digest") == provenance.get("taskpack_digest")
                        and receipt.get("receipt_digest") == content_digest(receipt_unsigned)
                    )
                    if official:
                        eligible_ids.append(task_id)
                        eligible_bindings[task_id] = {
                            "task_id": task_id,
                            "task_digest": task_digest,
                            "taskpack_digest": provenance["taskpack_digest"],
                            "official_source_row_digest": task[
                                "official_source_row_digest"
                            ],
                            "image_key": task["image_key"],
                            "local_image_id": task["local_image_id"],
                            "local_image_repo_digests": task[
                                "local_image_repo_digests"
                            ],
                            "base_commit": task["base_commit"],
                        }
                    else:
                        rejected["official_taskpack_receipt_or_binding_invalid"] = rejected.get(
                            "official_taskpack_receipt_or_binding_invalid", 0
                        ) + 1
        except (OSError, sqlite3.Error, TypeError, ValueError):
            reasons.append("anchored_taskbed_unreadable_or_schema_invalid")
    if not reasons and not eligible_ids:
        reasons.append("zero_eligible_isolated_swebench_tasks")
    return {
        "ready": not reasons,
        "path": str(path),
        "eligible_explore_tasks": len(eligible_ids),
        "next_explore_task_id": eligible_ids[0] if eligible_ids else None,
        "next_explore_task_binding": (
            eligible_bindings[eligible_ids[0]] if eligible_ids else None
        ),
        "required": 1,
        "read_only": True,
        "eligibility_policy": "official_swebench_taskpack_receipt.v1",
        "rejected_counts": rejected,
        "reasons": reasons,
    }


def unattended_control_readiness() -> dict[str, Any]:
    """Project HALT, fenced ownership, accounting, progress, and disk truth."""

    root = forge_state_root()
    control = root / "unattended_explore"
    reasons: list[str] = []
    try:
        safety = halt_status(root)
    except UnattendedError as exc:
        safety = {"active": True, "error": exc.code}
        reasons.append(f"halt_state_invalid:{exc.code}")
    if safety.get("active"):
        reasons.append("durable_HALT_active")
    try:
        lease = lease_status(control)
    except UnattendedError as exc:
        lease = {"ready": False, "active": False, "error": exc.code}
        reasons.append(f"lease_invalid:{exc.code}")
    if not lease.get("ready"):
        reasons.append("lease_expired_or_invalid")
    try:
        budget = budget_status(control / "budget_ledger.jsonl")
    except UnattendedError as exc:
        budget = {"ready": False, "open_run_ids": [], "error": exc.code}
        reasons.append(f"budget_invalid:{exc.code}")
    open_runs = set(budget.get("open_run_ids") or [])
    active_run = str(((lease.get("lease") or {}).get("run_id") or ""))
    if open_runs and open_runs != ({active_run} if active_run else set()):
        reasons.append("orphaned_budget_reservation")
    state = Path(os.environ.get("RSI_LAB_STATE", str(dharma_home().parent))).expanduser()
    try:
        usage = shutil.disk_usage(state)
        fraction = usage.free / usage.total if usage.total else 0.0
        disk = {
            "ready": usage.free >= 2 * 1024**3 and fraction >= 0.05,
            "free_bytes": usage.free,
            "free_fraction": round(fraction, 6),
        }
    except OSError as exc:
        disk = {"ready": False, "error": f"{type(exc).__name__}:{exc}"[:500]}
    if not disk["ready"]:
        reasons.append("state_disk_floor_not_met")
    return {
        "ready": not reasons,
        "halt": safety,
        "lease": lease,
        "budget": budget,
        "disk": disk,
        "reasons": reasons,
    }


def doctor() -> dict[str, Any]:
    checks = {
        "source": execution_source_status(),
        "state_anchor": state_anchor_status(),
        "providers": provider_readiness(),
        "grader": grader_readiness(),
        "taskbed": taskbed_readiness(),
        "legacy_controls": legacy_control_status(),
        "unattended_control": unattended_control_readiness(),
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
    control = unattended_control_readiness()
    for reason in control["reasons"]:
        findings.append({"code": "UNATTENDED_CONTROL_DRIFT", "detail": reason})
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
    "taskbed_readiness",
    "unattended_control_readiness",
]
