from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from dharma_swarm.evolution import Proposal
from scripts import loop3_evolution_closure_run as loop3


def test_bounded_change_rejects_archive_authority_paths() -> None:
    proposal = Proposal(
        component=loop3.COMPONENT,
        change_type=loop3.CHANGE_TYPE,
        description="bounded replay probe",
        diff="""diff --git a/dharma_swarm/archive.py b/dharma_swarm/archive.py
--- a/dharma_swarm/archive.py
+++ b/dharma_swarm/archive.py
@@ -1 +1 @@
-old
+new
""",
        think_notes=loop3.THINK_NOTES,
    )

    evidence = loop3._bounded_change_evidence(proposal)

    assert evidence["passed"] is False
    assert evidence["protected_hits"] == ["dharma_swarm/archive.py"]


def test_loop3_run_writes_strict_closure_receipt(tmp_path: Path) -> None:
    receipt = tmp_path / "2026-07-01_loop3_evolution_closure.json"
    scratch = tmp_path / "scratch"

    report = asyncio.run(loop3.run(report_path=receipt, scratch_root=scratch))
    written = json.loads(receipt.read_text(encoding="utf-8"))

    assert written == report
    assert loop3._is_closed(report) is True
    assert report["loop"] == 3
    assert report["cycles"] == 2
    assert report["real_data"] is True
    assert all(report["transitions_receipted"].values())
    assert report["tick_errors"] == []
    assert report["adapt_proof"]["before"] != report["adapt_proof"]["after"]
    assert report["adapt_proof"]["fed_forward"] is True


def test_loop3_run_uses_scratch_archive_and_later_cycle_reads_it(tmp_path: Path) -> None:
    report = asyncio.run(
        loop3.run(
            report_path=tmp_path / "receipt.json",
            scratch_root=tmp_path / "scratch",
        )
    )

    act = report["act_evidence"]
    adapt = report["adapt_evidence"]
    later = report["later_cycle_read_evidence"]

    assert act["live_archive_used"] is False
    assert act["scratch_archive_is_live_archive"] is False
    assert act["scratch_archive_one_wire_enforced"] is False
    assert str(tmp_path / "scratch") in act["scratch_archive_path"]
    assert act["fitness"]["weighted"] > 0.0
    assert adapt["prediction_after"] != adapt["prediction_before"]
    assert adapt["predictor_outcomes_after"] == adapt["predictor_outcomes_before"] + 1
    assert later["prediction_changed"] is True
    assert later["later_proposal_read_after_prediction"] is True
    assert later["parent_selection_read_archive_entry"] is True


def test_loop3_refuses_live_archive_as_scratch_root(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.delenv("DHARMA_STATE_DIR", raising=False)
    monkeypatch.delenv("DHARMA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(home))
    scratch = home / ".dharma"
    receipt = tmp_path / "receipt.json"

    with pytest.raises(RuntimeError, match="live Dharma archive"):
        asyncio.run(loop3.run(report_path=receipt, scratch_root=scratch))

    assert not receipt.exists()


def test_loop3_refuses_custom_state_archive_as_scratch_root(
    tmp_path: Path, monkeypatch
) -> None:
    state = tmp_path / "custom-dharma-state"
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state))
    receipt = tmp_path / "receipt.json"

    with pytest.raises(RuntimeError, match="live Dharma archive"):
        asyncio.run(loop3.run(report_path=receipt, scratch_root=state))

    assert not receipt.exists()
