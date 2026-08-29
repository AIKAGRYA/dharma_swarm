"""The proof pilot must complete at least five bounded, offline cycles."""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.foundry.evaluator import canonical_digest
from dharma_swarm.foundry.pilot import run_five_cycle_pilot


REPO = Path(__file__).resolve().parents[1]


def test_five_cycle_pilot_is_bounded_unique_chained_and_simulation_only(tmp_path):
    summary = run_five_cycle_pilot(
        state_root=tmp_path,
        repo_root=REPO,
        runs=5,
        max_proposals_per_run=2,
        max_spend_usd=0.0,
    )
    assert summary["runs_completed"] == 5
    assert summary["network_calls"] == 0
    assert summary["total_spend_usd"] == 0.0
    assert summary["promotion_allowed"] is False
    assert len(summary["cycle_receipts"]) == 5

    pilot_root = Path(summary["summary_path"]).parent
    previous = "genesis"
    seen_paths = set()
    for index, relative in enumerate(summary["cycle_receipts"], start=1):
        path = pilot_root / relative
        assert path not in seen_paths
        seen_paths.add(path)
        payload = json.loads(path.read_text())
        claimed = payload.pop("digest")
        assert claimed == canonical_digest(payload)
        assert payload["sequence"] == index
        assert payload["prev_digest"] == previous
        assert payload["simulation_only"] is True
        assert payload["promotion_allowed"] is False
        assert payload["proposed"] <= 2
        assert payload["spend_usd"] == 0.0
        previous = claimed
    assert summary["receipt_chain_head"] == previous
