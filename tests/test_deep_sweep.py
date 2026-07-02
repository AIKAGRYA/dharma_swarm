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
from dharma_swarm.world_radar.theme_window import load_theme_window


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


def _fake_ingest_ok(*, input_path, output_path, min_score, timeout_s, receipt_dir=None, correlation_id=""):
    rows = []
    for index, line in enumerate(Path(input_path).read_text(encoding="utf-8").splitlines()):
        row = json.loads(line)
        row["relevance_score"] = round(max(0.1, 0.95 - index * 0.05), 3)
        row.setdefault("category", "research")
        row.setdefault("description", row.get("title", ""))
        rows.append(row)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return rows, None


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


async def _fake_dispatch_failed_receipt(prompt, *, context_id, task_id, reason, timeout=300):
    return EvidenceReceipt(
        context_id=context_id,
        task_id=task_id,
        agent_id="signal_deep_sweep",
        provider="claude_code",
        status="failed",
        attributes={"output_text": "ERROR: simulated provider failure"},
    )


@pytest.mark.asyncio
async def test_deep_sweep_end_to_end_with_fakes(tmp_path: Path) -> None:
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=5),
        ingest_fn=_fake_ingest_ok,
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
        ingest_fn=_fake_ingest_ok,
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
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_ok,
    )
    assert result["verifications_count"] == 0


@pytest.mark.asyncio
async def test_scout_error_does_not_crash_the_cycle(tmp_path: Path) -> None:
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_error(),
        ingest_fn=_fake_ingest_ok,
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
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_raises,
    )
    assert result["verification_error"] is not None
    assert result["verifications_count"] == 2  # failures are still recorded as entries
    verifications = json.loads((Path(result["cycle_dir"]) / "verifications.json").read_text())
    assert all(v["status"] == "failed" for v in verifications)


@pytest.mark.asyncio
async def test_failed_verification_receipts_are_surfaced(tmp_path: Path) -> None:
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=3),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_failed_receipt,
    )
    assert result["failed_verification_count"] == 2
    assert result["verification_error"] == "2 verification receipt(s) failed or timed out"


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
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=dispatch_fn,
    )
    assert result["likely_fabricated_count"] == result["verifications_count"]


@pytest.mark.asyncio
async def test_own_movements_are_persisted_into_the_theme_window(tmp_path: Path) -> None:
    # Regression for a real bug (Greptile review, PR #738): the theme window
    # must be updated from THIS cycle's own beat-derived movements, not from
    # meta/world_signal_board.json (the separate, hourly world_scout job's
    # file -- reading that here would silently track the wrong job's
    # movements, or nothing if world_scout hasn't run recently).
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=3),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_ok,
    )
    window_path = tmp_path / "meta" / "world_radar" / "theme_window.json"
    assert window_path.exists()
    window = load_theme_window(window_path)
    assert len(window) == result["movements_count"] > 0

    # A second cycle must recognize the SAME movements as recurring, not new.
    result2 = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=3),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_ok,
    )
    assert result2["newly_seen_count"] == 0
    assert result2["verifications_count"] == 0


@pytest.mark.asyncio
async def test_theme_window_ignores_unrelated_world_scout_board(tmp_path: Path) -> None:
    # Even if the hourly world_scout job already wrote its own (unrelated)
    # board.json, the deep sweep's theme window must reflect ITS OWN
    # movements, not silently adopt world_scout's.
    meta = tmp_path / "meta"
    meta.mkdir(parents=True)
    (meta / "world_signal_board.json").write_text(
        json.dumps({"movements": [{"movement_id": "unrelated-from-world-scout", "title": "X", "weighted_score": 0.9}]}),
        encoding="utf-8",
    )
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=3),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_ok,
    )
    window = load_theme_window(tmp_path / "meta" / "world_radar" / "theme_window.json")
    assert "unrelated-from-world-scout" not in window
    assert len(window) == result["movements_count"]


@pytest.mark.asyncio
async def test_writes_only_under_state_dir_never_reports_directory(tmp_path: Path) -> None:
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=1,
        scout_fn=_fake_scout_ok(n_rows=2),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_ok,
    )
    cycle_dir = Path(result["cycle_dir"])
    assert cycle_dir.is_relative_to(tmp_path / "meta")
    assert "reports" not in cycle_dir.parts
