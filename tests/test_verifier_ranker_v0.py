from dharma_swarm.verifier_ranker_v0.inventory import build_inventory
from dharma_swarm.verifier_ranker_v0.package import verify_json_schema_basics
from dharma_swarm.verifier_ranker_v0.redaction import redact_record, redact_text
from dharma_swarm.verifier_ranker_v0.schemas import GRAPH_RECORD_TYPES, MODEL_OUTPUT_SCHEMA


def test_inventory_default_root_honors_env_and_explicit_override(
    tmp_path, monkeypatch
) -> None:
    env_home = tmp_path / "env-home"
    explicit_home = tmp_path / "explicit-home"
    sis_docs = tmp_path / "sis" / "docs"
    monkeypatch.setenv("DHARMA_HOME", str(env_home))

    default_inventory = build_inventory(repo_root=tmp_path, sis_docs=sis_docs)
    explicit_inventory = build_inventory(
        repo_root=tmp_path,
        dharma_home=explicit_home,
        sis_docs=sis_docs,
    )

    assert default_inventory["sqlite_metadata"]["runtime_state_db"]["path"] == str(
        env_home / "state" / "runtime.db"
    )
    assert explicit_inventory["sqlite_metadata"]["runtime_state_db"]["path"] == str(
        explicit_home / "state" / "runtime.db"
    )


def test_redact_text_catches_core_sensitive_spans() -> None:
    text = (
        "email john@example.com path /Users/dhyana/project token sk-abc1234567890abcdef "
        "url https://user:pass@example.com/a?token=secret ip 192.168.1.20"
    )
    result = redact_text(text)

    assert "john@example.com" not in result.redacted
    assert "/Users/dhyana" not in result.redacted
    assert "sk-abc" not in result.redacted
    assert "https://user:pass" not in result.redacted
    assert "192.168.1.20" not in result.redacted
    assert result.sensitive_count >= 5


def test_redact_record_hashes_raw_body_fields_fail_closed() -> None:
    record = {
        "id": "msg_1",
        "body": "private message content",
        "metadata": {"route": "ollama:qwen3-coder:480b-cloud"},
    }
    result = redact_record(record)

    assert result.fail_closed is True
    assert result.redacted["body"].startswith("<REDACTED_FIELD:body:sha256:")
    assert result.redacted["metadata"]["route"] == "ollama:qwen3-coder:480b-cloud"


def test_graph_schema_declares_required_record_types() -> None:
    assert set(GRAPH_RECORD_TYPES) == {
        "agent_event",
        "provider_attempt",
        "routing_decision",
        "semantic_receipt",
        "verifier_outcome",
        "artifact_ref",
        "claim_evidence",
        "a2a_delivery",
        "eval_result",
        "human_or_council_label",
    }
    assert verify_json_schema_basics() == []


def test_output_schema_is_strict_json_contract() -> None:
    assert MODEL_OUTPUT_SCHEMA["additionalProperties"] is False
    assert MODEL_OUTPUT_SCHEMA["properties"]["verdict"]["enum"] == [
        "approve",
        "revise",
        "block",
        "escalate",
        "insufficient_context",
    ]
    assert "rationale_refs" in MODEL_OUTPUT_SCHEMA["required"]
