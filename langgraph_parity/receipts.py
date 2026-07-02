"""Receipt helpers for LangGraph parity runs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dharma_swarm.spine.receipt import EvidenceReceipt


PROVIDER = "local_deterministic"
MODEL = "langgraph-parity-fixture-v1"


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def estimate_tokens(*parts: str) -> int:
    count = 0
    for part in parts:
        words = str(part or "").split()
        count += max(1, len(words))
    return count


def estimate_cost_usd(provider: str, input_tokens: int, output_tokens: int) -> float:
    if provider == PROVIDER:
        return 0.0
    return round((input_tokens + (3 * output_tokens)) / 1_000_000, 6)


def build_evidence_receipt(
    *,
    operation: str,
    task_id: str,
    agent_id: str,
    trace_id: str,
    status: str = "ok",
    mission_id: str = "",
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
    side_effect_key: str = "",
    idempotency_key: str = "",
    artifact_id: str = "",
    error_detail: str = "",
    attributes: dict[str, Any] | None = None,
) -> EvidenceReceipt:
    started = datetime.now(timezone.utc)
    receipt_attrs = {
        "mission_id": mission_id,
        "side_effect_key": side_effect_key,
        "idempotency_key": idempotency_key,
        "artifact_id": artifact_id,
        **(attributes or {}),
    }
    return EvidenceReceipt(
        trace_id=trace_id,
        span_id=uuid4().hex[:16],
        context_id=trace_id,
        task_id=task_id,
        agent_id=agent_id,
        provider=PROVIDER,
        model=MODEL,
        operation=operation,
        provider_attempted=False,
        status="ok" if status == "ok" else "failed",
        error_source="none" if status == "ok" else "internal_error",
        error_detail=error_detail or None,
        started_at=started,
        finished_at=datetime.now(timezone.utc),
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        attributes=receipt_attrs,
    )


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return path


def append_receipt_jsonl(path: Path, receipt: EvidenceReceipt) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt.to_dict(), sort_keys=True, default=str) + "\n")
    return path
