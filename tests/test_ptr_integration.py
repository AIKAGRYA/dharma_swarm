"""Integration-style tests for PTR artifacts and repair inputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from dharma_swarm.ptr_integrity import read_governance_integrity, read_repo_integrity
from dharma_swarm.ptr_metric import (
    PTRInputs,
    PTRPillar,
    compute_ptr_score,
    persist_ptr_score,
    pillar_from_repair_score,
    pillar_from_tcs,
)


def _repair_score(
    *,
    r_aggregate: float = 1.0,
    confidence: float = 1.0,
    provisional: bool = False,
    near_eigenform: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        r_aggregate=r_aggregate,
        confidence=confidence,
        provisional=provisional,
        near_eigenform=near_eigenform,
        notes=["synthetic repair evidence"],
    )


def test_ptr_score_from_repair_and_integrity_artifacts(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    meta_dir = state_dir / "meta"
    meta_dir.mkdir(parents=True)
    now = datetime(2026, 5, 4, tzinfo=timezone.utc)

    predictive_repair = pillar_from_repair_score(_repair_score())

    (meta_dir / "repo_integrity.json").write_text(
        json.dumps(
            {
                "score": 0.9,
                "confidence": 1.0,
                "computed_at": now.isoformat(),
                "checks": [{"name": "tests", "status": "pass"}],
                "hard_failures": [],
            }
        ),
        encoding="utf-8",
    )
    (meta_dir / "governance_integrity.json").write_text(
        json.dumps(
            {
                "score": 0.8,
                "confidence": 1.0,
                "computed_at": now.isoformat(),
                "checks": [{"name": "telos", "status": "pass"}],
                "hard_failures": [],
            }
        ),
        encoding="utf-8",
    )

    inputs = PTRInputs(
        predictive_repair=predictive_repair,
        tcs_identity=pillar_from_tcs(0.72),
        actuation_liveness=PTRPillar(point=0.76, lcb90=0.76),
        repo_integrity=read_repo_integrity(state_dir, now=now),
        governance_integrity=read_governance_integrity(state_dir, now=now),
        tcs=0.72,
        live_score=0.76,
        source="test.integration",
    )
    score = compute_ptr_score(inputs, now=now)

    assert score.authoritative is True
    assert score.components["predictive_repair"] == 1.0
    assert score.components["repo_integrity"] == 0.9
    assert score.components["governance_integrity"] == 0.8
    assert score.verdict in {"CAUTION", "PROCEED"}

    assert persist_ptr_score(
        score,
        score_path=meta_dir / "ptr_score.json",
        history_path=meta_dir / "ptr_history.jsonl",
    )
    persisted = json.loads((meta_dir / "ptr_score.json").read_text(encoding="utf-8"))
    assert persisted["authority_model"] == "negative_only"
    assert persisted["source"] == "test.integration"


def test_integrity_hard_failure_caps_pillar(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    meta_dir = state_dir / "meta"
    meta_dir.mkdir(parents=True)
    now = datetime(2026, 5, 4, tzinfo=timezone.utc)

    (meta_dir / "repo_integrity.json").write_text(
        json.dumps(
            {
                "score": 0.95,
                "confidence": 1.0,
                "computed_at": now.isoformat(),
                "hard_failures": ["module-budget"],
            }
        ),
        encoding="utf-8",
    )

    pillar = read_repo_integrity(state_dir, now=now)
    assert pillar.point == 0.49
    assert any("hard failures" in note for note in pillar.notes)


def test_integrity_malformed_artifact_is_missing(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    meta_dir = state_dir / "meta"
    meta_dir.mkdir(parents=True)
    (meta_dir / "governance_integrity.json").write_text(
        "{not valid json",
        encoding="utf-8",
    )

    pillar = read_governance_integrity(state_dir)
    assert pillar.is_missing()
    assert pillar.confidence == 0.0
    assert any("malformed" in note for note in pillar.notes)


def test_malformed_governance_artifact_withholds_authority(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    meta_dir = state_dir / "meta"
    meta_dir.mkdir(parents=True)
    (meta_dir / "governance_integrity.json").write_text(
        "{not valid json",
        encoding="utf-8",
    )

    score = compute_ptr_score(
        PTRInputs(
            predictive_repair=PTRPillar(point=0.8, lcb90=0.8),
            tcs_identity=pillar_from_tcs(0.72),
            actuation_liveness=PTRPillar(point=0.76, lcb90=0.76),
            repo_integrity=PTRPillar(point=0.9, lcb90=0.9),
            governance_integrity=read_governance_integrity(state_dir),
            tcs=0.72,
            live_score=0.76,
            source="test.integration",
        )
    )

    assert score.authoritative is False
    assert score.verdict == "INSUFFICIENT_EVIDENCE"
    assert "core_evidence_missing" in score.caps


def test_integrity_non_object_json_is_missing(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    meta_dir = state_dir / "meta"
    meta_dir.mkdir(parents=True)
    (meta_dir / "repo_integrity.json").write_text(
        "[1, 2, 3]",
        encoding="utf-8",
    )

    pillar = read_repo_integrity(state_dir)
    assert pillar.is_missing()
    assert pillar.confidence == 0.0
    assert any("malformed" in note for note in pillar.notes)


def test_skipped_governance_probe_withholds_authority(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    meta_dir = state_dir / "meta"
    meta_dir.mkdir(parents=True)
    now = datetime(2026, 5, 4, tzinfo=timezone.utc)
    (meta_dir / "governance_integrity.json").write_text(
        json.dumps(
            {
                "score": 0.9,
                "confidence": 0.0,
                "computed_at": now.isoformat(),
                "checks": [{"name": "governance-all", "status": "skipped"}],
                "hard_failures": [],
                "skipped": ["governance-all"],
            }
        ),
        encoding="utf-8",
    )

    governance = read_governance_integrity(state_dir, now=now)
    score = compute_ptr_score(
        PTRInputs(
            predictive_repair=PTRPillar(point=0.8, lcb90=0.8),
            tcs_identity=pillar_from_tcs(0.72),
            actuation_liveness=PTRPillar(point=0.76, lcb90=0.76),
            repo_integrity=PTRPillar(point=0.9, lcb90=0.9),
            governance_integrity=governance,
            tcs=0.72,
            live_score=0.76,
            source="test.integration",
        )
    )

    assert "low_coverage" in governance.flags
    assert score.authoritative is False
    assert score.verdict == "INSUFFICIENT_EVIDENCE"
    assert "authority_withheld" in score.caps


def test_integrity_string_fields_stay_single_items(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    meta_dir = state_dir / "meta"
    meta_dir.mkdir(parents=True)
    now = datetime(2026, 5, 4, tzinfo=timezone.utc)
    (meta_dir / "repo_integrity.json").write_text(
        json.dumps(
            {
                "score": 0.95,
                "confidence": 1.0,
                "computed_at": now.isoformat(),
                "hard_failures": "module-budget",
                "flags": "manual_review",
                "notes": "single-note",
            }
        ),
        encoding="utf-8",
    )

    pillar = read_repo_integrity(state_dir, now=now)
    assert pillar.point == 0.49
    assert pillar.flags == ["manual_review"]
    assert "single-note" in pillar.notes


def test_stale_integrity_artifact_marks_pillar_stale(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    meta_dir = state_dir / "meta"
    meta_dir.mkdir(parents=True)

    old = datetime(2026, 5, 1, tzinfo=timezone.utc)
    now = datetime(2026, 5, 4, tzinfo=timezone.utc)
    (meta_dir / "governance_integrity.json").write_text(
        json.dumps(
            {
                "score": 0.8,
                "confidence": 1.0,
                "computed_at": old.isoformat(),
                "hard_failures": [],
            }
        ),
        encoding="utf-8",
    )

    pillar = read_governance_integrity(state_dir, now=now)
    assert pillar.stale is True
    assert pillar.confidence == 0.5
