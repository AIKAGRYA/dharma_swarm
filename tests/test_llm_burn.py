from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.llm_burn import (
    load_llm_burn_rollup,
    rollup_llm_usage,
    span_from_trace_cost_ledger,
    span_from_trace_row,
)


def test_trace_row_normalizes_to_openinference_style_attributes() -> None:
    span = span_from_trace_row(
        {
            "trace_id": "trace-1",
            "span_id": "span-1",
            "kind": "llm_call",
            "status": "ok",
            "end_time": "2026-05-09T00:00:00+00:00",
            "duration_ms": 12.5,
            "attributes": {
                "model": "gpt-4.1",
                "prompt_tokens": 1000,
                "completion_tokens": 500,
            },
        }
    )

    assert span is not None
    assert span.cost_source == "estimated"
    assert span.estimated_cost_usd == 0.005
    attrs = span.to_openinference_attributes()
    assert attrs["openinference.span.kind"] == "LLM"
    assert attrs["llm.model_name"] == "gpt-4.1"
    assert attrs["llm.token_count.prompt"] == 1000
    assert attrs["llm.token_count.completion"] == 500
    assert attrs["llm.cost.usd"] == 0.005
    assert attrs["dharma.cost_source"] == "estimated"


def test_actual_cost_wins_over_recorded_estimate() -> None:
    span = span_from_trace_cost_ledger(
        {
            "timestamp": "2026-05-09T00:00:00+00:00",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "prompt_tokens": 1000,
            "completion_tokens": 1000,
            "actual_cost_usd": 0.12,
            "cost_usd": 0.018,
        }
    )

    assert span is not None
    assert span.cost_source == "logged"
    assert span.logged_cost_usd == 0.12
    assert span.estimated_cost_usd == 0.0
    assert span.effective_cost_usd == 0.12


def test_rollup_counts_errors_and_unpriced_zero_token_spans() -> None:
    priced = span_from_trace_row(
        {
            "trace_id": "trace-1",
            "span_id": "span-1",
            "kind": "llm_call",
            "status": "ok",
            "attributes": {"provider": "openai", "model": "gpt-4o", "prompt_tokens": 10},
        }
    )
    failed_zero = span_from_trace_row(
        {
            "trace_id": "trace-2",
            "span_id": "span-2",
            "kind": "agent_dispatch",
            "status": "error",
            "attributes": {"error": "provider failed"},
        }
    )

    rollup = rollup_llm_usage([span for span in (priced, failed_zero) if span is not None])

    assert rollup.spans == 2
    assert rollup.error_spans == 1
    assert rollup.zero_token_spans == 1
    assert rollup.unpriced_spans == 1
    assert rollup.top_failure_provider == "unknown=1"
    assert rollup.by_cost_source["zero_tokens"] == 1


def test_load_llm_burn_rollup_reads_existing_dharma_jsonl_shapes(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    traces = state / "traces"
    traces.mkdir(parents=True)
    now = datetime(2026, 5, 9, 1, tzinfo=timezone.utc)
    (state / "cost_log.jsonl").write_text(
        json.dumps(
            {
                "timestamp": now.timestamp(),
                "provider": "openai",
                "model": "gpt-4o",
                "input_tokens": 100,
                "output_tokens": 50,
                "estimated_cost_usd": 0.000625,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (traces / "cost_ledger.jsonl").write_text(
        json.dumps(
            {
                "timestamp": now.isoformat(),
                "provider": "ollama",
                "model": "glm-5",
                "prompt_tokens": 200,
                "completion_tokens": 300,
                "cost_usd": 0.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (traces / "traces_2026-05-09.jsonl").write_text(
        json.dumps(
            {
                "trace_id": "trace-1",
                "span_id": "span-1",
                "kind": "agent_dispatch",
                "status": "error",
                "end_time": now.isoformat(),
                "attributes": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-6",
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "cost_usd": 0.00033,
                    "success": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rollup = load_llm_burn_rollup(state, now=now, since_hours=24)

    assert rollup.spans == 3
    assert rollup.error_spans == 1
    assert rollup.by_source == {
        "cost_log": 1,
        "trace_cost_ledger": 1,
        "trace_dispatch": 1,
    }
    assert rollup.by_cost_source["recorded_estimate"] == 2
    assert rollup.by_cost_source["free_provider"] == 1
