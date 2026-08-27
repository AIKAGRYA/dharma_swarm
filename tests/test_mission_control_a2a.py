from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dharma_swarm.a2a.agent_card import (
    A2A_INBOX_ROUTE_ALIAS,
    a2a_inbox_subject,
)
from dharma_swarm.a2a.envelope_schema import build_send_envelope
from dharma_swarm.foundry.evaluator import (
    Candidate,
    EvaluationRunIdentity,
    candidate_digest,
    canonical_digest as foundry_digest,
)
from dharma_swarm.forge_v1.forge_v2 import promote
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.forge_v1.forge_v2.verify_promotion import (
    sign_promotion_verification,
    sign_receipt,
    verify_promotion,
)
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_a2a import (
    A2A_BINDING_SCHEMA,
    A2AEvidencePhase,
    A2AExecutionObservation,
    A2ANativeExecutionRef,
    A2APatchPromotionEvaluator,
    MissionControlA2AProjection,
)
from dharma_swarm.mission_control_contract import (
    MissionControlError,
    ReconciliationState,
)
from dharma_swarm.mission_control_verification import (
    FOUNDRY_PATCH_VERIFICATION_SCHEMA,
    PATCH_VERIFICATION_SCHEMA,
    PATCH_VIBE_SCHEMA,
    ExpectedPromotionBindings,
    PatchPromotionVerifier,
    PatchPromotionWarrant,
    PromotionRefusal,
    VerifierPrincipalBinding,
    expected_vibe_halt_binding,
)
from dharma_swarm.models import GateDecision, TaskStatus
from dharma_swarm.operator_core.governed_work_admission import (
    GovernedWorkAdmission,
)
from dharma_swarm.operator_core.semantic_receipt import (
    SCHEMA_VERSION as SEMANTIC_SCHEMA,
    validate_semantic_receipt,
)
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard
from scripts.runtime.a2a_domain_reply_artifact import (
    build_domain_reply_artifact,
    write_artifact_author_receipt,
)
from scripts.runtime.a2a_domain_reply_worker import (
    load_domain_reply_target,
    publish_domain_reply,
)
from scripts.runtime.codex_composer_semantic_responder import (
    Delivery,
    mark_processed,
    write_responder_receipt,
)

_A2A_HELPER_MODULES = (
    "dharma_swarm.mission_control_a2a_projection",
    "dharma_swarm.mission_control_a2a_evaluator",
    "dharma_swarm.mission_control_a2a_io",
)


@pytest.mark.parametrize("modules", tuple(permutations(_A2A_HELPER_MODULES)))
def test_a2a_helper_modules_cold_import_in_any_order(modules: tuple[str, ...]) -> None:
    code = ";".join(f"import {module}" for module in modules)
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _public_key(key: Ed25519PrivateKey) -> str:
    return (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        .hex()
    )


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _write_json(path: Path, value: dict) -> bytes:
    raw = _json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def _tree_fingerprint(root: Path) -> dict[str, tuple[int, str]]:
    return {
        str(path.relative_to(root)): (
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _delivery_id(path: Path, delivery: dict, envelope: dict) -> str:
    stable = {
        "path": str(path.resolve()),
        "packet_id": envelope["packet_id"],
        "reply_subject": envelope["reply_subject"],
        "envelope_sha256": delivery["envelope_sha256"],
    }
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True).encode(),
    ).hexdigest()[:24]


class _FakePublisher:
    async def publish(self, subject: str, payload: bytes, **kwargs):
        del subject, payload, kwargs
        return SimpleNamespace(stream="DHARMA_A2A", seq=1)

    async def flush(self, timeout: float | None = None) -> None:
        del timeout


@dataclass
class _Context:
    board: TaskBoard
    runtime: RuntimeStateStore
    control: MissionControl
    projection: MissionControlA2AProjection
    mission_id: str
    task_id: str
    expected: ExpectedPromotionBindings
    job_db: Path
    delivery_path: Path
    state_dir: Path
    processed_path: Path
    response_path: Path
    foundry_key: Ed25519PrivateKey
    vibe_key: Ed25519PrivateKey


async def _context(tmp_path: Path, *, proposal: bool) -> _Context:
    mission_id = "mission-reflex-1"
    packet_id = "packet-1"
    agent = "codex_composer"
    proposal_id = "proposal-1"
    correlation = f"a2a_send:{agent}:{packet_id}"
    subject = a2a_inbox_subject(agent)
    inbox_root = tmp_path / "inboxes"
    job_root = tmp_path / "semantic_jobs"
    responder_root = tmp_path / "external_agents"
    outbox_root = tmp_path / "outboxes"
    trusted_root = tmp_path / "trusted_receipts"
    for root in (
        inbox_root,
        job_root,
        responder_root,
        outbox_root,
        trusted_root,
    ):
        root.mkdir(parents=True)

    content = "repair the exact candidate"
    content_sha = _sha(content)
    envelope = build_send_envelope(
        packet_id=packet_id,
        sender="operator",
        to=agent,
        subject=subject,
        kind="task",
        route=A2A_INBOX_ROUTE_ALIAS,
        target_uid=agent,
        timestamp="2026-08-28T00:00:00Z",
        extra={"content": content, "sha256": content_sha},
    )
    reply_subject = envelope["reply_subject"]
    envelope_sha = _sha(json.dumps(envelope, sort_keys=True))
    delivery = {
        "schema_version": "dharma.a2a.inbox_delivery.v1",
        "agent_uid": agent,
        "bridge_kind": "filesystem_delivery_handler",
        "source_subject": envelope["subject"],
        "envelope_sha256": envelope_sha,
        "envelope": envelope,
    }
    delivery_path = inbox_root / agent / f"{packet_id}.json"
    _write_json(delivery_path, delivery)
    delivery_id = _delivery_id(delivery_path, delivery, envelope)

    job_db = job_root / f"{agent}.sqlite3"
    connection = sqlite3.connect(job_db)
    try:
        with connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE semantic_jobs (event_id TEXT PRIMARY KEY, "
                "envelope_sha256 TEXT, envelope_json TEXT, status TEXT, "
                "created_at TEXT, updated_at TEXT)",
            )
            connection.execute(
                "INSERT INTO semantic_jobs VALUES (?, ?, ?, 'PENDING', 'now', 'now')",
                (packet_id, envelope_sha, json.dumps(envelope, sort_keys=True)),
            )
    finally:
        connection.close()

    runtime = RuntimeStateStore(
        tmp_path / "runtime.db",
        include_memory_plane=False,
    )
    board = TaskBoard(tmp_path / "tasks.db")
    await runtime.init_db()
    await board.init_db()
    control = MissionControl(board, runtime)
    await control.create_mission(mission_id, title="Governed reflex")
    task = await control.create_task(
        mission_id,
        title="Patch candidate",
        metadata={
            "preserved": "yes",
            "a2a_binding": {
                "schema_version": A2A_BINDING_SCHEMA,
                "agent_uid": agent,
                "packet_id": packet_id,
                "correlation_id": correlation,
                "delivery_id": delivery_id,
                "proposal_id": proposal_id,
                "content_sha256": content_sha,
            },
        },
    )

    send_path = trusted_root / "send" / "send.json"
    send = {
        "schema_version": "dharma.a2a.send_receipt.v1",
        "packet_id": packet_id,
        "target_uid": agent,
        "to": agent,
        "from": "operator",
        "reply_subject": reply_subject,
        "status": "PUBLISH_ACKED",
    }
    _write_json(send_path, send)
    prompt_path = trusted_root / "prompts" / "packet-1.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("review packet-1", encoding="utf-8")
    semantic = validate_semantic_receipt(
        {
            "schema_version": SEMANTIC_SCHEMA,
            "receipt_id": "semr-packet-1",
            "created_at": "2026-08-28T00:00:00Z",
            "agent_uid": agent,
            "critic_agent_id": "ollama:test-model",
            "model_identity": {"provider": "ollama", "model": "test-model"},
            "authored_by_model": True,
            "review_target": f"a2a:{packet_id}",
            "intent_ack": True,
            "capability_match": 1.0,
            "understood_request": True,
            "missing_context": [],
            "verdict": "approve",
            "summary": "The exact packet was semantically reviewed.",
            "recommendations": [],
            "acceptance_gates": [],
            "explicit_disagreement": "",
            "evidence_refs": [str(prompt_path)],
            "confidence": 0.9,
            "not_claimed_agents": ["operator"],
            "failure_type": "",
            "failure_reason": "",
            "correlation_id": packet_id,
            "reply_to": reply_subject,
            "model_call_latency_ms": 1,
            "prompt_sha256": _sha("prompt"),
            "raw_response_sha256": _sha("response"),
        },
    )
    semantic_path = trusted_root / "semantic" / "semantic.json"
    _write_json(semantic_path, semantic)

    artifact = build_domain_reply_artifact(
        delivery_record=delivery,
        agent_uid=agent,
        verdict="approve",
        summary="Semantic packet receipt only; source audit not claimed.",
        evidence_refs=[str(delivery_path), str(prompt_path), str(semantic_path)],
        send_receipt_path=send_path,
        peer_model_processed_claim=True,
        semantic_reply_claim=True,
        author_kind=f"{agent}_semantic_inbox_drain",
    )
    artifact.update(
        {
            "semantic_receipt_path": str(semantic_path),
            "semantic_receipt_id": semantic["receipt_id"],
            "semantic_claim_basis": semantic["semantic_claim_basis"],
            "handler_ack_is_semantic_cognition": False,
            "source_audit_claim": False,
            "authenticated_target_runtime_claim": False,
            "semantic_audit_depth": "packet_only",
        },
    )
    artifact_path = outbox_root / agent / f"{packet_id}-domain-reply.json"
    artifact_raw = _write_json(artifact_path, artifact)
    artifact_sha = hashlib.sha256(artifact_raw).hexdigest()
    author_path = write_artifact_author_receipt(
        receipt_dir=trusted_root / "artifact_authors",
        artifact_path=artifact_path,
        artifact=artifact,
        delivery_record_path=delivery_path,
    )
    drain = {
        "schema_version": "dharma.a2a.codex_composer_semantic_inbox_drain.v1",
        "timestamp": "2026-08-28T00:00:00Z",
        "status": "SEMANTIC_INBOX_DRAINED",
        "agent_uid": agent,
        "packet_id": packet_id,
        "reply_subject": reply_subject,
        "delivery_record_path": str(delivery_path),
        "prompt_file": str(prompt_path),
        "semantic_receipt_path": str(semantic_path),
        "semantic_receipt_id": semantic["receipt_id"],
        "domain_reply_artifact_path": str(artifact_path),
        "domain_reply_artifact_author_receipt_path": str(author_path),
        "semantic_reply_claim": True,
        "peer_model_processed_claim": True,
        "source_audit_claim": False,
        "authenticated_target_runtime_claim": False,
        "semantic_audit_depth": "packet_only",
        "handler_ack_is_semantic_cognition": False,
        "typed_reply_publish_required_next": True,
        "operator_contact_note": "canonical model-authored drain",
    }
    drain_path = trusted_root / "drains" / "drain.json"
    _write_json(drain_path, drain)
    drain["drain_receipt_path"] = str(drain_path)

    target = load_domain_reply_target(
        send_receipt_path=send_path,
        reply_artifact_path=artifact_path,
        agent_uid=agent,
        outbox_root=outbox_root,
    )
    publish = await publish_domain_reply(
        target,
        publisher=_FakePublisher(),
        receipt_dir=trusted_root / "publish",
        endpoint="nats://127.0.0.1:4222",
        stream="DHARMA_A2A",
    )
    response = {
        "schema_version": "dharma.a2a.codex_composer_semantic_responder.v1",
        "timestamp": "2026-08-28T00:00:00Z",
        "status": "DOMAIN_REPLY_PUBLISHED",
        "agent_uid": agent,
        "delivery_id": delivery_id,
        "packet_id": packet_id,
        "reply_subject": reply_subject,
        "delivery_record_path": str(delivery_path),
        "send_receipt_path": str(send_path),
        "semantic_drain_receipt": drain,
        "domain_reply_publish_receipt": publish,
        "semantic_reply_claim": True,
        "domain_receipt_claim": True,
        "handler_ack_is_semantic_cognition": False,
        "authenticated_target_runtime_claim": False,
        "no_publish": False,
    }
    state_dir = responder_root / agent / "nest" / "semantic_responder"
    response_path = write_responder_receipt(state_dir, response)
    native_delivery = Delivery(
        path=delivery_path,
        payload=delivery,
        envelope=envelope,
        packet_id=packet_id,
        reply_subject=reply_subject,
        delivery_id=delivery_id,
    )
    mark_processed(
        state_dir,
        native_delivery,
        status="DOMAIN_REPLY_PUBLISHED",
        receipt_path=str(response_path),
    )

    candidate = Candidate(
        candidate_id=proposal_id,
        target_id="dharma_swarm",
        diff="diff",
        origin_model=agent,
    )
    foundry_run = EvaluationRunIdentity.from_execution(
        run_id="foundry-run-1",
        command=["python", "-m", "pytest", "tests/test_dgm_loop.py"],
        output={"exit_code": 0, "stdout": "passed", "stderr": ""},
    )
    foundry_key = Ed25519PrivateKey.generate()
    vibe_key = Ed25519PrivateKey.generate()
    expected = ExpectedPromotionBindings(
        mission_id=mission_id,
        task_id=task.task_id,
        attempt_id=packet_id,
        lease_id=delivery_id,
        packet_id=packet_id,
        correlation_id=correlation,
        delivery_id=delivery_id,
        proposal_id=proposal_id,
        candidate_digest=candidate_digest(candidate),
        diff_sha256=_sha(candidate.diff),
        base_sha="436ebcdcea9573a3dac93eb47078d1d83dcab7ba",
        artifact_sha256=artifact_sha,
        lineage_digest=foundry_digest({"candidate_id": proposal_id}),
        command_digest=foundry_run.command_digest,
        output_digest=foundry_run.output_digest,
        isolation_digest=foundry_digest(
            {"isolation_level": "docker_nonet", "network_disabled": True},
        ),
        authorized_source_files=("dharma_swarm/dgm_loop.py",),
        executor_agent_uid=agent,
        executor_run_id="executor-run-1",
        foundry_verifier=VerifierPrincipalBinding(
            role="foundry",
            agent_uid="forge_independent_verifier",
            run_id=foundry_run.run_id,
            signer_public_key=_public_key(foundry_key),
        ),
        vibe_verifier=VerifierPrincipalBinding(
            role="vibe_halt",
            agent_uid="vibe_halt_independent_verifier",
            run_id="vibe-run-1",
            signer_public_key=_public_key(vibe_key),
        ),
    )
    executor = ExecutionIdentity.new(
        task_id=task.task_id,
        trace_id="trace-executor",
        correlation_id=correlation,
        run_id=expected.executor_run_id,
        claim_id="claim-executor",
        idempotency_key="idem-executor",
        agent_id=agent,
        session_id=f"mission:{mission_id}",
        proposal_id=proposal_id,
    )
    await runtime.record_execution_identity(executor, source="test")
    if proposal:
        await runtime.commit_self_mod_receipt_exact(
            executor,
            stage="proposal",
            proposal_id=proposal_id,
            status="proposed",
            payload={
                "schema_version": "dharma.a2a.patch_candidate.v1",
                "mission_id": mission_id,
                "task_id": task.task_id,
                "attempt_id": packet_id,
                "lease_id": delivery_id,
                "packet_id": packet_id,
                "correlation_id": correlation,
                "delivery_id": delivery_id,
                "proposal_id": proposal_id,
                "candidate_digest": expected.candidate_digest,
                "diff_sha256": expected.diff_sha256,
                "base_sha": expected.base_sha,
                "artifact_sha256": artifact_sha,
                "authorized_source_files": list(
                    expected.authorized_source_files,
                ),
            },
        )
    projection = MissionControlA2AProjection(
        board,
        runtime,
        inbox_root=inbox_root,
        semantic_job_root=job_root,
        responder_state_root=responder_root,
        outbox_root=outbox_root,
        trusted_receipt_roots=(trusted_root,),
    )
    return _Context(
        board=board,
        runtime=runtime,
        control=control,
        projection=projection,
        mission_id=mission_id,
        task_id=task.task_id,
        expected=expected,
        job_db=job_db,
        delivery_path=delivery_path,
        state_dir=state_dir,
        processed_path=state_dir / "processed_deliveries.jsonl",
        response_path=response_path,
        foundry_key=foundry_key,
        vibe_key=vibe_key,
    )


async def _record_verifier(
    ctx: _Context,
    principal: VerifierPrincipalBinding,
) -> None:
    await ctx.runtime.record_execution_identity(
        ExecutionIdentity.new(
            task_id=ctx.task_id,
            trace_id=f"trace-{principal.role}",
            correlation_id=ctx.expected.correlation_id,
            parent_run_id=ctx.expected.executor_run_id,
            run_id=principal.run_id,
            claim_id=f"claim-{principal.role}",
            idempotency_key=f"idem-{principal.role}",
            agent_id=principal.agent_uid,
            session_id=f"mission:{ctx.mission_id}",
            proposal_id=ctx.expected.proposal_id,
        ),
        source="test",
    )


async def _record_verifiers(ctx: _Context) -> None:
    await _record_verifier(ctx, ctx.expected.foundry_verifier)
    await _record_verifier(ctx, ctx.expected.vibe_verifier)


def _signal(expected: ExpectedPromotionBindings) -> dict:
    return {
        "run_id": expected.foundry_verifier.run_id,
        "signal_key": f"forge-signal:{expected.candidate_digest}",
        "arm": "verify_chain",
        "taskbed": "fresh_taskbed",
        "mission_class": "verifier_role",
        "epoch_id": "epoch-test-1",
        "overall_ci": {
            "n": 500,
            "mean": 0.06,
            "lower": 0.02,
            "upper": 0.10,
            "p_le_0": 0.01,
        },
        "explore_ci": {
            "n": 0,
            "mean": 0.0,
            "lower": 0.0,
            "upper": 0.0,
            "p_le_0": 1.0,
        },
        "confirm_ci": {
            "n": 500,
            "mean": 0.06,
            "lower": 0.02,
            "upper": 0.10,
            "p_le_0": 0.01,
        },
        "fdr_positive_significant": True,
        "contamination_state": "fresh_heldout",
        "sealed_provenance": {"contamination_state": "fresh_heldout"},
        "class_null": "self_moa",
        "null_survived": False,
        "evidence_strength": 0.9,
        "packet_guard_review": {
            "deterministic_review": {
                "verdict": "pass_for_next_scale",
                "findings": [],
            },
        },
        "e4_discrimination_receipt": {
            "decision": "pass",
            "promotion_gate_satisfied": True,
            "blockers": [],
        },
        "promotion_blockers": [],
        "report_positive_promotion_allowed": False,
        "source_files": list(expected.authorized_source_files),
    }


class _AllowTelos:
    def check(self, *_args, **_kwargs):
        return (
            GateDecision.ALLOW,
            SimpleNamespace(receipt_sha256=_sha("telos")),
            None,
        )


def _forge_verdict(
    expected: ExpectedPromotionBindings,
    receipt_key: Ed25519PrivateKey,
) -> dict:
    epoch = _sha("receipt-epoch")
    receipts = [
        sign_receipt(
            name=name,
            payload={"receipt": name, "status": "pass"},
            signing_key=receipt_key,
            epoch_ruler_sha256=epoch,
            key_id="receipt-judge-test",
        )
        for name in promote.REQUIRED_RECEIPTS_V0_ABSENT
    ]

    def admission(request) -> GovernedWorkAdmission:
        return GovernedWorkAdmission(
            request_id=request.request_id,
            decision="allow",
            reasons=[],
            required_receipts=[],
            reduced_authority={
                "work_kind": "promotion",
                "risk_tier": "Q4",
                "allowed_files": list(expected.authorized_source_files),
                "forbidden_files": [],
                "autonomy_level": "operator_lease",
            },
        )

    return verify_promotion(
        _signal(expected),
        signed_receipts=receipts,
        operator_lease={"lease_id": expected.lease_id},
        trusted_receipt_public_keys=(_public_key(receipt_key),),
        lease_verifier_fn=lambda lease: lease.get("lease_id") == expected.lease_id,
        telos_gatekeeper=_AllowTelos(),
        admission_fn=admission,
    )


def _signed_vibe(
    expected: ExpectedPromotionBindings,
    key: Ed25519PrivateKey,
) -> dict:
    body = {
        "schema": PATCH_VIBE_SCHEMA,
        "candidate_digest": expected.candidate_digest,
        "diff_sha256": expected.diff_sha256,
        "verifier": {
            "agent_uid": expected.vibe_verifier.agent_uid,
            "run_id": expected.vibe_verifier.run_id,
            "parent_run_id": expected.executor_run_id,
        },
        "ran": True,
        "reported_outcome": "clean",
        "diff_bound": True,
        "calibration_only": False,
        "findings": [],
        "errors": [],
        "blockers": [],
        "process": {
            "exit_code": 0,
            "timed_out": False,
            "output_limited": False,
        },
    }
    body["payload_sha256"] = canonical_sha256(body)
    message = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    body["signature"] = {
        "scheme": "ed25519",
        "key_id": "vibe-verifier-test",
        "public_key": _public_key(key),
        "signature": key.sign(message).hex(),
    }
    return body


def _signed_envelope(
    expected: ExpectedPromotionBindings,
    vibe: dict,
    judge_key: Ed25519PrivateKey,
    foundry_key: Ed25519PrivateKey,
    receipt_key: Ed25519PrivateKey,
) -> dict:
    foundry_verdict = _forge_verdict(expected, receipt_key)
    foundry_verdict["schema"] = FOUNDRY_PATCH_VERIFICATION_SCHEMA
    foundry_verdict["decision"] = "verified_evidence"
    foundry_verdict["live_apply_allowed"] = False
    forge = sign_promotion_verification(
        foundry_verdict,
        foundry_key,
        key_id="foundry-verifier-test",
    )
    return sign_promotion_verification(
        {
            "schema": PATCH_VERIFICATION_SCHEMA,
            "forge_verification": forge,
            "a2a_binding": expected.to_signed_binding(),
            "vibe_halt_binding": expected_vibe_halt_binding(
                vibe,
                expected=expected,
            ),
        },
        judge_key,
        key_id="patch-judge-test",
    )


def _unused_authority(expected: ExpectedPromotionBindings) -> PatchPromotionVerifier:
    judge_key = Ed25519PrivateKey.generate()
    return PatchPromotionVerifier(
        trusted_judge_public_keys=(_public_key(judge_key),),
        trusted_foundry_verifier_public_keys={
            expected.foundry_verifier.agent_uid: (
                expected.foundry_verifier.signer_public_key,
            ),
        },
        trusted_vibe_verifier_public_keys={
            expected.vibe_verifier.agent_uid: (
                expected.vibe_verifier.signer_public_key,
            ),
        },
    )


@pytest.mark.asyncio
async def test_mismatched_delivery_fails_closed(tmp_path: Path) -> None:
    ctx = await _context(tmp_path, proposal=False)
    task = await ctx.board.get(ctx.task_id)
    assert task is not None
    binding = {**task.metadata["a2a_binding"], "delivery_id": "0" * 24}
    await ctx.board.update_task(
        task.id,
        metadata={**task.metadata, "a2a_binding": binding},
    )
    with pytest.raises(MissionControlError, match="delivery content"):
        await ctx.projection.observe(ctx.mission_id, ctx.task_id)


@pytest.mark.asyncio
async def test_projection_never_calls_mission_lifecycle(tmp_path: Path) -> None:
    ctx = await _context(tmp_path, proposal=True)
    before = await ctx.board.get(ctx.task_id)
    observation = await ctx.projection.observe(
        ctx.mission_id,
        ctx.task_id,
        expected=ctx.expected,
    )
    after = await ctx.board.get(ctx.task_id)
    assert observation and observation.phase is A2AEvidencePhase.VERIFYING
    assert observation.proves_executor_liveness is False
    assert before == after
    assert after is not None and "a2a_projection" not in after.metadata
    assert (
        await ctx.runtime.list_delegation_runs(
            session_id=f"mission:{ctx.mission_id}",
        )
        == []
    )
    assert (
        await ctx.runtime.list_task_claims(
            session_id=f"mission:{ctx.mission_id}",
        )
        == []
    )
    snapshot = await ctx.control.get_snapshot(ctx.mission_id)
    assert snapshot is not None
    assert snapshot.reconciliation is ReconciliationState.COHERENT


@pytest.mark.asyncio
async def test_projection_preserves_exact_source_file_set_and_bytes(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=True)
    before = _tree_fingerprint(tmp_path)

    observation = await ctx.projection.observe(
        ctx.mission_id,
        ctx.task_id,
        expected=ctx.expected,
    )

    assert observation.phase is A2AEvidencePhase.VERIFYING
    assert _tree_fingerprint(tmp_path) == before


@pytest.mark.asyncio
async def test_observe_does_not_overwrite_concurrent_task_metadata(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=False)
    await ctx.projection.observe(ctx.mission_id, ctx.task_id)
    task = await ctx.board.get(ctx.task_id)
    assert task is not None
    await ctx.board.update_task(
        task.id,
        metadata={**task.metadata, "concurrent_owner_write": "preserved"},
    )
    await ctx.projection.observe(ctx.mission_id, ctx.task_id)
    refreshed = await ctx.board.get(ctx.task_id)
    assert refreshed is not None
    assert refreshed.metadata["concurrent_owner_write"] == "preserved"
    assert "a2a_projection" not in refreshed.metadata


@pytest.mark.asyncio
async def test_held_open_wal_job_is_visible(tmp_path: Path) -> None:
    ctx = await _context(tmp_path, proposal=False)
    with sqlite3.connect(ctx.job_db) as setup:
        setup.execute(
            "UPDATE semantic_jobs SET status = 'STALE' WHERE event_id = 'packet-1'",
        )
        setup.commit()
        setup.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    writer = sqlite3.connect(ctx.job_db)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute(
            "UPDATE semantic_jobs SET status = 'PENDING' WHERE event_id = 'packet-1'",
        )
        writer.commit()
        before = _tree_fingerprint(tmp_path)
        observation = await ctx.projection.observe(ctx.mission_id, ctx.task_id)
        assert observation.semantic_job_status == "PENDING"
        assert _tree_fingerprint(tmp_path) == before
    finally:
        writer.close()


@pytest.mark.asyncio
async def test_failed_semantic_job_status_never_verifies(tmp_path: Path) -> None:
    ctx = await _context(tmp_path, proposal=True)
    with sqlite3.connect(ctx.job_db) as connection:
        connection.execute(
            "UPDATE semantic_jobs SET status = 'FAILED' WHERE event_id = 'packet-1'",
        )
    with pytest.raises(MissionControlError, match="semantic job and delivery"):
        await ctx.projection.observe(
            ctx.mission_id,
            ctx.task_id,
            expected=ctx.expected,
        )


@pytest.mark.asyncio
async def test_mutated_envelope_requires_recomputed_transport_digest(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=True)
    delivery = json.loads(ctx.delivery_path.read_text())
    envelope = dict(delivery["envelope"])
    envelope["subject"] = "dharma.a2a.foreign-owner"
    delivery["envelope"] = envelope
    _write_json(ctx.delivery_path, delivery)
    with sqlite3.connect(ctx.job_db) as connection:
        connection.execute(
            "UPDATE semantic_jobs SET envelope_json = ? WHERE event_id = 'packet-1'",
            (json.dumps(envelope, sort_keys=True),),
        )
    with pytest.raises(MissionControlError, match="delivery content"):
        await ctx.projection.observe(
            ctx.mission_id,
            ctx.task_id,
            expected=ctx.expected,
        )


@pytest.mark.asyncio
async def test_compatibility_lane_route_never_verifies(tmp_path: Path) -> None:
    ctx = await _context(tmp_path, proposal=True)
    delivery = json.loads(ctx.delivery_path.read_text())
    envelope = dict(delivery["envelope"])
    assert envelope["subject"] == a2a_inbox_subject("codex_composer")
    assert envelope["route"] == A2A_INBOX_ROUTE_ALIAS
    envelope["subject"] = "dharma.a2a.codex_composer"
    envelope["route"] = "direct"
    delivery["envelope"] = envelope
    delivery["source_subject"] = envelope["subject"]
    delivery["envelope_sha256"] = _sha(json.dumps(envelope, sort_keys=True))
    _write_json(ctx.delivery_path, delivery)
    with sqlite3.connect(ctx.job_db) as connection:
        connection.execute(
            "UPDATE semantic_jobs SET envelope_sha256 = ?, envelope_json = ? "
            "WHERE event_id = 'packet-1'",
            (delivery["envelope_sha256"], json.dumps(envelope, sort_keys=True)),
        )
    with pytest.raises(MissionControlError, match="delivery content"):
        await ctx.projection.observe(
            ctx.mission_id,
            ctx.task_id,
            expected=ctx.expected,
        )


@pytest.mark.asyncio
async def test_noncanonical_delivery_bridge_kind_never_verifies(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=True)
    delivery = json.loads(ctx.delivery_path.read_text())
    delivery["bridge_kind"] = "jetstream_durable_consumer"
    _write_json(ctx.delivery_path, delivery)
    with pytest.raises(MissionControlError, match="delivery content"):
        await ctx.projection.observe(
            ctx.mission_id,
            ctx.task_id,
            expected=ctx.expected,
        )


@pytest.mark.asyncio
async def test_rejected_or_foreign_proposal_never_verifies(tmp_path: Path) -> None:
    ctx = await _context(tmp_path, proposal=True)
    with sqlite3.connect(ctx.runtime.db_path) as connection:
        connection.execute(
            "UPDATE runtime_receipts SET status = 'rejected' "
            "WHERE side_effect_key = 'self_mod:proposal-1:proposal'",
        )
    with pytest.raises(MissionControlError, match="patch candidate"):
        await ctx.projection.observe(
            ctx.mission_id,
            ctx.task_id,
            expected=ctx.expected,
        )

    with sqlite3.connect(ctx.runtime.db_path) as connection:
        connection.execute(
            "UPDATE runtime_receipts SET status = 'proposed', trace_id = 'foreign' "
            "WHERE side_effect_key = 'self_mod:proposal-1:proposal'",
        )
    with pytest.raises(MissionControlError, match="patch candidate"):
        await ctx.projection.observe(
            ctx.mission_id,
            ctx.task_id,
            expected=ctx.expected,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", ["flat_payload", "missing_idempotency"])
async def test_flat_or_partial_proposal_evidence_never_verifies(
    tmp_path: Path,
    tamper: str,
) -> None:
    ctx = await _context(tmp_path, proposal=True)
    side_effect_key = "self_mod:proposal-1:proposal"
    with sqlite3.connect(ctx.runtime.db_path) as connection:
        if tamper == "flat_payload":
            raw = connection.execute(
                "SELECT payload_json FROM runtime_receipts WHERE side_effect_key = ?",
                (side_effect_key,),
            ).fetchone()[0]
            flat_payload = json.loads(raw)["evidence"]
            connection.execute(
                "UPDATE runtime_receipts SET payload_json = ? WHERE side_effect_key = ?",
                (
                    json.dumps(
                        flat_payload,
                        sort_keys=True,
                        ensure_ascii=True,
                        allow_nan=False,
                        separators=(",", ":"),
                    ),
                    side_effect_key,
                ),
            )
        else:
            connection.execute(
                "DELETE FROM idempotency_records WHERE side_effect_key = ?",
                (side_effect_key,),
            )

    with pytest.raises(MissionControlError, match="exact atomic proposal"):
        await ctx.projection.observe(
            ctx.mission_id,
            ctx.task_id,
            expected=ctx.expected,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    ["SEMANTIC_RESPONDER_FAILED", "PUBLISH_RETRIES_EXHAUSTED_DLQ"],
)
async def test_failed_processed_status_never_executes(
    tmp_path: Path,
    status: str,
) -> None:
    ctx = await _context(tmp_path, proposal=False)
    row = json.loads(ctx.processed_path.read_text().strip())
    row["status"] = status
    ctx.processed_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    observation = await ctx.projection.observe(ctx.mission_id, ctx.task_id)
    assert observation.phase is A2AEvidencePhase.DELIVERED
    assert observation.responder_status == status
    assert not observation.artifact_sha256


@pytest.mark.asyncio
async def test_failed_response_cannot_hide_behind_published_processed_row(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=False)
    response = json.loads(ctx.response_path.read_text())
    response["status"] = "SEMANTIC_RESPONDER_FAILED"
    _write_json(ctx.response_path, response)
    with pytest.raises(MissionControlError, match="receipt.status"):
        await ctx.projection.observe(ctx.mission_id, ctx.task_id)


@pytest.mark.asyncio
async def test_numeric_semantic_claim_cannot_inhabit_boolean_evidence(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=False)
    response = json.loads(ctx.response_path.read_text())
    response["semantic_reply_claim"] = 1
    _write_json(ctx.response_path, response)
    with pytest.raises(MissionControlError, match="semantic_reply_claim"):
        await ctx.projection.observe(ctx.mission_id, ctx.task_id)


@pytest.mark.asyncio
async def test_numeric_source_audit_claim_cannot_coerce_to_boolean(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=False)
    response = json.loads(ctx.response_path.read_text())
    drain = response["semantic_drain_receipt"]
    drain["source_audit_claim"] = 0
    drain_path = Path(drain["drain_receipt_path"])
    _write_json(
        drain_path,
        {key: value for key, value in drain.items() if key != "drain_receipt_path"},
    )
    _write_json(ctx.response_path, response)
    with pytest.raises(MissionControlError, match="source_audit_claim must be boolean"):
        await ctx.projection.observe(ctx.mission_id, ctx.task_id)


@pytest.mark.asyncio
async def test_persisted_receipt_numeric_claim_cannot_equal_nested_boolean(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=False)
    response = json.loads(ctx.response_path.read_text())
    drain = response["semantic_drain_receipt"]
    drain_path = Path(drain["drain_receipt_path"])
    persisted = json.loads(drain_path.read_text())
    persisted["semantic_reply_claim"] = 1
    _write_json(drain_path, persisted)
    with pytest.raises(MissionControlError, match="nested semantic drain differs"):
        await ctx.projection.observe(ctx.mission_id, ctx.task_id)


@pytest.mark.asyncio
async def test_boolean_transport_sequence_cannot_inhabit_integer_evidence(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=False)
    response = json.loads(ctx.response_path.read_text())
    publish = response["domain_reply_publish_receipt"]
    publish["transport_ack"]["seq"] = True
    publish_path = Path(publish["receipt_path"])
    _write_json(
        publish_path,
        {key: value for key, value in publish.items() if key != "receipt_path"},
    )
    _write_json(ctx.response_path, response)
    with pytest.raises(MissionControlError, match="durable transport ack"):
        await ctx.projection.observe(ctx.mission_id, ctx.task_id)


@pytest.mark.asyncio
async def test_numeric_transport_stream_cannot_inhabit_string_evidence(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=False)
    response = json.loads(ctx.response_path.read_text())
    publish = response["domain_reply_publish_receipt"]
    publish["transport_ack"]["stream"] = 7
    publish_path = Path(publish["receipt_path"])
    _write_json(
        publish_path,
        {key: value for key, value in publish.items() if key != "receipt_path"},
    )
    _write_json(ctx.response_path, response)
    with pytest.raises(MissionControlError, match="durable transport ack"):
        await ctx.projection.observe(ctx.mission_id, ctx.task_id)


@pytest.mark.asyncio
async def test_failed_causation_send_receipt_never_executes(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=False)
    response = json.loads(ctx.response_path.read_text())
    send_path = Path(response["send_receipt_path"])
    send = json.loads(send_path.read_text())
    send["status"] = "PUBLISH_FAILED"
    _write_json(send_path, send)
    with pytest.raises(MissionControlError, match="canonical successful status"):
        await ctx.projection.observe(ctx.mission_id, ctx.task_id)


@pytest.mark.asyncio
async def test_foreign_parent_same_basename_receipt_fails_closed(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=False)
    foreign = tmp_path / "foreign" / ctx.response_path.name
    foreign.parent.mkdir()
    foreign.write_bytes(ctx.response_path.read_bytes())
    row = json.loads(ctx.processed_path.read_text().strip())
    row["receipt_path"] = str(foreign)
    ctx.processed_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(MissionControlError, match="exact trusted responder"):
        await ctx.projection.observe(ctx.mission_id, ctx.task_id)


@pytest.mark.asyncio
async def test_pure_warrant_writes_no_gate_receipt(tmp_path: Path) -> None:
    ctx = await _context(tmp_path, proposal=True)
    await _record_verifiers(ctx)
    observation = await ctx.projection.observe(
        ctx.mission_id,
        ctx.task_id,
        expected=ctx.expected,
    )
    judge_key = Ed25519PrivateKey.generate()
    receipt_key = Ed25519PrivateKey.generate()
    vibe = _signed_vibe(ctx.expected, ctx.vibe_key)
    envelope = _signed_envelope(
        ctx.expected,
        vibe,
        judge_key,
        ctx.foundry_key,
        receipt_key,
    )
    authority = PatchPromotionVerifier(
        trusted_judge_public_keys=(_public_key(judge_key),),
        trusted_foundry_verifier_public_keys={
            ctx.expected.foundry_verifier.agent_uid: (_public_key(ctx.foundry_key),),
        },
        trusted_vibe_verifier_public_keys={
            ctx.expected.vibe_verifier.agent_uid: (_public_key(ctx.vibe_key),),
        },
    )
    result = await A2APatchPromotionEvaluator(
        ctx.projection,
        verifier=authority,
    ).issue_warrant(
        observation,
        expected=ctx.expected,
        signed_patch_verification=envelope,
        vibe_halt_receipt=vibe,
    )
    assert isinstance(result, PatchPromotionWarrant)
    assert result
    warrant = result.to_dict()
    assert warrant["capability_scope"] == "projection_only_gate"
    assert warrant["repository_effect_authorized"] is False
    assert warrant["verification_separation"] == {
        "level": "distinct_signing_principals",
        "independent_processes_proven": False,
    }
    assert (
        len(
            {
                warrant["foundry_verifier"]["signer_public_key"],
                warrant["vibe_verifier"]["signer_public_key"],
                _public_key(judge_key),
            }
        )
        == 3
    )
    assert (
        await ctx.runtime.list_runtime_receipts(
            receipt_type="self_mod_gate",
        )
        == []
    )


@pytest.mark.asyncio
async def test_missing_durable_foundry_identity_refuses_warrant(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=True)
    observation = await ctx.projection.observe(
        ctx.mission_id,
        ctx.task_id,
        expected=ctx.expected,
    )
    result = await A2APatchPromotionEvaluator(
        ctx.projection,
        verifier=_unused_authority(ctx.expected),
    ).issue_warrant(
        observation,
        expected=ctx.expected,
        signed_patch_verification=None,
        vibe_halt_receipt=None,
    )
    assert isinstance(result, PromotionRefusal)
    assert result.blockers == ("missing_exact_durable_foundry_identity",)
    assert (
        await ctx.runtime.list_runtime_receipts(
            receipt_type="self_mod_gate",
        )
        == []
    )


@pytest.mark.asyncio
async def test_missing_durable_vibe_identity_refuses_warrant(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=True)
    await _record_verifier(ctx, ctx.expected.foundry_verifier)
    observation = await ctx.projection.observe(
        ctx.mission_id,
        ctx.task_id,
        expected=ctx.expected,
    )
    result = await A2APatchPromotionEvaluator(
        ctx.projection,
        verifier=_unused_authority(ctx.expected),
    ).issue_warrant(
        observation,
        expected=ctx.expected,
        signed_patch_verification=None,
        vibe_halt_receipt=None,
    )
    assert isinstance(result, PromotionRefusal)
    assert result.blockers == ("missing_exact_durable_vibe_identity",)
    assert (
        await ctx.runtime.list_runtime_receipts(
            receipt_type="self_mod_gate",
        )
        == []
    )


@pytest.mark.parametrize(
    ("role", "blocker"),
    (
        ("foundry_verifier", "invalid_durable_foundry_identity"),
        ("vibe_verifier", "invalid_durable_vibe_identity"),
    ),
)
@pytest.mark.asyncio
async def test_malformed_durable_verifier_identity_refuses_without_raising(
    tmp_path: Path,
    role: str,
    blocker: str,
) -> None:
    ctx = await _context(tmp_path, proposal=True)
    await _record_verifiers(ctx)
    principal = getattr(ctx.expected, role)
    with sqlite3.connect(ctx.runtime.db_path) as db:
        db.execute(
            "UPDATE execution_identities SET metadata_json = '{' WHERE run_id = ?",
            (principal.run_id,),
        )
        db.commit()
    observation = await ctx.projection.observe(
        ctx.mission_id,
        ctx.task_id,
        expected=ctx.expected,
    )

    result = await A2APatchPromotionEvaluator(
        ctx.projection,
        verifier=_unused_authority(ctx.expected),
    ).issue_warrant(
        observation,
        expected=ctx.expected,
        signed_patch_verification=None,
        vibe_halt_receipt=None,
    )

    assert isinstance(result, PromotionRefusal)
    assert result.blockers == (blocker,)


@pytest.mark.asyncio
async def test_conflicting_warrant_replay_fails_closed(tmp_path: Path) -> None:
    ctx = await _context(tmp_path, proposal=True)
    await _record_verifiers(ctx)
    observed = await ctx.projection.observe(
        ctx.mission_id,
        ctx.task_id,
        expected=ctx.expected,
    )
    with sqlite3.connect(ctx.runtime.db_path) as connection:
        payload = json.loads(
            connection.execute(
                "SELECT payload_json FROM runtime_receipts "
                "WHERE side_effect_key = 'self_mod:proposal-1:proposal'",
            ).fetchone()[0],
        )
        payload["evidence"]["diff_sha256"] = _sha("foreign-diff")
        connection.execute(
            "UPDATE runtime_receipts SET payload_json = ? "
            "WHERE side_effect_key = 'self_mod:proposal-1:proposal'",
            (
                json.dumps(
                    payload,
                    sort_keys=True,
                    ensure_ascii=True,
                    allow_nan=False,
                    separators=(",", ":"),
                ),
            ),
        )
    result = await A2APatchPromotionEvaluator(
        ctx.projection,
        verifier=_unused_authority(ctx.expected),
    ).issue_warrant(
        observed,
        expected=ctx.expected,
        signed_patch_verification=None,
        vibe_halt_receipt=None,
    )
    assert isinstance(result, PromotionRefusal)
    assert result.blockers == ("a2a_observation_revalidation_failed",)
    assert (
        await ctx.runtime.list_runtime_receipts(
            receipt_type="self_mod_gate",
        )
        == []
    )


@pytest.mark.asyncio
async def test_fabricated_unsealed_observation_cannot_warrant(
    tmp_path: Path,
) -> None:
    ctx = await _context(tmp_path, proposal=True)
    fabricated = A2AExecutionObservation(
        native_ref=A2ANativeExecutionRef(
            mission_id="no-such-mission",
            task_id="no-such-task",
            agent_uid="fabricated-agent",
            packet_id="fabricated-packet",
            correlation_id="fabricated-correlation",
            delivery_id="0" * 24,
            proposal_id="fabricated-proposal",
            content_sha256="0" * 64,
        ),
        phase=A2AEvidencePhase.VERIFYING,
        task_status=TaskStatus.PENDING,
        envelope_sha256="0" * 64,
        proposal_receipt_id="fabricated-receipt",
        proposal_receipt_sha256="0" * 64,
    )
    assert not fabricated
    result = await A2APatchPromotionEvaluator(
        ctx.projection,
        verifier=_unused_authority(ctx.expected),
    ).issue_warrant(
        fabricated,
        expected=ctx.expected,
        signed_patch_verification=None,
        vibe_halt_receipt=None,
    )
    assert isinstance(result, PromotionRefusal)
    assert result.blockers == ("unsealed_or_nonverifying_a2a_observation",)


@pytest.mark.asyncio
async def test_absent_databases_fail_without_creating_files(tmp_path: Path) -> None:
    board_path = tmp_path / "absent-board.db"
    runtime_path = tmp_path / "absent-runtime.db"
    projection = MissionControlA2AProjection(
        TaskBoard(board_path),
        RuntimeStateStore(runtime_path, include_memory_plane=False),
        inbox_root=tmp_path,
        semantic_job_root=tmp_path,
        responder_state_root=tmp_path,
        outbox_root=tmp_path,
    )
    with pytest.raises(MissionControlError, match="RuntimeState database"):
        await projection.observe("mission-missing", "task-missing")
    assert not board_path.exists()
    assert not runtime_path.exists()


@pytest.mark.asyncio
async def test_absent_taskboard_is_not_created(tmp_path: Path) -> None:
    runtime_path = tmp_path / "runtime.db"
    runtime = RuntimeStateStore(runtime_path, include_memory_plane=False)
    await runtime.init_db()
    await MissionControl(TaskBoard(tmp_path / "unused.db"), runtime).create_mission(
        "mission-present",
        title="Read-only absence proof",
    )
    board_path = tmp_path / "absent-board.db"
    projection = MissionControlA2AProjection(
        TaskBoard(board_path),
        runtime,
        inbox_root=tmp_path,
        semantic_job_root=tmp_path,
        responder_state_root=tmp_path,
        outbox_root=tmp_path,
    )
    with pytest.raises(MissionControlError, match="TaskBoard database"):
        await projection.observe("mission-present", "task-missing")
    assert not board_path.exists()
