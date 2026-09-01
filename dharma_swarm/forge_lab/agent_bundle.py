"""Typed AgentBundle identity, receipt chaining, and promotion semantics.

This module is deliberately store-free. Runtime owners may persist the returned
records through the existing append-only archive/receipt primitives; this layer
only defines canonical values and checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from dharma_swarm.forge_lab.state_io import content_digest, now_utc, validate_digest

AGENT_BUNDLE_SCHEMA = "AgentBundle.v1"
RECEIPT_SCHEMA = "rsi_lab.agent_bundle_receipt.v1"
PROMOTION_SCHEMA = "rsi_lab.typed_promotion.v1"

AGENT_BUNDLE_COMPONENTS = (
    "code",
    "tools",
    "prompts",
    "skills",
    "memory",
    "orchestration",
    "search_policy",
)
IMMUTABLE_KERNEL_COMPONENTS = (
    "evaluator",
    "authority_rules",
    "budgets",
    "task_custody",
    "credential_broker",
    "model_weights",
)
RECEIPT_KINDS = (
    "observation",
    "mutation",
    "evaluation",
    "budget",
    "containment",
    "lineage",
    "decision",
)


class CandidateModality(str, Enum):
    EXPLORE = "Candidate<Explore>"
    CONFIRMED = "Candidate<Confirmed>"


def _exact_digest_map(
    values: Mapping[str, str],
    *,
    required: Iterable[str],
    field: str,
) -> dict[str, str]:
    required_keys = tuple(required)
    if set(values) != set(required_keys):
        raise ValueError(f"{field} must contain exactly {sorted(required_keys)}")
    return {key: validate_digest(values[key]) for key in required_keys}


@dataclass(frozen=True)
class AgentBundleManifest:
    parent_identity: str
    component_digests: Mapping[str, str]
    mutable_genes: Mapping[str, Any]
    immutable_kernel: Mapping[str, str]
    parent_bundle_digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        parent_identity = str(self.parent_identity or "").strip()
        if not parent_identity:
            raise ValueError("parent_identity must be non-empty")
        if self.parent_bundle_digest is not None:
            validate_digest(self.parent_bundle_digest)
        genes = dict(self.mutable_genes)
        overlap = sorted(set(genes) & set(IMMUTABLE_KERNEL_COMPONENTS))
        if overlap:
            raise ValueError(f"mutable_genes cross immutable-kernel boundary: {overlap}")
        payload = {
            "schema": AGENT_BUNDLE_SCHEMA,
            "parent_identity": parent_identity,
            "parent_bundle_digest": self.parent_bundle_digest,
            "component_digests": _exact_digest_map(
                self.component_digests,
                required=AGENT_BUNDLE_COMPONENTS,
                field="component_digests",
            ),
            "mutable_genes": genes,
            "immutable_kernel": _exact_digest_map(
                self.immutable_kernel,
                required=IMMUTABLE_KERNEL_COMPONENTS,
                field="immutable_kernel",
            ),
        }
        payload["bundle_digest"] = content_digest(payload)
        return payload


def build_receipt(
    kind: str,
    payload: Mapping[str, Any],
    *,
    previous_digest: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    if kind not in RECEIPT_KINDS:
        raise ValueError(f"unknown AgentBundle receipt kind: {kind}")
    if previous_digest is not None:
        validate_digest(previous_digest)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "kind": kind,
        "observed_at": observed_at or now_utc(),
        "previous_digest": previous_digest,
        "payload": dict(payload),
    }
    receipt["receipt_digest"] = content_digest(receipt)
    return receipt


def verify_receipt_chain(receipts: Iterable[Mapping[str, Any]]) -> bool:
    previous: str | None = None
    for raw in receipts:
        receipt = dict(raw)
        claimed = validate_digest(str(receipt.pop("receipt_digest", "")))
        if receipt.get("schema") != RECEIPT_SCHEMA:
            raise ValueError("unsupported AgentBundle receipt schema")
        if receipt.get("kind") not in RECEIPT_KINDS:
            raise ValueError("unsupported AgentBundle receipt kind")
        if receipt.get("previous_digest") != previous:
            raise ValueError("AgentBundle receipt chain discontinuity")
        if content_digest(receipt) != claimed:
            raise ValueError("AgentBundle receipt digest mismatch")
        previous = claimed
    return True


def _mutation_executed(receipt: Mapping[str, Any]) -> bool:
    payload = receipt.get("payload")
    if receipt.get("kind") != "mutation" or not isinstance(payload, Mapping):
        return False
    generator_input = payload.get("generator_input")
    if not isinstance(generator_input, Mapping):
        return False
    counterfactual = str(generator_input.get("counterfactual_prompt_digest") or "")
    executed = str(generator_input.get("executed_prompt_digest") or "")
    try:
        validate_digest(counterfactual)
        validate_digest(executed)
        validate_digest(str(generator_input.get("mutation_gene_digest") or ""))
    except ValueError:
        return False
    return bool(
        generator_input.get("mutation_gene_applied") is True
        and generator_input.get("provider_call_completed") is True
        and executed != counterfactual
    )


def _evaluation_obligations(receipt: Mapping[str, Any]) -> tuple[bool, bool]:
    payload = receipt.get("payload")
    if receipt.get("kind") != "evaluation" or not isinstance(payload, Mapping):
        return False, False
    try:
        validate_digest(str(payload.get("baseline_digest") or ""))
        validate_digest(str(payload.get("candidate_digest") or ""))
        validate_digest(str(payload.get("comparison_digest") or ""))
    except ValueError:
        return False, False
    baseline = payload.get("baseline_score")
    candidate = payload.get("candidate_score")
    numeric = (
        isinstance(baseline, (int, float))
        and not isinstance(baseline, bool)
        and isinstance(candidate, (int, float))
        and not isinstance(candidate, bool)
    )
    complete = bool(payload.get("evaluation_complete") is True and numeric)
    improved = bool(
        complete
        and payload.get("improvement_demonstrated") is True
        and float(candidate) > float(baseline)
    )
    return complete, improved


def _authority_allowed(receipt: Mapping[str, Any]) -> bool:
    payload = receipt.get("payload")
    return bool(
        receipt.get("kind") == "decision"
        and isinstance(payload, Mapping)
        and payload.get("authority_allowed") is True
        and payload.get("authority") not in (None, "")
    )


def evaluate_promotion(
    *,
    mutation_receipt: Mapping[str, Any],
    evaluation_receipt: Mapping[str, Any],
    authority_receipt: Mapping[str, Any],
    receipt_chain: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate the sole Explore→Confirmed promotion rule from evidence."""

    evidence_error = None
    chain = list(
        receipt_chain
        if receipt_chain is not None
        else [mutation_receipt, evaluation_receipt, authority_receipt]
    )
    try:
        verify_receipt_chain(chain)
        chain_digests = [
            str(receipt.get("receipt_digest") or "") for receipt in chain
        ]
        evidence_digests = [
            str(receipt.get("receipt_digest") or "")
            for receipt in (
                mutation_receipt,
                evaluation_receipt,
                authority_receipt,
            )
        ]
        positions = [chain_digests.index(digest) for digest in evidence_digests]
        if positions != sorted(set(positions)):
            raise ValueError(
                "promotion evidence receipts are missing, duplicated, or out of order"
            )
    except ValueError as exc:
        evidence_error = str(exc)
    evidence_chain_valid = evidence_error is None
    mutation_executed = evidence_chain_valid and _mutation_executed(mutation_receipt)
    if evidence_chain_valid:
        evaluation_complete, improvement_demonstrated = _evaluation_obligations(
            evaluation_receipt
        )
        authority_allowed = _authority_allowed(authority_receipt)
    else:
        evaluation_complete = False
        improvement_demonstrated = False
        authority_allowed = False
    obligations = {
        "MutationExecuted": mutation_executed,
        "EvaluationComplete": evaluation_complete,
        "ImprovementDemonstrated": improvement_demonstrated,
        "AuthorityAllowed": authority_allowed,
    }
    failed = [name for name, passed in obligations.items() if not passed]
    promoted = not failed
    result = {
        "schema": PROMOTION_SCHEMA,
        "source_type": CandidateModality.EXPLORE.value,
        "target_type": (
            CandidateModality.CONFIRMED.value
            if promoted
            else CandidateModality.EXPLORE.value
        ),
        "decision": "promoted" if promoted else "refused",
        "evidence_chain_valid": evidence_chain_valid,
        "evidence_error": evidence_error,
        "proof_obligations": obligations,
        "failed_obligations": failed,
        "evidence_digests": {
            "mutation": mutation_receipt.get("receipt_digest"),
            "evaluation": evaluation_receipt.get("receipt_digest"),
            "authority": authority_receipt.get("receipt_digest"),
        },
    }
    result["decision_digest"] = content_digest(result)
    return result


__all__ = [
    "AGENT_BUNDLE_COMPONENTS",
    "AGENT_BUNDLE_SCHEMA",
    "IMMUTABLE_KERNEL_COMPONENTS",
    "PROMOTION_SCHEMA",
    "RECEIPT_KINDS",
    "RECEIPT_SCHEMA",
    "AgentBundleManifest",
    "CandidateModality",
    "build_receipt",
    "evaluate_promotion",
    "verify_receipt_chain",
]
