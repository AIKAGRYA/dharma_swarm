"""Shadow-mode receipts for recursive discovery loops.

This module defines a bounded receipt layer for recursive self-improvement:
limitations, generated evals, candidate diffs, experiment results, witness
verdicts, and promotion decisions.  It is intentionally shadow-only: it records
evidence and recommendations, but it does not apply diffs or mutate runtime
code.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shlex
import sys
import time
from typing import Any, Literal, Sequence

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


RECEIPT_MODELS: dict[str, type[RecursiveReceipt]] = {
    "limitation": LimitationReceipt,
    "generated_eval": GeneratedEvalReceipt,
    "candidate_diff": CandidateDiffReceipt,
    "experiment_result": ExperimentResultReceipt,
    "witness_verdict": WitnessVerdictReceipt,
    "promotion_decision": PromotionDecisionReceipt,
}


@dataclass(frozen=True)
class RecursiveDiscoveryRecordResult:
    """Stored event-log result for one recursive discovery receipt."""

    receipt: RecursiveReceipt
    event: dict[str, Any]
    stream: str = EVENT_STREAM


@dataclass(frozen=True)
class RecursiveDiscoveryRunResult:
    """Replayable result for one bounded recursive-discovery shadow run."""

    session_id: str
    trace_id: str
    receipts: list[RecursiveReceipt]
    recorded_events: list[dict[str, Any]]
    registry_summaries: list[dict[str, Any]]
    proof_command: str
    proof_exit_code: int
    duration_seconds: float

    def to_report(self) -> dict[str, Any]:
        """Return a compact JSON-serializable run report."""
        return {
            "schema_version": "recursive_discovery_run.v0",
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "receipt_count": len(self.receipts),
            "receipt_counts": receipt_counts_by_type(self.receipts),
            "registry_summary_count": len(self.registry_summaries),
            "proof_command": self.proof_command,
            "proof_exit_code": self.proof_exit_code,
            "duration_seconds": round(self.duration_seconds, 3),
            "promotion_decisions": [
                getattr(receipt, "decision", "")
                for receipt in self.receipts
                if receipt.receipt_type == "promotion_decision"
            ],
            "archive_entry_ids": sorted(
                {
                    str(receipt.metadata.get("archive_entry_id", ""))
                    for receipt in self.receipts
                    if receipt.metadata.get("archive_entry_id")
                }
            ),
        }


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


def load_recursive_receipts(
    event_log: EventLog | None = None,
    *,
    session_id: str | None = None,
    trace_id: str | None = None,
    limit: int | None = None,
) -> list[RecursiveReceipt]:
    """Read complete recursive-discovery receipts from the append-only EventLog."""
    log = event_log or EventLog()
    rows = log.read_envelopes(
        stream=EVENT_STREAM,
        session_id=session_id,
        trace_id=trace_id,
        limit=limit,
    )
    receipts: list[RecursiveReceipt] = []
    for row in rows:
        payload = dict(row.get("payload") or {})
        raw_receipt = payload.get("receipt")
        if not isinstance(raw_receipt, dict):
            continue
        receipt_model = RECEIPT_MODELS.get(
            str(raw_receipt.get("receipt_type") or ""),
            RecursiveReceipt,
        )
        try:
            receipt = receipt_model.model_validate(raw_receipt)
        except ValueError:
            continue
        expected_hash = str(payload.get("receipt_hash") or "")
        if expected_hash and expected_hash != receipt.content_hash():
            continue
        receipts.append(receipt)
    return receipts


def validate_minimum_receipt_chain(receipts: Sequence[RecursiveReceipt]) -> tuple[bool, list[str]]:
    """Check that a receipt group proves the minimum no-apply recursion loop."""
    errors: list[str] = []
    rows = list(receipts)
    counts = receipt_counts_by_type(rows)
    for receipt_type in RECEIPT_TYPES:
        if counts.get(receipt_type, 0) < 1:
            errors.append(f"missing receipt_type:{receipt_type}")
    if not rows:
        errors.append("empty receipt chain")
    parent_ids = {receipt.parent_id for receipt in rows if receipt.parent_id}
    if len(parent_ids) > 1:
        errors.append("multiple parent_id values")
    for receipt in rows:
        if receipt.receipt_type == "candidate_diff" and not receipt.rollback_pointer:
            errors.append(f"{receipt.receipt_id}:missing rollback_pointer")
        if receipt.receipt_type == "experiment_result" and not receipt.commands:
            errors.append(f"{receipt.receipt_id}:missing experiment command")
        if receipt.receipt_type == "promotion_decision":
            decision = getattr(receipt, "decision", "hold")
            if decision == "promote_to_pr":
                errors.append(f"{receipt.receipt_id}:autonomous promotion not allowed")
    return not errors, errors


def build_recursive_shadow_run_receipts(
    *,
    parent_id: str,
    limitation_id: str,
    candidate_id: str,
    eval_id: str,
    prompt: str,
    model_id: str,
    files_touched: Sequence[str],
    proof: CommandReceipt,
    sandbox_path: str,
    source: str = "recursive_discovery_shadow_demo",
    archive_entry_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[RecursiveReceipt]:
    """Build a linked six-receipt recursive-discovery shadow chain."""

    prompt_hash = stable_payload_hash(
        {
            "prompt": prompt,
            "limitation_id": limitation_id,
            "candidate_id": candidate_id,
            "eval_id": eval_id,
        }
    )
    files = list(files_touched)
    passed = proof.exit_code == 0
    result_status: ReceiptStatus = "passed" if passed else "blocked"
    shared_metadata = {
        "source": source,
        "shadow_run": True,
        "diff_applied": False,
        "archive_entry_id": archive_entry_id or "",
        **dict(metadata or {}),
    }
    return [
        LimitationReceipt(
            parent_id=parent_id,
            limitation_id=limitation_id,
            model_id=model_id,
            prompt_hash=prompt_hash,
            files_touched=files,
            sandbox_path=sandbox_path,
            status="recorded",
            summary=(
                "Bounded recursive-discovery run must prove a limitation before "
                "candidate changes are considered."
            ),
            metadata={**shared_metadata, "phase": "limitation"},
        ),
        GeneratedEvalReceipt(
            parent_id=parent_id,
            limitation_id=limitation_id,
            model_id=model_id,
            prompt_hash=prompt_hash,
            eval_ids=[eval_id],
            files_touched=["tests/test_recursive_discovery.py"],
            commands=[proof],
            sandbox_path=sandbox_path,
            status=result_status,
            summary="Generated eval is represented by a fresh deterministic proof command.",
            metadata={**shared_metadata, "phase": "generated_eval"},
        ),
        CandidateDiffReceipt(
            parent_id=parent_id,
            limitation_id=limitation_id,
            candidate_id=candidate_id,
            model_id=model_id,
            prompt_hash=prompt_hash,
            eval_ids=[eval_id],
            files_touched=files,
            sandbox_path=sandbox_path,
            rollback_pointer="shadow-only: no diff applied",
            summary="Candidate diff is held as a no-apply shadow candidate.",
            status="recorded",
            metadata={**shared_metadata, "phase": "candidate_diff"},
        ),
        ExperimentResultReceipt(
            parent_id=parent_id,
            candidate_id=candidate_id,
            model_id=model_id,
            prompt_hash=prompt_hash,
            eval_ids=[eval_id],
            files_touched=files,
            commands=[proof],
            sandbox_path=sandbox_path,
            summary=(
                "Fresh proof command passed for the shadow candidate."
                if passed
                else "Fresh proof command failed; candidate remains blocked."
            ),
            status=result_status,
            metadata={**shared_metadata, "phase": "experiment_result"},
        ),
        WitnessVerdictReceipt(
            parent_id=parent_id,
            candidate_id=candidate_id,
            model_id=model_id,
            prompt_hash=prompt_hash,
            eval_ids=[eval_id],
            files_touched=files,
            sandbox_path=sandbox_path,
            witness_verdicts=[
                WitnessVerdict(
                    phase="before_promote",
                    verdict="warned" if passed else "blocked",
                    witness_id="recursive-discovery-shadow-witness",
                    reason=(
                        "Human-held promotion required; shadow run cannot apply its own diff."
                        if passed
                        else "Failed proof blocks promotion before human review."
                    ),
                )
            ],
            summary="Witness preserves the no-autonomous-promotion boundary.",
            status="warned" if passed else "blocked",
            metadata={**shared_metadata, "phase": "witness_verdict"},
        ),
        PromotionDecisionReceipt(
            parent_id=parent_id,
            candidate_id=candidate_id,
            model_id=model_id,
            prompt_hash=prompt_hash,
            eval_ids=[eval_id],
            files_touched=files,
            sandbox_path=sandbox_path,
            rollback_pointer="human-reviewed PR only",
            summary=(
                "Candidate is eligible for human PR review."
                if passed
                else "Candidate held because proof did not pass."
            ),
            status="pending" if passed else "blocked",
            decision="hold",
            metadata={**shared_metadata, "phase": "promotion_decision"},
        ),
    ]


async def run_recursive_discovery_shadow_demo(
    *,
    session_id: str,
    task_id: str = "",
    repo_root: Path | None = None,
    event_log: EventLog | None = None,
    evaluation_registry: Any | None = None,
    proof_command: Sequence[str] | None = None,
    proof_timeout: float = 60.0,
    created_by: str = "recursive_discovery.shadow_demo",
    trace_id: str | None = None,
) -> RecursiveDiscoveryRunResult:
    """Run one bounded shadow proof and persist linked recursive receipts."""

    root = Path(repo_root or Path.cwd()).resolve()
    parent_id = f"recursive-shadow-run-{stable_payload_hash({'session_id': session_id})[:12]}"
    resolved_trace_id = trace_id or parent_id
    command = tuple(
        proof_command
        or (
            sys.executable,
            "-m",
            "pytest",
            "tests/test_recursive_discovery.py",
            "-q",
        )
    )
    started = time.monotonic()
    proof_receipt, proof_metadata = await _run_proof_command(
        command,
        cwd=root,
        timeout=proof_timeout,
    )
    limitation_id = f"lim-shadow-proof-{stable_payload_hash({'trace': resolved_trace_id})[:10]}"
    candidate_id = f"cand-shadow-proof-{stable_payload_hash({'trace': resolved_trace_id, 'cmd': proof_receipt.command})[:10]}"
    eval_id = f"eval-shadow-proof-{stable_payload_hash({'cmd': proof_receipt.command})[:10]}"
    receipts = build_recursive_shadow_run_receipts(
        parent_id=parent_id,
        limitation_id=limitation_id,
        candidate_id=candidate_id,
        eval_id=eval_id,
        prompt="Run a bounded recursive-discovery shadow proof without applying a diff.",
        model_id="local-shadow-runner",
        files_touched=[
            "dharma_swarm/recursive_discovery.py",
            "tests/test_recursive_discovery.py",
        ],
        proof=proof_receipt,
        sandbox_path=str(root),
        metadata={
            "proof_stdout_hash": proof_metadata.get("stdout_hash", ""),
            "proof_stderr_hash": proof_metadata.get("stderr_hash", ""),
            "proof_timed_out": proof_metadata.get("timed_out", False),
        },
    )

    recorder = RecursiveDiscoveryRecorder(event_log)
    recorded_events = [
        recorder.record(
            receipt,
            session_id=session_id,
            agent_id=created_by,
            trace_id=resolved_trace_id,
        ).event
        for receipt in receipts
    ]

    registry_summaries: list[dict[str, Any]] = []
    if evaluation_registry is not None:
        for receipt in receipts:
            result = await evaluation_registry.record_recursive_discovery_receipt(
                receipt.model_dump(mode="json"),
                session_id=session_id,
                task_id=task_id,
                trace_id=resolved_trace_id,
                created_by=created_by,
            )
            registry_summaries.append(dict(result.summary))

    return RecursiveDiscoveryRunResult(
        session_id=session_id,
        trace_id=resolved_trace_id,
        receipts=receipts,
        recorded_events=recorded_events,
        registry_summaries=registry_summaries,
        proof_command=proof_receipt.command,
        proof_exit_code=proof_receipt.exit_code,
        duration_seconds=time.monotonic() - started,
    )


async def run_shadow_evolution_foundry(
    *,
    session_id: str,
    task_id: str = "",
    repo_root: Path | None = None,
    sandbox_root: Path | None = None,
    archive_path: Path | None = None,
    event_log: EventLog | None = None,
    evaluation_registry: Any | None = None,
    variant_count: int = 10,
    proof_timeout: float = 60.0,
    created_by: str = "evolution_foundry.shadow",
    trace_id: str | None = None,
) -> RecursiveDiscoveryRunResult:
    """Run deterministic no-apply variant evolution in isolated sandboxes."""

    from dharma_swarm.archive import ArchiveEntry, EvolutionArchive, FitnessScore

    started = time.monotonic()
    root = Path(repo_root or Path.cwd()).resolve()
    resolved_trace_id = trace_id or f"foundry-{stable_payload_hash({'session_id': session_id})[:12]}"
    sandbox_base = Path(
        sandbox_root
        or (Path.home() / ".dharma" / "evolution_foundry" / resolved_trace_id)
    ).expanduser().resolve()
    sandbox_base.mkdir(parents=True, exist_ok=True)
    archive = EvolutionArchive(Path(archive_path or (sandbox_base / "archive.jsonl")))
    await archive.load()
    recorder = RecursiveDiscoveryRecorder(event_log)
    receipts: list[RecursiveReceipt] = []
    recorded_events: list[dict[str, Any]] = []
    registry_summaries: list[dict[str, Any]] = []
    max_exit_code = 0
    parent_archive_id: str | None = None

    for index in range(max(0, variant_count)):
        variant_id = f"variant-{index + 1:02d}"
        sandbox = sandbox_base / variant_id
        sandbox.mkdir(parents=True, exist_ok=True)
        patch_text = _foundry_candidate_patch(variant_id, index)
        (sandbox / "candidate.patch").write_text(patch_text, encoding="utf-8")
        command = _foundry_variant_command(variant_id, index)
        proof, proof_metadata = await _run_proof_command(
            command,
            cwd=sandbox,
            timeout=proof_timeout,
        )
        max_exit_code = max(max_exit_code, proof.exit_code)
        passed = proof.exit_code == 0
        archive_entry = ArchiveEntry(
            parent_id=parent_archive_id,
            component="dharma_swarm/operator_core/control_surface.py",
            change_type="shadow_variant",
            description=f"{variant_id} no-apply Control Surface evidence variant",
            diff=patch_text,
            fitness=FitnessScore(
                correctness=1.0 if passed else 0.0,
                elegance=0.6,
                dharmic_alignment=0.8 if passed else 0.4,
                performance=0.0,
                utilization=0.0,
                economic_value=0.0,
                efficiency=0.9,
                safety=1.0,
            ),
            test_results={
                "shadow": True,
                "variant_id": variant_id,
                "proof_exit_code": proof.exit_code,
                "proof_stdout_hash": proof_metadata.get("stdout_hash", ""),
                "proof_stderr_hash": proof_metadata.get("stderr_hash", ""),
                "proof_timed_out": proof_metadata.get("timed_out", False),
            },
            evidence_tier="local",
            promotion_state="candidate" if passed else "rejected",
            status="shadow_passed" if passed else "shadow_failed",
            agent_id=created_by,
            model="deterministic-shadow",
        )
        archive_entry_id = await archive.add_entry(archive_entry)
        stored_entry = await archive.get_entry(archive_entry_id)
        parent_archive_id = archive_entry_id
        limitation_id = f"lim-{resolved_trace_id}-{variant_id}"
        candidate_id = f"cand-{resolved_trace_id}-{variant_id}"
        eval_id = f"eval-{resolved_trace_id}-{variant_id}"
        variant_receipts = build_recursive_shadow_run_receipts(
            parent_id=f"{resolved_trace_id}-{variant_id}",
            limitation_id=limitation_id,
            candidate_id=candidate_id,
            eval_id=eval_id,
            prompt=(
                "Evaluate one no-apply sandbox variant and preserve the "
                "human promotion boundary."
            ),
            model_id="deterministic-shadow",
            files_touched=["reports/evolution_foundry/README.md"],
            proof=proof,
            sandbox_path=str(sandbox),
            source="evolution_foundry_shadow",
            archive_entry_id=archive_entry_id,
            metadata={
                "variant_id": variant_id,
                "repo_root": str(root),
                "archive_merkle_root": stored_entry.merkle_root if stored_entry else "",
                "proof_stdout_hash": proof_metadata.get("stdout_hash", ""),
                "proof_stderr_hash": proof_metadata.get("stderr_hash", ""),
                "proof_timed_out": proof_metadata.get("timed_out", False),
            },
        )
        for receipt in variant_receipts:
            event = recorder.record(
                receipt,
                session_id=session_id,
                agent_id=created_by,
                trace_id=resolved_trace_id,
            ).event
            receipts.append(receipt)
            recorded_events.append(event)
            if evaluation_registry is not None:
                result = await evaluation_registry.record_recursive_discovery_receipt(
                    receipt.model_dump(mode="json"),
                    session_id=session_id,
                    task_id=task_id,
                    trace_id=resolved_trace_id,
                    created_by=created_by,
                )
                registry_summaries.append(dict(result.summary))

    return RecursiveDiscoveryRunResult(
        session_id=session_id,
        trace_id=resolved_trace_id,
        receipts=receipts,
        recorded_events=recorded_events,
        registry_summaries=registry_summaries,
        proof_command="deterministic foundry variant commands",
        proof_exit_code=max_exit_code,
        duration_seconds=time.monotonic() - started,
    )


def _foundry_variant_command(variant_id: str, index: int) -> tuple[str, ...]:
    exit_code = 1 if (index + 1) % 5 == 0 else 0
    code = (
        "import sys; "
        f"print('shadow foundry {variant_id} evaluated'); "
        f"raise SystemExit({exit_code})"
    )
    return (sys.executable, "-c", code)


def _foundry_candidate_patch(variant_id: str, index: int) -> str:
    return "\n".join(
        [
            "diff --git a/reports/evolution_foundry/README.md b/reports/evolution_foundry/README.md",
            "new file mode 100644",
            "index 0000000..0000000",
            "--- /dev/null",
            "+++ b/reports/evolution_foundry/README.md",
            "@@ -0,0 +1,3 @@",
            f"+# Shadow candidate {variant_id}",
            f"+variant_index={index}",
            "+This artifact is archive-only and must not be applied automatically.",
            "",
        ]
    )


def receipts_from_sealed_packet_result(
    result: Any,
    *,
    parent_id: str | None = None,
    model_id: str = "darwin-sealed-packet",
) -> list[RecursiveReceipt]:
    """Convert a sealed Darwin packet outcome into recursive-discovery receipts."""

    packet_root = str(getattr(result, "packet_root", ""))
    proposal_id = str(getattr(result, "proposal_id", "") or "")
    archive_entry_id = str(getattr(result, "archive_entry_id", "") or "")
    candidate_id = proposal_id or f"sealed-candidate-{stable_payload_hash({'packet_root': packet_root})[:10]}"
    trace_id = parent_id or f"sealed-packet-{stable_payload_hash({'packet_root': packet_root, 'candidate': candidate_id})[:12]}"
    exit_code = getattr(result, "proof_exit_code", None)
    accepted = bool(getattr(result, "accepted", False))
    applied = bool(getattr(result, "applied", False))
    shadow = bool(getattr(result, "shadow", True))
    files_changed = [
        str(path)
        for path in getattr(result, "files_changed", [])
        if str(path).strip()
    ]
    proof = CommandReceipt(
        command=_sealed_packet_command_text(result),
        exit_code=int(exit_code if exit_code is not None else (0 if accepted else 1)),
        wall_time_seconds=None,
    )
    receipts = build_recursive_shadow_run_receipts(
        parent_id=trace_id,
        limitation_id=f"lim-sealed-packet-{stable_payload_hash({'packet_root': packet_root})[:10]}",
        candidate_id=candidate_id,
        eval_id=f"eval-sealed-packet-{stable_payload_hash({'packet_root': packet_root, 'candidate': candidate_id})[:10]}",
        prompt="Bridge a Darwin sealed-packet outcome into recursive-discovery receipts.",
        model_id=model_id,
        files_touched=files_changed or ["sealed_packet"],
        proof=proof,
        sandbox_path=packet_root,
        source="darwin_sealed_packet",
        archive_entry_id=archive_entry_id,
        metadata={
            "accepted": accepted,
            "applied": applied,
            "shadow": shadow,
            "reason": str(getattr(result, "reason", "")),
            "refused_checks": list(getattr(result, "refused_checks", [])),
        },
    )
    promotion = receipts[-1]
    if isinstance(promotion, PromotionDecisionReceipt):
        promotion.status = "pending" if accepted and not applied else "blocked"
        promotion.summary = (
            "Sealed packet archived in shadow mode and held for human promotion."
            if accepted and not applied
            else "Sealed packet is not eligible for autonomous promotion."
        )
    return receipts


async def record_sealed_packet_recursive_receipts(
    result: Any,
    *,
    session_id: str,
    task_id: str = "",
    event_log: EventLog | None = None,
    evaluation_registry: Any | None = None,
    created_by: str = "darwin.sealed_packet",
    trace_id: str | None = None,
) -> RecursiveDiscoveryRunResult:
    """Persist recursive receipts for a sealed packet result."""

    started = time.monotonic()
    receipts = receipts_from_sealed_packet_result(result, parent_id=trace_id)
    resolved_trace_id = trace_id or (receipts[0].parent_id or receipts[0].receipt_id)
    recorder = RecursiveDiscoveryRecorder(event_log)
    recorded_events = [
        recorder.record(
            receipt,
            session_id=session_id,
            agent_id=created_by,
            trace_id=resolved_trace_id,
        ).event
        for receipt in receipts
    ]
    registry_summaries: list[dict[str, Any]] = []
    if evaluation_registry is not None:
        for receipt in receipts:
            registry_result = await evaluation_registry.record_recursive_discovery_receipt(
                receipt.model_dump(mode="json"),
                session_id=session_id,
                task_id=task_id,
                trace_id=resolved_trace_id,
                created_by=created_by,
            )
            registry_summaries.append(dict(registry_result.summary))
    proof = receipts[1].commands[0] if receipts[1].commands else CommandReceipt(command="", exit_code=0)
    return RecursiveDiscoveryRunResult(
        session_id=session_id,
        trace_id=resolved_trace_id,
        receipts=receipts,
        recorded_events=recorded_events,
        registry_summaries=registry_summaries,
        proof_command=proof.command,
        proof_exit_code=proof.exit_code,
        duration_seconds=time.monotonic() - started,
    )


async def _run_proof_command(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: float,
) -> tuple[CommandReceipt, dict[str, Any]]:
    started = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        timed_out = False
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            timed_out = True
            proc.kill()
            stdout, stderr = await proc.communicate()
        exit_code = proc.returncode if proc.returncode is not None else -1
        if timed_out and exit_code == 0:
            exit_code = 124
    except OSError as exc:
        stdout = b""
        stderr = str(exc).encode("utf-8", errors="replace")
        timed_out = False
        exit_code = 127
    return (
        CommandReceipt(
            command=shlex.join([str(part) for part in command]),
            exit_code=int(exit_code),
            wall_time_seconds=round(time.monotonic() - started, 3),
        ),
        {
            "timed_out": timed_out,
            "stdout_hash": hashlib.sha256(stdout).hexdigest(),
            "stderr_hash": hashlib.sha256(stderr).hexdigest(),
        },
    )


def _sealed_packet_command_text(result: Any) -> str:
    test_results = getattr(result, "test_results", {}) or {}
    sealed = dict(test_results.get("sealed_packet") or {})
    command = str(sealed.get("proof_command") or "").strip()
    if command:
        return command
    return "sealed_packet.proof"


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
