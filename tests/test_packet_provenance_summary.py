from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.packet_provenance_summary import (
    load_events,
    render_markdown,
    summarize_events,
)


def _event(
    *,
    valid: bool,
    required_count: int,
    bypass_reason: bool = False,
    reason: str | None = None,
    source: str = "local-witness",
) -> dict[str, object]:
    uncovered = []
    if reason:
        uncovered.append(
            {
                "path": "docs/governance/PROMPT_GOVERNANCE.md",
                "required": True,
                "reason": reason,
                "bypass_allowed": False,
            }
        )
    return {
        "valid": valid,
        "message": "test",
        "source": source,
        "required_count": required_count,
        "bypass_reason": bypass_reason,
        "missing_packet_ids": [],
        "requirements": [],
        "uncovered_required_files": uncovered,
    }


def test_summarize_events_counts_rejections_and_bypasses() -> None:
    events = [
        _event(valid=True, required_count=0),
        _event(valid=True, required_count=1, bypass_reason=True),
        _event(valid=False, required_count=1, reason="hot_or_governance_path"),
        _event(valid=False, required_count=1, reason="risky_source_cleanup_or_refactor"),
    ]

    summary = summarize_events(events)

    assert summary["total_events"] == 4
    assert summary["valid_events"] == 2
    assert summary["invalid_events"] == 2
    assert summary["packet_required_events"] == 3
    assert summary["bypass_events"] == 1
    assert summary["bypass_override_events"] == 1
    assert summary["level2_rejections"] == 1
    assert summary["level1_rejections"] == 1
    assert summary["uncovered_by_reason"] == {
        "hot_or_governance_path": 1,
        "risky_source_cleanup_or_refactor": 1,
    }


def test_load_events_reads_witness_jsonl_and_ci_artifacts(tmp_path: Path) -> None:
    witness = tmp_path / "packet_provenance.jsonl"
    ci_dir = tmp_path / "ci"
    ci_dir.mkdir()
    witness.write_text(json.dumps(_event(valid=True, required_count=0)) + "\n", encoding="utf-8")
    (ci_dir / "abc.json").write_text(
        json.dumps(_event(valid=False, required_count=1, source="ci-artifact")),
        encoding="utf-8",
    )

    events = load_events(witness_jsonl=witness, ci_report_dir=ci_dir)

    assert len(events) == 2
    assert {event["source"] for event in events} == {"local-witness", "ci-artifact"}


def test_render_markdown_handles_empty_summary() -> None:
    text = render_markdown(summarize_events([]))

    assert "# Packet Provenance Calibration" in text
    assert "No packet-provenance evidence has been recorded yet." in text
