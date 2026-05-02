"""Tests for dharma_swarm.autoresearch_history (Component 1.5).

Covers:
1. Cold start: all source paths missing -> empty result, no crash.
2. Strange-loop mutation match: kept vs reverted vs blocked outcomes.
3. Evolution archive match: ArchiveEntry-shaped records.
4. Causal ledger match: predictions with/without resolutions, drift.
5. Similarity threshold: irrelevant diagnosis returns nothing.
6. Multi-source merge: ranks by similarity across sources.
7. Robustness: corrupted JSONL lines skipped.

Run: pytest tests/test_autoresearch_history.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm import autoresearch_history


@pytest.fixture
def paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "mutations": tmp_path / "mutations.jsonl",
        "evolution": tmp_path / "evolution_archive.jsonl",
        "register": tmp_path / "register_marks.jsonl",
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


# ---------------------------------------------------------------------------
# 1. Cold start
# ---------------------------------------------------------------------------


def test_cold_start_no_substrates(paths: dict[str, Path]) -> None:
    result = autoresearch_history.consult_mutation_history(
        "high failure rate, routing_bias too low",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
    )
    assert result.tried_before == []
    assert result.succeeded == []
    assert result.failed == []
    assert result.n_total_records_considered == 0
    assert any("cold start" in n for n in result.notes)


def test_empty_diagnosis(paths: dict[str, Path]) -> None:
    result = autoresearch_history.consult_mutation_history(
        "",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
    )
    assert result.tried_before == []
    assert any("empty diagnosis" in n for n in result.notes)


# ---------------------------------------------------------------------------
# 2. Strange-loop mutations
# ---------------------------------------------------------------------------


def test_strange_loop_kept_mutation_lands_in_succeeded(
    paths: dict[str, Path],
) -> None:
    _write_jsonl(paths["mutations"], [
        {
            "id": "mut-001",
            "parameter": "routing_bias",
            "old_value": 0.0,
            "new_value": 0.05,
            "reason": "high failure rate triggered routing_bias increase",
            "kept": True,
            "gnani_verdict": True,
        },
    ])
    result = autoresearch_history.consult_mutation_history(
        "high failure rate routing_bias too low",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
    )
    assert len(result.succeeded) == 1
    assert result.succeeded[0].source == "strange_loop"
    assert result.succeeded[0].source_id == "mut-001"
    assert result.succeeded[0].outcome == "kept"
    assert result.succeeded[0].similarity > 0.3


def test_strange_loop_reverted_mutation_lands_in_failed(
    paths: dict[str, Path],
) -> None:
    _write_jsonl(paths["mutations"], [
        {
            "id": "mut-002",
            "parameter": "routing_bias",
            "old_value": 0.0,
            "new_value": 0.10,
            "reason": "high failure rate routing_bias adjustment",
            "kept": False,
            "gnani_verdict": True,
        },
    ])
    result = autoresearch_history.consult_mutation_history(
        "high failure rate routing_bias",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
    )
    assert len(result.failed) == 1
    assert result.failed[0].outcome == "reverted"


def test_strange_loop_blocked_by_gnani(paths: dict[str, Path]) -> None:
    _write_jsonl(paths["mutations"], [
        {
            "id": "mut-003",
            "parameter": "routing_bias",
            "reason": "high failure rate proposed routing change",
            "kept": None,
            "gnani_verdict": False,
        },
    ])
    result = autoresearch_history.consult_mutation_history(
        "high failure rate routing change",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
    )
    assert len(result.failed) == 1
    assert result.failed[0].outcome == "blocked"


# ---------------------------------------------------------------------------
# 3. Evolution archive
# ---------------------------------------------------------------------------


def test_evolution_archive_match(paths: dict[str, Path]) -> None:
    _write_jsonl(paths["evolution"], [
        {
            "id": "prop-aa",
            "component": "memory_consolidator",
            "description": "memory consolidation lag — increase batch size",
            "accepted": True,
            "fitness": 0.78,
        },
        {
            "id": "prop-bb",
            "component": "memory_consolidator",
            "description": "memory consolidation lag — try parallel write",
            "accepted": False,
            "fitness": 0.34,
        },
    ])
    result = autoresearch_history.consult_mutation_history(
        "memory consolidation lag concerning",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
    )
    assert len(result.succeeded) == 1
    assert result.succeeded[0].source_id == "prop-aa"
    assert len(result.failed) == 1
    assert result.failed[0].source_id == "prop-bb"


# ---------------------------------------------------------------------------
# 4. Causal ledger predictions + walk-backs
# ---------------------------------------------------------------------------


def test_causal_ledger_resolved_repaired(paths: dict[str, Path]) -> None:
    _write_jsonl(paths["register"], [
        {
            "mark_id": "pred-aaa",
            "plane": "causal",
            "discipline": "causal_prediction",
            "explanation": "stigmergy congestion mitigation prediction",
            "links": {
                "kind": "causal_prediction",
                "subject_kind": "mutation",
                "expected": {"density": 0.50},
            },
        },
        {
            "mark_id": "res-aaa",
            "plane": "causal",
            "discipline": "causal_resolution",
            "corrects": "pred-aaa",
            "links": {
                "kind": "causal_resolution",
                "actual": {"density": 0.52},
                "expected": {"density": 0.50},
            },
        },
    ])
    result = autoresearch_history.consult_mutation_history(
        "stigmergy congestion mitigation",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
    )
    assert len(result.succeeded) == 1
    assert result.succeeded[0].source == "causal_ledger"
    assert result.succeeded[0].outcome == "kept"


def test_causal_ledger_drift_detection(paths: dict[str, Path]) -> None:
    _write_jsonl(paths["register"], [
        {
            "mark_id": "pred-bbb",
            "plane": "causal",
            "discipline": "causal_prediction",
            "explanation": "evolution stagnation broken with new strategy",
            "links": {
                "kind": "causal_prediction",
                "subject_kind": "mutation",
            },
        },
        # post_deployment_drift mark with corrects-field pointing at the prediction
        {
            "mark_id": "drift-bbb",
            "plane": "register",  # NOT causal plane
            "discipline": "post_deployment_drift",
            "corrects": "pred-bbb",
            "explanation": "drift detected at T+25",
        },
    ])
    result = autoresearch_history.consult_mutation_history(
        "evolution stagnation broken strategy",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
    )
    assert len(result.failed) == 1
    assert result.failed[0].outcome == "drift_detected"


def test_causal_ledger_unresolved_lands_in_tried_before_only(
    paths: dict[str, Path],
) -> None:
    _write_jsonl(paths["register"], [
        {
            "mark_id": "pred-ccc",
            "plane": "causal",
            "discipline": "causal_prediction",
            "explanation": "telos drift slow correction in progress",
            "links": {
                "kind": "causal_prediction",
                "subject_kind": "mutation",
            },
        },
    ])
    result = autoresearch_history.consult_mutation_history(
        "telos drift slow correction",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
    )
    assert len(result.succeeded) == 0
    assert len(result.failed) == 0
    # Still surfaced in tried_before with outcome=unknown
    assert len(result.tried_before) == 1
    assert result.tried_before[0].outcome == "unknown"


# ---------------------------------------------------------------------------
# 5. Similarity threshold
# ---------------------------------------------------------------------------


def test_irrelevant_diagnosis_filtered(paths: dict[str, Path]) -> None:
    _write_jsonl(paths["mutations"], [
        {
            "id": "mut-x",
            "parameter": "routing_bias",
            "reason": "high failure rate triggered adjustment",
            "kept": True,
        },
    ])
    result = autoresearch_history.consult_mutation_history(
        "completely unrelated topic about cooking pasta",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
        similarity_threshold=0.30,
    )
    assert len(result.tried_before) == 0
    assert any("threshold" in n.lower() for n in result.notes)


def test_threshold_lowered_includes_marginal(paths: dict[str, Path]) -> None:
    _write_jsonl(paths["mutations"], [
        {
            "id": "mut-y",
            "parameter": "scaling_threshold",
            "reason": "memory consolidation cleanup",
            "kept": True,
        },
    ])
    result = autoresearch_history.consult_mutation_history(
        "consolidation issue",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
        similarity_threshold=0.10,
    )
    assert len(result.tried_before) == 1


# ---------------------------------------------------------------------------
# 6. Multi-source ranking
# ---------------------------------------------------------------------------


def test_multi_source_merge_ranks_by_similarity(paths: dict[str, Path]) -> None:
    # Strange-loop entry: medium similarity (~0.3)
    _write_jsonl(paths["mutations"], [
        {
            "id": "mut-medium",
            "parameter": "scaling_threshold",
            "reason": "high failure rate spike causing alarm",
            "kept": True,
        },
    ])
    # Evolution entry: high similarity
    _write_jsonl(paths["evolution"], [
        {
            "id": "prop-high",
            "component": "scaling_threshold",
            "description": "high failure rate spike alarm threshold tune",
            "accepted": True,
        },
    ])
    result = autoresearch_history.consult_mutation_history(
        "high failure rate spike alarm threshold",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
    )
    # Both succeeded; higher similarity ranked first
    assert len(result.succeeded) == 2
    sim_first = result.succeeded[0].similarity
    sim_second = result.succeeded[1].similarity
    assert sim_first >= sim_second


# ---------------------------------------------------------------------------
# 7. Robustness
# ---------------------------------------------------------------------------


def test_corrupted_jsonl_lines_skipped(paths: dict[str, Path]) -> None:
    paths["mutations"].parent.mkdir(parents=True, exist_ok=True)
    paths["mutations"].write_text(
        json.dumps({
            "id": "ok",
            "parameter": "routing_bias",
            "reason": "high failure rate routing fix",
            "kept": True,
        }) + "\n"
        + "not json\n"
        + "{partial json\n"
        + "\n",
        encoding="utf-8",
    )
    result = autoresearch_history.consult_mutation_history(
        "high failure rate routing fix",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
    )
    assert len(result.tried_before) == 1


def test_to_dict_round_trip(paths: dict[str, Path]) -> None:
    _write_jsonl(paths["mutations"], [
        {
            "id": "mut-rt",
            "parameter": "routing_bias",
            "reason": "test diagnosis match here",
            "kept": True,
        },
    ])
    result = autoresearch_history.consult_mutation_history(
        "test diagnosis match",
        mutations_path=paths["mutations"],
        evolution_archive_path=paths["evolution"],
        register_marks_path=paths["register"],
    )
    d = result.to_dict()
    s = json.dumps(d)
    parsed = json.loads(s)
    assert parsed["diagnosis"] == "test diagnosis match"
    assert len(parsed["succeeded"]) == 1
