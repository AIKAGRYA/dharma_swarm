#!/usr/bin/env python3
"""Watch the same NATS transport used by the local Hermes bridge.

Empty stdout means healthy. Any output is a local incident alert.
Only the configured transport endpoint is consumed; credentials are never emitted.
"""

from __future__ import annotations

import datetime as dt
import json
import socket
import subprocess
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path

BRIDGE_ENV = Path("/root/.dharma/nats/remote_agent_bridge.env")
HEARTBEAT = Path("/root/.dharma/a2a_bus/bridge_heartbeats/rushabdev.json")
STATE = Path("/root/.hermes/state/agni_nats_watchdog_state.json")
MAX_HEARTBEAT_AGE_SECONDS = 150


def transport_endpoint(config: Path) -> tuple[str, int]:
    """Resolve the bridge transport without echoing credential-bearing config."""
    for raw in config.read_text().splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        if sep and key.strip() == "NATS_URL":
            parsed = urlsplit(value.strip().strip("\"'"))
            if parsed.scheme != "nats" or not parsed.hostname:
                raise ValueError("bridge requires a supported nats transport URL")
            return parsed.hostname, parsed.port or 4222
    raise ValueError("bridge NATS_URL is missing")


def tcp_probe(host: str, port: int, *, read_banner: bool = False) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=4) as sock:
            if not read_banner:
                return True, ""
            sock.settimeout(2)
            return True, sock.recv(4096).decode("utf-8", "replace")
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def service_active(name: str) -> bool:
    proc = subprocess.run(
        ["systemctl", "is-active", name],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return proc.stdout.strip() == "active"


def gateway_health() -> tuple[bool, str]:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8422/health", timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
        return bool(response.status == 200 and body.get("ok") is True), json.dumps(body)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def recent_gateway_errors() -> list[str]:
    proc = subprocess.run(
        [
            "journalctl",
            "-u",
            "dharma-a2a-mailbox-gateway",
            "--since",
            "6 minutes ago",
            "--no-pager",
            "-o",
            "cat",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    needles = (
        "502 Bad Gateway",
        "503 Service Unavailable",
        "JetStream system temporarily unavailable",
        "err_code=10008",
    )
    return [line.strip() for line in proc.stdout.splitlines() if any(n in line for n in needles)][-5:]


def parse_timestamp(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    problems: list[str] = []

    try:
        host, port = transport_endpoint(BRIDGE_ENV)
    except (OSError, ValueError):
        host, port = None, None
        problems.append("bridge_transport_configuration_invalid")
    core_open, banner = tcp_probe(host, port, read_banner=True) if host else (False, "")
    if not core_open:
        if host:
            problems.append(f"bridge_transport_down:{host}:{port}:{banner}")
    else:
        payload = banner.strip()
        if payload.startswith("INFO "):
            try:
                info = json.loads(payload[5:].strip())
                if not info.get("jetstream"):
                    problems.append("jetstream_not_advertised")
            except json.JSONDecodeError:
                problems.append("invalid_nats_info_banner")
        else:
            problems.append("missing_nats_info_banner")

    for service in (
        "dharma-a2a-nats-tunnel",
        "dharma-a2a-rushabdev-hermes-bridge",
        "dharma-a2a-mailbox-gateway",
    ):
        if not service_active(service):
            problems.append(f"service_inactive:{service}")

    if not HEARTBEAT.exists():
        problems.append("bridge_heartbeat_missing")
    else:
        try:
            heartbeat = json.loads(HEARTBEAT.read_text())
            age = (now - parse_timestamp(str(heartbeat["timestamp"]))).total_seconds()
            if age > MAX_HEARTBEAT_AGE_SECONDS:
                problems.append(f"bridge_heartbeat_stale:{int(age)}s")
        except Exception as exc:
            problems.append(f"bridge_heartbeat_invalid:{type(exc).__name__}")

    health_ok, health_detail = gateway_health()
    if not health_ok:
        problems.append(f"gateway_unhealthy:{health_detail}")

    errors = recent_gateway_errors()
    if errors:
        problems.append(f"recent_gateway_errors:{len(errors)}")

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(
        json.dumps(
            {
                "checked_at": now.isoformat().replace("+00:00", "Z"),
                "healthy": not problems,
                "problems": problems,
                "monitoring_limitations": [
                    "rushabdev_hermes lacks JetStream management/API visibility",
                    "semantic AGNI responsiveness is tested separately, not every tick",
                ],
            },
            indent=2,
        )
        + "\n"
    )

    if problems:
        print("AGNI_NATS_INCIDENT " + " | ".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
