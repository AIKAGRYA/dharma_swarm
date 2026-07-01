from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from dharma_swarm.dgm_loop import DGMLoop, run_dgm_evolution_task
from dharma_swarm.forge_v1.forge_v2 import darwin_bridge, forge_fitness, promote, signals
from dharma_swarm.forge_v1.forge_v2.forge_fitness import ArmSpec, grade_genome
from dharma_swarm.forge_v1.forge_v2.verify_promotion import (
    sign_receipt,
    verify_promotion,
    verify_signed_receipt,
    verify_trusted_signed_receipt,
)
from scripts.governance.check_forge_bypass import check_file, check_paths


def _positive_receipt() -> dict:
    return {
        "closeout": "positive_lift_candidate",
        "split_contrasts": {
            "confirm": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
            "explore": {"n": 0, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
        },
        "contrast_vs_class_null": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
        "contamination_state": {"state": "fresh_heldout"},
        "budget_matched_proof": {"any_invalid": False},
    }


def test_grade_genome_routes_scaffold_to_forge_runner_confirm() -> None:
    captured = {}

    def fake_runner(instance_ids, **kwargs):
        captured["instance_ids"] = instance_ids
        captured.update(kwargs)
        return _positive_receipt()

    fitness = grade_genome(
        ArmSpec(arm="verify_chain", label="unit"),
        ["task-a", "task-b"],
        split="confirm",
        runner_fn=fake_runner,
    )

    assert captured["n_explore"] == 0
    assert captured["arm"] == "verify_chain"
    assert captured["gen_id"] == "glm-5.2"
    assert captured["ver_id"] == "moonshotai/kimi-k2.6"
    assert fitness.real_grade is True
    assert fitness.fitness == pytest.approx(0.06)
    assert fitness.promote_eligible is True


def test_grade_genome_blocks_underpowered_confirm() -> None:
    def underpowered_runner(*_args, **_kwargs):
        receipt = _positive_receipt()
        receipt["split_contrasts"]["confirm"] = {
            "n": 135,
            "mean": 0.08,
            "lower": 0.02,
            "upper": 0.14,
            "p_le_0": 0.01,
        }
        receipt["contrast_vs_class_null"] = receipt["split_contrasts"]["confirm"]
        return receipt

    fitness = grade_genome(
        ArmSpec(arm="verify_chain", label="unit"),
        ["task-a"],
        split="confirm",
        runner_fn=underpowered_runner,
    )

    assert fitness.promote_eligible is False
    assert "confirm_n<500" in fitness.blockers


def test_grade_genome_blocks_split_confirm_for_promotion() -> None:
    def split_runner(*_args, **_kwargs):
        receipt = _positive_receipt()
        receipt["split_contrasts"]["explore"] = {
            "n": 50,
            "mean": 0.08,
            "lower": 0.0,
            "upper": 0.15,
            "p_le_0": 0.05,
        }
        return receipt

    fitness = grade_genome(
        ArmSpec(arm="verify_chain", label="unit"),
        ["task-a"],
        split="confirm",
        runner_fn=split_runner,
    )

    assert fitness.promote_eligible is False
    assert "split_confirm_not_allowed_for_promotion" in fitness.blockers


def test_grade_genome_explore_can_learn_but_not_promote() -> None:
    def explore_runner(*_args, **_kwargs):
        receipt = _positive_receipt()
        receipt["split_contrasts"]["explore"] = {
            "n": 50,
            "mean": 0.08,
            "lower": 0.0,
            "upper": 0.15,
            "p_le_0": 0.05,
        }
        return receipt

    fitness = grade_genome(
        {"arm": "mixed_moa", "mix_models": ["glm-5.2", "moonshotai/kimi-k2.6"]},
        ["task-a"],
        split="explore",
        runner_fn=explore_runner,
    )

    assert fitness.fitness == pytest.approx(0.08)
    assert fitness.promote_eligible is False
    assert "promotion_requires_confirm_split" in fitness.blockers


def test_grade_genome_payload_worker_is_jsonable(monkeypatch) -> None:
    def fake_grade(genome, instance_ids, *, split, **kwargs):
        assert genome == {"arm": "verify_chain"}
        assert instance_ids == ["task-a"]
        assert split == "confirm"
        assert kwargs["budget_usd"] == 0.1
        return forge_fitness.ForgeGenomeFitness(
            genome={"arm": "verify_chain"},
            split="confirm",
            fitness=0.06,
            ci={"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1},
            closeout="positive_lift_candidate",
            real_grade=True,
            promote_eligible=False,
            runner_receipt={"source": "payload-worker"},
            blockers=["missing_signed_receipts"],
        )

    monkeypatch.setattr(forge_fitness, "grade_genome", fake_grade)

    result = forge_fitness.grade_genome_from_payload(
        {
            "genome": {"arm": "verify_chain"},
            "instance_ids": ["task-a"],
            "split": "confirm",
            "budget_usd": 0.1,
        }
    )

    assert result["fitness"] == pytest.approx(0.06)
    assert result["runner_receipt"]["source"] == "payload-worker"


def test_e4_underpowered_positive_lift_is_refused_before_receipts() -> None:
    signal = {
        "run_id": "e4-underpowered",
        "signal_key": "e4:key",
        "arm": "verify_chain",
        "taskbed": "fresh_taskbed",
        "mission_class": "verifier_role",
        "overall_ci": {"n": 135, "mean": 0.08, "lower": 0.02, "upper": 0.14, "p_le_0": 0.01},
        "explore_ci": {"n": 0, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
        "confirm_ci": {"n": 135, "mean": 0.08, "lower": 0.02, "upper": 0.14, "p_le_0": 0.01},
        "fdr_positive_significant": True,
        "contamination_state": "fresh_heldout",
        "class_null": "self_moa",
        "null_survived": False,
        "evidence_strength": 0.9,
        "promotion_blockers": [],
    }

    verdict = verify_promotion(signal, operator_lease={"lease_id": "op-1"})

    assert verdict["decision"] == "refused"
    assert "promotion_packet:e4_confirm_full_500" in verdict["blockers"]


def test_e4_split_confirm_is_refused_even_when_confirm_is_positive() -> None:
    signal = {
        "run_id": "e4-split",
        "signal_key": "e4:split",
        "arm": "verify_chain",
        "taskbed": "fresh_taskbed",
        "mission_class": "verifier_role",
        "overall_ci": {"n": 550, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
        "explore_ci": {"n": 50, "mean": 0.08, "lower": 0.0, "upper": 0.15, "p_le_0": 0.05},
        "confirm_ci": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
        "fdr_positive_significant": True,
        "contamination_state": "fresh_heldout",
        "class_null": "self_moa",
        "null_survived": False,
        "evidence_strength": 0.9,
        "promotion_blockers": [],
    }

    verdict = verify_promotion(signal, operator_lease={"lease_id": "op-1"})

    assert verdict["decision"] == "refused"
    assert "promotion_packet:e4_no_split_confirm" in verdict["blockers"]


def test_e4_wide_confirm_ci_is_refused_as_underpowered() -> None:
    signal = {
        "run_id": "e4-wide-ci",
        "signal_key": "e4:wide",
        "arm": "verify_chain",
        "taskbed": "fresh_taskbed",
        "mission_class": "verifier_role",
        "overall_ci": {"n": 500, "mean": 0.08, "lower": 0.01, "upper": 0.2, "p_le_0": 0.01},
        "explore_ci": {"n": 0, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
        "confirm_ci": {"n": 500, "mean": 0.08, "lower": 0.01, "upper": 0.2, "p_le_0": 0.01},
        "fdr_positive_significant": True,
        "contamination_state": "fresh_heldout",
        "class_null": "self_moa",
        "null_survived": False,
        "evidence_strength": 0.9,
        "promotion_blockers": [],
        "pre_registered_mde": 0.056,
    }

    verdict = verify_promotion(signal, operator_lease={"lease_id": "op-1"})

    assert verdict["decision"] == "refused"
    assert "promotion_packet:e4_confirm_power_sufficient" in verdict["blockers"]


def test_promotion_refuses_clean_contamination_without_sealed_provenance() -> None:
    signal = {
        "run_id": "contam-unsealed",
        "signal_key": "contam:key",
        "arm": "verify_chain",
        "taskbed": "fresh_taskbed",
        "mission_class": "verifier_role",
        "overall_ci": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
        "explore_ci": {"n": 0, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
        "confirm_ci": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
        "fdr_positive_significant": True,
        "contamination_state": "fresh_heldout",
        "class_null": "self_moa",
        "null_survived": False,
        "evidence_strength": 0.9,
        "promotion_blockers": [],
    }

    verdict = verify_promotion(signal, operator_lease={"lease_id": "op-1"})

    assert verdict["decision"] == "refused"
    assert "promotion_packet:contamination_sealed_provenance" in verdict["blockers"]


def test_promotion_accepts_sealed_clean_provenance_predicate_before_receipts() -> None:
    signal = {
        "run_id": "contam-sealed",
        "signal_key": "contam:sealed",
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
        "promotion_blockers": [],
    }

    verdict = verify_promotion(signal, operator_lease={"lease_id": "op-1"})

    predicate = verdict["promotion_packet"]["predicate"]
    assert predicate["contamination_self_mod_clean"] is True
    assert predicate["contamination_sealed_provenance"] is True
    assert "promotion_packet:contamination_sealed_provenance" not in verdict["blockers"]
    assert verdict["decision"] == "refused"  # missing signed receipts still fail closed


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


def _fake_signed_receipts(public_key: str) -> list[dict]:
    return [
        {
            "name": name,
            "payload": {"receipt": name},
            "signature": {
                "scheme": "ed25519",
                "public_key": public_key,
                "signature": "02" * 64,
            },
        }
        for name in promote.REQUIRED_RECEIPTS_V0_ABSENT
    ]


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


def test_signed_receipt_binds_name_payload_and_ruler_epoch(monkeypatch) -> None:
    from dharma_swarm.forge_v1.forge_v2 import verify_promotion as verifier

    monkeypatch.setattr(verifier, "_verify_ed25519_signature", _fake_verify_ed25519_signature)
    signing_key = _FakeEd25519Key()
    public_key = signing_key.public_key_hex()
    receipt = sign_receipt(
        name="preregistration",
        payload={"status": "pass", "epoch_ruler_sha256": "epoch-a"},
        signing_key=signing_key,
        epoch_ruler_sha256="epoch-a",
        key_id="test-judge",
    )

    assert verify_signed_receipt(receipt) is True
    assert verify_trusted_signed_receipt(receipt, trusted_public_keys=[public_key]) is True

    renamed = dict(receipt)
    renamed["name"] = "independent_judge"
    assert verify_signed_receipt(renamed) is False

    wrong_epoch = dict(receipt)
    wrong_epoch["epoch_ruler_sha256"] = "epoch-b"
    assert verify_signed_receipt(wrong_epoch) is False


def test_signed_receipt_requires_epoch_ruler_binding(monkeypatch) -> None:
    from dharma_swarm.forge_v1.forge_v2 import verify_promotion as verifier

    monkeypatch.setattr(verifier, "_verify_ed25519_signature", _fake_verify_ed25519_signature)
    signing_key = _FakeEd25519Key()
    receipt = sign_receipt(
        name="preregistration",
        payload={"status": "pass"},
        signing_key=signing_key,
        epoch_ruler_sha256="epoch-a",
    )
    receipt.pop("epoch_ruler_sha256")

    assert verify_signed_receipt(receipt) is False


def test_promotion_requires_packet_guard_review_before_receipts() -> None:
    signal = _receipt_ready_signal()
    signal.pop("packet_guard_review")

    verdict = verify_promotion(signal, operator_lease={"lease_id": "op-1"})

    predicate = verdict["promotion_packet"]["predicate"]
    assert predicate["packet_guard_review_present"] is False
    assert predicate["packet_guard_passed"] is False
    assert "missing:packet_guard_review" in verdict["promotion_packet"]["blockers"]
    assert "promotion_packet:packet_guard_review_present" in verdict["blockers"]
    assert verdict["decision"] == "refused"


def test_promotion_refuses_blocked_packet_guard_review_before_receipts() -> None:
    signal = _receipt_ready_signal()
    signal["packet_guard_review"] = {
        "deterministic_review": {
            "verdict": "blocked_with_evidence",
            "findings": [
                {
                    "severity": "error",
                    "code": "confirm_taskbed_underpowered",
                    "message": "CONFIRM taskbed is below the full E4 floor.",
                    "evidence": ["task_count=135"],
                }
            ],
        }
    }

    verdict = verify_promotion(signal, operator_lease={"lease_id": "op-1"})

    predicate = verdict["promotion_packet"]["predicate"]
    assert predicate["packet_guard_review_present"] is True
    assert predicate["packet_guard_passed"] is False
    assert "packet_guard:confirm_taskbed_underpowered" in verdict["promotion_packet"]["blockers"]
    assert "promotion_packet:packet_guard_passed" in verdict["blockers"]
    assert verdict["decision"] == "refused"


def test_promotion_accepts_passing_packet_guard_predicate_before_receipts() -> None:
    verdict = verify_promotion(_receipt_ready_signal(), operator_lease={"lease_id": "op-1"})

    predicate = verdict["promotion_packet"]["predicate"]
    assert predicate["packet_guard_review_present"] is True
    assert predicate["packet_guard_passed"] is True
    assert not any(b.startswith("packet_guard:") for b in verdict["promotion_packet"]["blockers"])
    assert verdict["decision"] == "refused"  # signed receipt predicates still fail closed.


def test_promotion_requires_e4_discrimination_receipt_before_receipts() -> None:
    signal = _receipt_ready_signal()
    signal.pop("e4_discrimination_receipt")

    verdict = verify_promotion(signal, operator_lease={"lease_id": "op-1"})

    predicate = verdict["promotion_packet"]["predicate"]
    assert predicate["e4_discrimination_receipt_present"] is False
    assert predicate["e4_discrimination_passed"] is False
    assert "missing:e4_discrimination_receipt" in verdict["promotion_packet"]["blockers"]
    assert "promotion_packet:e4_discrimination_receipt_present" in verdict["blockers"]
    assert verdict["decision"] == "refused"


def test_promotion_refuses_failed_e4_discrimination_receipt_before_receipts() -> None:
    signal = _receipt_ready_signal()
    signal["e4_discrimination_receipt"] = {
        "schema": "forge_v2.e4_discrimination_receipt.v1",
        "decision": "refused",
        "promotion_gate_satisfied": False,
        "blockers": ["confirm_cis_overlap", "good_confirm_n<500"],
    }

    verdict = verify_promotion(signal, operator_lease={"lease_id": "op-1"})

    predicate = verdict["promotion_packet"]["predicate"]
    assert predicate["e4_discrimination_receipt_present"] is True
    assert predicate["e4_discrimination_passed"] is False
    assert "e4_discrimination:confirm_cis_overlap" in verdict["promotion_packet"]["blockers"]
    assert "promotion_packet:e4_discrimination_passed" in verdict["blockers"]
    assert verdict["decision"] == "refused"


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


def test_verify_promotion_trusts_receipts_only_from_configured_judge_key(monkeypatch) -> None:
    from dharma_swarm.forge_v1.forge_v2 import verify_promotion as verifier

    monkeypatch.setattr(verifier, "verify_signed_receipt", lambda _receipt: True)
    public_key = "01" * 32

    verdict = verify_promotion(
        _receipt_ready_signal(),
        signed_receipts=_fake_signed_receipts(public_key),
        trusted_receipt_public_keys=[public_key],
        operator_lease={"lease_id": "op-1"},
    )

    assert verdict["decision"] == "allow"
    assert verdict["live_apply_allowed"] is True
    assert verdict["promotion_packet"]["decision"] == "promotable_candidate"
    assert verdict["promotion_packet"]["failed_conjuncts"] == []
    assert not verdict["blockers"]
    assert verdict["signed_receipts"]["preregistration"] is True
    assert not any(b.startswith("untrusted_signed_receipt:") for b in verdict["blockers"])
    assert not any(b.startswith("missing_or_invalid_signed_receipt:") for b in verdict["blockers"])


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
    )

    assert verdict["decision"] == "refused"
    assert verdict["live_apply_allowed"] is False
    assert verdict["signed_receipts"][missing] is False
    assert f"promotion_packet:receipt_{missing}_present" in verdict["blockers"]
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


def test_dgm_loop_refuses_direct_live_mode(monkeypatch) -> None:
    monkeypatch.setenv("DHARMA_EVOLUTION_SHADOW", "0")
    monkeypatch.setenv("DGC_AUTONOMY_LEVEL", "3")

    loop = DGMLoop(engine=object(), shadow_mode=None)
    assert loop._shadow_mode is True
    with pytest.raises(ValueError, match="verify_promotion"):
        DGMLoop(engine=object(), shadow_mode=False)


@pytest.mark.asyncio
async def test_dgm_task_refuses_shadow_false() -> None:
    result = await run_dgm_evolution_task(shadow=False)

    assert result["success"] is False
    assert result["shadow_mode"] is True
    assert "verify_promotion" in result["error"]


def test_e3_path_based_freeze_rejects_stats_edit_despite_coordination_label() -> None:
    signal = {
        "mission_class": "coordination_policy",
        "arm": "verify_chain",
        "action": "hold_for_confirm",
        "diff": (
            "diff --git a/dharma_swarm/forge_v1/forge_v2/stats.py "
            "b/dharma_swarm/forge_v1/forge_v2/stats.py\n"
            "--- a/dharma_swarm/forge_v1/forge_v2/stats.py\n"
            "+++ b/dharma_swarm/forge_v1/forge_v2/stats.py\n"
        ),
    }

    with pytest.raises(darwin_bridge.EvaluatorMutationRefused, match="stats.py"):
        darwin_bridge.signal_to_archive_entry(signal)


def test_report_to_signals_clean_kwarg_cannot_override_public_swebench() -> None:
    meta = {
        "arms_tested": ["verify_chain"],
        "task_stats": {"django__django-12209": {"class_null": "self_moa"}},
        "contrasts": {"verify_chain": {"overall": {}, "by_split": {"confirm": {}, "explore": {}}}},
    }

    sig = signals.report_to_signals(
        meta,
        source_report_sha256="sha",
        run_id="run",
        contamination_state="clean",
    )[0]

    assert sig.contamination_state == "possible_pretrain"
    assert "contamination_possible_pretrain" in sig.promotion_blockers


def test_report_to_signals_accepts_sealed_fresh_provenance() -> None:
    meta = {
        "arms_tested": ["verify_chain"],
        "provenance": {"contamination_state": "fresh_heldout"},
        "task_stats": {"fresh__task-1": {"class_null": "self_moa"}},
        "contrasts": {
            "verify_chain": {
                "overall": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
                "by_split": {
                    "confirm": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.1, "p_le_0": 0.01},
                    "explore": {"n": 0},
                },
                "fdr_positive_significant": True,
            }
        },
        "closeout_counts": {"positive_lift_candidate": 1},
    }

    sig = signals.report_to_signals(meta, source_report_sha256="sha", run_id="run")[0]

    assert sig.contamination_state == "fresh_heldout"
    assert sig.sealed_provenance["contamination_state"] == "fresh_heldout"
    assert not any(b.startswith("contamination_") for b in sig.promotion_blockers)


def test_bypass_guard_passes_current_tree_and_fails_shadow_false(tmp_path: Path) -> None:
    assert check_paths() == []

    bypass = tmp_path / "bypass.py"
    bypass.write_text(
        "from dharma_swarm.dgm_loop import DGMLoop\n"
        "DGMLoop(engine=object(), shadow_mode=False)\n",
        encoding="utf-8",
    )

    findings = check_file(bypass)
    assert findings
    assert "shadow_mode=False" in findings[0]
