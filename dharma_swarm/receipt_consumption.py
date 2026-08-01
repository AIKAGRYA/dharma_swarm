"""Bounded receipt-grounded provider ordering for Loop 1 closure."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from dharma_swarm.models import ProviderType

MAX_RECEIPT_DEMOTIONS = 2
RECEIPT_CONSUMPTION_WINDOW = 50
PROCESS_BOOT_ID = uuid4().hex


@dataclass(frozen=True)
class ReceiptConsumptionEvidence:
    consumed_trace_ids: tuple[str, ...] = ()
    decision_delta: dict[str, Any] = field(default_factory=dict)
    boot_id: str = PROCESS_BOOT_ID
    applied: bool = False
    fail_open_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "consumed_trace_ids": list(self.consumed_trace_ids),
            "decision_delta": dict(self.decision_delta),
            "boot_id": self.boot_id,
            "applied": self.applied,
            "fail_open_reason": self.fail_open_reason,
        }


def _provider_type(raw: object) -> ProviderType | None:
    value = str(raw or "").strip().lower()
    return next((provider for provider in ProviderType if provider.value == value), None)


def apply_receipt_consumption_ranking(
    chain: list[ProviderType],
    *,
    db_path: Path | None = None,
    window: int = RECEIPT_CONSUMPTION_WINDOW,
    boot_id: str = PROCESS_BOOT_ID,
) -> tuple[list[ProviderType], bool, ReceiptConsumptionEvidence]:
    """Reorder, never filter, from recent spine-written receipts; fail open."""

    default_order = list(chain)

    def fail_open(reason: str | None = None):
        return (
            default_order,
            False,
            ReceiptConsumptionEvidence(boot_id=boot_id, fail_open_reason=reason),
        )

    if len(default_order) <= 1:
        return fail_open()
    path = db_path or Path(
        os.environ.get(
            "DGC_ROUTER_RECEIPT_DB",
            str(Path.home() / ".dharma" / "state" / "runtime.db"),
        )
    )
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT receipt_json FROM delegation_runs "
                "WHERE receipt_json IS NOT NULL AND receipt_json != '' "
                "ORDER BY started_at DESC, rowid DESC LIMIT ?",
                (max(1, int(window)),),
            ).fetchall()
        finally:
            conn.close()
        failures: dict[ProviderType, str] = {}
        for (raw_receipt,) in rows:
            receipt = json.loads(str(raw_receipt))
            if not isinstance(receipt, dict):
                raise ValueError("receipt_json is not an object")
            provider = _provider_type(receipt.get("provider"))
            if provider not in default_order or provider in failures:
                continue
            status = str(receipt.get("status") or "").strip().lower()
            error_source = str(receipt.get("error_source") or "").strip().lower()
            if status == "ok" and error_source in {"", "none"}:
                continue
            trace_id = str(receipt.get("trace_id") or "").strip()
            if not trace_id:
                raise ValueError("failing receipt is missing trace_id")
            failures[provider] = trace_id
    except Exception as exc:
        return fail_open(type(exc).__name__)

    demoted = [provider for provider in default_order if provider in failures][
        :MAX_RECEIPT_DEMOTIONS
    ]
    if not demoted:
        return fail_open()
    reordered = [provider for provider in default_order if provider not in demoted] + demoted
    evidence = ReceiptConsumptionEvidence(
        consumed_trace_ids=tuple(failures[provider] for provider in demoted),
        decision_delta={
            "default_order": [provider.value for provider in default_order],
            "reordered_order": [provider.value for provider in reordered],
            "demoted_providers": [provider.value for provider in demoted],
        },
        boot_id=boot_id,
        applied=reordered != default_order,
    )
    return reordered, evidence.applied, evidence
