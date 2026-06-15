import json

from dharma_swarm.board.adapters.a2a_send_adapter import (
    A2ASendBoardAdapter,
    a2a_domain_reply_receipt_to_card,
    a2a_inbox_bridge_receipt_to_card,
    a2a_reply_capture_receipt_to_card,
    a2a_send_receipt_to_card,
    load_a2a_send_cards,
)


def _write_receipt(tmp_path, *, target: str = "fable_5_cursor", packet_id: str = "pkt-1"):
    receipt_root = tmp_path / "send_receipts"
    receipt_root.mkdir(exist_ok=True)
    receipt = {
        "schema_version": "dharma.a2a.send_receipt.v1",
        "packet_id": packet_id,
        "timestamp": "2026-06-11T07:40:00Z",
        "to": target,
        "subject": f"dharma.a2a.{target}",
        "ack_subject": f"dharma.a2a.{target}.ack.{packet_id}",
        "reply_subject": f"dharma.a2a.{target}.reply.{packet_id}",
        "file": "packet.md",
        "status": "NATS_CLIENT_MISSING",
        "ack_tier": None,
        "contact_evidence_tier": "NO_CONTACT",
        "live_contact_claim": False,
        "collaboration_claim": "none",
        "operator_contact_note": "no live A2A collaboration proven",
        "error": "ModuleNotFoundError: No module named 'nats'",
    }
    receipt_path = receipt_root / f"20260611T074000Z-{target}-{packet_id}.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    return receipt_root, receipt_path, receipt


def _write_bridge_receipt(tmp_path, *, target: str = "hermes-m5", packet_id: str = "pkt-bridge"):
    receipt_root = tmp_path / "bridge_receipts"
    receipt_root.mkdir(exist_ok=True)
    receipt = {
        "schema_version": "dharma.a2a.inbox_bridge_receipt.v1",
        "timestamp": "2026-06-11T08:15:00Z",
        "agent_uid": target,
        "subject": f"dharma.agent.{target}.inbox",
        "consumer": "hermes_inbox",
        "packet_id": packet_id,
        "status": "DELIVERED_AND_ACKED",
        "ack_subject": f"dharma.agent.{target}.inbox.ack.{packet_id}",
        "contact_evidence_tier": "HANDLER_ACKED",
        "collaboration_claim": "filesystem_delivery_handler_ack",
        "semantic_reply_claim": False,
        "peer_model_processed_claim": False,
        "delivery_path": f"/tmp/{packet_id}.json",
        "operator_contact_note": "delivery handler persisted the envelope",
    }
    receipt_path = receipt_root / f"20260611T081500Z-{target}-{packet_id}.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    return receipt_root, receipt_path, receipt


def _write_reply_receipt(tmp_path, *, target: str = "hermes", packet_id: str = "pkt-reply"):
    receipt_root = tmp_path / "reply_receipts"
    receipt_root.mkdir(exist_ok=True)
    receipt = {
        "schema_version": "dharma.a2a.reply_capture_receipt.v1",
        "timestamp": "2026-06-11T08:32:00Z",
        "to": target,
        "target_uid": "hermes-m5",
        "packet_id": packet_id,
        "status": "NO_REPLY",
        "reply_evidence_tier": "NO_REPLY",
        "contact_evidence_tier": "HANDLER_ACKED",
        "semantic_reply_claim": False,
        "domain_receipt_claim": False,
        "reply_subject": f"dharma.agent.hermes-m5.inbox.reply.{packet_id}",
        "send_receipt_path": f"/tmp/{packet_id}-send.json",
        "operator_contact_note": "no reply payload was available",
    }
    receipt_path = receipt_root / f"20260611T083200Z-{target}-{packet_id}.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    return receipt_root, receipt_path, receipt


def _write_domain_reply_receipt(tmp_path, *, target: str = "hermes-m5", packet_id: str = "pkt-domain"):
    receipt_root = tmp_path / "domain_reply_receipts"
    receipt_root.mkdir(exist_ok=True)
    receipt = {
        "schema_version": "dharma.a2a.domain_reply_publish_receipt.v1",
        "timestamp": "2026-06-11T08:49:00Z",
        "agent_uid": target,
        "packet_id": packet_id,
        "status": "ARTIFACT_INVALID",
        "reply_evidence_tier": "NO_CONTACT",
        "contact_evidence_tier": "NO_CONTACT",
        "semantic_reply_claim": False,
        "domain_receipt_claim": False,
        "target_owned_artifact_claim": False,
        "reply_subject": f"dharma.agent.{target}.inbox.reply.{packet_id}",
        "send_receipt_path": f"/tmp/{packet_id}-send.json",
        "reply_artifact_path": f"/tmp/{packet_id}-reply.json",
        "operator_contact_note": "reply artifact failed target-owned validation",
    }
    receipt_path = receipt_root / f"20260611T084900Z-{target}-{packet_id}.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    return receipt_root, receipt_path, receipt


def test_a2a_send_receipt_to_card_preserves_no_contact_claim(tmp_path):
    _, receipt_path, receipt = _write_receipt(tmp_path)

    card = a2a_send_receipt_to_card(receipt, receipt_path=receipt_path)

    assert card.id == "a2a_fable_5_cursor_pkt-1"
    assert card.parent_objective == "a2a_peer_contact"
    assert card.status == "blocked"
    assert card.assignee_kind == "cursor"
    assert card.render_hints.lane_hint == "a2a"
    assert card.render_hints.map_node_kind == "a2a_send_receipt"
    assert "contact_evidence_tier: NO_CONTACT" in card.body
    assert "live_contact_claim: False" in card.body
    assert card.receipt_refs[0].kind == "a2a_send_receipt"
    assert card.acceptance_criteria[1].kind == "external"


def test_a2a_inbox_bridge_receipt_to_card_preserves_semantic_gap(tmp_path):
    _, receipt_path, receipt = _write_bridge_receipt(tmp_path)

    card = a2a_inbox_bridge_receipt_to_card(receipt, receipt_path=receipt_path)

    assert card.id == "a2a_bridge_hermes-m5_pkt-bridge"
    assert card.status == "review"
    assert card.receipt_refs[0].kind == "a2a_inbox_bridge_receipt"
    assert card.render_hints.map_node_kind == "a2a_inbox_bridge_receipt"
    assert "kind: inbox_bridge" in card.body
    assert "semantic_reply_claim: False" in card.body
    assert "peer_model_processed_claim: False" in card.body


def test_a2a_reply_capture_receipt_to_card_preserves_no_reply_gap(tmp_path):
    _, receipt_path, receipt = _write_reply_receipt(tmp_path)

    card = a2a_reply_capture_receipt_to_card(receipt, receipt_path=receipt_path)

    assert card.id == "a2a_reply_hermes_pkt-reply"
    assert card.status == "review"
    assert card.receipt_refs[0].kind == "a2a_reply_capture_receipt"
    assert card.render_hints.map_node_kind == "a2a_reply_capture_receipt"
    assert "kind: reply_capture" in card.body
    assert "reply_evidence_tier: NO_REPLY" in card.body
    assert "semantic_reply_claim: False" in card.body
    assert "domain_receipt_claim: False" in card.body


def test_a2a_domain_reply_receipt_to_card_preserves_target_owned_gate(tmp_path):
    _, receipt_path, receipt = _write_domain_reply_receipt(tmp_path)

    card = a2a_domain_reply_receipt_to_card(receipt, receipt_path=receipt_path)

    assert card.id == "a2a_domain_reply_hermes-m5_pkt-domain"
    assert card.status == "blocked"
    assert card.receipt_refs[0].kind == "a2a_domain_reply_publish_receipt"
    assert card.render_hints.map_node_kind == "a2a_domain_reply_publish_receipt"
    assert "kind: domain_reply_publish" in card.body
    assert "target_owned_artifact_claim: False" in card.body
    assert card.acceptance_criteria[1].verifier == "scripts/runtime/a2a_reply_capture.py"


def test_a2a_send_adapter_lists_and_filters_cards(tmp_path):
    receipt_root, _, _ = _write_receipt(tmp_path, target="fable_5_cursor", packet_id="pkt-1")
    _write_receipt(tmp_path, target="hermes-m5", packet_id="pkt-2")

    cards = A2ASendBoardAdapter(receipt_root).list_cards(target="fable_5_cursor")

    assert [card.id for card in cards] == ["a2a_fable_5_cursor_pkt-1"]
    assert load_a2a_send_cards(receipt_root, limit=1)[0].render_hints.lane_hint == "a2a"


def test_a2a_adapter_includes_bridge_cards_when_root_is_supplied(tmp_path):
    send_root, _, _ = _write_receipt(tmp_path, target="hermes", packet_id="pkt-send")
    bridge_root, _, _ = _write_bridge_receipt(tmp_path, target="hermes-m5", packet_id="pkt-bridge")

    cards = load_a2a_send_cards(
        send_root,
        bridge_receipt_root=bridge_root,
        target="hermes-m5",
    )

    assert [card.render_hints.map_node_kind for card in cards] == [
        "a2a_inbox_bridge_receipt"
    ]


def test_a2a_adapter_includes_reply_cards_when_root_is_supplied(tmp_path):
    send_root, _, _ = _write_receipt(tmp_path, target="hermes", packet_id="pkt-send")
    reply_root, _, _ = _write_reply_receipt(tmp_path, target="hermes", packet_id="pkt-reply")

    cards = load_a2a_send_cards(
        send_root,
        reply_receipt_root=reply_root,
        target="hermes",
    )

    assert [card.render_hints.map_node_kind for card in cards] == [
        "a2a_reply_capture_receipt",
        "a2a_send_receipt",
    ]


def test_a2a_adapter_includes_domain_reply_cards_when_root_is_supplied(tmp_path):
    send_root, _, _ = _write_receipt(tmp_path, target="hermes", packet_id="pkt-send")
    domain_reply_root, _, _ = _write_domain_reply_receipt(
        tmp_path,
        target="hermes-m5",
        packet_id="pkt-domain",
    )

    cards = load_a2a_send_cards(
        send_root,
        domain_reply_receipt_root=domain_reply_root,
        target="hermes-m5",
    )

    assert [card.render_hints.map_node_kind for card in cards] == [
        "a2a_domain_reply_publish_receipt"
    ]
