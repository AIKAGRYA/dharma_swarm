from __future__ import annotations

from scripts.revenue.dogfood_cashclaw_autopilot import run_dogfood


def test_cashclaw_dogfood_run_writes_receipts(tmp_path):
    summary = run_dogfood(signal_count=5, output_root=tmp_path)

    assert summary["signals"] == 5
    assert summary["clean_cycles"] == 5
    assert summary["unauthorized_side_effects"] == 0
    assert summary["external_network_reads"] == 0
    assert summary["pass_to_human"] == 0
    assert summary["cycles_with_employee_receipts"] == 5
    assert summary["employee_receipts_written"] == 30
    assert summary["gateway_allow_count"] == 25
    assert summary["gateway_final_review"] == 0
    assert summary["gateway_final_block"] == 5
    run_dir = tmp_path / summary["run_id"]
    assert (run_dir / "summary.md").exists()
    assert (run_dir / "summary.json").exists()
    assert len(list((run_dir / "receipts").glob("cycle_*.md"))) == 5


def test_cashclaw_dogfood_full_signal_mix_summary_counts_verdicts(tmp_path):
    summary = run_dogfood(signal_count=30, output_root=tmp_path)

    assert summary["signals"] == 30
    assert summary["clean_cycles"] == 30
    assert summary["pass_to_human"] == 0
    assert summary["hold"] == 25
    assert summary["kill"] == 5
    assert summary["approval_ready"] == 0
    assert summary["unauthorized_side_effects"] == 0
    assert summary["external_network_reads"] == 0
    assert summary["cycles_with_employee_receipts"] == 30
    assert summary["employee_receipts_written"] == 180
    assert summary["gateway_allow_count"] == 150
    assert summary["gateway_final_review"] == 0
    assert summary["gateway_final_block"] == 30


def test_cashclaw_dogfood_summary_top_candidates_are_sorted_and_receipts_are_local(tmp_path):
    summary = run_dogfood(signal_count=30, output_root=tmp_path)

    scores = [item["score"] for item in summary["top_candidates"]]
    assert len(scores) == 10
    assert scores == sorted(scores, reverse=True)
    assert all(item["side_effects_performed"] is False for item in summary["results"])
    assert all(item["gateway_decision"] == "block" for item in summary["results"])
    assert all(item["employee_receipt_path"] for item in summary["results"])
    summary_md = (tmp_path / summary["run_id"] / "summary.md").read_text(encoding="utf-8")
    assert "not external buyer demand" in summary_md
