"""Tests for the GitHub evidence ingestor (G4).

Exercises the full path: run tools/github_ingestor_go against fixture
inputs for all four supported event types, then load the resulting Go
receipts via the Python bridge and assert the typed views round-trip.

All tests are fixture-driven; no live GitHub API.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from dharma_swarm.world_radar.go_invoke import go_toolchain_capable

from dharma_swarm.operator_core.go_github_bridge import (
    GO_EVIDENCE_SCHEMA_V0,
    SUPPORTED_GITHUB_EVENT_TYPES,
    GoGitHubBridgeError,
    GoGitHubReceipt,
    check_run_event,
    commit_event,
    load_go_github_receipt,
    pull_request_event,
    release_event,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "go_github_ingestor"
GO_MODULE = Path(__file__).resolve().parents[1] / "tools" / "github_ingestor_go"
CORRELATION_ID = "corr_v0_test_001"
GO_OBSERVED_AT = "2026-05-09T00:00:00Z"


def _run_ingestor(
    event_type: str,
    fixture_name: str,
    output_path: Path,
    *,
    expect_rejected: bool = False,
) -> None:
    """Drive the Go ingestor against a fixture's payload portion.

    The Go binary takes a payload file (raw JSON), not a full Fixture, so we
    read the input fixture JSON, serialize the payload field, and pass that
    file path to ``--input``. Source URL and correlation are passed via
    flags so the on-the-wire receipt matches what the Go contract tests
    produced.
    """
    if not go_toolchain_capable(GO_MODULE):
        pytest.skip("no Go toolchain satisfying github_ingestor_go/go.mod")
    fixture_raw = json.loads((FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))
    payload_path = output_path.parent / (fixture_name + ".payload")
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(json.dumps(fixture_raw["payload"]), encoding="utf-8")

    env = dict(os.environ)
    env["GOCACHE"] = "/tmp/dharma-swarm-go-build"
    env["GOMODCACHE"] = "/tmp/dharma-swarm-go-mod"
    args = [
        "go", "run", ".",
        "--input", str(payload_path),
        "--output", str(output_path),
        "--event-type", event_type,
        "--source-url", str(fixture_raw["source_url"]),
        "--correlation-id", CORRELATION_ID,
        "--observed-at", GO_OBSERVED_AT,
    ]
    completed = subprocess.run(
        args, cwd=GO_MODULE, env=env, check=False, capture_output=True, text=True,
    )
    if expect_rejected:
        assert output_path.exists(), (
            f"rejected receipt was not written: stderr={completed.stderr}"
        )
        assert "rejected" in completed.stderr, (
            f"expected rejection on stderr, got: {completed.stderr}"
        )
    else:
        if completed.returncode != 0:
            pytest.fail(
                f"ingestor failed for {event_type}: "
                f"stdout={completed.stdout} stderr={completed.stderr}"
            )


# ---------------------------------------------------------------------------
# Acceptance: each event type round-trips Go → JSON → Python view
# ---------------------------------------------------------------------------


def test_pull_request_round_trip(tmp_path: Path) -> None:
    receipt_path = tmp_path / "pr.json"
    _run_ingestor("github_pull_request", "pr_opened.json", receipt_path)
    receipt = load_go_github_receipt(receipt_path)
    assert receipt.source == "github_pull_request"
    assert receipt.status == "accepted"
    assert receipt.schema_version == GO_EVIDENCE_SCHEMA_V0
    assert receipt.correlation_id == CORRELATION_ID
    pr = pull_request_event(receipt)
    assert pr.number == 180
    assert pr.state == "merged"
    assert pr.head_sha == "0bd9c22"
    assert pr.base_sha == "b95708d"
    assert "Receipt SDK" in pr.title or "receipt SDK" in pr.title


def test_commit_round_trip(tmp_path: Path) -> None:
    receipt_path = tmp_path / "commit.json"
    _run_ingestor("github_commit", "commit_pushed.json", receipt_path)
    receipt = load_go_github_receipt(receipt_path)
    assert receipt.source == "github_commit"
    assert receipt.status == "accepted"
    commit = commit_event(receipt)
    assert commit.sha == "0bd9c22"
    assert commit.author == "Dhyana"


def test_check_run_round_trip(tmp_path: Path) -> None:
    receipt_path = tmp_path / "check.json"
    _run_ingestor("github_check_run", "check_run_completed.json", receipt_path)
    receipt = load_go_github_receipt(receipt_path)
    assert receipt.source == "github_check_run"
    assert receipt.status == "accepted"
    check = check_run_event(receipt)
    assert check.id == 75141272343
    assert check.name == "go-evidence-ingestor"
    assert check.status == "completed"


def test_release_round_trip(tmp_path: Path) -> None:
    receipt_path = tmp_path / "release.json"
    _run_ingestor("github_release", "release_published.json", receipt_path)
    receipt = load_go_github_receipt(receipt_path)
    assert receipt.source == "github_release"
    assert receipt.status == "accepted"
    release = release_event(receipt)
    assert release.tag_name == "v0.0.0-go-receipt-sdk"
    assert release.draft is False
    assert release.prerelease is True


# ---------------------------------------------------------------------------
# Determinism: identical inputs to Go produce identical receipts on disk
# ---------------------------------------------------------------------------


def test_ingestor_is_deterministic(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _run_ingestor("github_pull_request", "pr_opened.json", a)
    _run_ingestor("github_pull_request", "pr_opened.json", b)
    assert a.read_bytes() == b.read_bytes()


# ---------------------------------------------------------------------------
# Reject path: missing required field still emits a receipt with reason
# ---------------------------------------------------------------------------


def test_missing_field_emits_rejected_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "rejected.json"
    _run_ingestor(
        "github_pull_request",
        "pr_missing_fields.json",
        receipt_path,
        expect_rejected=True,
    )
    raw = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert raw["status"] == "rejected"
    assert raw["rejected_reason"].startswith("missing_required_fields:")
    # title and base_sha are dropped from the missing-fields fixture
    assert "title" in raw["rejected_reason"]
    assert "base_sha" in raw["rejected_reason"]


# ---------------------------------------------------------------------------
# Bridge invariants
# ---------------------------------------------------------------------------


def test_bridge_rejects_unsupported_schema_version() -> None:
    with pytest.raises(GoGitHubBridgeError):
        GoGitHubReceipt(
            receipt_id="goev_x",
            correlation_id=CORRELATION_ID,
            source="github_pull_request",
            source_url="https://example.invalid/x",
            observed_at=GO_OBSERVED_AT,
            content_hash="sha256:abc",
            event_uid="evt_x",
            schema_version="go_evidence_receipt.v9999",
            status="accepted",
            payload={"number": 1},
        )


def test_bridge_rejects_unsupported_event_type() -> None:
    with pytest.raises(GoGitHubBridgeError):
        GoGitHubReceipt(
            receipt_id="goev_x",
            correlation_id=CORRELATION_ID,
            source="github_workflow_dispatch",  # type: ignore[arg-type]
            source_url="https://example.invalid/x",
            observed_at=GO_OBSERVED_AT,
            content_hash="sha256:abc",
            event_uid="evt_x",
            schema_version=GO_EVIDENCE_SCHEMA_V0,
            status="accepted",
            payload={},
        )


def test_bridge_rejects_rejected_status_without_reason() -> None:
    with pytest.raises(GoGitHubBridgeError):
        GoGitHubReceipt(
            receipt_id="goev_x",
            correlation_id=CORRELATION_ID,
            source="github_pull_request",
            source_url="https://example.invalid/x",
            observed_at=GO_OBSERVED_AT,
            content_hash="sha256:abc",
            event_uid="evt_x",
            schema_version=GO_EVIDENCE_SCHEMA_V0,
            status="rejected",
            payload={},
            # rejected_reason intentionally empty
        )


def test_supported_event_types_set_matches_adapter() -> None:
    # Locks the Python view in step with tools/github_ingestor_go/adapter.go's
    # requiredFields keyset. If the Go adapter adds a new event type, this
    # test should fail until SUPPORTED_GITHUB_EVENT_TYPES is updated.
    assert set(SUPPORTED_GITHUB_EVENT_TYPES) == {
        "github_pull_request",
        "github_commit",
        "github_check_run",
        "github_release",
    }
