"""Recursive-discovery and swarm-integrity Control Surface projections."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.operator_core.control_surface_models import ControlSurfaceRow


def _file_freshness(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(timespec="seconds")
    except OSError:
        return ""


def observe_recursive_discovery_shadow(
    row: ControlSurfaceRow,
    repo_root: Path,
    *,
    event_log_dir: Path | None = None,
) -> None:
    """Project persisted recursive-discovery receipts for a manifest row."""

    try:
        from dharma_swarm.event_log import EventLog
        from dharma_swarm.recursive_discovery import (
            EVENT_STREAM,
            load_recursive_receipts,
            receipt_counts_by_type,
            shadow_fixture_receipts,
        )
    except Exception as exc:
        row.observed_state = "adapter_error"
        row.coherence_state = "drifted"
        row.gap_codes.append("recursive_discovery_adapter_error")
        row.add_evidence(
            "process",
            f"recursive discovery adapter failed: {exc}",
            status="error",
            provenance_chain=["recursive_discovery", "adapter_import"],
        )
        return

    receipt_type = row.raw.get("receipt_type", "")
    row.add_source_ref("file", "dharma_swarm/recursive_discovery.py", exists=True)
    row.freshness = _file_freshness(repo_root / "dharma_swarm" / "recursive_discovery.py")

    event_log = EventLog(event_log_dir) if event_log_dir is not None else EventLog()
    receipts = load_recursive_receipts(event_log)
    matching_receipts = [
        receipt for receipt in receipts if receipt.receipt_type == receipt_type
    ]
    if matching_receipts:
        latest = matching_receipts[-1]
        stream_path = event_log.stream_path(EVENT_STREAM)
        row.add_source_ref("config", str(stream_path), exists=stream_path.exists())
        row.observed_state = f"event_log:{len(matching_receipts)}"
        row.coherence_state = "partial"
        row.gap_codes.append("shadow_only")
        if receipt_type in {"candidate_diff", "promotion_decision"}:
            row.gap_codes.append("human_promotion_required")
        row.raw["event_count"] = len(matching_receipts)
        row.raw["latest_receipt_id"] = latest.receipt_id
        row.raw["latest_candidate_id"] = latest.candidate_id or ""
        row.raw["latest_archive_entry_id"] = latest.metadata.get("archive_entry_id", "")
        row.add_evidence(
            "recursive_receipt",
            (
                f"{receipt_type}: event_log_count={len(matching_receipts)} "
                f"latest={latest.receipt_id}"
            ),
            status="present",
            provenance_chain=["recursive_discovery", "event_log", EVENT_STREAM],
        )
    else:
        fixture_count = receipt_counts_by_type(shadow_fixture_receipts()).get(receipt_type, 0)
        row.raw["fixture_available"] = fixture_count
        row.observed_state = "no_persisted_evidence"
        row.coherence_state = "declared_only"
        row.gap_codes.append("recursive_discovery_evidence_missing")
        row.add_evidence(
            "recursive_receipt",
            f"{receipt_type}: event_count=0 fixture_available={fixture_count}",
            status="missing",
            provenance_chain=["recursive_discovery", "event_log", EVENT_STREAM],
        )


def swarm_integrity_rows(
    repo_root: Path,
    *,
    event_log_dir: Path | None = None,
) -> list[ControlSurfaceRow]:
    """Project the latest Swarm Integrity v0 benchmark report."""

    try:
        from dharma_swarm.event_log import EventLog
        from dharma_swarm.swarm_integrity_benchmark import EVENT_STREAM
    except Exception as exc:
        row = ControlSurfaceRow(
            id="eval.swarm_integrity_v0",
            kind="feedback_loop",
            label="Swarm Integrity v0",
            authority_role="evidence",
            declared_state="benchmark_unavailable",
            desired_state="multi_agent_integrity_eval_visible",
            observed_state="adapter_error",
            coherence_state="drifted",
            priority="p0",
            owner_module="dharma_swarm/swarm_integrity_benchmark.py",
            truth_owner="swarm_integrity",
            gap_codes=["swarm_integrity_adapter_error"],
            next_action="Repair swarm integrity benchmark import",
            raw={"error": str(exc)},
        )
        row.add_source_ref("file", "dharma_swarm/swarm_integrity_benchmark.py", exists=True)
        return [row]

    log = EventLog(event_log_dir) if event_log_dir is not None else EventLog()
    events = log.read_envelopes(stream=EVENT_STREAM)
    report_events = [
        event
        for event in events
        if dict(event.get("payload") or {}).get("action_name")
        == "swarm_integrity.report_recorded"
    ]
    latest = report_events[-1] if report_events else None
    payload = dict(latest.get("payload") or {}) if latest else {}
    passed = str(payload.get("decision") or "") == "passed"
    row = ControlSurfaceRow(
        id="eval.swarm_integrity_v0",
        kind="feedback_loop",
        label="Swarm Integrity v0",
        authority_role="evidence",
        declared_state="deterministic_system_eval",
        desired_state="multi_agent_integrity_eval_visible",
        observed_state=(
            f"latest_report:{payload.get('passed_count', 0)}/{payload.get('case_count', 0)}"
            if latest
            else "no_persisted_evidence"
        ),
        coherence_state=(
            "bound" if latest and passed else "declared_only" if not latest else "partial"
        ),
        priority="p1" if latest and passed else "p0",
        owner_module="dharma_swarm/swarm_integrity_benchmark.py",
        truth_owner="swarm_integrity",
        gap_codes=(
            []
            if latest and passed
            else ["swarm_integrity_evidence_missing"]
            if not latest
            else ["swarm_integrity_failures_present"]
        ),
        next_action="" if latest and passed else "Run Swarm Integrity v0 benchmark",
        raw={
            "stream": EVENT_STREAM,
            "event_count": len(events),
            "report_count": len(report_events),
            "latest_event_id": latest.get("event_id", "") if latest else "",
            "latest_payload": payload,
        },
    )
    row.add_evidence(
        "test",
        f"swarm_integrity reports={len(report_events)} events={len(events)}",
        status="present" if latest else "missing",
        provenance_chain=["swarm_integrity", "event_log", EVENT_STREAM],
    )
    row.add_source_ref("file", "dharma_swarm/swarm_integrity_benchmark.py", exists=True)
    row.add_source_ref(
        "file",
        "tests/test_swarm_integrity_benchmark.py",
        exists=(repo_root / "tests/test_swarm_integrity_benchmark.py").exists(),
    )
    v1_report_events = [
        event
        for event in events
        if dict(event.get("payload") or {}).get("action_name")
        == "swarm_integrity.v1.report_recorded"
    ]
    v1_latest = v1_report_events[-1] if v1_report_events else None
    v1_payload = dict(v1_latest.get("payload") or {}) if v1_latest else {}
    v1_passed = str(v1_payload.get("decision") or "") == "passed"
    v1_row = ControlSurfaceRow(
        id="eval.swarm_integrity_v1",
        kind="feedback_loop",
        label="Swarm Integrity v1",
        authority_role="evidence",
        declared_state="transcript_integrity_eval",
        desired_state="locked_evaluator_transcript_eval_visible",
        observed_state=(
            f"latest_report:{v1_payload.get('passed_count', 0)}/{v1_payload.get('case_count', 0)}"
            if v1_latest
            else "no_persisted_evidence"
        ),
        coherence_state=(
            "bound" if v1_latest and v1_passed else "declared_only" if not v1_latest else "partial"
        ),
        priority="p1" if v1_latest and v1_passed else "p0",
        owner_module="dharma_swarm/swarm_integrity_benchmark.py",
        truth_owner="swarm_integrity",
        gap_codes=(
            []
            if v1_latest and v1_passed
            else ["swarm_integrity_v1_evidence_missing"]
            if not v1_latest
            else ["swarm_integrity_v1_failures_present"]
        ),
        next_action="" if v1_latest and v1_passed else "Run Swarm Integrity v1 benchmark",
        raw={
            "stream": EVENT_STREAM,
            "event_count": len(events),
            "report_count": len(v1_report_events),
            "latest_event_id": v1_latest.get("event_id", "") if v1_latest else "",
            "latest_payload": v1_payload,
        },
    )
    v1_row.add_evidence(
        "test",
        f"swarm_integrity_v1 reports={len(v1_report_events)} events={len(events)}",
        status="present" if v1_latest else "missing",
        provenance_chain=["swarm_integrity_v1", "event_log", EVENT_STREAM],
    )
    v1_row.add_source_ref("file", "dharma_swarm/swarm_integrity_benchmark.py", exists=True)
    v1_row.add_source_ref(
        "file",
        "tests/test_swarm_integrity_benchmark.py",
        exists=(repo_root / "tests/test_swarm_integrity_benchmark.py").exists(),
    )
    return [row, v1_row]
