"""Tests for the PTR shadow metric."""

from __future__ import annotations

import ast
import math
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.ptr_metric import (
    PILLAR_WEIGHTS,
    PTRInputs,
    PTRPillar,
    compute_ptr_score,
    omega_attenuation,
    persist_ptr_score,
    pillar_from_repair_score,
    read_latest_ptr_score,
)


def _pillar(value: float, *, confidence: float = 1.0) -> PTRPillar:
    return PTRPillar(point=value, lcb90=value, confidence=confidence)


def _inputs(**overrides) -> PTRInputs:
    base = {
        "predictive_repair": _pillar(0.80),
        "tcs_identity": _pillar(0.70),
        "actuation_liveness": _pillar(0.75),
        "repo_integrity": _pillar(0.85),
        "governance_integrity": _pillar(0.90),
        "tcs": 0.70,
        "live_score": 0.75,
        "source": "test",
    }
    base.update(overrides)
    return PTRInputs(**base)


def test_ptr_uses_weighted_geometric_mean() -> None:
    inputs = _inputs()
    score = compute_ptr_score(inputs)

    expected = math.exp(
        sum(
            PILLAR_WEIGHTS[name] * math.log(value)
            for name, value in score.component_lcb90.items()
        )
    )
    assert score.ptr_raw == pytest.approx(expected, abs=0.0001)
    assert score.authority_model == "negative_only"
    assert score.ptr_autonomy_cap <= 2


def test_zero_repo_integrity_caps_to_hold() -> None:
    score = compute_ptr_score(_inputs(repo_integrity=_pillar(0.0)))

    assert score.verdict == "HOLD"
    assert "repo_integrity_low" in score.caps
    assert score.ptr < 0.4


def test_missing_predictive_repair_withholds_authoritative_score() -> None:
    score = compute_ptr_score(
        _inputs(
            predictive_repair=PTRPillar(
                point=None,
                confidence=0.0,
                missing=True,
                notes=["no causal predictions"],
            )
        )
    )

    assert score.authoritative is False
    assert score.verdict == "INSUFFICIENT_EVIDENCE"
    assert "core_evidence_missing" in score.caps
    assert {"pillar": "predictive_repair", "kind": "missing"} in score.missingness


def test_missing_governance_integrity_is_insufficient_not_hold() -> None:
    score = compute_ptr_score(
        _inputs(
            governance_integrity=PTRPillar(
                point=None,
                confidence=0.0,
                missing=True,
                notes=["no governance artifact"],
            )
        )
    )

    assert score.authoritative is False
    assert score.verdict == "INSUFFICIENT_EVIDENCE"
    assert "core_evidence_missing" in score.caps
    assert "governance_integrity_low" in score.caps


def test_missing_non_core_pillar_cannot_improve_score() -> None:
    known_dead = compute_ptr_score(_inputs(actuation_liveness=_pillar(0.0)))
    missing = compute_ptr_score(
        _inputs(actuation_liveness=PTRPillar(point=None, missing=True))
    )

    assert missing.ptr <= known_dead.ptr
    assert missing.verdict == "HOLD"
    assert {"pillar": "actuation_liveness", "kind": "missing"} in missing.missingness


def test_provisional_repair_score_withholds_authority() -> None:
    repair_score = SimpleNamespace(
        r_aggregate=0.95,
        confidence=1.0,
        provisional=True,
        near_eigenform=False,
        notes=["provisional"],
    )
    score = compute_ptr_score(
        _inputs(predictive_repair=pillar_from_repair_score(repair_score))
    )

    assert score.authoritative is False
    assert score.verdict == "INSUFFICIENT_EVIDENCE"
    assert "provisional" in score.caps
    assert "authority_withheld" in score.caps
    assert {"pillar": "authority", "kind": "provisional"} in score.missingness


def test_low_coverage_flag_withholds_authority() -> None:
    score = compute_ptr_score(
        _inputs(
            predictive_repair=PTRPillar(
                point=0.9,
                lcb90=0.9,
                confidence=0.8,
                flags=["low_coverage"],
            )
        )
    )

    assert score.authoritative is False
    assert score.verdict == "INSUFFICIENT_EVIDENCE"
    assert "low_coverage" in score.caps
    assert "authority_withheld" in score.caps


def test_near_eigenform_caps_proceed_to_caution() -> None:
    repair_score = SimpleNamespace(
        r_aggregate=0.99,
        confidence=1.0,
        provisional=False,
        near_eigenform=True,
        notes=["near_eigenform"],
    )
    score = compute_ptr_score(
        _inputs(
            predictive_repair=pillar_from_repair_score(repair_score),
            tcs_identity=_pillar(0.95),
            actuation_liveness=_pillar(0.95),
            repo_integrity=_pillar(0.95),
            governance_integrity=_pillar(0.95),
            tcs=0.95,
            live_score=0.95,
        )
    )

    assert score.authoritative is True
    assert score.verdict == "CAUTION"
    assert "near_eigenform" in score.caps


def test_direct_tcs_pillar_still_caps_tcs_lcb() -> None:
    score = compute_ptr_score(
        _inputs(
            predictive_repair=_pillar(0.95),
            tcs_identity=_pillar(1.0),
            actuation_liveness=_pillar(0.95),
            repo_integrity=_pillar(0.95),
            governance_integrity=_pillar(0.95),
            tcs=1.0,
            live_score=1.0,
        )
    )

    assert score.component_lcb90["tcs_identity"] == 0.85


def test_high_tcs_cannot_hide_dead_liveness() -> None:
    score = compute_ptr_score(
        _inputs(
            tcs_identity=_pillar(0.95),
            actuation_liveness=_pillar(0.0),
            tcs=0.95,
            live_score=0.0,
        )
    )

    assert score.verdict != "PROCEED"
    assert "omega_divergence" in score.caps
    assert score.omega_attenuator == pytest.approx(0.25)


def test_sustained_omega_divergence_holds_not_caution() -> None:
    score = compute_ptr_score(
        _inputs(
            predictive_repair=_pillar(0.95),
            tcs_identity=_pillar(1.0),
            actuation_liveness=_pillar(0.95),
            repo_integrity=_pillar(0.95),
            governance_integrity=_pillar(0.95),
            tcs=1.0,
            live_score=0.0,
            sustained_omega_cycles=3,
        )
    )

    assert score.verdict == "HOLD"
    assert "sustained_omega_divergence" in score.caps


def test_sustained_critical_tcs_holds() -> None:
    score = compute_ptr_score(
        _inputs(
            predictive_repair=_pillar(0.95),
            tcs_identity=_pillar(0.20),
            actuation_liveness=_pillar(0.95),
            repo_integrity=_pillar(0.95),
            governance_integrity=_pillar(0.95),
            tcs=0.20,
            live_score=0.20,
            sustained_low_tcs_cycles=3,
        )
    )

    assert score.verdict == "HOLD"
    assert "sustained_tcs_critical" in score.caps


def test_omega_attenuation_free_band_and_divergence() -> None:
    assert omega_attenuation(0.0) == 1.0
    assert omega_attenuation(0.15) == 1.0
    assert 0.25 < omega_attenuation(0.20) < 1.0
    assert omega_attenuation(0.40) == pytest.approx(0.25)


def test_stale_pillar_reduces_confidence() -> None:
    fresh = compute_ptr_score(_inputs())
    stale = compute_ptr_score(
        _inputs(repo_integrity=PTRPillar(point=0.85, lcb90=0.85, stale=True))
    )

    assert "repo_integrity" in stale.inputs_stale
    assert stale.confidence < fresh.confidence


def test_persist_and_read_latest_ptr_score(tmp_path: Path) -> None:
    score_path = tmp_path / "ptr_score.json"
    history_path = tmp_path / "ptr_history.jsonl"
    score = compute_ptr_score(
        _inputs(),
        now=datetime(2026, 5, 4, tzinfo=timezone.utc),
    )

    assert persist_ptr_score(score, score_path=score_path, history_path=history_path)
    latest = read_latest_ptr_score(score_path)

    assert latest is not None
    assert latest["ptr_version"] == "ptr.v0"
    assert latest["authority_model"] == "negative_only"
    assert history_path.read_text(encoding="utf-8").count("\n") == 1


def test_runtime_ptr_modules_do_not_import_subprocess_surfaces() -> None:
    forbidden = {"subprocess", "os", "asyncio"}
    for rel in ("dharma_swarm/ptr_metric.py", "dharma_swarm/ptr_integrity.py"):
        tree = ast.parse(Path(rel).read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
        assert imports.isdisjoint(forbidden)
