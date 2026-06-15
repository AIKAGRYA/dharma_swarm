#!/usr/bin/env python3
"""Loop 8 (Recognition / eigenform) closure driver — real eigenform on real Loop-1 data.

Loop 8 is the strange loop: it computes the system's self-model (recognition
seed) by synthesizing all signal sources, then scores its OWN output to a
quality fixpoint (F(S)=S) before persisting it as the L8 META context layer.

It CONSUMES Loop 1: the recognition seed's `evolution` signal must trace to a
REAL Loop-1 delegation_run receipt (provider!='orchestrator', model!='',
input_tokens>0), and its `cascade` signal must come from genuine cascade
eigenform runs. This driver drives both on REAL data WITHOUT touching the
production daemon, the live runtime.db, archive fitness, or the production
~/.dharma/meta dir. Everything is scoped to /tmp dirs.

The 5 transitions on the REAL Loop-8 owner surface (no mocks anywhere):

  SENSE      RecognitionEngine._collect_signals reads 8 signal sources. We
             seed two of them on the scoped state dir from REAL data:
               - evolution/archive.jsonl: ONE entry derived from a real
                 Loop-1 receipt (the JOIN to Loop 1 — proves the self-model
                 ingests real provider activity, not a fixture).
               - meta/cascade_history.jsonl: >=3 entries from GENUINE
                 cascade LoopEngine.run('meta') eigenform runs (real
                 F(S)=S convergence machinery, deterministic, no LLM).
  INTERPRET  RecognitionEngine._build_seed synthesizes the self-model
             markdown across all collected signals (the genuine engine).
  CONSTRAIN  RecognitionEngine._quality_loop scores the seed via the genuine
             ouroboros.score_behavioral_fitness and iterates <=3x stripping
             performative language until the quality fixpoint holds
             (quality>=0.5 AND mimicry>=1.0). THIS is the eigenform: F(seed)
             stabilizes. (the loop runs inside synthesize()).
  ACT        synthesize() writes recognition_seed.md + an immutable
             history/seed_<ts>.md snapshot to the scoped meta dir.
  ADAPT      We write loop8_adapt_receipt.json recording that the seed feeds
             agent context as the L8 META layer (context_agent tier 8),
             carrying the Loop-1 join key. INTERNAL signal only; never an
             archive.jsonl fitness write (One Wire stays intact).

Run:  LC_LOOP1_DB=/tmp/lc_loop1_scoped.db LC_LOOP8_DIR=/tmp/lc_loop8 \\
        python3 scripts/governance/closure/drive_loop_8.py
Then: LC_LOOP1_DB=/tmp/lc_loop1_scoped.db LC_LOOP8_DIR=/tmp/lc_loop8 \\
        python3 scripts/governance/closure/check_loop_8.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

LOOP1_DB = os.environ.get("LC_LOOP1_DB", "/tmp/lc_loop1_scoped.db")
LOOP8_DIR = Path(os.environ.get("LC_LOOP8_DIR", "/tmp/lc_loop8"))

BAD_PROVIDERS = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}
N_CASCADE_RUNS = 3


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
            "SELECT run_id, receipt_json FROM delegation_runs "
            "WHERE status='completed' AND receipt_json IS NOT NULL AND receipt_json!='' "
            "ORDER BY started_at"
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
            out.append({"run_id": run_id, "receipt": r})
    finally:
        conn.close()
    return out


async def _real_cascade_runs(history_file: Path, n: int) -> list[dict]:
    """Drive the GENUINE cascade eigenform engine n times, scoped.

    We call LoopEngine.run() directly (NOT run_domain) so feedback_ascent's
    hardcoded Path.home() write to production ~/.dharma/meta is never hit.
    We write the cascade history to the SCOPED dir ourselves, mirroring
    feedback_ascent's schema exactly.
    """
    from dharma_swarm.cascade import LoopEngine
    from dharma_swarm.cascade_domains import meta as meta_domain

    history_file.parent.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    for _ in range(n):
        domain = meta_domain.get_domain()
        engine = LoopEngine(domain)
        result = await engine.run(resume=False)
        entry = {
            "domain": result.domain,
            "converged": result.converged,
            "best_fitness": result.best_fitness,
            "eigenform_reached": result.eigenform_reached,
            "iterations": result.iterations_completed,
            "duration": result.duration_seconds,
            "convergence_reason": result.convergence_reason,
            "timestamp": time.time(),
        }
        with open(history_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        entries.append(entry)
        print(
            f"CASCADE run domain={result.domain} converged={result.converged} "
            f"eigenform={result.eigenform_reached} reason={result.convergence_reason}"
        )
    return entries


def main() -> int:
    rows = _real_loop1_rows(LOOP1_DB)
    if not rows:
        print(f"RED: no real-provider Loop-1 rows in {LOOP1_DB} — run drive_loop_1.py first")
        return 1

    state_dir = LOOP8_DIR / "state"
    meta_dir = state_dir / "meta"
    evo_dir = state_dir / "evolution"
    meta_dir.mkdir(parents=True, exist_ok=True)
    evo_dir.mkdir(parents=True, exist_ok=True)

    # ---- SENSE (a): seed the scoped evolution archive from a REAL Loop-1 receipt.
    # This is the JOIN to Loop 1: the self-model's `evolution` signal now traces
    # to a real provider response. We write a fitness-shaped row to the SCOPED
    # archive only (G1/G4: production archive is never touched).
    anchor = rows[0]["receipt"]
    anchor_run_id = rows[0]["run_id"]
    anchor_sek = (anchor.get("attributes", {}) or {}).get("side_effect_key")
    archive_path = evo_dir / "archive.jsonl"
    evo_entry = {
        "component": "loop8_closure_anchor",
        "fitness": {"composite": 0.5, "source": "loop1_real_receipt"},
        "delegation_run_id": anchor_run_id,
        "side_effect_key": anchor_sek,
        "provider": anchor.get("provider"),
        "model": anchor.get("model"),
        "input_tokens": anchor.get("input_tokens"),
        "scoped_note": "SCOPED loop8 closure archive ONLY — not production, not One Wire fitness",
    }
    with open(archive_path, "a") as f:
        f.write(json.dumps(evo_entry) + "\n")
    print(
        f"SENSE evolution anchored to real Loop-1 run={anchor_run_id} "
        f"provider={anchor.get('provider')} model={anchor.get('model')} "
        f"input_tokens={anchor.get('input_tokens')}"
    )

    # ---- SENSE (b): drive >=3 GENUINE cascade eigenform runs into scoped history.
    cascade_history = meta_dir / "cascade_history.jsonl"
    cascade_entries = asyncio.run(_real_cascade_runs(cascade_history, N_CASCADE_RUNS))
    eigenforms = sum(1 for e in cascade_entries if e.get("eigenform_reached"))

    # ---- INTERPRET + CONSTRAIN(eigenform) + ACT: run the GENUINE RecognitionEngine
    #      against the scoped state dir. synthesize() collects signals, builds the
    #      seed, runs the ouroboros quality fixpoint loop, and writes
    #      recognition_seed.md + an immutable history snapshot.
    from dharma_swarm.meta_daemon import RecognitionEngine

    engine = RecognitionEngine(state_dir=state_dir)
    seed_text = asyncio.run(engine.synthesize(synthesis_type="deep"))

    seed_path = meta_dir / "recognition_seed.md"
    history_seeds = sorted((meta_dir / "history").glob("seed_*.md"))

    # Re-score the final seed with the GENUINE ouroboros to record the eigenform
    # (quality fixpoint) measurement on the persisted artifact.
    from dharma_swarm.ouroboros import score_behavioral_fitness

    _, modifiers = score_behavioral_fitness(seed_text)
    quality = float(modifiers.get("quality", 0.0))
    mimicry = float(modifiers.get("mimicry_penalty", 0.0))
    eigenform_fixpoint = quality >= 0.5 and mimicry >= 1.0

    # the seed must reference the real cascade runs (proves SENSE->INTERPRET wiring)
    seed_references_cascade = "Cascade Loops:" in seed_text or "recent runs" in seed_text

    # ---- ADAPT: record that the seed feeds agent context as the L8 META layer.
    adapt_path = LOOP8_DIR / "loop8_adapt_receipt.json"
    adapt_receipt = {
        "type": "RECOGNITION_EIGENFORM",
        "source": "loop8_closer",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # provenance: the self-model ingests a real Loop-1 receipt
        "loop1_join": {
            "delegation_run_id": anchor_run_id,
            "side_effect_key": anchor_sek,
            "provider": anchor.get("provider"),
            "model": anchor.get("model"),
            "input_tokens": anchor.get("input_tokens"),
        },
        "sense": {
            "evolution_archive": str(archive_path),
            "cascade_history": str(cascade_history),
            "cascade_runs": len(cascade_entries),
            "cascade_eigenforms": eigenforms,
        },
        "interpret": {
            "engine": "RecognitionEngine",
            "seed_chars": len(seed_text),
            "seed_references_cascade": seed_references_cascade,
        },
        "constrain_eigenform": {
            "scorer": "ouroboros.score_behavioral_fitness",
            "quality": quality,
            "mimicry_penalty": mimicry,
            "fixpoint_reached": eigenform_fixpoint,
            "note": "F(seed)=seed: quality>=0.5 AND mimicry>=1.0 (the recognition eigenform)",
        },
        "act": {
            "recognition_seed_path": str(seed_path),
            "immutable_snapshots": [str(p) for p in history_seeds],
        },
        "adapt": {
            "feeds_agent_context": "L8 META layer (context_agent.py tier 8 reads recognition_seed.md)",
            "context_tier": 8,
        },
        "one_wire_note": "internal recognition SIGNAL only; no production archive.jsonl fitness write",
    }
    adapt_path.write_text(json.dumps(adapt_receipt, indent=2))

    print(f"\nLOOP8_DIR={LOOP8_DIR}")
    print(f"cascade runs: {len(cascade_entries)} ({eigenforms} eigenform) -> {cascade_history}")
    print(f"recognition seed: {seed_path} ({len(seed_text)} chars)")
    print(f"eigenform fixpoint: quality={quality:.3f} mimicry={mimicry:.3f} reached={eigenform_fixpoint}")
    print(f"seed references cascade signal: {seed_references_cascade}")
    print(f"immutable snapshots: {len(history_seeds)}")
    print(f"adapt receipt: {adapt_path}")

    ok = (
        len(cascade_entries) >= N_CASCADE_RUNS
        and seed_path.exists()
        and len(seed_text) > 50
        and eigenform_fixpoint
        and seed_references_cascade
        and len(history_seeds) >= 1
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
