"""Hermetic contract tests for the Python-owned Helm OnCall evaluator."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.model_status import (
    ACCEPTED_ROUTE_VERIFIER_ID,
    ACCEPTED_ROUTE_VERIFIER_VERSION,
    HELM_ON_CALL_PROJECTION_SCHEMA_VERSION,
    HELM_SLICE1_SEATS,
    MAX_ROUTE_VERIFICATION_TTL,
    ROUTE_VERIFICATION_SCHEMA_VERSION,
    HelmOnCallState,
    RouteEvidence,
    RouteVerdict,
    RouteVerification,
    evaluate_route_verification,
    helm_on_call_projection_from_dict,
    helm_on_call_projection_to_dict,
    project_helm_on_call,
    route_evidence_from_dict,
    route_verification_from_dict,
    route_verification_to_dict,
    unknown_helm_on_call_projection,
)


NOW = datetime(2026, 8, 9, 12, 0, 0, 900000, tzinfo=timezone.utc)
EPOCH = "terminal-bridge:boot-1"


def _evidence(index: int = 0, **changes: object) -> RouteEvidence:
    seat = HELM_SLICE1_SEATS[index]
    provider, model = seat.admissible_served_identities[0]
    row = RouteEvidence(
        seat_id=seat.seat_id,
        logical_lineage=seat.logical_lineage,
        requested_provider=provider,
        requested_model=model,
        served_provider=provider,
        served_model=model,
        success=True,
        synthetic=False,
        observed_at=NOW - timedelta(seconds=61, microseconds=500000),
        expires_at=NOW + timedelta(hours=1),
        verifier_id=ACCEPTED_ROUTE_VERIFIER_ID,
        verifier_version=ACCEPTED_ROUTE_VERIFIER_VERSION,
        verifier_accepted=True,
        receipt_ref=f"receipt://helm/{seat.seat_id}/{index}",
        receipt_sha256=f"{index + 1:064x}",
        runtime_epoch=EPOCH,
    )
    return replace(row, **changes)


def _verify(evidence: RouteEvidence | None = None, *, index: int = 0):
    return evaluate_route_verification(
        seat=HELM_SLICE1_SEATS[index],
        evidence=_evidence(index) if evidence is None else evidence,
        now=NOW,
        current_runtime_epoch=EPOCH,
    )


def test_fixed_seven_seat_order_and_allowlists_are_exact() -> None:
    assert tuple(seat.seat_id for seat in HELM_SLICE1_SEATS) == (
        "fable-5",
        "gpt-5.6",
        "grok-4.5-4.6-lineage",
        "fugu-ultra",
        "kimi-k3",
        "opus-5.0",
        "opus-4.8",
    )
    assert tuple(seat.logical_lineage for seat in HELM_SLICE1_SEATS) == (
        "fable-5",
        "openai-gpt-5.6",
        "xai-grok-4.5-4.6",
        "sakana-fugu-ultra",
        "moonshot-kimi-k3",
        "anthropic-opus-5.0",
        "anthropic-opus-4.8",
    )
    assert HELM_SLICE1_SEATS[2].admissible_served_identities == (
        ("openrouter", "x-ai/grok-4.5"),
        ("openrouter", "x-ai/grok-4.6"),
        ("xai", "grok-4.5"),
        ("xai", "grok-4.6"),
    )
    with pytest.raises(AttributeError):
        HELM_SLICE1_SEATS[0].seat_id = "forged"  # type: ignore[misc]


def test_route_verification_accepts_every_exact_positive_obligation() -> None:
    verification = _verify()

    assert verification.schema_version == ROUTE_VERIFICATION_SCHEMA_VERSION
    assert verification.verdict is RouteVerdict.ON_CALL
    assert verification.reason == "verified"
    assert verification.evidence is not None
    assert verification.evidence.age_seconds == 61


@pytest.mark.parametrize(
    ("changes", "verdict", "reason"),
    [
        ({"seat_id": "gpt-5.6"}, RouteVerdict.REJECTED, "seat_mismatch"),
        ({"logical_lineage": "fable-ish"}, RouteVerdict.REJECTED, "lineage_mismatch"),
        ({"success": False}, RouteVerdict.REJECTED, "provider_completion_failed"),
        ({"synthetic": True}, RouteVerdict.REJECTED, "synthetic_evidence"),
        ({"synthetic": None}, RouteVerdict.REJECTED, "synthetic_evidence"),
        ({"requested_provider": None}, RouteVerdict.REJECTED, "requested_identity_missing"),
        ({"requested_model": ""}, RouteVerdict.REJECTED, "requested_identity_missing"),
        ({"served_provider": None}, RouteVerdict.REJECTED, "served_identity_missing"),
        ({"served_model": ""}, RouteVerdict.REJECTED, "served_identity_missing"),
        ({"served_model": "claude-fable-5-alias"}, RouteVerdict.REJECTED, "served_identity_mismatch"),
        ({"verifier_id": "another.verifier"}, RouteVerdict.REJECTED, "verifier_identity_rejected"),
        ({"verifier_version": "1.0.1"}, RouteVerdict.REJECTED, "verifier_identity_rejected"),
        ({"verifier_accepted": False}, RouteVerdict.REJECTED, "verifier_decision_rejected"),
        ({"receipt_ref": ""}, RouteVerdict.REJECTED, "receipt_reference_missing"),
        ({"receipt_sha256": None}, RouteVerdict.REJECTED, "receipt_hash_invalid"),
        ({"receipt_sha256": "A" * 64}, RouteVerdict.REJECTED, "receipt_hash_invalid"),
    ],
)
def test_route_verification_rejects_each_independent_obligation(
    changes: dict[str, object],
    verdict: RouteVerdict,
    reason: str,
) -> None:
    verification = _verify(replace(_evidence(), **changes))

    assert verification.verdict is verdict
    assert verification.reason == reason


def test_route_verification_rejects_naive_timestamps() -> None:
    verification = _verify(replace(_evidence(), observed_at=NOW.replace(tzinfo=None)))

    assert verification.verdict is RouteVerdict.REJECTED
    assert verification.reason == "timestamp_not_timezone_aware"
    assert route_verification_to_dict(verification)["evidence"]["age_seconds"] is None


def test_route_verification_rejects_future_timestamp_without_clamping_age() -> None:
    verification = _verify(replace(_evidence(), observed_at=NOW + timedelta(microseconds=1)))
    payload = route_verification_to_dict(verification)

    assert verification.verdict is RouteVerdict.CLOCK_SKEW
    assert verification.reason == "timestamp_in_future"
    assert payload["evidence"]["age_seconds"] is None


def test_route_verification_rejects_ttl_over_24_hours() -> None:
    observed_at = NOW - timedelta(hours=1)
    evidence = replace(
        _evidence(),
        observed_at=observed_at,
        expires_at=observed_at + timedelta(hours=24, microseconds=1),
    )

    assert MAX_ROUTE_VERIFICATION_TTL == timedelta(hours=24)
    verification = _verify(evidence)
    assert verification.verdict is RouteVerdict.REJECTED
    assert verification.reason == "ttl_exceeds_24_hours"


def test_route_verification_accepts_exact_24_hour_ttl() -> None:
    observed_at = NOW - timedelta(hours=1)
    verification = _verify(
        replace(_evidence(), observed_at=observed_at, expires_at=observed_at + timedelta(hours=24))
    )

    assert verification.verdict is RouteVerdict.ON_CALL


def test_route_verification_expiry_is_exclusive() -> None:
    verification = _verify(replace(_evidence(), expires_at=NOW))

    assert verification.verdict is RouteVerdict.REJECTED
    assert verification.reason == "evidence_expired"


def test_route_verification_requires_expiry_after_observation() -> None:
    observed_at = NOW - timedelta(minutes=1)
    verification = _verify(replace(_evidence(), observed_at=observed_at, expires_at=observed_at))

    assert verification.reason == "expiry_not_after_observation"


def test_route_verification_rejects_replay_and_batch_duplicate() -> None:
    evidence = _evidence()
    replayed = evaluate_route_verification(
        seat=HELM_SLICE1_SEATS[0],
        evidence=evidence,
        now=NOW,
        current_runtime_epoch=EPOCH,
        replayed_receipts={evidence.receipt_sha256},
    )
    duplicated = evaluate_route_verification(
        seat=HELM_SLICE1_SEATS[0],
        evidence=evidence,
        now=NOW,
        current_runtime_epoch=EPOCH,
        receipt_duplicated=True,
    )

    assert (replayed.verdict, replayed.reason) == (RouteVerdict.REJECTED, "receipt_replayed")
    assert (duplicated.verdict, duplicated.reason) == (
        RouteVerdict.REJECTED,
        "receipt_duplicated",
    )


def test_runtime_epoch_mismatch_resets_truth_to_unknown() -> None:
    verification = _verify(replace(_evidence(), runtime_epoch="terminal-bridge:old-boot"))

    assert verification.verdict is RouteVerdict.UNKNOWN
    assert verification.reason == "runtime_epoch_mismatch"


def test_missing_evidence_is_unknown_not_substituted() -> None:
    verification = evaluate_route_verification(
        seat=HELM_SLICE1_SEATS[4],
        evidence=None,
        now=NOW,
        current_runtime_epoch=EPOCH,
    )

    assert verification.seat_id == "kimi-k3"
    assert verification.verdict is RouteVerdict.UNKNOWN
    assert verification.evidence is None


def test_only_evaluator_can_construct_positive_route_verdict() -> None:
    evaluated = _verify()

    with pytest.raises(ValueError, match="only be constructed"):
        RouteVerification(
            schema_version=evaluated.schema_version,
            seat_id=evaluated.seat_id,
            display_label=evaluated.display_label,
            logical_lineage=evaluated.logical_lineage,
            verdict=RouteVerdict.ON_CALL,
            reason="forged",
            evaluated_at=evaluated.evaluated_at,
            runtime_epoch=evaluated.runtime_epoch,
            evidence=evaluated.evidence,
        )


def test_forged_serialized_positive_verdict_is_rejected() -> None:
    verification_payload = route_verification_to_dict(_verify())
    projection_payload = helm_on_call_projection_to_dict(
        project_helm_on_call(
            [_evidence(index) for index in range(7)],
            now=NOW,
            current_runtime_epoch=EPOCH,
        )
    )

    with pytest.raises(ValueError, match="not evaluation authority"):
        route_verification_from_dict(verification_payload)
    with pytest.raises(ValueError, match="not evaluation authority"):
        helm_on_call_projection_from_dict(projection_payload)


def test_route_evidence_deserializer_is_strict_and_never_accepts_verdict() -> None:
    payload = {
        "seat_id": "fable-5",
        "logical_lineage": "fable-5",
        "requested_provider": "claude_code",
        "requested_model": "claude-fable-5",
        "served_provider": "claude_code",
        "served_model": "claude-fable-5",
        "success": True,
        "synthetic": False,
        "observed_at": "2026-08-09T11:58:59.400000Z",
        "expires_at": "2026-08-09T13:00:00.900000Z",
        "verifier_id": ACCEPTED_ROUTE_VERIFIER_ID,
        "verifier_version": ACCEPTED_ROUTE_VERIFIER_VERSION,
        "verifier_accepted": True,
        "receipt_ref": "receipt://helm/fable-5/0",
        "receipt_sha256": "1".zfill(64),
        "runtime_epoch": EPOCH,
    }
    assert route_evidence_from_dict(payload).observed_at is not None

    with pytest.raises(ValueError, match="exactly"):
        route_evidence_from_dict({**payload, "verdict": "ON_CALL"})
    with pytest.raises(ValueError, match="RFC 3339"):
        route_evidence_from_dict({**payload, "observed_at": "2026-08-09T11:58:59"})


def test_projection_is_on_call_only_at_exactly_seven_of_seven() -> None:
    projection = project_helm_on_call(
        [_evidence(index) for index in range(7)],
        now=NOW,
        current_runtime_epoch=EPOCH,
    )

    assert projection.schema_version == HELM_ON_CALL_PROJECTION_SCHEMA_VERSION
    assert projection.state is HelmOnCallState.ON_CALL
    assert projection.on_call_count == projection.total == 7
    assert all(row.verdict is RouteVerdict.ON_CALL for row in projection.seats)


def test_partial_projection_is_ordered_live_degraded_n_of_seven() -> None:
    projection = project_helm_on_call([_evidence(4)], now=NOW, current_runtime_epoch=EPOCH)

    assert projection.state is HelmOnCallState.LIVE_DEGRADED
    assert projection.on_call_count == 1
    assert tuple(row.seat_id for row in projection.seats) == tuple(
        seat.seat_id for seat in HELM_SLICE1_SEATS
    )
    assert projection.seats[4].verdict is RouteVerdict.ON_CALL
    assert all(
        row.verdict is RouteVerdict.UNKNOWN
        for index, row in enumerate(projection.seats)
        if index != 4
    )


def test_projection_future_evidence_is_clock_skew() -> None:
    projection = project_helm_on_call(
        [replace(_evidence(), observed_at=NOW + timedelta(seconds=1))],
        now=NOW,
        current_runtime_epoch=EPOCH,
    )

    assert projection.state is HelmOnCallState.CLOCK_SKEW
    assert projection.on_call_count == 0
    with pytest.raises(ValueError, match="requires CLOCK_SKEW"):
        replace(projection, state=HelmOnCallState.LIVE_DEGRADED)


def test_projection_epoch_mismatch_is_unknown_question_mark_count() -> None:
    projection = project_helm_on_call(
        [replace(_evidence(), runtime_epoch="terminal-bridge:old-boot")],
        now=NOW,
        current_runtime_epoch=EPOCH,
    )

    assert projection.state is HelmOnCallState.UNKNOWN
    assert projection.on_call_count is None
    assert all(row.verdict is RouteVerdict.UNKNOWN for row in projection.seats)


def test_one_old_epoch_resets_fresh_positive_rows_to_unknown() -> None:
    projection = project_helm_on_call(
        [
            _evidence(0),
            replace(_evidence(1), runtime_epoch="terminal-bridge:old-boot"),
        ],
        now=NOW,
        current_runtime_epoch=EPOCH,
    )

    assert projection.state is HelmOnCallState.UNKNOWN
    assert projection.on_call_count is None
    assert all(row.verdict is RouteVerdict.UNKNOWN for row in projection.seats)
    assert all(row.reason == "runtime_epoch_mismatch" for row in projection.seats)


def test_unknown_connect_projection_is_question_mark_seven() -> None:
    projection = unknown_helm_on_call_projection(now=NOW, current_runtime_epoch=EPOCH)

    assert projection.state is HelmOnCallState.UNKNOWN
    assert projection.on_call_count is None
    assert all(row.reason == "awaiting_authoritative_projection" for row in projection.seats)


def test_duplicate_or_wrong_order_seat_batch_fails_closed_unknown() -> None:
    duplicate = project_helm_on_call(
        [_evidence(0), replace(_evidence(0), receipt_ref="receipt://another")],
        now=NOW,
        current_runtime_epoch=EPOCH,
    )
    wrong_order = project_helm_on_call(
        [_evidence(1), _evidence(0)],
        now=NOW,
        current_runtime_epoch=EPOCH,
    )

    assert duplicate.state is HelmOnCallState.UNKNOWN
    assert wrong_order.state is HelmOnCallState.UNKNOWN
    assert duplicate.on_call_count is wrong_order.on_call_count is None


def test_duplicate_receipt_rejects_each_reuse_without_hiding_other_seats() -> None:
    first = _evidence(0)
    second = replace(
        _evidence(1),
        receipt_ref=first.receipt_ref,
        receipt_sha256=first.receipt_sha256,
    )
    projection = project_helm_on_call([first, second], now=NOW, current_runtime_epoch=EPOCH)

    assert projection.state is HelmOnCallState.LIVE_DEGRADED
    assert projection.on_call_count == 0
    assert [row.reason for row in projection.seats[:2]] == [
        "receipt_duplicated",
        "receipt_duplicated",
    ]


def test_projection_serializer_is_idempotent_and_age_is_python_computed() -> None:
    projection = project_helm_on_call([_evidence()], now=NOW, current_runtime_epoch=EPOCH)

    first = helm_on_call_projection_to_dict(projection)
    second = helm_on_call_projection_to_dict(projection)

    assert first == second
    assert first["seats"][0]["evidence"]["age_seconds"] == 61
    assert first["evaluated_at"] == "2026-08-09T12:00:00.900000Z"


def test_negative_projection_decoder_rejects_wrong_order_and_unknown_fields() -> None:
    payload = helm_on_call_projection_to_dict(
        unknown_helm_on_call_projection(now=NOW, current_runtime_epoch=EPOCH)
    )
    decoded = helm_on_call_projection_from_dict(payload)
    assert decoded.state is HelmOnCallState.UNKNOWN

    reordered = {**payload, "seats": list(reversed(payload["seats"]))}
    with pytest.raises(ValueError, match="complete and ordered"):
        helm_on_call_projection_from_dict(reordered)
    with pytest.raises(ValueError, match="exactly"):
        helm_on_call_projection_from_dict({**payload, "extra": False})
