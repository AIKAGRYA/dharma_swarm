"""Arena Truth governance report surface + cold-start corpus (track items 1 + 3).

The surface must be read-only, deterministic, replay-checked, and must never
smuggle a capability claim. The corpus must contain WINNER traces only, with
correctness labels from the deterministic scorer (zero training, v1 doctrine).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from dharma_swarm.coordination.arena.corpus import (
    COLD_START_TRACE_SCHEMA,
    build_cold_start_corpus,
    corpus_sha256,
)
from dharma_swarm.coordination.orchestrator_v1 import ZeroWeightOrchestratorV1


def _load(name: str):
    path = ROOT / "scripts" / "governance" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _evolved(seed: int = 0, generations: int = 6):
    orch = ZeroWeightOrchestratorV1(seed=seed)
    return orch, orch.evolve(generations=generations)


# --------------------------------------------------------------------- corpus
def test_corpus_contains_winner_traces_only():
    orch, result = _evolved()
    rows = build_cold_start_corpus(orch.runner, result.archive.elites())
    winner_ids = {e.genome.genome_id for e in result.archive.winners()}
    assert winner_ids, "seeded search should produce at least one winner"
    assert rows, "winners must produce corpus rows"
    assert {r["genome_id"] for r in rows} == winner_ids
    assert all(r["closeout_state"] == "positive_lift_candidate" for r in rows)


def test_corpus_rows_are_labeled_replayable_traces():
    orch, result = _evolved()
    rows = build_cold_start_corpus(orch.runner, result.archive.winners())
    task_count = len(orch.runner.taskpack.task_ids())
    assert len(rows) == task_count * len(result.archive.winners())
    for r in rows:
        assert r["schema"] == COLD_START_TRACE_SCHEMA
        assert isinstance(r["correct"], bool)
        assert r["prompt"]  # public view only
        assert r["task_manifest_hash"] and r["scorer_hash"]
    # deterministic: same winners -> same rows -> same content hash
    again = build_cold_start_corpus(orch.runner, result.archive.winners())
    assert corpus_sha256(rows) == corpus_sha256(again)


def test_corpus_skips_non_winners_entirely():
    orch, result = _evolved()
    losers = [
        e for e in result.archive.elites()
        if e.closeout_state != "positive_lift_candidate"
    ]
    assert build_cold_start_corpus(orch.runner, losers) == []


# -------------------------------------------------------------- report surface
def test_build_report_is_deterministic():
    mod = _load("arena_truth_report")
    core1, rows1, md1 = mod.build_report()
    core2, rows2, md2 = mod.build_report()
    assert core1 == core2
    assert rows1 == rows2
    assert md1 == md2


def test_report_carries_controls_and_no_capability_claim():
    mod = _load("arena_truth_report")
    core, _, _ = mod.build_report()
    best = core["best"]
    # every control arm's parity is logged on the surface (track blocker item 2)
    for arm in (
        "candidate",
        "best_single_full_budget",
        "same_budget_self_moa",
        "random_or_static_ensemble",
    ):
        assert arm in best["budget_parity"]
        assert arm in best["arm_scores"]
    assert {"observed_lift", "p_value", "significant", "n"} <= set(
        best["significance"]
    )
    assert best["dpi"]["learning_active"] is False  # zero-weight doctrine
    assert core["hermetic"] is True
    assert "NOT a production capability claim" in core["capability_claim"]


def test_write_then_check_roundtrip_and_tamper_detection(tmp_path):
    mod = _load("arena_truth_report")
    receipt = mod.write_surface(tmp_path)
    assert mod.check(tmp_path) == []
    # digest matches the house verifier convention (check_track_status)
    from dharma_swarm.memory_kernel.write_receipts import stable_digest

    assert receipt["digest"] == stable_digest(
        {k: v for k, v in receipt.items() if k != "digest"}
    )
    # tampering with the receipt must be caught
    path = tmp_path / mod.RECEIPT_NAME
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["best"]["arm_scores"]["candidate"] = 9.9
    path.write_text(json.dumps(tampered, indent=2, sort_keys=True), encoding="utf-8")
    findings = mod.check(tmp_path)
    assert any("digest mismatch" in f for f in findings)


def test_check_flags_stale_surface(tmp_path):
    mod = _load("arena_truth_report")
    mod.write_surface(tmp_path)
    # simulate drift: corpus edited after the receipt was cut
    corpus = tmp_path / mod.CORPUS_NAME
    corpus.write_text(corpus.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    findings = mod.check(tmp_path)
    assert any("corpus does not replay" in f for f in findings)


def test_committed_surface_replays():
    """The surface committed under reports/governance/arena must replay exactly."""
    mod = _load("arena_truth_report")
    assert mod.check(mod.DEFAULT_OUT_DIR) == []
