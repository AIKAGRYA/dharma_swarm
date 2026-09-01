from __future__ import annotations

import copy

import pytest

from dharma_swarm.forge_lab.agent_bundle import (
    AGENT_BUNDLE_COMPONENTS,
    IMMUTABLE_KERNEL_COMPONENTS,
    AgentBundleManifest,
    build_receipt,
    evaluate_promotion,
    verify_receipt_chain,
)

DIGEST = "sha256:" + "1" * 64


def _digest_map(keys: tuple[str, ...], digit: str) -> dict[str, str]:
    return {key: "sha256:" + digit * 64 for key in keys}


def _manifest() -> dict:
    return AgentBundleManifest(
        parent_identity="candidate-parent",
        parent_bundle_digest=DIGEST,
        component_digests=_digest_map(AGENT_BUNDLE_COMPONENTS, "2"),
        mutable_genes={"extra_instruction": "execute the bounded mutation"},
        immutable_kernel=_digest_map(IMMUTABLE_KERNEL_COMPONENTS, "3"),
    ).to_dict()


def _receipt_chain() -> list[dict]:
    receipts: list[dict] = []
    previous = None
    for kind in (
        "observation",
        "mutation",
        "evaluation",
        "budget",
        "containment",
        "lineage",
        "decision",
    ):
        receipt = build_receipt(
            kind,
            {"kind": kind},
            previous_digest=previous,
            observed_at="2026-09-02T00:00:00Z",
        )
        receipts.append(receipt)
        previous = receipt["receipt_digest"]
    return receipts


def _promotion_receipts() -> tuple[dict, dict, dict]:
    mutation = build_receipt(
        "mutation",
        {
            "generator_input": {
                "counterfactual_prompt_digest": "sha256:" + "4" * 64,
                "executed_prompt_digest": "sha256:" + "5" * 64,
                "mutation_gene_digest": "sha256:" + "6" * 64,
                "mutation_gene_applied": True,
                "provider_call_completed": True,
            }
        },
        observed_at="2026-09-02T00:00:00Z",
    )
    evaluation = build_receipt(
        "evaluation",
        {
            "evaluation_complete": True,
            "baseline_digest": "sha256:" + "7" * 64,
            "candidate_digest": "sha256:" + "8" * 64,
            "comparison_digest": "sha256:" + "9" * 64,
            "baseline_score": 0.0,
            "candidate_score": 1.0,
            "improvement_demonstrated": True,
        },
        previous_digest=mutation["receipt_digest"],
        observed_at="2026-09-02T00:01:00Z",
    )
    authority = build_receipt(
        "decision",
        {"authority_allowed": True, "authority": "bounded-rsi-evaluator"},
        previous_digest=evaluation["receipt_digest"],
        observed_at="2026-09-02T00:02:00Z",
    )
    return mutation, evaluation, authority


def _interleaved_promotion_chain() -> tuple[list[dict], dict, dict, dict]:
    receipts: list[dict] = []
    previous = None

    def append(kind: str, payload: dict) -> dict:
        nonlocal previous
        receipt = build_receipt(
            kind,
            payload,
            previous_digest=previous,
            observed_at=f"2026-09-02T00:0{len(receipts)}:00Z",
        )
        receipts.append(receipt)
        previous = receipt["receipt_digest"]
        return receipt

    append("observation", {"status": "admitted"})
    mutation = append(
        "mutation",
        {
            "generator_input": {
                "counterfactual_prompt_digest": "sha256:" + "4" * 64,
                "executed_prompt_digest": "sha256:" + "5" * 64,
                "mutation_gene_digest": "sha256:" + "6" * 64,
                "mutation_gene_applied": True,
                "provider_call_completed": True,
            }
        },
    )
    append("budget", {"reserved_usd": 1.25})
    append("containment", {"network": "disabled"})
    evaluation = append(
        "evaluation",
        {
            "evaluation_complete": True,
            "baseline_digest": "sha256:" + "7" * 64,
            "candidate_digest": "sha256:" + "8" * 64,
            "comparison_digest": "sha256:" + "9" * 64,
            "baseline_score": 0.0,
            "candidate_score": 1.0,
            "improvement_demonstrated": True,
        },
    )
    append("lineage", {"parent": "candidate-parent"})
    authority = append(
        "decision",
        {"authority_allowed": True, "authority": "bounded-rsi-evaluator"},
    )
    return receipts, mutation, evaluation, authority


def test_agent_bundle_manifest_binds_all_components_and_kernel_boundary() -> None:
    manifest = _manifest()

    assert manifest["schema"] == "AgentBundle.v1"
    assert set(manifest["component_digests"]) == set(AGENT_BUNDLE_COMPONENTS)
    assert set(manifest["immutable_kernel"]) == set(IMMUTABLE_KERNEL_COMPONENTS)
    assert manifest["bundle_digest"].startswith("sha256:")


def test_agent_bundle_rejects_mutable_gene_crossing_kernel_boundary() -> None:
    with pytest.raises(ValueError, match="immutable-kernel boundary"):
        AgentBundleManifest(
            parent_identity="candidate-parent",
            component_digests=_digest_map(AGENT_BUNDLE_COMPONENTS, "2"),
            mutable_genes={"evaluator": "caller-controlled"},
            immutable_kernel=_digest_map(IMMUTABLE_KERNEL_COMPONENTS, "3"),
        ).to_dict()


def test_agent_bundle_receipts_are_digest_linked_and_tamper_evident() -> None:
    receipts = _receipt_chain()
    assert verify_receipt_chain(receipts) is True

    tampered = copy.deepcopy(receipts)
    tampered[3]["payload"]["kind"] = "changed"
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_receipt_chain(tampered)


def test_typed_promotion_requires_all_four_evidence_obligations() -> None:
    mutation, evaluation, authority = _promotion_receipts()

    decision = evaluate_promotion(
        mutation_receipt=mutation,
        evaluation_receipt=evaluation,
        authority_receipt=authority,
    )

    assert decision["decision"] == "promoted"
    assert decision["source_type"] == "Candidate<Explore>"
    assert decision["target_type"] == "Candidate<Confirmed>"
    assert decision["failed_obligations"] == []


def test_typed_promotion_accepts_ordered_evidence_from_full_interleaved_chain() -> None:
    chain, mutation, evaluation, authority = _interleaved_promotion_chain()

    decision = evaluate_promotion(
        mutation_receipt=mutation,
        evaluation_receipt=evaluation,
        authority_receipt=authority,
        receipt_chain=chain,
    )

    assert verify_receipt_chain(chain) is True
    assert [receipt["kind"] for receipt in chain] == [
        "observation",
        "mutation",
        "budget",
        "containment",
        "evaluation",
        "lineage",
        "decision",
    ]
    assert decision["evidence_chain_valid"] is True
    assert decision["decision"] == "promoted"


@pytest.mark.parametrize(
    ("receipt_name", "payload_key", "value", "failed"),
    [
        ("mutation", "provider_call_completed", False, "MutationExecuted"),
        ("evaluation", "evaluation_complete", False, "EvaluationComplete"),
        (
            "evaluation",
            "improvement_demonstrated",
            False,
            "ImprovementDemonstrated",
        ),
        ("authority", "authority_allowed", False, "AuthorityAllowed"),
    ],
)
def test_typed_promotion_refuses_each_missing_obligation(
    receipt_name: str,
    payload_key: str,
    value: object,
    failed: str,
) -> None:
    mutation, evaluation, authority = _promotion_receipts()
    receipts = {
        "mutation": mutation,
        "evaluation": evaluation,
        "authority": authority,
    }
    target = receipts[receipt_name]["payload"]
    if receipt_name == "mutation":
        target = target["generator_input"]
    target[payload_key] = value

    decision = evaluate_promotion(
        mutation_receipt=mutation,
        evaluation_receipt=evaluation,
        authority_receipt=authority,
    )

    assert decision["decision"] == "refused"
    assert decision["target_type"] == "Candidate<Explore>"
    assert failed in decision["failed_obligations"]
