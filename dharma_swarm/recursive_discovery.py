"""Shadow-mode receipts for recursive discovery loops.

This module defines a bounded receipt layer for recursive self-improvement:
limitations, generated evals, candidate diffs, experiment results, witness
verdicts, and promotion decisions.  It is intentionally shadow-only: it records
evidence and recommendations, but it does not apply diffs or mutate runtime
code.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from dharma_swarm.event_log import EventLog
from dharma_swarm.models import _new_id, _utc_now
from dharma_swarm.runtime_contract import RuntimeEnvelope, RuntimeEventType


ReceiptType = Literal[
    "limitation",
    "generated_eval",
    "candidate_diff",
    "experiment_result",
    "witness_verdict",
    "promotion_decision",
]
WitnessPhase = Literal[
    "before_generate",
    "before_apply",
    "before_eval",
    "before_archive",
    "before_promote",
]
ReceiptStatus = Literal["pending", "passed", "warned", "blocked", "recorded"]
PromotionDecision = Literal["promote_to_pr", "revise", "reject", "hold"]

SCHEMA_VERSION = "recursive_discovery.v0"
EVENT_STREAM = "recursive_discovery"
RECEIPT_TYPES: tuple[str, ...] = (
    "limitation",
    "generated_eval",
    "candidate_diff",
    "experiment_result",
    "witness_verdict",
    "promotion_decision",
)


def stable_payload_hash(payload: dict[str, Any]) -> str:
    """Return a stable SHA-256 hash for a JSON-serializable payload."""
    material = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class CommandReceipt(BaseModel):
    """One command executed in a sandbox or dry-run context."""

    command: str
    exit_code: int
    wall_time_seconds: float | None = None


class WitnessVerdict(BaseModel):
    """Witness outcome for one recursive-discovery phase."""

    phase: WitnessPhase
    verdict: ReceiptStatus
    witness_id: str
    reason: str


class RecursiveReceipt(BaseModel):
    """Minimal receipt schema shared by all recursive discovery artifacts."""

    schema_version: Literal["recursive_discovery.v0"] = SCHEMA_VERSION
    receipt_id: str = Field(default_factory=_new_id)
    receipt_type: ReceiptType
    created_at: str = Field(default_factory=lambda: _utc_now().isoformat())
    parent_id: str | None = None
    limitation_id: str | None = None
    candidate_id: str | None = None
    model_id: str = ""
    prompt_hash: str = ""
    eval_ids: list[str] = Field(default_factory=list)
    files_touched: list[str] = Field(default_factory=list)
    commands: list[CommandReceipt] = Field(default_factory=list)
    cost_usd: float | None = None
    wall_time_seconds: float | None = None
    sandbox_path: str = ""
    witness_verdicts: list[WitnessVerdict] = Field(default_factory=list)
    rollback_pointer: str = ""
    status: ReceiptStatus = "recorded"
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("files_touched")
    @classmethod
    def reject_absolute_or_parent_paths(cls, paths: list[str]) -> list[str]:
        for path in paths:
            p = Path(path)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError(f"unsafe repo path in receipt: {path}")
        return paths

    def content_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude={"created_at", "receipt_id"})
        return stable_payload_hash(payload)


class LimitationReceipt(RecursiveReceipt):
    receipt_type: Literal["limitation"] = "limitation"
    limitation_id: str


class GeneratedEvalReceipt(RecursiveReceipt):
    receipt_type: Literal["generated_eval"] = "generated_eval"
    limitation_id: str
    eval_ids: list[str]

    @field_validator("eval_ids")
    @classmethod
    def require_eval_ids(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("generated eval receipt requires at least one eval id")
        return values


class CandidateDiffReceipt(RecursiveReceipt):
    receipt_type: Literal["candidate_diff"] = "candidate_diff"
    limitation_id: str
    candidate_id: str


class ExperimentResultReceipt(RecursiveReceipt):
    receipt_type: Literal["experiment_result"] = "experiment_result"
    candidate_id: str
    eval_ids: list[str]


class WitnessVerdictReceipt(RecursiveReceipt):
    receipt_type: Literal["witness_verdict"] = "witness_verdict"
    witness_verdicts: list[WitnessVerdict]

    @field_validator("witness_verdicts")
    @classmethod
    def require_witness_verdicts(cls, values: list[WitnessVerdict]) -> list[WitnessVerdict]:
        if not values:
            raise ValueError("witness verdict receipt requires at least one verdict")
        return values


class PromotionDecisionReceipt(RecursiveReceipt):
    receipt_type: Literal["promotion_decision"] = "promotion_decision"
    decision: PromotionDecision = "hold"


@dataclass(frozen=True)
class RecursiveDiscoveryRecordResult:
    """Stored event-log result for one recursive discovery receipt."""

    receipt: RecursiveReceipt
    event: dict[str, Any]
    stream: str = EVENT_STREAM


class RecursiveDiscoveryRecorder:
    """Append recursive-discovery receipts to the existing runtime EventLog."""

    def __init__(self, event_log: EventLog | None = None) -> None:
        self.event_log = event_log or EventLog()

    def record(
        self,
        receipt: RecursiveReceipt,
        *,
        session_id: str,
        agent_id: str = "recursive_discovery_shadow",
        trace_id: str | None = None,
    ) -> RecursiveDiscoveryRecordResult:
        event = self.event_log.append_envelope(
            RuntimeEnvelope.create(
                event_type=RuntimeEventType.ACTION_EVENT,
                source="recursive.discovery.shadow",
                agent_id=agent_id,
                session_id=session_id,
                trace_id=trace_id or receipt.parent_id or receipt.receipt_id,
                payload={
                    "action_name": f"recursive_discovery.{receipt.receipt_type}",
                    "decision": receipt.status,
                    "confidence": 1.0,
                    "receipt_id": receipt.receipt_id,
                    "receipt_type": receipt.receipt_type,
                    "receipt_hash": receipt.content_hash(),
                    "parent_id": receipt.parent_id,
                    "candidate_id": receipt.candidate_id,
                    "eval_ids": receipt.eval_ids,
                    "files_touched": receipt.files_touched,
                    "rollback_pointer": receipt.rollback_pointer,
                    "receipt": receipt.model_dump(mode="json"),
                },
            ),
            stream=EVENT_STREAM,
        )
        return RecursiveDiscoveryRecordResult(receipt=receipt, event=event)


def shadow_fixture_receipts() -> list[RecursiveReceipt]:
    """Return deterministic fixture receipts for the shadow control surface."""
    parent_id = "recursive-shadow-demo-001"
    limitation_id = "lim-docops-authority-drift"
    candidate_id = "cand-docops-authority-drift-001"
    eval_id = "eval-docops-authority-registration"
    prompt_hash = stable_payload_hash(
        {
            "prompt": "Find one declared-vs-actual documentation authority gap.",
            "scope": "docops",
        }
    )
    sandbox = "/tmp/dharma-recursive-shadow-demo"
    files = [
        "docs/governance/CANONICAL_DOC_STACK.md",
        "docs/docops/assertions.yaml",
    ]
    return [
        LimitationReceipt(
            parent_id=parent_id,
            limitation_id=limitation_id,
            model_id="fixture",
            prompt_hash=prompt_hash,
            summary="Authority-bearing docs can be changed without a paired canonical registration.",
            files_touched=files,
            sandbox_path=sandbox,
            status="recorded",
        ),
        GeneratedEvalReceipt(
            parent_id=parent_id,
            limitation_id=limitation_id,
            model_id="fixture",
            prompt_hash=prompt_hash,
            eval_ids=[eval_id],
            commands=[
                CommandReceipt(
                    command="python3 scripts/docops/check_docops_integrity.py --changed-from origin/main",
                    exit_code=0,
                    wall_time_seconds=0.4,
                )
            ],
            files_touched=["scripts/docops/check_docops_integrity.py"],
            sandbox_path=sandbox,
            summary="Generated eval checks unregistered authority claims against DocOps.",
            status="passed",
        ),
        CandidateDiffReceipt(
            parent_id=parent_id,
            limitation_id=limitation_id,
            candidate_id=candidate_id,
            model_id="fixture",
            prompt_hash=prompt_hash,
            eval_ids=[eval_id],
            files_touched=files,
            sandbox_path=sandbox,
            rollback_pointer="git restore --source=HEAD -- docs/governance/CANONICAL_DOC_STACK.md docs/docops/assertions.yaml",
            summary="Candidate diff registers authority docs and leaves apply to human promotion.",
            status="recorded",
        ),
        ExperimentResultReceipt(
            parent_id=parent_id,
            candidate_id=candidate_id,
            model_id="fixture",
            prompt_hash=prompt_hash,
            eval_ids=[eval_id],
            files_touched=files,
            sandbox_path=sandbox,
            commands=[
                CommandReceipt(
                    command="pytest -q tests/test_control_surface.py",
                    exit_code=0,
                    wall_time_seconds=2.7,
                ),
            ],
            summary="Shadow experiment passed fixture control-surface checks.",
            status="passed",
        ),
        WitnessVerdictReceipt(
            parent_id=parent_id,
            candidate_id=candidate_id,
            model_id="fixture",
            prompt_hash=prompt_hash,
            eval_ids=[eval_id],
            files_touched=files,
            sandbox_path=sandbox,
            witness_verdicts=[
                WitnessVerdict(
                    phase="before_promote",
                    verdict="warned",
                    witness_id="fixture-witness",
                    reason="Human promotion required; shadow receipt must not apply its own diff.",
                )
            ],
            summary="Witness allows archive, warns against autonomous promotion.",
            status="warned",
        ),
        PromotionDecisionReceipt(
            parent_id=parent_id,
            candidate_id=candidate_id,
            model_id="fixture",
            prompt_hash=prompt_hash,
            eval_ids=[eval_id],
            files_touched=files,
            sandbox_path=sandbox,
            rollback_pointer="human-reviewed PR only",
            summary="Promotion queue holds candidate for human PR review.",
            status="pending",
            decision="hold",
        ),
    ]


def receipt_counts_by_type(receipts: list[RecursiveReceipt]) -> dict[str, int]:
    counts = {rtype: 0 for rtype in RECEIPT_TYPES}
    for receipt in receipts:
        counts[receipt.receipt_type] = counts.get(receipt.receipt_type, 0) + 1
    return counts
