#!/usr/bin/env python3
"""Read-only AGNI hub readiness preflight.

This script observes the local AGNI hub surfaces and emits one JSON snapshot.
It does not start, stop, restart, message, mutate secrets, edit NATS config, or
create a second dispatcher.  The readiness claim is intentionally narrow:
broker/API/service/resource evidence only.  Agent rows and filesystem mirrors
are reported as evidence, not semantic liveness proof.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_ROOT = Path(os.environ.get("DHARMA_STATE_DIR", "~/.dharma")).expanduser()
DEFAULT_OUTPUT = DEFAULT_STATE_ROOT / "ops" / "agni_hub_readiness.json"
DEFAULT_API_BASE = "http://127.0.0.1:8420"
DEFAULT_NATS_JSZ_URL = "http://127.0.0.1:8222/jsz?streams=true&consumers=true"
DEFAULT_ROOT_PATH = Path("/")
DEFAULT_REQUIRED_SERVICES = (
    "nats.service",
    "openclaw.service",
    "dharma-a2a-agni-hermes-bridge.service",
    "dharma-codex-composer-agni-bridge.service",
    "dharma-remote-node.service",
)
OPTIONAL_SERVICES = (
    "sab-agora.service",
    "caddy.service",
)
AUTHORITY_REFS = (
    "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md",
    "docs/ops/MODEL_KEY_ROUTING.md",
    "docs/ops/TMUX_AGENT_SUBSTRATE.md",
    "scripts/governance/agent_onboard.py",
)

GIB = 1024**3
MEMORY_WARN_GIB = 1.5
MEMORY_FAIL_GIB = 0.75
DISK_WARN_USED_PCT = 75.0
DISK_FAIL_USED_PCT = 90.0
DISK_WARN_FREE_GIB = 20.0
DISK_FAIL_FREE_GIB = 10.0
AGENT_STALE_WARN_MINUTES = 60


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _age_minutes(value: object, *, now: datetime | None = None) -> float | None:
    parsed = _parse_iso(value)
    if parsed is None:
        return None
    reference = now or datetime.now(UTC)
    return round((reference - parsed).total_seconds() / 60.0, 2)


def _json_url(url: str, *, timeout: float) -> tuple[dict[str, Any] | None, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except (OSError, urllib.error.URLError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"JSONDecodeError: {exc}"
    if not isinstance(parsed, dict):
        return None, "payload is not a JSON object"
    return parsed, ""


def _run(args: list[str], *, timeout: float = 5.0) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)
    return proc.returncode, proc.stdout.strip()


def _memory_snapshot() -> dict[str, Any]:
    info: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if ":" not in line:
                continue
            key, raw = line.split(":", 1)
            parts = raw.strip().split()
            if parts and parts[0].isdigit():
                info[key] = int(parts[0]) * 1024
    except OSError:
        return {"available": False, "error": "could not read /proc/meminfo"}

    total = info.get("MemTotal", 0)
    available = info.get("MemAvailable", 0)
    swap_total = info.get("SwapTotal", 0)
    swap_free = info.get("SwapFree", 0)
    swap_used = max(swap_total - swap_free, 0)
    return {
        "available": True,
        "total_bytes": total,
        "available_bytes": available,
        "available_gib": round(available / GIB, 2),
        "swap_total_bytes": swap_total,
        "swap_used_bytes": swap_used,
        "swap_used_gib": round(swap_used / GIB, 2),
    }


def _disk_snapshot(path: Path = DEFAULT_ROOT_PATH) -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        return {"available": False, "path": str(path), "error": str(exc)}
    used_pct = (usage.used / usage.total * 100.0) if usage.total else 0.0
    return {
        "available": True,
        "path": str(path),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "free_gib": round(usage.free / GIB, 2),
        "used_pct": round(used_pct, 2),
    }


def _service_snapshot(services: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    if shutil.which("systemctl") is None:
        return {
            service: {"status": "unknown", "error": "systemctl not available"}
            for service in services
        }
    rows: dict[str, dict[str, Any]] = {}
    for service in services:
        rc, out = _run(["systemctl", "is-active", service], timeout=4)
        state = out.splitlines()[0].strip() if out else "unknown"
        rows[service] = {"status": state, "active": rc == 0 and state == "active"}
    return rows


def _bridge_heartbeat(state_root: Path) -> dict[str, Any]:
    path = state_root / "a2a_bus" / "bridge_heartbeats" / "agni.json"
    if not path.exists():
        return {"exists": False, "path": str(path)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"exists": True, "path": str(path), "error": str(exc)}
    if not isinstance(data, dict):
        return {"exists": True, "path": str(path), "error": "heartbeat is not object"}
    ts = data.get("timestamp")
    return {
        "exists": True,
        "path": str(path),
        "timestamp": ts,
        "age_minutes": _age_minutes(ts),
        "status": data.get("status", ""),
        "semantic_reply_capable": bool(data.get("semantic_reply_capable")),
    }


def _check(check_id: str, status: str, summary: str, **details: Any) -> dict[str, Any]:
    return {"id": check_id, "status": status, "summary": summary, "details": details}


def _evaluate_nats(jsz: dict[str, Any] | None, error: str) -> dict[str, Any]:
    if error:
        return _check("nats.jetstream", "fail", "NATS JetStream monitor unreachable", error=error)
    if jsz is None:
        return _check("nats.jetstream", "fail", "NATS JetStream monitor returned no data")
    streams = int(jsz.get("streams") or 0)
    consumers = int(jsz.get("consumers") or 0)
    messages = int(jsz.get("messages") or 0)
    storage = int(jsz.get("storage") or 0)
    status = "ok" if streams > 0 else "warn"
    summary = (
        f"JetStream reachable: streams={streams}, consumers={consumers}, "
        f"messages={messages}"
    )
    return _check(
        "nats.jetstream",
        status,
        summary,
        streams=streams,
        consumers=consumers,
        messages=messages,
        storage_bytes=storage,
    )


def _evaluate_agents(payload: dict[str, Any] | None, error: str) -> dict[str, Any]:
    if error:
        return _check("api.agents", "fail", "local agent API unreachable", error=error)
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return _check("api.agents", "fail", "local agent API returned invalid data")
    count = len(rows)
    stale_count = 0
    heartbeat_ages: list[float] = []
    providers: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        providers[str(row.get("provider") or "unknown")] = (
            providers.get(str(row.get("provider") or "unknown"), 0) + 1
        )
        age = _age_minutes(row.get("last_heartbeat"))
        if age is None:
            continue
        heartbeat_ages.append(age)
        if age > AGENT_STALE_WARN_MINUTES:
            stale_count += 1
    if count == 0:
        return _check("api.agents", "warn", "agent API reachable but no agents registered")
    if stale_count == count and count > 0:
        status = "warn"
        summary = "agent rows exist, but all observed heartbeats are stale"
    else:
        status = "ok"
        summary = f"agent API reports {count} agent rows"
    return _check(
        "api.agents",
        status,
        summary,
        count=count,
        stale_count=stale_count,
        max_heartbeat_age_minutes=max(heartbeat_ages) if heartbeat_ages else None,
        providers=providers,
        semantic_liveness_claim=False,
    )


def _evaluate_fleet(payload: dict[str, Any] | None, error: str) -> dict[str, Any]:
    if error:
        return _check("api.fleet_nodes", "fail", "fleet node API unreachable", error=error)
    nodes = payload.get("nodes", []) if isinstance(payload, dict) else []
    if not isinstance(nodes, list):
        return _check("api.fleet_nodes", "fail", "fleet node API returned invalid data")
    online = [
        node for node in nodes
        if isinstance(node, dict) and str(node.get("status") or "") in {"online", "degraded"}
    ]
    if not nodes:
        return _check("api.fleet_nodes", "warn", "fleet registry has no nodes")
    status = "ok" if online else "warn"
    return _check(
        "api.fleet_nodes",
        status,
        f"fleet registry nodes={len(nodes)}, reachable={len(online)}",
        count=len(nodes),
        reachable_count=len(online),
        node_ids=[str(node.get("node_id") or "") for node in nodes if isinstance(node, dict)],
    )


def _evaluate_services(services: dict[str, dict[str, Any]]) -> dict[str, Any]:
    inactive = [name for name, row in services.items() if not row.get("active")]
    status = "ok" if not inactive else "fail"
    summary = "required systemd services active" if not inactive else "required services inactive"
    return _check("systemd.required", status, summary, inactive=inactive, services=services)


def _evaluate_resources(memory: dict[str, Any], disk: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    if not memory.get("available"):
        warnings.append("memory_unknown")
    else:
        mem_gib = float(memory.get("available_gib") or 0.0)
        if mem_gib < MEMORY_FAIL_GIB:
            failures.append("memory_low")
        elif mem_gib < MEMORY_WARN_GIB:
            warnings.append("memory_low")

    if not disk.get("available"):
        warnings.append("disk_unknown")
    else:
        used_pct = float(disk.get("used_pct") or 0.0)
        free_gib = float(disk.get("free_gib") or 0.0)
        if used_pct >= DISK_FAIL_USED_PCT or free_gib < DISK_FAIL_FREE_GIB:
            failures.append("disk_pressure")
        elif used_pct >= DISK_WARN_USED_PCT or free_gib < DISK_WARN_FREE_GIB:
            warnings.append("disk_pressure")

    if failures:
        status = "fail"
        summary = "resource pressure crosses fail threshold"
    elif warnings:
        status = "warn"
        summary = "resource pressure should be watched"
    else:
        status = "ok"
        summary = "memory and disk headroom are acceptable"
    return _check("host.resources", status, summary, failures=failures, warnings=warnings, memory=memory, disk=disk)


def _evaluate_bridge_heartbeat(heartbeat: dict[str, Any]) -> dict[str, Any]:
    if not heartbeat.get("exists"):
        return _check(
            "a2a.bridge_heartbeat",
            "warn",
            "AGNI bridge heartbeat file missing",
            heartbeat=heartbeat,
        )
    if heartbeat.get("error"):
        return _check("a2a.bridge_heartbeat", "warn", "AGNI bridge heartbeat unreadable", heartbeat=heartbeat)
    age = heartbeat.get("age_minutes")
    if isinstance(age, (int, float)) and age > AGENT_STALE_WARN_MINUTES:
        return _check("a2a.bridge_heartbeat", "warn", "AGNI bridge heartbeat is stale", heartbeat=heartbeat)
    return _check("a2a.bridge_heartbeat", "ok", "AGNI bridge heartbeat is present", heartbeat=heartbeat)


def _overall_status(checks: list[dict[str, Any]]) -> str:
    statuses = {str(check.get("status")) for check in checks}
    if "fail" in statuses:
        return "blocked"
    if "warn" in statuses:
        return "degraded"
    return "ready"


def build_agni_hub_readiness(
    *,
    repo_root: Path | str = DEFAULT_REPO_ROOT,
    state_root: Path | str = DEFAULT_STATE_ROOT,
    api_base: str = DEFAULT_API_BASE,
    nats_jsz_url: str = DEFAULT_NATS_JSZ_URL,
    root_path: Path = DEFAULT_ROOT_PATH,
    timeout: float = 5.0,
    required_services: tuple[str, ...] = DEFAULT_REQUIRED_SERVICES,
    optional_services: tuple[str, ...] = OPTIONAL_SERVICES,
    nats_jsz_payload: dict[str, Any] | None = None,
    nats_jsz_error: str = "",
    agents_payload: dict[str, Any] | None = None,
    agents_error: str = "",
    fleet_payload: dict[str, Any] | None = None,
    fleet_error: str = "",
    services_payload: dict[str, dict[str, Any]] | None = None,
    memory_payload: dict[str, Any] | None = None,
    disk_payload: dict[str, Any] | None = None,
    bridge_heartbeat_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a read-only AGNI hub readiness snapshot."""

    repo = Path(repo_root)
    state = Path(state_root).expanduser()

    if nats_jsz_payload is None and not nats_jsz_error:
        nats_jsz_payload, nats_jsz_error = _json_url(nats_jsz_url, timeout=timeout)
    if agents_payload is None and not agents_error:
        agents_payload, agents_error = _json_url(
            f"{api_base.rstrip('/')}/api/agents",
            timeout=timeout,
        )
    if fleet_payload is None and not fleet_error:
        fleet_payload, fleet_error = _json_url(
            f"{api_base.rstrip('/')}/api/fleet/nodes",
            timeout=timeout,
        )

    services = services_payload or _service_snapshot(required_services)
    optional = _service_snapshot(optional_services)
    memory = memory_payload or _memory_snapshot()
    disk = disk_payload or _disk_snapshot(root_path)
    heartbeat = bridge_heartbeat_payload or _bridge_heartbeat(state)

    checks = [
        _evaluate_nats(nats_jsz_payload, nats_jsz_error),
        _evaluate_agents(agents_payload, agents_error),
        _evaluate_fleet(fleet_payload, fleet_error),
        _evaluate_services(services),
        _evaluate_resources(memory, disk),
        _evaluate_bridge_heartbeat(heartbeat),
    ]
    status = _overall_status(checks)
    return {
        "schema_version": "agni_hub_readiness.v1",
        "generated_at": utc_now(),
        "status": status,
        "repo_root": str(repo),
        "state_root": str(state),
        "authority_refs": [str(repo / ref) for ref in AUTHORITY_REFS],
        "inputs": {
            "api_base": api_base,
            "nats_jsz_url": nats_jsz_url,
            "required_services": list(required_services),
            "optional_services": list(optional_services),
        },
        "summary": {
            "checks_total": len(checks),
            "checks_failed": sum(1 for check in checks if check["status"] == "fail"),
            "checks_warn": sum(1 for check in checks if check["status"] == "warn"),
            "semantic_liveness_claim": False,
            "mutation_claim": False,
        },
        "checks": checks,
        "optional_services": optional,
    }


def write_readiness(payload: dict[str, Any], output: Path = DEFAULT_OUTPUT) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _print_human(payload: dict[str, Any]) -> None:
    print(f"AGNI hub readiness: {payload['status']}")
    for check in payload["checks"]:
        print(f"  [{check['status']}] {check['id']}: {check['summary']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only AGNI hub readiness preflight.")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--nats-jsz-url", default=DEFAULT_NATS_JSZ_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--write", action="store_true", help="write JSON to --output")
    parser.add_argument("--human", action="store_true", help="print a compact human summary")
    args = parser.parse_args(argv)

    payload = build_agni_hub_readiness(
        repo_root=args.repo_root,
        state_root=args.state_root,
        api_base=args.api_base,
        nats_jsz_url=args.nats_jsz_url,
        timeout=max(args.timeout, 0.1),
    )
    if args.write:
        print(write_readiness(payload, args.output))
    elif args.human:
        _print_human(payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
