import json
from pathlib import Path

import pytest

from dharma_swarm.versioning.promote_gate import (
    VersionPromotionGate,
    evaluate,
)


def _metrics(build_id, n=100, soak=24.0, correctness=0.9, ok=0.95, gate=0.95,
            rollback=0.0, cost=0.0, cost_observed=False, cb=0, gate_block=False,
            merkle_ok=True):
    return {
        "build_id": build_id,
        "circuit_breaker_trips": cb,
        "had_gate_block": gate_block,
        "merkle_ok": merkle_ok,
        "window": {"n_entries": n, "soak_hours": soak},
        "verified_metrics": {
            "correctness_mean": correctness,
            "gate_allow_rate": gate,
            "rollback_rate": rollback,
            "receipt_ok_rate": ok,
            "cost_usd_per_applied": cost,
            "cost_observed": cost_observed,
        },
    }


def test_better_candidate_promotes():
    cand = _metrics("0.1.0+new", correctness=0.92, ok=0.96)
    inc = _metrics("0.1.0+old", correctness=0.90, ok=0.95)
    v = evaluate(cand, inc)
    assert v.decision == "PROMOTE_CANDIDATE"
    assert v.ready_for_promotion is True


def test_rollback_rejects():
    cand = _metrics("0.1.0+bad", rollback=0.30)
    inc = _metrics("0.1.0+old")
    assert evaluate(cand, inc).decision == "REJECT"


def test_gate_block_rejects():
    cand = _metrics("0.1.0+bad", gate_block=True)
    inc = _metrics("0.1.0+old")
    assert evaluate(cand, inc).decision == "REJECT"


def test_broken_merkle_rejects():
    cand = _metrics("0.1.0+tampered", merkle_ok=False)
    inc = _metrics("0.1.0+old")
    assert evaluate(cand, inc).decision == "REJECT"


def test_circuit_breaker_rejects():
    cand = _metrics("0.1.0+trip", cb=2)
    assert evaluate(cand, _metrics("0.1.0+old")).decision == "REJECT"


def test_thin_sample_holds_not_rejects():
    cand = _metrics("0.1.0+thin", n=10)
    inc = _metrics("0.1.0+old")
    v = evaluate(cand, inc)
    assert v.decision == "HOLD"
    assert any("inconclusive" in r for r in v.reasons)


def test_short_soak_holds():
    cand = _metrics("0.1.0+fast", soak=2.0)
    assert evaluate(cand, _metrics("0.1.0+old")).decision == "HOLD"


def test_no_incumbent_holds():
    assert evaluate(_metrics("0.1.0+first"), None).decision == "HOLD"


def test_verifiably_worse_correctness_rejects():
    cand = _metrics("0.1.0+worse", n=1000, correctness=0.50)
    inc = _metrics("0.1.0+old", n=1000, correctness=0.90)
    assert evaluate(cand, inc).decision == "REJECT"


def test_low_receipt_floor_holds():
    cand = _metrics("0.1.0+meh", ok=0.80, correctness=0.90)
    inc = _metrics("0.1.0+old", ok=0.80)
    v = evaluate(cand, inc)
    assert v.decision == "HOLD"
    assert any("receipt_ok_rate" in r for r in v.reasons)


def test_gate_writes_pending_approval(tmp_path):
    g = VersionPromotionGate(tmp_path)
    (tmp_path / "0.1.0+new.json").write_text(json.dumps(_metrics("0.1.0+new", correctness=0.92)))
    (tmp_path / "0.1.0+old.json").write_text(json.dumps(_metrics("0.1.0+old", correctness=0.90)))
    verdict = g.compare("0.1.0+new", "0.1.0+old")
    assert verdict.decision == "PROMOTE_CANDIDATE"
    path = g.request_promotion(verdict)
    payload = json.loads(Path(path).read_text())
    assert payload["requires_operator_approval"] is True
    assert "promote_daemon_version.py" in payload["approval_command"]


def test_request_promotion_refuses_non_candidate(tmp_path):
    g = VersionPromotionGate(tmp_path)
    (tmp_path / "0.1.0+thin.json").write_text(json.dumps(_metrics("0.1.0+thin", n=5)))
    (tmp_path / "0.1.0+old.json").write_text(json.dumps(_metrics("0.1.0+old")))
    verdict = g.compare("0.1.0+thin", "0.1.0+old")
    assert verdict.decision == "HOLD"
    with pytest.raises(ValueError):
        g.request_promotion(verdict)
