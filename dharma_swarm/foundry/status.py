"""Truthful Foundry health assessment for cron, systemd, and operators."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from dharma_swarm.foundry import killswitch
from dharma_swarm.foundry.daemon import FoundryStateError, spend_ledger_summary
from dharma_swarm.foundry.evaluator import canonical_digest
from dharma_swarm.foundry.live import verify_live_chain
from dharma_swarm.foundry.receipts import audit_receipts

GitProbe = Callable[[Path], tuple[str, bool, str, str]]
ProcessProbe = Callable[[int], tuple[bool, str]]
RuntimeProbe = Callable[[str], dict[str, bool]]
DiskProbe = Callable[[Path], dict[str, int | float | bool]]

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
                    [
                        docker,
                        "image",
                        "inspect",
                        "foundry/openevolve-cpu@sha256:"
                        "13526567bc4d878d367ae2ad1d1f18a686b3cdad2be6c09942c92dd34db5ca53",
                    ],
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


def _provider_tariff_health(state_root: Path, now: datetime) -> dict[str, object]:
    """Report the nearest attested tariff expiry from durable cycle evidence."""
    projection = state_root / "provider_status.json"
    try:
        payload = json.loads(projection.read_text(encoding="utf-8"))
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != "foundry_provider_status.v1"
            or payload.get("digest") != canonical_digest({
                key: value for key, value in payload.items() if key != "digest"
            })
        ):
            raise ValueError("provider status projection seal is invalid")
        routes = payload.get("provider_route_provenance", {})
    except FileNotFoundError:
        return {
            "evidence": "none",
            "active_routes": 0,
            "next_expiry": None,
            "seconds_until_next_expiry": None,
        }
    except (OSError, ValueError, TypeError):
        return {"evidence": "invalid", "active_routes": 0, "next_expiry": None}
    expiries: list[datetime] = []
    invalid = payload.get("usage_verified") is not True
    if not isinstance(routes, dict):
        invalid = True
        routes = {}
    for route in routes.values():
        if not isinstance(route, dict):
            invalid = True
            continue
        if route.get("tariff_usd_per_mtok_upper_bound") is None:
            continue
        checked = _parse_time(str(route.get("tariff_checked_at", "")))
        expiry = _parse_time(str(route.get("tariff_valid_until", "")))
        if checked is None or expiry is None or not checked < expiry or checked > now + timedelta(minutes=5):
            invalid = True
            continue
        expiries.append(expiry)
    next_expiry = min(expiries) if expiries else None
    seconds = (next_expiry - now).total_seconds() if next_expiry else None
    return {
        "evidence": str(projection.relative_to(state_root)),
        "active_routes": len(expiries),
        "next_expiry": next_expiry.isoformat() if next_expiry else None,
        "seconds_until_next_expiry": seconds,
        "invalid": invalid,
    }


def _default_disk_probe(
    state_root: Path,
    *,
    max_entries: int = 100_000,
    max_scan_seconds: float = 2.0,
) -> dict[str, int | float | bool]:
    """Measure state storage without an unbounded recursive walk.

    Symlinks are never followed.  Crossing either bound is evidence that the
    measurement is incomplete, which the caller treats as unhealthy rather
    than silently understating state size.
    """
    usage = shutil.disk_usage(state_root)
    state_bytes = 0
    scanned_entries = 0
    complete = True
    started = time.monotonic()
    stack = [Path(state_root)]
    while stack:
        if scanned_entries >= max_entries or (
            time.monotonic() - started >= max_scan_seconds
        ):
            complete = False
            break
        directory = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    scanned_entries += 1
                    if scanned_entries > max_entries or (
                        time.monotonic() - started >= max_scan_seconds
                    ):
                        complete = False
                        break
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            state_bytes += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        complete = False
                if not complete:
                    break
        except OSError:
            complete = False
    return {
        "total_bytes": usage.total,
        "free_bytes": usage.free,
        "state_bytes": state_bytes,
        "scanned_entries": scanned_entries,
        "scan_elapsed_seconds": round(time.monotonic() - started, 6),
        "scan_complete": complete,
    }


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
    disk_probe: DiskProbe = _default_disk_probe,
    min_free_disk_bytes: int = 2 * 1024 * 1024 * 1024,
    max_state_bytes: int = 20 * 1024 * 1024 * 1024,
) -> tuple[dict, int]:
    """Return a machine-readable verdict; no score or PID alone implies health."""
    repo_root = Path(repo_root).resolve()
    state_root = Path(state_root).resolve()
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    problems: list[str] = []
    warnings: list[str] = []

    terminal = killswitch.read_terminal_kill(state_root)
    halt = killswitch.read_halt(state_root)
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
    live_statuses = {
        "running", "starting", "idle", "sleeping", "provider_cooldown",
        "degraded_provider_outage",
    }
    if service_status in live_statuses and not expected_process:
        problems.append("pid_missing_or_reused")
    if service_status == "degraded_provider_outage":
        warnings.append("provider_outage_active")
    if service_status in {"stopped", "killed"}:
        warnings.append(f"service_{service_status}")

    last_completed = _parse_time(str(service.get("last_completed_cycle_at", "")))
    progress_age = (now - last_completed).total_seconds() if last_completed else None
    if last_completed and progress_age is not None:
        if progress_age < -60:
            problems.append("progress_timestamp_from_future")
        elif service_status == "running" and progress_age > max_receipt_age_seconds:
            warnings.append("evolution_progress_stale")
    try:
        no_op_ratio = float(service.get("no_op_ratio", 0.0) or 0.0)
    except (TypeError, ValueError):
        no_op_ratio = 1.0
        problems.append("no_op_ratio_invalid")
    if not math.isfinite(no_op_ratio) or not 0.0 <= no_op_ratio <= 1.0:
        no_op_ratio = 1.0
        problems.append("no_op_ratio_invalid")
    if no_op_ratio > 0.90:
        warnings.append("no_op_ratio_high")
    try:
        restart_churn = int(service.get("restart_churn_24h", 0) or 0)
    except (TypeError, ValueError):
        restart_churn = 0
        problems.append("restart_churn_invalid")
    if restart_churn > 3:
        warnings.append("restart_churn_high")

    try:
        disk = disk_probe(state_root)
        free_disk = int(disk["free_bytes"])
        state_bytes = int(disk["state_bytes"])
    except (OSError, KeyError, TypeError, ValueError):
        disk = {}
        problems.append("disk_probe_failed")
    else:
        if disk.get("scan_complete", True) is not True:
            problems.append("disk_scan_incomplete")
        if free_disk < min_free_disk_bytes:
            problems.append("free_disk_below_threshold")
        if state_bytes > max_state_bytes:
            problems.append("foundry_state_above_threshold")

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

    provider_tariffs = _provider_tariff_health(state_root, now)
    if provider_tariffs.get("evidence") != "none":
        if provider_tariffs.get("invalid") is True:
            problems.append("provider_tariff_evidence_invalid")
        seconds_to_expiry = provider_tariffs.get("seconds_until_next_expiry")
        if provider_tariffs.get("active_routes") == 0:
            problems.append("no_current_priced_provider_route")
        elif isinstance(seconds_to_expiry, (int, float)):
            if seconds_to_expiry <= 0:
                problems.append("provider_tariff_expired")
            elif seconds_to_expiry <= 86_400:
                warnings.append("provider_tariff_expires_within_24h")

    if terminal:
        verdict, exit_code = "killed", EXIT_TERMINAL
    elif quarantine_files:
        verdict, exit_code = "quarantined", EXIT_TERMINAL
    elif halt:
        verdict, exit_code = "halted", EXIT_TERMINAL
    elif problems:
        verdict, exit_code = "unhealthy", EXIT_UNHEALTHY
    elif service_status == "stopped":
        verdict, exit_code = "stopped", EXIT_DEGRADED
    elif warnings:
        verdict, exit_code = "degraded", EXIT_DEGRADED
    else:
        verdict, exit_code = "healthy", EXIT_OK

    payload = {
        "schema_version": "foundry_status.v2",
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
            "writer_fence": service.get("writer_fence", 0),
            "restart_churn_24h": restart_churn,
            "last_completed_cycle_at": (
                last_completed.isoformat() if last_completed else None
            ),
            "progress_age_seconds": progress_age,
            "valid_candidates": service.get("total_valid_candidates", 0),
            "verified_receipts": service.get("verified_receipts", 0),
            "comparable_fitness": service.get("comparable_fitness", 0.0),
            "no_op_ratio": no_op_ratio,
            "spend_rate_usd_per_hour": service.get(
                "spend_rate_usd_per_hour", 0.0
            ),
            "target_quarantine": service.get("target_quarantine", {}),
        },
        "terminal_kill": terminal,
        "durable_halt": halt,
        "quarantine": [str(path) for path in quarantine_files],
        "runtime_dependencies": runtime,
        "receipt_audit": receipt_audit.to_dict(),
        "live_receipt_chain": {"ok": live_ok, "detail": live_detail},
        "spend_ledger": spend_ledger,
        "provider_tariffs": provider_tariffs,
        "disk": disk,
        "latest_receipt_at": newest_receipt.isoformat() if newest_receipt else None,
        "receipt_age_seconds": receipt_age,
        "problems": problems,
        "warnings": warnings,
        "health_basis": (
            "exact clean code SHA + fresh heartbeat + expected live process + "
            "runtime dependencies + append-only receipt/artifact integrity"
            " + conservative crash-durable spend accounting + distinct "
            "evolution-progress evidence"
        ),
    }
    return payload, exit_code
