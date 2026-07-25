from __future__ import annotations

import json
import subprocess
from pathlib import Path

from dharma_swarm.world_radar import go_bridge as bridge
from dharma_swarm.world_radar import go_invoke


def test_world_radar_promotes_operator_drop_with_fake_ingestor(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / ".dharma"
    _write_jsonl(
        state / "meta" / "world_operator_drops.jsonl",
        [_signal("operator_drop", score=0.86)],
    )
    monkeypatch.setattr(bridge, "_run_go_ingestor", _fake_ingestor)

    result = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=False)

    assert result.ok is True
    assert result.promotion_ready == 1
    inbox = _read_jsonl(state / "meta" / "world_zeitgeist_inbox.jsonl")
    assert inbox[0]["source"] == "world_zeitgeist"
    assert "first_principles_questions" in inbox[0]["metadata"]


def test_world_radar_incubates_single_source_and_writes_rnd(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / ".dharma"
    _write_jsonl(
        state / "meta" / "world_radar_observations.jsonl",
        [_signal("hacker_news", score=0.72)],
    )
    monkeypatch.setattr(bridge, "_run_go_ingestor", _fake_ingestor)

    result = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=False)

    assert result.ok is True
    assert result.promotion_ready == 0
    assert result.incubations_written >= 4
    board = json.loads((state / "meta" / "world_signal_board.json").read_text())
    assert board["movements"][0]["status"] == "incubating"
    assert list((state / "meta" / "world_radar" / "incubations").glob("*/evolve.md"))
    assert (state / "meta" / "world_radar" / "world_radar_health.json").exists()


def test_world_radar_cascade_can_promote_after_second_source(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / ".dharma"

    def fake_scout(**kwargs):
        if kwargs.get("cascade_for"):
            return [_signal("github", score=0.74)], None, {"successful_sources": 1, "failed_sources": 0}
        return [_signal("hacker_news", score=0.72)], None, {"successful_sources": 1, "failed_sources": 0}

    monkeypatch.setattr(bridge, "_run_go_scout", fake_scout)
    monkeypatch.setattr(bridge, "_run_go_ingestor", _fake_ingestor)

    result = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=True)

    assert result.ok is True
    assert result.promotion_ready == 1
    health = json.loads((state / "meta" / "world_radar" / "world_radar_health.json").read_text())
    assert health["successful_sources"] == 2


def test_world_radar_source_weights_feedback_persists(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / ".dharma"
    meta = state / "meta"
    meta.mkdir(parents=True)
    (meta / "opportunity_board.json").write_text(
        json.dumps(
            [
                {
                    "source_inputs": [{"raw_source": "github"}],
                    "realized_outcomes": [{"success": True}],
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bridge, "_run_go_ingestor", _fake_ingestor)

    result = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=False)
    second = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=False)

    assert result.ok is True
    assert second.ok is True
    weights = json.loads((meta / "world_radar" / "source_weights.json").read_text())
    assert weights["github"] == 0.89
    health = json.loads((meta / "world_radar" / "world_radar_health.json").read_text())
    assert health["feedback_events_applied"] == 0
    ledger = json.loads((meta / "world_radar" / "source_feedback_ledger.json").read_text())
    assert len(ledger["applied_event_ids"]) == 1


def test_no_fetch_pass_preserves_prior_radar_raw_observations(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / ".dharma"
    raw_path = state / "meta" / "world_radar" / "raw_observations.jsonl"
    _write_jsonl(
        raw_path,
        [
            _signal("hacker_news", score=0.72),
            _signal("github", score=0.74),
        ],
    )
    monkeypatch.setattr(bridge, "_run_go_ingestor", _fake_ingestor)

    result = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=False)

    assert result.ok is True
    assert result.raw_observations == 2
    assert len(_read_jsonl(raw_path)) == 2
    assert result.promotion_ready == 1



def test_run_go_scout_plumbs_archive_flags(monkeypatch, tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    output_path = tmp_path / "observations.jsonl"
    health_path = tmp_path / "health.json"
    archive_dir = tmp_path / "archive"
    url_file = tmp_path / "urls.txt"
    url_file.write_text("https://cofounder.co/how-to/start\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(cmd, cwd, capture_output, text, timeout):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        _write_jsonl(output_path, [_signal("cofounder", score=0.91)])
        health_path.write_text(
            json.dumps(
                {
                    "successful_sources": 1,
                    "failed_sources": 0,
                    "archive_enabled": True,
                    "archive_count": 2,
                    "dedupe_count": 0,
                    "archive_dir": str(archive_dir),
                    "archive_index_path": str(archive_dir / "archive_index.jsonl"),
                    "archive_replay_index_path": str(archive_dir / "replay_index.json"),
                    "archive_manifest_path": str(archive_dir / "manifest.json"),
                    "archive_discovered_count": 3,
                    "archive_workers": 8,
                    "archive_total_bytes": 1234,
                    "archive_clean_text_count": 2,
                    "archive_clean_text_bytes": 987,
                    "archive_error_count": 1,
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    # Host-independent: pretend a Go toolchain is on PATH so the toolchain-checked
    # _go_invocation() offers `go run .` even on hosts without Go installed.
    monkeypatch.setattr(go_invoke, "go_toolchain_capable", lambda *_a, **_k: True)  # WP-0C2: capability, not presence

    rows, error, counts = bridge._run_go_scout(
        state=state,
        output_path=output_path,
        health_path=health_path,
        timeout_s=30,
        archive=True,
        archive_dir=archive_dir,
        archive_urls=["https://cofounder.co/how-to/start"],
        archive_url_files=[str(url_file)],
        archive_source_specs=[str(tmp_path / "sourcespec.json")],
        archive_max_bytes=123_456,
        archive_max_pages=4,
        archive_max_depth=0,
        archive_same_domain=False,
        archive_rate_limit_ms=250,
        archive_robots=False,
        archive_default_crawl_delay_ms=75,
        archive_max_retries=3,
        archive_retry_base_delay_ms=11,
        archive_retry_max_delay_ms=99,
        archive_max_fetch_duration_ms=1234,
        archive_exclude=["app.cofounder.co"],
        archive_workers=8,
        archive_discover_llms=True,
        archive_discover_sitemap=True,
        archive_sitemap_max_urls=25,
    )

    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert error is None
    assert rows[0]["source"] == "cofounder"
    assert counts["archive_enabled"] is True
    assert counts["archive_count"] == 2
    assert counts["archive_index_path"] == str(archive_dir / "archive_index.jsonl")
    assert counts["archive_replay_index_path"] == str(archive_dir / "replay_index.json")
    assert counts["archive_discovered_count"] == 3
    assert counts["archive_workers"] == 8
    assert counts["archive_total_bytes"] == 1234
    assert counts["archive_clean_text_count"] == 2
    assert counts["archive_clean_text_bytes"] == 987
    assert counts["archive_error_count"] == 1
    assert "--archive" in cmd
    assert "--archive-discover-llms" in cmd
    assert "--archive-discover-sitemap" in cmd
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-workers"] == ["8"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-sitemap-max-urls"] == ["25"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-max-bytes"] == ["123456"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-rate-limit-ms"] == ["250"]
    assert "--archive-same-domain=false" in cmd
    assert "--archive-robots=false" in cmd
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-default-crawl-delay-ms"] == ["75"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-max-retries"] == ["3"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-retry-base-delay-ms"] == ["11"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-retry-max-delay-ms"] == ["99"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--archive-max-fetch-duration-ms"] == ["1234"]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--query-url"] == [
        "https://cofounder.co/how-to/start"
    ]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--query-url-file"] == [str(url_file)]
    assert [cmd[idx + 1] for idx, item in enumerate(cmd) if item == "--source-spec"] == [str(tmp_path / "sourcespec.json")]
    assert "app.cofounder.co" in cmd


def test_run_go_scout_treats_partial_source_failure_as_nonfatal(monkeypatch, tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    output_path = tmp_path / "observations.jsonl"
    health_path = tmp_path / "health.json"

    def fake_run(cmd, cwd, capture_output, text, timeout):  # type: ignore[no-untyped-def]
        _write_jsonl(output_path, [_signal("github", score=0.74)])
        health_path.write_text(
            json.dumps(
                {
                    "successful_sources": 1,
                    "failed_sources": 1,
                    "errors": ["arxiv_agentic_design_patterns: 429"],
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    # Host-independent: pretend a Go toolchain is on PATH so the toolchain-checked
    # _go_invocation() offers `go run .` even on hosts without Go installed.
    monkeypatch.setattr(go_invoke, "go_toolchain_capable", lambda *_a, **_k: True)  # WP-0C2: capability, not presence

    rows, error, counts = bridge._run_go_scout(
        state=state,
        output_path=output_path,
        health_path=health_path,
        timeout_s=30,
    )

    assert error is None
    assert rows[0]["source"] == "github"
    assert counts["successful_sources"] == 1
    assert counts["failed_sources"] == 1


def test_partial_source_error_still_reports_total_source_failure() -> None:
    error = bridge._partial_source_error(
        {
            "successful_sources": 0,
            "failed_sources": 2,
            "errors": ["arxiv: 429", "hn: 503"],
        }
    )

    assert error is not None
    assert "partial source failures=2" in error


def test_partial_source_error_never_raises_on_malformed_health() -> None:
    # Copilot review finding: a non-numeric health field must not crash the
    # scout -- health parsing is advisory, never fatal.
    error = bridge._partial_source_error(
        {"successful_sources": "not-a-number", "failed_sources": None, "errors": "not-a-list"}
    )
    assert error is None  # failed coerces to 0 -> failed <= 0 -> no error


def test_source_counts_never_raises_on_malformed_health() -> None:
    counts = bridge._source_counts(
        {
            "successful_sources": "N/A",
            "failed_sources": [],
            "retry_count": {},
            "archive_count": "inf",
            "dedupe_count": "-1",
        }
    )
    assert counts["successful_sources"] == 0
    assert counts["failed_sources"] == 0
    assert counts["retry_count"] == 0
    assert counts["archive_count"] == 0
    assert counts["dedupe_count"] == 0


def test_world_radar_imports_go_archive_rows_as_untrusted_evidence(monkeypatch, tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    clean = archive_dir / "clean.txt"
    clean.write_text("Agent bounty public evidence with $50 payment signal.", encoding="utf-8")
    body = archive_dir / "body.html"
    body.write_text("<html><body>raw</body></html>", encoding="utf-8")
    receipt = archive_dir / "receipt.json"
    receipt.write_text(json.dumps({"receipt_id": "goarch_1", "run_id": "archive-run-1"}), encoding="utf-8")
    index = archive_dir / "archive_index.jsonl"
    _write_jsonl(
        index,
        [
            {
                "run_id": "archive-run-1",
                "source_spec_id": "cashclaw-public-github",
                "url": "https://github.com/example/repo/issues/1",
                "canonical_url": "https://github.com/example/repo/issues/1",
                "final_canonical_url": "https://github.com/example/repo/issues/1",
                "title": "Agent bounty public evidence",
                "source_kind": "html",
                "content_hash": "sha256:" + "a" * 64,
                "capture_status": "captured",
                "body_path": str(body),
                "receipt_path": str(receipt),
                "clean_text_path": str(clean),
                "robots_decision": "allowed",
            }
        ],
    )

    def fake_scout(**_kwargs):  # type: ignore[no-untyped-def]
        return [], None, {
            "successful_sources": 1,
            "failed_sources": 0,
            "archive_enabled": True,
            "archive_count": 1,
            "archive_index_path": str(index),
            "archive_replay_index_path": str(archive_dir / "replay_index.json"),
            "archive_manifest_path": str(archive_dir / "manifest.json"),
            "archive_clean_text_count": 1,
            "archive_clean_text_bytes": clean.stat().st_size,
        }

    monkeypatch.setattr(bridge, "_run_go_scout", fake_scout)
    monkeypatch.setattr(bridge, "_run_go_ingestor", _fake_ingestor)

    result = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=True, scout_archive=True)

    assert result.ok is True
    assert result.archive_enabled is True
    assert result.archive_clean_text_count == 1
    raw_rows = _read_jsonl(state / "meta" / "world_radar" / "raw_observations.jsonl")
    archive_rows = [row for row in raw_rows if row.get("source") == "go_archive"]
    assert len(archive_rows) == 1
    metadata = archive_rows[0]["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["trust_state"] == "untrusted_capture"
    assert metadata["authority"] == "evidence_only"
    assert metadata["no_external_action"] is True
    assert metadata["receipt_path"] == str(receipt)


def test_run_go_ingestor_projects_current_run_receipts(monkeypatch, tmp_path: Path) -> None:
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "signals.jsonl"
    receipt_dir = tmp_path / "receipts"
    _write_jsonl(input_path, [_signal("operator_drop", score=0.86)])
    captured: dict[str, object] = {}

    def fake_run(cmd, cwd, capture_output, text, timeout):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        corr = str(cmd[cmd.index("--correlation-id") + 1])
        out_dir = Path(cmd[cmd.index("--receipt-dir") + 1])
        out_dir.mkdir(parents=True)
        _write_jsonl(output_path, [_signal("operator_drop", score=0.86)])
        (out_dir / "goev_world_signal.json").write_text(
            json.dumps(
                {
                    "receipt_id": "goev_world_signal",
                    "correlation_id": corr,
                    "source": "world_signal",
                    "source_url": "https://example.com/operator_drop",
                    "observed_at": "2026-05-09T00:00:00Z",
                    "content_hash": "sha256:" + "a" * 64,
                    "event_uid": "evt_world_signal",
                    "schema_version": "go_evidence_receipt.v0",
                    "status": "accepted",
                    "payload": {
                        "id": "sig-operator",
                        "source": "world_scout",
                        "raw_source": "operator_drop",
                        "source_type": "operator_drop",
                        "category": "company",
                        "title": "SubQ managed agent runtime",
                        "description": "Managed agent execution infrastructure signal.",
                        "relevance_score": 0.86,
                        "url": "https://example.com/operator_drop",
                        "keywords": ["agentic", "runtime"],
                        "observed_at": "2026-05-09T00:00:00Z",
                        "metadata": {"movement_key": "subq managed agent runtime"},
                    },
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    # Host-independent: pretend a Go toolchain is on PATH so the toolchain-checked
    # _go_invocation() offers `go run .` even on hosts without Go installed.
    monkeypatch.setattr(go_invoke, "go_toolchain_capable", lambda *_a, **_k: True)  # WP-0C2: capability, not presence

    rows, error, invocation_mode = bridge._run_go_ingestor(
        input_path=input_path,
        output_path=output_path,
        min_score=0.45,
        timeout_s=30,
        receipt_dir=receipt_dir,
        correlation_id="corr-current-run",
    )

    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert error is None
    assert invocation_mode in {"binary", "go_run"}
    assert "--receipt-dir" in cmd
    assert "--correlation-id" in cmd
    assert rows[0]["source"] == "go_world_signal_receipt"
    assert rows[0]["metadata"]["correlation_id"] == "corr-current-run"
    assert rows[0]["metadata"]["raw_source"] == "operator_drop"


def test_world_radar_writes_ingest_summary_and_cost_event(monkeypatch, tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    _write_jsonl(
        state / "meta" / "world_operator_drops.jsonl",
        [_signal("operator_drop", score=0.86)],
    )
    monkeypatch.setattr(bridge, "_run_go_ingestor", _fake_ingestor)

    result = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=False)

    summary_path = state / "meta" / "world_radar" / "ingest_run_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert result.ingest_run_id == summary["run_id"]
    assert result.ingest_summary_path == str(summary_path)
    assert summary["schema_version"] == "world_radar_go_ingest_summary.v1"
    assert summary["raw_count"] == 1
    assert summary["signal_count"] == 1
    assert summary["accepted_count"] == 1
    assert summary["rejected_count"] == 0
    assert summary["retry_count"] == 0
    assert summary["byte_count"] > 0
    assert summary["provisional_compute_units"] >= 1
    assert summary["cost_model"] == "neutral_compute_unit_v0_no_usd"
    assert summary["nats_receipt_transport"]["status"] == "disabled"

    cost_rows = _read_jsonl(state / "meta" / "world_radar" / "ingest_cost_ledger.jsonl")
    assert len(cost_rows) == 1
    assert cost_rows[0]["schema_version"] == "world_radar_ingest_cost_event.v1"
    assert cost_rows[0]["idempotency_key"] == result.ingest_run_id
    assert cost_rows[0]["amount"] == summary["provisional_compute_units"]
    assert cost_rows[0]["cost_usd"] == 0.0

    health = json.loads((state / "meta" / "world_radar" / "world_radar_health.json").read_text(encoding="utf-8"))
    assert health["ingest_summary_path"] == str(summary_path)
    assert health["ingest_cost_ledger_path"] == str(state / "meta" / "world_radar" / "ingest_cost_ledger.jsonl")
    assert health["nats_receipt_transport"]["status"] == "disabled"


def test_go_invocation_prefers_prebuilt_binary(monkeypatch, tmp_path: Path) -> None:
    module_dir = tmp_path / "world_scout_go"
    module_dir.mkdir()

    # No binary + toolchain on PATH -> `go run .` (host-independent via patch).
    monkeypatch.setattr(go_invoke, "go_toolchain_capable", lambda *_a, **_k: True)  # WP-0C2: capability, not presence
    cmd, mode = bridge._go_invocation(module_dir)
    assert cmd == ["go", "run", "."]
    assert mode == "go_run"

    binary = module_dir / "world_scout_go"
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)

    cmd, mode = bridge._go_invocation(module_dir)
    assert cmd == [str(binary)]
    assert mode == "binary"


def test_go_invocation_needs_host_without_binary_or_toolchain(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Toolchain-checked invocation: neither binary nor `go` -> needs_host, no argv."""
    module_dir = tmp_path / "world_scout_go"
    module_dir.mkdir()
    monkeypatch.setattr(go_invoke.shutil, "which", lambda _cmd: None)

    cmd, mode = bridge._go_invocation(module_dir)
    assert cmd == []
    assert mode == "needs_host"


def test_run_go_scout_needs_host_returns_structured_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """needs_host never invokes a subprocess and names the fix (`make go-build`)."""
    monkeypatch.setattr(
        go_invoke, "_go_invocation", lambda _module_dir: ([], "needs_host")
    )

    def _no_subprocess(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("subprocess must not run when the host lacks Go")

    monkeypatch.setattr(go_invoke.subprocess, "run", _no_subprocess)

    rows, error, counts = bridge._run_go_scout(
        state=tmp_path / ".dharma",
        output_path=tmp_path / "observations.jsonl",
        health_path=tmp_path / "health.json",
        timeout_s=5,
    )

    assert rows == []
    assert error is not None
    assert "make go-build" in error
    assert "world_scout_go" in error
    assert counts["invocation_mode"] == "needs_host"
    assert counts["source_errors"] == [
        {"source": "world_scout_go", "stage": "scout", "error": error}
    ]


def test_run_go_ingestor_needs_host_returns_structured_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        go_invoke, "_go_invocation", lambda _module_dir: ([], "needs_host")
    )

    def _no_subprocess(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("subprocess must not run when the host lacks Go")

    monkeypatch.setattr(go_invoke.subprocess, "run", _no_subprocess)

    rows, error, invocation_mode = bridge._run_go_ingestor(
        input_path=tmp_path / "observations.jsonl",
        output_path=tmp_path / "signals.jsonl",
        min_score=0.4,
        timeout_s=5,
    )

    assert rows == []
    assert error is not None
    assert "make go-build" in error
    assert "world_signal_ingestor_go" in error
    assert invocation_mode == "needs_host"


def test_run_go_scout_surfaces_structured_source_errors_and_mode(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "observations.jsonl"
    health_path = tmp_path / "health.json"

    def fake_run(cmd, cwd, capture_output, text, timeout):  # type: ignore[no-untyped-def]
        _write_jsonl(output_path, [_signal("hacker_news_ai", score=0.7)])
        health_path.write_text(
            json.dumps(
                {
                    "successful_sources": 1,
                    "failed_sources": 2,
                    "errors": [
                        "arxiv_agents: fetch https://export.arxiv.org: 503",
                        "some free-form failure text",
                    ],
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    # Host-independent: pretend a Go toolchain is on PATH so the toolchain-checked
    # _go_invocation() offers `go run .` even on hosts without Go installed.
    monkeypatch.setattr(go_invoke, "go_toolchain_capable", lambda *_a, **_k: True)  # WP-0C2: capability, not presence

    rows, error, counts = bridge._run_go_scout(
        state=tmp_path / ".dharma",
        output_path=output_path,
        health_path=health_path,
        timeout_s=30,
    )

    assert rows[0]["source"] == "hacker_news_ai"
    # Merged semantics (origin/main): the flat error string fires only when
    # ALL sources fail; partial failures surface via structured source_errors.
    assert error is None
    assert counts["invocation_mode"] in {"binary", "go_run"}
    assert counts["source_errors"] == [
        {
            "source": "arxiv_agents",
            "stage": "scout",
            "error": "fetch https://export.arxiv.org: 503",
        },
        {
            "source": "world_scout_go",
            "stage": "scout",
            "error": "some free-form failure text",
        },
    ]


def test_world_radar_surfaces_source_errors_in_result_and_health(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / ".dharma"

    def fake_scout(**kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("cascade_for"):
            return [], None, {"successful_sources": 1, "failed_sources": 0}
        return (
            [_signal("hacker_news", score=0.72)],
            "world_scout_go partial source failures=1: arxiv_agents: 503",
            {
                "successful_sources": 1,
                "failed_sources": 1,
                "invocation_mode": "go_run",
                "source_errors": [
                    {"source": "arxiv_agents", "stage": "scout", "error": "503"}
                ],
            },
        )

    monkeypatch.setattr(bridge, "_run_go_scout", fake_scout)
    monkeypatch.setattr(bridge, "_run_go_ingestor", _fake_ingestor)

    result = bridge.run_world_radar_go_once(state_dir=state, scout_fetch=True)

    assert result.ok is False
    assert result.scout_invocation_mode == "go_run"
    assert result.ingestor_invocation_mode == "go_run"
    assert result.source_errors == (
        {"source": "arxiv_agents", "stage": "scout", "error": "503"},
    )
    health = json.loads(
        (state / "meta" / "world_radar" / "world_radar_health.json").read_text(encoding="utf-8")
    )
    assert health["source_errors"] == [
        {"source": "arxiv_agents", "stage": "scout", "error": "503"}
    ]
    assert health["scout_invocation_mode"] == "go_run"
    assert health["ingestor_invocation_mode"] == "go_run"
    health_md = (state / "meta" / "world_radar" / "world_radar_health.md").read_text(
        encoding="utf-8"
    )
    assert "arxiv_agents" in health_md
    assert "scout_invocation_mode: go_run" in health_md


def test_record_ingest_cost_event_is_idempotent(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ingest_cost_ledger.jsonl"
    summary = {
        "run_id": "run-fixed",
        "correlation_id": "run-fixed",
        "provisional_compute_units": 7,
        "source_count": 2,
        "raw_count": 3,
        "signal_count": 1,
        "accepted_count": 1,
        "rejected_count": 0,
        "retry_count": 1,
        "byte_count": 123,
        "receipt_dir": str(tmp_path / "receipts"),
        "summary_path": str(tmp_path / "summary.json"),
    }

    first = bridge._record_ingest_cost_event(ledger_path, summary)
    second = bridge._record_ingest_cost_event(ledger_path, summary)

    rows = _read_jsonl(ledger_path)
    assert first is True
    assert second is False
    assert len(rows) == 1
    assert rows[0]["event_id"] == "world_radar_ingest_cost:run-fixed"
    assert rows[0]["amount"] == 7


def _fake_ingestor(
    *,
    input_path: Path,
    output_path: Path,
    min_score: float,
    timeout_s: int,
    receipt_dir: Path | None = None,
    correlation_id: str = "",
) -> tuple[list[dict[str, object]], None, str]:
    rows = [
        row
        for row in _read_jsonl(input_path)
        if float(row.get("relevance_score", 0.0) or 0.0) >= min_score
    ]
    _write_jsonl(output_path, rows)
    return rows, None, "go_run"


def _signal(source: str, *, score: float) -> dict[str, object]:
    return {
        "id": f"{source}-subq",
        "source": source,
        "source_type": source,
        "category": "company",
        "title": "SubQ managed agent runtime",
        "description": "Managed agent execution infrastructure signal.",
        "relevance_score": score,
        "keywords": ["agentic", "runtime"],
        "url": f"https://example.com/{source}",
        "metadata": {"movement_key": "subq managed agent runtime"},
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
