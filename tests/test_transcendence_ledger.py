"""E1 transcendence decomposition — hand-computed fixture + receipt replay."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from dharma_swarm.chamber.traces import GymTraceRow, SeatAnswer, write_corpus

_SPEC = importlib.util.spec_from_file_location(
    "transcendence_ledger",
    Path(__file__).resolve().parents[1] / "scripts/governance/transcendence_ledger.py",
)
tl = importlib.util.module_from_spec(_SPEC)
sys.modules["transcendence_ledger"] = tl
_SPEC.loader.exec_module(tl)


def _corpus(tmp_path: Path) -> Path:
    """4 tasks, 2 seats with perfectly anti-correlated errors:
    A errors on t3,t4; B errors on t1,t2; aggregate always correct.
    Hand computation: e_mean=0.5, e_ensemble=0.0, e_diversity=0.5,
    e_best=0.5, lift_vs_best=0.5, pearson(A,B) = -1.0."""
    a_correct = {"t1": True, "t2": True, "t3": False, "t4": False}
    rows = []
    for t in ("t1", "t2", "t3", "t4"):
        rows.append(GymTraceRow(
            env_id="g1_git_history", task_id=t, taskpack_sha="p" * 64,
            scorer_hash="s" * 64, seed=1,
            answers=(
                SeatAnswer(seat_id="A", answer=f"ans-A-{t}", correct=a_correct[t]),
                SeatAnswer(seat_id="B", answer=f"ans-B-{t}", correct=not a_correct[t]),
            ),
            aggregated_answer="winner", correct=True,
        ).to_dict())
    path = tmp_path / "corpus.jsonl"
    write_corpus(rows, path)
    return path


def test_decomposition_matches_hand_computation(tmp_path):
    receipt = tl.build_receipt(_corpus(tmp_path))
    (block,) = receipt["decomposition"]
    assert block["n_tasks"] == 4 and block["seats"] == ["A", "B"]
    assert block["seat_error_rates"] == {"A": 0.5, "B": 0.5}
    assert block["e_mean"] == 0.5
    assert block["e_ensemble"] == 0.0
    assert block["e_diversity_realized"] == 0.5
    assert block["e_best_seat"] == 0.5
    assert block["lift_vs_best_seat"] == 0.5
    assert block["error_correlation"]["pairs"] == {"A|B": -1.0}
    assert block["error_correlation"]["mean_offdiag"] == -1.0
    assert block["disagreement_rate"] == 1.0  # answers always differ
    assert receipt["summary"]["any_positive_lift_vs_best_seat"] is True
    assert receipt["capability_claim"].startswith("NONE")


def test_constant_error_vector_reports_undefined_correlation(tmp_path):
    rows = []
    for t in ("t1", "t2"):
        rows.append(GymTraceRow(
            env_id="e", task_id=t, taskpack_sha="p" * 64, scorer_hash="s" * 64,
            seed=1,
            answers=(SeatAnswer(seat_id="A", answer="x", correct=True),
                     SeatAnswer(seat_id="B", answer="y", correct=(t == "t1"))),
            aggregated_answer="x", correct=True,
        ).to_dict())
    path = tmp_path / "c.jsonl"
    write_corpus(rows, path)
    (block,) = tl.build_receipt(path)["decomposition"]
    assert block["error_correlation"]["pairs"] == {"A|B": None}
    assert block["error_correlation"]["mean_offdiag"] is None
    assert block["error_correlation"]["undefined_pairs"] == 1


def test_missing_per_seat_label_is_refused(tmp_path):
    row = GymTraceRow(
        env_id="e", task_id="t1", taskpack_sha="p" * 64, scorer_hash="s" * 64,
        seed=1, answers=(SeatAnswer(seat_id="A", answer="x", correct=None),),
        aggregated_answer="x", correct=True,
    ).to_dict()
    path = tmp_path / "c.jsonl"
    write_corpus([row], path)
    with pytest.raises(ValueError, match="lacks a correctness label"):
        tl.build_receipt(path)


def test_receipt_writes_seals_and_check_replays(tmp_path, monkeypatch):
    corpus = _corpus(tmp_path)
    out = tmp_path / "transcendence_receipt.json"
    monkeypatch.setattr(tl, "REPO_ROOT", tmp_path)
    receipt = tl.write_receipt(corpus, out)
    assert receipt["digest"] and receipt["corpus_rows"] == 4
    assert tl.check(out) == []
    committed = json.loads(out.read_text())
    committed["decomposition"][0]["e_ensemble"] = 0.25  # tamper
    out.write_text(json.dumps(committed, indent=2, sort_keys=True) + "\n")
    findings = tl.check(out)
    assert findings and any("digest mismatch" in f for f in findings)


def test_fabricated_all_seats_wrong_ensemble_right_is_refused(tmp_path):
    # R2-3: under selection aggregation the ensemble cannot be correct while
    # every seat is wrong. A corpus claiming so is fabricated -> ValueError.
    rows = []
    for t in ("t1", "t2"):
        rows.append(GymTraceRow(
            env_id="g1_git_history", task_id=t, taskpack_sha="p" * 64,
            scorer_hash="s" * 64, seed=1,
            answers=(SeatAnswer(seat_id="A", answer="w", correct=False),
                     SeatAnswer(seat_id="B", answer="w", correct=False)),
            aggregated_answer="winner", correct=True,  # impossible under selection
            attributes={"aggregation_rule": "oracle_argmax_v0 (train-signal)"},
        ).to_dict())
    path = tmp_path / "fabricated.jsonl"
    write_corpus(rows, path)
    with pytest.raises(ValueError, match="fabricated"):
        tl.build_receipt(path)


def test_selection_metadata_recorded(tmp_path):
    receipt = tl.build_receipt(_corpus(tmp_path))
    block = receipt["decomposition"][0]
    assert "selection_aggregation" in block
    assert "all_seats_wrong_tasks" in block


def test_check_detects_stale_receipt_after_corpus_change(tmp_path, monkeypatch):
    corpus = _corpus(tmp_path)
    out = tmp_path / "r.json"
    monkeypatch.setattr(tl, "REPO_ROOT", tmp_path)
    tl.write_receipt(corpus, out)
    rows = [GymTraceRow(
        env_id="g1_git_history", task_id="t9", taskpack_sha="p" * 64,
        scorer_hash="s" * 64, seed=1,
        answers=(SeatAnswer(seat_id="A", answer="z", correct=False),
                 SeatAnswer(seat_id="B", answer="z", correct=False)),
        aggregated_answer="z", correct=False,
    ).to_dict()]
    write_corpus(rows, corpus)  # corpus drifts under the receipt
    findings = tl.check(out)
    assert findings and any("does not replay" in f for f in findings)
