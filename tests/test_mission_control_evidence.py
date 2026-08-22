from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.mission_control_evidence import (
    EvidenceDelta,
    IndependentAcceptance,
    candidate_output_digest,
)


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def _delta(**overrides: object) -> EvidenceDelta:
    values: dict[str, object] = {
        "mission_id": "mission-alpha",
        "task_id": "task-alpha",
        "run_id": "run-alpha",
        "claim_id": "claim-alpha",
        "agent_id": "agent-alpha",
        "sequence": 1,
        "observed_at": NOW,
        "summary": "Produced a durable candidate artifact.",
        "artifact_ids": ("artifact-alpha",),
    }
    values.update(overrides)
    return EvidenceDelta.new(**values)  # type: ignore[arg-type]


def _acceptance(**overrides: object) -> IndependentAcceptance:
    values: dict[str, object] = {
        "mission_id": "mission-alpha",
        "task_id": "task-alpha",
        "producer_run_id": "producer-run",
        "producer_agent_id": "producer-agent",
        "producer_model_family": "family-producer",
        "producer_output_digest": candidate_output_digest("candidate output"),
        "verifier_run_id": "verifier-run",
        "verifier_agent_id": "verifier-agent",
        "verifier_model_family": "family-verifier",
        "oracle_kind": "model",
        "accepted": True,
        "observed_at": NOW,
        "rationale": "The held requirements are satisfied.",
        "evidence_receipt_ids": ("verifier-receipt",),
    }
    values.update(overrides)
    return IndependentAcceptance.new(**values)


def test_evidence_delta_rejects_empty_duplicate_and_wrong_identity() -> None:
    with pytest.raises(MissionControlError, match="cite durable evidence"):
        _delta(artifact_ids=(), receipt_ids=())

    with pytest.raises(MissionControlError, match="duplicate"):
        _delta(artifact_ids=("artifact-alpha", "artifact-alpha"))

    valid = _delta()
    with pytest.raises(MissionControlError, match="does not bind"):
        replace(valid, run_id="foreign-run")


def test_evidence_delta_requires_fresh_monotonic_sequence() -> None:
    delta = _delta()

    delta.require_fresh(
        now=NOW + timedelta(seconds=30),
        last_sequence=0,
        max_age=timedelta(minutes=1),
    )
    with pytest.raises(MissionControlError, match="duplicate or stale"):
        delta.require_fresh(
            now=NOW,
            last_sequence=1,
            max_age=timedelta(minutes=1),
        )
    with pytest.raises(MissionControlError, match="is stale"):
        delta.require_fresh(
            now=NOW + timedelta(minutes=2),
            last_sequence=0,
            max_age=timedelta(minutes=1),
        )


def test_acceptance_payload_is_digest_bound_and_independent() -> None:
    acceptance = _acceptance()
    payload = acceptance.to_payload()

    assert IndependentAcceptance.from_payload(payload) == acceptance

    tampered = {**payload, "accepted": False}
    with pytest.raises(MissionControlError, match="digest is invalid"):
        IndependentAcceptance.from_payload(tampered)

    with pytest.raises(MissionControlError, match="must be independent"):
        _acceptance(verifier_agent_id="producer-agent")
    with pytest.raises(MissionControlError, match="must be independent"):
        _acceptance(verifier_model_family="family-producer")

    malformed = dict(payload)
    malformed.pop("acceptance_digest")
    malformed["observed_at"] = "not-a-timestamp"
    encoded = json.dumps(
        malformed,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode()
    malformed["acceptance_digest"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    with pytest.raises(MissionControlError, match="payload is malformed"):
        IndependentAcceptance.from_payload(malformed)


def test_deterministic_held_out_oracle_requires_digest() -> None:
    with pytest.raises(MissionControlError, match="oracle_digest"):
        _acceptance(
            oracle_kind="deterministic_held_out",
            verifier_agent_id="producer-agent",
            verifier_model_family="family-producer",
        )

    acceptance = _acceptance(
        oracle_kind="deterministic_held_out",
        verifier_agent_id="producer-agent",
        verifier_model_family="family-producer",
        oracle_digest="sha256:" + "a" * 64,
    )
    assert acceptance.oracle_kind == "deterministic_held_out"
