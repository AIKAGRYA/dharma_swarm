"""End-to-end Operator Idea Spark ingest orchestrator.

Runs one fired-in input through the whole receipt-backed chain, recording each
hop into the lifecycle receipt by ``correlation_id``:

    OperatorInputReceipt -> IdeaSparkCandidate -> Chetana staged atom
      -> MemoryKernel receipt -> Semantic Commons owner route
      -> proposal/task/BetCard -> implementation/experiment receipt
      -> retrieval proof by correlation_id

Every substantive capability is delegated to its existing owner; this module is
pure plumbing. It takes injectable roots (``state_root``, ``commons``) and a
fixed ``created_at`` so a full run is deterministic and hermetic (the e2e
fixture runs it under temp roots with no network).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.semantic_commons import SemanticCommons

from .action_routing import ActionRoute, route_action
from .chetana_adapter import StagedCandidate, stage_candidate
from .memory_bridge import MemoryKernelBridgeResult, emit_memory_kernel_receipt
from .paths import idea_spark_root
from .projection import candidate_from_operator_receipt
from .retrieval import LifecycleProbeResult, probe_by_correlation_id
from .schemas import (
    AuthorityLevel,
    IdeaSparkCandidate,
    OperatorInputReceipt,
    RedactionPolicy,
    SourceKind,
    SourceRights,
    utc_now_iso,
)
from .semantic_routing import SemanticRoute, route_candidate
from .store import (
    append_candidate,
    build_operator_input_receipt,
    update_lifecycle_receipt,
    write_input_receipt,
)

IMPLEMENTATION_RECEIPT_SCHEMA = "idea_spark_implementation_receipt.v0"


@dataclass(frozen=True)
class LifecycleRunResult:
    correlation_id: str
    input_receipt: OperatorInputReceipt
    candidate: IdeaSparkCandidate
    staged: StagedCandidate
    memory: MemoryKernelBridgeResult
    route: SemanticRoute
    action: ActionRoute
    implementation_receipt_id: str
    probe: LifecycleProbeResult


def _write_implementation_receipt(
    *,
    correlation_id: str,
    candidate_id: str,
    action: ActionRoute,
    state_root: Path | None,
    created_at: str,
) -> str:
    impl_id = f"impl_{hashlib.sha256(f'{correlation_id}|{action.lane}'.encode()).hexdigest()[:16]}"
    directory = idea_spark_root(state_root) / "implementation_receipts"
    directory.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": IMPLEMENTATION_RECEIPT_SCHEMA,
        "implementation_receipt_id": impl_id,
        "correlation_id": correlation_id,
        "candidate_id": candidate_id,
        "lane": action.lane,
        "proposal_id": action.proposal_id,
        "task_id": action.task_id,
        "bet_id": action.bet_id,
        "dispatch_authority": action.dispatch_authority,
        "mock": True,
        "created_at": created_at,
    }
    path = directory / f"{correlation_id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return impl_id


def run_operator_idea_spark(
    *,
    source_kind: SourceKind,
    source_ref: str,
    content: str,
    source_rights: SourceRights,
    captured_by: str = "operator",
    claim: str | None = None,
    title: str | None = None,
    why_now: str = "",
    domain: str = "",
    authority_level: AuthorityLevel | None = None,
    redaction_policy: RedactionPolicy | None = None,
    commons: SemanticCommons | None = None,
    state_root: Path | None = None,
    created_at: str | None = None,
    proposals_path: Path | None = None,
    frontier_path: Path | None = None,
    grant_authority: bool = False,
) -> LifecycleRunResult:
    """Run the full ingest lifecycle for one fired-in input."""
    when = created_at or utc_now_iso()
    resolved_claim = claim if claim is not None else content

    # 1. Immutable source receipt.
    receipt = build_operator_input_receipt(
        source_kind=source_kind,
        source_ref=source_ref,
        content=content,
        source_rights=source_rights,
        captured_by=captured_by,
        captured_at=when,
        redaction_policy=redaction_policy,
    )
    write_input_receipt(receipt, state_root)
    update_lifecycle_receipt(
        receipt.correlation_id,
        state_root,
        status="captured",
        input_id=receipt.input_id,
    )

    # 2. Normalized candidate (embeds idea_spark_triage.v0).
    candidate = candidate_from_operator_receipt(
        receipt,
        claim=resolved_claim,
        title=title,
        why_now=why_now,
        domain=domain,
        authority_level=authority_level,
        now=when,
    )
    append_candidate(candidate, state_root)
    update_lifecycle_receipt(
        receipt.correlation_id, state_root, candidate_id=candidate.candidate_id
    )

    # 3. Chetana staged (untrusted) atom.
    staged = stage_candidate(candidate, captured_by=captured_by)
    update_lifecycle_receipt(
        receipt.correlation_id,
        state_root,
        status="staged",
        chetana_staged_atom_id=staged.atom_id,
        evidence_paths=[str(staged.path)],
    )

    # 4. Governed MemoryKernel receipt (no silent mutation).
    memory = emit_memory_kernel_receipt(
        candidate,
        state_root=state_root,
        created_at=when,
        redaction_policy=receipt.redaction_policy,
    )

    # 5. Semantic Commons owner route (fail-closed).
    route, routed_candidate = route_candidate(
        candidate, commons=commons, state_root=state_root, created_at=when
    )

    # 6. Proposal / task / BetCard (authority-gated).
    action = route_action(
        routed_candidate,
        state_root=state_root,
        proposals_path=proposals_path,
        frontier_path=frontier_path,
        grant_authority=grant_authority,
    )

    # 7. Mock implementation/experiment receipt + lifecycle closure.
    impl_id = _write_implementation_receipt(
        correlation_id=receipt.correlation_id,
        candidate_id=candidate.candidate_id,
        action=action,
        state_root=state_root,
        created_at=when,
    )
    update_lifecycle_receipt(
        receipt.correlation_id,
        state_root,
        status="implemented",
        implementation_receipt_id=impl_id,
    )

    # 8. Retrieval proof.
    probe = probe_by_correlation_id(receipt.correlation_id, state_root)
    update_lifecycle_receipt(
        receipt.correlation_id, state_root, retrieval_probe_id=probe.retrieval_probe_id
    )

    return LifecycleRunResult(
        correlation_id=receipt.correlation_id,
        input_receipt=receipt,
        candidate=routed_candidate,
        staged=staged,
        memory=memory,
        route=route,
        action=action,
        implementation_receipt_id=impl_id,
        probe=probe,
    )
