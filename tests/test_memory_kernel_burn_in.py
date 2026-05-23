from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
import pytest

from dharma_swarm.memory_kernel.burn_in import (
    append_burn_in_receipt,
    build_burn_in_receipt,
    canonical_json,
    load_burn_in_status,
)


def test_burn_in_status_blocks_missing_stale_and_failing_receipts(tmp_path: Path) -> None:
    path = tmp_path / "burn_in.jsonl"

    missing = load_burn_in_status(path, now=datetime(2026, 5, 16, tzinfo=UTC))

    assert missing.burn_in_ready is False
    assert "burn_in_receipt_log_missing" in missing.blockers

    stale = build_burn_in_receipt(
        strict_readiness_ready=True,
        synthetic_canary_detected=True,
        rollback_available=True,
        context_case_count=3,
        context_case_failure_count=0,
        context_case_hard_failure_count=0,
        shadow_scenario_count=2,
        parity_hard_failure_count=0,
        warning_count=0,
        created_at="2026-05-15T00:00:00Z",
    )
    append_burn_in_receipt(path, stale)

    status = load_burn_in_status(
        path,
        max_age_seconds=60,
        now=datetime(2026, 5, 16, tzinfo=UTC),
    )

    assert status.burn_in_ready is False
    assert "burn_in_latest_receipt_stale" in status.blockers

    fresh = build_burn_in_receipt(
        strict_readiness_ready=True,
        synthetic_canary_detected=True,
        rollback_available=True,
        context_case_count=3,
        context_case_failure_count=0,
        context_case_hard_failure_count=0,
        shadow_scenario_count=2,
        parity_hard_failure_count=0,
        warning_count=0,
        created_at=(datetime(2026, 5, 16, tzinfo=UTC) - timedelta(seconds=5)).isoformat().replace("+00:00", "Z"),
    )
    append_burn_in_receipt(path, fresh)

    ready = load_burn_in_status(
        path,
        max_age_seconds=60,
        now=datetime(2026, 5, 16, tzinfo=UTC),
    )

    assert ready.burn_in_ready is True
    assert ready.synthetic_canary_detected is True
    assert ready.parity_hard_failure_count == 0


def test_burn_in_receipt_blocks_parity_failures() -> None:
    receipt = build_burn_in_receipt(
        strict_readiness_ready=True,
        synthetic_canary_detected=True,
        rollback_available=True,
        context_case_count=3,
        context_case_failure_count=0,
        context_case_hard_failure_count=0,
        shadow_scenario_count=2,
        parity_hard_failure_count=1,
        warning_count=0,
    )

    assert receipt.status == "blocked"
    assert "parity_hard_failures" in receipt.warnings


def test_burn_in_receipt_future_timestamp_blocks_readiness(tmp_path: Path) -> None:
    path = tmp_path / "burn_in.jsonl"
    receipt = build_burn_in_receipt(
        strict_readiness_ready=True,
        synthetic_canary_detected=True,
        rollback_available=True,
        context_case_count=3,
        context_case_failure_count=0,
        context_case_hard_failure_count=0,
        shadow_scenario_count=2,
        parity_hard_failure_count=0,
        warning_count=0,
        created_at="2030-01-01T00:00:00Z",
    )
    append_burn_in_receipt(path, receipt)

    status = load_burn_in_status(path, now=datetime(2026, 5, 16, tzinfo=UTC))

    assert status.burn_in_ready is False
    assert status.latest_age_seconds is not None
    assert status.latest_age_seconds < 0
    assert "burn_in_latest_receipt_from_future" in status.blockers


def test_burn_in_log_rejects_duplicate_id_with_conflicting_digest(tmp_path: Path) -> None:
    path = tmp_path / "burn_in.jsonl"
    first = build_burn_in_receipt(
        strict_readiness_ready=True,
        synthetic_canary_detected=True,
        rollback_available=True,
        context_case_count=3,
        context_case_failure_count=0,
        context_case_hard_failure_count=0,
        shadow_scenario_count=2,
        parity_hard_failure_count=0,
        warning_count=0,
        created_at="2026-05-16T00:00:00Z",
    )
    second = build_burn_in_receipt(
        strict_readiness_ready=True,
        synthetic_canary_detected=True,
        rollback_available=True,
        context_case_count=4,
        context_case_failure_count=0,
        context_case_hard_failure_count=0,
        shadow_scenario_count=2,
        parity_hard_failure_count=0,
        warning_count=0,
        created_at="2026-05-16T00:00:01Z",
    )
    conflicting = replace(second, receipt_id=first.receipt_id)

    append_burn_in_receipt(path, first)
    with pytest.raises(ValueError, match="conflicting immutable receipt"):
        append_burn_in_receipt(path, conflicting)

    path.write_text(
        canonical_json(first.to_json()) + "\n" + canonical_json(conflicting.to_json()) + "\n",
        encoding="utf-8",
    )
    status = load_burn_in_status(path, now=datetime(2026, 5, 16, 0, 0, 2, tzinfo=UTC))

    assert status.immutable_log is False
    assert status.burn_in_ready is False
    assert "burn_in_receipt_log_not_immutable" in status.blockers


def test_burn_in_log_fails_closed_on_malformed_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "burn_in.jsonl"
    receipt = build_burn_in_receipt(
        strict_readiness_ready=True,
        synthetic_canary_detected=True,
        rollback_available=True,
        context_case_count=3,
        context_case_failure_count=0,
        context_case_hard_failure_count=0,
        shadow_scenario_count=2,
        parity_hard_failure_count=0,
        warning_count=0,
        created_at="2026-05-16T00:00:00Z",
    )
    path.write_text(
        "{malformed json}\n" + canonical_json(receipt.to_json()) + "\n",
        encoding="utf-8",
    )

    status = load_burn_in_status(path, now=datetime(2026, 5, 16, 0, 0, 2, tzinfo=UTC))

    assert status.immutable_log is False
    assert status.burn_in_ready is False
    assert "burn_in_receipt_log_not_immutable" in status.blockers
