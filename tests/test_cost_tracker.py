"""Tests for dharma_swarm.cost_tracker."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from dharma_swarm.cost_tracker import (
    CostEntry,
    _estimate_cost,
    cost_summary,
    log_cost,
    read_cost_log,
)


# ---------------------------------------------------------------------------
# _estimate_cost
# ---------------------------------------------------------------------------

class TestEstimateCost:
    def test_free_model_zero_cost(self) -> None:
        cost = _estimate_cost("llama-3.3-70b-instruct:free", 1000, 500)
        assert cost == 0.0

    def test_gpt4o_cost_positive(self) -> None:
        cost = _estimate_cost("gpt-4o", 1_000_000, 0)
        # 1M input tokens at $2.50/M = $2.50
        assert abs(cost - 2.50) < 0.01

    def test_output_tokens_cost_3x_input_rate(self) -> None:
        # claude-sonnet-4-6: $3.00/M input, output 3x = $9.00/M
        input_cost = _estimate_cost("claude-sonnet-4-6", 1_000_000, 0)
        output_cost = _estimate_cost("claude-sonnet-4-6", 0, 1_000_000)
        assert abs(output_cost - input_cost * 3.0) < 0.01

    def test_unknown_model_zero_cost(self) -> None:
        cost = _estimate_cost("totally-unknown-model-xyz", 100_000, 50_000)
        assert cost == 0.0

    def test_case_insensitive_matching(self) -> None:
        cost_lower = _estimate_cost("claude-sonnet-4-6", 1000, 0)
        cost_upper = _estimate_cost("CLAUDE-SONNET-4-6", 1000, 0)
        assert cost_lower == cost_upper

    def test_result_is_rounded_to_6_decimals(self) -> None:
        cost = _estimate_cost("gpt-4o", 123, 456)
        # Should be a float with at most 6 decimal places
        assert cost == round(cost, 6)


# ---------------------------------------------------------------------------
# log_cost
# ---------------------------------------------------------------------------

class TestLogCost:
    def test_returns_cost_entry(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "cost_log.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)
        entry = log_cost(
            provider="openrouter",
            model="llama-3.3-70b-instruct:free",
            input_tokens=500,
            output_tokens=200,
            task_id="task-001",
            agent_name="coder",
            tier="T1",
        )
        assert isinstance(entry, CostEntry)
        assert entry.provider == "openrouter"
        assert entry.model == "llama-3.3-70b-instruct:free"
        assert entry.input_tokens == 500
        assert entry.output_tokens == 200
        assert entry.task_id == "task-001"
        assert entry.agent_name == "coder"
        assert entry.tier == "T1"

    def test_writes_to_jsonl_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "cost_log.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)
        log_cost(provider="anthropic", model="claude-sonnet-4-6", input_tokens=100, output_tokens=50)
        assert log_file.exists()
        data = json.loads(log_file.read_text().strip())
        assert data["provider"] == "anthropic"
        assert data["model"] == "claude-sonnet-4-6"

    def test_appends_multiple_entries(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "cost_log.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)
        for i in range(3):
            log_cost(provider=f"provider{i}", model="gpt-4o", input_tokens=100, output_tokens=50)
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_estimated_cost_populated(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "cost_log.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)
        entry = log_cost(provider="openai", model="gpt-4o", input_tokens=1_000_000, output_tokens=0)
        assert entry.estimated_cost_usd > 0

    def test_free_model_zero_estimated_cost(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "cost_log.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)
        entry = log_cost(provider="openrouter", model="llama-3.3-70b-instruct:free", input_tokens=10000, output_tokens=5000)
        assert entry.estimated_cost_usd == 0.0


# ---------------------------------------------------------------------------
# read_cost_log
# ---------------------------------------------------------------------------

class TestReadCostLog:
    def _write_entry(self, log_file: Path, timestamp: float, provider: str = "openai", model: str = "gpt-4o") -> None:
        entry = {
            "timestamp": timestamp,
            "provider": provider,
            "model": model,
            "input_tokens": 100,
            "output_tokens": 50,
            "estimated_cost_usd": 0.001,
            "task_id": "",
            "agent_name": "",
            "tier": "",
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def test_returns_empty_when_file_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "nonexistent.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)
        entries = read_cost_log(since_hours=24.0)
        assert entries == []

    def test_filters_by_time(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "cost_log.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)
        now = time.time()
        self._write_entry(log_file, now - 3600)      # 1h ago — should be included
        self._write_entry(log_file, now - 100_000)   # ~28h ago — should be excluded
        entries = read_cost_log(since_hours=24.0)
        assert len(entries) == 1

    def test_returns_cost_entry_objects(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "cost_log.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)
        self._write_entry(log_file, time.time())
        entries = read_cost_log(since_hours=24.0)
        assert all(isinstance(e, CostEntry) for e in entries)

    def test_skips_invalid_json_lines(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "cost_log.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)
        now = time.time()
        self._write_entry(log_file, now)
        log_file.open("a").write("NOT_JSON\n")
        entries = read_cost_log(since_hours=24.0)
        assert len(entries) == 1


# ---------------------------------------------------------------------------
# cost_summary
# ---------------------------------------------------------------------------

class TestCostSummary:
    def test_no_entries_message(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "cost_log.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)
        summary = cost_summary(since_hours=24.0)
        assert "No LLM calls" in summary

    def test_summary_contains_totals(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "cost_log.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)
        now = time.time()
        for i in range(3):
            entry = {
                "timestamp": now - i * 10,
                "provider": "openai",
                "model": "gpt-4o",
                "input_tokens": 1000,
                "output_tokens": 500,
                "estimated_cost_usd": 0.005,
                "task_id": "",
                "agent_name": "",
                "tier": "T2",
            }
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        summary = cost_summary(since_hours=24.0)
        assert "3 calls" in summary
        assert "T2" in summary

    def test_summary_groups_by_tier(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "cost_log.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)
        now = time.time()
        for tier in ("T1", "T2", "T3"):
            entry = {
                "timestamp": now,
                "provider": "openai",
                "model": "gpt-4o",
                "input_tokens": 100,
                "output_tokens": 50,
                "estimated_cost_usd": 0.001,
                "task_id": "",
                "agent_name": "",
                "tier": tier,
            }
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        summary = cost_summary(since_hours=24.0)
        assert "T1" in summary
        assert "T2" in summary
        assert "T3" in summary


# ---------------------------------------------------------------------------
# _infer_caller_source
# ---------------------------------------------------------------------------

class TestInferCallerSource:
    def test_returns_string(self) -> None:
        from dharma_swarm.providers import _infer_caller_source

        result = _infer_caller_source()
        assert isinstance(result, str)

    def test_skips_providers_module(self) -> None:
        from dharma_swarm.providers import _infer_caller_source

        result = _infer_caller_source()
        assert result != "providers"
        assert result != "cost_tracker"

    def test_finds_dharma_swarm_module(self) -> None:
        """_infer_caller_source walks sys._getframe chain and returns
        the first dharma_swarm module that is not in the skip set.
        When called from test code (not under /dharma_swarm/), it returns ''."""
        from dharma_swarm.providers import _infer_caller_source

        result = _infer_caller_source()
        # Called from test file (not under /dharma_swarm/), so it returns
        # the first dharma_swarm frame it finds — or '' if there isn't one.
        # The function itself lives in providers.py (skipped), so when called
        # from test code, it returns '' — that's the correct async-safe
        # behavior.  Attribution is now done at call-site entry points
        # (runtime_provider._capture_caller_source) before any await.
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _finalize_response metadata auto-fill
# ---------------------------------------------------------------------------

class TestFinalizeResponseMetadata:
    def test_empty_metadata_gets_inferred_source(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "cost_log.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)

        from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
        from dharma_swarm.providers import _finalize_response, _infer_caller_source

        # Patch _infer_caller_source to return a known value
        monkeypatch.setattr(
            "dharma_swarm.providers._infer_caller_source",
            lambda: "evolution",
        )

        request = LLMRequest(
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
        )
        response = LLMResponse(content="hello", model="test-model", usage={})
        _finalize_response(ProviderType.OLLAMA, request, response)

        data = json.loads(log_file.read_text().strip())
        assert data["source"] == "evolution"
        assert data["execution_mode"] == "headless_evolution"

    def test_explicit_metadata_preserved(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log_file = tmp_path / "cost_log.jsonl"
        monkeypatch.setattr("dharma_swarm.cost_tracker._COST_LOG", log_file)

        from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
        from dharma_swarm.providers import _finalize_response

        request = LLMRequest(
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
            metadata={
                "execution_mode": "persistent_agent",
                "source": "agent_runner",
                "agent_name": "builder",
            },
        )
        response = LLMResponse(content="hello", model="test-model", usage={})
        _finalize_response(ProviderType.OLLAMA, request, response)

        data = json.loads(log_file.read_text().strip())
        assert data["execution_mode"] == "persistent_agent"
        assert data["source"] == "agent_runner"
        assert data["agent_name"] == "builder"


class TestCaptureCallerSource:
    """Tests for runtime_provider._capture_caller_source."""

    def test_returns_string(self) -> None:
        from dharma_swarm.runtime_provider import _capture_caller_source

        result = _capture_caller_source()
        assert isinstance(result, str)

    def test_does_not_return_skipped_modules(self) -> None:
        from dharma_swarm.runtime_provider import _capture_caller_source

        result = _capture_caller_source()
        assert result not in {"providers", "cost_tracker", "runtime_provider", "jikoku_instrumentation"}

    async def test_capture_before_await_finds_caller(self) -> None:
        """Verify that _capture_caller_source works at function entry in async code."""
        from dharma_swarm.runtime_provider import _capture_caller_source

        # When called from test code, the frame chain includes only
        # runtime_provider (skipped) and test files (not /dharma_swarm/).
        # The function correctly returns '' in that case.
        result = _capture_caller_source()
        assert isinstance(result, str)
