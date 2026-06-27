"""Swarm Health API — lightweight HTTP health + metrics endpoint for dgc orchestrate-live.

Exposes:
    GET /health         → liveness probe (k8s/launchd compatible)
    GET /metrics        → structured JSON metrics for dashboards
    GET /loops          → status of all 15 concurrent loops
    GET /providers      → current provider chain + circuit breaker state
    GET /runtime-context → agent startup packet with live provider/runtime truth
    GET /telos          → TelosGraph progress summary
    GET /archaeology    → latest lessons_learned.md excerpt

Starts on port 7433 (configurable via DHARMA_API_PORT) as a background task
in orchestrate_live.py. All endpoints are read-only — no mutation exposed.

Usage:
    # Called from orchestrate_live task_factories:
    "health-api": lambda: run_health_api(shutdown_event),

    # Check from anywhere:
    curl http://localhost:7433/health
    curl http://localhost:7433/metrics | python3 -m json.tool
"""
from __future__ import annotations

import asyncio
import json
import logging
import multiprocessing
import os
import queue as queue_module
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from dharma_swarm.daemon_config import dharma_state_dir

logger = logging.getLogger(__name__)

_PORT = int(os.environ.get("DHARMA_API_PORT", "7433"))
_STATE_DIR = dharma_state_dir("DHARMA_STATE_DIR")
_START_TIME = time.monotonic()
_DAEMON_PARENT_PID: int | None = None


def _uptime() -> str:
    elapsed = int(time.monotonic() - _START_TIME)
    h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_lines(path: Path, n: int = 10) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()[-n:]
    except Exception:
        return []


def _loop_status() -> list[dict]:
    """Check which loops have live artifacts."""
    checks = [
        ("evolution", _STATE_DIR / "evolution" / "archive.jsonl"),
        ("stigmergy", _STATE_DIR / "stigmergy" / "marks.jsonl"),
        ("telos", _STATE_DIR / "telos" / "objectives.jsonl"),
        ("memory-palace", _STATE_DIR / "memory" / "palace.db"),
        ("knowledge-store", _STATE_DIR / "db" / "knowledge_store.db"),
        ("archaeology", _STATE_DIR / "meta" / "lessons_learned.md"),
        ("guardian", _STATE_DIR / "guardian" / "GUARDIAN_REPORT.md"),
        ("gnani", _STATE_DIR / "meta" / "gnani_seeded"),
        ("telos-substrate", _STATE_DIR / "meta" / "telos_seeded"),
        ("sub-swarms", _STATE_DIR / "sub_swarms"),
    ]
    result = []
    for name, path in checks:
        exists = path.exists()
        age_h = None
        if exists and path.is_file():
            age_h = round((time.time() - path.stat().st_mtime) / 3600, 1)
        result.append({
            "loop": name,
            "artifact_exists": exists,
            "age_hours": age_h,
            "status": "ok" if exists else "no-data",
        })
    return result


def _provider_status() -> dict:
    cb_path = _STATE_DIR / "meta" / "circuit_breakers.json"
    return {
        "circuit_breakers": _read_json(cb_path),
        "shadow_mode": os.environ.get("DHARMA_EVOLUTION_SHADOW", "1") == "1",
        "autonomy_level": int(os.environ.get("DGC_AUTONOMY_LEVEL", "1")),
    }


def _runtime_dispatch_status() -> dict:
    """Non-secret runtime dispatch mode for daemon/default proof."""
    enabled = os.environ.get("DHARMA_SPINE_DISPATCH") == "1"
    return {
        "spine_dispatch_enabled": enabled,
        "dispatch_mode": "spine" if enabled else "legacy",
        "env_key_present": "DHARMA_SPINE_DISPATCH" in os.environ,
        "source": "process_env_non_secret_boolean",
    }


def _runtime_truth_status() -> dict[str, Any]:
    """Live runtime truth closeout for the daemon-local operator endpoint."""
    try:
        from scripts.runtime.runtime_truth_closeout import (
            _build_census,
            evaluate_closeout,
        )

        repo_root = Path(__file__).resolve().parents[1]
        census = _build_census(repo_root, _STATE_DIR)
        return evaluate_closeout(census, state_root=_STATE_DIR)
    except Exception as exc:
        return {
            "schema_version": "runtime_truth_closeout.v1",
            "status": "error",
            "passed": False,
            "state_root": str(_STATE_DIR),
            "error": f"{type(exc).__name__}: {exc}",
            "checks": [
                {
                    "id": "runtime_truth_endpoint_available",
                    "status": "fail",
                    "passed": False,
                    "evidence": f"{type(exc).__name__}: {exc}",
                }
            ],
        }


def _runtime_context_packet() -> dict[str, Any]:
    try:
        from dharma_swarm.runtime_context import build_runtime_context_packet

        return build_runtime_context_packet(
            repo_root=Path(__file__).resolve().parents[1],
            state_dir=_STATE_DIR,
            health=_health_payload(),
            runtime_truth=_runtime_truth_status(),
            provider_status=_provider_status(),
        )
    except Exception as exc:
        return {
            "schema": "dharma_swarm.runtime_context.v1",
            "generated_at": _utc_now(),
            "authority": "projection_only",
            "secrets_included": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _process_alive(pid: int | None) -> bool | None:
    if not pid:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _health_payload() -> dict[str, Any]:
    daemon_alive = _process_alive(_DAEMON_PARENT_PID)
    payload: dict[str, Any] = {
        "status": "ok" if daemon_alive is not False else "degraded",
        "uptime": _uptime(),
        "timestamp": _utc_now(),
        "version": "dharma_swarm",
        "runtime_dispatch": _runtime_dispatch_status(),
        "health_process_pid": os.getpid(),
    }
    if _DAEMON_PARENT_PID:
        payload["daemon_pid"] = _DAEMON_PARENT_PID
        payload["daemon_process_alive"] = daemon_alive
    return payload


def _telos_summary() -> dict:
    obj_path = _STATE_DIR / "telos" / "objectives.jsonl"
    if not obj_path.exists():
        return {"status": "no-data"}
    try:
        lines = [line for line in obj_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        objs = [json.loads(line) for line in lines]
        total = len(objs)
        active = sum(1 for o in objs if o.get("status") == "active")
        avg_progress = sum(o.get("progress", 0) for o in objs) / total if total else 0
        high_priority = sorted(
            [o for o in objs if o.get("priority", 0) >= 8],
            key=lambda o: -o.get("progress", 0)
        )[:5]
        return {
            "total_objectives": total,
            "active": active,
            "avg_progress": round(avg_progress, 3),
            "top_objectives": [
                {"name": o.get("name", "")[:60], "progress": o.get("progress", 0)}
                for o in high_priority
            ],
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _evolution_summary() -> dict:
    arch = _STATE_DIR / "evolution" / "archive.jsonl"
    if not arch.exists():
        return {"status": "no-data"}
    try:
        lines = [line for line in arch.read_text(encoding="utf-8").splitlines() if line.strip()]
        entries = [json.loads(line) for line in lines[-200:]]
        applied = sum(1 for e in entries if e.get("status") == "applied")
        rolled = sum(1 for e in entries if e.get("status") == "rolled_back")
        return {
            "total_entries": len(lines),
            "recent_applied": applied,
            "recent_rolled_back": rolled,
            "shadow_mode": os.environ.get("DHARMA_EVOLUTION_SHADOW", "1") == "1",
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _response_for_path(path: str) -> tuple[str, str]:
    if path == "/health" or path == "/":
        payload = _health_payload()
        status = "200 OK" if payload["status"] == "ok" else "503 Service Unavailable"
        return (
            status,
            json.dumps(payload),
        )

    if path == "/metrics":
        return (
            "200 OK",
            json.dumps({
                "uptime": _uptime(),
                "timestamp": _utc_now(),
                "loops": _loop_status(),
                "evolution": _evolution_summary(),
                "providers": _provider_status(),
                "runtime_dispatch": _runtime_dispatch_status(),
                "runtime_truth": _runtime_truth_status(),
                "telos": _telos_summary(),
            }, indent=2),
        )

    if path == "/runtime-truth":
        payload = _runtime_truth_status()
        return (
            "200 OK" if payload.get("passed") is True else "503 Service Unavailable",
            json.dumps(payload, indent=2),
        )

    if path == "/runtime-context":
        return "200 OK", json.dumps(_runtime_context_packet(), indent=2)

    if path == "/loops":
        return "200 OK", json.dumps(_loop_status(), indent=2)

    if path == "/providers":
        return "200 OK", json.dumps(_provider_status(), indent=2)

    if path == "/telos":
        return "200 OK", json.dumps(_telos_summary(), indent=2)

    if path == "/archaeology":
        lessons = _STATE_DIR / "meta" / "lessons_learned.md"
        excerpt = "\n".join(_read_lines(lessons, 30)) if lessons.exists() else "No lessons yet."
        return "200 OK", json.dumps({"lessons_excerpt": excerpt, "timestamp": _utc_now()})

    if path == "/guardian":
        report = _STATE_DIR / "guardian" / "GUARDIAN_REPORT.md"
        content = report.read_text(encoding="utf-8", errors="ignore") if report.exists() else "No report yet."
        return "200 OK", json.dumps({"report": content[:5000], "timestamp": _utc_now()})

    return "404 Not Found", json.dumps({"error": "not found", "path": path})


class _ThreadedHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        status, body = _response_for_path(urlsplit(self.path).path)
        code_text, message = status.split(" ", 1)
        payload = body.encode()
        self.send_response(int(code_text), message)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("Health API request: " + format, *args)


@dataclass
class HealthAPIServerHandle:
    server: ThreadingHTTPServer
    thread: threading.Thread
    host: str
    port: int

    def close(self, timeout: float = 2.0) -> None:
        self.server.server_close()
        self.thread.join(timeout=timeout)


@dataclass
class HealthAPIProcessHandle:
    process: multiprocessing.Process
    host: str
    port: int
    daemon_pid: int

    def close(self, timeout: float = 2.0) -> None:
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(timeout=timeout)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(timeout=timeout)


def start_health_api_thread(
    shutdown_event: Any,
    *,
    host: str = "127.0.0.1",
    port: int = _PORT,
) -> HealthAPIServerHandle:
    """Start the health API in a small thread independent of the asyncio loop."""
    server = ThreadingHTTPServer((host, port), _ThreadedHealthHandler)
    server.timeout = 0.5
    actual_port = int(server.server_address[1])

    def _serve() -> None:
        logger.info("Swarm health API listening on http://%s:%d", host, actual_port)
        try:
            while not shutdown_event.is_set():
                server.handle_request()
        finally:
            server.server_close()
            logger.info("Swarm health API stopped")

    thread = threading.Thread(
        target=_serve,
        name="dharma-swarm-health-api",
        daemon=True,
    )
    thread.start()
    return HealthAPIServerHandle(server=server, thread=thread, host=host, port=actual_port)


def _serve_health_api_process(
    host: str,
    port: int,
    daemon_pid: int,
    ready_queue: multiprocessing.Queue,
) -> None:
    global _DAEMON_PARENT_PID
    _DAEMON_PARENT_PID = daemon_pid
    server: ThreadingHTTPServer | None = None
    try:
        server = ThreadingHTTPServer((host, port), _ThreadedHealthHandler)
        server.timeout = 0.5
        actual_port = int(server.server_address[1])
        ready_queue.put({"ok": True, "port": actual_port})
        logger.info("Swarm health API listening on http://%s:%d", host, actual_port)
        while _process_alive(daemon_pid) is not False:
            server.handle_request()
        logger.info("Daemon parent PID %d exited; stopping health API", daemon_pid)
    except BaseException as exc:
        try:
            ready_queue.put({"ok": False, "error": str(exc)})
        except Exception:
            pass
        raise
    finally:
        if server is not None:
            server.server_close()
        logger.info("Swarm health API stopped")


def start_health_api_process(
    *,
    host: str = "127.0.0.1",
    port: int = _PORT,
    daemon_pid: int | None = None,
    startup_timeout: float = 5.0,
) -> HealthAPIProcessHandle:
    """Start the health API in a child process so daemon CPU work cannot starve it."""
    parent_pid = int(daemon_pid or os.getpid())
    ready_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=1)
    process = multiprocessing.Process(
        target=_serve_health_api_process,
        args=(host, port, parent_pid, ready_queue),
        name="dharma-swarm-health-api",
        daemon=True,
    )
    process.start()
    try:
        ready = ready_queue.get(timeout=startup_timeout)
    except queue_module.Empty as exc:
        process.terminate()
        process.join(timeout=1.0)
        raise RuntimeError("health API process did not report startup") from exc
    if not ready.get("ok"):
        process.join(timeout=1.0)
        error = ready.get("error") or "unknown startup failure"
        raise RuntimeError(f"health API process failed to start: {error}")
    return HealthAPIProcessHandle(
        process=process,
        host=host,
        port=int(ready["port"]),
        daemon_pid=parent_pid,
    )


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Handle one HTTP request — minimal HTTP/1.1 server without dependencies."""
    try:
        raw = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        request = raw.decode(errors="ignore")
        first_line = request.splitlines()[0] if request.splitlines() else ""
        method, path_qs, *_ = (first_line.split() + ["", ""])[:3]
        path = path_qs.split("?")[0]

        status, body = _response_for_path(path)

        response = (
            f"HTTP/1.1 {status}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body.encode())}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{body}"
        )
        writer.write(response.encode())
        await writer.drain()
    except Exception as exc:
        logger.debug("Health API request failed: %s", exc)
    finally:
        writer.close()


async def run_health_api(shutdown_event: asyncio.Event) -> None:
    """Run the health API server until shutdown."""
    try:
        server = await asyncio.start_server(_handle, "0.0.0.0", _PORT)
        logger.info("Swarm health API listening on http://0.0.0.0:%d", _PORT)
        async with server:
            await shutdown_event.wait()
        logger.info("Swarm health API stopped")
    except OSError as exc:
        logger.warning("Health API failed to start on port %d: %s", _PORT, exc)
    except Exception as exc:
        logger.error("Health API crashed: %s", exc)
