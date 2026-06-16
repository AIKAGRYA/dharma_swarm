import json

from dharma_swarm.board.adapters.agentops_adapter import (
    AgentOpsBoardAdapter,
    load_agentops_cards,
    work_packet_to_card,
)


def _write_packet(tmp_path, *, packet_id: str = "packet-one"):
    packet_root = tmp_path / "work_packets"
    packet_root.mkdir(exist_ok=True)
    packet = {
        "id": packet_id,
        "base_ref": "origin/main",
        "branch": "chore/agentops-card-projection",
        "worktree": "/tmp/agentops-card-projection",
        "intent": "Project AgentOps packets into BoardStore cards.",
        "allowed_files": ["dharma_swarm/board/**", "tests/**"],
        "forbidden_files": ["ACTIVE_TRACK.yaml"],
        "gates": [
            {
                "name": "diff-check",
                "command": "git diff --check",
            },
            {
                "name": "adapter-tests",
                "command": "pytest -q tests/test_agentops_board_adapter.py",
            },
        ],
        "approval": {
            "before_commit": True,
            "before_merge": True,
        },
    }
    packet_path = packet_root / f"{packet_id}.json"
    packet_path.write_text(json.dumps(packet, sort_keys=True), encoding="utf-8")
    return packet_root, packet_path, packet


def _write_packet_with_artifact(tmp_path, *, packet_id: str = "packet-with-artifact"):
    packet_root = tmp_path / "reports" / "agentops" / "work_packets"
    artifact_path = tmp_path / "reports" / "agentops" / "semantic_reviews" / "review.json"
    packet_root.mkdir(parents=True, exist_ok=True)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text('{"schema_version":"dharma.agentops.semantic_review.v1"}\n', encoding="utf-8")
    packet = {
        "id": packet_id,
        "status": "done",
        "claimed_by": "codex_workhorse_semantic_reviewer",
        "base_ref": "HEAD",
        "branch": "holon/spine-v1",
        "worktree": str(tmp_path),
        "intent": "Verify AgentOps output artifact receipt projection.",
        "allowed_files": ["reports/agentops/**"],
        "forbidden_files": ["api/**"],
        "output_artifacts": [
            {
                "kind": "agentops_semantic_review",
                "uri": "reports/agentops/semantic_reviews/review.json",
                "summary": "Codex workhorse semantic review",
                "created_at": "2026-06-11T09:23:22Z",
            }
        ],
        "gates": [{"name": "json", "command": "python3 -m json.tool reports/agentops/semantic_reviews/review.json"}],
        "commit": {"allowed": False, "message": "reports(agentops): semantic review"},
        "approval": {"before_commit": True, "before_merge": True},
    }
    packet_path = packet_root / f"{packet_id}.json"
    packet_path.write_text(json.dumps(packet, sort_keys=True), encoding="utf-8")
    return packet_root, packet_path, packet, artifact_path


def test_work_packet_to_card_preserves_gates_receipt_and_lane(tmp_path):
    _, packet_path, packet = _write_packet(tmp_path)

    card = work_packet_to_card(packet, packet_path=packet_path)

    assert card.id == "agop_packet-one"
    assert card.parent_objective == "agentops_work_packets"
    assert card.status == "planned"
    assert card.source_surface == "operator_bridge"
    assert card.render_hints.lane_hint == "agentops"
    assert card.render_hints.thread_hint == "/tmp/agentops-card-projection"
    assert card.receipt_refs[0].kind == "agentops_work_packet"
    assert card.receipt_refs[0].uri == str(packet_path.resolve())
    assert [criterion.verifier for criterion in card.acceptance_criteria[:2]] == [
        "git diff --check",
        "pytest -q tests/test_agentops_board_adapter.py",
    ]
    assert {criterion.kind for criterion in card.acceptance_criteria[-2:]} == {"manual"}


def test_adapter_lists_and_filters_work_packet_cards(tmp_path):
    packet_root, _, _ = _write_packet(tmp_path, packet_id="packet-one")
    _write_packet(tmp_path, packet_id="packet-two")

    cards = AgentOpsBoardAdapter(packet_root).list_cards(packet_id="packet-one")

    assert [card.id for card in cards] == ["agop_packet-one"]
    assert load_agentops_cards(packet_root, limit=1)[0].id == "agop_packet-one"


def test_work_packet_to_card_includes_output_artifact_receipts(tmp_path):
    _, packet_path, packet, artifact_path = _write_packet_with_artifact(tmp_path)

    card = work_packet_to_card(packet, packet_path=packet_path)

    assert card.status == "review"
    assert card.receipt_refs[0].kind == "agentops_work_packet"
    assert card.receipt_refs[1].kind == "agentops_semantic_review"
    assert card.receipt_refs[1].uri == "reports/agentops/semantic_reviews/review.json"
    assert card.receipt_refs[1].checksum.startswith("sha256:")
    assert "claimed_by: codex_workhorse_semantic_reviewer" in card.body
    assert f"agentops_semantic_review: {artifact_path.relative_to(tmp_path)}" in card.body


def test_work_packet_to_card_requires_runtime_ref_for_done_projection(tmp_path):
    _, packet_path, packet, _ = _write_packet_with_artifact(tmp_path)

    assert work_packet_to_card(packet, packet_path=packet_path).status == "review"

    packet["runtime_truth_ref"] = {
        "run_id": "run_agentops_1",
        "receipt_id": "runtime_receipts:rr_agentops_1",
    }
    card = work_packet_to_card(packet, packet_path=packet_path)

    assert card.status == "done"
