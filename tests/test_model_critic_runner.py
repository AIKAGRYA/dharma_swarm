import json
import os
import subprocess
import sys
from pathlib import Path

from dharma_swarm.operator_core.semantic_receipt import SCHEMA_VERSION
from scripts.runtime.model_critic_runner import run_model_critic


REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_default_runner_receipt_does_not_churn_checkout(tmp_path):
    prompt_path = _write_prompt(tmp_path)
    response_path = _write_mock_response(tmp_path)
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env.pop("DHARMA_STATE_DIR", None)
    env.pop("DHARMA_HOME", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    before = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout

    result = subprocess.run(
        [
            sys.executable,
            "scripts/runtime/model_critic_runner.py",
            "--prompt-file",
            str(prompt_path),
            "--mock-response-file",
            str(response_path),
            "--review-target",
            "prompt:checkout-churn",
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        env=env,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    artifact = Path(payload["artifact_path"])
    assert artifact.is_relative_to(tmp_path / "home" / ".dharma")
    assert not artifact.is_relative_to(REPO_ROOT)
    after = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    assert after == before


def test_runner_default_honors_explicit_state_root_override(tmp_path):
    state_root = tmp_path / "explicit-state"
    env = {
        **os.environ,
        "DHARMA_STATE_DIR": str(state_root),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from scripts.runtime.model_critic_runner import DEFAULT_OUT_DIR; "
                "print(DEFAULT_OUT_DIR)"
            ),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        env=env,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == (
        state_root
        / "external_agents/codex_composer/nest/semantic_responder/semantic_receipts"
    )


def test_runner_cli_out_dir_remains_an_explicit_fixture_override(tmp_path):
    prompt_path = _write_prompt(tmp_path)
    response_path = _write_mock_response(tmp_path)
    fixture_root = tmp_path / "repo-fixture-receipts"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/runtime/model_critic_runner.py",
            "--prompt-file",
            str(prompt_path),
            "--mock-response-file",
            str(response_path),
            "--out-dir",
            str(fixture_root),
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert Path(json.loads(result.stdout)["artifact_path"]).is_relative_to(fixture_root)
