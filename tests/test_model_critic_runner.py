import json
import urllib.error

from dharma_swarm.operator_core.semantic_receipt import SCHEMA_VERSION
import scripts.runtime.model_critic_runner as runner


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

    result = runner.run_model_critic(
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

    result = runner.run_model_critic(
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


def test_runner_records_provider_unavailable_for_ollama_url_error(tmp_path, monkeypatch):
    prompt_path = _write_prompt(tmp_path)

    def fail_call_ollama(*, model, prompt, endpoint, timeout_seconds):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(runner, "_call_ollama", fail_call_ollama)

    result = runner.run_model_critic(
        prompt_file=prompt_path,
        provider="ollama",
        model="llama3.2:latest",
        out_dir=tmp_path / "semantic_receipts",
        review_target="prompt:mock",
    )

    receipt = json.loads(open(result["artifact_path"], encoding="utf-8").read())
    assert receipt["semantic_reply_claim"] is False
    assert receipt["failure_type"] == "provider_unavailable"
    assert receipt["verdict"] == "blocked"


def test_runner_prompt_uses_requested_agent_uid(tmp_path, monkeypatch):
    prompt_path = _write_prompt(tmp_path)
    response_path = _write_mock_response(tmp_path)
    response = response_path.read_text(encoding="utf-8")
    calls = []

    def fake_call_ollama(*, model, prompt, endpoint, timeout_seconds):
        calls.append(prompt)
        return response, {"response": json.loads(response), "done": True}, 20

    monkeypatch.setattr(runner, "_call_ollama", fake_call_ollama)

    result = runner.run_model_critic(
        prompt_file=prompt_path,
        provider="ollama",
        model="glm-5:cloud",
        out_dir=tmp_path / "semantic_receipts",
        agent_uid="hermes-m5",
        review_target="prompt:mock",
    )

    receipt = json.loads(open(result["artifact_path"], encoding="utf-8").read())
    assert "- agent_uid: hermes-m5" in calls[0]
    assert "- agent_uid: codex_composer" not in calls[0]
    assert receipt["agent_uid"] == "hermes-m5"


def test_runner_repairs_malformed_ollama_semantic_receipt(tmp_path, monkeypatch):
    prompt_path = _write_prompt(tmp_path)
    invalid_response = _write_mock_response(tmp_path)
    invalid = json.loads(invalid_response.read_text(encoding="utf-8"))
    invalid["intent_ack"] = "yes"
    invalid["capability_match"] = "high"
    invalid["summary"] = ""

    repaired = json.loads(invalid_response.read_text(encoding="utf-8"))
    repaired["receipt_id"] = "semr-repaired"
    repaired["summary"] = "The repair keeps the semantic judgment but fixes field types."

    calls = []

    def fake_call_ollama(*, model, prompt, endpoint, timeout_seconds):
        calls.append(prompt)
        response = invalid if len(calls) == 1 else repaired
        return json.dumps(response), {"response": response, "done": True}, 20 + len(calls)

    monkeypatch.setattr(runner, "_call_ollama", fake_call_ollama)

    result = runner.run_model_critic(
        prompt_file=prompt_path,
        provider="ollama",
        model="llama3.2:latest",
        out_dir=tmp_path / "semantic_receipts",
        review_target="prompt:repair",
        repair_attempts=2,
    )

    receipt = json.loads(open(result["artifact_path"], encoding="utf-8").read())
    assert len(calls) == 2
    assert "repairing your previous SemanticReceipt JSON response" in calls[1]
    assert "intent_ack must be a boolean" in calls[1]
    assert receipt["semantic_reply_claim"] is True
    assert receipt["peer_model_processed_claim"] is True
    assert receipt["summary"] == repaired["summary"]
    assert receipt["model_runner"]["repair_attempts_allowed"] == 2
    assert receipt["model_runner"]["repair_attempts_used"] == 1
