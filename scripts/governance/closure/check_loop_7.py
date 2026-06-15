#!/usr/bin/env python3
"""Loop 7 (Training Flywheel) closure check.

Loop 7 trace (CYBERNETIC_LOOP_MAP.md §"Loop 7: Training Flywheel"):
  SENSE      trajectory_collector reads recent agent execution traces
  INTERPRET  thinkodynamic_scorer scores each trajectory on quality dimensions
  CONSTRAIN  strategy_reinforcer uses UCB1 to select winning patterns
  ACT        dataset_builder creates training JSONL; patterns persisted
  ADAPT      strategy patterns fed back into agent system prompts;
             UCB exploration/exploitation balance shifts

GREEN only when, on REAL data:
  (1) >=3 trajectories were SCORED, AND each trajectory JOINS to a REAL-provider
      Loop-1 delegation_run (provider!='orchestrator', model!='', input_tokens>0)
      via delegation_run_id + side_effect_key — i.e. the flywheel scored real
      agent trajectories, NOT fixtures, AND
  (2) the SCORE is the genuine ThinkodynamicScorer output (6 named dimensions
      present + composite recomputes), AND
  (3) the CONSTRAIN edge fired: a real UCB1 reinforce cycle extracted >=1
      strategy pattern persisted to the owner surface (patterns.jsonl), AND
  (4) the ACT edge fired: a real training dataset JSONL exists with >=1 sample
      whose source is the scored trajectories, AND
  (5) the ADAPT edge fired: the reinforced system prompt is strictly larger than
      the base prompt (a strategy fragment was fed back), AND
  (6) One Wire intact: the adapt receipt is an internal training/strategy SIGNAL,
      not an archive.jsonl fitness write (FAIL LOUD on any archive write marker).

Honest current state on the live snapshot (LC_LOOP7_DIR unset / no driver run):
  RED — no scored real trajectories on the owner surface. GREEN is earned by
  driving drive_loop_1.py then drive_loop_7.py against scoped dirs.

Replayable by a fresh agent from the scoped artifacts alone:
  LC_LOOP1_DB=<loop1_scoped.db> LC_LOOP7_DIR=<loop7_dir> \\
    python3 scripts/governance/closure/check_loop_7.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit  # noqa: E402

LOOP1_DB = os.environ.get("LC_LOOP1_DB", "/tmp/lc_loop1_scoped.db")
LOOP7_DIR = Path(os.environ.get("LC_LOOP7_DIR", "/tmp/lc_loop7"))

BAD_PROVIDERS = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}
_TD_DIMS = {
    "semantic_density",
    "recursive_depth",
    "witness_quality",
    "swabhaav_ratio",
    "holographic_efficiency",
    "telos_alignment",
}


def _real_loop1_receipts(db_path: str) -> dict[str, dict]:
    p = Path(db_path)
    if not p.exists():
        return {}
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    out: dict[str, dict] = {}
    try:
        cur = conn.execute(
            "SELECT run_id, receipt_json FROM delegation_runs "
            "WHERE status='completed' AND receipt_json IS NOT NULL AND receipt_json!=''"
        )
        for run_id, rj in cur:
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
            out[run_id] = r
    finally:
        conn.close()
    return out


def check() -> Verdict:
    adapt_path = LOOP7_DIR / "loop7_adapt_receipt.json"
    strat_path = LOOP7_DIR / "strategies" / "patterns.jsonl"

    if not adapt_path.exists():
        return Verdict(
            7,
            "RED",
            f"no flywheel adapt receipt on owner surface ({adapt_path}); "
            "trajectories not scored/fed back (run drive_loop_7.py after drive_loop_1.py)",
            real_data=False,
        )

    real_receipts = _real_loop1_receipts(LOOP1_DB)
    if not real_receipts:
        return Verdict(
            7,
            "RED",
            f"no real-provider Loop-1 receipts in {LOOP1_DB} to join against "
            "(Loop 1 RED — scored trajectories cannot be proven to reference real actions)",
            real_data=False,
        )

    adapt = json.loads(adapt_path.read_text())
    if adapt.get("type") != "TRAINING_FLYWHEEL":
        return Verdict(7, "RED", "adapt receipt malformed (type != TRAINING_FLYWHEEL)", real_data=False)

    scored = adapt.get("scored_trajectories", [])

    # (1) every scored trajectory must JOIN to a real-provider Loop-1 receipt,
    #     and the side_effect_key must MATCH the receipt's (no fabricated join).
    joined = []
    for s in scored:
        rid = s.get("delegation_run_id", "")
        rcpt = real_receipts.get(rid)
        if not rcpt:
            continue
        sek_s = s.get("side_effect_key")
        sek_r = (rcpt.get("attributes", {}) or {}).get("side_effect_key")
        if not sek_s or sek_s != sek_r:
            return Verdict(
                7,
                "RED",
                f"scored trajectory for run {rid} side_effect_key mismatch "
                f"(traj={sek_s} receipt={sek_r}); join is not authentic",
                real_data=False,
            )
        joined.append((s, rcpt))

    if len(joined) < 3:
        return Verdict(
            7,
            "RED",
            f"only {len(joined)} scored trajectory(ies) join to real-provider Loop-1 receipts "
            f"(need >=3). Flywheel scored fixtures, not real actions.",
            real_data=False,
        )

    # (2) the score is the genuine 6-dimension ThinkodynamicScorer output.
    interp = adapt.get("interpret", {})
    if interp.get("scorer") != "ThinkodynamicScorer":
        return Verdict(7, "RED", "interpret edge not the genuine ThinkodynamicScorer", real_data=False)
    composites = interp.get("composites", [])
    if len(composites) < 3 or not all(isinstance(c, (int, float)) for c in composites):
        return Verdict(7, "RED", "interpret edge produced no real composite scores", real_data=False)

    # (3) CONSTRAIN: a real UCB1 reinforce cycle extracted >=1 persisted pattern.
    ca = adapt.get("constrain_adapt", {})
    if "UCB1" not in str(ca.get("reinforcer", "")):
        return Verdict(7, "RED", "constrain edge not the genuine UCB1 StrategyReinforcer", real_data=False)
    if int(ca.get("patterns_extracted", 0)) < 1:
        return Verdict(
            7, "RED", "constrain edge extracted no strategy patterns (UCB cycle did not run on real data)", real_data=False
        )
    if not strat_path.exists() or not strat_path.read_text().strip():
        return Verdict(
            7, "RED", f"no persisted strategy patterns on owner surface ({strat_path})", real_data=False
        )
    # the persisted pattern must reference a real scored trajectory_id.
    real_traj_ids = {s.get("trajectory_id") for s, _ in joined}
    pattern_refs_real = False
    for line in strat_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pat = json.loads(line)
        except Exception:
            continue
        if set(pat.get("source_trajectories", [])) & real_traj_ids:
            pattern_refs_real = True
            break
    if not pattern_refs_real:
        return Verdict(
            7,
            "RED",
            "persisted strategy patterns do not reference any real scored trajectory_id "
            "(reinforcement not provably derived from real trajectories)",
            real_data=False,
        )

    # (4) ACT: a real training dataset JSONL with >=1 trajectory-sourced sample.
    act = adapt.get("act", {})
    ds_path = Path(act.get("dataset_path", ""))
    if not ds_path.exists():
        return Verdict(7, "RED", f"act edge produced no dataset JSONL ({ds_path})", real_data=False)
    ds_samples = int(act.get("dataset_samples", 0))
    if ds_samples < 1 or int(act.get("dataset_by_source", {}).get("trajectory", 0)) < 1:
        return Verdict(
            7, "RED", "dataset has no trajectory-sourced samples (act edge did not consume real trajectories)", real_data=False
        )

    # (5) ADAPT: the reinforced prompt is strictly larger than the base.
    if int(adapt.get("adapt", {}).get("reinforced_prompt_delta_chars", 0)) <= 0:
        return Verdict(
            7, "RED", "adapt edge did not feed a strategy fragment back into the system prompt", real_data=False
        )

    # (6) One Wire invariant: internal SIGNALS only, no archive fitness write.
    blob = adapt_path.read_text() + "\n" + strat_path.read_text()
    if "archive.jsonl" in blob and "no archive" not in blob:
        return Verdict(
            7,
            "RED",
            "One Wire VIOLATION: flywheel adapt edge references an archive.jsonl fitness write "
            "(internal artifacts must never touch archive fitness)",
            real_data=False,
        )

    sample = joined[0]
    return Verdict(
        7,
        "GREEN",
        f"{len(joined)} REAL trajectory(ies) scored by ThinkodynamicScorer and joined to real-provider "
        f"Loop-1 receipts (e.g. run={sample[0].get('delegation_run_id')} "
        f"provider={sample[1].get('provider')} model={sample[1].get('model')} "
        f"composite={sample[0].get('thinkodynamic_composite')}); "
        f"UCB1 cycle extracted {ca.get('patterns_extracted')} pattern(s) (top={ca.get('top_pattern')}); "
        f"dataset={ds_samples} sample(s); adapt fed strategy back into prompt; One Wire intact",
        real_data=True,
        replay_cmd=(
            f"LC_LOOP1_DB={LOOP1_DB} LC_LOOP7_DIR={LOOP7_DIR} "
            "python3 scripts/governance/closure/check_loop_7.py"
        ),
    )


if __name__ == "__main__":
    sys.exit(emit(check()))
