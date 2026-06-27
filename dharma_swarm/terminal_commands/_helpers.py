"""Shared utilities for terminal commands."""

from __future__ import annotations

from dharma_swarm.daemon_config import dharma_state_dir
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import asyncio
import json
import os
import subprocess

HOME = Path.home()
DHARMA_STATE = dharma_state_dir()
DHARMA_SWARM = HOME / "dharma_swarm"
DGC_CORE = HOME / "dgc-core"
DEFAULT_SPRINT_LLM_TIMEOUT_SEC = 12.0



def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(errors="ignore").splitlines()
    except Exception:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (
            len(value) >= 2
            and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'"))
        ):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _bootstrap_env() -> None:
    # Load dharma_swarm defaults and optional local runtime overrides.
    _load_env_file(HOME / "dharma_swarm" / ".env")
    _load_env_file(HOME / ".dharma" / "env" / "nvidia_remote.env")


_bootstrap_env()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro: Any) -> Any:
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _load_json_object(
    *,
    json_payload: str | None = None,
    file_path: str | None = None,
    label: str = "JSON payload",
) -> dict[str, Any]:
    if json_payload is None and file_path is None:
        raise ValueError(f"{label} is required")

    raw = json_payload
    if file_path is not None:
        raw = Path(file_path).read_text(encoding="utf-8")

    try:
        payload = json.loads(raw if raw is not None else "")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {exc.msg}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"{label} must decode to a JSON object")
    return payload


def _normalize_optional_text(value: str | None, *, default: str = "") -> str:
    normalized = str(value or "").strip()
    return normalized or default


def _default_ouroboros_log_path() -> Path:
    candidates = (
        DHARMA_STATE / "evolution" / "observations" / "ouroboros_log.jsonl",
        DHARMA_STATE / "evolution" / "ouroboros_log.jsonl",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _load_ouroboros_observation(
    *,
    log_path: Path,
    cycle_id: str | None = None,
) -> dict[str, Any]:
    if not log_path.exists():
        raise FileNotFoundError(f"ouroboros log not found: {log_path}")

    selected: dict[str, Any] | None = None
    for line_no, raw_line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"ouroboros log {log_path} contains invalid JSON on line {line_no}"
            ) from exc
        if not isinstance(decoded, dict):
            raise ValueError(
                f"ouroboros log {log_path} contains a non-object JSON record on line {line_no}"
            )
        if cycle_id:
            if str(decoded.get("cycle_id") or "").strip() == cycle_id:
                selected = decoded
        else:
            selected = decoded

    if selected is None:
        if cycle_id:
            raise ValueError(f"no ouroboros observation found for cycle_id={cycle_id}")
        raise ValueError(f"no ouroboros observations found in {log_path}")
    return selected


async def _get_swarm(state_dir: str = ".dharma"):
    from dharma_swarm.swarm import SwarmManager

    swarm = SwarmManager(state_dir=state_dir)
    await swarm.init()
    return swarm


async def _get_task_board(state_dir: str = ".dharma"):
    """Thin path: open just the TaskBoard without booting the full swarm.

    Used by CLI task create/list/show to avoid spawning agents and seed tasks.
    """
    from dharma_swarm.task_board import TaskBoard

    db_path = Path(state_dir) / "db" / "tasks.db"
    tb = TaskBoard(db_path)
    await tb.init_db()
    return tb


def _pid_alive(pid: int) -> bool:
    try:
        if pid <= 1:
            return False
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except Exception:
        return False


def _tail(path: Path, lines: int = 60) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(errors="ignore")
        return "\n".join(text.splitlines()[-lines:])
    except Exception:
        return ""


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_age(seconds: float) -> str:
    total = max(0, int(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _runtime_pid_status() -> tuple[int | None, str]:
    pid_file = DHARMA_STATE / "daemon.pid"
    if not pid_file.exists():
        return (None, "missing")
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except Exception:
        return (None, "invalid")
    if _pid_alive(pid):
        return (pid, "alive")
    return (pid, "stale")


def _list_daemon_like_processes() -> list[tuple[int, str]]:
    """Best-effort process scan for live daemon/orchestrator launchers."""
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
    except Exception:
        return []

    if proc.returncode != 0:
        return []

    current_pid = os.getpid()
    matches: list[tuple[int, str]] = []
    needles = (
        "dgc orchestrate-live",
        "dharma_swarm.orchestrate_live",
        "orchestrate_live.py",
        "run_daemon.sh",
    )
    skip_markers = ("dgc doctor", "ps -axo", "rg ", "pytest")

    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        command = parts[1]
        if pid == current_pid:
            continue
        if not any(needle in command for needle in needles):
            continue
        if any(marker in command for marker in skip_markers):
            continue
        matches.append((pid, command))

    return matches


def _first_daemon_like_process() -> tuple[int, str] | None:
    matches = _list_daemon_like_processes()
    if not matches:
        return None
    return matches[0]
