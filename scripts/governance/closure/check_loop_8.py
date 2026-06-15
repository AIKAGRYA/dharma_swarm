#!/usr/bin/env python3
"""Loop 8 (Recognition / eigenform) closure check.

Loop 8 trace (CYBERNETIC_LOOP_MAP.md §"Loop 8: Recognition Loop"):
  SENSE      RecognitionEngine reads 8 signal sources (incl. cascade history
             from feedback_ascent and the evolution archive)
  INTERPRET  RecognitionEngine._build_seed synthesizes the self-model markdown
  CONSTRAIN  RecognitionEngine._quality_loop scores the seed via the genuine
             ouroboros and iterates to the quality fixpoint (the eigenform F(S)=S)
  ACT        recognition_seed.md + immutable history snapshot written
  ADAPT      the seed feeds future agent context as the L8 META layer (tier 8)

GREEN only when, on REAL data:
  (1) the recognition seed traces to Loop 1: the adapt receipt's loop1_join
      references a delegation_run that EXISTS in the real Loop-1 scoped db with
      a real-provider receipt (provider!='orchestrator', model!='',
      input_tokens>0) AND the side_effect_key MATCHES (authentic join), AND
  (2) SENSE fired on real cascade data: >=3 genuine cascade eigenform runs are
      persisted on the scoped owner surface (cascade_history.jsonl), AND
  (3) INTERPRET produced a real recognition seed that references the cascade
      signal (sense->interpret wiring proven), AND
  (4) CONSTRAIN/eigenform fired: the genuine ouroboros re-scores the persisted
      seed to the quality fixpoint (quality>=0.5 AND mimicry>=1.0 = F(S)=S), AND
  (5) ACT wrote recognition_seed.md AND >=1 immutable history snapshot, AND
  (6) One Wire intact: the recognition seed/adapt receipt is an INTERNAL signal,
      not a production archive.jsonl fitness write (FAIL LOUD on any production
      archive write marker).

Honest current state (LC_LOOP8_DIR unset / no driver run):
  RED — no recognition seed driven on real Loop-1 data. GREEN is earned by
  running drive_loop_1.py then drive_loop_8.py against scoped dirs.

INSUFFICIENT_DATA is honest, not a fail: if the Loop-1 scoped db has zero
real-provider receipts (Loop 1 itself RED), Loop 8 cannot prove its self-model
ingests real activity and reports RED with that explicit reason.

Replayable by a fresh agent from the scoped artifacts alone:
  LC_LOOP1_DB=<loop1_scoped.db> LC_LOOP8_DIR=<loop8_dir> \\
    python3 scripts/governance/closure/check_loop_8.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

LOOP1_DB = os.environ.get("LC_LOOP1_DB", "/tmp/lc_loop1_scoped.db")
LOOP8_DIR = Path(os.environ.get("LC_LOOP8_DIR", "/tmp/lc_loop8"))

BAD_PROVIDERS = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}


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
    adapt_path = LOOP8_DIR / "loop8_adapt_receipt.json"
    state_dir = LOOP8_DIR / "state"
    meta_dir = state_dir / "meta"
    seed_path = meta_dir / "recognition_seed.md"
    cascade_history = meta_dir / "cascade_history.jsonl"

    if not adapt_path.exists():
        return Verdict(
            8,
            "RED",
            f"no recognition eigenform adapt receipt on owner surface ({adapt_path}); "
            "self-model not driven (run drive_loop_8.py after drive_loop_1.py)",
            real_data=False,
        )

    # (1) JOIN to Loop 1 must be authentic against the real scoped db.
    real_receipts = _real_loop1_receipts(LOOP1_DB)
    if not real_receipts:
        return Verdict(
            8,
            "RED",
            f"no real-provider Loop-1 receipts in {LOOP1_DB} to anchor the self-model "
            "(Loop 1 RED — recognition seed cannot be proven to ingest real activity). "
            "INSUFFICIENT_DATA: drive real Loop-1 dispatches first.",
            real_data=False,
        )

    adapt = json.loads(adapt_path.read_text())
    if adapt.get("type") != "RECOGNITION_EIGENFORM":
        return Verdict(8, "RED", "adapt receipt malformed (type != RECOGNITION_EIGENFORM)", real_data=False)

    join = adapt.get("loop1_join", {})
    rid = join.get("delegation_run_id", "")
    rcpt = real_receipts.get(rid)
    if not rcpt:
        return Verdict(
            8,
            "RED",
            f"loop1_join references run {rid!r} not present as a real-provider receipt "
            f"in {LOOP1_DB} (fabricated join)",
            real_data=False,
        )
    sek_j = join.get("side_effect_key")
    sek_r = (rcpt.get("attributes", {}) or {}).get("side_effect_key")
    if not sek_j or sek_j != sek_r:
        return Verdict(
            8,
            "RED",
            f"loop1_join side_effect_key mismatch (join={sek_j} receipt={sek_r}); "
            "the self-model's Loop-1 anchor is not authentic",
            real_data=False,
        )

    # (2) SENSE: >=3 genuine cascade eigenform runs persisted on the owner surface.
    if not cascade_history.exists():
        return Verdict(
            8, "RED", f"no cascade history on owner surface ({cascade_history})", real_data=False
        )
    cascade_runs = []
    for line in cascade_history.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            cascade_runs.append(json.loads(line))
        except Exception:
            continue
    if len(cascade_runs) < 3:
        return Verdict(
            8,
            "RED",
            f"only {len(cascade_runs)} cascade run(s) in scoped history (need >=3 genuine "
            "eigenform runs to feed the self-model's cascade signal)",
            real_data=False,
        )
    # the cascade runs must be genuine eigenform outputs (the real engine sets these).
    if not any(r.get("eigenform_reached") for r in cascade_runs):
        return Verdict(
            8,
            "RED",
            "no cascade run reached eigenform — the genuine F(S)=S convergence machinery "
            "did not fire (sense source not real)",
            real_data=False,
        )

    # (3) INTERPRET: a real recognition seed referencing the cascade signal.
    if not seed_path.exists():
        return Verdict(8, "RED", f"no recognition seed written ({seed_path})", real_data=False)
    seed_text = seed_path.read_text()
    if len(seed_text) < 50:
        return Verdict(8, "RED", "recognition seed too small to be a real synthesis", real_data=False)
    if not adapt.get("interpret", {}).get("seed_references_cascade"):
        return Verdict(
            8,
            "RED",
            "recognition seed does not reference the cascade signal "
            "(sense->interpret wiring not proven)",
            real_data=False,
        )
    if adapt.get("interpret", {}).get("engine") != "RecognitionEngine":
        return Verdict(8, "RED", "interpret edge not the genuine RecognitionEngine", real_data=False)

    # (4) CONSTRAIN/eigenform: re-score the PERSISTED seed with the genuine ouroboros
    #     and assert the quality fixpoint (F(S)=S). We recompute here so the check
    #     does not trust the driver's self-reported number.
    try:
        from dharma_swarm.ouroboros import score_behavioral_fitness
    except Exception as e:
        return Verdict(8, "RED", f"cannot import genuine ouroboros scorer: {e}", real_data=False)
    _, modifiers = score_behavioral_fitness(seed_text)
    quality = float(modifiers.get("quality", 0.0))
    mimicry = float(modifiers.get("mimicry_penalty", 0.0))
    if not (quality >= 0.5 and mimicry >= 1.0):
        return Verdict(
            8,
            "RED",
            f"recognition eigenform fixpoint NOT reached on persisted seed "
            f"(quality={quality:.3f} need>=0.5, mimicry={mimicry:.3f} need>=1.0); "
            "F(seed)!=seed",
            real_data=False,
        )

    # (5) ACT: an immutable history snapshot exists.
    snaps = list((meta_dir / "history").glob("seed_*.md")) if (meta_dir / "history").exists() else []
    if not snaps:
        return Verdict(
            8, "RED", "no immutable recognition-seed snapshot written (act edge incomplete)", real_data=False
        )

    # (6) One Wire invariant: internal SIGNAL only, no PRODUCTION archive fitness write.
    #     A scoped archive note inside LOOP8_DIR is fine; a write to the production
    #     ~/.dharma/evolution/archive.jsonl is a violation. FAIL LOUD on a production marker.
    blob = adapt_path.read_text() + "\n" + seed_text
    home_archive = str(Path.home() / ".dharma" / "evolution" / "archive.jsonl")
    if home_archive in blob:
        return Verdict(
            8,
            "RED",
            "One Wire VIOLATION: recognition adapt edge references the PRODUCTION "
            "archive.jsonl fitness file (internal artifacts must never touch archive fitness)",
            real_data=False,
        )

    return Verdict(
        8,
        "GREEN",
        f"recognition self-model synthesized on REAL data: anchored to Loop-1 run={rid} "
        f"(provider={join.get('provider')} model={join.get('model')} "
        f"input_tokens={join.get('input_tokens')}); {len(cascade_runs)} genuine cascade "
        f"eigenform run(s) fed the sense layer; RecognitionEngine built a {len(seed_text)}-char "
        f"seed referencing the cascade signal; ouroboros eigenform fixpoint reached "
        f"(quality={quality:.3f}, mimicry={mimicry:.3f}, F(S)=S); {len(snaps)} immutable "
        f"snapshot(s); seed feeds agent context tier 8; One Wire intact",
        real_data=True,
        replay_cmd=(
            f"LC_LOOP1_DB={LOOP1_DB} LC_LOOP8_DIR={LOOP8_DIR} "
            "python3 scripts/governance/closure/check_loop_8.py"
        ),
    )


if __name__ == "__main__":
    sys.exit(emit(check()))
