import json

from dharma_swarm.board.adapters.semantic_receipt_adapter import (
    SemanticReceiptBoardAdapter,
    load_semantic_receipt_cards,
    semantic_receipt_to_card,
)
from dharma_swarm.operator_core.semantic_receipt import SCHEMA_VERSION


def _receipt():
    return {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": "semr-board",
        "created_at": "2026-06-11T16:45:00Z",
        "agent_uid": "codex_composer",
        "critic_agent_id": "ollama:glm-5:cloud",
        "model_identity": {"provider": "ollama", "model": "glm-5:cloud"},
        "authored_by_model": True,
        "review_target": "prompt:board",
        "intent_ack": True,
        "capability_match": 0.87,
        "understood_request": True,
        "missing_context": ["semantic Hermes reply"],
        "verdict": "revise",
        "summary": "Projection should expose semantic fields.",
        "recommendations": [{"priority": "p0", "action": "show verdict"}],
        "acceptance_gates": [{"name": "api", "condition": "card returned", "met": True}],
        "explicit_disagreement": "Do not hide missing context.",
        "evidence_refs": ["prompt:board"],
        "confidence": 0.79,
        "not_claimed_agents": ["codex", "claude", "fable", "hermes", "devin"],
        "failure_type": "",
        "failure_reason": "",
        "correlation_id": "corr-board",
        "reply_to": "",
        "model_call_latency_ms": 222,
        "semantic_reply_claim": True,
        "peer_model_processed_claim": True,
    }


def test_semantic_receipt_to_card_projects_model_verdict_and_claims(tmp_path):
    path = tmp_path / "semr-board.json"
    path.write_text(json.dumps(_receipt(), sort_keys=True), encoding="utf-8")

    card = semantic_receipt_to_card(_receipt(), receipt_path=path)

    assert card.id == "semr_semr-board"
    assert card.parent_objective == "semantic_receipts"
    assert card.status == "review"
    assert card.render_hints.lane_hint == "semantic_receipts"
    assert card.receipt_refs[0].kind == "semantic_receipt"
    assert "provider: ollama" in card.body
    assert "confidence: 0.79" in card.body
    assert "semantic_reply_claim: True" in card.body


def test_semantic_receipt_adapter_lists_and_filters_cards(tmp_path):
    root = tmp_path / "semantic_receipts"
    root.mkdir()
    (root / "semr-board.json").write_text(json.dumps(_receipt(), sort_keys=True), encoding="utf-8")

    cards = SemanticReceiptBoardAdapter(root).list_cards(model="glm-5:cloud")

    assert [card.id for card in cards] == ["semr_semr-board"]
    assert load_semantic_receipt_cards(root, verdict="revise")[0].id == "semr_semr-board"
