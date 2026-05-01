"""Tests for dharma_swarm.causal_ledger (Component 1.1).

Covers:
1. declare_prediction writes a mark with links.kind == "causal_prediction"
   and the expected payload.
2. resolve_prediction writes a second mark with corrects pointing back
   and links.delta computed correctly.
3. find_unresolved_predictions returns predictions without resolution.
4. compute_repair_rate_for_kind aggregates correctly across a fixture.
5. Composition with strange_loop pattern: round-trip a Mutation.id-shaped
   subject_id without loss.

Run: pytest tests/test_causal_ledger.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm import causal_ledger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_log(tmp_path: Path) -> Path:
    """Per-test register_marks.jsonl so we don't pollute the real one."""
    return tmp_path / "register_marks.jsonl"


def _read_marks(log_path: Path) -> list[dict]:
    """Helper: read all marks from a log file."""
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# 1. declare_prediction
# ---------------------------------------------------------------------------


def test_declare_prediction_writes_causal_plane_mark(tmp_log: Path) -> None:
    mark = causal_ledger.declare_prediction(
        subject_kind="mutation",
        subject_id="mut-abc123",
        expected={"avg_failure": 0.10, "health": 0.85},
        window_heartbeats=5,
        decision_point="strange_loop._observe_diagnose_propose",
        rationale="lower routing_bias should reduce failure rate",
        log_path=tmp_log,
    )

    assert mark is not None
    assert mark.plane == "causal"
    assert mark.discipline == causal_ledger.DISCIPLINE_PREDICT
    assert mark.subject_type == "decision"
    assert mark.subject_id == "mut-abc123"
    assert mark.flagged is False
    assert mark.severity == "note"
    assert mark.recommended_action == "continue"
    assert mark.corrects is None  # predictions don't correct anything
    assert mark.links["kind"] == "causal_prediction"
    assert mark.links["subject_kind"] == "mutation"
    assert mark.links["expected"] == {"avg_failure": 0.10, "health": 0.85}
    assert mark.links["window_heartbeats"] == 5

    # And it's actually on disk
    on_disk = _read_marks(tmp_log)
    assert len(on_disk) == 1
    assert on_disk[0]["mark_id"] == mark.mark_id


def test_declare_prediction_coerces_unknown_subject_kind_to_other(tmp_log: Path) -> None:
    mark = causal_ledger.declare_prediction(
        subject_kind="not_a_real_kind",
        subject_id="x",
        expected={"k": 1.0},
        window_heartbeats=1,
        log_path=tmp_log,
    )
    assert mark is not None
    assert mark.links["subject_kind"] == "other"


def test_declare_prediction_handles_non_numeric_expected_values(tmp_log: Path) -> None:
    mark = causal_ledger.declare_prediction(
        subject_kind="gate",
        subject_id="g1",
        expected={"valid": 0.5, "invalid": "not_a_number"},  # type: ignore[dict-item]
        window_heartbeats=1,
        log_path=tmp_log,
    )
    assert mark is not None
    # "invalid" silently dropped, "valid" preserved
    assert mark.links["expected"] == {"valid": 0.5}


# ---------------------------------------------------------------------------
# 2. resolve_prediction
# ---------------------------------------------------------------------------


def test_resolve_prediction_writes_with_corrects_and_delta(tmp_log: Path) -> None:
    pred = causal_ledger.declare_prediction(
        subject_kind="mutation",
        subject_id="mut-1",
        expected={"avg_failure": 0.10, "health": 0.85},
        window_heartbeats=5,
        log_path=tmp_log,
    )
    assert pred is not None

    resolution = causal_ledger.resolve_prediction(
        prediction_mark_id=pred.mark_id,
        actual={"avg_failure": 0.08, "health": 0.90},
        expected={"avg_failure": 0.10, "health": 0.85},
        decision_point="strange_loop._measure_decide",
        log_path=tmp_log,
    )

    assert resolution is not None
    assert resolution.plane == "causal"
    assert resolution.discipline == causal_ledger.DISCIPLINE_RESOLVE
    assert resolution.corrects == pred.mark_id  # the walk-back link
    assert resolution.subject_id == pred.mark_id  # group-by surface
    assert resolution.links["kind"] == "causal_resolution"
    assert resolution.links["actual"] == {"avg_failure": 0.08, "health": 0.90}

    # Delta math: actual - expected
    delta = resolution.links["delta"]
    assert delta["avg_failure"] == pytest.approx(-0.02)
    assert delta["health"] == pytest.approx(0.05)

    # Two marks on disk: prediction + resolution
    on_disk = _read_marks(tmp_log)
    assert len(on_disk) == 2
    assert on_disk[1]["corrects"] == pred.mark_id


def test_resolve_prediction_without_expected_skips_delta(tmp_log: Path) -> None:
    pred = causal_ledger.declare_prediction(
        subject_kind="gate",
        subject_id="g1",
        expected={"k": 1.0},
        window_heartbeats=1,
        log_path=tmp_log,
    )
    assert pred is not None

    resolution = causal_ledger.resolve_prediction(
        prediction_mark_id=pred.mark_id,
        actual={"k": 0.7},
        # no expected= passed
        log_path=tmp_log,
    )
    assert resolution is not None
    assert "delta" not in resolution.links
    assert resolution.links["actual"] == {"k": 0.7}


# ---------------------------------------------------------------------------
# 3. find_unresolved_predictions
# ---------------------------------------------------------------------------


def test_find_unresolved_returns_only_unresolved(tmp_log: Path) -> None:
    p1 = causal_ledger.declare_prediction(
        subject_kind="mutation",
        subject_id="mut-1",
        expected={"x": 1.0},
        window_heartbeats=5,
        log_path=tmp_log,
    )
    p2 = causal_ledger.declare_prediction(
        subject_kind="mutation",
        subject_id="mut-2",
        expected={"x": 2.0},
        window_heartbeats=5,
        log_path=tmp_log,
    )
    p3 = causal_ledger.declare_prediction(
        subject_kind="gate",
        subject_id="g1",
        expected={"x": 3.0},
        window_heartbeats=5,
        log_path=tmp_log,
    )
    assert p1 and p2 and p3

    # Resolve only p2
    causal_ledger.resolve_prediction(
        prediction_mark_id=p2.mark_id,
        actual={"x": 2.1},
        log_path=tmp_log,
    )

    unresolved = causal_ledger.find_unresolved_predictions(log_path=tmp_log)
    unresolved_ids = {u["mark_id"] for u in unresolved}
    assert unresolved_ids == {p1.mark_id, p3.mark_id}

    # Filter by kind
    only_mutations = causal_ledger.find_unresolved_predictions(
        log_path=tmp_log, subject_kind="mutation"
    )
    assert {u["mark_id"] for u in only_mutations} == {p1.mark_id}


def test_find_unresolved_returns_empty_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.jsonl"
    assert causal_ledger.find_unresolved_predictions(log_path=missing) == []


# ---------------------------------------------------------------------------
# 4. compute_repair_rate_for_kind
# ---------------------------------------------------------------------------


def test_repair_rate_basic(tmp_log: Path) -> None:
    # Three mutations: 2 repaired (within tolerance), 1 not.
    p1 = causal_ledger.declare_prediction(
        subject_kind="mutation",
        subject_id="m1",
        expected={"score": 0.80},
        window_heartbeats=5,
        log_path=tmp_log,
    )
    p2 = causal_ledger.declare_prediction(
        subject_kind="mutation",
        subject_id="m2",
        expected={"score": 0.50},
        window_heartbeats=5,
        log_path=tmp_log,
    )
    p3 = causal_ledger.declare_prediction(
        subject_kind="mutation",
        subject_id="m3",
        expected={"score": 0.70},
        window_heartbeats=5,
        log_path=tmp_log,
    )
    assert p1 and p2 and p3

    # Repaired: actual within 50% magnitude AND same sign
    causal_ledger.resolve_prediction(
        prediction_mark_id=p1.mark_id,
        actual={"score": 0.85},  # close to 0.80 -> repaired
        expected={"score": 0.80},
        log_path=tmp_log,
    )
    causal_ledger.resolve_prediction(
        prediction_mark_id=p2.mark_id,
        actual={"score": 0.55},  # close to 0.50 -> repaired
        expected={"score": 0.50},
        log_path=tmp_log,
    )
    # NOT repaired: opposite sign
    causal_ledger.resolve_prediction(
        prediction_mark_id=p3.mark_id,
        actual={"score": -0.10},  # sign flipped from +0.70 -> not repaired
        expected={"score": 0.70},
        log_path=tmp_log,
    )

    rate, n_pred, n_resolved = causal_ledger.compute_repair_rate_for_kind(
        "mutation", log_path=tmp_log
    )
    assert n_pred == 3
    assert n_resolved == 3
    assert rate == pytest.approx(2 / 3)


def test_repair_rate_zero_predictions_returns_zero(tmp_log: Path) -> None:
    # No predictions ever written
    rate, n_pred, n_resolved = causal_ledger.compute_repair_rate_for_kind(
        "mutation", log_path=tmp_log
    )
    assert rate == 0.0
    assert n_pred == 0
    assert n_resolved == 0


def test_repair_rate_unresolved_counted_in_denominator(tmp_log: Path) -> None:
    # 2 predictions, 1 resolved-and-repaired, 1 unresolved.
    # n_pred=2, n_resolved=1, repair_rate = 1/2 (unresolved counts AGAINST repair).
    p1 = causal_ledger.declare_prediction(
        subject_kind="gate",
        subject_id="g1",
        expected={"k": 1.0},
        window_heartbeats=5,
        log_path=tmp_log,
    )
    p2 = causal_ledger.declare_prediction(
        subject_kind="gate",
        subject_id="g2",
        expected={"k": 2.0},
        window_heartbeats=5,
        log_path=tmp_log,
    )
    assert p1 and p2

    causal_ledger.resolve_prediction(
        prediction_mark_id=p1.mark_id,
        actual={"k": 1.05},
        expected={"k": 1.0},
        log_path=tmp_log,
    )
    # p2 left unresolved

    rate, n_pred, n_resolved = causal_ledger.compute_repair_rate_for_kind(
        "gate", log_path=tmp_log
    )
    assert n_pred == 2
    assert n_resolved == 1
    assert rate == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# 5. Composition with strange_loop pattern (round-trip)
# ---------------------------------------------------------------------------


def test_mutation_id_round_trips_through_subject_id(tmp_log: Path) -> None:
    # Simulate a Mutation: id is uuid4()[:12] like strange_loop.py uses
    mutation_id = "abc123def456"

    pred = causal_ledger.declare_prediction(
        subject_kind="mutation",
        subject_id=mutation_id,
        expected={"avg_failure": 0.10},
        window_heartbeats=5,
        rationale="reduce routing_bias to lower cost",
        log_path=tmp_log,
    )
    assert pred is not None
    assert pred.subject_id == mutation_id

    resolution = causal_ledger.resolve_prediction(
        prediction_mark_id=pred.mark_id,
        actual={"avg_failure": 0.09},
        expected={"avg_failure": 0.10},
        log_path=tmp_log,
    )
    assert resolution is not None

    # The resolution's subject_id is the prediction's mark_id (group-by
    # surface), but the prediction's subject_id is the mutation_id.
    # That's the chain:
    #   prediction.subject_id == mutation_id
    #   prediction.mark_id    == resolution.subject_id == resolution.corrects
    # so a query for "all causal events for this mutation" walks:
    #   1. find prediction where subject_id == mutation_id
    #   2. find resolutions where corrects == prediction.mark_id
    on_disk = _read_marks(tmp_log)
    assert len(on_disk) == 2
    pred_disk = next(m for m in on_disk if m["discipline"] == "causal_prediction")
    res_disk = next(m for m in on_disk if m["discipline"] == "causal_resolution")
    assert pred_disk["subject_id"] == mutation_id
    assert res_disk["corrects"] == pred_disk["mark_id"]
    assert res_disk["subject_id"] == pred_disk["mark_id"]


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_corrupted_jsonl_lines_are_skipped(tmp_log: Path) -> None:
    pred = causal_ledger.declare_prediction(
        subject_kind="mutation",
        subject_id="m1",
        expected={"x": 1.0},
        window_heartbeats=1,
        log_path=tmp_log,
    )
    assert pred is not None

    # Inject malformed lines into the log
    with tmp_log.open("a", encoding="utf-8") as f:
        f.write("not json at all\n")
        f.write("{partial json\n")
        f.write("\n")

    # Should not crash; should still find the one valid prediction
    unresolved = causal_ledger.find_unresolved_predictions(log_path=tmp_log)
    assert len(unresolved) == 1
    assert unresolved[0]["mark_id"] == pred.mark_id

    rate, n, resolved = causal_ledger.compute_repair_rate_for_kind(
        "mutation", log_path=tmp_log
    )
    assert n == 1
    assert resolved == 0
