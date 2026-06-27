"""Verifier for holon session persistence/replay (U6).

The load-bearing assertions:
- save N records -> load returns N in append order;
- resume_point returns the LAST cycle record (so a restart continues, not repeats);
- missing file -> load returns [] and resume_point returns None;
- it is append-only, pure file I/O — no provider/agent/model calls (STUBS only).
All filesystem state is under tmp_path; the canonical ``~/.dharma/agents`` is never touched.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm import holon_persistence


def test_save_three_then_load_returns_three_in_order(tmp_path):
    for i in range(3):
        holon_persistence.save_cycle_record("h", {"step": i, "note": f"cycle-{i}"}, agents_root=tmp_path)

    events = holon_persistence.load_session("h", agents_root=tmp_path)
    assert len(events) == 3
    assert [e["cycle"] for e in events] == [0, 1, 2]
    assert [e["record"]["step"] for e in events] == [0, 1, 2]
    assert [e["record"]["note"] for e in events] == ["cycle-0", "cycle-1", "cycle-2"]


def test_resume_point_returns_last_record(tmp_path):
    holon_persistence.save_cycle_record("h", {"step": 0}, agents_root=tmp_path)
    holon_persistence.save_cycle_record("h", {"step": 1}, agents_root=tmp_path)
    last = holon_persistence.save_cycle_record("h", {"step": 2}, agents_root=tmp_path)

    rp = holon_persistence.resume_point("h", agents_root=tmp_path)
    assert rp is not None
    assert rp["cycle"] == 2
    assert rp["record"]["step"] == 2
    assert rp == last  # the persisted last event IS the resume point


def test_missing_file_load_returns_empty(tmp_path):
    assert holon_persistence.load_session("never-ran", agents_root=tmp_path) == []


def test_missing_file_resume_point_returns_none(tmp_path):
    assert holon_persistence.resume_point("never-ran", agents_root=tmp_path) is None


def test_events_live_under_agent_home_not_new_tree(tmp_path):
    holon_persistence.save_cycle_record("h", {"x": 1}, agents_root=tmp_path)
    expected = tmp_path / "h" / "holon_events.jsonl"
    assert expected.exists()
    # exactly one file created under the per-agent dir; no parallel top-level tree
    assert [p.name for p in (tmp_path / "h").iterdir()] == ["holon_events.jsonl"]


def test_jsonl_is_append_only_one_line_per_record(tmp_path):
    holon_persistence.save_cycle_record("h", {"a": 1}, agents_root=tmp_path)
    holon_persistence.save_cycle_record("h", {"b": 2}, agents_root=tmp_path)
    path = tmp_path / "h" / "holon_events.jsonl"
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        rec = json.loads(line)
        assert rec["holon"] == "h"
        assert "cycle" in rec
        assert "at" in rec
        assert "record" in rec


def test_save_returns_event_with_cycle_and_payload(tmp_path):
    ev = holon_persistence.save_cycle_record("h", {"k": "v"}, agents_root=tmp_path)
    assert ev["cycle"] == 0
    assert ev["holon"] == "h"
    assert ev["record"] == {"k": "v"}
    assert "at" in ev


def test_restart_replay_continues_not_repeats(tmp_path):
    """Simulate a restart: write some cycles, 'restart' (fresh load), and confirm the next
    cycle index continues from resume_point+1 rather than colliding with an existing index."""
    holon_persistence.save_cycle_record("h", {"phase": "pre-restart-0"}, agents_root=tmp_path)
    holon_persistence.save_cycle_record("h", {"phase": "pre-restart-1"}, agents_root=tmp_path)

    # --- process restart: only the on-disk log survives ---
    rp = holon_persistence.resume_point("h", agents_root=tmp_path)
    assert rp["cycle"] == 1
    next_cycle = rp["cycle"] + 1

    new_event = holon_persistence.save_cycle_record(
        "h", {"phase": "post-restart"}, agents_root=tmp_path
    )
    assert new_event["cycle"] == next_cycle == 2

    events = holon_persistence.load_session("h", agents_root=tmp_path)
    assert [e["cycle"] for e in events] == [0, 1, 2]  # continued, no repeat/overwrite


def test_separate_holons_have_separate_logs(tmp_path):
    holon_persistence.save_cycle_record("alpha", {"x": 1}, agents_root=tmp_path)
    holon_persistence.save_cycle_record("beta", {"y": 2}, agents_root=tmp_path)
    holon_persistence.save_cycle_record("alpha", {"x": 3}, agents_root=tmp_path)

    assert len(holon_persistence.load_session("alpha", agents_root=tmp_path)) == 2
    assert len(holon_persistence.load_session("beta", agents_root=tmp_path)) == 1
    assert holon_persistence.resume_point("beta", agents_root=tmp_path)["record"]["y"] == 2


def test_malformed_line_is_skipped_not_fatal(tmp_path):
    """A single corrupt append must not make the whole session unreplayable."""
    holon_persistence.save_cycle_record("h", {"good": 1}, agents_root=tmp_path)
    path = tmp_path / "h" / "holon_events.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{ this is not valid json\n")
    holon_persistence.save_cycle_record("h", {"good": 2}, agents_root=tmp_path)

    events = holon_persistence.load_session("h", agents_root=tmp_path)
    assert len(events) == 2  # corrupt line skipped, two good records survive
    assert [e["record"]["good"] for e in events] == [1, 2]


def test_blank_lines_ignored(tmp_path):
    path = tmp_path / "h" / "holon_events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n\n{"cycle": 0, "holon": "h", "at": "t", "record": {"z": 9}}\n\n', encoding="utf-8")
    events = holon_persistence.load_session("h", agents_root=tmp_path)
    assert len(events) == 1
    assert events[0]["record"]["z"] == 9


def test_non_dict_record_rejected(tmp_path):
    with pytest.raises(TypeError):
        holon_persistence.save_cycle_record("h", ["not", "a", "dict"], agents_root=tmp_path)  # type: ignore[arg-type]


def test_append_talk_receipt_writes_ledger_and_conversation_receipt(tmp_path):
    receipt = holon_persistence.append_talk_receipt(
        "h",
        {
            "session_id": "holon-h",
            "model": "test-model",
            "you": "status?",
            "reply": "read-only status",
            "context_refs": ["identity.json"],
        },
        agents_root=tmp_path,
    )

    ledger = tmp_path / "h" / "talk_receipts.jsonl"
    strict_receipt = tmp_path / "h" / "dialogue" / "conversation_receipts"
    assert ledger.exists()
    assert strict_receipt.exists()
    ledger_row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
    receipt_path = tmp_path / "h" / "dialogue" / "conversation_receipts" / Path(receipt["receipt_path"]).name
    strict_row = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert ledger_row["schema_version"] == "dharma.holon_conversation_receipt.v1"
    assert ledger_row["receipt_path"] == str(receipt_path)
    assert strict_row["reply_sha256"] == ledger_row["reply_sha256"]
    assert strict_row["policy_ceiling"] == "read_only_dialogue_no_privileged_action"


def test_load_talk_receipts_skips_malformed_lines(tmp_path):
    holon_persistence.append_talk_receipt("h", {"you": "a", "reply": "b"}, agents_root=tmp_path)
    ledger = tmp_path / "h" / "talk_receipts.jsonl"
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write("{bad json\n")
    holon_persistence.append_talk_receipt("h", {"you": "c", "reply": "d"}, agents_root=tmp_path)

    receipts = holon_persistence.load_talk_receipts("h", agents_root=tmp_path)

    assert len(receipts) == 2
    assert [item["you"] for item in receipts] == ["a", "c"]
