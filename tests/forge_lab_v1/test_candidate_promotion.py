from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dharma_swarm.forge_lab.candidate_envelope import (
    CandidateEnvelope,
    EvidenceBinding,
    TerminalDisposition,
    TerminalState,
    sign_candidate_envelope,
)
from dharma_swarm.a2a.candidate_lease_receipt import (
    OperatorLeaseGrant,
    SignedLeaseFileVerifier,
    sign_operator_lease_grant,
)
from dharma_swarm.forge_lab.candidate_store import CandidateStore
from dharma_swarm.forge_lab.promotion_controller import (
    CANARY_RESULT_EVIDENCE_SCHEMA,
    ROLLBACK_RESULT_EVIDENCE_SCHEMA,
    CanaryResult,
    IndependentEvaluation,
    LeaseVerification,
    PromotionController,
    PromotionControlError,
    RollbackResult,
    aggregate_independent_evaluations,
    canary_result_evidence_content,
    rollback_result_evidence_content,
    sign_canary_result,
    sign_independent_evaluation,
    sign_rollback_result,
    verify_signed_promotion_decision,
)
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _at(seconds: int = 0) -> str:
    value = datetime(2026, 8, 27, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    return value.isoformat().replace("+00:00", "Z")


def _evidence(name: str, seconds: int = 0) -> EvidenceBinding:
    return EvidenceBinding(
        schema=f"test.{name}.v1",
        receipt_id=f"receipt-{name}",
        sha256=_sha(name),
        issuer=f"issuer-{name}",
        created_at=_at(seconds),
    )


def _canary_evidence(
    envelope_id: str,
    aggregate_id: str,
    *,
    healthy: bool = True,
    rollback_ready: bool = True,
    seconds: int = 20,
) -> EvidenceBinding:
    performed_at = _at(seconds)
    content = canary_result_evidence_content(
        canary_id="shadow-canary-1",
        envelope_id=envelope_id,
        aggregate_id=aggregate_id,
        healthy=healthy,
        rollback_ready=rollback_ready,
        performed_at=performed_at,
    )
    return EvidenceBinding(
        schema=CANARY_RESULT_EVIDENCE_SCHEMA,
        receipt_id="receipt-shadow-canary",
        sha256=canonical_sha256(content),
        issuer="shadow-canary-runner",
        created_at=performed_at,
    )


def _rollback_evidence(
    envelope_id: str,
    reason_code: str,
    *,
    rolled_back: bool = True,
    seconds: int = 21,
) -> EvidenceBinding:
    performed_at = _at(seconds)
    content = rollback_result_evidence_content(
        envelope_id=envelope_id,
        reason_code=reason_code,
        rolled_back=rolled_back,
        performed_at=performed_at,
    )
    return EvidenceBinding(
        schema=ROLLBACK_RESULT_EVIDENCE_SCHEMA,
        receipt_id="receipt-rollback",
        sha256=canonical_sha256(content),
        issuer="rollback-executor",
        created_at=performed_at,
    )


def _public(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


_CANARY_KEY = Ed25519PrivateKey.generate()
_ROLLBACK_KEY = Ed25519PrivateKey.generate()


def _envelope() -> CandidateEnvelope:
    return CandidateEnvelope(
        candidate_id="cand_promotion",
        revision=1,
        predecessor_envelope_id="",
        correlation_id="corr-promotion",
        idempotency_key="idem-promotion",
        source_run_id="rsi-run",
        source_task_id="rsi-task",
        source_sha="1" * 40,
        controller_sha="2" * 40,
        harness_sha="3" * 40,
        evaluator_sha="4" * 40,
        target_sha="5" * 40,
        base_sha="6" * 40,
        patch_sha256=_sha("patch"),
        dependencies_sha256=_sha("deps"),
        toolchain_sha256=_sha("tools"),
        artifact_sha256=_sha("artifact"),
        configuration_sha256=_sha("config"),
        provider_attestation=_evidence("provider"),
        budget_receipt=_evidence("budget"),
        evaluation_receipt=_evidence("source-eval"),
        provenance_receipt=_evidence("provenance"),
        task_identity="swebench::django-12209",
        holdout_identity="holdout::django-12209::v1",
        parent_lineage=("cand_parent",),
        evaluation_outcome="source_pass",
        evaluation_comparable=True,
        authority_id="rsi-source-controller",
        lease_id="rsi-lease-1",
        lease_expires_at=_at(400),
        created_at=_at(),
        expires_at=_at(300),
        attempt=1,
        fence=11,
        terminal_disposition=TerminalDisposition(
            state=TerminalState.SUBMITTED,
            reason_code="submitted_for_foundry",
            receipt_id="submit-1",
            at=_at(),
        ),
    )


def _evaluation(
    envelope: CandidateEnvelope,
    evaluator_id: str,
    key: Ed25519PrivateKey,
    *,
    passed: bool = True,
):
    evaluation = IndependentEvaluation(
        envelope_id=envelope.envelope_id,
        candidate_id=envelope.candidate_id,
        evaluator_id=evaluator_id,
        evaluator_sha=("7" if evaluator_id.endswith("a") else "8") * 40,
        evaluator_executable_sha256=_sha(f"executable-{evaluator_id}"),
        evaluator_release_tree_sha256=_sha(f"release-tree-{evaluator_id}"),
        target_sha=envelope.target_sha,
        outcome="pass" if passed else "fail",
        comparable=True,
        passed=passed,
        score_micros=900_000 if passed else 100_000,
        isolation_receipt=_evidence(f"isolation-{evaluator_id}"),
        evidence_receipt=_evidence(f"evaluation-{evaluator_id}"),
        created_at=_at(10),
    )
    return sign_independent_evaluation(
        evaluation,
        signing_key=key,
        authority_epoch_sha256=_sha(f"epoch-{evaluator_id}"),
    )


class _Canary:
    def __init__(
        self,
        *,
        healthy: bool = True,
        rollback_ready: bool = True,
        signing_key: Ed25519PrivateKey = _CANARY_KEY,
    ) -> None:
        self.healthy = healthy
        self.rollback_ready = rollback_ready
        self.signing_key = signing_key
        self.calls = 0

    async def run(self, envelope, aggregate):
        self.calls += 1
        assert aggregate.passed
        return sign_canary_result(
            canary_id="shadow-canary-1",
            envelope_id=envelope.envelope_id,
            aggregate_id=aggregate.aggregate_id,
            healthy=self.healthy,
            rollback_ready=self.rollback_ready,
            receipt=_canary_evidence(
                envelope.envelope_id,
                aggregate.aggregate_id,
                healthy=self.healthy,
                rollback_ready=self.rollback_ready,
            ),
            signing_key=self.signing_key,
            authority_epoch_sha256=_sha("canary-epoch"),
        )


class _Rollback:
    def __init__(self, *, signing_key: Ed25519PrivateKey = _ROLLBACK_KEY) -> None:
        self.calls = 0
        self.signing_key = signing_key

    async def rollback(self, envelope, *, reason_code):
        self.calls += 1
        return sign_rollback_result(
            envelope_id=envelope.envelope_id,
            reason_code=reason_code,
            rolled_back=True,
            receipt=_rollback_evidence(envelope.envelope_id, reason_code),
            signing_key=self.signing_key,
            authority_epoch_sha256=_sha("rollback-epoch"),
        )


class _LeaseVerifier:
    def __init__(self, allowed: bool = True, **overrides) -> None:
        self.allowed = allowed
        self.overrides = overrides
        self.calls = 0

    async def verify(self, **request):
        self.calls += 1
        payload = {
            "allowed": self.allowed,
            "reason_code": "verified" if self.allowed else "scope_mismatch",
            "authority_id": request["authority_id"],
            "lease_id": request["lease_id"],
            "candidate_id": request["candidate_id"],
            "envelope_id": request["envelope_id"],
            "fence": request["fence"],
            "expires_at": request["lease_expires_at"],
            "required_scope": request["required_scope"],
            "verified_at": request["now"],
            "verifier_receipt_sha256": _sha("lease-verification") if self.allowed else "",
        }
        payload.update(self.overrides)
        return LeaseVerification(**payload)


def _fixture():
    envelope = _envelope()
    source_key = Ed25519PrivateKey.generate()
    evaluator_a = Ed25519PrivateKey.generate()
    evaluator_b = Ed25519PrivateKey.generate()
    signed = sign_candidate_envelope(
        envelope,
        signing_key=source_key,
        authority_epoch_sha256=_sha("source-epoch"),
    )
    evaluations = [
        _evaluation(envelope, "foundry-evaluator-a", evaluator_a),
        _evaluation(envelope, "independent-evaluator-b", evaluator_b),
    ]
    return envelope, signed, evaluations, source_key, evaluator_a, evaluator_b


def test_aggregate_requires_distinct_trusted_evaluator_and_signer_lanes() -> None:
    envelope, _, evaluations, _, evaluator_a, evaluator_b = _fixture()
    aggregate = aggregate_independent_evaluations(
        evaluations,
        envelope=envelope,
        trusted_public_keys=[_public(evaluator_a), _public(evaluator_b)],
    )
    assert aggregate.passed is True
    assert aggregate.conservative_score_micros == 900_000
    with pytest.raises(FrozenInstanceError):
        aggregate.passed = False  # type: ignore[misc]
    with pytest.raises(TypeError):
        evaluations[0].signature_receipt["name"] = "tampered"  # type: ignore[index]

    duplicate_key = _evaluation(envelope, "third-evaluator", evaluator_a)
    refused = aggregate_independent_evaluations(
        [evaluations[0], duplicate_key],
        envelope=envelope,
        trusted_public_keys=[_public(evaluator_a)],
    )
    assert refused.passed is False
    assert any(blocker.startswith("duplicate_evaluator_lane") for blocker in refused.blockers)


def test_evaluation_schema_score_time_and_source_signer_are_fail_closed() -> None:
    envelope, _, evaluations, source_key, evaluator_a, evaluator_b = _fixture()
    with pytest.raises(PromotionControlError, match="schema"):
        replace(evaluations[0].evaluation, schema="forge_lab.independent_evaluation.v1")
    with pytest.raises(PromotionControlError, match="integer"):
        replace(evaluations[0].evaluation, score_micros=True)
    source_lane = _evaluation(envelope, "cryptographic-source-reuse", source_key)
    source_refused = aggregate_independent_evaluations(
        [source_lane, evaluations[1]],
        envelope=envelope,
        trusted_public_keys=[_public(source_key), _public(evaluator_b)],
        excluded_signer_public_keys=[_public(source_key)],
    )
    assert source_refused.passed is False
    assert any("signer_not_independent" in blocker for blocker in source_refused.blockers)

    future = replace(evaluations[0].evaluation, created_at=_at(301))
    future_signed = sign_independent_evaluation(
        future, signing_key=evaluator_a, authority_epoch_sha256=_sha("future-epoch")
    )
    time_refused = aggregate_independent_evaluations(
        [future_signed, evaluations[1]],
        envelope=envelope,
        trusted_public_keys=[_public(evaluator_a), _public(evaluator_b)],
    )
    assert any("evaluation_time_mismatch" in blocker for blocker in time_refused.blockers)


def test_canary_and_rollback_results_require_boolean_evidence_contracts() -> None:
    with pytest.raises(PromotionControlError, match="boolean"):
        CanaryResult("canary", "a" * 64, "b" * 64, 1, True, _evidence("canary"), {})  # type: ignore[arg-type]
    with pytest.raises(PromotionControlError, match="boolean"):
        RollbackResult("a" * 64, "forced", 1, _evidence("rollback"), {})  # type: ignore[arg-type]


def test_canary_and_rollback_receipts_bind_every_result_field() -> None:
    canary = sign_canary_result(
        canary_id="shadow-canary-1", envelope_id="a" * 64, aggregate_id="b" * 64,
        healthy=True, rollback_ready=True,
        receipt=_canary_evidence("a" * 64, "b" * 64),
        signing_key=_CANARY_KEY, authority_epoch_sha256=_sha("canary-epoch"),
    )
    with pytest.raises(PromotionControlError, match="exact result content"):
        replace(canary, healthy=False)
    with pytest.raises(PromotionControlError, match="exact result content"):
        replace(canary, aggregate_id="c" * 64)
    with pytest.raises(PromotionControlError, match="schema"):
        replace(canary, receipt=_evidence("unrelated-canary", 20))

    rollback = sign_rollback_result(
        envelope_id="a" * 64, reason_code="forced_rollback", rolled_back=True,
        receipt=_rollback_evidence("a" * 64, "forced_rollback"),
        signing_key=_ROLLBACK_KEY, authority_epoch_sha256=_sha("rollback-epoch"),
    )
    with pytest.raises(PromotionControlError, match="exact result content"):
        replace(rollback, rolled_back=False)
    with pytest.raises(PromotionControlError, match="exact result content"):
        replace(rollback, reason_code="unrelated_reason")
    with pytest.raises(PromotionControlError, match="schema"):
        replace(rollback, receipt=_evidence("unrelated-rollback", 21))
    missing_body = dict(canary.signature_receipt)
    missing_body.pop("payload")
    with pytest.raises(PromotionControlError, match="exact result body"):
        replace(canary, signature_receipt=missing_body)


def test_real_signed_file_lease_verifier_binds_every_request_field(tmp_path) -> None:
    envelope = _envelope()
    operator_key = Ed25519PrivateKey.generate()
    signed_grant = sign_operator_lease_grant(
        OperatorLeaseGrant(
            authority_id=envelope.authority_id,
            lease_id=envelope.lease_id,
            candidate_id=envelope.candidate_id,
            envelope_id=envelope.envelope_id,
            fence=envelope.fence,
            scopes=("foundry_rsi.candidate_delivery", "foundry_rsi.live_promotion"),
            issued_at=_at(),
            expires_at=envelope.lease_expires_at,
        ),
        signing_key=operator_key,
        authority_epoch_sha256=_sha("operator-lease-epoch"),
    )
    path = tmp_path / "operator-lease.json"
    path.write_text(json.dumps(signed_grant.to_dict(), sort_keys=True), encoding="utf-8")
    path.chmod(0o644)
    verifier = SignedLeaseFileVerifier(path, trusted_public_keys=[_public(operator_key)])
    request = dict(
        authority_id=envelope.authority_id,
        lease_id=envelope.lease_id,
        candidate_id=envelope.candidate_id,
        envelope_id=envelope.envelope_id,
        fence=envelope.fence,
        lease_expires_at=envelope.lease_expires_at,
        required_scope="foundry_rsi.candidate_delivery",
        now=_at(30),
    )

    assert verifier.verify(**request).allowed is True
    assert verifier.verify(**{**request, "candidate_id": "confused-candidate"}).allowed is False
    assert verifier.verify(**{**request, "required_scope": "ungranted.scope"}).allowed is False


@pytest.mark.asyncio
async def test_shadow_canary_is_signed_but_never_live_and_is_durable(tmp_path) -> None:
    envelope, signed, evaluations, source_key, evaluator_a, evaluator_b = _fixture()
    decision_key = Ed25519PrivateKey.generate()
    store = CandidateStore(tmp_path / "terminal.jsonl", experiment_id="integration")
    await store.load()
    canary, rollback = _Canary(), _Rollback()
    controller = PromotionController(
        trusted_source_public_keys=[_public(source_key)],
        trusted_evaluator_public_keys=[_public(evaluator_a), _public(evaluator_b)],
        trusted_canary_public_keys=[_public(_CANARY_KEY)],
        trusted_rollback_public_keys=[_public(_ROLLBACK_KEY)],
        decision_signing_key=decision_key,
        decision_authority_epoch_sha256=_sha("decision-epoch"),
        canary_runner=canary,
        rollback_executor=rollback,
        terminal_store=store,
    )

    run = await controller.run(signed, evaluations, now=_at(30))

    assert run.decision["outcome"] == "shadow_canary_passed"
    assert run.decision["evidence_binding_only"] is False
    assert run.decision["typed_canary_result_signature_verified"] is True
    assert run.decision["independent_evidence_bodies_verified_by_controller"] is False
    assert run.live_apply_allowed is False
    assert run.terminal_envelope.terminal_disposition.state is TerminalState.CANARY_PASSED
    assert verify_signed_promotion_decision(run, trusted_public_keys=[_public(decision_key)])
    assert await store.latest_terminal(
        candidate_id=envelope.candidate_id,
        envelope_id=run.terminal_envelope.envelope_id,
    ) is not None


@pytest.mark.asyncio
async def test_untrusted_canary_and_rollback_signers_are_fail_closed() -> None:
    _, signed, evaluations, source_key, evaluator_a, evaluator_b = _fixture()
    common = dict(
        trusted_source_public_keys=[_public(source_key)],
        trusted_evaluator_public_keys=[_public(evaluator_a), _public(evaluator_b)],
        trusted_canary_public_keys=[_public(_CANARY_KEY)],
        trusted_rollback_public_keys=[_public(_ROLLBACK_KEY)],
        decision_signing_key=Ed25519PrivateKey.generate(),
        decision_authority_epoch_sha256=_sha("decision-epoch"),
    )
    untrusted_canary = PromotionController(
        **common,
        canary_runner=_Canary(signing_key=Ed25519PrivateKey.generate()),
        rollback_executor=_Rollback(),
    )
    refused = await untrusted_canary.run(signed, evaluations, now=_at(30))
    assert "canary_result_invalid" in refused.decision["blockers"]

    untrusted_rollback = PromotionController(
        **common,
        canary_runner=_Canary(),
        rollback_executor=_Rollback(signing_key=Ed25519PrivateKey.generate()),
    )
    refused = await untrusted_rollback.run(
        signed, evaluations, now=_at(30), force_rollback=True
    )
    assert "rollback_result_invalid" in refused.decision["blockers"]


@pytest.mark.asyncio
async def test_live_request_stays_disabled_even_if_a_lease_verifier_would_allow() -> None:
    _, signed, evaluations, source_key, evaluator_a, evaluator_b = _fixture()
    lease = _LeaseVerifier(allowed=True)
    controller = PromotionController(
        trusted_source_public_keys=[_public(source_key)],
        trusted_evaluator_public_keys=[_public(evaluator_a), _public(evaluator_b)],
        trusted_canary_public_keys=[_public(_CANARY_KEY)],
        trusted_rollback_public_keys=[_public(_ROLLBACK_KEY)],
        decision_signing_key=Ed25519PrivateKey.generate(),
        decision_authority_epoch_sha256=_sha("decision-epoch"),
        canary_runner=_Canary(),
        rollback_executor=_Rollback(),
        lease_verifier=lease,
        live_enabled=False,
    )

    run = await controller.run(signed, evaluations, now=_at(30), requested_live=True)

    assert run.live_apply_allowed is False
    assert "live_promotion_disabled" in run.decision["blockers"]
    assert lease.calls == 0


@pytest.mark.asyncio
async def test_valid_bound_operator_lease_is_consumed_once_when_live_fixture_enabled(tmp_path) -> None:
    _, signed, evaluations, source_key, evaluator_a, evaluator_b = _fixture()
    decision_key = Ed25519PrivateKey.generate()
    lease = _LeaseVerifier(allowed=True)
    store = CandidateStore(tmp_path / "live-terminal.jsonl", experiment_id="live-fixture")
    await store.load()
    controller = PromotionController(
        trusted_source_public_keys=[_public(source_key)],
        trusted_evaluator_public_keys=[_public(evaluator_a), _public(evaluator_b)],
        trusted_canary_public_keys=[_public(_CANARY_KEY)],
        trusted_rollback_public_keys=[_public(_ROLLBACK_KEY)],
        decision_signing_key=decision_key,
        decision_authority_epoch_sha256=_sha("decision-epoch"),
        canary_runner=_Canary(),
        rollback_executor=_Rollback(),
        lease_verifier=lease,
        live_enabled=True,
        terminal_store=store,
    )

    run = await controller.run(signed, evaluations, now=_at(30), requested_live=True)

    assert run.live_apply_allowed is True
    assert run.decision["outcome"] == "live_authorized"
    assert lease.calls == 1
    assert verify_signed_promotion_decision(run, trusted_public_keys=[_public(decision_key)])
    replay = await controller.run(signed, evaluations, now=_at(31), requested_live=True)
    assert replay.live_apply_allowed is False
    assert "operator_lease_already_consumed" in replay.decision["blockers"]


@pytest.mark.asyncio
async def test_live_lease_atomic_token_has_exactly_one_concurrent_winner(tmp_path) -> None:
    archive = tmp_path / "atomic-live.jsonl"
    first = CandidateStore(archive, experiment_id="atomic-live")
    second = CandidateStore(archive, experiment_id="atomic-live")
    await first.load()
    await second.load()
    envelope = _envelope()
    request = dict(
        authority_id=envelope.authority_id,
        lease_id=envelope.lease_id,
        candidate_id=envelope.candidate_id,
        envelope_id=envelope.envelope_id,
        fence=envelope.fence,
        required_scope="foundry_rsi.live_promotion",
        expires_at=envelope.lease_expires_at,
        verifier_receipt_sha256=_sha("atomic-lease-receipt"),
        consumed_at=_at(30),
    )
    import asyncio

    results = await asyncio.gather(
        first.consume_live_lease_once(**request),
        second.consume_live_lease_once(**request),
    )
    assert sorted(results) == [False, True]
    tokens = list((archive.with_name(archive.name + ".live-leases")).glob("*.json"))
    assert len(tokens) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    (
        {"authority_id": "other-authority"},
        {"lease_id": "other-lease"},
        {"candidate_id": "other-candidate"},
        {"envelope_id": "f" * 64},
        {"fence": 999},
        {"expires_at": _at(20)},
        {"required_scope": "other.scope"},
        {"verified_at": _at(29)},
        {"verifier_receipt_sha256": "abcd"},
    ),
)
async def test_live_gate_rejects_every_confused_lease_binding(overrides) -> None:
    _, signed, evaluations, source_key, evaluator_a, evaluator_b = _fixture()
    controller = PromotionController(
        trusted_source_public_keys=[_public(source_key)],
        trusted_evaluator_public_keys=[_public(evaluator_a), _public(evaluator_b)],
        trusted_canary_public_keys=[_public(_CANARY_KEY)],
        trusted_rollback_public_keys=[_public(_ROLLBACK_KEY)],
        decision_signing_key=Ed25519PrivateKey.generate(),
        decision_authority_epoch_sha256=_sha("decision-epoch"),
        canary_runner=_Canary(),
        rollback_executor=_Rollback(),
        lease_verifier=_LeaseVerifier(**overrides),
        live_enabled=True,
    )

    run = await controller.run(signed, evaluations, now=_at(30), requested_live=True)

    assert run.live_apply_allowed is False
    expected = (
        "operator_lease_verification_error"
        if overrides.get("verifier_receipt_sha256") == "abcd"
        else "operator_lease_binding_invalid"
    )
    assert expected in run.decision["blockers"]


@pytest.mark.asyncio
async def test_expired_lease_or_envelope_cannot_reach_live_gate() -> None:
    _, signed, evaluations, source_key, evaluator_a, evaluator_b = _fixture()
    verifier = _LeaseVerifier()
    controller = PromotionController(
        trusted_source_public_keys=[_public(source_key)],
        trusted_evaluator_public_keys=[_public(evaluator_a), _public(evaluator_b)],
        trusted_canary_public_keys=[_public(_CANARY_KEY)],
        trusted_rollback_public_keys=[_public(_ROLLBACK_KEY)],
        decision_signing_key=Ed25519PrivateKey.generate(),
        decision_authority_epoch_sha256=_sha("decision-epoch"),
        canary_runner=_Canary(),
        rollback_executor=_Rollback(),
        lease_verifier=verifier,
        live_enabled=True,
    )

    run = await controller.run(signed, evaluations, now=_at(400), requested_live=True)

    assert run.live_apply_allowed is False
    assert "candidate_envelope_expired" in run.decision["blockers"]
    assert verifier.calls == 0


@pytest.mark.asyncio
async def test_forced_rollback_executes_and_is_signed() -> None:
    _, signed, evaluations, source_key, evaluator_a, evaluator_b = _fixture()
    rollback = _Rollback()
    controller = PromotionController(
        trusted_source_public_keys=[_public(source_key)],
        trusted_evaluator_public_keys=[_public(evaluator_a), _public(evaluator_b)],
        trusted_canary_public_keys=[_public(_CANARY_KEY)],
        trusted_rollback_public_keys=[_public(_ROLLBACK_KEY)],
        decision_signing_key=Ed25519PrivateKey.generate(),
        decision_authority_epoch_sha256=_sha("decision-epoch"),
        canary_runner=_Canary(),
        rollback_executor=rollback,
    )

    run = await controller.run(signed, evaluations, now=_at(30), force_rollback=True)

    assert run.decision["outcome"] == "rolled_back"
    assert run.live_apply_allowed is False
    assert rollback.calls == 1
    assert run.terminal_envelope.terminal_disposition.state is TerminalState.ROLLED_BACK


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state", (TerminalState.REFUSED, TerminalState.PROMOTED, TerminalState.CANARY_PASSED)
)
async def test_promotion_refuses_already_terminal_candidate_revisions(state) -> None:
    envelope, _, evaluations, source_key, evaluator_a, evaluator_b = _fixture()
    derived = envelope.derive_terminal(
        TerminalDisposition(state, "already_terminal", "terminal-receipt", _at(20))
    )
    signed = sign_candidate_envelope(
        derived, signing_key=source_key, authority_epoch_sha256=_sha("source-epoch")
    )
    canary = _Canary()
    controller = PromotionController(
        trusted_source_public_keys=[_public(source_key)],
        trusted_evaluator_public_keys=[_public(evaluator_a), _public(evaluator_b)],
        trusted_canary_public_keys=[_public(_CANARY_KEY)],
        trusted_rollback_public_keys=[_public(_ROLLBACK_KEY)],
        decision_signing_key=Ed25519PrivateKey.generate(),
        decision_authority_epoch_sha256=_sha("decision-epoch"),
        canary_runner=canary,
        rollback_executor=_Rollback(),
    )
    with pytest.raises(PromotionControlError, match="genesis submitted"):
        await controller.run(signed, evaluations, now=_at(30))
    assert canary.calls == 0
