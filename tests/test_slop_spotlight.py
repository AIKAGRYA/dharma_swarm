"""Tests for the Sentry Spotlight adapter."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dharma_swarm.slop.adapters.spotlight_adapter import (
    SpotlightProbe,
    _classify_envelope,
    _location_from_envelope,
    _parse_envelope,
    probe_spotlight,
    run_spotlight,
)
from dharma_swarm.slop.models import DetectorFamily, Severity


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    (src / "b.py").write_text("def g():\n    return 1\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def events_dir(tmp_path: Path) -> Path:
    d = tmp_path / "spotlight_events"
    d.mkdir()
    return d


def write_envelope(events_dir: Path, name: str, envelope: dict) -> Path:
    p = events_dir / f"{name}.json"
    p.write_text(json.dumps(envelope), encoding="utf-8")
    return p


class TestProbeSpotlight:
    def test_unreachable_returns_false_with_error(self) -> None:
        probe = probe_spotlight("http://127.0.0.1:1", timeout=0.05)
        assert probe.reachable is False
        assert probe.error is not None

    def test_probe_record_contains_url(self) -> None:
        probe = probe_spotlight("http://127.0.0.1:1", timeout=0.05)
        assert probe.url == "http://127.0.0.1:1"


class TestParseEnvelope:
    def test_parses_single_json_object(self) -> None:
        env = _parse_envelope('{"type": "event", "event_id": "abc"}')
        assert env is not None
        assert env["type"] == "event"

    def test_parses_jsonl_envelope_format(self) -> None:
        raw = (
            '{"sent_at": "x"}\n'
            '{"type": "event", "event_id": "abc"}\n'
            '{"some": "payload"}\n'
        )
        env = _parse_envelope(raw)
        assert env is not None
        assert env.get("event_id") == "abc"

    def test_returns_none_on_invalid(self) -> None:
        assert _parse_envelope("") is None
        assert _parse_envelope("not-json") is None


class TestLocationExtraction:
    def test_in_app_frame_takes_precedence(self, tmp_repo: Path) -> None:
        envelope = {
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "stacktrace": {
                            "frames": [
                                {"filename": "external.py", "lineno": 5, "in_app": False},
                                {"filename": "src/a.py", "lineno": 42, "in_app": True},
                            ]
                        },
                    }
                ]
            }
        }
        loc = _location_from_envelope(envelope, tmp_repo)
        assert loc is not None
        assert loc[0].endswith("a.py")
        assert loc[1] == 42


class TestClassifyEnvelope:
    def test_broad_exception_no_message_flagged(self, tmp_repo: Path) -> None:
        envelope = {
            "type": "event",
            "transaction": "swallow_handler",
            "exception": {
                "values": [
                    {
                        "type": "Exception",
                        "value": "",
                        "stacktrace": {
                            "frames": [
                                {"filename": "src/a.py", "lineno": 1, "in_app": True}
                            ]
                        },
                    }
                ]
            },
        }
        findings = _classify_envelope(envelope, tmp_repo)
        broad = [f for f in findings if f.issue_type == "broad_exception_swallow"]
        assert len(broad) == 1
        assert broad[0].family is DetectorFamily.AI_SLOP
        assert broad[0].severity is Severity.MEDIUM

    def test_typed_exception_with_message_not_flagged(self, tmp_repo: Path) -> None:
        envelope = {
            "type": "event",
            "transaction": "real_handler",
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "bad input",
                        "stacktrace": {
                            "frames": [
                                {"filename": "src/a.py", "lineno": 1, "in_app": True}
                            ]
                        },
                    }
                ]
            },
        }
        findings = _classify_envelope(envelope, tmp_repo)
        broad = [f for f in findings if f.issue_type == "broad_exception_swallow"]
        assert broad == []

    def test_implausible_perf_on_heavy_op_flagged(self, tmp_repo: Path) -> None:
        envelope = {
            "type": "transaction",
            "transaction": "fake_db_query",
            "start_timestamp": 1000.0,
            "timestamp": 1000.0001,
            "spans": [],
            "contexts": {"trace": {"op": "db.query", "location": "src/a.py"}},
        }
        findings = _classify_envelope(envelope, tmp_repo)
        perf = [f for f in findings if f.issue_type == "implausible_perf"]
        assert len(perf) == 1
        assert perf[0].family is DetectorFamily.AI_SLOP

    def test_silent_no_op_transaction_flagged(self, tmp_repo: Path) -> None:
        envelope = {
            "type": "transaction",
            "transaction": "ceremonial_handler",
            "start_timestamp": 1000.0,
            "timestamp": 1000.005,
            "spans": [],
            "contexts": {"trace": {"op": "task", "location": "src/a.py"}},
        }
        findings = _classify_envelope(envelope, tmp_repo)
        silent = [f for f in findings if f.issue_type == "silent_no_op"]
        assert len(silent) == 1
        assert silent[0].family is DetectorFamily.AI_SLOP


class TestRunSpotlight:
    def test_no_envelopes_no_probe_returns_clean(
        self, tmp_repo: Path, events_dir: Path
    ) -> None:
        with patch(
            "dharma_swarm.slop.adapters.spotlight_adapter.probe_spotlight",
            return_value=SpotlightProbe(url="http://x", reachable=False, error="x"),
        ):
            result = run_spotlight(
                [tmp_repo / "src" / "a.py"],
                repo_root=tmp_repo,
                events_dir=events_dir,
            )
        assert result.exit_code == 0
        assert result.findings == []

    def test_no_envelopes_require_envelopes_errors(
        self, tmp_repo: Path, events_dir: Path
    ) -> None:
        with patch(
            "dharma_swarm.slop.adapters.spotlight_adapter.probe_spotlight",
            return_value=SpotlightProbe(url="http://x", reachable=False, error="x"),
        ):
            result = run_spotlight(
                [tmp_repo / "src" / "a.py"],
                repo_root=tmp_repo,
                events_dir=events_dir,
                require_envelopes=True,
            )
        assert result.exit_code == 1
        assert result.error is not None

    def test_envelopes_yield_findings(
        self, tmp_repo: Path, events_dir: Path
    ) -> None:
        write_envelope(
            events_dir,
            "broad_swallow",
            {
                "type": "event",
                "transaction": "swallow",
                "exception": {
                    "values": [
                        {
                            "type": "Exception",
                            "value": "",
                            "stacktrace": {
                                "frames": [
                                    {"filename": "src/a.py", "lineno": 5, "in_app": True}
                                ]
                            },
                        }
                    ]
                },
            },
        )
        with patch(
            "dharma_swarm.slop.adapters.spotlight_adapter.probe_spotlight",
            return_value=SpotlightProbe(url="http://x", reachable=True),
        ):
            result = run_spotlight(
                [tmp_repo / "src" / "a.py"],
                repo_root=tmp_repo,
                events_dir=events_dir,
            )
        assert result.exit_code == 0
        broad = [f for f in result.findings if f.issue_type == "broad_exception_swallow"]
        assert len(broad) == 1

    def test_high_error_rate_finding(
        self, tmp_repo: Path, events_dir: Path
    ) -> None:
        for i in range(5):
            write_envelope(
                events_dir,
                f"err_{i}",
                {
                    "type": "event",
                    "transaction": "f",
                    "exception": {
                        "values": [
                            {
                                "type": "ValueError",
                                "value": "msg",
                                "stacktrace": {
                                    "frames": [
                                        {"filename": "src/a.py", "lineno": 1, "in_app": True}
                                    ]
                                },
                            }
                        ]
                    },
                },
            )
        for i in range(2):
            write_envelope(
                events_dir,
                f"trans_{i}",
                {
                    "type": "transaction",
                    "transaction": "f",
                    "start_timestamp": 1000.0,
                    "timestamp": 1000.5,
                    "spans": [{"op": "x"}],
                    "contexts": {"trace": {"op": "task", "location": "src/a.py"}},
                },
            )
        with patch(
            "dharma_swarm.slop.adapters.spotlight_adapter.probe_spotlight",
            return_value=SpotlightProbe(url="http://x", reachable=True),
        ):
            result = run_spotlight(
                [tmp_repo / "src" / "a.py"],
                repo_root=tmp_repo,
                events_dir=events_dir,
            )
        rates = [f for f in result.findings if f.issue_type == "high_error_rate"]
        assert len(rates) == 1
        assert rates[0].family is DetectorFamily.BEHAVIORAL

    def test_zero_trace_finding_for_unseen_path(
        self, tmp_repo: Path, events_dir: Path
    ) -> None:
        write_envelope(
            events_dir,
            "any_event",
            {
                "type": "event",
                "transaction": "x",
                "exception": {
                    "values": [
                        {
                            "type": "ValueError",
                            "value": "msg",
                            "stacktrace": {
                                "frames": [
                                    {"filename": "src/a.py", "lineno": 3, "in_app": True}
                                ]
                            },
                        }
                    ]
                },
            },
        )
        with patch(
            "dharma_swarm.slop.adapters.spotlight_adapter.probe_spotlight",
            return_value=SpotlightProbe(url="http://x", reachable=True),
        ):
            result = run_spotlight(
                [tmp_repo / "src" / "a.py", tmp_repo / "src" / "b.py"],
                repo_root=tmp_repo,
                events_dir=events_dir,
            )
        zero_traces = [f for f in result.findings if f.issue_type == "zero_trace"]
        zero_paths = {f.path for f in zero_traces}
        assert any("b.py" in p for p in zero_paths)
        assert not any("a.py" in p for p in zero_paths)
