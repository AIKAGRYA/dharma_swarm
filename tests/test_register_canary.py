"""Canaries for the chetana register-write kill switch.

These tests pin the Move 0 safety boundary: with DHARMA_CHETANA_ENABLED off,
canonical register writes must not leak even when defaulted producers pass the
canonical path explicitly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm import causal_ledger, drift_monitor, register_disciplines as rd
from dharma_swarm import witness_resolver
from dharma_swarm.register_disciplines import (
    DisciplineResult,
    log_to_stigmergy,
    make_register_mark,
    write_register_mark,
)


def _patch_canonical_register(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    log = tmp_path / "stigmergy" / "register_marks.jsonl"
    monkeypatch.delenv("DHARMA_CHETANA_ENABLED", raising=False)
    monkeypatch.setattr(rd, "DEFAULT_REGISTER_LOG", log)
    monkeypatch.setattr(causal_ledger, "DEFAULT_REGISTER_LOG", log)
    monkeypatch.setattr(drift_monitor, "DEFAULT_REGISTER_LOG", log)
    monkeypatch.setattr(witness_resolver, "DEFAULT_REGISTER_LOG", log)
    rd.reset_suppressed_register_mark_count()
    return log


def test_canonical_register_writers_suppressed_when_flag_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = _patch_canonical_register(tmp_path, monkeypatch)
    result = DisciplineResult(
        flagged=True,
        confidence=0.8,
        explanation="canary",
        discipline="canary",
    )
    mark = make_register_mark(result, subject_id="canary-subject")

    assert write_register_mark(mark) is False
    assert write_register_mark(mark, log_path=rd.DEFAULT_REGISTER_LOG) is False
    assert log_to_stigmergy(result) is False
    assert causal_ledger.declare_prediction(
        subject_kind="gate",
        subject_id="canary-gate",
        expected={"score": 1.0},
        window_heartbeats=1,
    ) is None
    assert causal_ledger.resolve_prediction(
        prediction_mark_id="canary-prediction",
        actual={"score": 1.0},
        expected={"score": 1.0},
    ) is None

    assert not log.exists()
    assert rd.get_suppressed_register_mark_count() >= 5


def test_defaulted_register_producers_do_not_leak_when_flag_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = _patch_canonical_register(tmp_path, monkeypatch)

    monitor = drift_monitor.DriftMonitor(
        watch_path=tmp_path / "drift_watch.jsonl",
        target_cycles=(25,),
    )
    monitor.add_watch(
        mutation_id="canary-drift",
        parameter="routing_bias",
        pre_metrics={"health": 0.60},
        post_metrics_t5={"health": 0.85},
        kept_at_cycle=100,
        original_mark_id="canary-original",
    )
    assert monitor.tick(current_cycle=130, current_metrics={"health": 0.55}) == []

    resolver = witness_resolver.WitnessResolver(
        pending_path=tmp_path / "witness" / "_pending.jsonl",
        witness_dir=tmp_path / "witness",
    )
    resolver.enqueue(
        prediction_mark_id="canary-prediction",
        subject_kind="gate",
        subject_id="canary-subject",
        expected={"score": 1.0},
        window_heartbeats=1,
        current_cycle=0,
    )
    assert resolver.tick(current_cycle=2) == []

    assert not log.exists()
    assert rd.get_suppressed_register_mark_count() >= 2
