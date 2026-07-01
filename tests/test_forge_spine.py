"""Forge Learning Spine v0 — acceptance + invariant tests.

Hermetic: a faithful inline replica of the seed campaign_meta_report (both arms,
flat CONFIRM, ``positive_promotion_allowed: true``) is written to a tmp run dir, so
the tests never depend on ~/.dharma state. The headline test proves the spine
REFUSES to promote despite the report's positive flag.
"""
from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.forge_v1.forge_v2 import signals as S
from dharma_swarm.forge_v1.forge_v2 import promote as P
from dharma_swarm.forge_v1.forge_v2.learning_store import LearningStore
from dharma_swarm.forge_v1.forge_v2.ingest_learning import ingest_run

# Faithful replica of the seed report (overnight_verifier_role_20260630T033806Z):
# both arms have CONFIRM lower == 0.0, negative/near-zero overall lower, and the
# report nonetheless flags positive_promotion_allowed = true.
SEED_META = {
    "schema": "forge_v2.campaign_meta_report.v1",
    "arms_tested": ["mixed_moa", "verify_chain"],
    "attempt_count": 210,
    "closeout_counts": {"inconclusive_low_power": 2, "measured_negative": 5},
    "inference_scope": "fixed_allocation_confirmable",
    "contrasts": {
        "mixed_moa": {
            "by_split": {
                "confirm": {"lower": 0.0, "mean": 0.0, "n": 18, "p_le_0": 1.0, "upper": 0.0},
                "explore": {"lower": -0.037, "mean": 0.1852, "n": 27, "p_le_0": 0.079, "upper": 0.4074},
            },
            "fdr_positive_significant": False,
            "overall": {"lower": -0.0222, "mean": 0.1111, "n": 45, "p_le_0": 0.0775, "upper": 0.2667},
            "promotion_suppressed_reason": "",
        },
        "verify_chain": {
            "by_split": {
                "confirm": {"lower": 0.0, "mean": 0.0, "n": 24, "p_le_0": 1.0, "upper": 0.0},
                "explore": {"lower": -0.2778, "mean": -0.1111, "n": 36, "p_le_0": 0.9315, "upper": 0.0556},
            },
            "fdr_positive_significant": False,
            "overall": {"lower": -0.1667, "mean": -0.0667, "n": 60, "p_le_0": 0.933, "upper": 0.0333},
            "promotion_suppressed_reason": "",
        },
    },
    "learning_state": {
        "hard_task_count": 5,
        "null_survived_arms": ["verify_chain"],
        "positive_lift_candidates": [],
        "saturated_task_count": 0,
    },
    "next_policy": {"recommended_arms": ["verify_chain_hard_only"], "recommended_instances": []},
    "promotion_policy": {
        "adaptive_run": False,
        "positive_promotion_allowed": True,
        "reason": "fixed allocation; FDR/CONFIRM gates may promote positive candidates",
    },
    "reliability": {
        "mixed_moa": {"pass_all_observed_replicates": 0.2, "pass_at_observed_k": 0.6, "task_count": 5},
        "self_moa": {"pass_all_observed_replicates": 0.0, "pass_at_observed_k": 0.6, "task_count": 5},
        "verify_chain": {"pass_all_observed_replicates": 0.2, "pass_at_observed_k": 0.6, "task_count": 5},
    },
    "scheduler": {"label": "overnight_verifier_role", "completed_campaigns": 7, "total_cost_usd": 1.7088},
    "task_stats": {
        "django__django-12209": {"class_null": "self_moa", "hard_for_null": True, "self_moa_pass_rate": 0.2381},
        "sympy__sympy-22914": {"class_null": "self_moa", "hard_for_null": True, "self_moa_pass_rate": 0.8571},
    },
}


def _write_seed_run(tmp_path: Path) -> Path:
    run = tmp_path / "overnight_verifier_role_20260630T033806Z"
    run.mkdir()
    (run / "campaign_meta_report.json").write_text(json.dumps(SEED_META), encoding="utf-8")
    return run


def _signals():
    return S.report_to_signals(SEED_META, source_report_sha256="deadbeef", run_id="seed")


# 1 ------------------------------------------------------------------ negative knowledge
def test_negative_knowledge_preserved():
    sigs = _signals()
    assert len(sigs) == 2
    actions = {s.arm: s.action for s in sigs}
    assert actions["verify_chain"] == "downrank_or_ablate"  # null survived
    assert actions["mixed_moa"] == "hold_for_confirm"        # explore-positive, unconfirmed
    for s in sigs:
        assert s.action in S.SHADOW_ACTIONS
        assert s.evidence_strength == 0.0
        assert s.promotion_blockers  # a null result still carries pressure


# 2 ------------------------------------------------------------------ idempotency
def test_idempotency(tmp_path):
    store = LearningStore(root=tmp_path / "store")
    sigs = _signals()
    store.append_signals(sigs, source_report_sha256="deadbeef", run_id="seed", ingested_at="t1")
    store.append_signals(sigs, source_report_sha256="deadbeef", run_id="seed", ingested_at="t2")
    rows = [l for l in store.signals_path.read_text().splitlines() if l.strip()]
    ledger = [l for l in store.ledger_path.read_text().splitlines() if l.strip()]
    assert len(rows) == 2          # no duplicate signal rows
    assert len(ledger) == 2        # but every ingest is audited, even all-duplicate


# 3 -------------------------------------------------- HEADLINE: refuse despite positive flag
def test_promote_refuses_despite_positive_flag(tmp_path):
    summary = ingest_run(_write_seed_run(tmp_path), store_root=tmp_path / "store")
    assert summary["ok"] is True
    assert summary["promotion"]["n_refused"] == 2
    assert summary["promotion"]["n_promotable"] == 0

    packets = json.loads(Path(summary["promotion_packets_path"]).read_text())
    for pk in packets:
        assert pk["decision"] == "refused"
        assert pk["report_positive_promotion_allowed"] is True  # the trap is visible...
        assert pk["predicate"]["stats_confirm_gate"] is False    # ...and not obeyed
        assert "confirm_ci_lower<=0" in pk["blockers"]
        assert "contamination_possible_pretrain" in pk["blockers"]
        # payload hash integrity
        body = {k: v for k, v in pk.items() if k != "payload_sha256"}
        assert S.canonical_sha256(body) == pk["payload_sha256"]
        assert pk["safety"] == {"shadow_only": True, "live_apply_allowed": False, "code_diff_allowed": False}


# 4 ------------------------------------------------------------------ shadow isolation
def _stat(p: Path):
    return (p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None


def test_shadow_isolation(tmp_path):
    live_archive = Path("~/.dharma/evolution/archive.jsonl").expanduser()
    routing_db = Path("~/.dharma/logs/router/routing_memory.sqlite3").expanduser()
    before = (_stat(live_archive), _stat(routing_db))

    store_root = tmp_path / "store"
    ingest_run(_write_seed_run(tmp_path), store_root=store_root)

    after = (_stat(live_archive), _stat(routing_db))
    assert before == after, "live evolution archive / routing memory must be untouched"

    # All shadow artifacts live ONLY under the tmp store root.
    assert (store_root / "shadow_router" / "route_outcomes.jsonl").exists()
    assert (store_root / "darwin_shadow" / "darwin_shadow_archive.jsonl").exists()
    for row in (store_root / "darwin_shadow" / "darwin_shadow_archive.jsonl").read_text().splitlines():
        if row.strip():
            entry = json.loads(row)
            assert entry["status"] == "proposed"
            assert entry["evidence_tier"] == "unvalidated"
            assert entry["diff"] == ""  # never a code diff in v0


# 5 ------------------------------------------------------------------ signals purity
def test_signals_are_pure(tmp_path, monkeypatch):
    # Run with cwd in an empty tmp dir; calling signals must create no files.
    monkeypatch.chdir(tmp_path)
    a = _signals()
    b = _signals()
    assert [s.signal_key for s in a] == [s.signal_key for s in b]  # deterministic
    assert list(tmp_path.iterdir()) == []  # wrote nothing
