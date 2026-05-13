"""Read-only bridge for world-radar Go evidence receipts.

The Go side emits canonical ``go_evidence_receipt.v0`` receipts. This module
parses those sidecar receipts and projects accepted ``world_signal`` receipts
into the existing world-feed shape consumed by Zeitgeist/Shakti surfaces.

It does not fetch the network, run Go, write runtime state, dispatch agents, or
decide strategy. Those remain outside this bridge.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from dharma_swarm.daemon_config import dharma_state_dir

GO_EVIDENCE_SCHEMA_V0 = "go_evidence_receipt.v0"

WorldEventType = Literal[
    "world_raw_observation",
    "world_signal",
    "world_scout_health",
]

SUPPORTED_WORLD_EVENT_TYPES: tuple[WorldEventType, ...] = (
    "world_raw_observation",
    "world_signal",
    "world_scout_health",
)


class GoWorldBridgeError(ValueError):
    """Raised when a Go world-radar receipt cannot be admitted."""


@dataclass(frozen=True)
class GoWorldReceipt:
    """Typed view of a Go-emitted world-radar receipt."""

    receipt_id: str
    correlation_id: str
    source: WorldEventType
    source_url: str
    observed_at: str
    content_hash: str
    event_uid: str
    schema_version: str
    status: str
    payload: dict[str, Any]
    rejected_reason: str = ""

    def __post_init__(self) -> None:
        required = (
            self.receipt_id,
            self.correlation_id,
            self.source,
            self.observed_at,
            self.content_hash,
            self.event_uid,
            self.schema_version,
            self.status,
        )
        if not all(required):
            raise GoWorldBridgeError("GoWorldReceipt missing required identity fields")
        if self.schema_version != GO_EVIDENCE_SCHEMA_V0:
            raise GoWorldBridgeError(
                f"unsupported Go evidence schema: {self.schema_version}"
            )
        if self.source not in SUPPORTED_WORLD_EVENT_TYPES:
            raise GoWorldBridgeError(f"unsupported world event type: {self.source}")
        if self.status not in {"accepted", "rejected"}:
            raise GoWorldBridgeError(f"unsupported receipt status: {self.status}")
        if self.status == "rejected" and not self.rejected_reason:
            raise GoWorldBridgeError("rejected receipt must carry rejected_reason")


def world_receipts_dir(state_dir: Path | None = None) -> Path:
    """Return the default sidecar directory for world-radar Go receipts."""
    state = state_dir or dharma_state_dir("DHARMA_STATE_DIR")
    return state / "go_receipts" / "world"


def load_go_world_receipt(path: Path) -> GoWorldReceipt:
    """Read a JSON receipt produced by world_signal_ingestor_go."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        raise GoWorldBridgeError("Go world receipt payload must be a JSON object")
    source = str(raw.get("source", ""))
    if source not in SUPPORTED_WORLD_EVENT_TYPES:
        raise GoWorldBridgeError(f"unsupported world event type: {source!r}")
    return GoWorldReceipt(
        receipt_id=str(raw.get("receipt_id", "")),
        correlation_id=str(raw.get("correlation_id", "")),
        source=source,  # type: ignore[arg-type]
        source_url=str(raw.get("source_url", "")),
        observed_at=str(raw.get("observed_at", "")),
        content_hash=str(raw.get("content_hash", "")),
        event_uid=str(raw.get("event_uid", "")),
        schema_version=str(raw.get("schema_version", "")),
        status=str(raw.get("status", "")),
        rejected_reason=str(raw.get("rejected_reason", "")),
        payload=payload,
    )


def load_go_world_receipts(paths: list[Path] | tuple[Path, ...]) -> list[GoWorldReceipt]:
    """Load receipts from explicit paths, skipping unreadable/malformed files."""
    receipts: list[GoWorldReceipt] = []
    for path in sorted(paths):
        try:
            receipts.append(load_go_world_receipt(path))
        except (OSError, json.JSONDecodeError, GoWorldBridgeError):
            continue
    return receipts


def receipt_paths(receipts_dir: Path | None = None) -> tuple[Path, ...]:
    """Return candidate receipt JSON files from a sidecar directory."""
    directory = receipts_dir or world_receipts_dir()
    if not directory.exists():
        return ()
    return tuple(sorted(path for path in directory.glob("*.json") if path.is_file()))


def project_world_signal_receipts(
    paths: list[Path] | tuple[Path, ...],
) -> list[dict[str, Any]]:
    """Project accepted world-signal receipts into world-feed rows."""
    rows: list[dict[str, Any]] = []
    for receipt in load_go_world_receipts(tuple(paths)):
        if receipt.status != "accepted" or receipt.source != "world_signal":
            continue
        rows.append(world_feed_row_from_signal_receipt(receipt))
    return sorted(
        rows,
        key=lambda row: (
            -_float(row.get("relevance_score")),
            str(row.get("title", "")),
        ),
    )


def world_feed_row_from_signal_receipt(receipt: GoWorldReceipt) -> dict[str, Any]:
    """Convert one accepted ``world_signal`` receipt to world-feed JSON."""
    if receipt.source != "world_signal":
        raise GoWorldBridgeError(f"expected world_signal receipt, got {receipt.source!r}")
    if receipt.status != "accepted":
        raise GoWorldBridgeError(f"cannot project rejected receipt: {receipt.rejected_reason}")

    payload = receipt.payload
    title = str(payload.get("title", "")).strip()
    category = str(payload.get("category", "opportunity")).strip() or "opportunity"
    score = _float(payload.get("relevance_score"))
    keywords = _string_list(payload.get("keywords"))
    description = str(payload.get("description") or title).strip()

    metadata = {
        "receipt_id": receipt.receipt_id,
        "correlation_id": receipt.correlation_id,
        "content_hash": receipt.content_hash,
        "event_uid": receipt.event_uid,
        "raw_observation_event_uid": str(payload.get("raw_observation_event_uid", "")),
        "matched_terms": _string_list(payload.get("matched_terms")),
        "first_principles_questions": _string_list(
            payload.get("first_principles_questions")
        ),
        "iteration_steps": _string_list(payload.get("iteration_steps")),
        "adjacent_search_queries": _string_list(payload.get("adjacent_search_queries")),
        "strategic_moves": _string_list(payload.get("strategic_moves")),
        "human_review_required": bool(payload.get("human_review_required", True)),
        "raw_signal_not_final_judgment": bool(
            payload.get("raw_signal_not_final_judgment", True)
        ),
        "radar_version": str(payload.get("radar_version", "")),
    }

    return {
        "id": receipt.event_uid,
        "source": "go_world_signal_receipt",
        "source_url": receipt.source_url,
        "category": category,
        "title": title,
        "relevance_score": score,
        "keywords": keywords,
        "description": description,
        "observed_at": receipt.observed_at,
        "metadata": metadata,
    }


def summarize_go_world_receipts(receipts_dir: Path | None = None) -> dict[str, Any]:
    """Return a compact control-surface summary for world-radar receipts."""
    directory = receipts_dir or world_receipts_dir()
    paths = receipt_paths(directory)
    receipts = load_go_world_receipts(paths)
    by_source = Counter(receipt.source for receipt in receipts)
    by_status = Counter(receipt.status for receipt in receipts)
    rejected_reasons = Counter(
        receipt.rejected_reason for receipt in receipts if receipt.rejected_reason
    )
    freshest = max((receipt.observed_at for receipt in receipts), default="")
    signal_rows = project_world_signal_receipts(paths)
    return {
        "receipts_dir": str(directory),
        "exists": directory.exists(),
        "total": len(receipts),
        "accepted": by_status.get("accepted", 0),
        "rejected": by_status.get("rejected", 0),
        "world_raw_observation": by_source.get("world_raw_observation", 0),
        "world_signal": by_source.get("world_signal", 0),
        "world_scout_health": by_source.get("world_scout_health", 0),
        "freshest_observed_at": freshest,
        "rejected_reasons": dict(sorted(rejected_reasons.items())),
        "projected_world_signals": len(signal_rows),
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


__all__ = [
    "GO_EVIDENCE_SCHEMA_V0",
    "SUPPORTED_WORLD_EVENT_TYPES",
    "GoWorldBridgeError",
    "GoWorldReceipt",
    "load_go_world_receipt",
    "load_go_world_receipts",
    "project_world_signal_receipts",
    "receipt_paths",
    "summarize_go_world_receipts",
    "world_feed_row_from_signal_receipt",
    "world_receipts_dir",
]
