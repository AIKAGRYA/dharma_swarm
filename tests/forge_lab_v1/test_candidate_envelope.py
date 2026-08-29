from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dharma_swarm.forge_lab.candidate_envelope import (
    CandidateEnvelope,
    CandidateEnvelopeError,
    EvidenceBinding,
    SignedCandidateEnvelope,
    TerminalDisposition,
    TerminalState,
    sign_candidate_envelope,
)
from dharma_swarm.forge_lab.candidate_store import CandidateStore, CandidateStoreError
from dharma_swarm.forge_lab.freeform_explore import (
    MEMBRANE_REQUIREMENTS,
    FreeformExploreEnvelope,
)


def _sha(label: str) -> str:
    import hashlib

    return hashlib.sha256(label.encode()).hexdigest()


def _now(offset: int = 0) -> str:
    value = datetime(2026, 8, 27, tzinfo=timezone.utc) + timedelta(seconds=offset)
    return value.isoformat().replace("+00:00", "Z")


def _evidence(name: str) -> EvidenceBinding:
    return EvidenceBinding(
        schema=f"test.{name}.v1",
        receipt_id=f"receipt-{name}",
        sha256=_sha(name),
        issuer=f"issuer-{name}",
        created_at=_now(),
    )


def candidate_envelope() -> CandidateEnvelope:
    return CandidateEnvelope(
        candidate_id="cand_0123456789abcdef",
        revision=1,
        predecessor_envelope_id="",
        correlation_id="corr-1",
        idempotency_key="idem-1",
        source_run_id="run-1",
        source_task_id="task-1",
        source_sha="1" * 40,
        controller_sha="2" * 40,
        harness_sha="3" * 40,
        evaluator_sha="4" * 40,
        target_sha="5" * 40,
        base_sha="6" * 40,
        patch_sha256=_sha("patch"),
        dependencies_sha256=_sha("dependencies"),
        toolchain_sha256=_sha("toolchain"),
        artifact_sha256=_sha("artifact"),
        configuration_sha256=_sha("configuration"),
        provider_attestation=_evidence("provider"),
        budget_receipt=_evidence("budget"),
        evaluation_receipt=_evidence("evaluation"),
        provenance_receipt=_evidence("provenance"),
        task_identity="swebench::django-12209",
        holdout_identity="holdout::django-12209::v1",
        parent_lineage=("cand_parent",),
        evaluation_outcome="executed_pass",
        evaluation_comparable=True,
        authority_id="rsi-controller",
        lease_id="lease-rsi-1",
        lease_expires_at=_now(400),
        created_at=_now(),
        expires_at=_now(300),
        attempt=1,
        fence=7,
        terminal_disposition=TerminalDisposition(
            state=TerminalState.SUBMITTED,
            reason_code="awaiting_foundry_evaluation",
            receipt_id="submit-receipt-1",
            at=_now(),
        ),
    )


def _public_key_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


def test_content_address_signature_and_round_trip_are_strict() -> None:
    envelope = candidate_envelope()
    key = Ed25519PrivateKey.generate()
    signed = sign_candidate_envelope(
        envelope,
        signing_key=key,
        authority_epoch_sha256=_sha("rsi-authority-epoch"),
        key_id="rsi-source-v1",
    )

    restored = SignedCandidateEnvelope.from_dict(signed.to_dict())

    assert restored.envelope.envelope_id == envelope.envelope_id
    assert restored.verify(trusted_public_keys=[_public_key_hex(key)]) is True
    assert restored.verify(trusted_public_keys=["00" * 32]) is False


def test_address_rejects_any_bound_field_rewrite() -> None:
    payload = candidate_envelope().to_dict()
    tampered = copy.deepcopy(payload)
    tampered["digests"]["patch"] = _sha("different-patch")

    with pytest.raises(CandidateEnvelopeError, match="content hash mismatch"):
        CandidateEnvelope.from_dict(tampered)


def test_envelope_signature_and_lineage_cannot_be_mutated_by_alias() -> None:
    envelope = candidate_envelope()
    key = Ed25519PrivateKey.generate()
    signed = sign_candidate_envelope(
        envelope,
        signing_key=key,
        authority_epoch_sha256=_sha("epoch"),
    )

    with pytest.raises(FrozenInstanceError):
        envelope.fence = 8  # type: ignore[misc]
    with pytest.raises(TypeError):
        signed.signature_receipt["name"] = "renamed"  # type: ignore[index]
    assert envelope.parent_lineage == ("cand_parent",)


def test_terminal_transition_is_a_new_addressed_revision() -> None:
    submitted = candidate_envelope()
    evaluated = submitted.derive_terminal(
        TerminalDisposition(
            state=TerminalState.EVALUATED,
            reason_code="foundry_comparable_pass",
            receipt_id="foundry-eval-1",
            at=_now(20),
        ),
        evaluation_receipt=_evidence("foundry-evaluation"),
        evaluation_outcome="foundry_pass",
        evaluator_sha="7" * 40,
    )

    assert submitted.terminal_disposition.state is TerminalState.SUBMITTED
    assert evaluated.revision == 2
    assert evaluated.predecessor_envelope_id == submitted.envelope_id
    assert evaluated.envelope_id != submitted.envelope_id
    assert evaluated.terminal_disposition.state is TerminalState.EVALUATED


def test_expiry_and_lease_are_fail_closed_at_schema_boundary() -> None:
    payload = candidate_envelope().to_dict()
    payload["expires_at"] = payload["created_at"]
    payload.pop("envelope_id")

    with pytest.raises(CandidateEnvelopeError, match="expires_at must be later"):
        CandidateEnvelope.from_dict({**payload, "envelope_id": _sha("irrelevant")})

    assert candidate_envelope().is_expired(now=_now(300)) is True


def test_lifecycle_revision_and_temporal_invariants_refuse_forged_states() -> None:
    genesis = candidate_envelope()
    final = TerminalDisposition(
        state=TerminalState.PROMOTED,
        reason_code="forged_genesis_promotion",
        receipt_id="forged",
        at=_now(1),
    )
    with pytest.raises(CandidateEnvelopeError, match="revision 1 must have submitted"):
        replace(genesis, terminal_disposition=final)
    with pytest.raises(CandidateEnvelopeError, match="derived revisions require a final"):
        replace(
            genesis,
            revision=2,
            predecessor_envelope_id=genesis.envelope_id,
        )
    with pytest.raises(CandidateEnvelopeError, match="within envelope lifetime"):
        replace(
            genesis,
            revision=2,
            predecessor_envelope_id=genesis.envelope_id,
            terminal_disposition=replace(final, at=_now(301)),
        )
    with pytest.raises(CandidateEnvelopeError, match="cannot outlive.*lease"):
        replace(genesis, lease_expires_at=_now(200))
    with pytest.raises(CandidateEnvelopeError, match="24-hour bound"):
        replace(
            genesis,
            expires_at=_now(24 * 60 * 60 + 1),
            lease_expires_at=_now(24 * 60 * 60 + 1),
        )
    with pytest.raises(CandidateEnvelopeError, match="revision must be a positive integer"):
        replace(genesis, revision=1.0)  # type: ignore[arg-type]
    for field in (
        "provider_attestation", "budget_receipt", "evaluation_receipt", "provenance_receipt",
    ):
        with pytest.raises(CandidateEnvelopeError, match=f"{field} cannot postdate"):
            replace(genesis, **{field: replace(getattr(genesis, field), created_at=_now(1))})


@pytest.mark.asyncio
async def test_candidate_store_export_is_deterministic_and_detached(tmp_path) -> None:
    store = CandidateStore(tmp_path / "archive.jsonl", experiment_id="exp-integration")
    await store.load()
    source = FreeformExploreEnvelope(
        candidate_id="cand_export",
        parent_id=None,
        experiment_id="exp-integration",
        category="agent_evolution",
        artifacts={"patch_sha256": _sha("patch")},
        membrane={name: True for name in MEMBRANE_REQUIREMENTS},
    )
    await store.append_graded(
        candidate_id="cand_export",
        genome={"arm_kind": "freeform_single", "instruction": "bounded"},
        parent_id=None,
        generation=1,
        loop_iteration=2,
        role="candidate",
        pass_rate=1.0,
        per_task=[{"task_id": "django-12209", "resolved": True}],
        budget={"spent_tokens": 10, "spent_usd": 0.01},
        tier="confirm-swebench-docker",
        executed_fields=("arm_kind", "instruction"),
        ignored_fields=(),
        envelope=source,
    )

    first = await store.export_candidate("cand_export")
    first["genome"]["instruction"] = "tampered-copy"
    second = await store.export_candidate("cand_export")

    assert second["genome"]["instruction"] == "bounded"
    assert first["record_sha256"] == second["record_sha256"]


@pytest.mark.asyncio
async def test_terminal_store_is_idempotent_durable_and_conflict_refusing(tmp_path) -> None:
    archive_path = tmp_path / "archive.jsonl"
    store = CandidateStore(archive_path, experiment_id="exp-terminal")
    await store.load()
    disposition = TerminalDisposition(
        state=TerminalState.EVALUATED,
        reason_code="foundry_evaluation_complete",
        receipt_id="eval-receipt",
        at=_now(30),
    )
    envelope_id = candidate_envelope().envelope_id

    first = await store.append_terminal_disposition(
        candidate_id="cand_external",
        envelope_id=envelope_id,
        disposition=disposition,
        attempt=1,
        fence=9,
        allow_external_candidate=True,
    )
    duplicate = await store.append_terminal_disposition(
        candidate_id="cand_external",
        envelope_id=envelope_id,
        disposition=disposition,
        attempt=1,
        fence=9,
        allow_external_candidate=True,
    )
    assert duplicate.id == first.id

    reloaded = CandidateStore(archive_path, experiment_id="exp-terminal")
    await reloaded.load()
    latest = await reloaded.latest_terminal(
        candidate_id="cand_external",
        envelope_id=envelope_id,
    )
    assert latest["terminal"]["disposition"]["state"] == "evaluated"

    with pytest.raises(CandidateStoreError, match="different terminal"):
        await reloaded.append_terminal_disposition(
            candidate_id="cand_external",
            envelope_id=envelope_id,
            disposition=TerminalDisposition(
                state=TerminalState.REFUSED,
                reason_code="conflicting_rewrite",
                receipt_id="other-receipt",
                at=_now(31),
            ),
            attempt=1,
            fence=9,
            allow_external_candidate=True,
        )
