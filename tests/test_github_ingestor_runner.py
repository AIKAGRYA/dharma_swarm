"""Tests for the go-g04 github_ingestor live trigger (watched-dir runner).

Fixture-driven; no live GitHub API. The happy path drives the REAL Go
ingestor (prebuilt binary or `go run .`), matching the convention in
tests/test_go_github_ingestor_bridge.py; it skips when the host has neither.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from dharma_swarm.world_radar.go_invoke import go_toolchain_capable

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "go_github_ingestor"
MODULE_DIR = REPO_ROOT / "tools" / "github_ingestor_go"

_spec = importlib.util.spec_from_file_location(
    "github_ingestor_runner",
    REPO_ROOT / "scripts" / "runtime" / "github_ingestor_runner.py",
)
runner = importlib.util.module_from_spec(_spec)
sys.modules["github_ingestor_runner"] = runner
_spec.loader.exec_module(runner)


def _require_go_host() -> None:
    if not (MODULE_DIR / MODULE_DIR.name).is_file() and not go_toolchain_capable(
        MODULE_DIR
    ):
        pytest.skip(
            "neither prebuilt github_ingestor_go binary nor a Go toolchain "
            "satisfying the module's go.mod directive"
        )


def _drop_envelope(inbox: Path, name: str, envelope: dict) -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / name
    path.write_text(json.dumps(envelope), encoding="utf-8")
    return path


def test_runner_converts_dropped_payload_into_accepted_receipt(tmp_path: Path) -> None:
    _require_go_host()
    fixture = json.loads((FIXTURE_DIR / "pr_opened.json").read_text(encoding="utf-8"))
    inbox = tmp_path / "inbox"
    receipts = tmp_path / "receipts"
    _drop_envelope(
        inbox,
        "pr_180.json",
        {
            "event_type": "github_pull_request",
            "source_url": fixture["source_url"],
            "correlation_id": "corr_runner_test_001",
            "payload": fixture["payload"],
        },
    )

    summary = runner.process_inbox(inbox_dir=inbox, receipt_dir=receipts)

    assert summary["status"] == "ok"
    assert summary["processed"] == 1
    assert summary["failed"] == 0
    assert summary["invocation_mode"] in {"binary", "go_run"}
    assert len(summary["receipts"]) == 1
    receipt = json.loads(Path(summary["receipts"][0]).read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "go_evidence_receipt.v0"
    assert receipt["status"] == "accepted"
    assert receipt["source"] == "github_pull_request"
    assert receipt["correlation_id"] == "corr_runner_test_001"
    # Envelope moved out of the watched dir.
    assert not (inbox / "pr_180.json").exists()
    assert (inbox / "processed" / "pr_180.json").exists()


def test_runner_quarantines_unsupported_event_type(tmp_path: Path) -> None:
    _require_go_host()
    inbox = tmp_path / "inbox"
    receipts = tmp_path / "receipts"
    _drop_envelope(
        inbox,
        "bad_event.json",
        {"event_type": "github_star", "payload": {"x": 1}},
    )

    summary = runner.process_inbox(inbox_dir=inbox, receipt_dir=receipts)

    assert summary["status"] == "degraded"
    assert summary["processed"] == 0
    assert summary["failed"] == 1
    assert (inbox / "failed" / "bad_event.json").exists()
    assert (inbox / "failed" / "bad_event.error.txt").exists()
    assert "unsupported event_type" in summary["errors"][0]


def test_runner_reports_needs_host_without_binary_or_toolchain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbox = tmp_path / "inbox"
    envelope = _drop_envelope(
        inbox,
        "pr_1.json",
        {"event_type": "github_pull_request", "payload": {"number": 1}},
    )
    fake_module = tmp_path / "github_ingestor_go"
    fake_module.mkdir()
    # No monkeypatch needed: the module has no go.mod, and the version-aware
    # capability helper fails closed on an unreadable directive (WP-0C2),
    # regardless of any toolchain on the host.

    summary = runner.process_inbox(
        inbox_dir=inbox,
        receipt_dir=tmp_path / "receipts",
        module_dir=fake_module,
    )

    assert summary["status"] == "needs_host"
    # Host-aware: payload stays in place for a capable host to pick up.
    assert envelope.exists()


def test_runner_reports_needs_host_when_binary_not_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale, non-executable file named like the binary must NOT count as a
    usable host: _go_invocation() would fall back to `go run .`, so without a
    toolchain the envelope must stay queued (needs_host), never fail/.
    """
    inbox = tmp_path / "inbox"
    envelope = _drop_envelope(
        inbox,
        "pr_1.json",
        {"event_type": "github_pull_request", "payload": {"number": 1}},
    )
    fake_module = tmp_path / "github_ingestor_go"
    fake_module.mkdir()
    # A file with the binary's name but no execute bit (e.g. a stale artifact).
    stale_binary = fake_module / fake_module.name
    stale_binary.write_text("not a real executable\n", encoding="utf-8")
    stale_binary.chmod(0o644)
    # No go.mod in the fake module: the version-aware capability helper fails
    # closed (WP-0C2), so no toolchain monkeypatch is required.

    summary = runner.process_inbox(
        inbox_dir=inbox,
        receipt_dir=tmp_path / "receipts",
        module_dir=fake_module,
    )

    assert summary["status"] == "needs_host"
    # Inbox left intact: nothing quarantined to failed/.
    assert envelope.exists()
    assert not (inbox / "failed").exists()
