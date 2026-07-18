"""Tests for Go world-radar receipt projection.

The Go side emits receipts only. Python parses those sidecar receipts and
projects accepted world-signal evidence into existing world-feed rows.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from dharma_swarm.world_radar.go_invoke import go_toolchain_capable

from dharma_swarm.operator_core.control_surface import _go_world_receipt_summary_rows
from dharma_swarm.operator_core.world_radar.receipt_bridge import (
    GO_EVIDENCE_SCHEMA_V0,
    GoWorldBridgeError,
    load_go_world_receipt,
    project_world_signal_receipts,
    summarize_go_world_receipts,
    world_feed_row_from_signal_receipt,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "go_world_signal_ingestor"
GO_MODULE = Path(__file__).resolve().parents[1] / "tools" / "world_signal_ingestor_go"
GO_OBSERVED_AT = "2026-05-12T00:00:00Z"


def _run_ingestor(
    event_type: str,
    fixture_name: str,
    output_path: Path,
    *,
    expect_rejected: bool = False,
) -> None:
    if not go_toolchain_capable(GO_MODULE):
        pytest.skip("no Go toolchain satisfying world_signal_ingestor_go/go.mod")
    fixture_raw = json.loads((FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))
    payload_path = output_path.parent / (fixture_name + ".payload")
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    if "payload_text" in fixture_raw:
        payload_path.write_text(str(fixture_raw["payload_text"]), encoding="utf-8")
    else:
        payload_path.write_text(json.dumps(fixture_raw["payload"]), encoding="utf-8")

    env = dict(os.environ)
    env["GOCACHE"] = "/tmp/dharma-swarm-go-build"
    env["GOMODCACHE"] = "/tmp/dharma-swarm-go-mod"
    completed = subprocess.run(
        [
            "go",
            "run",
            ".",
            "--input",
            str(payload_path),
            "--output",
            str(output_path),
            "--event-type",
            event_type,
            "--source-url",
            str(fixture_raw["source_url"]),
            "--correlation-id",
            str(fixture_raw["correlation_id"]),
            "--observed-at",
            GO_OBSERVED_AT,
        ],
        cwd=GO_MODULE,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if expect_rejected:
        assert output_path.exists(), (
            f"rejected receipt was not written: stderr={completed.stderr}"
        )
        assert "rejected" in completed.stderr
    elif completed.returncode != 0:
        pytest.fail(
            f"world ingestor failed for {event_type}: "
            f"stdout={completed.stdout} stderr={completed.stderr}"
        )


def test_world_signal_receipt_round_trips_to_world_feed_row(tmp_path: Path) -> None:
    receipt_path = tmp_path / "world_signal.json"
    _run_ingestor("world_signal", "world_signal.json", receipt_path)

    receipt = load_go_world_receipt(receipt_path)
    assert receipt.source == "world_signal"
    assert receipt.status == "accepted"
    assert receipt.schema_version == GO_EVIDENCE_SCHEMA_V0

    row = world_feed_row_from_signal_receipt(receipt)
    assert row["id"] == receipt.event_uid
    assert row["source"] == "go_world_signal_receipt"
    assert row["category"] == "model_release"
    assert row["relevance_score"] == 0.91
    assert row["metadata"]["receipt_id"] == receipt.receipt_id
    assert "claim_verification" in row["metadata"]["strategic_moves"]


def test_rejected_world_receipt_is_loaded_with_reason(tmp_path: Path) -> None:
    receipt_path = tmp_path / "bad_score.json"
    _run_ingestor(
        "world_signal",
        "bad_score.json",
        receipt_path,
        expect_rejected=True,
    )

    receipt = load_go_world_receipt(receipt_path)
    assert receipt.status == "rejected"
    assert receipt.rejected_reason == "invalid_field_type:relevance_score"
    with pytest.raises(GoWorldBridgeError):
        world_feed_row_from_signal_receipt(receipt)


def test_summary_counts_world_receipts_and_projection(tmp_path: Path) -> None:
    receipts_dir = tmp_path / "receipts"
    _run_ingestor("world_raw_observation", "raw_observation.json", receipts_dir / "raw.json")
    _run_ingestor("world_signal", "world_signal.json", receipts_dir / "signal.json")
    _run_ingestor("world_scout_health", "scout_health.json", receipts_dir / "health.json")
    _run_ingestor(
        "world_signal",
        "bad_score.json",
        receipts_dir / "bad_score.json",
        expect_rejected=True,
    )

    summary = summarize_go_world_receipts(receipts_dir)
    assert summary["total"] == 4
    assert summary["accepted"] == 3
    assert summary["rejected"] == 1
    assert summary["world_raw_observation"] == 1
    assert summary["world_signal"] == 2
    assert summary["world_scout_health"] == 1
    assert summary["projected_world_signals"] == 1
    assert summary["rejected_reasons"] == {
        "invalid_field_type:relevance_score": 1,
    }

    rows = project_world_signal_receipts(tuple(receipts_dir.glob("*.json")))
    assert len(rows) == 1
    assert rows[0]["title"].startswith("SubQ claims")


def test_control_surface_projects_world_receipt_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_dir = tmp_path / ".dharma"
    receipts_dir = state_dir / "go_receipts" / "world"
    _run_ingestor("world_signal", "world_signal.json", receipts_dir / "signal.json")
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state_dir))

    rows = _go_world_receipt_summary_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row.id == "go.world_signal_receipts"
    assert row.observed_state == "receipts accepted"
    assert row.coherence_state == "bound"
    assert row.freshness == GO_OBSERVED_AT
    assert row.raw["projected_world_signals"] == 1
