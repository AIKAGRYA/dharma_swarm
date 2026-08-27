from __future__ import annotations

import copy
import hashlib
import inspect
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import dharma_swarm.mission_control_verification as verification_module
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
from dharma_swarm.mission_control_verification import (
    CURRENT_VIBE_SCHEMA,
    PATCH_VERIFICATION_SCHEMA,
    PATCH_VIBE_SCHEMA,
    ExpectedPromotionBindings,
    InconclusiveCapability,
    PatchPromotionVerifier,
    PatchPromotionWarrant,
    PromotionRefusal,
    VerifiedVibeHalt,
    evaluate_vibe_halt,
    expected_vibe_halt_binding,
)
from dharma_swarm.models import GateDecision
from dharma_swarm.operator_core.governed_work_admission import GovernedWorkAdmission

_VERIFICATION_HELPER_ORDERS = (
    (
        "dharma_swarm.mission_control_verification_forge",
        "dharma_swarm.mission_control_verification_vibe",
    ),
    (
        "dharma_swarm.mission_control_verification_vibe",
        "dharma_swarm.mission_control_verification_forge",
    ),
)


@pytest.mark.parametrize("modules", _VERIFICATION_HELPER_ORDERS)
def test_verification_helpers_cold_import_in_any_order(modules: tuple[str, ...]) -> None:
    code = ";".join(f"import {module}" for module in modules)
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _public_key(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


def _foundry_evidence() -> dict[str, str]:
    candidate = Candidate(
        candidate_id="proposal-1",
        target_id="dharma_swarm",
        diff="diff",
        origin_model="codex_composer",
    )
    run = EvaluationRunIdentity.from_execution(
        run_id="foundry-run-1",
        command=["python", "-m", "pytest", "tests/test_dgm_loop.py"],
        output={"exit_code": 0, "stdout": "passed", "stderr": ""},
    )
    return {
        "candidate_digest": candidate_digest(candidate),
        "diff_sha256": _sha(candidate.diff),
        "lineage_digest": foundry_digest({"candidate_id": candidate.candidate_id}),
        "command_digest": run.command_digest,
        "output_digest": run.output_digest,
        "isolation_digest": foundry_digest(
            {"isolation_level": "docker_nonet", "network_disabled": True},
        ),
    }


@pytest.fixture
def expected() -> ExpectedPromotionBindings:
    foundry = _foundry_evidence()
    return ExpectedPromotionBindings(
        mission_id="mission-reflex-1",
        task_id="task-patch-1",
        attempt_id="packet-1",
        lease_id="delivery-1",
        packet_id="packet-1",
        correlation_id="a2a_send:codex_composer:packet-1",
        delivery_id="delivery-1",
        proposal_id="proposal-1",
        candidate_digest=foundry["candidate_digest"],
        diff_sha256=foundry["diff_sha256"],
        base_sha="436ebcdcea9573a3dac93eb47078d1d83dcab7ba",
        artifact_sha256=_sha("artifact"),
        lineage_digest=foundry["lineage_digest"],
        command_digest=foundry["command_digest"],
        output_digest=foundry["output_digest"],
        isolation_digest=foundry["isolation_digest"],
        authorized_source_files=("dharma_swarm/dgm_loop.py",),
        executor_agent_uid="codex_composer",
        executor_run_id="executor-run-1",
        verifier_agent_uid="forge_independent_verifier",
        verifier_run_id="verifier-run-1",
        verifier_parent_run_id="executor-run-1",
    )


@pytest.fixture
def judge_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


@pytest.fixture
def receipt_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


@pytest.fixture
def vibe_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def _signal(expected: ExpectedPromotionBindings) -> dict:
    return {
        "run_id": expected.verifier_run_id,
        "signal_key": f"forge-signal:{expected.candidate_digest}",
        "arm": "verify_chain",
        "taskbed": "fresh_taskbed",
        "mission_class": "verifier_role",
        "epoch_id": "epoch-test-1",
        "overall_ci": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.10, "p_le_0": 0.01},
        "explore_ci": {"n": 0, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
        "confirm_ci": {"n": 500, "mean": 0.06, "lower": 0.02, "upper": 0.10, "p_le_0": 0.01},
        "fdr_positive_significant": True,
        "contamination_state": "fresh_heldout",
        "sealed_provenance": {"contamination_state": "fresh_heldout"},
        "class_null": "self_moa",
        "null_survived": False,
        "evidence_strength": 0.9,
        "packet_guard_review": {"deterministic_review": {"verdict": "pass_for_next_scale", "findings": []}},
        "e4_discrimination_receipt": {"decision": "pass", "promotion_gate_satisfied": True, "blockers": []},
        "promotion_blockers": [],
        "report_positive_promotion_allowed": False,
        "source_files": list(expected.authorized_source_files),
    }


def _signed_receipts(key: Ed25519PrivateKey) -> list[dict]:
    epoch = _sha("receipt-epoch")
    return [
        sign_receipt(
            name=name,
            payload={"receipt": name, "status": "pass"},
            signing_key=key,
            epoch_ruler_sha256=epoch,
            key_id="receipt-judge-test",
        )
        for name in promote.REQUIRED_RECEIPTS_V0_ABSENT
    ]


class _AllowTelos:
    def check(self, *_args, **_kwargs):
        return GateDecision.ALLOW, SimpleNamespace(receipt_sha256=_sha("telos")), None


def _canonical_forge_verdict(
    expected: ExpectedPromotionBindings,
    receipt_key: Ed25519PrivateKey,
    *,
    controlled_admission: bool = True,
) -> dict:
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

    kwargs = {
        "signed_receipts": _signed_receipts(receipt_key),
        "operator_lease": {"lease_id": expected.lease_id},
        "trusted_receipt_public_keys": (_public_key(receipt_key),),
        "lease_verifier_fn": lambda lease: lease.get("lease_id") == expected.lease_id,
        "telos_gatekeeper": _AllowTelos(),
    }
    if controlled_admission:
        kwargs["admission_fn"] = admission
    return verify_promotion(_signal(expected), **kwargs)


def _sign_vibe(
    expected: ExpectedPromotionBindings,
    key: Ed25519PrivateKey,
    *,
    outcome: str = "clean",
    findings: list | None = None,
) -> dict:
    body = {
        "schema": PATCH_VIBE_SCHEMA,
        "candidate_digest": expected.candidate_digest,
        "diff_sha256": expected.diff_sha256,
        "verifier": {
            "agent_uid": expected.verifier_agent_uid,
            "run_id": expected.verifier_run_id,
            "parent_run_id": expected.verifier_parent_run_id,
        },
        "ran": True,
        "reported_outcome": outcome,
        "diff_bound": True,
        "calibration_only": False,
        "findings": [] if findings is None else findings,
        "errors": [],
        "blockers": [],
        "process": {"exit_code": 0, "timed_out": False, "output_limited": False},
    }
    body["payload_sha256"] = canonical_sha256(body)
    message = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
    body["signature"] = {
        "scheme": "ed25519",
        "key_id": "vibe-verifier-test",
        "public_key": _public_key(key),
        "signature": key.sign(message).hex(),
    }
    return body


def _envelope(expected, vibe, judge_key, receipt_key) -> dict:
    forge = sign_promotion_verification(
        _canonical_forge_verdict(expected, receipt_key), judge_key, key_id="forge-judge-test"
    )
    return sign_promotion_verification(
        {
            "schema": PATCH_VERIFICATION_SCHEMA,
            "forge_verification": forge,
            "a2a_binding": expected.to_signed_binding(),
            "vibe_halt_binding": expected_vibe_halt_binding(vibe, expected=expected),
        },
        judge_key,
        key_id="patch-judge-test",
    )


def _authority(expected, judge_key, vibe_key) -> PatchPromotionVerifier:
    return PatchPromotionVerifier(
        trusted_judge_public_keys=(_public_key(judge_key),),
        trusted_vibe_verifier_public_keys={expected.verifier_agent_uid: (_public_key(vibe_key),)},
    )


def _resign_inner_and_outer(envelope: dict, judge_key: Ed25519PrivateKey) -> dict:
    envelope["forge_verification"] = sign_promotion_verification(
        envelope["forge_verification"], judge_key, key_id="forge-judge-test"
    )
    return sign_promotion_verification(envelope, judge_key, key_id="patch-judge-test")


def _evaluate(expected, judge_key, receipt_key, vibe_key):
    vibe = _sign_vibe(expected, vibe_key)
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    authority = _authority(expected, judge_key, vibe_key)
    return authority, vibe, envelope, authority.evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )


def test_canonical_producer_core_and_two_signatures_issue_projection_only_warrant(
    expected, judge_key, receipt_key, vibe_key
) -> None:
    authority, vibe, envelope, result = _evaluate(expected, judge_key, receipt_key, vibe_key)

    assert isinstance(result, PatchPromotionWarrant)
    assert bool(result)
    projected = result.to_dict()
    assert projected["capability_scope"] == "projection_only_gate"
    assert projected["repository_effect_authorized"] is False
    assert projected["patch_verification_sha256"] == envelope["payload_sha256"]
    assert projected["forge_verification_sha256"] == envelope["forge_verification"]["payload_sha256"]
    assert projected["vibe_halt_receipt_sha256"] == expected_vibe_halt_binding(
        vibe, expected=expected
    )["receipt_sha256"]
    assert "trusted_judge_public_keys" not in inspect.signature(authority.evaluate).parameters


@pytest.mark.parametrize(
    "field",
    [
        "candidate_digest",
        "lineage_digest",
        "command_digest",
        "output_digest",
        "isolation_digest",
    ],
)
def test_canonical_foundry_digest_type_is_required(
    expected, judge_key, receipt_key, vibe_key, field
) -> None:
    assert getattr(expected, field).startswith("sha256:")
    malformed = replace(
        expected,
        **{field: getattr(expected, field).removeprefix("sha256:")},
    )
    _, _, _, result = _evaluate(malformed, judge_key, receipt_key, vibe_key)

    assert isinstance(result, PromotionRefusal)
    assert f"invalid_expected:{field}_shape" in result.blockers


@pytest.mark.parametrize("field", ["diff_sha256", "artifact_sha256"])
def test_raw_artifact_digest_type_rejects_foundry_prefix(
    expected, judge_key, receipt_key, vibe_key, field
) -> None:
    malformed = replace(expected, **{field: f"sha256:{getattr(expected, field)}"})
    _, _, _, result = _evaluate(malformed, judge_key, receipt_key, vibe_key)

    assert isinstance(result, PromotionRefusal)
    assert f"invalid_expected:{field}_shape" in result.blockers


def test_positive_inner_verdict_is_from_canonical_verify_promotion(expected, receipt_key) -> None:
    verdict = _canonical_forge_verdict(expected, receipt_key)

    assert verdict["schema"] == "forge_v2.promotion_verification.v1"
    assert verdict["decision"] == "allow"
    assert verdict["promotion_packet"]["decision"] == "promotable_candidate"
    assert verdict["promotion_packet"]["safety"] == {
        "shadow_only": True,
        "live_apply_allowed": False,
        "code_diff_allowed": False,
    }
    assert verdict["authorized_source_files"] == list(expected.authorized_source_files)


def test_current_unextended_canonical_output_cannot_warrant(
    expected, judge_key, receipt_key, vibe_key
) -> None:
    vibe = _sign_vibe(expected, vibe_key)
    canonical = _canonical_forge_verdict(expected, receipt_key)
    result = _authority(expected, judge_key, vibe_key).evaluate(
        canonical, expected=expected, vibe_halt_receipt=vibe
    )

    assert isinstance(result, PromotionRefusal)
    assert "patch:schema" in result.blockers
    assert "untrusted_or_invalid_patch_signature" in result.blockers


def test_default_canonical_admission_remains_blocked_and_scope_empty(expected, receipt_key) -> None:
    verdict = _canonical_forge_verdict(expected, receipt_key, controlled_admission=False)

    assert verdict["decision"] == "refused"
    assert "governed_admission_review" in verdict["blockers"]
    assert verdict["governed_admission"]["reduced_authority"]["allowed_files"] == []


def test_current_vibe_calibration_is_inconclusive(expected) -> None:
    result = evaluate_vibe_halt(
        {
            "schema": CURRENT_VIBE_SCHEMA,
            "reported_outcome": "clean",
            "calibration_only": True,
            "diff_bound": False,
        },
        expected=expected,
    )
    assert isinstance(result, InconclusiveCapability)
    assert result.reason == "not_candidate_bound"


def test_public_vibe_classifier_cannot_mint_with_fabricated_coverage(expected, vibe_key) -> None:
    vibe = _sign_vibe(expected, vibe_key)
    result = evaluate_vibe_halt(
        vibe,
        expected=expected,
        signed_identity_coverage=expected_vibe_halt_binding(vibe, expected=expected),
    )
    assert isinstance(result, InconclusiveCapability)
    assert result.reason == "trusted_verifier_signature_required"


def test_transport_or_heartbeat_cannot_warrant(expected, judge_key, vibe_key) -> None:
    result = _authority(expected, judge_key, vibe_key).evaluate(
        {"schema": "dharma.a2a.delivery_record.v1", "status": "acked"},
        expected=expected,
        vibe_halt_receipt=None,
    )
    assert isinstance(result, PromotionRefusal)
    assert not result


def test_vibe_key_must_be_distinct_from_every_judge_key(expected, judge_key, receipt_key) -> None:
    vibe = _sign_vibe(expected, judge_key)
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    result = _authority(expected, judge_key, judge_key).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )

    assert isinstance(result, PromotionRefusal)
    assert "vibe_halt:verifier_key_not_independent" in result.blockers


def test_vibe_key_is_bound_to_expected_verifier_identity(
    expected, judge_key, receipt_key, vibe_key
) -> None:
    vibe = _sign_vibe(expected, vibe_key)
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    result = _authority(expected, judge_key, Ed25519PrivateKey.generate()).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )

    assert isinstance(result, PromotionRefusal)
    assert "vibe_halt:untrusted_verifier_signature" in result.blockers


def test_self_verifier_is_rejected(
    expected, judge_key, receipt_key, vibe_key
) -> None:
    aliased = replace(
        expected,
        verifier_agent_uid=expected.executor_agent_uid,
        verifier_run_id=expected.executor_run_id,
    )
    vibe = _sign_vibe(aliased, vibe_key)
    envelope = _envelope(aliased, vibe, judge_key, receipt_key)
    result = _authority(aliased, judge_key, vibe_key).evaluate(
        envelope, expected=aliased, vibe_halt_receipt=vibe
    )

    assert isinstance(result, PromotionRefusal)
    assert "verifier_agent_not_independent" in result.blockers
    assert "verifier_run_not_independent" in result.blockers


def test_direct_replace_copy_mutation_and_subclass_cannot_forge_capability(
    expected, judge_key, receipt_key, vibe_key
) -> None:
    _, _, _, minted = _evaluate(expected, judge_key, receipt_key, vibe_key)
    assert isinstance(minted, PatchPromotionWarrant)
    direct = PatchPromotionWarrant(
        bindings=expected,
        patch_verification_sha256=_sha("patch"),
        forge_verification_sha256=_sha("forge"),
        vibe_halt_receipt_sha256=_sha("vibe"),
    )
    direct_vibe = VerifiedVibeHalt(
        candidate_digest=expected.candidate_digest,
        diff_sha256=expected.diff_sha256,
        verifier_agent_uid=expected.verifier_agent_uid,
        verifier_run_id=expected.verifier_run_id,
        verifier_public_key=_sha("key"),
        receipt_sha256=_sha("receipt"),
    )
    replaced = replace(minted, forge_verification_sha256=_sha("replacement"))
    copied = copy.copy(minted)
    object.__setattr__(copied, "forge_verification_sha256", _sha("mutated-copy"))

    assert not direct
    assert not direct_vibe
    assert not replaced
    assert not copied
    assert direct.to_dict()["decision"] == "refused"
    assert replaced.to_dict()["decision"] == "refused"
    assert copied.to_dict()["decision"] == "refused"
    with pytest.raises(TypeError):
        class _Forged(PatchPromotionWarrant):
            def __bool__(self) -> bool:
                return True


def test_mutating_original_minted_content_invalidates_registry_fingerprint(
    expected, judge_key, receipt_key, vibe_key
) -> None:
    _, _, _, result = _evaluate(expected, judge_key, receipt_key, vibe_key)
    assert isinstance(result, PatchPromotionWarrant)
    object.__setattr__(result, "forge_verification_sha256", _sha("tampered"))

    assert not result
    assert result.to_dict()["decision"] == "refused"


def test_capability_mint_is_not_module_accessible() -> None:
    assert not hasattr(verification_module, "_remember_capability")
    assert not hasattr(verification_module, "_CAPABILITY_SEAL")


@pytest.mark.parametrize("strength", [float("nan"), float("inf"), float("-inf"), 0.0, -1.0])
def test_evidence_strength_must_be_finite_and_positive(
    expected, judge_key, receipt_key, vibe_key, strength
) -> None:
    vibe = _sign_vibe(expected, vibe_key)
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    promotion = envelope["forge_verification"]["promotion_packet"]
    promotion["evidence_strength"] = strength
    promotion.pop("payload_sha256")
    promotion["payload_sha256"] = canonical_sha256(promotion)
    envelope = _resign_inner_and_outer(envelope, judge_key)

    result = _authority(expected, judge_key, vibe_key).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )
    assert isinstance(result, PromotionRefusal)
    assert "forge:promotion_evidence_strength" in result.blockers


@pytest.mark.parametrize("target", ["admission", "telos"])
def test_admission_and_telos_shapes_reject_unknown_or_revoked_fields(
    expected, judge_key, receipt_key, vibe_key, target
) -> None:
    vibe = _sign_vibe(expected, vibe_key)
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    field = "governed_admission" if target == "admission" else "telos"
    envelope["forge_verification"][field]["revoked"] = True
    envelope = _resign_inner_and_outer(envelope, judge_key)

    result = _authority(expected, judge_key, vibe_key).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )
    assert isinstance(result, PromotionRefusal)
    blocker = "forge:governed_admission" if target == "admission" else "forge:telos"
    assert blocker in result.blockers


def test_nested_reduced_authority_shape_is_closed(expected, judge_key, receipt_key, vibe_key) -> None:
    vibe = _sign_vibe(expected, vibe_key)
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    envelope["forge_verification"]["governed_admission"]["reduced_authority"]["revoked"] = True
    envelope = _resign_inner_and_outer(envelope, judge_key)
    result = _authority(expected, judge_key, vibe_key).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )

    assert isinstance(result, PromotionRefusal)
    assert "forge:governed_admission" in result.blockers


def test_telos_keyword_cannot_hide_blockers(expected, judge_key, receipt_key, vibe_key) -> None:
    vibe = _sign_vibe(expected, vibe_key)
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    envelope["forge_verification"]["telos"]["keyword"] = {
        "decision": "allow",
        "gate": "SATYA",
        "reason": "pass",
        "blockers": ["hidden"],
    }
    envelope = _resign_inner_and_outer(envelope, judge_key)
    result = _authority(expected, judge_key, vibe_key).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )

    assert isinstance(result, PromotionRefusal)
    assert "forge:telos" in result.blockers


@pytest.mark.parametrize("layer", ["outer", "inner", "vibe"])
def test_every_signature_shape_rejects_unknown_or_revoked_fields(
    expected, judge_key, receipt_key, vibe_key, layer
) -> None:
    vibe = _sign_vibe(expected, vibe_key)
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    if layer == "outer":
        envelope["verification_signature"]["revoked"] = True
    elif layer == "inner":
        envelope["forge_verification"]["verification_signature"]["revoked"] = True
        envelope = sign_promotion_verification(envelope, judge_key, key_id="patch-judge-test")
    else:
        vibe["signature"]["revoked"] = True
        envelope["vibe_halt_binding"] = expected_vibe_halt_binding(vibe, expected=expected)
        envelope = sign_promotion_verification(envelope, judge_key, key_id="patch-judge-test")

    result = _authority(expected, judge_key, vibe_key).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )
    assert isinstance(result, PromotionRefusal)
    assert any("signature" in blocker for blocker in result.blockers)


def test_exact_a2a_binding_and_authorized_file_scope_are_required(
    expected, judge_key, receipt_key, vibe_key
) -> None:
    vibe = _sign_vibe(expected, vibe_key)
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    envelope["a2a_binding"]["delivery_id"] = "foreign-delivery"
    envelope["forge_verification"]["authorized_source_files"] = ["dharma_swarm/foreign.py"]
    envelope = _resign_inner_and_outer(envelope, judge_key)

    result = _authority(expected, judge_key, vibe_key).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )
    assert isinstance(result, PromotionRefusal)
    assert "patch:a2a_binding" in result.blockers
    assert "forge:authorized_source_files" in result.blockers


def test_every_expected_digest_and_identity_is_signed_exactly(
    expected, judge_key, receipt_key, vibe_key
) -> None:
    vibe = _sign_vibe(expected, vibe_key)
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    envelope["a2a_binding"]["artifact_sha256"] = _sha("foreign-artifact")
    envelope["a2a_binding"]["executor"]["run_id"] = "foreign-run"
    envelope = sign_promotion_verification(envelope, judge_key, key_id="patch-judge-test")

    result = _authority(expected, judge_key, vibe_key).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )
    assert isinstance(result, PromotionRefusal)
    assert "patch:a2a_binding" in result.blockers


def test_vibe_payload_tamper_is_refused_even_when_outer_judge_rebinds_digest(
    expected, judge_key, receipt_key, vibe_key
) -> None:
    vibe = _sign_vibe(expected, vibe_key)
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    vibe["process"]["exit_code"] = 1
    unsigned_vibe = {
        key: value for key, value in vibe.items() if key not in {"payload_sha256", "signature"}
    }
    vibe["payload_sha256"] = canonical_sha256(unsigned_vibe)
    envelope["vibe_halt_binding"] = expected_vibe_halt_binding(vibe, expected=expected)
    envelope = sign_promotion_verification(envelope, judge_key, key_id="patch-judge-test")

    result = _authority(expected, judge_key, vibe_key).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )
    assert isinstance(result, PromotionRefusal)
    assert "vibe_halt:invalid_verifier_signature" in result.blockers


def test_signed_findings_are_rejection_not_verified_capability(
    expected, judge_key, receipt_key, vibe_key
) -> None:
    vibe = _sign_vibe(
        expected,
        vibe_key,
        outcome="findings",
        findings=[{"code": "unsafe-diff"}],
    )
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    result = _authority(expected, judge_key, vibe_key).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )

    assert isinstance(result, PromotionRefusal)
    assert "vibe_halt:findings" in result.blockers


@pytest.mark.parametrize(
    ("field", "value", "blocker"),
    [
        ("errors", ["scanner-crashed"], "vibe_halt:contradictory_capability_output"),
        ("blockers", ["policy-denied"], "vibe_halt:contradictory_capability_output"),
        ("findings", [{"code": "hidden"}], "vibe_halt:clean_with_findings"),
    ],
)
def test_clean_vibe_cannot_hide_negative_arrays(
    expected, judge_key, receipt_key, vibe_key, field, value, blocker
) -> None:
    vibe = _sign_vibe(expected, vibe_key)
    vibe[field] = value
    unsigned = {key: val for key, val in vibe.items() if key not in {"payload_sha256", "signature"}}
    vibe["payload_sha256"] = canonical_sha256(unsigned)
    message = json.dumps(
        {key: val for key, val in vibe.items() if key != "signature"},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    vibe["signature"]["signature"] = vibe_key.sign(message).hex()
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    result = _authority(expected, judge_key, vibe_key).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )

    assert isinstance(result, PromotionRefusal)
    assert blocker in result.blockers


@pytest.mark.parametrize("malformed", [None, [], "signed", 7])
def test_malformed_input_refuses_without_raising(expected, judge_key, vibe_key, malformed) -> None:
    result = _authority(expected, judge_key, vibe_key).evaluate(
        malformed,  # type: ignore[arg-type]
        expected=expected,
        vibe_halt_receipt=None,
    )
    assert isinstance(result, PromotionRefusal)
    assert not result


def test_trust_roots_are_required_at_composition_time(expected, judge_key, vibe_key) -> None:
    with pytest.raises(ValueError, match="trusted_judge_public_keys"):
        PatchPromotionVerifier(
            trusted_judge_public_keys=(),
            trusted_vibe_verifier_public_keys={
                expected.verifier_agent_uid: (_public_key(vibe_key),)
            },
        )
    with pytest.raises(ValueError, match="trusted_vibe_verifier_public_keys"):
        PatchPromotionVerifier(
            trusted_judge_public_keys=(_public_key(judge_key),),
            trusted_vibe_verifier_public_keys={},
        )

    authority = _authority(expected, judge_key, vibe_key)
    with pytest.raises(AttributeError, match="immutable"):
        authority._judge_keys = frozenset()  # type: ignore[misc]
    with pytest.raises(TypeError):
        authority._vibe_keys_by_agent[expected.verifier_agent_uid] = frozenset()  # type: ignore[index]


def test_outer_envelope_and_nested_forge_signatures_are_both_required(
    expected, judge_key, receipt_key, vibe_key
) -> None:
    vibe = _sign_vibe(expected, vibe_key)
    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    envelope["forge_verification"]["verification_signature"]["signature"] = "00" * 64
    envelope = sign_promotion_verification(envelope, judge_key, key_id="patch-judge-test")

    result = _authority(expected, judge_key, vibe_key).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )
    assert isinstance(result, PromotionRefusal)
    assert "untrusted_or_invalid_forge_signature" in result.blockers

    envelope = _envelope(expected, vibe, judge_key, receipt_key)
    envelope["verification_signature"]["signature"] = "00" * 64
    result = _authority(expected, judge_key, vibe_key).evaluate(
        envelope, expected=expected, vibe_halt_receipt=vibe
    )
    assert isinstance(result, PromotionRefusal)
    assert "untrusted_or_invalid_patch_signature" in result.blockers
