"""Tests for the capped, automated deep sweep.

All tests inject scout_fn/dispatch_fn -- nothing here touches the real Go
scout binary or the real `claude` CLI.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm.knowledge_ops.deep_sweep import _headless_invoker, run_deep_sweep
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
async def test_headless_invoker_marks_claude_error_prefix_failed(monkeypatch) -> None:
    monkeypatch.setattr(
        "dharma_swarm.knowledge_ops.deep_sweep.run_claude_headless",
        lambda *_args, **_kwargs: "Error (rc=1): Credit balance is too low",
    )
    receipt = await _headless_invoker(
        task={"id": "verify", "prompt": "verify"},
        agent_id="signal_deep_sweep",
        context_id="ctx",
        routing=RoutingDecision(
            agent_id="signal_deep_sweep",
            provider="claude_code",
            model="",
            reason="test",
            router_name="test",
            context_id="ctx",
            task_id="verify",
        ),
    )

    assert receipt.status == "failed"
    assert receipt.error_source == "provider_failed"
    assert "Credit balance" in str(receipt.error_detail)


@pytest.mark.asyncio
async def test_headless_invoker_requests_keyless_subscription_lane(monkeypatch) -> None:
    # Codex review finding: run_claude_headless's own default (bare=True)
    # fast-fails without ANTHROPIC_API_KEY, defeating the keyless
    # claude_code/subscription lane this module is documented to use.
    seen_kwargs: dict[str, object] = {}

    def fake_run_claude_headless(*args, **kwargs):
        seen_kwargs.update(kwargs)
        return "confirmed_real: ok"

    monkeypatch.setattr(
        "dharma_swarm.knowledge_ops.deep_sweep.run_claude_headless",
        fake_run_claude_headless,
    )
    await _headless_invoker(
        task={"id": "verify", "prompt": "verify"},
        agent_id="signal_deep_sweep",
        context_id="ctx",
        routing=RoutingDecision(agent_id="signal_deep_sweep", provider="claude_code", model=""),
    )
    assert seen_kwargs["bare"] is False


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
    assert result["verification_backlog_count"] > 0


@pytest.mark.asyncio
async def test_scout_error_does_not_crash_the_cycle(tmp_path: Path) -> None:
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=10,
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
async def test_failed_verification_leaves_movement_eligible_for_retry(tmp_path: Path) -> None:
    # Codex review finding: a movement whose verification failed/timed out
    # must NOT be persisted into the window as "seen" -- otherwise a rerun
    # sees newly_seen_count == 0 and never retries it.
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=2),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_failed_receipt,
    )
    assert result["movements_count"] == 2
    assert result["failed_verification_count"] == 2
    window = load_theme_window(tmp_path / "meta" / "world_radar" / "theme_window.json")
    assert len(window) == 0  # nothing succeeded, so nothing is "seen" yet

    result2 = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=2),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_ok,
    )
    assert result2["newly_seen_count"] == 2  # both still eligible for retry
    assert result2["verifications_count"] == 2


@pytest.mark.asyncio
async def test_missing_verdict_leaves_movement_eligible_for_retry(tmp_path: Path) -> None:
    # Codex review finding: a dispatch-level success (status="ok") whose
    # output never names a required verdict token must not be treated as a
    # real verification -- otherwise malformed/empty model output permanently
    # suppresses the claim.
    async def dispatch_fn(prompt, *, context_id, task_id, reason, timeout=300):
        return EvidenceReceipt(
            context_id=context_id,
            task_id=task_id,
            agent_id="signal_deep_sweep",
            provider="claude_code",
            status="ok",
            attributes={"output_text": "I'm not sure, let me think about this differently."},
        )

    result = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=2),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=dispatch_fn,
    )
    assert result["failed_verification_count"] == 2
    window = load_theme_window(tmp_path / "meta" / "world_radar" / "theme_window.json")
    assert len(window) == 0


@pytest.mark.asyncio
async def test_verification_prompt_includes_movement_primary_url(tmp_path: Path) -> None:
    # Codex review finding: movements carry a concrete primary_url from
    # arxiv/GitHub/Reddit/HN -- dropping it left the verifier guessing at an
    # artifact from title/summary text alone.
    seen_prompts: list[str] = []

    async def dispatch_fn(prompt, *, context_id, task_id, reason, timeout=300):
        if task_id != "synthesis":
            seen_prompts.append(prompt)
        return await _fake_dispatch_ok(prompt, context_id=context_id, task_id=task_id, reason=reason, timeout=timeout)

    await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=1),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=dispatch_fn,
    )
    assert seen_prompts
    assert "https://example.com/paper-0" in seen_prompts[0]


@pytest.mark.asyncio
async def test_failed_synthesis_receipt_is_surfaced_not_written_as_digest(tmp_path: Path) -> None:
    async def dispatch_fn(prompt, *, context_id, task_id, reason, timeout=300):
        if task_id == "synthesis":
            return EvidenceReceipt(
                context_id=context_id,
                task_id=task_id,
                agent_id="signal_deep_sweep",
                provider="claude_code",
                status="failed",
                attributes={"output_text": "Error (rc=1): synthesis provider failed"},
            )
        return await _fake_dispatch_ok(prompt, context_id=context_id, task_id=task_id, reason=reason, timeout=timeout)

    result = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=3),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=dispatch_fn,
    )

    assert result["synthesis_error"] == "Error (rc=1): synthesis provider failed"
    assert Path(result["digest_path"]).read_text(encoding="utf-8") == ""


@pytest.mark.asyncio
async def test_likely_fabricated_count_is_surfaced(tmp_path: Path) -> None:
    async def dispatch_fn(prompt, *, context_id, task_id, reason, timeout=300):
        return EvidenceReceipt(
            context_id=context_id,
            task_id=task_id,
            agent_id="signal_deep_sweep",
            provider="claude_code",
            status="ok",
            attributes={"output_text": "LIKELY_FABRICATED: no corroboration anywhere."},
        )

    result = await run_deep_sweep(
        tmp_path,
        max_verifications=10,
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
        max_verifications=10,
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
        max_verifications=10,
        scout_fn=_fake_scout_ok(n_rows=3),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_ok,
    )
    assert result2["newly_seen_count"] == 0
    assert result2["verifications_count"] == 0


@pytest.mark.asyncio
async def test_capped_new_themes_remain_eligible_next_cycle(tmp_path: Path) -> None:
    result = await run_deep_sweep(
        tmp_path,
        max_verifications=1,
        scout_fn=_fake_scout_ok(n_rows=4),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_ok,
    )
    assert result["verifications_count"] == 1
    assert result["verification_backlog_count"] > 0

    result2 = await run_deep_sweep(
        tmp_path,
        max_verifications=10,
        scout_fn=_fake_scout_ok(n_rows=4),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_ok,
    )
    assert result2["newly_seen_count"] == result["verification_backlog_count"]
    assert result2["verifications_count"] == result["verification_backlog_count"]


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
        max_verifications=10,
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


@pytest.mark.asyncio
async def test_state_dir_is_resolved_before_writes(tmp_path: Path) -> None:
    aliased_state = tmp_path / "nested" / ".."
    result = await run_deep_sweep(
        aliased_state,
        max_verifications=1,
        scout_fn=_fake_scout_ok(n_rows=2),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_ok,
    )

    cycle_dir = Path(result["cycle_dir"])
    assert cycle_dir.is_relative_to(tmp_path.resolve() / "meta")
    assert ".." not in cycle_dir.parts


@pytest.mark.asyncio
async def test_context_ids_are_collision_resistant(tmp_path: Path) -> None:
    result1 = await run_deep_sweep(
        tmp_path,
        max_verifications=0,
        scout_fn=_fake_scout_ok(n_rows=1),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_ok,
    )
    result2 = await run_deep_sweep(
        tmp_path,
        max_verifications=0,
        scout_fn=_fake_scout_ok(n_rows=1),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=_fake_dispatch_ok,
    )

    assert result1["context_id"] != result2["context_id"]
    assert Path(result1["cycle_dir"]) != Path(result2["cycle_dir"])


@pytest.mark.asyncio
async def test_successful_empty_ingest_yields_no_candidates(tmp_path: Path) -> None:
    # Codex review finding: `ingested_rows or scout_rows` resurrected raw,
    # unscored scout rows as verification candidates even when the ingestor
    # legitimately accepted zero of them. A successful empty ingest must
    # produce zero movements, not a fallback to raw scout data.
    def ingest_rejects_everything(*, input_path, output_path, min_score, timeout_s, receipt_dir=None, correlation_id=""):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("", encoding="utf-8")
        return [], None  # success, zero accepted rows

    result = await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=3),
        ingest_fn=ingest_rejects_everything,
        dispatch_fn=_fake_dispatch_ok,
    )
    assert result["ingest_error"] is None
    assert result["movements_count"] == 0
    assert result["verifications_count"] == 0


@pytest.mark.asyncio
async def test_synthesis_prompt_receives_theme_window_occurrence_counts(tmp_path: Path) -> None:
    # Codex review finding: the synthesis prompt asks the model to flag
    # high-occurrence recurring themes, but build_world_signal_board's
    # movements never carry occurrence_count -- only the theme window does.
    seen_prompts: list[str] = []

    async def dispatch_fn(prompt, *, context_id, task_id, reason, timeout=300):
        if task_id == "synthesis":
            seen_prompts.append(prompt)
        return await _fake_dispatch_ok(prompt, context_id=context_id, task_id=task_id, reason=reason, timeout=timeout)

    await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=2),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=dispatch_fn,
    )
    # Second cycle: the same movements now recur, so occurrence_count > 1.
    await run_deep_sweep(
        tmp_path,
        max_verifications=2,
        scout_fn=_fake_scout_ok(n_rows=2),
        ingest_fn=_fake_ingest_ok,
        dispatch_fn=dispatch_fn,
    )
    assert len(seen_prompts) == 2
    assert '"occurrence_count": 2' in seen_prompts[1]
