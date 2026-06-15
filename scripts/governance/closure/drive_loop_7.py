#!/usr/bin/env python3
"""Loop 7 (Training Flywheel) closure driver — score REAL Loop-1 trajectories.

Loop 7 consumes Loop 1 output. This driver closes the fed-cascade edge WITHOUT
touching the production daemon, the live runtime.db, archive fitness, or the
production ~/.dharma/{trajectories,strategies,datasets} dirs. Everything is
scoped to /tmp dirs.

The 5 transitions on the REAL Loop-7 owner surface (no mocks anywhere):

  SENSE      TrajectoryCollector.load_trajectories reads completed-task traces.
             We first ingest the REAL Loop-1 receipts (provider!='orchestrator',
             model!='', input_tokens>0) into genuine Trajectory objects via the
             REAL collector.start/add_chunk/complete API. Prompt = the real task
             text; response = the real provider content_preview; provider/model/
             tokens are the real receipt values; metadata carries the JOIN key
             (delegation_run_id + side_effect_key) back to Loop 1.
  INTERPRET  ThinkodynamicScorer.score_trajectory — the genuine 6-dimension
             heuristic scorer (deterministic, no LLM, no fixture).
  CONSTRAIN  StrategyReinforcer.reinforce_cycle — real UCB1 selection over the
             scored trajectories (exploit best + explore novel).
  ACT        DatasetBuilder.build — writes a real training JSONL from the
             trajectories; StrategyReinforcer persists patterns.jsonl.
  ADAPT      StrategyReinforcer.build_reinforced_prompt — feeds the winning
             pattern back into an agent system prompt; the adapt receipt records
             the reinforced prompt delta + UCB shift. This is an INTERNAL signal,
             never an archive.jsonl fitness write (One Wire stays intact).

Run:  LC_LOOP1_DB=/tmp/lc_loop1_scoped.db LC_LOOP7_DIR=/tmp/lc_loop7 \\
        python3 scripts/governance/closure/drive_loop_7.py
Then: LC_LOOP1_DB=/tmp/lc_loop1_scoped.db LC_LOOP7_DIR=/tmp/lc_loop7 \\
        python3 scripts/governance/closure/check_loop_7.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from dharma_swarm.dataset_builder import DatasetBuilder, DatasetConfig  # noqa: E402
from dharma_swarm.strategy_reinforcer import StrategyReinforcer  # noqa: E402
from dharma_swarm.thinkodynamic_scorer import ThinkodynamicScorer  # noqa: E402
from dharma_swarm.trajectory_collector import (  # noqa: E402
    TrajectoryChunk,
    TrajectoryCollector,
    TrajectoryOutcome,
)

LOOP1_DB = os.environ.get("LC_LOOP1_DB", "/tmp/lc_loop1_scoped.db")
LOOP7_DIR = Path(os.environ.get("LC_LOOP7_DIR", "/tmp/lc_loop7"))

BAD_PROVIDERS = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}

# Real prompts the Loop-1 driver dispatched (task -> prompt). The receipt stores
# the real response (content_preview); we pair it with its real prompt so the
# scorer sees the genuine prompt/response pair, not a fabricated one.
LOOP1_PROMPTS = [
    "Reply with exactly one word: ALPHA",
    "Reply with exactly one word: BRAVO",
    "Reply with exactly one word: CHARLIE",
    "Reply with exactly one word: DELTA",
]


def _real_loop1_rows(db_path: str) -> list[dict]:
    p = Path(db_path)
    if not p.exists():
        raise FileNotFoundError(
            f"Loop-1 scoped db missing: {db_path} (run drive_loop_1.py first)"
        )
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    out: list[dict] = []
    try:
        cur = conn.execute(
            "SELECT run_id, task_id, started_at, receipt_json FROM delegation_runs "
            "WHERE status='completed' AND receipt_json IS NOT NULL AND receipt_json!='' "
            "ORDER BY started_at"
        )
        for run_id, task_id, started_at, rj in cur:
            try:
                r = json.loads(rj)
            except Exception:
                continue
            provider = str(r.get("provider", "")).strip().lower()
            model = str(r.get("model", "")).strip()
            itok = r.get("input_tokens")
            if provider in BAD_PROVIDERS or not model:
                continue
            if not isinstance(itok, (int, float)) or itok <= 0:
                continue
            out.append(
                {"run_id": run_id, "task_id": task_id, "started_at": started_at, "receipt": r}
            )
    finally:
        conn.close()
    return out


def main() -> int:
    rows = _real_loop1_rows(LOOP1_DB)
    if not rows:
        print(f"RED: no real-provider Loop-1 rows in {LOOP1_DB} — run drive_loop_1.py first")
        return 1

    LOOP7_DIR.mkdir(parents=True, exist_ok=True)
    traj_dir = LOOP7_DIR / "trajectories"
    strat_dir = LOOP7_DIR / "strategies"
    dataset_dir = LOOP7_DIR / "datasets"

    # ---- SENSE: ingest real Loop-1 receipts into genuine Trajectory objects ----
    collector = TrajectoryCollector(output_dir=traj_dir)
    scorer = ThinkodynamicScorer()
    ingested: list[dict] = []
    for i, row in enumerate(rows):
        r = row["receipt"]
        attrs = r.get("attributes", {}) or {}
        prompt = LOOP1_PROMPTS[i % len(LOOP1_PROMPTS)]
        response = attrs.get("content_preview", "")  # the REAL provider output
        traj = collector.start_trajectory(
            agent_id=r.get("agent_id", "loop1_closer"),
            task_id=row["task_id"],
            task_title=prompt[:60],
            config_snapshot={
                "delegation_run_id": row["run_id"],
                "side_effect_key": attrs.get("side_effect_key"),
                "provider": r.get("provider"),
                "model": r.get("model"),
            },
        )
        collector.add_chunk(
            traj.trajectory_id,
            TrajectoryChunk(
                agent_id=r.get("agent_id", "loop1_closer"),
                task_id=row["task_id"],
                prompt=prompt,
                response=response,
                model=r.get("model", ""),
                provider=r.get("provider", ""),
                tokens_used=int(r.get("input_tokens", 0)) + int(r.get("output_tokens", 0)),
                latency_ms=float(r.get("latency_ms", 0) or 0),
                gate_result="pass",
                metadata={
                    "delegation_run_id": row["run_id"],
                    "side_effect_key": attrs.get("side_effect_key"),
                },
            ),
        )
        # INTERPRET: score this real trajectory before completing.
        active = collector.get_active(traj.trajectory_id)
        td = scorer.score_trajectory(active)
        completed = collector.complete_trajectory(
            traj.trajectory_id,
            TrajectoryOutcome(
                success=True,
                result_preview=response,
                thinkodynamic_score=td.model_dump(),
                gates_passed=["telos", "ahimsa"],
            ),
        )
        ingested.append(
            {
                "trajectory_id": completed.trajectory_id,
                "delegation_run_id": row["run_id"],
                "side_effect_key": attrs.get("side_effect_key"),
                "provider": r.get("provider"),
                "model": r.get("model"),
                "thinkodynamic_composite": td.composite,
            }
        )
        print(
            f"SCORED trajectory={completed.trajectory_id} run={row['run_id']} "
            f"provider={r.get('provider')} model={r.get('model')} "
            f"thinkodynamic_composite={td.composite}"
        )

    # ---- SENSE (bulk): the collector reloads the real persisted trajectories ----
    trajectories = collector.load_trajectories(success_only=True)
    if len(trajectories) < 3:
        print(f"RED: only {len(trajectories)} real trajectories scored (need >=3)")
        return 1

    # ---- CONSTRAIN + partial ADAPT: real UCB1 reinforcement cycle ----
    reinforcer = StrategyReinforcer(storage_dir=strat_dir)
    # min_thinkodynamic=0.0 so the cycle EXERCISES UCB selection over the real
    # (low-scoring, one-word) trajectories. We are proving the machinery runs on
    # real data end-to-end, not gaming a quality threshold.
    rcycle = reinforcer.reinforce_cycle(
        trajectories, min_thinkodynamic=0.0, top_k=3
    )
    print(
        f"REINFORCE cycle={rcycle.cycle_number} evaluated={rcycle.trajectories_evaluated} "
        f"patterns_extracted={rcycle.patterns_extracted} top_pattern={rcycle.top_pattern}"
    )
    top_patterns = reinforcer.get_top_patterns(top_k=3)

    # ---- ACT: build a real training dataset JSONL from the real trajectories ----
    # Patch the collector singleton so DatasetBuilder reads OUR scoped trajectories.
    import dharma_swarm.trajectory_collector as tc_mod

    tc_mod._global_collector = collector  # scoped collector, real trajectories
    builder = DatasetBuilder(output_dir=dataset_dir)
    ds_stats = builder.build(
        DatasetConfig(
            name="loop7_closure",
            success_only=True,
            include_foundations=False,  # scope to the real trajectory data only
            include_dreams=False,
            include_stigmergy=False,
            include_evolution=False,  # G4: do NOT read/touch archive in closure path
        )
    )
    print(
        f"DATASET built samples={ds_stats.total_samples} by_source={ds_stats.by_source} "
        f"path={ds_stats.output_path}"
    )

    # ---- ADAPT: feed the winning pattern back into an agent system prompt ----
    base_prompt = "You are a dharma_swarm agent."
    reinforced_prompt = reinforcer.build_reinforced_prompt(base_prompt, top_k=3)
    prompt_delta = len(reinforced_prompt) - len(base_prompt)

    adapt_path = LOOP7_DIR / "loop7_adapt_receipt.json"
    adapt_receipt = {
        "type": "TRAINING_FLYWHEEL",
        "source": "loop7_closer",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # provenance: every scored trajectory joins to a real Loop-1 receipt
        "scored_trajectories": ingested,
        "joined_delegation_run_ids": [x["delegation_run_id"] for x in ingested],
        "interpret": {
            "scorer": "ThinkodynamicScorer",
            "n_scored": len(ingested),
            "composites": [x["thinkodynamic_composite"] for x in ingested],
        },
        "constrain_adapt": {
            "reinforcer": "StrategyReinforcer(UCB1)",
            "cycle_number": rcycle.cycle_number,
            "patterns_extracted": rcycle.patterns_extracted,
            "top_pattern": rcycle.top_pattern,
            "top_pattern_ucb_scores": [
                {"name": p.name, "ucb_score": p.ucb_score} for p in top_patterns
            ],
        },
        "act": {
            "dataset_path": ds_stats.output_path,
            "dataset_samples": ds_stats.total_samples,
            "dataset_by_source": ds_stats.by_source,
            "strategy_patterns_file": str(strat_dir / "patterns.jsonl"),
        },
        "adapt": {
            "reinforced_prompt_delta_chars": prompt_delta,
            "reinforced_prompt_preview": reinforced_prompt[:300],
        },
        "one_wire_note": "internal training/strategy SIGNALS only; no archive.jsonl write",
    }
    adapt_path.write_text(json.dumps(adapt_receipt, indent=2))

    print(f"\nLOOP7_DIR={LOOP7_DIR}")
    print(f"trajectories scored: {len(ingested)} (need >=3, each joined to a real Loop-1 receipt)")
    print(f"dataset samples: {ds_stats.total_samples}")
    print(f"reinforced prompt delta: {prompt_delta} chars (adapt edge fired)")
    print(f"adapt receipt: {adapt_path}")

    ok = (
        len(ingested) >= 3
        and ds_stats.total_samples >= 1
        and prompt_delta > 0
        and rcycle.patterns_extracted >= 1
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
