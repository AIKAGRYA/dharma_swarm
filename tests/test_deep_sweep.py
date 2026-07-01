"""Tests for the capped, automated deep sweep.

All tests inject scout_fn/dispatch_fn -- nothing here touches the real Go
scout binary or the real `claude` CLI.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm.knowledge_ops.deep_sweep import run_deep_sweep
from dharma_swarm.spine.receipt import EvidenceReceipt
from dharma_swarm.spine.routing import RoutingDecision


def _fake_scout_rows(n: int) -> list[dict[str, object]]:
    return [
        {
            "id": f"obs-{i}",
            "source": "arxiv",
            "source_type": "arxiv",
            "title": f"Some Real Paper Title Number {i}",
            "url": f"https://example.com/paper-{i}",
            "keywords": ["agentic", "test"],
        }
        for i in range(n)
    ]


def _fake_scout_ok(n_rows: int = 3):
    def scout_fn(*, state, output_path, health_path, timeout_s, beats=False):
        return _fake_scout_rows(n_rows), None, {"successful_sources": 5, "failed_sources": 0}

    return scout_fn


def _fake_scout_error():
    def scout_fn(*, state, output_path, health_path, timeout_s, beats=False):
        return [], "scout could not start", {}

    return scout_fn


async def _fake_dispatch_ok(prompt, *, context_id, task_id, reason, timeout=300):
    text = "confirmed_real: this claim checks out against a real, fetchable artifact."
    if "fabricated_theme" in prompt:
        text = "likely_fabricated: no independent corroboration found for this claim."
    return EvidenceReceipt(
        context_id=context_id,
        task_id=task_id,
        agent_id="signal_deep_sweep",
        provider="claude_code",
        status="ok",
        attributes={"output_text": text},
    )


async def _fake_dispatch_raises(prompt, *, context_id, task_id, reason, timeout=300):
    raise RuntimeError("simulated dispatch failure")


@pytest.mark.asyncio
async def test_deep_sweep_end_to_end_with_fakes(tmp_path: Path) -> None:
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=5),
        dispatch_fn=_fake_dispatch_ok,
    )
    assert result["movements_count"] > 0
    assert result["verifications_count"] == 2  # respects the cap even with 5 movements
    assert result["scout_error"] is None
    assert Path(result["digest_path"]).exists()
    assert Path(result["cycle_dir"]).exists()

    # Never writes anywhere except under the state dir's meta/ tree.
    cycle_dir = Path(result["cycle_dir"])
    assert str(tmp_path) in str(cycle_dir)
    assert "meta" in cycle_dir.parts


@pytest.mark.asyncio
async def test_cap_is_respected_even_with_many_movements(tmp_path: Path) -> None:
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=3,
        scout_fn=_fake_scout_ok(n_rows=50),
        dispatch_fn=_fake_dispatch_ok,
    )
    assert result["movements_count"] >= 3
    assert result["verifications_count"] == 3


@pytest.mark.asyncio
async def test_zero_max_verifications_skips_verification_entirely(tmp_path: Path) -> None:
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=0,
        scout_fn=_fake_scout_ok(n_rows=5),
        dispatch_fn=_fake_dispatch_ok,
    )
    assert result["verifications_count"] == 0


@pytest.mark.asyncio
async def test_scout_error_does_not_crash_the_cycle(tmp_path: Path) -> None:
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_error(),
        dispatch_fn=_fake_dispatch_ok,
    )
    assert result["scout_error"] == "scout could not start"
    assert result["movements_count"] == 0
    assert result["verifications_count"] == 0
    # Still writes a (empty-content) cycle dir, never raises.
    assert Path(result["cycle_dir"]).exists()


@pytest.mark.asyncio
async def test_verification_dispatch_failure_is_recorded_not_raised(tmp_path: Path) -> None:
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=3),
        dispatch_fn=_fake_dispatch_raises,
    )
    assert result["verification_error"] is not None
    assert result["verifications_count"] == 2  # failures are still recorded as entries
    verifications = json.loads((Path(result["cycle_dir"]) / "verifications.json").read_text())
    assert all(v["status"] == "failed" for v in verifications)


@pytest.mark.asyncio
async def test_likely_fabricated_count_is_surfaced(tmp_path: Path) -> None:
    async def dispatch_fn(prompt, *, context_id, task_id, reason, timeout=300):
        return EvidenceReceipt(
            context_id=context_id,
            task_id=task_id,
            agent_id="signal_deep_sweep",
            provider="claude_code",
            status="ok",
            attributes={"output_text": "likely_fabricated: no corroboration anywhere."},
        )

    result = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=3),
        dispatch_fn=dispatch_fn,
    )
    assert result["likely_fabricated_count"] == result["verifications_count"]


@pytest.mark.asyncio
async def test_writes_only_under_state_dir_never_reports_directory(tmp_path: Path) -> None:
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=1,
        scout_fn=_fake_scout_ok(n_rows=2),
        dispatch_fn=_fake_dispatch_ok,
    )
    cycle_dir = Path(result["cycle_dir"])
    assert cycle_dir.is_relative_to(tmp_path / "meta")
    assert "reports" not in cycle_dir.parts
