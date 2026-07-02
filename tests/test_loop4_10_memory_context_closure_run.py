from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from dharma_swarm.cybernetics_codex import _evaluate_loop_closure_replay
from scripts.loop4_10_memory_context_closure_run import (
    MARKER,
    TRANSITIONS,
    _memory_db_path,
    _prepare_state_dir,
    main,
    run_replay,
)


OBSERVED_AT = "2026-07-01T00:00:00Z"


def _read(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_replay_writes_loop4_and_loop10_receipts_that_satisfy_audit(tmp_path: Path) -> None:
    result = asyncio.run(
        run_replay(
            receipt_dir=tmp_path / "receipts",
            state_dir=tmp_path / "state",
            observed_at=OBSERVED_AT,
        )
    )

    assert result["closed"] == {"loop4": True, "loop10": True}
    loop4 = _read(result["receipt_paths"]["loop4"])
    loop10 = _read(result["receipt_paths"]["loop10"])

    assert loop4["loop"] == 4
    assert loop10["loop"] == 10
    for receipt in (loop4, loop10):
        assert receipt["cycles"] > 0
        assert receipt["real_data"] is True
        assert receipt["tick_errors"] == []
        assert all(receipt["transitions_receipted"][name] is True for name in TRANSITIONS)
        assert _evaluate_loop_closure_replay(receipt)["closed"] is True


def test_loop4_receipt_proves_memory_consolidation_and_later_read(tmp_path: Path) -> None:
    result = asyncio.run(
        run_replay(
            receipt_dir=tmp_path / "receipts",
            state_dir=tmp_path / "state",
            observed_at=OBSERVED_AT,
        )
    )
    loop4 = _read(result["receipt_paths"]["loop4"])

    assert loop4["sense_evidence"]["status"] == "completed"
    assert all(item["exists"] and item["sha256"] for item in loop4["sense_evidence"]["artifacts"])
    assert loop4["constrain_evidence"]["admitted_to_memory"] is True
    assert loop4["constrain_evidence"]["artifacts_hashed"] is True
    assert loop4["act_evidence"]["inserted_memory_ids"]
    assert loop4["adapt_proof"]["after"] > loop4["adapt_proof"]["before"]
    assert loop4["adapt_proof"]["fed_forward"] is True
    assert loop4["later_cycle_read_evidence"]["memory_get_context_contains_marker"] is True
    assert loop4["later_cycle_read_evidence"]["read_recent_memories_contains_marker"] is True
    assert MARKER in loop4["later_cycle_read_evidence"]["memory_get_context_snippet"]


def test_loop10_receipt_proves_context_assembly_reads_memory(tmp_path: Path) -> None:
    result = asyncio.run(
        run_replay(
            receipt_dir=tmp_path / "receipts",
            state_dir=tmp_path / "state",
            observed_at=OBSERVED_AT,
        )
    )
    loop10 = _read(result["receipt_paths"]["loop10"])

    assert loop10["sense_evidence"]["reader"] == "dharma_swarm.context.read_memory_context"
    assert loop10["sense_evidence"]["contains_marker"] is True
    assert loop10["interpret_evidence"]["assembler"] == "dharma_swarm.context.build_agent_context"
    assert loop10["interpret_evidence"]["context_contains_marker"] is True
    assert loop10["constrain_evidence"]["admitted_to_package"] is True
    assert loop10["adapt_proof"]["before"] != loop10["adapt_proof"]["after"]
    assert loop10["adapt_proof"]["fed_forward"] is True
    assert loop10["later_cycle_read_evidence"]["later_context_assembly_contains_marker"] is True
    assert MARKER in loop10["later_cycle_read_evidence"]["later_context_snippet"]


def test_state_reset_refuses_existing_memory_db_without_sentinel(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    db_path = _memory_db_path(state_dir)
    db_path.parent.mkdir(parents=True)
    db_path.write_text("live memory", encoding="utf-8")

    with pytest.raises(RuntimeError, match="refusing to reset non-owned state dir"):
        _prepare_state_dir(state_dir, reset_state=True)

    assert db_path.read_text(encoding="utf-8") == "live memory"


def test_cli_writes_receipts_to_requested_directory(tmp_path: Path) -> None:
    receipt_dir = tmp_path / "receipts"
    state_dir = tmp_path / "state"

    exit_code = main(
        [
            "--receipt-dir",
            str(receipt_dir),
            "--state-dir",
            str(state_dir),
            "--observed-at",
            OBSERVED_AT,
        ]
    )

    assert exit_code == 0
    assert (receipt_dir / "2026-07-01_loop4_memory_context_closure.json").exists()
    assert (receipt_dir / "2026-07-01_loop10_context_agent_closure.json").exists()
