"""JSONL telemetry for memory context retrieval effects.

Canonical-default writes are gated by the master ``DHARMA_CHETANA_ENABLED``
canary. Explicit-path callers (tests, ad-hoc tooling) bypass the gate. The
canonical bundle telemetry always lands in ``ContextBundleRecord.metadata``
regardless of this gate; this JSONL is an optional projection.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_RETRIEVAL_EFFECT_LOG = Path.home() / ".dharma" / "retrieval" / "effect.jsonl"

_SUPPRESSED_RETRIEVAL_EFFECT_COUNT: int = 0


def _normalized_retrieval_log_path(path: Path) -> Path:
    try:
        return Path(path).expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        return Path(path).expanduser().absolute()


def _is_canonical_retrieval_log(path: Path) -> bool:
    return _normalized_retrieval_log_path(path) == _normalized_retrieval_log_path(
        DEFAULT_RETRIEVAL_EFFECT_LOG
    )


def get_suppressed_retrieval_effect_count() -> int:
    """Process-local counter of canonical-default writes suppressed by the gate."""
    return _SUPPRESSED_RETRIEVAL_EFFECT_COUNT


def reset_suppressed_retrieval_effect_count() -> None:
    """Test helper to reset the suppressed-write counter."""
    global _SUPPRESSED_RETRIEVAL_EFFECT_COUNT
    _SUPPRESSED_RETRIEVAL_EFFECT_COUNT = 0


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


def log_effect(effect: RetrievalEffect, path: Path | str | None = None) -> bool:
    """Append a RetrievalEffect to the JSONL projection.

    Returns True on a successful write, False if the canonical-default path is
    suppressed by the master canary or the write itself fails. Never raises.
    """
    global _SUPPRESSED_RETRIEVAL_EFFECT_COUNT
    target = Path(path) if path is not None else DEFAULT_RETRIEVAL_EFFECT_LOG
    if _is_canonical_retrieval_log(target):
        from dharma_swarm.register_disciplines import chetana_register_enabled

        if not chetana_register_enabled():
            _SUPPRESSED_RETRIEVAL_EFFECT_COUNT += 1
            return False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(effect), sort_keys=True, default=str) + "\n")
        return True
    except Exception:
        return False


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
