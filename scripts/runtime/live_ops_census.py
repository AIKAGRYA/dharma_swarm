#!/usr/bin/env python3
"""Build a read-only live-ops census for the operator cockpit.

This script is an observation surface, not a supervisor. It does not start,
stop, restart, kill, message, or mutate live processes. It folds the existing
governance owner files into one runtime census so the dashboard can show
declared intent, observed state, evidence paths, and operator policy together.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import plistlib
import re
import shlex
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_IMPORT))

from dharma_swarm.operator_core.live_ops_census_contract import (  # noqa: E402
    DEFAULT_OUTPUT,
    DEFAULT_STATE_ROOT,
    LIVE_OPS_CENSUS_MAX_AGE_HOURS as LIVE_OPS_CENSUS_MAX_AGE_HOURS,
    LIVE_OPS_CENSUS_SCHEMA_VERSION,
    census_payload_freshness as census_payload_freshness,
    default_output_path as default_output_path,
    default_state_root as default_state_root,
    validate_census_payload as validate_census_payload,
)
from dharma_swarm.operator_core.ds_goal_wrapper_contract import (  # noqa: E402
    default_wrapper_target as ds_goal_default_wrapper_target,
    installed_wrapper_contract,
    wrapper_convergence_decision_packet,
    wrapper_longrun_preflight_gate,
)
from dharma_swarm.holon_persistence import (  # noqa: E402
    load_session as load_holon_session,
    resume_point as holon_resume_point,
)
from dharma_swarm.holon_service_liveness import (  # noqa: E402
    assess_service_liveness as assess_holon_service_liveness,
    service_heartbeat_path as holon_service_heartbeat_path,
)
from dharma_swarm.holon_transport_liveness import (  # noqa: E402
    assess_a2a_inbox_bridge_liveness as assess_holon_a2a_transport_liveness,
)


RUNTIME_RECEIPT_HEAD_WINDOWS_MINUTES = (5, 15, 60)
RUNTIME_RECEIPT_HEAD_MAX_AGE_HOURS = 6.0
RUNTIME_RECEIPT_SINCE_BOOT_MAJOR_TYPES = ("a2a_task", "delegation_run", "task_claim")
RUNTIME_TRUTH_CLEAN_EPOCH_FILENAME = "runtime_truth_clean_epoch.json"
NATS_HOT_CONTACT_MAX_AGE_HOURS = 24.0
NATS_OPERATOR_HOT_CONTACT_ACK_TIERS = {"HANDLER_ACKED", "DOMAIN_RECEIPTED"}
A2A_MIRROR_MAX_AGE_HOURS = 24.0
A2A_INBOX_BRIDGE_HEARTBEAT_MAX_AGE_HOURS = 1.0
HOLON_L4_AGENT_UID = "codex_composer"
HOLON_L4_SERVICE_FRESH_SECONDS = 3600
HOLON_L4_PROOF_MAX_AGE_HOURS = 24.0
HOLON_L4_MODEL_PROOF_MAX_AGE_HOURS = 24.0
DEFAULT_REPO_ROOT = _REPO_ROOT_FOR_IMPORT


AUTHORITY_SOURCES: tuple[dict[str, str], ...] = (
    {
        "id": "onboard_renderer",
        "layer": "renderer",
        "path": "scripts/governance/agent_onboard.py",
        "role": "single-door render of current operating reality",
    },
    {
        "id": "intent",
        "layer": "intent",
        "path": "docs/governance/ACTIVE_TRACK.yaml",
        "role": "single owner of active build-track intent",
    },
    {
        "id": "surface_manifest",
        "layer": "surface",
        "path": "ACTIVE_SURFACE_MANIFEST.yaml",
        "role": "single owner of declared surfaces, state dirs, routers, and dashboard nav",
    },
    {
        "id": "live_ops",
        "layer": "state",
        "path": "docs/state/LIVE_OPS_DASHBOARD.md",
        "role": "plain-language live-state briefing; may be stale",
    },
    {
        "id": "broken_register",
        "layer": "state",
        "path": "docs/state/BROKEN_REGISTER.md",
        "role": "known breakage register",
    },
    {
        "id": "sovereign_manifest",
        "layer": "doctrine",
        "path": "docs/governance/SOVEREIGN_MANIFEST.md",
        "role": "architecture, axioms, and invariants",
    },
    {
        "id": "anti_slop",
        "layer": "governance",
        "path": "docs/governance/ANTI_SLOP_RULES.md",
        "role": "anti-duplication and no-new-substrate discipline",
    },
    {
        "id": "canonical_doc_stack",
        "layer": "governance",
        "path": "docs/governance/CANONICAL_DOC_STACK.md",
        "role": "doc ownership map and three-layer SSoT model",
    },
    {
        "id": "nats_substrate",
        "layer": "transport",
        "path": "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md",
        "role": "internal live-transport contract",
    },
    {
        "id": "tmux_substrate",
        "layer": "terminal",
        "path": "docs/ops/TMUX_AGENT_SUBSTRATE.md",
        "role": "terminal-persistence contract",
    },
)


PROCESS_PATTERNS: dict[str, str] = {
    "dharma_daemon": r"dharma_swarm\.dgc_cli orchestrate-live|[ /]dgc orchestrate-live",
    "dharma_cron": r"dharma_swarm\.dgc_cli cron daemon|[ /]dgc cron daemon",
    "nats": r"nats-server .*local-nats\.conf",
    "a2a_inbox_bridge": r"a2a_inbox_bridge\.py",
    "hermes_a2a": r"hermes_a2a_server\.py",
    "hermes_llm_bridge": r"hermes_llm_bridge\.py",
    "dashboard_api": r"uvicorn api\.main:app|api\.main:app",
    "dashboard_web": r"next-server|next dev|node .*:3420",
    "forge_hydra": r"codex_overnight_autopilot\.py|forge-reality-arena-master",
    "revenue_gate": r"revenue_wedge_gate",
    "cashclaw": r"cashclaw|CashClaw",
    "agni": r"kaizen_agni|agni-trading|ssh agni",
    "merge_master_mike": r"merge_master_mike|merge-master-mike",
    "terminal_tui": r"dharma_terminal_tui|bun run src/index\.tsx|bun .*terminal/src/index\.tsx",
    "colima_openclaw": r"colima-openclaw-secure|qemu-system-aarch64 .*openclaw",
}

LAUNCHD_PROCESS_FALLBACKS: dict[str, str] = {
    "dharma_daemon": "com.dharma.swarm",
    "dharma_cron": "com.dharma.cron-daemon",
}


def _launch_uses_repo_cli(command: str, repo_root: Path, cli_args: str) -> bool:
    repo_text = str(repo_root)
    return f"-m dharma_swarm.dgc_cli {cli_args}" in command and (
        f"PYTHONPATH={repo_text}" in command
        or "PYTHONPATH=." in command
        or f"cd {repo_text}" in command
        or ".venv/bin/python" in command
    )


def _launch_uses_repo_module(command: str, repo_root: Path) -> bool:
    return _launch_uses_repo_cli(command, repo_root, "orchestrate-live")


def _launch_uses_ambient_dgc_cli(command: str, cli_args: str) -> bool:
    pattern = rf"(^|[\s/])dgc\s+{re.escape(cli_args)}\b"
    return re.search(pattern, command) is not None


def _launch_uses_ambient_dgc(command: str) -> bool:
    return _launch_uses_ambient_dgc_cli(command, "orchestrate-live")


PORTS: dict[str, int] = {
    "dharma_daemon": 7433,
    "nats": 4222,
    "nats_monitor": 8222,
    "hermes_a2a": 8421,
    "hermes_llm_bridge": 9421,
    "dashboard_api": 8420,
    "dashboard_web": 3420,
}

HTTP_PROBES: dict[str, str] = {
    "dashboard_control_surface_rows": "http://127.0.0.1:8420/api/control-surface/rows",
}

HTTP_PROBE_TIMEOUT_SECONDS = 5.0
DAEMON_HEALTH_URL = "http://127.0.0.1:7433/health"
DAEMON_HEALTH_TIMEOUT_SECONDS = 1.5
DAEMON_RUNTIME_DISPATCH_SELF_REPORT_MAX_AGE_HOURS = 0.25
DASHBOARD_ROWS_PROBE_TIMEOUT_SECONDS = 12.0
DASHBOARD_ROWS_FAST_RESPONSE_SECONDS = 2.0
FORGE_REALITY_ARENA_STATUS_PACKET = (
    "reports/agentops/work_packets/forge-reality-arena-status.json"
)
PROC_PIDTBSDINFO = 3
MAXCOMLEN = 16

DAEMON_SPINE_RUNTIME_PROOFS = {
    "spine_enabled_self_report",
    "daemon_default_receipt_proven",
    "daemon_default_spine_receipt_proven",
}
DAEMON_RUNTIME_DISPATCH_SELF_REPORT_SCHEMA_VERSION = (
    "dharma.daemon.runtime_dispatch_self_report.v1"
)

DAEMON_RUNTIME_SOURCE_PATHS: tuple[str, ...] = (
    "dharma_swarm/dgc_cli.py",
    "dharma_swarm/orchestrator.py",
    "dharma_swarm/runtime_lifecycle.py",
    "dharma_swarm/runtime_state.py",
    "dharma_swarm/swarm_health_api.py",
)

DASHBOARD_CONTROL_SURFACE_SOURCE_PATHS: tuple[str, ...] = (
    "api/main.py",
    "api/routers/control_surface.py",
    "dashboard/src/app/dashboard/control-surface/page.tsx",
    "dashboard/src/components/cockpit/EvidenceDrawer.tsx",
    "dashboard/src/components/cockpit/SystemTruthMatrix.tsx",
    "dashboard/src/lib/controlSurfaceRuntimeEvidence.ts",
    "dharma_swarm/operator_core/control_surface.py",
    "dharma_swarm/operator_core/control_surface_live_ops.py",
    "dharma_swarm/operator_core/control_surface_models.py",
)

TERMINAL_TUI_SOURCE_PATHS: tuple[str, ...] = (
    "terminal/package.json",
    "terminal/src/index.tsx",
    "terminal/src/app.tsx",
    "terminal/src/state.ts",
    "terminal/src/protocol.ts",
    "terminal/src/bridge.ts",
    "terminal/src/persistence.ts",
    "terminal/src/routePolicy.ts",
)

DS_GOAL_CLI_SOURCE_PATHS: tuple[str, ...] = (
    "scripts/runtime/autonomy_spine.py",
    "dharma_swarm/runtime_state.py",
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iso_mtime(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except OSError:
        return ""


def _age_hours(iso_ts: str) -> float | None:
    if not iso_ts:
        return None
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return round((datetime.now(UTC) - ts).total_seconds() / 3600, 2)


def _run(args: list[str], *, cwd: Path | None = None, timeout: int = 5) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)
    return proc.returncode, proc.stdout.strip()


def _authority_sources(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in AUTHORITY_SOURCES:
        path = repo_root / item["path"]
        rows.append(
            {
                **item,
                "exists": path.exists(),
                "mtime": _iso_mtime(path),
            }
        )
    return rows


def _git_boundary(repo_root: Path) -> dict[str, Any]:
    rc_head, head = _run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root)
    rc_branch, branch = _run(["git", "branch", "--show-current"], cwd=repo_root)
    rc_status, status = _run(["git", "status", "--short"], cwd=repo_root)
    dirty_lines = [line for line in status.splitlines() if line.strip()] if rc_status == 0 else []
    return {
        "branch": branch if rc_branch == 0 else "",
        "head": head if rc_head == 0 else "",
        "dirty_count": len(dirty_lines),
        "dirty_sample": dirty_lines[:20],
    }


def _same_resolved_path(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left.expanduser().absolute() == right.expanduser().absolute()


def _path_is_within(child: Path, parent: Path) -> bool:
    try:
        child.expanduser().resolve().relative_to(parent.expanduser().resolve())
    except (OSError, ValueError):
        return False
    return True


def _source_file_rows(repo_root: Path, source_paths: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel_path in source_paths:
        path = repo_root / rel_path
        row: dict[str, Any] = {
            "path": rel_path,
            "exists": path.exists(),
            "mtime": _iso_mtime(path),
        }
        rows.append(row)
    return rows


def _ds_goal_sync_receipt_hardening_state(repo_root: Path) -> dict[str, Any]:
    source = repo_root / "dharma_swarm" / "runtime_state.py"
    result: dict[str, Any] = {
        "source_path": str(source),
        "source_exists": source.exists(),
        "task_claim_side_effect_key": False,
        "delegation_run_side_effect_key": False,
        "state": "source_missing",
        "evidence": "runtime_state.py missing in ds-goal target checkout",
    }
    if not source.exists():
        return result
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        result["state"] = "source_unreadable"
        result["evidence"] = str(exc)
        return result

    task_claim_side_effect_key = "task_claim:{claim.claim_id}:{claim.status}" in text
    delegation_run_side_effect_key = (
        "delegation_run:{identity.run_id}:{run.status}" in text
    )
    result.update({
        "task_claim_side_effect_key": task_claim_side_effect_key,
        "delegation_run_side_effect_key": delegation_run_side_effect_key,
    })
    if task_claim_side_effect_key and delegation_run_side_effect_key:
        result["state"] = "sync_receipt_side_effect_keys_hardened"
        result["evidence"] = "sync claim/run helpers derive side_effect_key before receipt emission"
    else:
        result["state"] = "sync_receipt_side_effect_keys_missing"
        result["evidence"] = "sync claim/run helpers can emit identity receipts without side_effect_key"
    return result


def _ds_goal_cli_state(repo_root: Path) -> dict[str, Any]:
    home = Path.home()
    wrapper = home / ".dharma" / "bin" / "ds-goal"
    result: dict[str, Any] = {
        "wrapper_path": str(wrapper),
        "wrapper_exists": wrapper.exists(),
        "wrapper_mentions_dharma_swarm_main": False,
        "installed_wrapper_contract": {},
        "convergence_decision_packet": {},
        "longrun_preflight_gate": {},
        "default_wrapper_target": {},
        "target_repo": "",
        "target_resolution_source": "",
        "current_repo": str(repo_root),
        "target_matches_current_repo": False,
        "safe_current_checkout_invocation": "",
        "target_source_files": [],
        "target_sync_receipt_hardening": {},
        "state": "wrapper_missing",
        "evidence": "ds-goal wrapper not found",
    }
    if not wrapper.exists():
        return result
    if not _path_is_within(repo_root, home):
        result["state"] = "repo_outside_operator_home"
        result["evidence"] = "ds-goal wrapper target check skipped for non-home checkout"
        return result

    try:
        contract = installed_wrapper_contract(wrapper)
    except OSError as exc:
        result["state"] = "wrapper_unreadable"
        result["evidence"] = str(exc)
        return result
    result["installed_wrapper_contract"] = contract
    result["wrapper_mentions_dharma_swarm_main"] = bool(
        contract.get("dharma_swarm_main_preference_declared")
    )
    if contract.get("read_error"):
        result["state"] = "wrapper_unreadable"
        result["evidence"] = str(contract.get("read_error") or "")
        return result
    if contract.get("dharma_swarm_repo_pin_supported"):
        result["safe_current_checkout_invocation"] = (
            f"DHARMA_SWARM_REPO={shlex.quote(str(repo_root))} "
            f"{shlex.quote(str(wrapper))}"
        )

    env_repo = str(os.environ.get("DHARMA_SWARM_REPO") or "").strip()
    repo_pin = Path(env_repo).expanduser() if env_repo else None
    default_target = ds_goal_default_wrapper_target(
        home=home,
        audited_repo=repo_root,
        wrapper=wrapper,
    )
    result["convergence_decision_packet"] = wrapper_convergence_decision_packet(
        home=home,
        audited_repo=repo_root,
        wrapper=wrapper,
    )
    result["longrun_preflight_gate"] = wrapper_longrun_preflight_gate(
        home=home,
        audited_repo=repo_root,
        wrapper=wrapper,
        repo_pin=repo_pin,
        repo_pin_source="DHARMA_SWARM_REPO" if repo_pin is not None else "none",
    )
    result["default_wrapper_target"] = default_target
    if env_repo:
        target_repo = repo_pin if repo_pin is not None else Path(env_repo).expanduser()
        resolution_source = "DHARMA_SWARM_REPO"
    else:
        target_repo = Path(str(default_target.get("target_repo") or ""))
        resolution_source = str(default_target.get("target_resolution_source") or "")

    target_matches_current_repo = _same_resolved_path(target_repo, repo_root)
    hardening = _ds_goal_sync_receipt_hardening_state(target_repo)
    target_source_files = _source_file_rows(target_repo, DS_GOAL_CLI_SOURCE_PATHS)
    result.update({
        "target_repo": str(target_repo),
        "target_resolution_source": resolution_source,
        "target_matches_current_repo": target_matches_current_repo,
        "target_source_files": target_source_files,
        "target_sync_receipt_hardening": hardening,
    })
    if not target_matches_current_repo:
        result["state"] = "target_repo_mismatch"
        result["evidence"] = "ds-goal wrapper resolves to a different checkout than this census"
    elif hardening.get("state") != "sync_receipt_side_effect_keys_hardened":
        result["state"] = "target_lacks_sync_receipt_hardening"
        result["evidence"] = str(hardening.get("evidence") or "")
    else:
        result["state"] = "target_current_and_hardened"
        result["evidence"] = "ds-goal wrapper targets this checkout and sync receipts are hardened"
    return result


def _parse_pgrep(output: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 1:
            rows.append({"pid": parts[0], "command": ""})
        else:
            rows.append({"pid": parts[0], "command": parts[1]})
    return rows


def _parse_lsof_listeners(output: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("COMMAND "):
            continue
        parts = line.split(maxsplit=8)
        if len(parts) < 2:
            continue
        pid = parts[1].strip()
        if not pid.isdigit() or pid in seen:
            continue
        seen.add(pid)
        rows.append(
            {
                "pid": pid,
                "command": parts[0].strip(),
                "listen_name": parts[8].strip() if len(parts) >= 9 else "",
                "source": "lsof_listen",
            }
        )
    return rows


def _merge_port_owner_processes(
    processes: dict[str, list[dict[str, str]]],
    ports: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    merged = {key: [dict(row) for row in rows] for key, rows in processes.items()}
    for key, port_data in ports.items():
        owner_rows = [
            row
            for row in (port_data.get("owner_processes") or [])
            if isinstance(row, dict)
        ]
        if not owner_rows:
            continue
        rows = merged.setdefault(key, [])
        existing_pids = {str(row.get("pid") or "") for row in rows}
        for owner in owner_rows:
            pid = str(owner.get("pid") or "").strip()
            if not pid or pid in existing_pids:
                continue
            rows.append({str(k): str(v) for k, v in owner.items()})
            existing_pids.add(pid)
    return merged


def _process_snapshot(run_probes: bool) -> dict[str, list[dict[str, str]]]:
    if not run_probes:
        return {key: [] for key in PROCESS_PATTERNS}
    snapshot: dict[str, list[dict[str, str]]] = {}
    for key, pattern in PROCESS_PATTERNS.items():
        rc, out = _run(["pgrep", "-fl", pattern], timeout=4)
        rows = _parse_pgrep(out) if rc == 0 else []
        if not rows and key in LAUNCHD_PROCESS_FALLBACKS:
            rows = _launchctl_process_rows(LAUNCHD_PROCESS_FALLBACKS[key])
        snapshot[key] = rows
    return snapshot


def _launchctl_process_rows(label: str) -> list[dict[str, str]]:
    rc, out = _run(["launchctl", "print", f"gui/{os.getuid()}/{label}"], timeout=4)
    if rc != 0:
        return []
    state_match = re.search(r"(?m)^\s*state = ([^\n]+)", out)
    state = state_match.group(1).strip() if state_match else ""
    if state != "running":
        return []
    pid_match = re.search(r"(?m)^\s*pid = ([0-9]+)", out)
    if not pid_match:
        return []
    return [
        {
            "pid": pid_match.group(1),
            "command": f"launchctl:{label} state={state}",
        }
    ]


def _parse_ps_lstart(value: str) -> str:
    text = " ".join(value.split())
    if not text:
        return ""
    try:
        started = datetime.strptime(text, "%a %b %d %H:%M:%S %Y")
    except ValueError:
        return ""
    return started.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _darwin_process_start_time(pid: str) -> tuple[str, str]:
    if sys.platform != "darwin":
        return "", ""
    try:
        pid_int = int(pid)
    except ValueError:
        return "", "pid is not numeric"

    class ProcBsdInfo(ctypes.Structure):
        _fields_ = [
            ("pbi_flags", ctypes.c_uint32),
            ("pbi_status", ctypes.c_uint32),
            ("pbi_xstatus", ctypes.c_uint32),
            ("pbi_pid", ctypes.c_uint32),
            ("pbi_ppid", ctypes.c_uint32),
            ("pbi_uid", ctypes.c_uint32),
            ("pbi_gid", ctypes.c_uint32),
            ("pbi_ruid", ctypes.c_uint32),
            ("pbi_rgid", ctypes.c_uint32),
            ("pbi_svuid", ctypes.c_uint32),
            ("pbi_svgid", ctypes.c_uint32),
            ("rfu_1", ctypes.c_uint32),
            ("pbi_comm", ctypes.c_char * MAXCOMLEN),
            ("pbi_name", ctypes.c_char * (2 * MAXCOMLEN)),
            ("pbi_nfiles", ctypes.c_uint32),
            ("pbi_pgid", ctypes.c_uint32),
            ("pbi_pjobc", ctypes.c_uint32),
            ("e_tdev", ctypes.c_uint32),
            ("e_tpgid", ctypes.c_uint32),
            ("pbi_nice", ctypes.c_int32),
            ("pbi_start_tvsec", ctypes.c_uint64),
            ("pbi_start_tvusec", ctypes.c_uint64),
        ]

    try:
        libproc = ctypes.CDLL("/usr/lib/libproc.dylib")
        libproc.proc_pidinfo.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        libproc.proc_pidinfo.restype = ctypes.c_int
        info = ProcBsdInfo()
        size = ctypes.sizeof(info)
        ret = libproc.proc_pidinfo(
            pid_int,
            PROC_PIDTBSDINFO,
            0,
            ctypes.byref(info),
            size,
        )
    except (OSError, AttributeError, TypeError, ValueError) as exc:
        return "", f"libproc start probe failed: {exc}"

    if ret <= 0:
        return "", f"libproc start probe returned {ret}"
    if not info.pbi_start_tvsec:
        return "", "libproc start probe returned no start time"

    started = datetime.fromtimestamp(
        info.pbi_start_tvsec + (info.pbi_start_tvusec / 1_000_000),
        UTC,
    )
    return started.replace(microsecond=0).isoformat().replace("+00:00", "Z"), ""


def _process_start_snapshot(
    processes: dict[str, list[dict[str, str]]],
    run_probes: bool,
) -> dict[str, dict[str, str]]:
    if not run_probes:
        return {}
    snapshot: dict[str, dict[str, str]] = {}
    for key, rows in processes.items():
        starts: dict[str, str] = {}
        errors: list[dict[str, str]] = []
        for row in rows:
            pid = str(row.get("pid", "")).strip()
            if not pid.isdigit():
                continue
            started_at, libproc_error = _darwin_process_start_time(pid)
            rc = 0
            out = ""
            if not started_at:
                rc, out = _run(["ps", "-o", "lstart=", "-p", pid], timeout=4)
                started_at = _parse_ps_lstart(out) if rc == 0 else ""
            if started_at:
                starts[pid] = started_at
            elif rc != 0 or libproc_error:
                error_parts = [part for part in (libproc_error, out) if part]
                errors.append({"pid": pid, "error": "; ".join(error_parts)})
        if errors:
            starts["__probe_errors__"] = json.dumps(errors, sort_keys=True)
        if starts:
            snapshot[key] = starts
    return snapshot


def _process_start_probe_errors(process_starts: dict[str, str]) -> list[dict[str, str]]:
    raw = str(process_starts.get("__probe_errors__") or "")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return [{"pid": "", "error": raw}]
    if not isinstance(parsed, list):
        return []
    return [
        {"pid": str(row.get("pid") or ""), "error": str(row.get("error") or "")}
        for row in parsed
        if isinstance(row, dict)
    ]


def _port_snapshot(run_probes: bool) -> dict[str, dict[str, Any]]:
    if not run_probes:
        return {
            key: {
                "port": port,
                "listening": False,
                "evidence": "",
                "owner_processes": [],
            }
            for key, port in PORTS.items()
        }
    snapshot: dict[str, dict[str, Any]] = {}
    for key, port in PORTS.items():
        rc, out = _run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], timeout=4)
        snapshot[key] = {
            "port": port,
            "listening": rc == 0 and bool(out.strip()),
            "evidence": out.splitlines()[-1] if rc == 0 and out.splitlines() else "",
            "owner_processes": _parse_lsof_listeners(out) if rc == 0 else [],
        }
    return snapshot


def _http_json_probe(
    url: str,
    *,
    timeout_seconds: float = HTTP_PROBE_TIMEOUT_SECONDS,
    slow_threshold_seconds: float = DASHBOARD_ROWS_FAST_RESPONSE_SECONDS,
    max_bytes: int = 1_048_576,
) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(max_bytes + 1)
            elapsed = round(time.perf_counter() - started, 3)
            if len(body) > max_bytes:
                return {
                    "url": url,
                    "state": "too_large",
                    "http_status": int(response.status),
                    "elapsed_seconds": elapsed,
                    "timeout_seconds": timeout_seconds,
                    "evidence": f"JSON response exceeds {max_bytes} bytes",
                }
            payload = json.loads(body.decode("utf-8"))
    except TimeoutError as exc:
        elapsed = round(time.perf_counter() - started, 3)
        return {
            "url": url,
            "state": "timeout",
            "elapsed_seconds": elapsed,
            "timeout_seconds": timeout_seconds,
            "evidence": f"timed out after {timeout_seconds}s: {exc}",
        }
    except urllib.error.URLError as exc:
        elapsed = round(time.perf_counter() - started, 3)
        return {
            "url": url,
            "state": "unreachable",
            "elapsed_seconds": elapsed,
            "timeout_seconds": timeout_seconds,
            "evidence": str(exc.reason),
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        elapsed = round(time.perf_counter() - started, 3)
        return {
            "url": url,
            "state": "unreadable",
            "elapsed_seconds": elapsed,
            "timeout_seconds": timeout_seconds,
            "evidence": str(exc),
        }
    if not isinstance(payload, dict):
        return {
            "url": url,
            "state": "unreadable",
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "timeout_seconds": timeout_seconds,
            "evidence": "JSON response is not an object",
        }
    data = payload.get("data")
    source_errors = payload.get("source_errors")
    if isinstance(data, list):
        slow = elapsed > slow_threshold_seconds
        return {
            "url": url,
            "state": "ok",
            "http_status": int(response.status),
            "elapsed_seconds": elapsed,
            "timeout_seconds": timeout_seconds,
            "slow_threshold_seconds": slow_threshold_seconds,
            "slow": slow,
            "performance_state": "slow" if slow else "fast",
            "row_count": len(data),
            "source_error_count": len(source_errors) if isinstance(source_errors, list) else 0,
            "evidence": f"control-surface rows envelope returned data list in {elapsed}s",
        }
    return {
        "url": url,
        "state": "missing_data",
        "http_status": int(response.status),
        "elapsed_seconds": elapsed,
        "timeout_seconds": timeout_seconds,
        "evidence": "control-surface rows envelope missing data list",
    }


def _http_probe_snapshot(run_probes: bool) -> dict[str, dict[str, Any]]:
    if not run_probes:
        return {
            key: {
                "url": url,
                "state": "not_checked",
                "evidence": "HTTP probes disabled",
            }
            for key, url in HTTP_PROBES.items()
        }
    return {
        key: _http_json_probe(
            url,
            timeout_seconds=(
                DASHBOARD_ROWS_PROBE_TIMEOUT_SECONDS
                if key == "dashboard_control_surface_rows"
                else HTTP_PROBE_TIMEOUT_SECONDS
            ),
        )
        for key, url in HTTP_PROBES.items()
    }


def _fetch_json_document(
    url: str,
    *,
    timeout_seconds: float,
    max_bytes: int = 65_536,
) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError(f"JSON response exceeds {max_bytes} bytes")
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON response is not an object")
        return int(response.status), payload


def _daemon_health_self_report(
    *,
    run_probes: bool,
    url: str = DAEMON_HEALTH_URL,
    timeout_seconds: float = DAEMON_HEALTH_TIMEOUT_SECONDS,
    observed_pids: set[str] | None = None,
) -> dict[str, Any]:
    if not run_probes:
        return {
            "url": url,
            "state": "not_inspected_no_secret_env_dump",
            "evidence": "daemon health probe disabled",
        }
    try:
        status, payload = _fetch_json_document(url, timeout_seconds=timeout_seconds)
    except TimeoutError as exc:
        return {
            "url": url,
            "state": "timeout",
            "timeout_seconds": timeout_seconds,
            "evidence": f"timed out after {timeout_seconds}s: {exc}",
        }
    except urllib.error.URLError as exc:
        return {
            "url": url,
            "state": "unreachable",
            "timeout_seconds": timeout_seconds,
            "evidence": str(exc.reason),
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "url": url,
            "state": "unreadable",
            "timeout_seconds": timeout_seconds,
            "evidence": str(exc),
        }

    runtime_dispatch = payload.get("runtime_dispatch")
    if not isinstance(runtime_dispatch, dict):
        return {
            "url": url,
            "http_status": status,
            "state": "missing_runtime_dispatch",
            "evidence": "daemon /health JSON did not include runtime_dispatch",
        }

    daemon_pid = payload.get("daemon_pid")
    daemon_pid_text = str(daemon_pid) if daemon_pid not in {None, ""} else ""
    if daemon_pid_text and observed_pids and daemon_pid_text not in observed_pids:
        return {
            "url": url,
            "http_status": status,
            "state": "daemon_pid_mismatch",
            "daemon_pid": daemon_pid_text,
            "observed_pids": sorted(observed_pids),
            "evidence": "daemon /health parent PID did not match observed daemon PID",
        }
    if payload.get("daemon_process_alive") is False:
        return {
            "url": url,
            "http_status": status,
            "state": "daemon_parent_not_alive",
            "daemon_pid": daemon_pid_text,
            "evidence": "daemon /health reports its parent daemon process is gone",
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
        "daemon_pid": daemon_pid_text,
        "daemon_process_alive": payload.get("daemon_process_alive"),
        "health_process_pid": payload.get("health_process_pid"),
        "evidence": "daemon /health returned non-secret runtime_dispatch block",
    }


def _daemon_runtime_dispatch_file_self_report(
    state_root: Path,
    *,
    observed_pids: set[str],
    observed_pid_sources: dict[str, str] | None = None,
    now: datetime,
    max_age_hours: float = DAEMON_RUNTIME_DISPATCH_SELF_REPORT_MAX_AGE_HOURS,
) -> dict[str, Any]:
    path = state_root / "ops" / "daemon_runtime_dispatch_self_report.json"
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "state": "missing",
        "max_age_hours": max_age_hours,
        "evidence": "daemon runtime-dispatch self-report missing",
    }
    payload = _read_json(path)
    if not payload:
        return result
    result["schema_version"] = str(payload.get("schema_version") or "")
    if result["schema_version"] != DAEMON_RUNTIME_DISPATCH_SELF_REPORT_SCHEMA_VERSION:
        result["state"] = "schema_invalid"
        result["evidence"] = "daemon runtime-dispatch self-report schema invalid"
        return result
    pid = str(payload.get("pid") or "")
    result["pid"] = pid
    if not pid or pid not in observed_pids:
        result["state"] = "pid_not_observed"
        result["observed_pids"] = sorted(observed_pids)
        result["evidence"] = "daemon self-report pid does not match observed daemon process"
        return result
    if observed_pid_sources:
        result["pid_source"] = observed_pid_sources.get(pid, "observed_process")
    updated_at = str(payload.get("updated_at") or "")
    result["updated_at"] = updated_at
    parsed = _parse_iso_utc(updated_at)
    if parsed is None:
        result["state"] = "timestamp_invalid"
        result["evidence"] = "daemon runtime-dispatch self-report timestamp invalid"
        return result
    age_hours = round((now - parsed).total_seconds() / 3600, 3)
    result["age_hours"] = age_hours
    if age_hours > max_age_hours:
        result["state"] = "stale"
        result["evidence"] = "daemon runtime-dispatch self-report is stale"
        return result
    runtime_dispatch = payload.get("runtime_dispatch")
    if not isinstance(runtime_dispatch, dict):
        result["state"] = "missing_runtime_dispatch"
        result["evidence"] = "daemon self-report missing runtime_dispatch"
        return result

    enabled = runtime_dispatch.get("spine_dispatch_enabled")
    if enabled is True:
        state = "spine_enabled_self_report"
    elif enabled is False:
        state = "legacy_self_report"
    else:
        state = "ambiguous_runtime_dispatch"
    result.update({
        "state": state,
        "runtime_dispatch": {
            "spine_dispatch_enabled": enabled,
            "dispatch_mode": runtime_dispatch.get("dispatch_mode"),
            "env_key_present": runtime_dispatch.get("env_key_present"),
            "source": runtime_dispatch.get("source"),
        },
        "source": str(payload.get("source") or ""),
        "evidence": "fresh pid-bound daemon runtime-dispatch self-report",
    })
    return result


def _daemon_pid_file_state(state_root: Path) -> dict[str, Any]:
    path = state_root / "daemon.pid"
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "state": "missing",
        "evidence": "daemon pid file missing",
    }
    try:
        raw_pid = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return result
    except OSError as exc:
        result["state"] = "unreadable"
        result["evidence"] = f"daemon pid file unreadable: {exc}"
        return result
    pid = raw_pid.splitlines()[0].strip() if raw_pid else ""
    result["pid"] = pid
    if not pid:
        result["state"] = "empty"
        result["evidence"] = "daemon pid file is empty"
        return result
    if not pid.isdigit():
        result["state"] = "invalid"
        result["evidence"] = "daemon pid file is not numeric"
        return result
    result["state"] = "present"
    result["evidence"] = "daemon pid file declares child runtime pid"
    return result


def _tmux_sessions(run_probes: bool) -> list[str]:
    if not run_probes:
        return []
    rc, out = _run(["tmux", "ls"], timeout=4)
    if rc != 0:
        return []
    return [line.split(":", 1)[0] for line in out.splitlines() if ":" in line]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_latest_jsonl(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _receipt_timestamp(payload: dict[str, Any]) -> str:
    for key in ("ts", "timestamp", "created_at", "verified_at", "updated_at"):
        value = str(payload.get(key) or "")
        if value:
            return value
    proof = payload.get("proof")
    if isinstance(proof, dict):
        return str(proof.get("verified_at") or "")
    return ""


def _receipt_age_hours(payload: dict[str, Any]) -> float | None:
    return _age_hours(_receipt_timestamp(payload))


def _latest_hot_contact_send_receipt(root: Path) -> dict[str, Any]:
    if not root.exists():
        return {}
    matches: list[tuple[str, Path, dict[str, Any]]] = []
    for path in root.glob("*.json"):
        payload = _read_json(path)
        tier = str(payload.get("contact_evidence_tier") or payload.get("ack_tier") or "")
        if tier not in NATS_OPERATOR_HOT_CONTACT_ACK_TIERS:
            continue
        ts = _receipt_timestamp(payload) or _iso_mtime(path)
        if not ts:
            continue
        enriched = dict(payload)
        enriched["_path"] = str(path)
        enriched["_source"] = "reports/a2a/send_receipts"
        enriched["_timestamp"] = ts
        matches.append((ts, path, enriched))
    if not matches:
        return {}
    return sorted(matches, key=lambda item: item[0], reverse=True)[0][2]


def _latest_packet_receipt(root: Path, packet_id: str) -> dict[str, Any]:
    if not packet_id or not root.exists():
        return {"state": "missing"}
    matches: list[tuple[str, Path, dict[str, Any]]] = []
    for path in root.glob("*.json"):
        payload = _read_json(path)
        if str(payload.get("packet_id") or "") != packet_id:
            continue
        ts = _receipt_timestamp(payload) or _iso_mtime(path)
        matches.append((ts, path, payload))
    if not matches:
        return {"state": "missing"}
    ts, path, payload = sorted(matches, key=lambda item: item[0], reverse=True)[0]
    nested = (
        payload.get("domain_receipt_payload")
        if isinstance(payload.get("domain_receipt_payload"), dict)
        else {}
    )
    return {
        "state": "found",
        "path": str(path),
        "timestamp": ts,
        "age_hours": _age_hours(ts),
        "status": str(payload.get("status") or ""),
        "contact_evidence_tier": str(payload.get("contact_evidence_tier") or ""),
        "reply_evidence_tier": str(payload.get("reply_evidence_tier") or ""),
        "domain_receipt_claim": bool(payload.get("domain_receipt_claim")),
        "semantic_reply_claim": bool(
            payload.get("semantic_reply_claim") or nested.get("semantic_reply_claim")
        ),
        "peer_model_processed_claim": bool(
            payload.get("peer_model_processed_claim")
            or nested.get("peer_model_processed_claim")
        ),
    }


def _nats_ack_tier_state(
    *,
    nats_live_receipt: Path,
    nats_contact_receipts: Path,
    nats_oz_receipts: Path,
    latest_nats_receipt: Path | None,
    latest_send_hot_contact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_receipt = _read_json(nats_live_receipt)
    contact_receipt = _read_latest_jsonl(nats_contact_receipts)
    oz_receipt = _read_latest_jsonl(nats_oz_receipts)
    canonical_receipt = _read_json(latest_nats_receipt) if latest_nats_receipt else {}

    hot_candidates: list[dict[str, Any]] = []
    legacy_ack_tier = str(contact_receipt.get("ack_tier") or "")
    legacy_ack_age = _receipt_age_hours(contact_receipt)
    if legacy_ack_tier and legacy_ack_age is not None:
        hot_candidates.append({
            "path": str(nats_contact_receipts),
            "exists": nats_contact_receipts.exists(),
            "ack_tier": legacy_ack_tier,
            "verdict": str(contact_receipt.get("verdict") or ""),
            "agent_uid": str(contact_receipt.get("agent_uid") or ""),
            "packet_id": str(contact_receipt.get("packet_id") or ""),
            "source": "nats_contact_receipts.jsonl",
            "ts": _receipt_timestamp(contact_receipt),
            "age_hours": legacy_ack_age,
            "fresh": (
                legacy_ack_tier in NATS_OPERATOR_HOT_CONTACT_ACK_TIERS
                and legacy_ack_age <= NATS_HOT_CONTACT_MAX_AGE_HOURS
            ),
        })
    send_contact = latest_send_hot_contact or {}
    send_ack_tier = str(send_contact.get("contact_evidence_tier") or send_contact.get("ack_tier") or "")
    send_ack_age = _receipt_age_hours(send_contact)
    if send_ack_tier and send_ack_age is not None:
        hot_candidates.append({
            "path": str(send_contact.get("_path") or ""),
            "exists": bool(send_contact.get("_path")),
            "ack_tier": send_ack_tier,
            "verdict": str(send_contact.get("status") or ""),
            "agent_uid": str(send_contact.get("target_uid") or send_contact.get("to") or ""),
            "packet_id": str(send_contact.get("packet_id") or ""),
            "source": str(send_contact.get("_source") or "send_receipts"),
            "ts": _receipt_timestamp(send_contact),
            "age_hours": send_ack_age,
            "fresh": (
                send_ack_tier in NATS_OPERATOR_HOT_CONTACT_ACK_TIERS
                and send_ack_age <= NATS_HOT_CONTACT_MAX_AGE_HOURS
            ),
        })
    fresh_hot_candidates = [candidate for candidate in hot_candidates if candidate["fresh"]]
    selected_hot_contact = {}
    if fresh_hot_candidates:
        selected_hot_contact = min(fresh_hot_candidates, key=lambda item: item["age_hours"])
    elif hot_candidates:
        selected_hot_contact = min(hot_candidates, key=lambda item: item["age_hours"])
    hot_ack_fresh = bool(fresh_hot_candidates)
    live_ack_verified = bool(live_receipt.get("ack_verified"))
    live_ack_tier = str(live_receipt.get("ack_tier") or "")
    return {
        "operator_hot_contact_ready": hot_ack_fresh,
        "operator_hot_contact_max_age_hours": NATS_HOT_CONTACT_MAX_AGE_HOURS,
        "live_probe": {
            "path": str(nats_live_receipt),
            "exists": nats_live_receipt.exists(),
            "ack_verified": live_ack_verified,
            "ack_tier": live_ack_tier,
            "ts": _receipt_timestamp(live_receipt),
            "age_hours": _receipt_age_hours(live_receipt),
        },
        "hot_contact": selected_hot_contact,
        "hot_contact_sources": hot_candidates,
        "oz_delivery": {
            "path": str(nats_oz_receipts),
            "exists": nats_oz_receipts.exists(),
            "seq": str(oz_receipt.get("seq") or ""),
            "ts": _receipt_timestamp(oz_receipt),
            "age_hours": _receipt_age_hours(oz_receipt),
        },
        "canonical_receipt": {
            "path": str(latest_nats_receipt) if latest_nats_receipt else "",
            "exists": bool(latest_nats_receipt),
            "schema_version": str(canonical_receipt.get("schema_version") or ""),
            "ts": _receipt_timestamp(canonical_receipt),
            "age_hours": _receipt_age_hours(canonical_receipt),
        },
    }


def _a2a_inbox_bridge_consumer_probe(
    *,
    run_probes: bool,
    nats_port: dict[str, Any],
    stream: str,
    consumer: str,
) -> dict[str, Any]:
    endpoint = "nats://127.0.0.1:4222"
    base: dict[str, Any] = {
        "endpoint": endpoint,
        "stream": stream,
        "consumer": consumer,
        "state": "not_checked",
        "evidence": "consumer probe disabled",
    }
    if not run_probes:
        return base
    if not nats_port.get("listening"):
        return {
            **base,
            "state": "nats_not_listening",
            "evidence": "127.0.0.1:4222 is not listening",
        }
    # Read-only: `nats consumer info <stream> <consumer> --json` inspects state only.
    rc, out = _run(
        [
            "nats",
            "--no-context",
            "--server",
            endpoint,
            "consumer",
            "info",
            stream,
            consumer,
            "--json",
        ],
        timeout=5,
    )
    if rc != 0:
        return {
            **base,
            "state": "consumer_unavailable",
            "exit_code": rc,
            "evidence": out.splitlines()[-1] if out else "nats consumer info failed",
        }
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as exc:
        return {
            **base,
            "state": "consumer_unreadable",
            "evidence": f"nats consumer info returned invalid JSON: {exc}",
        }
    if not isinstance(payload, dict):
        return {
            **base,
            "state": "consumer_unreadable",
            "evidence": "nats consumer info JSON is not an object",
        }
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    delivered = payload.get("delivered") if isinstance(payload.get("delivered"), dict) else {}
    ack_floor = payload.get("ack_floor") if isinstance(payload.get("ack_floor"), dict) else {}
    return {
        **base,
        "state": "consumer_inspectable",
        "evidence": "nats consumer info succeeded",
        "filter_subject": str(config.get("filter_subject") or ""),
        "deliver_policy": str(config.get("deliver_policy") or ""),
        "ack_policy": str(config.get("ack_policy") or ""),
        "num_ack_pending": int(payload.get("num_ack_pending") or 0),
        "num_pending": int(payload.get("num_pending") or 0),
        "num_waiting": int(payload.get("num_waiting") or 0),
        "delivered_last_active": str(delivered.get("last_active") or ""),
        "ack_floor_last_active": str(ack_floor.get("last_active") or ""),
        "reported_at": str(payload.get("ts") or ""),
    }


def _a2a_inbox_bridge_runtime_state(
    *,
    repo_root: Path,
    heartbeat: Path,
    latest_receipt: Path | None,
    agent_uid: str,
    session: str,
    stream: str,
    consumer: str,
    tmux_live: bool,
    process_live: bool,
    run_probes: bool,
    nats_port: dict[str, Any],
) -> dict[str, Any]:
    heartbeat_payload = _read_json(heartbeat)
    heartbeat_ts = _receipt_timestamp(heartbeat_payload) or _iso_mtime(heartbeat)
    heartbeat_age = _age_hours(heartbeat_ts) if heartbeat_ts else None
    heartbeat_fresh = (
        heartbeat_age is not None
        and heartbeat_age <= A2A_INBOX_BRIDGE_HEARTBEAT_MAX_AGE_HOURS
    )
    latest_receipt_payload = _read_json(latest_receipt) if latest_receipt else {}
    latest_receipt_ts = (
        _receipt_timestamp(latest_receipt_payload)
        or (_iso_mtime(latest_receipt) if latest_receipt else "")
    )
    latest_receipt_age = _age_hours(latest_receipt_ts) if latest_receipt_ts else None
    packet_id = str(latest_receipt_payload.get("packet_id") or "")
    contact_tier = str(latest_receipt_payload.get("contact_evidence_tier") or "")
    bridge_status = str(latest_receipt_payload.get("status") or "")
    send_receipt = _latest_packet_receipt(
        repo_root / "reports" / "a2a" / "send_receipts",
        packet_id,
    )
    reply_capture_receipt = _latest_packet_receipt(
        repo_root / "reports" / "a2a" / "reply_receipts",
        packet_id,
    )
    domain_reply_receipt = _latest_packet_receipt(
        repo_root / "reports" / "a2a" / "domain_reply_receipts",
        packet_id,
    )
    domain_receipt_claim = bool(
        reply_capture_receipt.get("domain_receipt_claim")
        or domain_reply_receipt.get("domain_receipt_claim")
    )
    semantic_reply_claim = bool(
        latest_receipt_payload.get("semantic_reply_claim")
        or reply_capture_receipt.get("semantic_reply_claim")
        or domain_reply_receipt.get("semantic_reply_claim")
    )
    peer_model_processed_claim = bool(
        latest_receipt_payload.get("peer_model_processed_claim")
        or reply_capture_receipt.get("peer_model_processed_claim")
        or domain_reply_receipt.get("peer_model_processed_claim")
    )
    handler_ack_claim = contact_tier == "HANDLER_ACKED" or bridge_status in {
        "DELIVERED_AND_ACKED",
        "HANDLER_ACKED",
    }
    domain_receipt_state = (
        "domain_receipted"
        if domain_receipt_claim
        else "not_domain_receipted"
        if reply_capture_receipt.get("state") == "found"
        or domain_reply_receipt.get("state") == "found"
        else "missing"
    )
    semantic_reply_state = "claimed" if semantic_reply_claim else "missing"
    peer_model_state = "processed" if peer_model_processed_claim else "missing"
    completed_state = (
        "completed"
        if domain_receipt_claim and semantic_reply_claim and peer_model_processed_claim
        else "incomplete"
    )
    runtime_script = repo_root / "scripts" / "runtime" / "a2a_inbox_bridge.py"
    start_script = repo_root / "scripts" / "start_a2a_inbox_bridge_tmux.sh"
    status_script = repo_root / "scripts" / "status_a2a_inbox_bridge_tmux.sh"
    stop_script = repo_root / "scripts" / "stop_a2a_inbox_bridge_tmux.sh"
    return {
        "agent_uid": agent_uid,
        "session": session,
        "stream": stream,
        "consumer": consumer,
        "process_live": process_live,
        "tmux_session_live": tmux_live,
        "runtime_script_exists": runtime_script.exists(),
        "start_script_exists": start_script.exists(),
        "status_script_exists": status_script.exists(),
        "stop_script_exists": stop_script.exists(),
        "heartbeat_path": str(heartbeat),
        "heartbeat_exists": heartbeat.exists(),
        "heartbeat_status": str(heartbeat_payload.get("status") or ""),
        "heartbeat_timestamp": heartbeat_ts,
        "heartbeat_age_hours": heartbeat_age,
        "heartbeat_max_age_hours": A2A_INBOX_BRIDGE_HEARTBEAT_MAX_AGE_HOURS,
        "heartbeat_fresh": heartbeat_fresh,
        "latest_receipt": str(latest_receipt) if latest_receipt else "",
        "latest_receipt_timestamp": latest_receipt_ts,
        "latest_receipt_age_hours": latest_receipt_age,
        "latest_packet_id": packet_id,
        "latest_contact_evidence_tier": contact_tier,
        "consumer_probe": _a2a_inbox_bridge_consumer_probe(
            run_probes=run_probes,
            nats_port=nats_port,
            stream=stream,
            consumer=consumer,
        ),
        "bridge_kind": "filesystem_delivery_handler",
        "semantic_reply_claim": semantic_reply_claim,
        "peer_model_processed_claim": peer_model_processed_claim,
        "a2a_lifecycle": {
            "packet_id": packet_id,
            "sent": (
                "send_receipt_found"
                if send_receipt.get("state") == "found"
                else "missing"
            ),
            "handler_ack": "handler_acked" if handler_ack_claim else "missing",
            "handler_ack_tier": contact_tier,
            "delivery_status": bridge_status,
            "delivery_age_hours": latest_receipt_age,
            "domain_receipt": domain_receipt_state,
            "semantic_reply": semantic_reply_state,
            "peer_model": peer_model_state,
            "completed": completed_state,
            "send_receipt": send_receipt,
            "reply_capture_receipt": reply_capture_receipt,
            "domain_reply_receipt": domain_reply_receipt,
        },
    }


def _dharma_launch_dispatch(repo_root: Path) -> dict[str, Any]:
    """Read daemon launch dispatch mode without dumping process environments."""
    candidates = [
        Path.home() / "Library" / "LaunchAgents" / "com.dharma.swarm.plist",
        repo_root / "com.dharma.swarm.plist",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open("rb") as handle:
                data = plistlib.load(handle)
        except (OSError, plistlib.InvalidFileException) as exc:
            return {
                "path": str(path),
                "state": "launch_spec_unreadable",
                "evidence": f"unable to parse launch plist: {exc}",
            }
        args = data.get("ProgramArguments") or []
        env = data.get("EnvironmentVariables") or {}
        command = " ".join(str(arg) for arg in args)
        env_value = str(env.get("DHARMA_SPINE_DISPATCH", ""))
        command_mentions_flag = "DHARMA_SPINE_DISPATCH" in command
        spine_enabled = env_value == "1" or "DHARMA_SPINE_DISPATCH=1" in command
        repo_module_invocation = _launch_uses_repo_module(command, repo_root)
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
        return {
            "path": str(path),
            "state": state,
            "evidence": evidence,
            "env_declares_spine": env_value == "1",
            "command_mentions_spine": command_mentions_flag,
            "repo_module_invocation": repo_module_invocation,
            "ambient_dgc_invocation": ambient_dgc_invocation,
        }
    return {
        "path": "",
        "state": "launch_spec_missing",
        "evidence": "no com.dharma.swarm.plist launch spec found",
    }


def _cron_launch_dispatch(repo_root: Path) -> dict[str, Any]:
    """Read cron daemon launch dispatch mode without dumping process environments."""
    candidates = [
        Path.home() / "Library" / "LaunchAgents" / "com.dharma.cron-daemon.plist",
        repo_root / "scripts" / "com.dharma.cron-daemon.plist",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open("rb") as handle:
                data = plistlib.load(handle)
        except (OSError, plistlib.InvalidFileException) as exc:
            return {
                "path": str(path),
                "state": "cron_launch_spec_unreadable",
                "evidence": f"unable to parse cron launch plist: {exc}",
            }
        args = data.get("ProgramArguments") or []
        env = data.get("EnvironmentVariables") or {}
        command = " ".join(str(arg) for arg in args)
        env_pythonpath = str(env.get("PYTHONPATH", ""))
        repo_module_invocation = _launch_uses_repo_cli(command, repo_root, "cron daemon")
        ambient_dgc_invocation = _launch_uses_ambient_dgc_cli(command, "cron daemon")
        if repo_module_invocation:
            state = "repo_pinned_cron_launch_spec"
            evidence = "cron launch spec invokes repo-pinned dharma_swarm.dgc_cli module"
        elif ambient_dgc_invocation:
            state = "ambient_dgc_cron_launch_spec"
            evidence = (
                "cron launch spec invokes ambient dgc console script instead of the "
                "repo-pinned module"
            )
        elif "-m dharma_swarm.dgc_cli cron daemon" in command:
            state = "unblessed_cron_launch_spec"
            evidence = (
                "cron launch spec uses dharma_swarm.dgc_cli but is not pinned to "
                "this checkout"
            )
        else:
            state = "legacy_default_cron_launch_spec"
            evidence = "cron launch spec does not invoke dharma_swarm.dgc_cli"
        return {
            "path": str(path),
            "state": state,
            "evidence": evidence,
            "repo_module_invocation": repo_module_invocation,
            "ambient_dgc_invocation": ambient_dgc_invocation,
            "env_pythonpath_pinned": env_pythonpath in {str(repo_root), "."},
        }
    return {
        "path": "",
        "state": "cron_launch_spec_missing",
        "evidence": "no com.dharma.cron-daemon.plist launch spec found",
    }


def _latest_path(root: Path, pattern: str) -> Path | None:
    if not root.exists():
        return None
    paths = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return paths[0] if paths else None


def _count_files(root: Path, pattern: str) -> int:
    if not root.exists():
        return 0
    try:
        return sum(1 for path in root.glob(pattern) if path.is_file())
    except OSError:
        return 0


def _freshest_existing(paths: list[Path | None]) -> Path | None:
    existing = [path for path in paths if path and path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def _parse_iso_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _runtime_db_path(state_root: Path) -> Path:
    env_path = str(os.environ.get("DHARMA_RUNTIME_DB") or "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return state_root / "state" / "runtime.db"


def _table_exists(db: sqlite3.Connection, table: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _runtime_truth_clean_epoch_path(state_root: Path) -> Path:
    return state_root / "state" / RUNTIME_TRUTH_CLEAN_EPOCH_FILENAME


def _runtime_truth_clean_epoch_state(state_root: Path) -> dict[str, Any]:
    """Read the append-only runtime truth clean-epoch marker."""
    path = _runtime_truth_clean_epoch_path(state_root)
    db_path = _runtime_db_path(state_root)
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "enabled": False,
        "valid": False,
        "receipt_verified": False,
        "receipt_id": "",
        "receipt_type": "",
        "since_created_at": "",
        "created_at": "",
        "reason": "",
        "historical_dirt_policy": "",
        "scope_mode": "all",
        "evidence": "runtime truth clean epoch file not found",
    }
    if not path.exists():
        return result

    payload = _read_json(path)
    if not payload:
        result["evidence"] = "runtime truth clean epoch file is unreadable or empty"
        return result

    since_created_at = str(payload.get("since_created_at") or "").strip()
    receipt_id = str(payload.get("receipt_id") or "").strip()
    result.update(
        receipt_id=receipt_id,
        since_created_at=since_created_at,
        created_at=str(payload.get("created_at") or ""),
        reason=str(payload.get("reason") or ""),
        historical_dirt_policy=str(payload.get("historical_dirt_policy") or ""),
        scope_mode="since_created_at" if since_created_at else "all",
    )
    if _parse_iso_utc(since_created_at) is None:
        result["evidence"] = (
            "runtime truth clean epoch since_created_at is missing or invalid"
        )
        return result
    result["valid"] = True

    if not receipt_id:
        result["evidence"] = "runtime truth clean epoch receipt_id is missing"
        return result
    if not db_path.exists():
        result["evidence"] = (
            "runtime truth clean epoch receipt cannot be verified; runtime DB missing"
        )
        return result

    try:
        uri = f"{db_path.resolve().as_uri()}?mode=ro"
        db = sqlite3.connect(uri, uri=True)
        db.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        result["evidence"] = (
            f"runtime truth clean epoch receipt cannot be verified: {exc}"
        )
        return result

    try:
        if not _table_exists(db, "runtime_receipts"):
            result["evidence"] = (
                "runtime truth clean epoch receipt cannot be verified; "
                "runtime_receipts table missing"
            )
            return result
        row = db.execute(
            """
            SELECT receipt_id, receipt_type, status, payload_json, created_at
            FROM runtime_receipts
            WHERE receipt_id = ?
            """,
            (receipt_id,),
        ).fetchone()
        if row is None:
            result["evidence"] = (
                "runtime truth clean epoch receipt is missing from runtime DB"
            )
            return result
        receipt_type = str(row["receipt_type"] or "")
        status = str(row["status"] or "")
        receipt_payload = json.loads(str(row["payload_json"] or "{}"))
        receipt_since = str(receipt_payload.get("since_created_at") or "").strip()
        result["receipt_type"] = receipt_type
        result["receipt_created_at"] = str(row["created_at"] or "")
        if receipt_type != "runtime_truth_clean_epoch":
            result["evidence"] = (
                "runtime truth clean epoch receipt has unexpected type "
                f"{receipt_type or '<blank>'}"
            )
            return result
        if status not in {"active", "completed"}:
            result["evidence"] = (
                "runtime truth clean epoch receipt has unexpected status "
                f"{status or '<blank>'}"
            )
            return result
        if receipt_since != since_created_at:
            result["evidence"] = (
                "runtime truth clean epoch receipt boundary does not match file"
            )
            return result
        result["receipt_verified"] = True
        result["enabled"] = True
        result["evidence"] = (
            "active-head runtime truth is scoped to append-only clean epoch receipt"
        )
        return result
    except (json.JSONDecodeError, sqlite3.Error) as exc:
        result["evidence"] = (
            f"runtime truth clean epoch receipt verification failed: {exc}"
        )
        return result
    finally:
        db.close()


def _runtime_receipt_active_head_state(
    state_root: Path,
    *,
    since_created_at: str = "",
    windows_minutes: tuple[int, ...] = RUNTIME_RECEIPT_HEAD_WINDOWS_MINUTES,
    max_age_hours: float = RUNTIME_RECEIPT_HEAD_MAX_AGE_HOURS,
) -> dict[str, Any]:
    """Read the canonical runtime DB head without mutating it."""
    db_path = _runtime_db_path(state_root)
    clean_since_created_at = str(since_created_at or "").strip()
    result: dict[str, Any] = {
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "readable": False,
        "table_exists": False,
        "scope_mode": "since_created_at" if clean_since_created_at else "all",
        "scope_since_created_at": clean_since_created_at,
        "latest_created_at": "",
        "latest_age_hours": None,
        "latest_max_age_hours": max_age_hours,
        "latest_fresh": None,
        "unscoped_runtime_receipts_total": 0,
        "runtime_receipts_total": 0,
        "active_head_side_effect_key_clean": None,
        "windows": [],
        "evidence": "",
    }
    clean_since_dt = None
    if clean_since_created_at:
        clean_since_dt = _parse_iso_utc(clean_since_created_at)
        if clean_since_dt is None:
            result["active_head_side_effect_key_clean"] = False
            result["evidence"] = "active-head clean epoch since_created_at is invalid"
            return result
    if not db_path.exists():
        result["evidence"] = "runtime DB not found"
        return result

    try:
        uri = f"{db_path.resolve().as_uri()}?mode=ro"
        db = sqlite3.connect(uri, uri=True)
        db.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        result["evidence"] = f"runtime DB unreadable: {exc}"
        return result

    try:
        result["readable"] = True
        result["table_exists"] = _table_exists(db, "runtime_receipts")
        if not result["table_exists"]:
            result["evidence"] = "runtime_receipts table not found"
            return result

        unscoped_total = int(
            db.execute("SELECT COUNT(*) FROM runtime_receipts").fetchone()[0]
        )
        if clean_since_created_at:
            scope_where = "created_at >= ?"
            scope_params = (clean_since_created_at,)
        else:
            scope_where = "1=1"
            scope_params = ()
        total = int(
            db.execute(
                f"SELECT COUNT(*) FROM runtime_receipts WHERE {scope_where}",
                scope_params,
            ).fetchone()[0]
        )
        latest_created_at = str(
            db.execute(
                f"SELECT MAX(created_at) FROM runtime_receipts WHERE {scope_where}",
                scope_params,
            ).fetchone()[0]
            or ""
        )
        result["unscoped_runtime_receipts_total"] = unscoped_total
        result["runtime_receipts_total"] = total
        result["latest_created_at"] = latest_created_at
        if not latest_created_at:
            result["active_head_side_effect_key_clean"] = False
            result["evidence"] = (
                "runtime_receipts selected active-head scope is empty"
                if clean_since_created_at
                else "runtime_receipts table is empty"
            )
            return result

        anchor = _parse_iso_utc(latest_created_at)
        if anchor is None:
            result["active_head_side_effect_key_clean"] = False
            result["evidence"] = "latest runtime_receipts.created_at is unparseable"
            return result
        latest_age_hours = round((datetime.now(UTC) - anchor).total_seconds() / 3600, 2)
        result["latest_age_hours"] = latest_age_hours
        result["latest_fresh"] = latest_age_hours <= max_age_hours

        windows: list[dict[str, Any]] = []
        for minutes in windows_minutes:
            cutoff_dt = anchor - timedelta(minutes=max(0, minutes))
            if clean_since_dt is not None:
                cutoff_dt = max(cutoff_dt, clean_since_dt)
            cutoff = cutoff_dt.isoformat()
            window_total = int(
                db.execute(
                    "SELECT COUNT(*) FROM runtime_receipts WHERE created_at >= ?",
                    (cutoff,),
                ).fetchone()[0]
            )
            missing_side_effect_key = int(
                db.execute(
                    """
                    SELECT COUNT(*) FROM runtime_receipts
                    WHERE created_at >= ?
                      AND (side_effect_key IS NULL OR side_effect_key = '')
                    """,
                    (cutoff,),
                ).fetchone()[0]
            )
            windows.append(
                {
                    "window_minutes": minutes,
                    "anchor_created_at": latest_created_at,
                    "cutoff_created_at": cutoff,
                    "scope_since_created_at": clean_since_created_at,
                    "total": window_total,
                    "missing_side_effect_key": missing_side_effect_key,
                    "missing_side_effect_key_percent": (
                        round((missing_side_effect_key / window_total) * 100, 2)
                        if window_total
                        else 0.0
                    ),
                }
            )
        result["windows"] = windows
        dirty_windows = [
            row
            for row in windows
            if int(row.get("total", 0)) > 0
            and int(row.get("missing_side_effect_key", 0)) > 0
        ]
        result["active_head_side_effect_key_clean"] = not dirty_windows
        if dirty_windows:
            result["evidence"] = (
                "recent runtime receipt head contains blank side_effect_key receipts"
            )
        elif result["latest_fresh"] is False:
            result["evidence"] = "latest runtime receipt head is stale"
        else:
            result["evidence"] = (
                "recent runtime receipt head has complete side_effect_key coverage"
            )
        return result
    except sqlite3.Error as exc:
        result["active_head_side_effect_key_clean"] = None
        result["evidence"] = f"runtime_receipts query failed: {exc}"
        return result
    finally:
        db.close()


def _runtime_receipt_since_boot_state(
    state_root: Path,
    process_source_state: dict[str, Any],
) -> dict[str, Any]:
    """Read whether the current daemon boot created blank major receipts."""
    db_path = _runtime_db_path(state_root)
    result: dict[str, Any] = {
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "readable": False,
        "table_exists": False,
        "process_started_at": "",
        "major_receipt_types": list(RUNTIME_RECEIPT_SINCE_BOOT_MAJOR_TYPES),
        "major_since_boot_total": 0,
        "missing_side_effect_key": 0,
        "missing_idempotency_key": 0,
        "since_boot_major_identity_clean": None,
        "gap_sample": [],
        "evidence": "",
    }
    starts = [
        _parse_iso_utc(str(row.get("started_at") or ""))
        for row in (process_source_state.get("process_starts") or [])
        if isinstance(row, dict)
    ]
    parsed_starts = [started for started in starts if started is not None]
    if not parsed_starts:
        result["evidence"] = "daemon process start time not available"
        return result
    started_at = min(parsed_starts)
    started_text = started_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result["process_started_at"] = started_text

    if not db_path.exists():
        result["evidence"] = "runtime DB not found"
        return result

    try:
        uri = f"{db_path.resolve().as_uri()}?mode=ro"
        db = sqlite3.connect(uri, uri=True)
        db.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        result["evidence"] = f"runtime DB unreadable: {exc}"
        return result

    try:
        result["readable"] = True
        result["table_exists"] = _table_exists(db, "runtime_receipts")
        if not result["table_exists"]:
            result["evidence"] = "runtime_receipts table not found"
            return result
        columns = {
            str(row[1])
            for row in db.execute("PRAGMA table_info(runtime_receipts)").fetchall()
        }
        required_columns = {"receipt_type", "created_at", "idempotency_key", "side_effect_key"}
        missing_columns = sorted(required_columns - columns)
        if missing_columns:
            result["evidence"] = (
                "runtime_receipts table missing columns: " + ",".join(missing_columns)
            )
            return result

        placeholders = ", ".join("?" for _ in RUNTIME_RECEIPT_SINCE_BOOT_MAJOR_TYPES)
        params = (started_text, *RUNTIME_RECEIPT_SINCE_BOOT_MAJOR_TYPES)
        type_filter = f"receipt_type IN ({placeholders})"
        total = int(
            db.execute(
                f"""
                SELECT COUNT(*) FROM runtime_receipts
                WHERE created_at >= ? AND {type_filter}
                """,
                params,
            ).fetchone()[0]
        )
        missing_side = int(
            db.execute(
                f"""
                SELECT COUNT(*) FROM runtime_receipts
                WHERE created_at >= ? AND {type_filter}
                  AND (side_effect_key IS NULL OR side_effect_key = '')
                """,
                params,
            ).fetchone()[0]
        )
        missing_idem = int(
            db.execute(
                f"""
                SELECT COUNT(*) FROM runtime_receipts
                WHERE created_at >= ? AND {type_filter}
                  AND (idempotency_key IS NULL OR idempotency_key = '')
                """,
                params,
            ).fetchone()[0]
        )
        sample_rows = db.execute(
            f"""
            SELECT receipt_id, receipt_type, status, run_id, task_id, agent_id,
                   created_at, idempotency_key, side_effect_key
            FROM runtime_receipts
            WHERE created_at >= ? AND {type_filter}
              AND (
                side_effect_key IS NULL OR side_effect_key = ''
                OR idempotency_key IS NULL OR idempotency_key = ''
              )
            ORDER BY created_at DESC
            LIMIT 5
            """,
            params,
        ).fetchall()
        result.update(
            major_since_boot_total=total,
            missing_side_effect_key=missing_side,
            missing_idempotency_key=missing_idem,
            since_boot_major_identity_clean=missing_side == 0 and missing_idem == 0,
            gap_sample=[
                {
                    "receipt_id": str(row["receipt_id"] or ""),
                    "receipt_type": str(row["receipt_type"] or ""),
                    "status": str(row["status"] or ""),
                    "run_id": str(row["run_id"] or ""),
                    "task_id": str(row["task_id"] or ""),
                    "agent_id": str(row["agent_id"] or ""),
                    "created_at": str(row["created_at"] or ""),
                    "missing_idempotency_key": not bool(
                        str(row["idempotency_key"] or "").strip()
                    ),
                    "missing_side_effect_key": not bool(
                        str(row["side_effect_key"] or "").strip()
                    ),
                }
                for row in sample_rows
            ],
        )
        if missing_side or missing_idem:
            result["evidence"] = "current daemon boot created blank major receipts"
        elif total:
            result["evidence"] = "current daemon boot major receipts have required keys"
        else:
            result["evidence"] = "current daemon boot has not created major receipts"
        return result
    except sqlite3.Error as exc:
        result["evidence"] = f"runtime_receipts since-boot query failed: {exc}"
        return result
    finally:
        db.close()


def _active_head_gap_producer_groups_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    runtime_receipts = (
        report.get("runtime_receipts")
        if isinstance(report.get("runtime_receipts"), dict)
        else {}
    )
    windows = runtime_receipts.get("recent_side_effect_key_gap_windows") or []
    if not isinstance(windows, list):
        return []
    for window in windows:
        if not isinstance(window, dict):
            continue
        if int(window.get("missing_side_effect_key") or 0) <= 0:
            continue
        groups = window.get("top_gap_producer_groups") or []
        if not isinstance(groups, list):
            return []
        compact: list[dict[str, Any]] = []
        for group in groups[:3]:
            if not isinstance(group, dict):
                continue
            compact.append(
                {
                    "window_minutes": window.get("window_minutes"),
                    "receipt_type": group.get("receipt_type"),
                    "producer_source": group.get("producer_source"),
                    "producer_failure_code": group.get("producer_failure_code"),
                    "topology": group.get("topology"),
                    "identifier_shape": group.get("identifier_shape"),
                    "missing_side_effect_key": group.get("missing_side_effect_key"),
                    "sample_agent_id": group.get("sample_agent_id"),
                    "sample_task_id": group.get("sample_task_id"),
                }
            )
        return compact
    return []


def _provider_model_unproven_producer_groups_from_report(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    major = (
        report.get("major_task_receipts")
        if isinstance(report.get("major_task_receipts"), dict)
        else {}
    )
    groups = major.get("latest_provider_model_unproven_producer_groups") or []
    if not isinstance(groups, list):
        return []
    compact: list[dict[str, Any]] = []
    for group in groups[:5]:
        if not isinstance(group, dict):
            continue
        compact.append(
            {
                "receipt_type": group.get("receipt_type"),
                "provider_model_payload_class": group.get("provider_model_payload_class"),
                "provider_model_truth_source": group.get("provider_model_truth_source"),
                "producer_source": group.get("producer_source"),
                "producer_failure_code": group.get("producer_failure_code"),
                "topology": group.get("topology"),
                "missing_provider_model_provenance": group.get(
                    "missing_provider_model_provenance"
                ),
                "sample_agent_id": group.get("sample_agent_id"),
                "sample_task_id": group.get("sample_task_id"),
            }
        )
    return compact


def _field_gap_producer_groups_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    major = (
        report.get("major_task_receipts")
        if isinstance(report.get("major_task_receipts"), dict)
        else {}
    )
    groups = major.get("field_gap_producer_groups") or []
    if not isinstance(groups, list):
        return []
    compact: list[dict[str, Any]] = []
    for group in groups[:5]:
        if not isinstance(group, dict):
            continue
        compact.append(
            {
                "gap_type": group.get("gap_type"),
                "receipt_type": group.get("receipt_type"),
                "producer_source": group.get("producer_source"),
                "producer_failure_code": group.get("producer_failure_code"),
                "topology": group.get("topology"),
                "identifier_shape": group.get("identifier_shape"),
                "missing": group.get("missing"),
                "latest_created_at": group.get("latest_created_at"),
                "freshness_class": group.get("freshness_class"),
                "age_minutes_from_head": group.get("age_minutes_from_head"),
                "recommended_action": group.get("recommended_action"),
                "sample_agent_id": group.get("sample_agent_id"),
                "sample_task_id": group.get("sample_task_id"),
                "sample_run_id": group.get("sample_run_id"),
            }
        )
    return compact


def _runtime_receipt_coverage_state(
    state_root: Path,
    clean_epoch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize the canonical runtime receipt coverage report for live ops."""
    db_path = _runtime_db_path(state_root)
    epoch = clean_epoch or {}
    scope_since_created_at = (
        str(epoch.get("since_created_at") or "").strip()
        if epoch.get("enabled") is True
        else ""
    )
    result: dict[str, Any] = {
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "coverage_report_available": False,
        "scope_mode": "since_created_at" if scope_since_created_at else "all",
        "scope_since_created_at": scope_since_created_at,
        "active_epoch_enabled": bool(scope_since_created_at),
        "active_epoch_receipt_id": str(epoch.get("receipt_id") or ""),
        "active_epoch_path": str(epoch.get("path") or ""),
        "historical_scope_note": (
            "historical dirty receipts before the clean epoch remain inspectable "
            "and are excluded from active-head readiness"
            if scope_since_created_at
            else ""
        ),
        "runtime_receipts_total": 0,
        "major_task_receipts_total": 0,
        "latest_sample_size": 0,
        "latest_with_provider_payload": 0,
        "latest_with_model_payload": 0,
        "latest_with_provider_model_payload": 0,
        "latest_with_provider_model_provenance": 0,
        "latest_with_provider_model_accounted": 0,
        "latest_provider_model_pending_execution": 0,
        "latest_major_status_breakdown": {},
        "latest_terminal_sample_size": 0,
        "latest_terminal_with_provider_payload": 0,
        "latest_terminal_with_model_payload": 0,
        "latest_terminal_with_provider_model_payload": 0,
        "latest_terminal_with_provider_model_provenance": 0,
        "latest_terminal_with_provider_model_accounted": 0,
        "latest_major_task_receipts_provider_model_percent": None,
        "latest_major_task_receipts_provider_model_provenance_percent": None,
        "latest_major_task_receipts_provider_model_accounted_percent": None,
        "latest_terminal_major_task_receipts_provider_model_percent": None,
        "latest_terminal_major_task_receipts_provider_model_provenance_percent": None,
        "latest_terminal_major_task_receipts_provider_model_accounted_percent": None,
        "provider_model_payload_complete": None,
        "provider_model_provenance_complete": None,
        "provider_model_accounted_complete": None,
        "terminal_provider_model_payload_complete": None,
        "terminal_provider_model_provenance_complete": None,
        "terminal_provider_model_accounted_complete": None,
        "provider_model_latest_complete": None,
        "provider_model_readiness_basis": "unproven",
        "latest_provider_model_payload_class_breakdown": {},
        "latest_terminal_provider_model_payload_class_breakdown": {},
        "latest_provider_model_unproven_producer_groups": [],
        "latest_terminal_provider_model_unproven_producer_groups": [],
        "blockers": [],
        "production_readiness_blockers": [],
        "gate_70_to_75_components": [],
        "active_head_gap_producer_groups": [],
        "field_gap_producer_groups": [],
        "field_gap_summary": {},
        "field_gap_action_queue": [],
        "evidence": "",
    }
    if not db_path.exists():
        result["evidence"] = "runtime DB not found"
        return result

    try:
        repo_root = Path(__file__).resolve().parents[2]
        repo_root_text = str(repo_root)
        if repo_root_text not in sys.path:
            sys.path.insert(0, repo_root_text)
        from scripts.governance.runtime_receipt_coverage_report import build_report

        report = build_report(
            db_path,
            latest_limit=500,
            since_created_at=scope_since_created_at,
        )
    except Exception as exc:
        result["evidence"] = f"runtime receipt coverage report failed: {exc}"
        return result

    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    scope = report.get("scope") if isinstance(report.get("scope"), dict) else {}
    result["scope_mode"] = str(scope.get("mode") or result["scope_mode"])
    result["scope_since_created_at"] = str(
        scope.get("since_created_at") or result["scope_since_created_at"]
    )
    major = (
        report.get("major_task_receipts")
        if isinstance(report.get("major_task_receipts"), dict)
        else {}
    )
    result["runtime_receipts_total"] = int(summary.get("runtime_receipts_total") or 0)
    result["major_task_receipts_total"] = int(summary.get("major_task_receipts_total") or 0)
    result["latest_sample_size"] = int(major.get("latest_sample_size") or 0)
    result["latest_with_provider_payload"] = int(major.get("latest_with_provider_payload") or 0)
    result["latest_with_model_payload"] = int(major.get("latest_with_model_payload") or 0)
    result["latest_with_provider_model_payload"] = int(
        major.get("latest_with_provider_model_payload") or 0
    )
    result["latest_with_provider_model_provenance"] = int(
        major.get("latest_with_provider_model_provenance") or 0
    )
    result["latest_with_provider_model_accounted"] = int(
        major.get("latest_with_provider_model_accounted") or 0
    )
    result["latest_provider_model_pending_execution"] = int(
        major.get("latest_provider_model_pending_execution") or 0
    )
    result["latest_terminal_sample_size"] = int(major.get("latest_terminal_sample_size") or 0)
    result["latest_terminal_with_provider_payload"] = int(
        major.get("latest_terminal_with_provider_payload") or 0
    )
    result["latest_terminal_with_model_payload"] = int(
        major.get("latest_terminal_with_model_payload") or 0
    )
    result["latest_terminal_with_provider_model_payload"] = int(
        major.get("latest_terminal_with_provider_model_payload") or 0
    )
    result["latest_terminal_with_provider_model_provenance"] = int(
        major.get("latest_terminal_with_provider_model_provenance") or 0
    )
    result["latest_terminal_with_provider_model_accounted"] = int(
        major.get("latest_terminal_with_provider_model_accounted") or 0
    )
    status_breakdown = major.get("latest_major_status_breakdown")
    if isinstance(status_breakdown, dict):
        result["latest_major_status_breakdown"] = {
            str(key): int(value or 0) for key, value in status_breakdown.items()
        }
    class_breakdown = major.get("latest_provider_model_payload_class_breakdown")
    if isinstance(class_breakdown, dict):
        result["latest_provider_model_payload_class_breakdown"] = {
            str(key): int(value or 0) for key, value in class_breakdown.items()
        }
    terminal_class_breakdown = major.get(
        "latest_terminal_provider_model_payload_class_breakdown"
    )
    if isinstance(terminal_class_breakdown, dict):
        result["latest_terminal_provider_model_payload_class_breakdown"] = {
            str(key): int(value or 0) for key, value in terminal_class_breakdown.items()
        }
    result["active_head_gap_producer_groups"] = _active_head_gap_producer_groups_from_report(
        report
    )
    result["latest_provider_model_unproven_producer_groups"] = (
        _provider_model_unproven_producer_groups_from_report(report)
    )
    result["field_gap_producer_groups"] = _field_gap_producer_groups_from_report(report)
    field_gap_summary = major.get("field_gap_summary")
    if isinstance(field_gap_summary, dict):
        result["field_gap_summary"] = field_gap_summary
    field_gap_action_queue = major.get("field_gap_action_queue")
    if isinstance(field_gap_action_queue, list):
        result["field_gap_action_queue"] = [
            item for item in field_gap_action_queue if isinstance(item, dict)
        ]
    terminal_groups = major.get("latest_terminal_provider_model_unproven_producer_groups")
    if isinstance(terminal_groups, list):
        result["latest_terminal_provider_model_unproven_producer_groups"] = [
            group for group in terminal_groups[:5] if isinstance(group, dict)
        ]
    percent = summary.get("latest_major_task_receipts_provider_model_percent")
    result["latest_major_task_receipts_provider_model_percent"] = percent
    provenance_percent = summary.get(
        "latest_major_task_receipts_provider_model_provenance_percent"
    )
    result["latest_major_task_receipts_provider_model_provenance_percent"] = (
        provenance_percent
    )
    result["latest_major_task_receipts_provider_model_accounted_percent"] = (
        summary.get("latest_major_task_receipts_provider_model_accounted_percent")
    )
    result["latest_terminal_major_task_receipts_provider_model_percent"] = summary.get(
        "latest_terminal_major_task_receipts_provider_model_percent"
    )
    result["latest_terminal_major_task_receipts_provider_model_provenance_percent"] = (
        summary.get("latest_terminal_major_task_receipts_provider_model_provenance_percent")
    )
    result["latest_terminal_major_task_receipts_provider_model_accounted_percent"] = (
        summary.get("latest_terminal_major_task_receipts_provider_model_accounted_percent")
    )
    payload_complete = summary.get("provider_model_coverage_complete")
    provenance_complete = summary.get("provider_model_provenance_complete")
    accounted_complete = summary.get("provider_model_accounted_complete")
    terminal_payload_complete = summary.get("terminal_provider_model_coverage_complete")
    terminal_provenance_complete = summary.get(
        "terminal_provider_model_provenance_complete"
    )
    terminal_accounted_complete = summary.get(
        "terminal_provider_model_accounted_complete"
    )
    if payload_complete is not None:
        result["provider_model_payload_complete"] = bool(payload_complete)
    if provenance_complete is not None:
        result["provider_model_provenance_complete"] = bool(provenance_complete)
    if accounted_complete is not None:
        result["provider_model_accounted_complete"] = bool(accounted_complete)
    if terminal_payload_complete is not None:
        result["terminal_provider_model_payload_complete"] = bool(
            terminal_payload_complete
        )
    if terminal_provenance_complete is not None:
        result["terminal_provider_model_provenance_complete"] = bool(
            terminal_provenance_complete
        )
    if terminal_accounted_complete is not None:
        result["terminal_provider_model_accounted_complete"] = bool(
            terminal_accounted_complete
        )
    blockers = summary.get("production_readiness_blockers") or []
    if isinstance(blockers, list):
        result["production_readiness_blockers"] = [
            str(blocker) for blocker in blockers if str(blocker)
        ]
    coverage_blockers = summary.get("blockers") or []
    if isinstance(coverage_blockers, list):
        result["blockers"] = [
            str(blocker) for blocker in coverage_blockers if str(blocker)
        ]
    gate_components = summary.get("gate_70_to_75_components") or report.get(
        "gate_70_to_75_components"
    )
    if isinstance(gate_components, list):
        result["gate_70_to_75_components"] = [
            component for component in gate_components if isinstance(component, dict)
        ]
    if report.get("error"):
        result["evidence"] = f"runtime receipt coverage report unavailable: {report['error']}"
        return result

    result["coverage_report_available"] = bool(summary.get("readable"))
    latest_sample_size = result["latest_sample_size"]
    terminal_sample_size = result["latest_terminal_sample_size"]
    all_latest_accounted = bool(
        latest_sample_size and result["provider_model_accounted_complete"] is True
    )
    terminal_latest_accounted = bool(
        terminal_sample_size
        and result["terminal_provider_model_accounted_complete"] is True
    )
    provider_model_complete = all_latest_accounted or terminal_latest_accounted
    result["provider_model_latest_complete"] = provider_model_complete
    if all_latest_accounted:
        result["provider_model_readiness_basis"] = "latest_major_accounted"
        result["evidence"] = (
            "latest major runtime receipts account for provider/model truth"
        )
    elif terminal_latest_accounted:
        result["provider_model_readiness_basis"] = "latest_terminal_accounted"
        result["evidence"] = (
            "latest terminal major runtime receipts account for provider/model truth; "
            "pending receipts remain incomplete"
        )
    elif result["provider_model_payload_complete"] is True:
        result["evidence"] = (
            "latest major runtime receipts carry provider/model payloads without "
            "production provenance"
        )
    else:
        result["evidence"] = "latest major runtime receipts do not all carry provider/model payloads"
    return result


def _daemon_process_source_state(
    repo_root: Path,
    process_rows: list[dict[str, str]],
    process_starts: dict[str, str],
    source_paths: tuple[str, ...] = DAEMON_RUNTIME_SOURCE_PATHS,
) -> dict[str, Any]:
    pids = [
        str(row.get("pid", "")).strip()
        for row in process_rows
        if str(row.get("pid", "")).strip()
    ]
    source_rows: list[dict[str, Any]] = []
    for rel_path in source_paths:
        path = repo_root / rel_path
        if not path.exists():
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        source_rows.append(
            {
                "path": rel_path,
                "mtime": datetime.fromtimestamp(mtime, UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "mtime_epoch": mtime,
            }
        )

    start_rows: list[dict[str, str]] = []
    for pid in pids:
        started_at = str(process_starts.get(pid) or "")
        if started_at:
            start_rows.append({"pid": pid, "started_at": started_at})
    start_probe_errors = _process_start_probe_errors(process_starts)

    result: dict[str, Any] = {
        "state": "no_process" if not pids else "process_start_uninspected",
        "pids": pids,
        "process_starts": start_rows,
        "process_start_probe_errors": start_probe_errors,
        "source_paths": [
            {"path": row["path"], "mtime": row["mtime"]}
            for row in source_rows
        ],
        "source_newer_files": [],
        "evidence": "",
    }
    if not pids:
        result["evidence"] = "process not observed"
        return result
    if not source_rows:
        result["state"] = "source_files_missing"
        result["evidence"] = "runtime source files not found in checkout"
        return result
    if not start_rows:
        if start_probe_errors:
            result["state"] = "process_start_probe_failed"
            result["evidence"] = "process start time probe failed"
        else:
            result["evidence"] = "process start time not inspected"
        return result

    parsed_starts = [
        (row["pid"], parsed)
        for row in start_rows
        if (parsed := _parse_iso_utc(row["started_at"])) is not None
    ]
    if not parsed_starts:
        result["state"] = "process_start_unparseable"
        result["evidence"] = "process start time could not be parsed"
        return result

    newest_source_epoch = max(float(row["mtime_epoch"]) for row in source_rows)
    newest_source = datetime.fromtimestamp(newest_source_epoch, UTC)
    stale_start_times = [
        started_at
        for _pid, started_at in parsed_starts
        if started_at.timestamp() < newest_source_epoch
    ]
    stale_pids = [
        {
            "pid": pid,
            "started_at": started_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        for pid, started_at in parsed_starts
        if started_at in stale_start_times
    ]
    if stale_pids:
        result["state"] = "source_changed_after_process_start"
        result["stale_pids"] = stale_pids
        result["newest_source_mtime"] = (
            newest_source.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        oldest_stale_start = min(stale_start_times)
        result["source_newer_files"] = [
            {"path": row["path"], "mtime": row["mtime"]}
            for row in source_rows
            if float(row["mtime_epoch"]) > oldest_stale_start.timestamp()
        ]
        result["evidence"] = "source changed after process start"
        return result

    result["state"] = "process_started_after_sources"
    result["newest_source_mtime"] = (
        newest_source.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    result["evidence"] = "process started after inspected source files"
    return result


def _required_live_gap_code(
    surface_id: str,
    status: str,
    desired_state: str,
    priority: str,
) -> str:
    if priority != "p0" or desired_state != "live" or status == "live":
        return ""
    surface_token = re.sub(r"[^a-z0-9]+", "_", surface_id.lower()).strip("_")
    status_token = re.sub(r"[^a-z0-9]+", "_", status.lower()).strip("_")
    return f"{surface_token}_{status_token or 'not_live'}"


def _stale_priority_gap_code(surface_id: str, status: str, priority: str) -> str:
    if priority != "p0" or status != "stale":
        return ""
    surface_token = re.sub(r"[^a-z0-9]+", "_", surface_id.lower()).strip("_")
    return f"{surface_token}_stale"


def _unknown_priority_gap_code(surface_id: str, status: str, priority: str) -> str:
    if priority != "p0" or status != "unknown":
        return ""
    surface_token = re.sub(r"[^a-z0-9]+", "_", surface_id.lower()).strip("_")
    return f"{surface_token}_unknown"


def _supervised_surface_gap_code(
    surface_id: str,
    status: str,
    desired_state: str,
) -> str:
    if desired_state != "supervised" or status == "live":
        return ""
    surface_token = re.sub(r"[^a-z0-9]+", "_", surface_id.lower()).strip("_")
    status_token = re.sub(r"[^a-z0-9]+", "_", status.lower()).strip("_")
    return f"{surface_token}_{status_token or 'not_live'}"


def _forge_external_gate_state(repo_root: Path) -> dict[str, Any]:
    status_packet = repo_root / FORGE_REALITY_ARENA_STATUS_PACKET
    raw = _read_json(status_packet)
    policy = _first_dict(
        raw,
        (
            "control_watch_tower_visibility",
            "autonomy_cycle_policy",
        ),
        ("v1_scorecard", "autonomy_cycle_policy"),
    )
    inputs = policy.get("decision_inputs") if isinstance(policy, dict) else {}
    inputs = inputs if isinstance(inputs, dict) else {}
    completion_state = str(
        inputs.get("completion_state")
        or _nested_value(raw, ("control_watch_tower_visibility", "completion_state"))
        or _nested_value(raw, ("v1_scorecard", "completion_state"))
        or ""
    )
    remaining_internal = inputs.get("remaining_internal_packet_count")
    if remaining_internal is None:
        remaining_packets = _nested_value(
            raw,
            ("control_watch_tower_visibility", "remaining_internal_packets"),
        )
        if isinstance(remaining_packets, list):
            remaining_internal = len(remaining_packets)
    external_lease_needed = bool(inputs.get("external_action_lease_needed"))
    decision = str(policy.get("decision") or "") if isinstance(policy, dict) else ""
    external_gated = (
        status_packet.exists()
        and decision == "stop_internal_autonomy_cycles"
        and completion_state == "internal_exhausted_external_gated"
        and remaining_internal == 0
        and external_lease_needed
    )
    return {
        "status_packet": str(status_packet),
        "status_packet_exists": status_packet.exists(),
        "state": "external_gated" if external_gated else "not_external_gated",
        "decision": decision,
        "completion_state": completion_state,
        "remaining_internal_packet_count": remaining_internal,
        "external_action_lease_needed": external_lease_needed,
        "next_packet": str(policy.get("next_packet") or "") if isinstance(policy, dict) else "",
        "reason": str(policy.get("reason") or "") if isinstance(policy, dict) else "",
    }


def _first_dict(raw: dict[str, Any], *paths: tuple[str, ...]) -> dict[str, Any]:
    for path in paths:
        value = _nested_value(raw, path)
        if isinstance(value, dict):
            return value
    return {}


def _nested_value(raw: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = raw
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _path_from_record(raw: object, *, repo_root: Path) -> Path | None:
    value = str(raw or "").strip()
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else repo_root / path


def _latest_holon_prod_verifier_state(repo_root: Path) -> dict[str, Any]:
    receipt_path = _latest_path(
        repo_root / "reports" / "sovereign_holons",
        "verify_holon_harness_prod_*.json",
    )
    raw = _read_json(receipt_path) if receipt_path else {}
    checks = raw.get("checks") if isinstance(raw.get("checks"), dict) else {}
    orchestration_check = (
        checks.get("l4_orchestration_probe_stub")
        if isinstance(checks.get("l4_orchestration_probe_stub"), dict)
        else {}
    )
    return {
        "path": str(receipt_path) if receipt_path else "",
        "exists": bool(receipt_path),
        "overall_pass": raw.get("overall_pass") is True,
        "l4_orchestration_probe_stub_pass": orchestration_check.get("pass") is True,
        "generated_at": str(raw.get("timestamp") or ""),
    }


def _latest_holon_model_responsiveness_state(
    *,
    repo_root: Path,
    agents_root: Path,
    holon_name: str,
) -> dict[str, Any]:
    events = load_holon_session(holon_name, agents_root=agents_root)
    latest_seen: dict[str, Any] = {}
    for event in reversed(events):
        record = event.get("record") if isinstance(event.get("record"), dict) else {}
        if not record:
            continue
        model_probe = (
            record.get("model_probe")
            if isinstance(record.get("model_probe"), dict)
            else {}
        )
        if not model_probe:
            continue
        route_policy = (
            model_probe.get("route_policy")
            if isinstance(model_probe.get("route_policy"), dict)
            else {}
        )
        lease_evidence = (
            route_policy.get("lease_evidence")
            if isinstance(route_policy.get("lease_evidence"), dict)
            else {}
        )
        artifact = record.get("artifact") if isinstance(record.get("artifact"), dict) else {}
        artifact_path = _path_from_record(artifact.get("path"), repo_root=repo_root)
        proof_at = str(event.get("at") or record.get("created_at") or "")
        age_hours = _age_hours(proof_at) if proof_at else None
        latest_seen = {
            "event_seen": True,
            "event_at": proof_at,
            "age_hours": age_hours,
            "max_age_hours": HOLON_L4_MODEL_PROOF_MAX_AGE_HOURS,
            "fresh": (
                age_hours is not None
                and age_hours <= HOLON_L4_MODEL_PROOF_MAX_AGE_HOURS
            ),
            "session_id": str(record.get("session_id") or ""),
            "proof_digest": str(record.get("proof_digest") or ""),
            "artifact_path": str(artifact_path) if artifact_path else "",
            "artifact_exists": bool(artifact_path and artifact_path.exists()),
            "provider_source": str(model_probe.get("provider_source") or ""),
            "provider_type": str(model_probe.get("provider_type") or ""),
            "model": str(model_probe.get("model") or ""),
            "status": str(model_probe.get("status") or ""),
            "attempted": model_probe.get("attempted") is True,
            "responsive": model_probe.get("responsive") is True,
            "reply_digest": str(model_probe.get("reply_digest") or ""),
            "route_policy_decision": str(route_policy.get("decision") or ""),
            "explicit_lease": route_policy.get("explicit_lease") is True,
            "lease_id": str(route_policy.get("model_probe_lease_id") or ""),
            "lease_valid": lease_evidence.get("valid") is True,
            "lease_path": str(lease_evidence.get("path") or ""),
        }
        declared_route = latest_seen["provider_source"] == "declared_identity"
        latest_seen["declared_route"] = declared_route
        latest_seen["model_responsive_proven"] = (
            latest_seen["fresh"]
            and latest_seen["artifact_exists"]
            and latest_seen["attempted"]
            and latest_seen["responsive"]
            and latest_seen["route_policy_decision"] == "allow"
            and latest_seen["explicit_lease"]
            and latest_seen["lease_valid"]
            and declared_route
        )
        if latest_seen["model_responsive_proven"]:
            return latest_seen
    if latest_seen:
        latest_seen["model_responsive_proven"] = False
        return latest_seen
    return {
        "event_seen": False,
        "model_responsive_proven": False,
        "max_age_hours": HOLON_L4_MODEL_PROOF_MAX_AGE_HOURS,
    }


def _latest_holon_supervisor_activation_state(
    *,
    agents_root: Path,
    holon_name: str,
    tmux_sessions: list[str],
) -> dict[str, Any]:
    activation_dir = agents_root / holon_name / "supervisor" / "tmux_live"
    plan_path = activation_dir / "tmux_supervisor_plan.json"
    activation_path = activation_dir / "activation_receipts.jsonl"
    plan = _read_json(plan_path)
    rows = _read_jsonl_rows(activation_path)
    tmux_session = str(plan.get("tmux_session") or "")
    install_receipts = [
        row
        for row in rows
        if row.get("target_kind") == "launch_artifact"
        and row.get("status") == "installed"
    ]
    start_receipts = [
        row
        for row in rows
        if row.get("target_kind") == "launch_start"
    ]
    activated_starts = [
        row
        for row in start_receipts
        if row.get("status") == "activated"
    ]
    latest_install = install_receipts[-1] if install_receipts else {}
    latest_start = start_receipts[-1] if start_receipts else {}
    latest_activated = activated_starts[-1] if activated_starts else {}
    service_state = (
        latest_activated.get("service_state_ref")
        if isinstance(latest_activated.get("service_state_ref"), dict)
        else {}
    )
    tmux_session_live = bool(tmux_session and tmux_session in set(tmux_sessions))
    strict_service_bound = (
        bool(service_state.get("service_alive"))
        and service_state.get("required_new_record_observed") is True
        and service_state.get("required_service_id_matched") is True
        and service_state.get("required_session_id_matched") is True
    )
    configured = bool(plan_path.exists() or activation_path.exists() or rows)
    proof_gaps: list[str] = []
    if configured:
        if not latest_install:
            proof_gaps.append("holon_l4_supervisor_install_receipt_missing")
        if not latest_activated:
            proof_gaps.append("holon_l4_supervisor_activation_missing")
        elif not strict_service_bound:
            proof_gaps.append("holon_l4_supervisor_activation_heartbeat_unbound")
        if tmux_session and not tmux_session_live:
            proof_gaps.append("holon_l4_supervisor_tmux_session_missing")
        elif configured and not tmux_session:
            proof_gaps.append("holon_l4_supervisor_tmux_session_undeclared")
    status = (
        "active"
        if configured and not proof_gaps
        else "partial"
        if configured
        else "not_configured"
    )
    return {
        "configured": configured,
        "status": status,
        "activation_dir": str(activation_dir),
        "plan_path": str(plan_path),
        "activation_path": str(activation_path),
        "tmux_session": tmux_session,
        "tmux_session_live": tmux_session_live,
        "latest_install_receipt_hash": str(latest_install.get("record_hash") or ""),
        "latest_start_receipt_hash": str(latest_start.get("record_hash") or ""),
        "latest_activated_start_receipt_hash": str(latest_activated.get("record_hash") or ""),
        "latest_start_status": str(latest_start.get("status") or ""),
        "latest_start_created_at": str(latest_start.get("created_at") or ""),
        "strict_service_bound": strict_service_bound,
        "service_state_ref": service_state,
        "proof_gaps": proof_gaps,
    }


def _holon_l4_runtime_state(
    repo_root: Path,
    state_root: Path,
    *,
    holon_name: str = HOLON_L4_AGENT_UID,
    tmux_sessions: list[str] | None = None,
) -> dict[str, Any]:
    agents_root = state_root / "agents"
    service_liveness = assess_holon_service_liveness(
        holon_name,
        agents_root=agents_root,
        fresh_after_seconds=HOLON_L4_SERVICE_FRESH_SECONDS,
        service_id="holon-l4-service",
    )
    transport_heartbeat = state_root / "a2a_bus" / "bridge_heartbeats" / f"{holon_name}.json"
    transport_liveness = assess_holon_a2a_transport_liveness(
        holon_name,
        heartbeat_path=transport_heartbeat,
    )
    event = holon_resume_point(holon_name, agents_root=agents_root) or {}
    record = event.get("record") if isinstance(event.get("record"), dict) else {}
    proof_levels = (
        record.get("proof_levels") if isinstance(record.get("proof_levels"), dict) else {}
    )
    artifact = record.get("artifact") if isinstance(record.get("artifact"), dict) else {}
    artifact_path = _path_from_record(artifact.get("path"), repo_root=repo_root)
    artifact_exists = bool(artifact_path and artifact_path.exists())
    latest_artifact = _latest_path(agents_root / holon_name / "artifacts", "*.json")
    proof_at = str(event.get("at") or record.get("created_at") or "")
    proof_age_hours = _age_hours(proof_at) if proof_at else None
    proof_fresh = (
        proof_age_hours is not None
        and proof_age_hours <= HOLON_L4_PROOF_MAX_AGE_HOURS
    )
    prod_verifier = _latest_holon_prod_verifier_state(repo_root)
    model_responsiveness = _latest_holon_model_responsiveness_state(
        repo_root=repo_root,
        agents_root=agents_root,
        holon_name=holon_name,
    )
    supervisor_activation = _latest_holon_supervisor_activation_state(
        agents_root=agents_root,
        holon_name=holon_name,
        tmux_sessions=list(tmux_sessions or []),
    )

    proof_gaps: list[str] = []
    service_paused = bool(service_liveness.get("service_paused"))
    if not service_liveness.get("service_alive") and not service_paused:
        if not service_liveness.get("heartbeat_seen"):
            proof_gaps.append("holon_service_heartbeat_missing")
        elif not service_liveness.get("ledger_ok"):
            proof_gaps.append("holon_service_heartbeat_ledger_invalid")
        elif not service_liveness.get("fresh"):
            proof_gaps.append("holon_service_heartbeat_stale")
        else:
            proof_gaps.append("holon_service_not_alive")

    if not transport_liveness.get("transport_reachable"):
        reasons = transport_liveness.get("failure_reasons")
        if isinstance(reasons, list) and reasons:
            proof_gaps.extend(f"holon_transport_{reason}" for reason in reasons)
        else:
            proof_gaps.append("holon_transport_unreachable")

    if not record:
        proof_gaps.append("holon_l4_persisted_proof_missing")
    else:
        if record.get("overall_pass") is not True:
            proof_gaps.append("holon_l4_persisted_proof_failed")
        if not artifact_exists:
            proof_gaps.append("holon_l4_artifact_missing")
        if not proof_fresh:
            proof_gaps.append("holon_l4_persisted_proof_stale")
        if proof_levels.get("orchestration") is not True:
            proof_gaps.append("holon_l4_orchestration_unproven")

    if not model_responsiveness.get("event_seen"):
        proof_gaps.append("holon_l4_model_responsive_proof_missing")
    elif not model_responsiveness.get("model_responsive_proven"):
        if model_responsiveness.get("fresh") is False:
            proof_gaps.append("holon_l4_model_responsive_proof_stale")
        elif not model_responsiveness.get("artifact_exists"):
            proof_gaps.append("holon_l4_model_responsive_artifact_missing")
        elif not model_responsiveness.get("declared_route"):
            proof_gaps.append("holon_l4_model_responsive_not_declared_route")
        elif not model_responsiveness.get("explicit_lease"):
            proof_gaps.append("holon_l4_model_responsive_lease_missing")
        elif not model_responsiveness.get("lease_valid"):
            proof_gaps.append("holon_l4_model_responsive_lease_invalid")
        elif not model_responsiveness.get("responsive"):
            proof_gaps.append("holon_l4_model_responsive_unproven")
        else:
            proof_gaps.append("holon_l4_model_responsive_unbound")

    if not prod_verifier["exists"]:
        proof_gaps.append("holon_l4_prod_verifier_missing")
    elif not prod_verifier["overall_pass"]:
        proof_gaps.append("holon_l4_prod_verifier_failed")
    elif not prod_verifier["l4_orchestration_probe_stub_pass"]:
        proof_gaps.append("holon_l4_prod_verifier_orchestration_unproven")

    if supervisor_activation.get("configured"):
        proof_gaps.extend(
            str(gap)
            for gap in supervisor_activation.get("proof_gaps", [])
            if str(gap)
        )

    evidence_seen = bool(
        service_liveness.get("heartbeat_seen")
        or transport_liveness.get("heartbeat_seen")
        or record
        or prod_verifier["exists"]
        or supervisor_activation.get("configured")
    )
    status = (
        "paused"
        if service_paused and not proof_gaps
        else "live"
        if not proof_gaps
        else "stale"
        if service_liveness.get("heartbeat_seen") and not service_liveness.get("fresh")
        else "partial"
        if evidence_seen
        else "unknown"
    )
    return {
        "holon": holon_name,
        "status": status,
        "agents_root": str(agents_root),
        "service_liveness": service_liveness,
        "transport_liveness": transport_liveness,
        "persisted_l4_proof": {
            "event_seen": bool(record),
            "event_at": proof_at,
            "age_hours": proof_age_hours,
            "max_age_hours": HOLON_L4_PROOF_MAX_AGE_HOURS,
            "fresh": proof_fresh,
            "overall_pass": record.get("overall_pass") is True,
            "proof_digest": str(record.get("proof_digest") or ""),
            "proof_levels": dict(proof_levels),
            "artifact_path": str(artifact_path) if artifact_path else "",
            "artifact_exists": artifact_exists,
            "latest_artifact": str(latest_artifact) if latest_artifact else "",
        },
        "model_responsiveness": model_responsiveness,
        "prod_verifier": prod_verifier,
        "supervisor_activation": supervisor_activation,
        "proof_gaps": proof_gaps,
    }


def _surface(
    *,
    surface_id: str,
    label: str,
    surface_class: str,
    status: str,
    desired_state: str,
    evidence: list[str],
    authority_refs: list[str],
    priority: str = "p1",
    freshness: str = "",
    process_key: str | None = None,
    processes: dict[str, list[dict[str, str]]] | None = None,
    ports: dict[str, dict[str, Any]] | None = None,
    restart_command: str = "",
    stop_policy: str = "",
    next_action: str = "",
    human_authority_required: bool = False,
    vps_candidate: bool = False,
    proof_gaps: list[str] | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proc_rows = processes.get(process_key, []) if process_key and processes else []
    port = ports.get(process_key, {}) if process_key and ports else {}
    proof_gap_list = [item for item in (proof_gaps or []) if item]
    required_live_gap = _required_live_gap_code(
        surface_id,
        status,
        desired_state,
        priority,
    )
    if required_live_gap and required_live_gap not in proof_gap_list:
        proof_gap_list.append(required_live_gap)
    stale_priority_gap = _stale_priority_gap_code(surface_id, status, priority)
    if stale_priority_gap and stale_priority_gap not in proof_gap_list:
        proof_gap_list.append(stale_priority_gap)
    unknown_priority_gap = _unknown_priority_gap_code(surface_id, status, priority)
    if unknown_priority_gap and unknown_priority_gap not in proof_gap_list:
        proof_gap_list.append(unknown_priority_gap)
    supervised_surface_gap = _supervised_surface_gap_code(
        surface_id,
        status,
        desired_state,
    )
    if supervised_surface_gap and supervised_surface_gap not in proof_gap_list:
        proof_gap_list.append(supervised_surface_gap)
    return {
        "id": surface_id,
        "label": label,
        "class": surface_class,
        "status": status,
        "desired_state": desired_state,
        "priority": priority,
        "freshness": freshness,
        "age_hours": _age_hours(freshness) if freshness else None,
        "pid_count": len(proc_rows),
        "pids": [row["pid"] for row in proc_rows],
        "port": port.get("port"),
        "port_listening": port.get("listening", False),
        "evidence": [item for item in evidence if item],
        "authority_refs": authority_refs,
        "restart_command": restart_command,
        "stop_policy": stop_policy,
        "next_action": next_action,
        "human_authority_required": human_authority_required,
        "vps_candidate": vps_candidate,
        "proof_gaps": proof_gap_list,
        "proof_state": "partial" if proof_gap_list else "bound",
        "raw": raw or {},
    }


def _live_if_process_or_port(process_key: str, processes: dict[str, list[dict[str, str]]], ports: dict[str, dict[str, Any]]) -> str:
    return "live" if processes.get(process_key) or ports.get(process_key, {}).get("listening") else "stopped"


def build_live_ops_census(
    *,
    repo_root: Path | str = DEFAULT_REPO_ROOT,
    state_root: Path | str = DEFAULT_STATE_ROOT,
    run_probes: bool = True,
    processes: dict[str, list[dict[str, str]]] | None = None,
    process_starts: dict[str, dict[str, str]] | None = None,
    ports: dict[str, dict[str, Any]] | None = None,
    http_probes: dict[str, dict[str, Any]] | None = None,
    daemon_health_self_report: dict[str, Any] | None = None,
    tmux_sessions: list[str] | None = None,
) -> dict[str, Any]:
    """Return the live-ops census as a pure data structure."""
    root = Path(repo_root)
    state = Path(state_root).expanduser()
    processes = processes if processes is not None else _process_snapshot(run_probes)
    ports = ports if ports is not None else _port_snapshot(run_probes)
    processes = _merge_port_owner_processes(processes, ports)
    process_starts = (
        process_starts
        if process_starts is not None
        else _process_start_snapshot(processes, run_probes)
    )
    http_probes = http_probes if http_probes is not None else _http_probe_snapshot(run_probes)
    tmux = tmux_sessions if tmux_sessions is not None else _tmux_sessions(run_probes)

    forge_heartbeat = state / "forge_reality_arena_master" / "codex_overnight_heartbeat.json"
    forge_handoff = state / "forge_reality_arena_master" / "shared" / "codex_overnight_handoff.md"
    forge_data = _read_json(forge_heartbeat)
    forge_freshness = str(forge_data.get("ts") or _iso_mtime(forge_heartbeat))
    forge_live = bool(processes.get("forge_hydra"))
    forge_external_gate = _forge_external_gate_state(root)
    forge_is_external_gated = forge_external_gate["state"] == "external_gated"
    forge_status = (
        "live"
        if forge_live
        else "blocked"
        if forge_is_external_gated
        else "stopped"
        if forge_heartbeat.exists()
        else "unknown"
    )
    forge_desired_state = (
        "blocked-until-operator-external-lease"
        if forge_is_external_gated and not forge_live
        else "supervised"
    )
    forge_next_action = (
        "wait for operator external-action lease or Guardian countersign before resuming"
        if forge_is_external_gated and not forge_live
        else "read handoff before restart"
    )
    forge_restart_command = (
        ""
        if forge_is_external_gated and not forge_live
        else "scripts/codex_overnight_autopilot.py"
    )

    revenue_state = state / "state" / "revenue_wedge_last_state.json"
    revenue_data = _read_json(revenue_state)
    gate_decision = str(revenue_data.get("gauntlet_decision") or "unknown")
    revenue_status = "blocked" if gate_decision == "HOLD" else _live_if_process_or_port("revenue_gate", processes, ports)

    agni_json = state / "remote_nodes" / "agni" / "kaizen_agni_latest.json"
    agni_md = state / "remote_nodes" / "agni" / "kaizen_agni_latest.md"
    agni_data = _read_json(agni_json)
    agni_freshness = str(agni_data.get("updated_at") or agni_data.get("ts") or _iso_mtime(agni_json))
    agni_age = _age_hours(agni_freshness) if agni_freshness else None
    agni_status = "live" if processes.get("agni") else "stale" if agni_age is not None and agni_age > 6 else "blocked" if agni_json.exists() else "unknown"

    managed_tmux = {"dharma-control", "dharma-agents", "dharma-vps"}
    tmux_missing = sorted(managed_tmux - set(tmux))
    tmux_status = "live" if not tmux_missing and tmux else "stopped"

    dashboard_live = (
        ports.get("dashboard_api", {}).get("listening")
        and ports.get("dashboard_web", {}).get("listening")
    )
    dashboard_rows_probe = http_probes.get("dashboard_control_surface_rows", {})
    dashboard_probe_state = str(dashboard_rows_probe.get("state") or "unknown")
    dashboard_rows_slow = bool(dashboard_rows_probe.get("slow"))
    dashboard_process_source = _daemon_process_source_state(
        root,
        processes.get("dashboard_api", []),
        process_starts.get("dashboard_api", {}),
        DASHBOARD_CONTROL_SURFACE_SOURCE_PATHS,
    )
    dashboard_next_action = (
        "inspect or restart dashboard API; control-surface rows probe did not answer"
        if dashboard_live and dashboard_probe_state not in {"ok", "not_checked"}
        else "profile dashboard API rows endpoint; live proof is slow"
        if dashboard_live and dashboard_rows_slow
        else "restart dashboard API to load current control-surface projector"
        if (
            dashboard_live
            and dashboard_process_source.get("state") == "source_changed_after_process_start"
        )
        else ""
    )

    sources = _authority_sources(root)
    source_refs = [item["path"] for item in sources if item.get("exists")]
    a2a_root = state / "a2a_bus"
    a2a_receipts_root = a2a_root / "receipts"
    a2a_messages_root = a2a_root / "messages"
    a2a_queue = a2a_root / "tasks" / "queue.jsonl"
    latest_a2a_receipt = _latest_path(a2a_receipts_root, "**/*.json")
    latest_a2a_message = _latest_path(a2a_messages_root, "*.json")
    freshest_a2a_mirror = _freshest_existing([
        latest_a2a_receipt,
        latest_a2a_message,
        a2a_queue,
    ])
    a2a_mirror_age_hours = _age_hours(_iso_mtime(freshest_a2a_mirror)) if freshest_a2a_mirror else None
    a2a_mirror_fresh = (
        a2a_mirror_age_hours is not None
        and a2a_mirror_age_hours <= A2A_MIRROR_MAX_AGE_HOURS
    )
    a2a_mirror_stale = bool(freshest_a2a_mirror and not a2a_mirror_fresh)
    nats_receipts_root = state / "nats" / "receipts"
    latest_nats_receipt = _latest_path(nats_receipts_root, "*.json")
    nats_log = state / "nats" / "nats-server.log"
    nats_live_receipt = a2a_root / "nats_live_receipt.json"
    nats_contact_receipts = a2a_root / "nats_contact_receipts.jsonl"
    nats_oz_receipts = a2a_root / "nats_oz_receipts.jsonl"
    a2a_send_receipts_root = repo_root / "reports" / "a2a" / "send_receipts"
    latest_send_hot_contact = _latest_hot_contact_send_receipt(a2a_send_receipts_root)
    latest_send_hot_contact_path = (
        Path(str(latest_send_hot_contact.get("_path")))
        if latest_send_hot_contact.get("_path")
        else None
    )
    freshest_nats_evidence = _freshest_existing([
        latest_nats_receipt,
        nats_live_receipt,
        nats_contact_receipts,
        nats_oz_receipts,
        latest_send_hot_contact_path,
        nats_log,
    ])
    nats_ack_state = _nats_ack_tier_state(
        nats_live_receipt=nats_live_receipt,
        nats_contact_receipts=nats_contact_receipts,
        nats_oz_receipts=nats_oz_receipts,
        latest_nats_receipt=latest_nats_receipt,
        latest_send_hot_contact=latest_send_hot_contact,
    )
    nats_receipts_status = "live" if freshest_nats_evidence else "unknown"
    nats_receipt_proof_gaps: list[str] = []
    if nats_receipts_status == "live":
        live_probe = nats_ack_state.get("live_probe", {})
        hot_contact = nats_ack_state.get("hot_contact", {})
        if not live_probe.get("ack_verified"):
            nats_receipt_proof_gaps.append("nats_live_ack_unproven")
        elif not nats_ack_state.get("operator_hot_contact_ready"):
            hot_ack_tier = str(hot_contact.get("ack_tier") or "")
            hot_ack_age = hot_contact.get("age_hours")
            if hot_ack_tier and hot_ack_age is not None:
                nats_receipt_proof_gaps.append("nats_hot_contact_ack_stale")
            else:
                nats_receipt_proof_gaps.append("nats_hot_contact_ack_unproven")
    nats_receipts_next_action = (
        "collect fresh HANDLER_ACKED or DOMAIN_RECEIPTED NATS hot-contact receipt before claiming live contact"
        if nats_receipt_proof_gaps
        else "NATS ack tier is freshly proven for operator hot contact"
    )
    nats_live_contact_bound = nats_receipts_status == "live" and not nats_receipt_proof_gaps
    a2a_mirror_proof_gaps: list[str] = []
    if a2a_mirror_stale and not nats_live_contact_bound:
        a2a_mirror_proof_gaps.append("a2a_mirror_evidence_stale")
    a2a_mirror_next_action = (
        "NATS live-contact proof is bound; filesystem mirrors are historical compatibility evidence"
        if a2a_mirror_stale and nats_live_contact_bound
        else "treat filesystem mirrors as historical; use NATS ack/domain receipts for live-contact proof"
        if a2a_mirror_stale
        else "inspect NATS ack receipts for live-contact proof"
    )
    a2a_bridge_agent_uid = "hermes-m5"
    a2a_bridge_session = "dharma_a2a_inbox_bridge_hermes_m5"
    a2a_bridge_heartbeat = a2a_root / "bridge_heartbeats" / f"{a2a_bridge_agent_uid}.json"
    a2a_bridge_receipts_root = root / "reports" / "a2a" / "inbox_bridge_receipts"
    latest_a2a_bridge_receipt = _latest_path(a2a_bridge_receipts_root, "*.json")
    a2a_bridge_process_live = bool(processes.get("a2a_inbox_bridge"))
    a2a_bridge_tmux_live = a2a_bridge_session in tmux
    a2a_bridge_runtime_state = _a2a_inbox_bridge_runtime_state(
        repo_root=root,
        heartbeat=a2a_bridge_heartbeat,
        latest_receipt=latest_a2a_bridge_receipt,
        agent_uid=a2a_bridge_agent_uid,
        session=a2a_bridge_session,
        stream="DHARMA_FLEET",
        consumer="hermes_inbox",
        tmux_live=a2a_bridge_tmux_live,
        process_live=a2a_bridge_process_live,
        run_probes=run_probes,
        nats_port=ports.get("nats", {}),
    )
    consumer_state = str(
        (a2a_bridge_runtime_state.get("consumer_probe") or {}).get("state") or ""
    )
    a2a_bridge_heartbeat_live = (
        a2a_bridge_runtime_state.get("heartbeat_fresh") is True
        and consumer_state
        not in {
            "nats_not_listening",
            "consumer_unavailable",
            "consumer_unreadable",
        }
    )
    a2a_bridge_status = (
        "live"
        if a2a_bridge_process_live
        or a2a_bridge_tmux_live
        or a2a_bridge_heartbeat_live
        else "stopped"
    )
    if a2a_bridge_status != "live":
        a2a_bridge_proof_gaps = ["a2a_inbox_bridge_stopped"]
    elif not a2a_bridge_heartbeat.exists():
        a2a_bridge_proof_gaps = ["a2a_inbox_bridge_heartbeat_missing"]
    else:
        a2a_bridge_proof_gaps = []
    if (
        a2a_bridge_heartbeat.exists()
        and a2a_bridge_runtime_state.get("heartbeat_fresh") is False
    ):
        a2a_bridge_proof_gaps.append("a2a_inbox_bridge_heartbeat_stale")
    if consumer_state in {
        "nats_not_listening",
        "consumer_unavailable",
        "consumer_unreadable",
    }:
        a2a_bridge_proof_gaps.append("a2a_inbox_bridge_consumer_unproven")
    holon_l4_state = _holon_l4_runtime_state(root, state, tmux_sessions=tmux)
    runtime_truth_clean_epoch = _runtime_truth_clean_epoch_state(state)
    runtime_receipt_scope_since = (
        str(runtime_truth_clean_epoch.get("since_created_at") or "")
        if runtime_truth_clean_epoch.get("enabled") is True
        else ""
    )
    runtime_receipt_head = _runtime_receipt_active_head_state(
        state,
        since_created_at=runtime_receipt_scope_since,
    )
    runtime_receipt_head_dirty = (
        runtime_receipt_head.get("active_head_side_effect_key_clean") is False
        and any(
            int(row.get("total", 0)) > 0
            and int(row.get("missing_side_effect_key", 0)) > 0
            for row in runtime_receipt_head.get("windows", [])
        )
    )
    runtime_receipt_head_stale = (
        runtime_receipt_head.get("latest_fresh") is False
        and int(runtime_receipt_head.get("runtime_receipts_total") or 0) > 0
    )
    runtime_receipt_coverage = _runtime_receipt_coverage_state(
        state,
        clean_epoch=runtime_truth_clean_epoch,
    )
    runtime_provider_model_unproven = (
        runtime_receipt_coverage.get("coverage_report_available") is True
        and int(runtime_receipt_coverage.get("latest_sample_size") or 0) > 0
        and runtime_receipt_coverage.get("provider_model_latest_complete") is False
    )
    dharma_launch = _dharma_launch_dispatch(root)
    cron_launch = _cron_launch_dispatch(root)
    dharma_status = _live_if_process_or_port("dharma_daemon", processes, ports)
    cron_status = "live" if processes.get("dharma_cron") else "stopped"
    dharma_observed_pids = {
        str(row.get("pid") or "")
        for row in processes.get("dharma_daemon", [])
        if str(row.get("pid") or "")
    }
    dharma_observed_pid_sources = {
        pid: "process_snapshot" for pid in dharma_observed_pids
    }
    daemon_pid_file = _daemon_pid_file_state(state)
    if (
        dharma_status == "live"
        and daemon_pid_file.get("state") == "present"
        and daemon_pid_file.get("pid")
    ):
        daemon_pid = str(daemon_pid_file["pid"])
        dharma_observed_pids.add(daemon_pid)
        dharma_observed_pid_sources.setdefault(daemon_pid, "daemon_pid_file")
    dharma_surface_processes = {key: [dict(row) for row in rows] for key, rows in processes.items()}
    if daemon_pid_file.get("state") == "present" and daemon_pid_file.get("pid"):
        daemon_pid = str(daemon_pid_file["pid"])
        rows = dharma_surface_processes.setdefault("dharma_daemon", [])
        if daemon_pid not in {str(row.get("pid") or "") for row in rows}:
            insert_at = next(
                (
                    idx
                    for idx, row in enumerate(rows)
                    if row.get("source") == "lsof_listen"
                ),
                len(rows),
            )
            rows.insert(insert_at, {
                "pid": daemon_pid,
                "command": f"daemon_pid_file:{state / 'daemon.pid'}",
                "source": "daemon_pid_file",
            })
    daemon_health = (
        daemon_health_self_report
        if daemon_health_self_report is not None
        else _daemon_health_self_report(
            run_probes=run_probes,
            observed_pids=dharma_observed_pids,
        )
    )
    daemon_file_self_report = _daemon_runtime_dispatch_file_self_report(
        state,
        observed_pids=dharma_observed_pids,
        observed_pid_sources=dharma_observed_pid_sources,
        now=datetime.now(UTC),
    )
    daemon_health_state = str(daemon_health.get("state") or "")
    daemon_file_state = str(daemon_file_self_report.get("state") or "")
    if daemon_health_state in DAEMON_SPINE_RUNTIME_PROOFS:
        dharma_running_proof = daemon_health_state
        dharma_running_proof_source = "daemon_health_http"
    elif daemon_file_state in DAEMON_SPINE_RUNTIME_PROOFS:
        dharma_running_proof = daemon_file_state
        dharma_running_proof_source = "daemon_runtime_dispatch_self_report_file"
    else:
        dharma_running_proof = (
            daemon_health_state
            or daemon_file_state
            or "not_inspected_no_secret_env_dump"
        )
        dharma_running_proof_source = "unproven"
    dharma_dispatch_runtime_proven = (
        dharma_running_proof in DAEMON_SPINE_RUNTIME_PROOFS
    )
    dharma_process_source = _daemon_process_source_state(
        root,
        processes.get("dharma_daemon", []),
        process_starts.get("dharma_daemon", {}),
    )
    runtime_receipt_since_boot = _runtime_receipt_since_boot_state(
        state,
        dharma_process_source,
    )
    runtime_receipt_since_boot_dirty = (
        runtime_receipt_since_boot.get("since_boot_major_identity_clean") is False
        and (
            int(runtime_receipt_since_boot.get("missing_side_effect_key") or 0) > 0
            or int(runtime_receipt_since_boot.get("missing_idempotency_key") or 0) > 0
        )
    )
    dharma_dispatch_next_action = (
        "fix current-boot runtime receipt producers before claiming daemon readiness"
        if runtime_receipt_since_boot_dirty
        else "fix active runtime receipt producers before claiming daemon readiness"
        if runtime_receipt_head_dirty
        else "exercise a fresh daemon/default runtime receipt path before claiming daemon readiness"
        if runtime_receipt_head_stale
        else "route actual provider/model into runtime receipts before claiming daemon readiness"
        if runtime_provider_model_unproven
        else "controlled restart plus daemon/default receipt probe required"
        if dharma_launch.get("state") == "spine_enabled_launch_spec"
        and not dharma_dispatch_runtime_proven
        else "pin LaunchAgent to repo module before restart"
        if dharma_launch.get("state")
        in {"ambient_dgc_spine_launch_spec", "unblessed_spine_launch_spec"}
        else "set DHARMA_SPINE_DISPATCH=1 in LaunchAgent before restart"
        if dharma_launch.get("state") != "spine_enabled_launch_spec"
        else ""
    )
    dharma_proof_gaps: list[str] = []
    if dharma_status == "live":
        if dharma_launch.get("state") in {
            "ambient_dgc_spine_launch_spec",
            "unblessed_spine_launch_spec",
        }:
            dharma_proof_gaps.append("daemon_launch_not_repo_pinned")
        elif dharma_launch.get("state") != "spine_enabled_launch_spec":
            dharma_proof_gaps.append("daemon_launch_not_spine_enabled")
        if dharma_running_proof not in DAEMON_SPINE_RUNTIME_PROOFS:
            dharma_proof_gaps.append("daemon_dispatch_runtime_unproven")
        if dharma_process_source.get("state") == "source_changed_after_process_start":
            dharma_proof_gaps.append("daemon_process_source_stale")
        if dharma_process_source.get("state") == "process_start_probe_failed":
            dharma_proof_gaps.append("daemon_process_start_uninspected")
        if runtime_receipt_since_boot_dirty:
            dharma_proof_gaps.append("daemon_runtime_receipts_since_boot_dirty")
        if runtime_receipt_head_dirty:
            dharma_proof_gaps.append("daemon_runtime_receipts_active_head_dirty")
        if runtime_receipt_head_stale:
            dharma_proof_gaps.append("daemon_runtime_receipts_stale")
        if runtime_provider_model_unproven:
            dharma_proof_gaps.append("daemon_runtime_provider_model_unproven")
        if (
            runtime_truth_clean_epoch.get("exists") is True
            and runtime_truth_clean_epoch.get("enabled") is not True
        ):
            dharma_proof_gaps.append("daemon_runtime_truth_clean_epoch_invalid")
    cron_proof_gaps: list[str] = []
    cron_launch_state = str(cron_launch.get("state") or "")
    if cron_status == "live":
        if cron_launch_state in {
            "ambient_dgc_cron_launch_spec",
            "unblessed_cron_launch_spec",
        }:
            cron_proof_gaps.append("cron_launch_not_repo_pinned")
        elif cron_launch_state != "repo_pinned_cron_launch_spec":
            cron_proof_gaps.append("cron_launch_unproven")
    cron_next_action = (
        "pin cron LaunchAgent to repo module before burn-in"
        if "cron_launch_not_repo_pinned" in cron_proof_gaps
        else "install or repair cron LaunchAgent before burn-in"
        if "cron_launch_unproven" in cron_proof_gaps
        else ""
    )
    dashboard_proof_gaps: list[str] = []
    if dashboard_live and dashboard_probe_state not in {"ok", "not_checked"}:
        dashboard_proof_gaps.append("dashboard_control_surface_rows_unproven")
    if (
        dashboard_live
        and dashboard_process_source.get("state") == "source_changed_after_process_start"
    ):
        dashboard_proof_gaps.append("dashboard_control_surface_source_stale")
    if (
        dashboard_live
        and dashboard_process_source.get("state") == "process_start_probe_failed"
    ):
        dashboard_proof_gaps.append("dashboard_control_surface_process_start_uninspected")
    terminal_session = "dharma_terminal_tui"
    terminal_tmux_live = terminal_session in tmux
    terminal_process_live = bool(processes.get("terminal_tui"))
    terminal_status = "live" if terminal_process_live or terminal_tmux_live else "stopped"
    terminal_process_source = _daemon_process_source_state(
        root,
        processes.get("terminal_tui", []),
        process_starts.get("terminal_tui", {}),
        TERMINAL_TUI_SOURCE_PATHS,
    )
    terminal_proof_gaps: list[str] = []
    if (
        terminal_status == "live"
        and terminal_process_source.get("state") == "source_changed_after_process_start"
    ):
        terminal_proof_gaps.append("terminal_tui_source_stale")
    terminal_next_action = (
        "restart terminal TUI to load current terminal source after operator approval"
        if terminal_proof_gaps
        else "restore only after dashboard truth lane is stable"
    )
    ds_goal_cli = _ds_goal_cli_state(root)
    ds_goal_cli_proof_gaps: list[str] = []
    ds_goal_cli_hardening = ds_goal_cli.get("target_sync_receipt_hardening", {})
    ds_goal_cli_decision = (
        ds_goal_cli.get("convergence_decision_packet")
        if isinstance(ds_goal_cli.get("convergence_decision_packet"), dict)
        else {}
    )
    ds_goal_cli_preflight = (
        ds_goal_cli.get("longrun_preflight_gate")
        if isinstance(ds_goal_cli.get("longrun_preflight_gate"), dict)
        else {}
    )
    ds_goal_cli_human_authority_required = bool(
        ds_goal_cli_decision.get("operator_approval_required")
        or ds_goal_cli_preflight.get("operator_convergence_required")
    )
    if ds_goal_cli.get("wrapper_exists"):
        ds_goal_cli_state = str(ds_goal_cli.get("state") or "")
        if ds_goal_cli_state == "wrapper_unreadable":
            ds_goal_cli_proof_gaps.append("ds_goal_cli_wrapper_unreadable")
        if (
            ds_goal_cli_state not in {"repo_outside_operator_home", "wrapper_unreadable"}
            and ds_goal_cli.get("target_matches_current_repo") is False
        ):
            ds_goal_cli_proof_gaps.append("ds_goal_cli_target_repo_mismatch")
        if (
            ds_goal_cli_hardening
            and ds_goal_cli_state != "repo_outside_operator_home"
            and ds_goal_cli_hardening.get("state")
            != "sync_receipt_side_effect_keys_hardened"
        ):
            ds_goal_cli_proof_gaps.append(
                "ds_goal_cli_target_lacks_sync_side_effect_hardening"
            )
    ds_goal_cli_next_action = (
        "use the pinned current-checkout invocation, converge the wrapper target, or deploy runtime receipt hardening to its target"
        if ds_goal_cli_proof_gaps
        else "record an operator decision on ds-goal default wrapper convergence before claiming production readiness"
        if ds_goal_cli_human_authority_required
        else "install ds-goal wrapper only if the ds-goal runtime lane is active"
        if not ds_goal_cli.get("wrapper_exists")
        else ""
    )

    surfaces = [
        _surface(
            surface_id="substrate.dharma_daemon",
            label="Dharma daemon",
            surface_class="substrate",
            status=dharma_status,
            desired_state="live",
            evidence=["port:7433", "/Users/dhyana/.dharma/logs/swarm.log"],
            authority_refs=["docs/state/LIVE_OPS_DASHBOARD.md", "ACTIVE_SURFACE_MANIFEST.yaml"],
            priority="p0",
            process_key="dharma_daemon",
            processes=dharma_surface_processes,
            ports=ports,
            restart_command="launchctl kickstart gui/$UID/com.dharma.swarm",
            stop_policy="do-not-stop-before-travel",
            next_action=dharma_dispatch_next_action,
            proof_gaps=dharma_proof_gaps,
            raw={
                "dispatch_launch": dharma_launch,
                "running_dispatch_proof": dharma_running_proof,
                "running_dispatch_proof_source": dharma_running_proof_source,
                "daemon_health_self_report": daemon_health,
                "daemon_pid_file": daemon_pid_file,
                "daemon_runtime_dispatch_self_report": daemon_file_self_report,
                "process_source_state": dharma_process_source,
                "runtime_truth_clean_epoch": runtime_truth_clean_epoch,
                "runtime_receipt_active_head": runtime_receipt_head,
                "runtime_receipt_since_boot": runtime_receipt_since_boot,
                "runtime_receipt_coverage": runtime_receipt_coverage,
            },
        ),
        _surface(
            surface_id="cli.ds_goal",
            label="ds-goal runtime CLI",
            surface_class="terminal",
            status="live" if ds_goal_cli.get("wrapper_exists") else "unknown",
            desired_state="wrapper-targets-current-runtime-checkout",
            evidence=[
                str(Path.home() / ".dharma" / "bin" / "ds-goal"),
                str(ds_goal_cli.get("target_repo") or ""),
                str(ds_goal_cli.get("evidence") or ""),
            ],
            authority_refs=[
                "scripts/runtime/autonomy_spine.py",
                "dharma_swarm/runtime_state.py",
                "docs/governance/ACTIVE_TRACK.yaml",
            ],
            priority="p1",
            restart_command=(
                f"{ds_goal_cli.get('safe_current_checkout_invocation')} --help"
                if ds_goal_cli.get("safe_current_checkout_invocation")
                else "DHARMA_SWARM_REPO=<current-checkout> ds-goal --help"
            ),
            stop_policy="cli-only; do not mutate wrapper or launch longruns from census",
            next_action=ds_goal_cli_next_action,
            human_authority_required=ds_goal_cli_human_authority_required,
            proof_gaps=ds_goal_cli_proof_gaps,
            raw=ds_goal_cli,
        ),
        _surface(
            surface_id="substrate.dharma_cron",
            label="Dharma cron daemon",
            surface_class="substrate",
            status=cron_status,
            desired_state="live",
            evidence=["dharma_swarm.dgc_cli cron daemon"],
            authority_refs=["scripts/governance/agent_onboard.py", "docs/governance/ACTIVE_TRACK.yaml"],
            priority="p0",
            process_key="dharma_cron",
            processes=processes,
            ports=ports,
            restart_command="launchctl kickstart gui/$UID/com.dharma.cron-daemon",
            stop_policy="do-not-stop-before-travel",
            next_action=cron_next_action,
            proof_gaps=cron_proof_gaps,
            raw={"dispatch_launch": cron_launch},
        ),
        _surface(
            surface_id="transport.nats",
            label="Local NATS JetStream",
            surface_class="substrate",
            status=_live_if_process_or_port("nats", processes, ports),
            desired_state="live",
            evidence=["127.0.0.1:4222", str(state / "nats" / "nats-server.log")],
            authority_refs=["docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"],
            priority="p0",
            process_key="nats",
            processes=processes,
            ports=ports,
            restart_command="make onboard  # verify; launcher is persistent layer owned",
            stop_policy="do-not-stop-if-A2A-needed",
        ),
        _surface(
            surface_id="transport.a2a_bridge",
            label="A2A inbox delivery bridge",
            surface_class="substrate",
            status=a2a_bridge_status,
            desired_state="delivery-handler-not-semantic-peer",
            evidence=[
                "scripts/runtime/a2a_inbox_bridge.py",
                "scripts/status_a2a_inbox_bridge_fleet_launchd.sh",
                str(a2a_bridge_heartbeat),
                f"latest_receipt={latest_a2a_bridge_receipt}" if latest_a2a_bridge_receipt else "",
                f"heartbeat_age_hours={a2a_bridge_runtime_state.get('heartbeat_age_hours')}"
                if a2a_bridge_runtime_state.get("heartbeat_age_hours") is not None
                else "",
                "consumer_probe="
                f"{(a2a_bridge_runtime_state.get('consumer_probe') or {}).get('state')}",
                f"session={a2a_bridge_session}",
            ],
            authority_refs=["docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"],
            priority="p0",
            process_key="a2a_inbox_bridge",
            processes=processes,
            ports=ports,
            restart_command="bash scripts/start_a2a_inbox_bridge_fleet_launchd.sh",
            stop_policy="do-not-stop-if-A2A-needed",
            next_action=(
                "start governed launchd inbox bridge fleet if live A2A delivery is required"
                if a2a_bridge_status != "live"
                else "require reply/domain receipt before claiming semantic collaboration"
            ),
            proof_gaps=a2a_bridge_proof_gaps,
            raw=a2a_bridge_runtime_state,
        ),
        _surface(
            surface_id="holon.codex_composer_l4",
            label="codex_composer L4 HOLON",
            surface_class="holon",
            status=str(holon_l4_state["status"]),
            desired_state="l4-body-proof-bound",
            evidence=[
                "dharma_swarm/holon_l4_smoke.py",
                "dharma_swarm/holon_l4_service.py",
                "dharma_swarm/holon_l4_supervisor.py",
                "dharma_swarm/holon_l4_activation.py",
                "dharma_swarm/holon_orchestrate.py",
                "scripts/holon_l4_service.py",
                "scripts/holon_l4_supervisor.py",
                "scripts/holon_l4_activation.py",
                str(
                    holon_service_heartbeat_path(
                        HOLON_L4_AGENT_UID,
                        state / "agents",
                    )
                ),
                str(state / "a2a_bus" / "bridge_heartbeats" / f"{HOLON_L4_AGENT_UID}.json"),
                str(
                    holon_l4_state["persisted_l4_proof"].get("artifact_path")
                    or holon_l4_state["persisted_l4_proof"].get("latest_artifact")
                    or ""
                ),
                str(holon_l4_state["prod_verifier"].get("path") or ""),
                str(holon_l4_state["model_responsiveness"].get("artifact_path") or ""),
                str(holon_l4_state["model_responsiveness"].get("lease_path") or ""),
                str(holon_l4_state["supervisor_activation"].get("plan_path") or ""),
                str(holon_l4_state["supervisor_activation"].get("activation_path") or ""),
                f"model_responsive={holon_l4_state['model_responsiveness'].get('model_responsive_proven')}",
                f"tmux_session={holon_l4_state['supervisor_activation'].get('tmux_session')}"
                if holon_l4_state["supervisor_activation"].get("tmux_session")
                else "",
                f"tmux_session_live={holon_l4_state['supervisor_activation'].get('tmux_session_live')}"
                if holon_l4_state["supervisor_activation"].get("configured")
                else "",
            ],
            authority_refs=[
                "docs/sovereign_holons/STATE_OF_TRUTH.md",
                "docs/sovereign_holons/HOLON_ORCHESTRATOR_BUILD_SPEC.md",
                "reports/sovereign_holons/L4_HOLON_SUBSTRATE_HYGIENE_AND_SMOKE_20260618.md",
            ],
            priority="p0",
            freshness=str(
                holon_l4_state["persisted_l4_proof"].get("event_at")
                or holon_l4_state["supervisor_activation"].get("latest_start_created_at")
                or holon_l4_state["service_liveness"].get("latest_observed_at")
                or ""
            ),
            stop_policy="do-not-stop-if-agent-contact-needed; observer surface only",
            next_action=(
                "run governed leased L4 model probe before claiming full HOLON L4 responsiveness"
                if any(
                    str(gap).startswith("holon_l4_model_responsive")
                    for gap in holon_l4_state["proof_gaps"]
                )
                else "run governed L4 smoke with orchestration and transport heartbeat before claiming HOLON live"
                if holon_l4_state["proof_gaps"]
                else "HOLON L4 proof is bound, including governed model responsiveness"
            ),
            proof_gaps=list(holon_l4_state["proof_gaps"]),
            raw=holon_l4_state,
        ),
        _surface(
            surface_id="evidence.a2a_mirrors",
            label="A2A filesystem mirrors",
            surface_class="evidence",
            status="live" if latest_a2a_receipt or latest_a2a_message or a2a_queue.exists() else "unknown",
            desired_state="evidence-mirror-not-authority",
            evidence=[
                str(a2a_receipts_root),
                str(a2a_messages_root),
                str(a2a_queue),
                f"latest_receipt={latest_a2a_receipt}" if latest_a2a_receipt else "",
                f"latest_message={latest_a2a_message}" if latest_a2a_message else "",
            ],
            authority_refs=["docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"],
            priority="p1",
            freshness=_iso_mtime(freshest_a2a_mirror) if freshest_a2a_mirror else "",
            stop_policy="mirror-only; do not treat as live-contact authority",
            next_action=a2a_mirror_next_action,
            proof_gaps=a2a_mirror_proof_gaps,
            raw={
                "receipt_count": _count_files(a2a_receipts_root, "**/*.json"),
                "message_count": _count_files(a2a_messages_root, "*.json"),
                "queue_exists": a2a_queue.exists(),
                "latest_mirror_path": str(freshest_a2a_mirror) if freshest_a2a_mirror else "",
                "latest_mirror_age_hours": a2a_mirror_age_hours,
                "mirror_max_age_hours": A2A_MIRROR_MAX_AGE_HOURS,
                "mirror_fresh": a2a_mirror_fresh,
                "mirror_stale": a2a_mirror_stale,
                "nats_live_contact_bound": nats_live_contact_bound,
            },
        ),
        _surface(
            surface_id="evidence.nats_receipts",
            label="NATS receipts and logs",
            surface_class="evidence",
            status=nats_receipts_status,
            desired_state="ack-receipt-evidence",
            evidence=[
                str(nats_receipts_root),
                str(nats_log),
                str(nats_live_receipt),
                str(nats_contact_receipts),
                str(nats_oz_receipts),
                f"latest_receipt={latest_nats_receipt}" if latest_nats_receipt else "",
                (
                    f"latest_send_hot_contact={latest_send_hot_contact_path}"
                    if latest_send_hot_contact_path
                    else ""
                ),
            ],
            authority_refs=["docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"],
            priority="p0",
            freshness=_iso_mtime(freshest_nats_evidence or nats_log),
            stop_policy="receipt-only; NATS process lifecycle remains operator-controlled",
            next_action=nats_receipts_next_action,
            proof_gaps=nats_receipt_proof_gaps,
            raw={
                "receipt_count": _count_files(nats_receipts_root, "*.json"),
                "log_exists": nats_log.exists(),
                "nats_live_receipt_exists": nats_live_receipt.exists(),
                "nats_contact_receipts_exists": nats_contact_receipts.exists(),
                "nats_oz_receipts_exists": nats_oz_receipts.exists(),
                "latest_send_hot_contact_exists": bool(latest_send_hot_contact_path),
                "ack_tier_state": nats_ack_state,
            },
        ),
        _surface(
            surface_id="external.hermes_a2a",
            label="Hermes A2A server",
            surface_class="substrate",
            status=_live_if_process_or_port("hermes_a2a", processes, ports),
            desired_state="live",
            evidence=["127.0.0.1:8421", str(Path.home() / ".hermes" / "logs" / "a2a-server.log")],
            authority_refs=["docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"],
            priority="p1",
            process_key="hermes_a2a",
            processes=processes,
            ports=ports,
            restart_command="make onboard  # verify A2A readiness",
            stop_policy="safe-to-stop-only-if-no-agent-contact-needed",
        ),
        _surface(
            surface_id="dashboard.local",
            label="Dashboard API and web",
            surface_class="dashboard",
            status="live" if dashboard_live else "stopped",
            desired_state="live",
            evidence=[
                "127.0.0.1:8420",
                "127.0.0.1:3420",
                "scripts/dashboard_ctl.sh status",
                f"control_surface_rows={dashboard_probe_state}",
                (
                    f"control_surface_rows_elapsed={dashboard_rows_probe.get('elapsed_seconds')}s"
                    if dashboard_rows_probe.get("elapsed_seconds") is not None
                    else ""
                ),
            ],
            authority_refs=["ACTIVE_SURFACE_MANIFEST.yaml", "docs/governance/CANONICAL_DOC_STACK.md"],
            priority="p0",
            process_key="dashboard_api",
            processes=processes,
            ports=ports,
            restart_command="bash scripts/dashboard_ctl.sh start",
            stop_policy="safe-to-restart-for-dashboard-work",
            next_action=dashboard_next_action,
            proof_gaps=dashboard_proof_gaps,
            raw={
                "control_surface_rows_probe": dashboard_rows_probe,
                "process_source_state": dashboard_process_source,
            },
        ),
        _surface(
            surface_id="tmux.cockpit",
            label="Canonical tmux cockpit",
            surface_class="terminal",
            status=tmux_status,
            desired_state="live",
            evidence=[f"sessions={','.join(tmux) if tmux else 'none'}"],
            authority_refs=["docs/ops/TMUX_AGENT_SUBSTRATE.md"],
            priority="p0",
            restart_command="make tmux-bootstrap",
            stop_policy="safe-to-recreate; tmux-is-not-truth",
            next_action="bootstrap managed sessions" if tmux_missing else "",
            raw={"sessions": tmux, "missing": tmux_missing},
        ),
        _surface(
            surface_id="mission.forge_reality_arena",
            label="Forge Reality Arena Hydra",
            surface_class="mission",
            status=forge_status,
            desired_state=forge_desired_state,
            evidence=[
                str(forge_heartbeat),
                str(forge_handoff),
                str(root / FORGE_REALITY_ARENA_STATUS_PACKET),
            ],
            authority_refs=["docs/governance/ACTIVE_TRACK.yaml", "docs/ops/LIVE_OPS_COCKPIT.md"],
            priority="p1",
            freshness=forge_freshness,
            process_key="forge_hydra",
            processes=processes,
            ports=ports,
            restart_command=forge_restart_command,
            stop_policy="external-action-lease-required" if forge_is_external_gated else "restart-only-after-reading-latest-handoff",
            next_action=forge_next_action,
            human_authority_required=forge_is_external_gated and not forge_live,
            raw={"heartbeat": forge_data, "external_gate": forge_external_gate},
        ),
        _surface(
            surface_id="revenue.cashclaw_gate",
            label="Revenue / CashClaw gate",
            surface_class="revenue",
            status=revenue_status,
            desired_state="blocked-until-operator-approval",
            evidence=[str(revenue_state), "reports/revenue_wedge/first_cash_receipt_status.md"],
            authority_refs=["docs/governance/ACTIVE_TRACK.yaml", "docs/governance/VENTURE_CELL_PORTFOLIO.yaml"],
            priority="p0",
            freshness=str(revenue_data.get("fire_ts") or _iso_mtime(revenue_state)),
            process_key="revenue_gate",
            processes=processes,
            ports=ports,
            restart_command="launchd loop revenue_wedge_gate",
            stop_policy="monitor-only; no outreach or money without operator approval",
            next_action="keep HOLD until explicit operator approval" if gate_decision == "HOLD" else "inspect gate state",
            human_authority_required=True,
            raw={"revenue_state": revenue_data},
        ),
        _surface(
            surface_id="remote.agni",
            label="AGNI remote watcher / trading",
            surface_class="remote",
            status=agni_status,
            desired_state="remote-observed-or-blocked",
            evidence=[str(agni_json), str(agni_md)],
            authority_refs=["docs/ops/TMUX_AGENT_SUBSTRATE.md", "docs/governance/VENTURE_CELL_PORTFOLIO.yaml"],
            priority="p0",
            freshness=agni_freshness,
            process_key="agni",
            processes=processes,
            ports=ports,
            restart_command="ssh agni  # inspect remote receipts before launching anything",
            stop_policy="no-real-money-without-operator-approval",
            next_action="refresh remote receipts and feeds",
            human_authority_required=True,
            vps_candidate=True,
            raw={"agni": agni_data},
        ),
        _surface(
            surface_id="agent.merge_master_mike",
            label="Merge Master Mike",
            surface_class="mission",
            status="live" if processes.get("merge_master_mike") else "stopped",
            desired_state="operator-mediated",
            evidence=["scripts/runtime/merge_master_mike_daemon.py"],
            authority_refs=["docs/ops/PR_REVIEW_CONTROL.md", "docs/governance/COHERENCE_DELTA.md"],
            priority="p1",
            process_key="merge_master_mike",
            processes=processes,
            ports=ports,
            restart_command="make mike-status && make mike-wake",
            stop_policy="no-automerge-without-operator-authority",
            next_action="restart only when PR queue triage is active",
            human_authority_required=True,
        ),
        _surface(
            surface_id="terminal.tui",
            label="Terminal TUI",
            surface_class="terminal",
            status=terminal_status,
            desired_state="optional-cockpit",
            evidence=[
                "scripts/status_terminal_tui_tmux.sh",
                "scripts/capture_terminal_tui_tmux.sh",
                "scripts/send_terminal_tui_keys.sh",
            ],
            authority_refs=["docs/ops/TMUX_AGENT_SUBSTRATE.md", "specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md"],
            priority="p1",
            process_key="terminal_tui",
            processes=processes,
            ports=ports,
            restart_command="./scripts/start_terminal_tui_tmux.sh",
            stop_policy="optional; dashboard cockpit is primary tonight",
            next_action=terminal_next_action,
            proof_gaps=terminal_proof_gaps,
            raw={
                "session": terminal_session,
                "tmux_session_live": terminal_tmux_live,
                "process_live": terminal_process_live,
                "process_source_state": terminal_process_source,
            },
        ),
        _surface(
            surface_id="load.colima_openclaw",
            label="Colima / OpenClaw VM",
            surface_class="heavy",
            status="live" if processes.get("colima_openclaw") else "stopped",
            desired_state="operator-choice",
            evidence=["colima-openclaw-secure", "qemu-system-aarch64"],
            authority_refs=["docs/ops/LIVE_OPS_COCKPIT.md"],
            priority="p2",
            process_key="colima_openclaw",
            processes=processes,
            ports=ports,
            restart_command="colima start openclaw-secure",
            stop_policy="safe-to-stop-if-not-using-openclaw",
            next_action="stop for battery/flight if not needed",
            human_authority_required=True,
        ),
    ]

    counts = Counter(surface["status"] for surface in surfaces)
    return {
        "schema_version": LIVE_OPS_CENSUS_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "repo_root": str(root),
        "state_root": str(state),
        "git": _git_boundary(root),
        "authority_sources": sources,
        "summary": {
            "total": len(surfaces),
            "by_status": dict(sorted(counts.items())),
            "human_authority_required": sum(1 for item in surfaces if item["human_authority_required"]),
            "vps_candidates": sum(1 for item in surfaces if item["vps_candidate"]),
            "proof_gap_surfaces": sum(1 for item in surfaces if item.get("proof_gaps")),
        },
        "surfaces": surfaces,
        "source_refs": source_refs,
    }


def write_census(payload: dict[str, Any], output: Path = DEFAULT_OUTPUT) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output.with_name(
        f".{output.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    try:
        tmp_output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_output, output)
    finally:
        if tmp_output.exists():
            tmp_output.unlink()
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the read-only live ops census.")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true", help="write the census JSON to --output")
    parser.add_argument("--no-probes", action="store_true", help="skip process/port/tmux probes")
    args = parser.parse_args()

    payload = build_live_ops_census(
        repo_root=args.repo_root,
        state_root=args.state_root,
        run_probes=not args.no_probes,
    )
    if args.write:
        path = write_census(payload, args.output)
        print(path)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
