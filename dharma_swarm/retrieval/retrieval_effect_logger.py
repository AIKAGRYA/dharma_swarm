"""JSONL telemetry for memory context retrieval effects."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_RETRIEVAL_EFFECT_LOG = Path.home() / ".dharma" / "retrieval" / "effect.jsonl"


@dataclass(frozen=True)
class RetrievalEffect:
    effect_id: str
    session_id: str
    task_id: str
    injected_fact_ids: list[str]
    citation_handles: list[str]
    policy_used: dict[str, Any]
    token_budget: int
    actual_tokens: int
    contradictions_dropped: list[tuple[str, str, str]]
    ts: str


def new_effect_id() -> str:
    return f"ret-{uuid.uuid4().hex[:24]}"


def citation_handle_for_fact_id(fact_id: str) -> str:
    digest = hashlib.sha256(fact_id.encode("utf-8")).hexdigest()[:26].upper()
    return f"PR-{digest}"


def log_effect(effect: RetrievalEffect, path: Path | str | None = None) -> None:
    target = Path(path) if path is not None else DEFAULT_RETRIEVAL_EFFECT_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(effect), sort_keys=True, default=str) + "\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
