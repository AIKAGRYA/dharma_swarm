from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.governance.prompt_lane_run import (
    DEFAULT_PACK,
    PromptLaneError,
    build_work_packet,
    find_lane,
    load_prompt_pack,
    normalize_target,
    prompt_hash,
    write_work_packet,
)


def test_find_lane_returns_requested_lane() -> None:
    pack = load_prompt_pack(DEFAULT_PACK)

    lane = find_lane(pack, "dead_code_removal")

    assert lane["source_artifact"] == "IMG_3594.png"
    assert "Remove only what is CONFIRMED dead" in lane["transcript"]


def test_find_lane_reports_available_lanes() -> None:
    pack = load_prompt_pack(DEFAULT_PACK)

    with pytest.raises(PromptLaneError) as exc_info:
        find_lane(pack, "missing")

    assert "unknown lane_id" in str(exc_info.value)
    assert "dead_code_removal" in str(exc_info.value)


def test_normalize_target_rejects_outside_repo() -> None:
    with pytest.raises(PromptLaneError):
        normalize_target("/tmp")


def test_prompt_hash_changes_with_target() -> None:
    pack = load_prompt_pack(DEFAULT_PACK)
    lane = find_lane(pack, "dead_code_removal")

    first = prompt_hash(pack, lane, "dharma_swarm/vector_store.py", "origin/main")
    second = prompt_hash(pack, lane, "dharma_swarm/file_lock.py", "origin/main")

    assert first != second
    assert len(first) == 24


def test_build_work_packet_contains_governance_constraints() -> None:
    pack = load_prompt_pack(DEFAULT_PACK)
    lane = find_lane(pack, "error_handling_cleanup")
    packet = build_work_packet(
        pack_path=DEFAULT_PACK,
        pack=pack,
        lane=lane,
        target="dharma_swarm/vector_store.py",
        base_ref="origin/main",
    )

    assert packet["kind"] == "prompt_lane_work_packet"
    assert packet["authority"]["authorizes_source_edits"] is False
    assert packet["lane"]["manual_review_required"] is True
    assert "No error hiding" in packet["agent_prompt"]
    assert "Run impact analysis before editing" in packet["agent_prompt"]


def test_write_work_packet_creates_json_and_markdown(tmp_path: Path) -> None:
    pack = load_prompt_pack(DEFAULT_PACK)
    lane = find_lane(pack, "type_strengthening")
    packet = build_work_packet(
        pack_path=DEFAULT_PACK,
        pack=pack,
        lane=lane,
        target="dharma_swarm/vector_store.py",
        base_ref="origin/main",
    )

    json_path, md_path = write_work_packet(packet, tmp_path)

    row = json.loads(json_path.read_text(encoding="utf-8"))
    assert row["prompt_hash"] == packet["prompt_hash"]
    assert "Prompt Lane Run" in md_path.read_text(encoding="utf-8")
