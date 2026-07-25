"""U1 one-door tests: verify_promotion is the sole live-apply arbiter.

Extracted from feat/rsi-lab's tests/test_forge_workstream_b.py, restricted to
the modules U1 lands (promote, verify_promotion, signals). The full
workstream-B suite rides with U2/U3 (it imports arms/forge_fitness/anchors/
darwin_bridge/sequential, which are not on main yet).
"""

from __future__ import annotations

import hashlib

from dharma_swarm.forge_v1.forge_v2 import promote
from dharma_swarm.forge_v1.forge_v2.verify_promotion import (
    sign_receipt,
    verify_promotion,
)


def _passing_packet_guard_review() -> dict:
    return {
        "deterministic_review": {
            "verdict": "pass_for_next_scale",
            "findings": [],
            "task_count": 500,
            "taskbed_power": {
                "split": "confirm",
                "task_count": 500,
                "full_confirm": True,
                "no_split_confirm": True,
                "clean_confirm": True,
                "ci_half_width": 0.04,
                "pre_registered_mde": 0.056,
            },
        }
    }


def _passing_e4_discrimination_receipt() -> dict:
    return {
        "schema": "forge_v2.e4_discrimination_receipt.v1",
        "decision": "pass",
        "promotion_gate_satisfied": True,
        "good_id": "candidate",
        "bad_id": "known_bad_scaffold",
        "min_confirm_n": 500,
        "min_effect": 0.05,
        "pre_registered_mde": 0.056,
        "good": {"n": 500, "mean": 0.10, "lower": 0.08, "upper": 0.12, "ci_half_width": 0.02},
        "bad": {"n": 500, "mean": 0.02, "lower": 0.0, "upper": 0.03, "ci_half_width": 0.015},
        "delta_mean": 0.08,
        "ci_gap": 0.05,
        "blockers": [],
    }


def _receipt_ready_signal() -> dict:
    return {
        "run_id": "receipt-ready",
        "signal_key": "receipt:key",
        "arm": "verify_chain",
        "taskbed": "fresh_taskbed",
        "mission_class": "verifier_role",
        "overall_ci": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
        "explore_ci": {"n": 0, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
        "confirm_ci": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
        "fdr_positive_significant": True,
        "contamination_state": "fresh_heldout",
        "sealed_provenance": {"contamination_state": "fresh_heldout"},
        "class_null": "self_moa",
        "null_survived": False,
        "evidence_strength": 0.9,
        "packet_guard_review": _passing_packet_guard_review(),
        "e4_discrimination_receipt": _passing_e4_discrimination_receipt(),
        "promotion_blockers": [],
    }


def _fake_signed_receipts(public_key: str) -> list[dict]:
    return [
        {
            "name": name,
            "payload": {"receipt": name, "status": "pass"},
            "signature": {
                "scheme": "ed25519",
                "public_key": public_key,
                "signature": "02" * 64,
            },
        }
        for name in promote.REQUIRED_RECEIPTS_V0_ABSENT
    ]


def _verified_lease(_lease: dict) -> bool:
    """Simulates real lease infrastructure (PR-001's loader returns None today).
    Default behavior without this injection: operator_lease_unverified blocker."""
    return True


class _FakeEd25519Key:
    public_hex = "ab" * 32

    def public_key_hex(self) -> str:
        return self.public_hex

    def sign(self, message: bytes) -> bytes:
        return hashlib.sha512(bytes.fromhex(self.public_hex) + message).digest()[:64]


def _fake_verify_ed25519_signature(public_key: bytes, signature: bytes, message: bytes) -> None:
    expected = hashlib.sha512(public_key + message).digest()[:64]
    if signature != expected:
        raise ValueError("bad signature")


def _backend_signed_receipts(signing_key, *, epoch_ruler_sha256: str = "ruler-epoch-sha") -> list[dict]:
    return [
        sign_receipt(
            name=name,
            payload={"receipt": name, "status": "pass", "epoch_ruler_sha256": epoch_ruler_sha256},
            signing_key=signing_key,
            epoch_ruler_sha256=epoch_ruler_sha256,
            key_id="test-judge",
        )
        for name in promote.REQUIRED_RECEIPTS_V0_ABSENT
    ]


def test_verify_promotion_empty_signal_fails_closed() -> None:
    verdict = verify_promotion({})

    assert verdict["decision"] == "refused"
    assert verdict["live_apply_allowed"] is False


def test_verify_promotion_ready_signal_without_receipts_refuses() -> None:
    verdict = verify_promotion(_receipt_ready_signal(), operator_lease={"lease_id": "op-1"})

    assert verdict["decision"] == "refused"
    assert verdict["live_apply_allowed"] is False


def test_verify_promotion_rejects_self_signed_receipts_without_trusted_key(monkeypatch) -> None:
    from dharma_swarm.forge_v1.forge_v2 import verify_promotion as verifier

    monkeypatch.setattr(verifier, "verify_signed_receipt", lambda _receipt: True)
    public_key = "01" * 32

    verdict = verify_promotion(
        _receipt_ready_signal(),
        signed_receipts=_fake_signed_receipts(public_key),
        operator_lease={"lease_id": "op-1"},
    )

    assert verdict["decision"] == "refused"
    assert "untrusted_signed_receipt:preregistration" in verdict["blockers"]
    assert verdict["signed_receipts"]["preregistration"] is False


def _allow_admission_fn(_request) -> dict:
    """Simulates the PR-6 hardened admission that will verify the holdout
    receipt against the signed packet. On main today, PROMOTION admission
    unconditionally reviews (fail-closed) — see
    test_verify_promotion_default_admission_keeps_door_closed."""
    return {"decision": "allow", "reasons": [], "required_receipts": []}


def test_verify_promotion_default_admission_keeps_door_closed(monkeypatch) -> None:
    """THE U1 custody invariant: with main's real governed admission (which
    never trusts caller metadata for the promotion review skip), even a fully
    receipted, trusted-signed signal REFUSES. The one door exists but stays
    closed until PR-6 lands a receipt-bound admission."""
    from dharma_swarm.forge_v1.forge_v2 import verify_promotion as verifier

    monkeypatch.setattr(verifier, "verify_signed_receipt", lambda _receipt: True)
    public_key = "01" * 32

    verdict = verify_promotion(
        _receipt_ready_signal(),
        signed_receipts=_fake_signed_receipts(public_key),
        trusted_receipt_public_keys=[public_key],
        operator_lease={"lease_id": "op-1"},
    )

    assert verdict["decision"] == "refused"
    assert verdict["live_apply_allowed"] is False
    assert "governed_admission_review" in verdict["blockers"]


def test_verify_promotion_trusts_receipts_only_from_configured_judge_key(monkeypatch) -> None:
    from dharma_swarm.forge_v1.forge_v2 import verify_promotion as verifier

    monkeypatch.setattr(verifier, "verify_signed_receipt", lambda _receipt: True)
    public_key = "01" * 32

    verdict = verify_promotion(
        _receipt_ready_signal(),
        signed_receipts=_fake_signed_receipts(public_key),
        trusted_receipt_public_keys=[public_key],
        operator_lease={"lease_id": "op-1"},
        admission_fn=_allow_admission_fn,
        lease_verifier_fn=_verified_lease,
    )

    assert verdict["decision"] == "allow"
    assert verdict["live_apply_allowed"] is True
    assert verdict["promotion_packet"]["decision"] == "promotable_candidate"
    assert verdict["promotion_packet"]["failed_conjuncts"] == []
    assert not verdict["blockers"]
    assert verdict["signed_receipts"]["preregistration"] is True


def test_verify_promotion_missing_one_trusted_receipt_fails_closed(monkeypatch) -> None:
    from dharma_swarm.forge_v1.forge_v2 import verify_promotion as verifier

    monkeypatch.setattr(verifier, "verify_signed_receipt", lambda _receipt: True)
    public_key = "01" * 32
    receipts = _fake_signed_receipts(public_key)[:-1]
    missing = promote.REQUIRED_RECEIPTS_V0_ABSENT[-1]

    verdict = verify_promotion(
        _receipt_ready_signal(),
        signed_receipts=receipts,
        trusted_receipt_public_keys=[public_key],
        operator_lease={"lease_id": "op-1"},
        lease_verifier_fn=_verified_lease,
    )

    assert verdict["decision"] == "refused"
    assert verdict["live_apply_allowed"] is False
    assert verdict["signed_receipts"][missing] is False
    assert f"missing_or_invalid_signed_receipt:{missing}" in verdict["blockers"]


def test_verify_promotion_allows_backend_verified_trusted_receipt_bundle(monkeypatch) -> None:
    from dharma_swarm.forge_v1.forge_v2 import verify_promotion as verifier

    monkeypatch.setattr(verifier, "_verify_ed25519_signature", _fake_verify_ed25519_signature)
    signing_key = _FakeEd25519Key()
    public_key = signing_key.public_key_hex()

    verdict = verify_promotion(
        _receipt_ready_signal(),
        signed_receipts=_backend_signed_receipts(signing_key),
        trusted_receipt_public_keys=[public_key],
        operator_lease={"lease_id": "op-1"},
        admission_fn=_allow_admission_fn,
        lease_verifier_fn=_verified_lease,
    )

    assert verdict["decision"] == "allow"
    assert verdict["live_apply_allowed"] is True
    assert verdict["promotion_packet"]["decision"] == "promotable_candidate"
    assert verdict["promotion_packet"]["failed_conjuncts"] == []
    assert not verdict["blockers"]


def test_e2_green_pytest_red_holdout_is_refused() -> None:
    signal = {
        "run_id": "e2",
        "signal_key": "e2:key",
        "arm": "verify_chain",
        "taskbed": "fresh_taskbed",
        "mission_class": "verifier_role",
        "overall_ci": {"n": 10, "mean": 0.2, "lower": 0.1, "upper": 0.3, "p_le_0": 0.01},
        "explore_ci": {"n": 5, "mean": 0.4, "lower": 0.1, "upper": 0.6, "p_le_0": 0.01},
        "confirm_ci": {"n": 5, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
        "fdr_positive_significant": True,
        "contamination_state": "fresh_heldout",
        "class_null": "self_moa",
        "null_survived": False,
        "evidence_strength": 0.9,
        "promotion_blockers": [],
        "local_pytest_passed": True,
    }

    verdict = verify_promotion(signal, operator_lease={"lease_id": "op-1"})

    assert verdict["decision"] == "refused"
    assert verdict["live_apply_allowed"] is False
    assert "promotion_packet:stats_confirm_gate" in verdict["blockers"]


def test_signed_receipt_payload_without_pass_status_refuses(monkeypatch) -> None:
    """Signature validity proves authorship, not assent (review finding #5)."""
    from dharma_swarm.forge_v1.forge_v2 import verify_promotion as verifier

    monkeypatch.setattr(verifier, "verify_signed_receipt", lambda _receipt: True)
    public_key = "01" * 32
    receipts = _fake_signed_receipts(public_key)
    del receipts[0]["payload"]["status"]  # signed, trusted, but payload never says pass

    verdict = verify_promotion(
        _receipt_ready_signal(),
        signed_receipts=receipts,
        trusted_receipt_public_keys=[public_key],
        operator_lease={"lease_id": "op-1"},
        admission_fn=_allow_admission_fn,
        lease_verifier_fn=_verified_lease,
    )

    assert verdict["decision"] == "refused"
    assert "invalid_receipt_payload:preregistration" in verdict["blockers"]
    assert verdict["signed_receipts"]["preregistration"] is False


def test_bare_lease_dict_is_not_a_verified_lease(monkeypatch) -> None:
    """{"lease_id": "x"} must never satisfy the lease conjunct (finding #6)."""
    from dharma_swarm.forge_v1.forge_v2 import verify_promotion as verifier

    monkeypatch.setattr(verifier, "verify_signed_receipt", lambda _receipt: True)
    public_key = "01" * 32

    verdict = verify_promotion(
        _receipt_ready_signal(),
        signed_receipts=_fake_signed_receipts(public_key),
        trusted_receipt_public_keys=[public_key],
        operator_lease={"lease_id": "x"},
        admission_fn=_allow_admission_fn,
        # no lease_verifier_fn: default must refuse
    )

    assert verdict["decision"] == "refused"
    assert "operator_lease_unverified" in verdict["blockers"]


def _gate_ready_packet() -> dict:
    return {
        "schema": "forge_v2.promotion_verification.v1",
        "decision": "allow",
        "live_apply_allowed": True,
        "operator_lease_present": True,
        "blockers": [],
        "promotion_packet": {"decision": "promotable_candidate"},
        "governed_admission": {"decision": "allow"},
        "telos": {"decision": "allow"},
        "signed_receipts": {name: True for name in promote.REQUIRED_RECEIPTS_V0_ABSENT},
        "authorized_source_files": ["dharma_swarm/agent_scaffolds/demo.py"],
    }


def test_evolution_gate_packet_is_scoped_not_bearer(monkeypatch) -> None:
    """A packet authorizes ONE mutation, never all mutations (finding #2)."""
    from dharma_swarm.forge_v1.forge_v2 import verify_promotion as verifier
    from dharma_swarm.evolution import _promotion_verification_allows_live

    monkeypatch.setattr(
        verifier, "verify_promotion_verification_signature", lambda *_a, **_k: True
    )

    packet = _gate_ready_packet()
    assert _promotion_verification_allows_live(
        packet,
        requested_source_files=["dharma_swarm/agent_scaffolds/demo.py"],
    ) is True

    # Unrequested file -> refuse: the packet's scope does not cover it.
    assert _promotion_verification_allows_live(
        packet,
        requested_source_files=["dharma_swarm/agent_scaffolds/other.py"],
    ) is False

    # Packet with no authorization scope at all -> refuse outright.
    unbound = dict(packet)
    unbound.pop("authorized_source_files")
    assert _promotion_verification_allows_live(
        unbound,
        requested_source_files=["dharma_swarm/agent_scaffolds/demo.py"],
    ) is False
    assert _promotion_verification_allows_live(unbound) is False


def test_evolution_gate_requires_exact_receipt_names(monkeypatch) -> None:
    """signed_receipts={"anything": true} must never pass (finding #7)."""
    from dharma_swarm.forge_v1.forge_v2 import verify_promotion as verifier
    from dharma_swarm.evolution import _promotion_verification_allows_live

    monkeypatch.setattr(
        verifier, "verify_promotion_verification_signature", lambda *_a, **_k: True
    )

    packet = _gate_ready_packet()
    packet["signed_receipts"] = {"anything": True}
    assert _promotion_verification_allows_live(
        packet,
        requested_source_files=["dharma_swarm/agent_scaffolds/demo.py"],
    ) is False


def test_nvidia_advisory_review_cannot_satisfy_packet_guard() -> None:
    """The advisory NIM review must never stand in for the deterministic
    packet guard (finding #3)."""
    signal = _receipt_ready_signal()
    review = signal.pop("packet_guard_review")
    signal["nvidia_guard_review"] = review  # advisory only

    packet = promote.evaluate_promotion(signal)

    assert packet["decision"] == "refused"
    assert "packet_guard_passed" in packet["failed_conjuncts"]
