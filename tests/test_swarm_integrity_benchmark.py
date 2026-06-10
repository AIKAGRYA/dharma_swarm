from __future__ import annotations

from dharma_swarm.event_log import EventLog
from dharma_swarm.operator_core.control_surface import build_control_surface_rows
from dharma_swarm.recursive_discovery import EVENT_STREAM as RECURSIVE_STREAM
from dharma_swarm.swarm_integrity_benchmark import (
    EVENT_STREAM,
    default_swarm_integrity_cases,
    render_swarm_integrity_markdown,
    run_swarm_integrity_v0,
)


def test_swarm_integrity_v0_blocks_malicious_cases_and_records_events(tmp_path):
    event_log = EventLog(tmp_path / "events")

    report = run_swarm_integrity_v0(
        event_log=event_log,
        session_id="sess-integrity",
    )
    rows = event_log.read_envelopes(stream=EVENT_STREAM)
    recursive_rows = event_log.read_envelopes(stream=RECURSIVE_STREAM)

    malicious_cases = [
        case for case in default_swarm_integrity_cases() if case.failure_mode != "none"
    ]

    assert report.all_passed is True
    assert report.case_count == len(default_swarm_integrity_cases())
    assert report.malicious_case_count == len(malicious_cases)
    assert report.malicious_blocked_or_held_count == len(malicious_cases)
    assert {result.outcome for result in report.results if result.failure_mode != "none"} <= {
        "blocked",
        "hold",
    }
    assert len(rows) == report.case_count + 1
    assert len(recursive_rows) == report.case_count
    assert all(result.recursive_receipt_id for result in report.results)


def test_swarm_integrity_markdown_is_compact_report(tmp_path):
    report = run_swarm_integrity_v0(
        event_log=EventLog(tmp_path / "events"),
        session_id="sess-integrity",
        record_recursive_receipts=False,
    )

    rendered = render_swarm_integrity_markdown(report)

    assert "Swarm Integrity v0" in rendered
    assert "hidden_failed_tests" in rendered
    assert "MASK" not in rendered


def test_control_surface_projects_swarm_integrity_report(tmp_path):
    event_log = EventLog(tmp_path / "events")
    run_swarm_integrity_v0(event_log=event_log, session_id="sess-integrity")

    rows = build_control_surface_rows(
        repo_root=tmp_path,
        event_log_dir=tmp_path / "events",
    )
    row = [candidate for candidate in rows if candidate.id == "eval.swarm_integrity_v0"][0]

    assert row.observed_state == "latest_report:9/9"
    assert row.coherence_state == "bound"
    assert row.gap_codes == []
