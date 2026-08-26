"""Truthful Foundry health assessment for cron, systemd, and operators."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from dharma_swarm.foundry import killswitch
from dharma_swarm.foundry.daemon import FoundryStateError, spend_ledger_summary
from dharma_swarm.foundry.live import verify_live_chain
from dharma_swarm.foundry.receipts import audit_receipts

GitProbe = Callable[[Path], tuple[str, bool, str, str]]
ProcessProbe = Callable[[int], tuple[bool, str]]
RuntimeProbe = Callable[[str], dict[str, bool]]

EXIT_OK = 0
EXIT_DEGRADED = 1
EXIT_UNHEALTHY = 2
EXIT_TERMINAL = 3
CANONICAL_REMOTE = "https://github.com/AIKAGRYA/dharma_swarm.git"
_FULL_SHA = re.compile(r"[0-9a-f]{40}")


def _parse_time(raw: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _default_git_probe(repo_root: Path) -> tuple[str, bool, str, str]:
    try:
        sha_proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        dirty_proc = subprocess.run(
            [
                "git", "-C", str(repo_root), "status", "--porcelain",
                "--untracked-files=normal",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        remote_proc = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return "unknown", True, "", type(exc).__name__
    return (
        sha_proc.stdout.strip() or "unknown",
        bool(dirty_proc.stdout.strip()),
        remote_proc.stdout.strip(),
        "",
    )


def _default_process_probe(pid: int) -> tuple[bool, str]:
    if pid <= 1:
        return False, ""
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False, ""
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return True, "unknown"
    return True, proc.stdout.strip()


def _default_runtime_probe(mode: str) -> dict[str, bool]:
    checks = {
        "python_3_11_plus": sys.version_info >= (3, 11),
        "git": shutil.which("git") is not None,
        "patch": shutil.which("patch") is not None,
    }
    if mode == "campaign":
        docker = shutil.which("docker")
        checks["docker_cli"] = docker is not None
        if docker:
            try:
                probe = subprocess.run(
                    [docker, "info", "--format", "{{.ServerVersion}}"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                checks["docker_daemon"] = probe.returncode == 0
                image_probe = subprocess.run(
                    [docker, "image", "inspect", "foundry/openevolve-cpu:1"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                checks["oracle_image"] = image_probe.returncode == 0
            except (OSError, subprocess.SubprocessError):
                checks["docker_daemon"] = False
                checks["oracle_image"] = False
        else:
            checks["docker_daemon"] = False
            checks["oracle_image"] = False
    return checks


def _latest_receipt_time(state_root: Path) -> datetime | None:
    newest: datetime | None = None
    paths = list((state_root / "receipts").glob("*.json"))
    paths += list((state_root / "live_eval").glob("*.json"))
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        parsed = _parse_time(str(data.get("created_at") or data.get("ran_at") or ""))
        if parsed is not None and (newest is None or parsed > newest):
            newest = parsed
    return newest


def assess_status(
    *,
    repo_root: Path,
    state_root: Path,
    expected_sha: str = "",
    max_heartbeat_age_seconds: float = 900.0,
    max_receipt_age_seconds: float = 86_400.0,
    now: datetime | None = None,
    git_probe: GitProbe = _default_git_probe,
    process_probe: ProcessProbe = _default_process_probe,
    runtime_probe: RuntimeProbe = _default_runtime_probe,
) -> tuple[dict, int]:
    """Return a machine-readable verdict; no score or PID alone implies health."""
    repo_root = Path(repo_root).resolve()
    state_root = Path(state_root).resolve()
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    problems: list[str] = []
    warnings: list[str] = []

    terminal = killswitch.read_terminal_kill(state_root)
    quarantine_files = [
        path for path in (state_root / "QUARANTINE.json", state_root / "QUARANTINE")
        if path.exists()
    ]

    service_path = state_root / "service_state.json"
    try:
        service = json.loads(service_path.read_text(encoding="utf-8"))
        if not isinstance(service, dict):
            raise TypeError("service state is not an object")
    except FileNotFoundError:
        service = {}
        problems.append("service_state_missing")
    except (OSError, ValueError, TypeError) as exc:
        service = {}
        problems.append(f"service_state_invalid:{type(exc).__name__}")

    mode = str(service.get("mode", "unknown"))
    runtime = runtime_probe(mode)
    missing_runtime = sorted(name for name, present in runtime.items() if not present)
    if missing_runtime:
        problems.append("runtime_dependencies_missing:" + ",".join(missing_runtime))

    checkout_sha, checkout_dirty, remote_url, git_error = git_probe(repo_root)
    recorded_sha = str(service.get("code_sha", ""))
    if git_error:
        problems.append(f"git_probe_failed:{git_error}")
    if not recorded_sha or recorded_sha == "unknown" or recorded_sha != checkout_sha:
        problems.append("code_sha_mismatch")
    if not _FULL_SHA.fullmatch(expected_sha):
        problems.append("expected_sha_missing_or_invalid")
    elif checkout_sha != expected_sha or recorded_sha != expected_sha:
        problems.append("expected_sha_mismatch")
    if remote_url != CANONICAL_REMOTE:
        problems.append("canonical_remote_mismatch")
    if checkout_dirty:
        problems.append("checkout_dirty_unsealed_code")

    heartbeat = _parse_time(str(service.get("heartbeat_at", "")))
    heartbeat_age = (now - heartbeat).total_seconds() if heartbeat else None
    if heartbeat_age is None:
        problems.append("heartbeat_missing_or_invalid")
    elif heartbeat_age < -60:
        problems.append("heartbeat_from_future")
    elif heartbeat_age > max_heartbeat_age_seconds:
        problems.append("heartbeat_stale")

    try:
        pid = int(service.get("pid", 0) or 0)
    except (TypeError, ValueError):
        pid = 0
    pid_alive, command = process_probe(pid)
    expected_process = pid_alive and "foundry_daemon.py" in command
    service_status = str(service.get("status", "unknown"))
    live_statuses = {"running", "starting", "idle", "degraded_provider_outage"}
    if service_status in live_statuses and not expected_process:
        problems.append("pid_missing_or_reused")
    if service_status == "degraded_provider_outage":
        warnings.append("provider_outage_active")
    if service_status in {"stopped", "killed"}:
        warnings.append(f"service_{service_status}")

    receipt_audit = audit_receipts(state_root)
    if not receipt_audit.ok:
        problems.append("receipt_or_artifact_audit_failed")
    live_ok, live_detail = verify_live_chain(state_root)
    if not live_ok:
        problems.append("live_receipt_chain_failed")

    newest_receipt = _latest_receipt_time(state_root)
    receipt_age = (now - newest_receipt).total_seconds() if newest_receipt else None
    if receipt_age is None:
        warnings.append("no_receipt_evidence")
    elif receipt_age < -60:
        problems.append("receipt_from_future")
    elif receipt_age > max_receipt_age_seconds:
        warnings.append("receipt_evidence_stale")

    try:
        spend_ledger = spend_ledger_summary(state_root)
    except FoundryStateError as exc:
        spend_ledger = {"error": type(exc).__name__}
        problems.append("spend_ledger_invalid")
    else:
        unresolved = int(spend_ledger.get("unresolved_reservations", 0))
        if unresolved:
            warnings.append(f"spend_reservations_unresolved:{unresolved}")

    if terminal:
        verdict, exit_code = "killed", EXIT_TERMINAL
    elif quarantine_files:
        verdict, exit_code = "quarantined", EXIT_TERMINAL
    elif problems:
        verdict, exit_code = "unhealthy", EXIT_UNHEALTHY
    elif service_status == "stopped":
        verdict, exit_code = "stopped", EXIT_DEGRADED
    elif warnings:
        verdict, exit_code = "degraded", EXIT_DEGRADED
    else:
        verdict, exit_code = "healthy", EXIT_OK

    payload = {
        "schema_version": "foundry_status.v1",
        "verdict": verdict,
        "checked_at": now.isoformat(),
        "repo_root": str(repo_root),
        "state_root": str(state_root),
        "checkout_sha": checkout_sha,
        "expected_sha": expected_sha,
        "recorded_code_sha": recorded_sha,
        "canonical_remote": CANONICAL_REMOTE,
        "checkout_remote": remote_url,
        "checkout_clean": not checkout_dirty,
        "service": {
            "status": service_status,
            "mode": mode,
            "boot_id": service.get("boot_id", ""),
            "pid": pid,
            "pid_alive": pid_alive,
            "expected_process": expected_process,
            "heartbeat_age_seconds": heartbeat_age,
            "cycles_run": service.get("cycles_run", 0),
            "total_proposed": service.get("total_proposed", 0),
            "provider_failures": service.get("provider_failures", 0),
            "consecutive_provider_outages": service.get(
                "consecutive_provider_outages", 0
            ),
        },
        "terminal_kill": terminal,
        "quarantine": [str(path) for path in quarantine_files],
        "runtime_dependencies": runtime,
        "receipt_audit": receipt_audit.to_dict(),
        "live_receipt_chain": {"ok": live_ok, "detail": live_detail},
        "spend_ledger": spend_ledger,
        "latest_receipt_at": newest_receipt.isoformat() if newest_receipt else None,
        "receipt_age_seconds": receipt_age,
        "problems": problems,
        "warnings": warnings,
        "health_basis": (
            "exact clean code SHA + fresh heartbeat + expected live process + "
            "runtime dependencies + append-only receipt/artifact integrity"
            " + conservative crash-durable spend accounting"
        ),
    }
    return payload, exit_code
