#!/usr/bin/env python3
"""Read-only watchdog for dharma_swarm pulse-loop stalls.

Safe for cron/launchd. It never restarts, signals, or mutates the daemon
process. Its only write is the structured stale-pulse alert JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_STATE_DIR = Path.home() / ".dharma"
DEFAULT_ALERT_PATH = DEFAULT_STATE_DIR / "alerts" / "pulse_stall.json"
DEFAULT_HEALTH_BASE_URL = os.environ.get("DHARMA_HEALTH_URL", "http://127.0.0.1:7433").rstrip("/")
DEFAULT_STALE_SECONDS = 15 * 60


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_from_timestamp(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def read_int(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def pid_alive(pid: int | None) -> bool | None:
    if pid is None:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return None
    return True


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def pulse_log_candidates(state_dir: Path) -> tuple[Path, ...]:
    return (
        state_dir / "logs" / "pulse.log",
        state_dir / "pulse.log",
    )


def find_freshest_pulse_log(state_dir: Path) -> Path | None:
    existing = [path for path in pulse_log_candidates(state_dir) if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def read_tail(path: Path, max_bytes: int = 65536) -> str:
    with path.open("rb") as handle:
        size = path.stat().st_size
        handle.seek(max(0, size - max_bytes))
        return handle.read().decode("utf-8", errors="replace")


def parse_latest_record_time(path: Path) -> str | None:
    try:
        tail = read_tail(path)
    except Exception:
        return None
    pulse_headers = re.findall(r"--- PULSE @ ([^\s\]]+)", tail)
    if pulse_headers:
        return pulse_headers[-1]
    collected_at = re.findall(r'"collected_at"\s*:\s*"([^"]+)"', tail)
    if collected_at:
        return collected_at[-1]
    return None


def pulse_log_snapshot(state_dir: Path) -> dict[str, Any]:
    now = utc_now().timestamp()
    candidates: list[dict[str, Any]] = []
    for path in pulse_log_candidates(state_dir):
        item: dict[str, Any] = {"path": str(path), "exists": path.exists()}
        if path.exists():
            stat = path.stat()
            item.update(
                {
                    "modified_at": iso_from_timestamp(stat.st_mtime),
                    "age_seconds": max(0.0, now - stat.st_mtime),
                    "size_bytes": stat.st_size,
                    "latest_record_time": parse_latest_record_time(path),
                }
            )
        candidates.append(item)

    freshest = find_freshest_pulse_log(state_dir)
    if freshest is None:
        return {
            "exists": False,
            "freshest_path": None,
            "last_pulse_time": None,
            "age_seconds": None,
            "candidates": candidates,
        }

    stat = freshest.stat()
    return {
        "exists": True,
        "freshest_path": str(freshest),
        "last_pulse_time": iso_from_timestamp(stat.st_mtime),
        "age_seconds": max(0.0, now - stat.st_mtime),
        "size_bytes": stat.st_size,
        "latest_record_time": parse_latest_record_time(freshest),
        "candidates": candidates,
    }


def http_json(url: str, timeout: float) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(262144).decode("utf-8", errors="replace")
            try:
                payload: Any = json.loads(body)
            except json.JSONDecodeError:
                payload = None
            return {
                "ok": 200 <= int(response.status) < 300,
                "status_code": int(response.status),
                "elapsed_seconds": time.monotonic() - started,
                "json": payload,
            }
    except HTTPError as exc:
        return {"ok": False, "status_code": int(exc.code), "error": f"HTTPError: {exc}"}
    except (TimeoutError, URLError, OSError) as exc:
        return {"ok": False, "status_code": None, "error": f"{type(exc).__name__}: {exc}"}


def collect_health(base_url: str, timeout: float, include_metrics: bool) -> dict[str, Any]:
    endpoints = {"health": "/health", "loops": "/loops"}
    if include_metrics:
        endpoints["metrics"] = "/metrics"
    return {
        "base_url": base_url,
        "timeout_seconds": timeout,
        "endpoints": {name: http_json(f"{base_url}{path}", timeout) for name, path in endpoints.items()},
    }


def object_mentions_pulse(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any("pulse" in str(k).lower() or object_mentions_pulse(v) for k, v in obj.items())
    if isinstance(obj, list):
        return any(object_mentions_pulse(item) for item in obj)
    if isinstance(obj, str):
        return "pulse" in obj.lower()
    return False


def pulse_task_observation(health: dict[str, Any]) -> dict[str, Any]:
    reachable: list[str] = []
    pulse_sources: list[str] = []
    timed_out: list[str] = []
    errors: dict[str, str] = {}

    for name, result in health.get("endpoints", {}).items():
        if result.get("ok"):
            reachable.append(name)
            if object_mentions_pulse(result.get("json")):
                pulse_sources.append(name)
        else:
            error = str(result.get("error") or "unknown")
            errors[name] = error
            if "timed out" in error.lower() or "timeout" in error.lower():
                timed_out.append(name)

    if pulse_sources:
        status = "reported_by_health_endpoint"
        detail = "At least one reachable health endpoint includes pulse data."
    elif reachable:
        status = "not_reported_by_reachable_health_endpoints"
        detail = "Reachable health endpoints do not expose asyncio task membership or pulse-loop liveness."
    else:
        status = "health_unreachable"
        detail = "No health endpoint could be queried."

    return {
        "status": status,
        "detail": detail,
        "reachable_endpoints": reachable,
        "pulse_data_sources": pulse_sources,
        "timed_out_endpoints": timed_out,
        "errors": errors,
        "external_asyncio_task_visibility": (
            "unknown unless the daemon exports task state; OS thread probes cannot prove a Python asyncio task is alive."
        ),
    }


def discover_pid_from_ps() -> int | None:
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            pid_text, command = stripped.split(None, 1)
        except ValueError:
            continue
        if "orchestrate-live" in command and "pulse_watchdog.py" not in command:
            try:
                return int(pid_text)
            except ValueError:
                continue
    return None


def daemon_pid_from_health(health: dict[str, Any]) -> int | None:
    payload = health.get("endpoints", {}).get("health", {}).get("json")
    if not isinstance(payload, dict):
        return None
    try:
        return int(payload.get("daemon_pid"))
    except (TypeError, ValueError):
        return None


def resolve_daemon_pid(state_dir: Path, health: dict[str, Any]) -> dict[str, Any]:
    runtime_report = read_json(state_dir / "ops" / "daemon_runtime_dispatch_self_report.json")
    pid_sources = {
        "health_endpoint": daemon_pid_from_health(health),
        "daemon_pid_file": read_int(state_dir / "daemon.pid"),
        "runtime_dispatch_self_report": runtime_report.get("pid"),
        "ps_orchestrate_live_scan": discover_pid_from_ps(),
    }
    pid: int | None = None
    for value in pid_sources.values():
        try:
            if value is not None:
                pid = int(value)
                break
        except (TypeError, ValueError):
            continue
    return {
        "pid": pid,
        "alive": pid_alive(pid),
        "pid_sources": pid_sources,
        "runtime_dispatch_self_report": {
            "path": str(state_dir / "ops" / "daemon_runtime_dispatch_self_report.json"),
            "updated_at": runtime_report.get("updated_at"),
            "source": runtime_report.get("source"),
            "runtime_dispatch": runtime_report.get("runtime_dispatch"),
        },
    }


def proc_thread_probe(pid: int | None) -> dict[str, Any]:
    if pid is None:
        return {"status": "skipped", "reason": "daemon pid unknown"}

    task_dir = Path("/proc") / str(pid) / "task"
    if task_dir.exists():
        threads: list[dict[str, Any]] = []
        try:
            for tid_dir in sorted(task_dir.iterdir(), key=lambda p: p.name):
                status_path = tid_dir / "status"
                comm_path = tid_dir / "comm"
                state = None
                if status_path.exists():
                    for line in status_path.read_text(encoding="utf-8", errors="replace").splitlines():
                        if line.startswith("State:"):
                            state = line.split(":", 1)[1].strip()
                            break
                threads.append(
                    {
                        "tid": tid_dir.name,
                        "name": comm_path.read_text(encoding="utf-8", errors="replace").strip()
                        if comm_path.exists()
                        else None,
                        "state": state,
                    }
                )
        except Exception as exc:
            return {"status": "error", "source": "procfs", "error": f"{type(exc).__name__}: {exc}"}
        return {
            "status": "ok",
            "source": "procfs",
            "thread_count": len(threads),
            "threads_sample": threads[:64],
            "asyncio_task_visibility": "process threads only; Python asyncio tasks are not visible in procfs",
        }

    try:
        proc = subprocess.run(
            ["ps", "-M", "-p", str(pid), "-o", "pid,tid,stat,pcpu,time,command"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception as exc:
        return {
            "status": "error",
            "source": "ps -M",
            "error": f"{type(exc).__name__}: {exc}",
            "asyncio_task_visibility": "unavailable",
        }
    return {
        "status": "ok" if proc.returncode == 0 else "unavailable",
        "source": "ps -M",
        "returncode": proc.returncode,
        "stdout": proc.stdout[-12000:],
        "stderr": proc.stderr[-4000:],
        "asyncio_task_visibility": "process threads only; Python asyncio tasks are not visible in ps output",
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    state_dir = Path(args.state_dir).expanduser()
    health = collect_health(args.health_base_url.rstrip("/"), args.http_timeout, not args.skip_metrics)
    daemon = resolve_daemon_pid(state_dir, health)
    pulse_log = pulse_log_snapshot(state_dir)
    age_seconds = pulse_log.get("age_seconds")
    stale = not pulse_log.get("exists") or age_seconds is None or float(age_seconds) > float(args.stale_seconds)
    return {
        "schema": "dharma_swarm.watchdog.pulse_stall.v1",
        "timestamp": utc_now().isoformat(),
        "status": "stale" if stale else "fresh",
        "diagnostic_only": True,
        "restart_attempted": False,
        "threshold_seconds": float(args.stale_seconds),
        "daemon_pid": daemon.get("pid"),
        "last_pulse_time": pulse_log.get("last_pulse_time"),
        "age_seconds": age_seconds,
        "pulse_log": pulse_log,
        "daemon": daemon,
        "health_endpoint": health,
        "asyncio_pulse_task": pulse_task_observation(health),
        "thread_probe": proc_thread_probe(daemon.get("pid")),
    }


def write_alert(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether dharma_swarm pulse.log is stale.")
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument("--alert-path", default=str(DEFAULT_ALERT_PATH))
    parser.add_argument("--health-base-url", default=DEFAULT_HEALTH_BASE_URL)
    parser.add_argument("--stale-seconds", type=float, default=DEFAULT_STALE_SECONDS)
    parser.add_argument("--http-timeout", type=float, default=2.0)
    parser.add_argument("--skip-metrics", action="store_true", help="Skip /metrics probe if it is known to be slow.")
    parser.add_argument("--fail-on-stale", action="store_true", help="Exit 2 when stale. Default exits 0 for cron.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    report = build_report(args)
    if report["status"] == "stale":
        write_alert(Path(args.alert_path).expanduser(), report)
    print(json.dumps(report, sort_keys=True))
    if report["status"] == "stale" and args.fail_on_stale:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
