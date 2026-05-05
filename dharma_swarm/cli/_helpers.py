"""Shared CLI helper functions used by dgc_cli.py and its submodules."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir

HOME = Path.home()
DHARMA_STATE = dharma_state_dir()
DHARMA_SWARM = HOME / "dharma_swarm"


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
