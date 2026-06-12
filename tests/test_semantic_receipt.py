import pytest

from dharma_swarm.operator_core.semantic_receipt import (
    SCHEMA_VERSION,
    SemanticReceiptValidationError,
    semantic_attributes,
    validate_semantic_receipt,
)


def _valid_receipt():
    return {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": "semr-test",
        "created_at": "2026-06-11T16:30:00Z",
        "agent_uid": "codex_composer",
        "critic_agent_id": "ollama:glm-5:cloud",
        "model_identity": {"provider": "ollama", "model": "glm-5:cloud"},
        "authored_by_model": True,
        "review_target": "prompt:test",
        "intent_ack": True,
        "capability_match": 0.82,
        "understood_request": True,
        "missing_context": ["live Hermes semantic reply"],
        "verdict": "revise",
        "summary": "Build the runner and keep provenance explicit.",
        "recommendations": [{"priority": "p0", "action": "validate provenance"}],
        "acceptance_gates": [{"name": "runner", "condition": "fixture passes", "met": True}],
        "explicit_disagreement": "Do not accept self-reported model identity as proof.",
        "evidence_refs": ["reports/agentops/workhorse_prompts/test.md"],
        "confidence": 0.76,
        "not_claimed_agents": ["codex", "claude", "fable", "hermes", "devin"],
        "failure_type": "",
        "failure_reason": "",
        "correlation_id": "corr-test",
        "reply_to": "",
        "model_call_latency_ms": 1234,
    }


def test_valid_semantic_receipt_sets_semantic_claim_from_validation():
    receipt = validate_semantic_receipt(_valid_receipt())

    assert receipt["semantic_reply_claim"] is True
    assert receipt["peer_model_processed_claim"] is True
    assert receipt["semantic_claim_basis"] == "validated_non_codex_model_artifact"
    attrs = semantic_attributes(receipt)
    assert attrs["dharma.semantic.model_identity.provider"] == "ollama"
    assert attrs["dharma.semantic.verdict"] == "revise"


def test_invalid_semantic_receipt_reports_specific_errors():
    bad = _valid_receipt()
    bad["model_identity"] = {}
    bad["confidence"] = 1.5
    bad["not_claimed_agents"] = []

    with pytest.raises(SemanticReceiptValidationError) as exc:
        validate_semantic_receipt(bad)

    message = str(exc.value)
    assert "model_identity.provider" in message
    assert "confidence must be a number between 0 and 1" in message
    assert "not_claimed_agents must be a non-empty list" in message


def test_typed_failure_artifact_validates_without_semantic_claim():
    failed = _valid_receipt()
    failed.update(
        {
            "authored_by_model": False,
            "intent_ack": False,
            "capability_match": 0.0,
            "understood_request": False,
            "verdict": "blocked",
            "summary": "Provider was unavailable.",
            "explicit_disagreement": "provider_unavailable",
            "confidence": 0.0,
            "failure_type": "provider_unavailable",
            "failure_reason": "provider is not supported by this runner",
        }
    )

    receipt = validate_semantic_receipt(failed)

    assert receipt["semantic_reply_claim"] is False
    assert receipt["peer_model_processed_claim"] is False
    assert receipt["semantic_claim_basis"] == "typed_failure_or_non_model_artifact"
