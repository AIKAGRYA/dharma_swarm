"""Tests for the around-the-clock cycle: compounding seed selection + idle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from dharma_swarm.foundry.campaign_cycle import best_prior_artifact


def _mint(root: Path, target_id: str, metric: float, diff: str) -> None:
    sha = hashlib.sha256(diff.encode("utf-8")).hexdigest()
    (root / "artifacts").mkdir(parents=True, exist_ok=True)
    (root / "receipts").mkdir(parents=True, exist_ok=True)
    (root / "artifacts" / f"{sha}.patch").write_text(diff, encoding="utf-8")
    (root / "receipts" / f"{target_id}-{metric}.json").write_text(json.dumps({
        "target_id": target_id,
        "benchmark": {"candidate_metric": metric},
        "disclosure": {"diff_sha256": sha},
    }), encoding="utf-8")


def test_best_prior_artifact_selects_highest_metric(tmp_path):
    _mint(tmp_path, "t1", 0.40, "diff-a")
    _mint(tmp_path, "t1", 0.58, "diff-b")
    _mint(tmp_path, "t1", 0.47, "diff-c")
    _mint(tmp_path, "OTHER", 0.99, "diff-other")  # different target: ignored
    best = best_prior_artifact(tmp_path, "t1")
    assert best is not None
    path, metric = best
    assert metric == 0.58
    assert path.read_text() == "diff-b"


def test_best_prior_artifact_requires_artifact_on_disk(tmp_path):
    _mint(tmp_path, "t1", 0.40, "diff-a")
    # receipt without its artifact (the kimi case) must be skipped
    (tmp_path / "receipts" / "t1-lost.json").write_text(json.dumps({
        "target_id": "t1",
        "benchmark": {"candidate_metric": 9.9},
        "disclosure": {"diff_sha256": "deadbeef" * 8},
    }), encoding="utf-8")
    best = best_prior_artifact(tmp_path, "t1")
    assert best is not None and best[1] == 0.40


def test_best_prior_artifact_none_when_empty(tmp_path):
    assert best_prior_artifact(tmp_path, "t1") is None


def test_daemon_idles_on_stop_and_resumes(tmp_path):
    from dharma_swarm.foundry.campaign import CampaignResult
    from dharma_swarm.foundry.daemon import DaemonConfig, run_daemon

    stop = tmp_path / "STOP"
    stop.write_text("", encoding="utf-8")
    sleeps = {"n": 0}

    def counting_sleep(_s: float) -> None:
        sleeps["n"] += 1
        if sleeps["n"] == 3:
            stop.unlink()  # operator clears STOP -> work must resume

    def cycle(target_id, gens, cap, root):
        return CampaignResult(target_id=target_id, generations_run=1)

    cfg = DaemonConfig(targets=["t"], max_cycles=2, state_root=tmp_path,
                       interval_seconds=1, idle_on_stop=True)
    state = run_daemon(cfg, cycle_fn=cycle, sleep_fn=counting_sleep)
    assert sleeps["n"] >= 3            # idled while STOP present
    assert state.cycles_run == 2       # resumed and completed after clearing
    assert "kill-switch" not in state.stopped_reason


def test_daemon_idles_on_budget_cap(tmp_path):
    from dharma_swarm.foundry.campaign import CampaignResult
    from dharma_swarm.foundry.daemon import DaemonConfig, run_daemon

    # Pre-write a ledger at the cap; daemon must idle, then resume when the
    # ledger drops (simulating month rollover rewritten by _load_month_spend).
    ledger = tmp_path / "spend_ledger.json"
    from dharma_swarm.foundry.daemon import _month_key
    ledger.write_text(json.dumps({"month": _month_key(), "spend_usd": 300.0}))
    sleeps = {"n": 0}

    def counting_sleep(_s: float) -> None:
        sleeps["n"] += 1
        if sleeps["n"] == 2:
            ledger.write_text(json.dumps({"month": _month_key(), "spend_usd": 0.0}))

    def cycle(target_id, gens, cap, root):
        return CampaignResult(target_id=target_id, generations_run=1)

    cfg = DaemonConfig(targets=["t"], max_cycles=1, budget_cap_usd=300.0,
                       state_root=tmp_path, interval_seconds=1, idle_on_stop=True)
    state = run_daemon(cfg, cycle_fn=cycle, sleep_fn=counting_sleep)
    assert sleeps["n"] >= 2
    assert state.cycles_run == 1
    assert state.stopped_reason != "budget exhausted"
