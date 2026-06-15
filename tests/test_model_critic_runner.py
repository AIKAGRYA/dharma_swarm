import json

from dharma_swarm.operator_core.semantic_receipt import SCHEMA_VERSION
from scripts.runtime.model_critic_runner import run_model_critic


def _write_prompt(tmp_path):
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("Review the SemanticReceipt runner plan.", encoding="utf-8")
    return prompt_path


def _write_mock_response(tmp_path):
    response = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": "semr-mock",
        "created_at": "2026-06-11T16:40:00Z",
        "agent_uid": "codex_composer",
        "critic_agent_id": "ollama:glm-5:cloud",
        "model_identity": {"provider": "ollama", "model": "glm-5:cloud"},
        "authored_by_model": True,
        "review_target": "prompt:mock",
        "intent_ack": True,
        "capability_match": 0.9,
        "understood_request": True,
        "missing_context": [],
        "verdict": "pass",
        "summary": "The runner is narrow and receipt-backed.",
        "recommendations": [{"priority": "p1", "action": "project the receipt"}],
        "acceptance_gates": [{"name": "projection", "condition": "card exists", "met": True}],
        "explicit_disagreement": "",
        "evidence_refs": [],
        "confidence": 0.84,
        "not_claimed_agents": ["codex", "claude", "fable", "hermes", "devin"],
        "failure_type": "",
        "failure_reason": "",
        "correlation_id": "corr-mock",
        "reply_to": "",
        "model_call_latency_ms": 17,
    }
    response_path = tmp_path / "mock_response.json"
    response_path.write_text(json.dumps(response), encoding="utf-8")
    return response_path


def test_runner_writes_validated_artifact_from_mock_model_response(tmp_path):
    prompt_path = _write_prompt(tmp_path)
    response_path = _write_mock_response(tmp_path)

    result = run_model_critic(
        prompt_file=prompt_path,
        provider="ollama",
        model="glm-5:cloud",
        out_dir=tmp_path / "semantic_receipts",
        mock_response_file=response_path,
        review_target="prompt:mock",
    )

    artifact_path = result["artifact_path"]
    receipt = json.loads(open(artifact_path, encoding="utf-8").read())
    assert receipt["semantic_reply_claim"] is True
    assert receipt["peer_model_processed_claim"] is True
    assert receipt["failure_type"] == ""
    assert receipt["raw_response_sha256"]


def test_runner_records_typed_failure_for_unavailable_provider(tmp_path):
    prompt_path = _write_prompt(tmp_path)

    result = run_model_critic(
        prompt_file=prompt_path,
        provider="unavailable",
        model="missing-model",
        out_dir=tmp_path / "semantic_receipts",
        review_target="prompt:mock",
    )

    receipt = json.loads(open(result["artifact_path"], encoding="utf-8").read())
    assert receipt["semantic_reply_claim"] is False
    assert receipt["failure_type"] == "provider_unavailable"
    assert receipt["failure_reason"]
    assert receipt["verdict"] == "blocked"
