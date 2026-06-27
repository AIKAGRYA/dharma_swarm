#!/usr/bin/env python3
"""Compact read-only daemon status for operator use.

This script intentionally avoids process-environment dumps. It combines the
launchd service state, daemon health endpoint, live-ops census, recent log
signals, and git hygiene into one terminal-sized report.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
STATE_ROOT = Path.home() / ".dharma"
DEFAULT_CENSUS = STATE_ROOT / "ops" / "live_process_census.json"
DEFAULT_LOG = STATE_ROOT / "logs" / "swarm.log"
HEALTH_URL = "http://127.0.0.1:7433/health"
LAUNCHD_LABEL = f"gui/{os.getuid()}/com.dharma.swarm"

TICK_RE = re.compile(
    r"tick-(?P<tick>\d+) done \((?P<seconds>[\d.]+)s\): "
    r"dispatched=(?P<dispatched>\d+) settled=(?P<settled>\d+) "
    r"rescued=(?P<rescued>\d+) reopened=(?P<reopened>\d+) "
    r"ready=(?P<ready>\d+) blocked=(?P<blocked>\d+)"
)

from scripts.runtime.runtime_truth_closeout import (  # noqa: E402
    _burn_in_preflight_evidence,
    _burn_in_preflight_passed,
    _task_backlog_summary,
)

MAX_BURN_IN_PENDING_HIGH = 25
MAX_BURN_IN_PENDING_TOTAL = 100
MAX_BURN_IN_RUNNING = 25


def run(args: list[str], *, cwd: Path | None = None, timeout: float = 10.0) -> str:
    proc = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout).strip()
    return proc.stdout.strip()


def fetch_health(url: str = HEALTH_URL) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, json.JSONDecodeError, urllib.error.URLError) as exc:
        return {"status": "unreachable", "error": exc.__class__.__name__}
    return payload if isinstance(payload, dict) else {"status": "bad_payload"}


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def refresh_census(census_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "runtime" / "live_ops_census.py"
    run(
        [
            sys.executable,
            str(script),
            "--write",
            "--output",
            str(census_path),
        ],
        cwd=REPO_ROOT,
        timeout=45.0,
    )


def launchd_state(label: str) -> dict[str, str]:
    text = run(["launchctl", "print", label], timeout=10.0)
    state: dict[str, str] = {"raw_ok": "true" if " = {" in text else "false"}
    for key in ("state", "runs", "pid", "last exit code"):
        match = re.search(rf"^\s*{re.escape(key)} = (.+)$", text, re.MULTILINE)
        if match:
            state[key.replace(" ", "_")] = match.group(1).strip()
    return state


def git_state() -> dict[str, str]:
    branch = run(["git", "branch", "--show-current"], cwd=REPO_ROOT)
    dirty_lines = run(
        ["git", "status", "--porcelain=v1", "-uall"],
        cwd=REPO_ROOT,
        timeout=20.0,
    ).splitlines()
    divergence = run(
        ["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"],
        cwd=REPO_ROOT,
        timeout=20.0,
    )
    return {
        "branch": branch or "<detached>",
        "dirty_entries": str(len([line for line in dirty_lines if line.strip()])),
        "origin_main_divergence": divergence,
    }


def ps_for_health(health: dict[str, Any]) -> str:
    pids = [
        str(value)
        for value in (health.get("daemon_pid"), health.get("health_process_pid"))
        if value
    ]
    if not pids:
        return ""
    return run(["ps", "-p", ",".join(pids), "-o", "pid,ppid,etime,stat,command"])


def tail_text(path: Path, max_bytes: int = 200_000) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def log_summary(path: Path) -> dict[str, Any]:
    text = tail_text(path)
    lines = text.splitlines()
    latest_tick: dict[str, str] = {}
    for line in reversed(lines):
        match = TICK_RE.search(line)
        if match:
            latest_tick = match.groupdict()
            break
    start_index = 0
    for index, line in reversed(list(enumerate(lines))):
        if "DGC Live Orchestrator starting" in line:
            start_index = index
            break
    current_run_lines = lines[start_index:]
    latest_pause = next(
        (line for line in reversed(current_run_lines) if "Paused (.PAUSE file)" in line),
        "",
    )
    latest_ancillary = next(
        (line for line in reversed(current_run_lines) if "Ancillary systems launched" in line),
        "",
    )
    return {
        "latest_tick": latest_tick,
        "latest_pause": latest_pause,
        "latest_ancillary": latest_ancillary,
        "token_budget_blocks": str(text.count("Daily token budget exhausted")),
        "rate_limits": str(text.count("Too Many Requests")),
        "credit_balance_errors": str(text.count("Credit balance is too low")),
    }


def find_surface(census: dict[str, Any], surface_id: str) -> dict[str, Any]:
    for surface in census.get("surfaces") or []:
        if isinstance(surface, dict) and surface.get("id") == surface_id:
            return surface
    return {}


def provider_model_line(coverage: dict[str, Any]) -> str:
    sample = coverage.get("latest_sample_size")
    latest = coverage.get("latest_major_task_receipts_provider_model_percent")
    latest_accounted = coverage.get(
        "latest_major_task_receipts_provider_model_accounted_percent"
    )
    terminal_sample = coverage.get("latest_terminal_sample_size")
    terminal = coverage.get("latest_terminal_major_task_receipts_provider_model_percent")
    terminal_accounted = coverage.get(
        "latest_terminal_major_task_receipts_provider_model_accounted_percent"
    )
    basis = coverage.get("provider_model_readiness_basis")
    scope = coverage.get("scope_mode") or "all"
    since = coverage.get("scope_since_created_at") or ""
    scope_text = f"; scope={scope}"
    if since:
        scope_text += f" since={since}"
    return (
        f"latest_payload={latest}% of {sample}; "
        f"latest_accounted={latest_accounted}% of {sample}; "
        f"terminal_payload={terminal}% of {terminal_sample}; "
        f"terminal_accounted={terminal_accounted}% of {terminal_sample}; "
        f"basis={basis}"
        f"{scope_text}"
    )


def pause_state(path: Path, logs: dict[str, Any]) -> dict[str, Any]:
    present = path.exists()
    return {
        "present": present,
        "state": "paused_by_file" if present else "not_paused",
        "path": str(path),
        "latest_pause_seen": bool(logs.get("latest_pause")),
        "effect": (
            "daemon should skip dispatch/action loops while the file exists"
            if present
            else "daemon is not gated by the pause file"
        ),
    }


def launch_spec_line(raw: dict[str, Any]) -> str:
    dispatch = raw.get("dispatch_launch")
    if not isinstance(dispatch, dict) or not dispatch:
        return "state=unknown repo_module=? ambient_dgc=? evidence=missing"
    evidence = str(dispatch.get("evidence") or "no evidence")
    return (
        f"state={dispatch.get('state', 'unknown')} "
        f"repo_module={dispatch.get('repo_module_invocation', '?')} "
        f"ambient_dgc={dispatch.get('ambient_dgc_invocation', '?')} "
        f"evidence={evidence}"
    )


def runtime_readiness_failures(
    daemon: dict[str, Any],
    *,
    burn_in_preflight: dict[str, Any] | None = None,
) -> list[str]:
    failures: list[str] = []
    if not daemon:
        return ["daemon_surface_missing"]

    proof_gaps = [
        str(gap)
        for gap in (daemon.get("proof_gaps") or [])
        if str(gap or "").strip()
    ]
    failures.extend(f"proof_gap:{gap}" for gap in proof_gaps)

    raw = daemon.get("raw") or {}
    coverage = raw.get("runtime_receipt_coverage") or {}
    active_head = raw.get("runtime_receipt_active_head") or {}
    since_boot = raw.get("runtime_receipt_since_boot") or {}
    clean_epoch = raw.get("runtime_truth_clean_epoch") or {}

    if coverage.get("coverage_report_available") is not True:
        failures.append("runtime_receipt_coverage_unavailable")
    if not coverage.get("latest_sample_size"):
        failures.append("runtime_receipt_latest_sample_empty")
    if coverage.get("provider_model_latest_complete") is not True:
        failures.append("provider_model_latest_incomplete")
    if coverage.get("active_head_clean") is False:
        failures.append("runtime_receipt_coverage_active_head_dirty")
    if coverage.get("latest_fresh") is False:
        failures.append("runtime_receipt_coverage_stale")
    if clean_epoch.get("exists") is True and clean_epoch.get("enabled") is not True:
        failures.append("runtime_truth_clean_epoch_invalid")

    blockers = [
        str(blocker)
        for blocker in (coverage.get("production_readiness_blockers") or [])
        if str(blocker or "").strip()
    ]
    failures.extend(f"readiness_blocker:{blocker}" for blocker in blockers)
    coverage_blockers = [
        str(blocker)
        for blocker in (coverage.get("blockers") or [])
        if str(blocker or "").strip()
    ]
    failures.extend(f"coverage_blocker:{blocker}" for blocker in coverage_blockers)

    if active_head.get("active_head_side_effect_key_clean") is not True:
        failures.append("runtime_receipt_active_head_side_effect_key_dirty")
    if active_head.get("latest_fresh") is not True:
        failures.append("runtime_receipt_active_head_stale")

    if since_boot.get("since_boot_major_identity_clean") is not True:
        failures.append("runtime_receipt_since_boot_identity_unproven")
    if since_boot.get("since_boot_major_identity_clean") is False:
        if int(since_boot.get("missing_side_effect_key") or 0) > 0:
            failures.append("runtime_receipt_since_boot_side_effect_key_dirty")
        if int(since_boot.get("missing_idempotency_key") or 0) > 0:
            failures.append("runtime_receipt_since_boot_idempotency_key_dirty")

    if burn_in_preflight is not None and not _burn_in_preflight_passed(
        burn_in_preflight,
        max_pending_high=MAX_BURN_IN_PENDING_HIGH,
        max_pending_total=MAX_BURN_IN_PENDING_TOTAL,
        max_running=MAX_BURN_IN_RUNNING,
    ):
        failures.append("unpaused_burn_in_preflight_unsafe")

    return failures


def print_status(args: argparse.Namespace) -> int:
    census_path = Path(args.census)
    if args.refresh_census:
        refresh_census(census_path)

    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    health = fetch_health(args.health_url)
    launchd = launchd_state(args.launchd_label)
    census = load_json(census_path)
    daemon = find_surface(census, "substrate.dharma_daemon")
    raw = daemon.get("raw") or {}
    coverage = raw.get("runtime_receipt_coverage") or {}
    active_head = raw.get("runtime_receipt_active_head") or {}
    since_boot = raw.get("runtime_receipt_since_boot") or {}
    source_state = raw.get("process_source_state") or {}
    logs = log_summary(Path(args.log))
    git = git_state()
    summary = census.get("summary") or {}
    proof_gaps = daemon.get("proof_gaps") or []
    tick = logs.get("latest_tick") or {}
    blockers = [
        *(coverage.get("blockers") or []),
        *(coverage.get("production_readiness_blockers") or []),
    ]
    pause = pause_state(STATE_ROOT / ".PAUSE", logs)
    burn_in_preflight = _task_backlog_summary(STATE_ROOT)
    burn_in_safe = _burn_in_preflight_passed(
        burn_in_preflight,
        max_pending_high=MAX_BURN_IN_PENDING_HIGH,
        max_pending_total=MAX_BURN_IN_PENDING_TOTAL,
        max_running=MAX_BURN_IN_RUNNING,
    )
    burn_in_evidence = _burn_in_preflight_evidence(burn_in_preflight)
    readiness_failures = runtime_readiness_failures(
        daemon,
        burn_in_preflight=burn_in_preflight,
    )
    if pause["present"]:
        readiness_failures.append("daemon_pause_file_present")

    print("Dharma Daemon Operator Status")
    print(f"generated: {now}")
    print(f"repo: {git['branch']} dirty={git['dirty_entries']} origin/main...HEAD={git['origin_main_divergence']}")
    print(
        "launchd: "
        f"state={launchd.get('state', 'unknown')} "
        f"pid={launchd.get('pid', '?')} "
        f"runs={launchd.get('runs', '?')} "
        f"last_exit={launchd.get('last_exit_code', '?')}"
    )
    print(
        "health: "
        f"status={health.get('status')} uptime={health.get('uptime', '?')} "
        f"daemon_pid={health.get('daemon_pid', '?')} "
        f"health_pid={health.get('health_process_pid', '?')} "
        f"spine={((health.get('runtime_dispatch') or {}).get('spine_dispatch_enabled'))}"
    )
    print(f"launch_spec: {launch_spec_line(raw)}")
    print(
        "pause: "
        f"state={pause['state']} present={pause['present']} "
        f"path={pause['path']} "
        f"effect={pause['effect']} "
        f"latest_pause_seen={pause['latest_pause_seen']} "
        f"latest_ancillary_seen={bool(logs.get('latest_ancillary'))}"
    )
    print(
        "census: "
        f"daemon={daemon.get('status', 'missing')}/{daemon.get('proof_state', 'unknown')} "
        f"summary={summary.get('by_status', {})} proof_gap_surfaces={summary.get('proof_gap_surfaces')}"
    )
    print(
        "source: "
        f"{source_state.get('state', 'unknown')} - {source_state.get('evidence', 'no evidence')}"
    )
    print(
        "efficacy: "
        f"tick={tick.get('tick', '?')} dispatched={tick.get('dispatched', '?')} "
        f"ready={tick.get('ready', '?')} blocked={tick.get('blocked', '?')} "
        f"tick_seconds={tick.get('seconds', '?')}"
    )
    print(
        "log_pressure: "
        f"token_budget_blocks={logs['token_budget_blocks']} "
        f"rate_limits={logs['rate_limits']} "
        f"credit_balance_errors={logs['credit_balance_errors']}"
    )
    print(f"provider_model_receipts: {provider_model_line(coverage)}")
    print(
        "unpaused_burn_in_preflight: "
        f"safe={burn_in_safe} "
        f"{burn_in_evidence} "
        f"limits high_or_urgent<={MAX_BURN_IN_PENDING_HIGH} "
        f"total<={MAX_BURN_IN_PENDING_TOTAL} "
        f"running<={MAX_BURN_IN_RUNNING}"
    )
    clean_epoch = raw.get("runtime_truth_clean_epoch") or {}
    if clean_epoch:
        print(
            "runtime_truth_clean_epoch: "
            f"enabled={clean_epoch.get('enabled')} "
            f"since={clean_epoch.get('since_created_at', '') or '?'} "
            f"receipt={clean_epoch.get('receipt_id', '') or '?'} "
            f"evidence={clean_epoch.get('evidence', '') or '?'}"
        )
    print(f"active_head_side_effect_key: {active_head.get('active_head_side_effect_key_clean')}")
    print(
        "since_boot_major_receipts: "
        f"clean={since_boot.get('since_boot_major_identity_clean')} "
        f"start={since_boot.get('process_started_at', '') or '?'} "
        f"total={since_boot.get('major_since_boot_total', '?')} "
        f"missing_side_effect_key={since_boot.get('missing_side_effect_key', '?')} "
        f"missing_idempotency_key={since_boot.get('missing_idempotency_key', '?')}"
    )

    if proof_gaps:
        print("proof_gaps:")
        for gap in proof_gaps:
            print(f"  - {gap}")

    if blockers:
        print("readiness_blockers:")
        for blocker in blockers:
            print(f"  - {blocker}")

    if readiness_failures:
        print("runtime_readiness_failures:")
        for failure in readiness_failures:
            print(f"  - {failure}")

    problems = [
        surface
        for surface in census.get("surfaces") or []
        if isinstance(surface, dict)
        and (surface.get("status") != "live" or surface.get("proof_gaps"))
    ]
    if problems:
        print("problem_surfaces:")
        for surface in problems[:8]:
            gaps = ",".join(surface.get("proof_gaps") or [])
            gap_text = f" gaps={gaps}" if gaps else ""
            print(
                f"  - {surface.get('id')}: {surface.get('status')}/"
                f"{surface.get('proof_state')}{gap_text}"
            )

    process_lines = ps_for_health(health) if args.show_process else ""
    if process_lines:
        print("process:")
        for line in process_lines.splitlines():
            print(f"  {line}")

    return (
        0
        if health.get("status") == "ok"
        and launchd.get("state") == "running"
        and not readiness_failures
        else 1
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census", default=str(DEFAULT_CENSUS))
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--health-url", default=HEALTH_URL)
    parser.add_argument("--launchd-label", default=LAUNCHD_LABEL)
    parser.add_argument(
        "--refresh-census",
        dest="refresh_census",
        action="store_true",
        default=True,
        help="refresh the live-ops census before printing status (default)",
    )
    parser.add_argument(
        "--no-refresh-census",
        dest="refresh_census",
        action="store_false",
        help="read the existing census file without refreshing it",
    )
    parser.add_argument("--show-process", action="store_true")
    return print_status(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
