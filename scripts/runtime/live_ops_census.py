#!/usr/bin/env python3
"""Build a read-only live-ops census for the operator cockpit.

This script is an observation surface, not a supervisor. It does not start,
stop, restart, kill, message, or mutate live processes. It folds the existing
governance owner files into one runtime census so the dashboard can show
declared intent, observed state, evidence paths, and operator policy together.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_ROOT = Path(os.environ.get("DHARMA_STATE_DIR", "~/.dharma")).expanduser()
DEFAULT_OUTPUT = DEFAULT_STATE_ROOT / "ops" / "live_process_census.json"


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
    # ALL launch spellings: the console script installed by com.dharma.swarm.plist
    # (`dgc orchestrate-live`), the module form used by the release runner
    # (`-m dharma_swarm.dgc_cli orchestrate-live`), and the container entrypoint
    # (`python -m dharma_swarm.orchestrate_live`, Dockerfile.swarm CMD).
    # Each omission has cost a false "daemon absent" on a healthy host: the
    # CLI-only pattern on containers, and this pattern on every launchd host
    # until 2026-08-03. Mirrored from
    # dharma_swarm/runtime_process_identity.ORCHESTRATE_COMMAND_NEEDLES — this
    # census stays import-free by design, so tests/test_runtime_command_forms.py
    # pins the mirror against the real launch definitions.
    "dharma_daemon": r"dgc orchestrate-live|dharma_swarm\.dgc_cli orchestrate-live|dharma_swarm\.orchestrate_live",
    "dharma_cron": r"dharma_swarm\.dgc_cli cron daemon",
    "nats": r"nats-server .*local-nats\.conf",
    "nats_a2a_bridge": r"dharma_swarm\.operator_core\.nats_a2a_bridge",
    "hermes_a2a": r"hermes_a2a_server\.py",
    "hermes_llm_bridge": r"hermes_llm_bridge\.py",
    "dashboard_api": r"uvicorn api\.main:app|api\.main:app",
    "dashboard_web": r"next-server|next dev|node .*:3420",
    "forge_hydra": r"codex_overnight_autopilot\.py|forge-reality-arena-master",
    "revenue_gate": r"revenue_wedge_gate",
    "cashclaw": r"cashclaw|CashClaw",
    "agni": r"kaizen_agni|agni-trading|ssh agni",
    "merge_master_mike": r"merge_master_mike|merge-master-mike",
    "terminal_tui": r"dharma_terminal_tui|terminal_tui_interaction|terminal.*start",
    "colima_openclaw": r"colima-openclaw-secure|qemu-system-aarch64 .*openclaw",
}


PORTS: dict[str, int] = {
    "dharma_daemon": 7433,
    "nats": 4222,
    "nats_monitor": 8222,
    "hermes_a2a": 8421,
    "hermes_llm_bridge": 9421,
    "dashboard_api": 8420,
    "dashboard_web": 3420,
}


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


def _process_snapshot(run_probes: bool) -> dict[str, list[dict[str, str]]]:
    if not run_probes:
        return {key: [] for key in PROCESS_PATTERNS}
    snapshot: dict[str, list[dict[str, str]]] = {}
    for key, pattern in PROCESS_PATTERNS.items():
        rc, out = _run(["pgrep", "-fl", pattern], timeout=4)
        snapshot[key] = _parse_pgrep(out) if rc == 0 else []
    return snapshot


def _port_snapshot(run_probes: bool) -> dict[str, dict[str, Any]]:
    if not run_probes:
        return {key: {"port": port, "listening": False, "evidence": ""} for key, port in PORTS.items()}
    snapshot: dict[str, dict[str, Any]] = {}
    for key, port in PORTS.items():
        rc, out = _run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], timeout=4)
        snapshot[key] = {
            "port": port,
            "listening": rc == 0 and bool(out.strip()),
            "evidence": out.splitlines()[-1] if rc == 0 and out.splitlines() else "",
        }
    return snapshot


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
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proc_rows = processes.get(process_key, []) if process_key and processes else []
    port = ports.get(process_key, {}) if process_key and ports else {}
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
    ports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the live-ops census as a pure data structure."""
    root = Path(repo_root)
    state = Path(state_root).expanduser()
    processes = processes if processes is not None else _process_snapshot(run_probes)
    ports = ports if ports is not None else _port_snapshot(run_probes)
    tmux = _tmux_sessions(run_probes)

    forge_heartbeat = state / "forge_reality_arena_master" / "codex_overnight_heartbeat.json"
    forge_handoff = state / "forge_reality_arena_master" / "shared" / "codex_overnight_handoff.md"
    forge_data = _read_json(forge_heartbeat)
    forge_freshness = str(forge_data.get("ts") or _iso_mtime(forge_heartbeat))
    forge_live = bool(processes.get("forge_hydra"))
    forge_status = "live" if forge_live else "stopped" if forge_heartbeat.exists() else "unknown"

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

    sources = _authority_sources(root)
    source_refs = [item["path"] for item in sources if item.get("exists")]
    a2a_root = state / "a2a_bus"
    a2a_receipts_root = a2a_root / "receipts"
    a2a_messages_root = a2a_root / "messages"
    a2a_queue = a2a_root / "tasks" / "queue.jsonl"
    latest_a2a_receipt = _latest_path(a2a_receipts_root, "**/*.json")
    latest_a2a_message = _latest_path(a2a_messages_root, "*.json")
    nats_receipts_root = state / "nats" / "receipts"
    latest_nats_receipt = _latest_path(nats_receipts_root, "*.json")
    nats_log = state / "nats" / "nats-server.log"
    nats_live_receipt = a2a_root / "nats_live_receipt.json"
    nats_contact_receipts = a2a_root / "nats_contact_receipts.jsonl"
    nats_oz_receipts = a2a_root / "nats_oz_receipts.jsonl"
    freshest_nats_evidence = _freshest_existing([
        latest_nats_receipt,
        nats_live_receipt,
        nats_contact_receipts,
        nats_oz_receipts,
        nats_log,
    ])

    surfaces = [
        _surface(
            surface_id="substrate.dharma_daemon",
            label="Dharma daemon",
            surface_class="substrate",
            status=_live_if_process_or_port("dharma_daemon", processes, ports),
            desired_state="live",
            evidence=["port:7433", "/Users/dhyana/.dharma/logs/swarm.log"],
            authority_refs=["docs/state/LIVE_OPS_DASHBOARD.md", "ACTIVE_SURFACE_MANIFEST.yaml"],
            priority="p0",
            process_key="dharma_daemon",
            processes=processes,
            ports=ports,
            restart_command="launchctl kickstart gui/$UID/com.dharma.swarm",
            stop_policy="do-not-stop-before-travel",
        ),
        _surface(
            surface_id="substrate.dharma_cron",
            label="Dharma cron daemon",
            surface_class="substrate",
            status="live" if processes.get("dharma_cron") else "stopped",
            desired_state="live",
            evidence=["dharma_swarm.dgc_cli cron daemon"],
            authority_refs=["scripts/governance/agent_onboard.py", "docs/governance/ACTIVE_TRACK.yaml"],
            priority="p0",
            process_key="dharma_cron",
            processes=processes,
            ports=ports,
            restart_command="launchctl kickstart gui/$UID/com.dharma.cron-daemon",
            stop_policy="do-not-stop-before-travel",
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
            label="NATS A2A bridge",
            surface_class="substrate",
            status="live" if processes.get("nats_a2a_bridge") else "stopped",
            desired_state="live",
            evidence=["dharma_swarm.operator_core.nats_a2a_bridge"],
            authority_refs=["docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"],
            priority="p0",
            process_key="nats_a2a_bridge",
            processes=processes,
            ports=ports,
            restart_command="make onboard  # verify persistent substrate",
            stop_policy="do-not-stop-if-A2A-needed",
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
            freshness=_iso_mtime(latest_a2a_receipt or latest_a2a_message or a2a_queue),
            stop_policy="mirror-only; do not treat as live-contact authority",
            next_action="inspect NATS ack receipts for live-contact proof",
            raw={
                "receipt_count": _count_files(a2a_receipts_root, "**/*.json"),
                "message_count": _count_files(a2a_messages_root, "*.json"),
                "queue_exists": a2a_queue.exists(),
            },
        ),
        _surface(
            surface_id="evidence.nats_receipts",
            label="NATS receipts and logs",
            surface_class="evidence",
            status="live" if freshest_nats_evidence else "unknown",
            desired_state="ack-receipt-evidence",
            evidence=[
                str(nats_receipts_root),
                str(nats_log),
                str(nats_live_receipt),
                str(nats_contact_receipts),
                str(nats_oz_receipts),
                f"latest_receipt={latest_nats_receipt}" if latest_nats_receipt else "",
            ],
            authority_refs=["docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"],
            priority="p0",
            freshness=_iso_mtime(freshest_nats_evidence or nats_log),
            stop_policy="receipt-only; NATS process lifecycle remains operator-controlled",
            next_action="verify ack tier before claiming live contact",
            raw={
                "receipt_count": _count_files(nats_receipts_root, "*.json"),
                "log_exists": nats_log.exists(),
                "nats_live_receipt_exists": nats_live_receipt.exists(),
                "nats_contact_receipts_exists": nats_contact_receipts.exists(),
                "nats_oz_receipts_exists": nats_oz_receipts.exists(),
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
            evidence=["127.0.0.1:8420", "127.0.0.1:3420", "scripts/dashboard_ctl.sh status"],
            authority_refs=["ACTIVE_SURFACE_MANIFEST.yaml", "docs/governance/CANONICAL_DOC_STACK.md"],
            priority="p0",
            process_key="dashboard_api",
            processes=processes,
            ports=ports,
            restart_command="bash scripts/dashboard_ctl.sh start",
            stop_policy="safe-to-restart-for-dashboard-work",
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
            desired_state="supervised",
            evidence=[str(forge_heartbeat), str(forge_handoff)],
            authority_refs=["docs/governance/ACTIVE_TRACK.yaml", "docs/ops/LIVE_OPS_COCKPIT.md"],
            priority="p1",
            freshness=forge_freshness,
            process_key="forge_hydra",
            processes=processes,
            ports=ports,
            restart_command="scripts/start_forge_hydra_long_run.sh",
            stop_policy="restart-only-after-reading-latest-handoff",
            next_action="read handoff before restart",
            raw={"heartbeat": forge_data},
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
            status="live" if processes.get("terminal_tui") else "stopped",
            desired_state="optional-cockpit",
            evidence=["scripts/status_terminal_tui_tmux.sh", "scripts/runtime/terminal_tui_interaction_smoke.py"],
            authority_refs=["docs/ops/TMUX_AGENT_SUBSTRATE.md", "specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md"],
            priority="p1",
            process_key="terminal_tui",
            processes=processes,
            ports=ports,
            restart_command="./scripts/start_terminal_tui_tmux.sh",
            stop_policy="optional; dashboard cockpit is primary tonight",
            next_action="restore only after dashboard truth lane is stable",
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
        "schema_version": "live_ops_census.v1",
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
        },
        "surfaces": surfaces,
        "source_refs": source_refs,
    }


def write_census(payload: dict[str, Any], output: Path = DEFAULT_OUTPUT) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
