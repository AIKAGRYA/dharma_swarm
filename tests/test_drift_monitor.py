"""Tests for dharma_swarm.drift_monitor (Component 1.4).

Covers:
1. add_watch + idempotency.
2. tick: target not elapsed -> nothing fires.
3. tick: T+25 elapsed, no decay -> no mark, target consumed.
4. tick: T+25 elapsed, real decay -> mark fired with corrects linkage.
5. Drift detection: half-loss of gain crosses threshold.
6. Drift detection: gain restored -> no fire.
7. Drift detection: material-gain-floor (noise) doesn't fire.
8. Drift detection: quorum (must hit >50% of metrics).
9. Severity bucketing (warn/hold/block) by decay_ratio magnitude.
10. Persistence: rehydrate after restart.
11. Eviction: max age + all-targets-fired.

Run: pytest tests/test_drift_monitor.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm import drift_monitor


@pytest.fixture
def paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "watch": tmp_path / "drift_watch.jsonl",
        "register_marks": tmp_path / "register_marks.jsonl",
    }


def _make_monitor(paths: dict[str, Path], **kwargs) -> drift_monitor.DriftMonitor:
    return drift_monitor.DriftMonitor(
        watch_path=paths["watch"],
        register_marks_path=paths["register_marks"],
        **kwargs,
    )


def _read_register_marks(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# 1. add_watch + idempotency
# ---------------------------------------------------------------------------


def test_add_watch_basic(paths: dict[str, Path]) -> None:
    m = _make_monitor(paths)
    ok = m.add_watch(
        mutation_id="mut-1",
        parameter="routing_bias",
        pre_metrics={"health": 0.6},
        post_metrics_t5={"health": 0.85},
        kept_at_cycle=100,
        original_mark_id="mark-xyz",
    )
    assert ok is True
    assert m.watch_count() == 1


def test_add_watch_idempotent(paths: dict[str, Path]) -> None:
    m = _make_monitor(paths)
    m.add_watch(
        mutation_id="dup",
        parameter="x",
        pre_metrics={"k": 0.0},
        post_metrics_t5={"k": 1.0},
        kept_at_cycle=0,
        original_mark_id="orig",
    )
    second = m.add_watch(
        mutation_id="dup",
        parameter="x",
        pre_metrics={"k": 0.0},
        post_metrics_t5={"k": 1.0},
        kept_at_cycle=0,
        original_mark_id="orig",
    )
    assert second is False
    assert m.watch_count() == 1


def test_add_watch_empty_id_rejected(paths: dict[str, Path]) -> None:
    m = _make_monitor(paths)
    ok = m.add_watch(
        mutation_id="",
        parameter="x",
        pre_metrics={"k": 0.0},
        post_metrics_t5={"k": 1.0},
        kept_at_cycle=0,
        original_mark_id="o",
    )
    assert ok is False


# ---------------------------------------------------------------------------
# 2-3. tick: target not elapsed / no decay
# ---------------------------------------------------------------------------


def test_tick_target_not_elapsed_no_fire(paths: dict[str, Path]) -> None:
    m = _make_monitor(paths)
    m.add_watch(
        mutation_id="m",
        parameter="p",
        pre_metrics={"h": 0.6},
        post_metrics_t5={"h": 0.85},
        kept_at_cycle=100,
        original_mark_id="o",
    )
    # T+25 = absolute cycle 125. Tick at cycle 110.
    produced = m.tick(current_cycle=110, current_metrics={"h": 0.85})
    assert produced == []
    assert m.watch_count() == 1


def test_tick_target_elapsed_no_decay(paths: dict[str, Path]) -> None:
    m = _make_monitor(paths)
    m.add_watch(
        mutation_id="m",
        parameter="p",
        pre_metrics={"h": 0.6},
        post_metrics_t5={"h": 0.85},
        kept_at_cycle=100,
        original_mark_id="o",
    )
    # T+25 elapsed; current matches T+5 -> no decay
    produced = m.tick(current_cycle=130, current_metrics={"h": 0.85})
    assert produced == []
    # T+25 target consumed; T+100 still pending
    assert m.watch_count() == 1


# ---------------------------------------------------------------------------
# 4. Real decay -> drift mark fired
# ---------------------------------------------------------------------------


def test_tick_real_decay_fires_drift_mark(paths: dict[str, Path]) -> None:
    m = _make_monitor(paths)
    m.add_watch(
        mutation_id="mut-decay",
        parameter="routing_bias",
        pre_metrics={"health": 0.60},
        post_metrics_t5={"health": 0.85},   # gain of 0.25
        kept_at_cycle=100,
        original_mark_id="orig-mark-decay",
    )
    # At T+25, current is back near baseline -> 100% loss of gain
    produced = m.tick(current_cycle=130, current_metrics={"health": 0.55})
    assert len(produced) == 1
    mark_summary = produced[0]
    assert mark_summary["mutation_id"] == "mut-decay"
    assert mark_summary["original_mark_id"] == "orig-mark-decay"
    assert mark_summary["decay_ratio"] >= 1.0  # full loss + worse than baseline

    # Verify the actual register mark on disk
    marks = _read_register_marks(paths["register_marks"])
    assert len(marks) == 1
    m_disk = marks[0]
    assert m_disk["discipline"] == "post_deployment_drift"
    assert m_disk["corrects"] == "orig-mark-decay"
    assert m_disk["recommended_action"] == "hold"
    assert m_disk["plane"] == "evolution"


def test_default_register_path_is_gated_when_flag_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dharma_swarm import register_disciplines as rd

    monkeypatch.delenv("DHARMA_CHETANA_ENABLED", raising=False)
    log = tmp_path / "stigmergy" / "register_marks.jsonl"
    monkeypatch.setattr(rd, "DEFAULT_REGISTER_LOG", log)
    monkeypatch.setattr(drift_monitor, "DEFAULT_REGISTER_LOG", log)
    rd.reset_suppressed_register_mark_count()

    m = drift_monitor.DriftMonitor(
        watch_path=tmp_path / "drift_watch.jsonl",
        target_cycles=(25,),
    )
    m.add_watch(
        mutation_id="mut-default-gated",
        parameter="routing_bias",
        pre_metrics={"health": 0.60},
        post_metrics_t5={"health": 0.85},
        kept_at_cycle=100,
        original_mark_id="orig-default-gated",
    )

    produced = m.tick(current_cycle=130, current_metrics={"health": 0.55})

    assert produced == []
    assert not log.exists()
    assert rd.get_suppressed_register_mark_count() == 1


# ---------------------------------------------------------------------------
# 5-7. Drift-detection unit cases
# ---------------------------------------------------------------------------


def test_detect_drift_half_loss_crosses_threshold() -> None:
    out = drift_monitor._detect_drift(
        pre={"h": 0.5},
        post_t5={"h": 1.0},   # gain 0.5
        current={"h": 0.7},   # current gain 0.2 -> 60% loss of gain
        tolerance=0.5,
        quorum=0.5,
    )
    assert out["fired"] is True
    assert out["n_metrics_decayed"] == 1


def test_detect_drift_no_fire_when_gain_held() -> None:
    out = drift_monitor._detect_drift(
        pre={"h": 0.5},
        post_t5={"h": 1.0},
        current={"h": 0.95},  # only ~10% loss of gain
        tolerance=0.5,
        quorum=0.5,
    )
    assert out["fired"] is False


def test_detect_drift_material_gain_floor(monkeypatch) -> None:
    # gain_t5 = 0.005, well below MATERIAL_GAIN_FLOOR=0.01
    out = drift_monitor._detect_drift(
        pre={"h": 0.500},
        post_t5={"h": 0.505},
        current={"h": 0.500},  # full reversion
        tolerance=0.5,
        quorum=0.5,
    )
    # Skipped due to material-gain floor
    assert out["fired"] is False
    assert out["n_metrics_decayed"] == 0


def test_detect_drift_quorum_required() -> None:
    # 1 of 3 metrics decays -> below quorum
    out = drift_monitor._detect_drift(
        pre={"a": 0.0, "b": 0.0, "c": 0.0},
        post_t5={"a": 1.0, "b": 1.0, "c": 1.0},
        current={"a": 0.0, "b": 1.0, "c": 1.0},  # only "a" decayed
        tolerance=0.5,
        quorum=0.5,
    )
    assert out["fired"] is False
    assert out["n_metrics_decayed"] == 1
    assert out["n_metrics_compared"] == 3


def test_detect_drift_quorum_met() -> None:
    # 2 of 3 metrics decay -> at quorum
    out = drift_monitor._detect_drift(
        pre={"a": 0.0, "b": 0.0, "c": 0.0},
        post_t5={"a": 1.0, "b": 1.0, "c": 1.0},
        current={"a": 0.0, "b": 0.0, "c": 1.0},  # "a", "b" decayed
        tolerance=0.5,
        quorum=0.5,
    )
    assert out["fired"] is True


# ---------------------------------------------------------------------------
# 9. Severity bucketing
# ---------------------------------------------------------------------------


def test_severity_warn_for_modest_decay(paths: dict[str, Path]) -> None:
    m = _make_monitor(paths)
    m.add_watch(
        mutation_id="m-warn",
        parameter="p",
        pre_metrics={"h": 0.5},
        post_metrics_t5={"h": 1.0},
        kept_at_cycle=0,
        original_mark_id="o",
    )
    # decay_ratio = 0.7 (below 1.0 threshold) -> warn
    m.tick(current_cycle=25, current_metrics={"h": 0.65})
    marks = _read_register_marks(paths["register_marks"])
    assert len(marks) == 1
    assert marks[0]["severity"] == "warn"


def test_severity_block_for_severe_decay(paths: dict[str, Path]) -> None:
    m = _make_monitor(paths)
    m.add_watch(
        mutation_id="m-block",
        parameter="p",
        pre_metrics={"h": 0.5},
        post_metrics_t5={"h": 1.0},
        kept_at_cycle=0,
        original_mark_id="o",
    )
    # decay_ratio approx 1.6 (way worse than baseline) -> block
    m.tick(current_cycle=25, current_metrics={"h": 0.20})
    marks = _read_register_marks(paths["register_marks"])
    assert len(marks) == 1
    assert marks[0]["severity"] == "block"


# ---------------------------------------------------------------------------
# 10. Persistence
# ---------------------------------------------------------------------------


def test_watches_rehydrate_on_construction(paths: dict[str, Path]) -> None:
    m1 = _make_monitor(paths)
    m1.add_watch(
        mutation_id="rehyd",
        parameter="p",
        pre_metrics={"h": 0.5},
        post_metrics_t5={"h": 0.8},
        kept_at_cycle=50,
        original_mark_id="o",
    )
    m2 = _make_monitor(paths)
    assert m2.watch_count() == 1


# ---------------------------------------------------------------------------
# 11. Eviction
# ---------------------------------------------------------------------------


def test_eviction_after_all_targets_fired(paths: dict[str, Path]) -> None:
    m = _make_monitor(paths, target_cycles=(25,))  # only one target
    m.add_watch(
        mutation_id="m-evict",
        parameter="p",
        pre_metrics={"h": 0.5},
        post_metrics_t5={"h": 0.85},
        kept_at_cycle=0,
        original_mark_id="o",
    )
    # Tick past T+25 with no decay
    m.tick(current_cycle=30, current_metrics={"h": 0.85})
    # Watch should be evicted (only target consumed)
    assert m.watch_count() == 0


def test_eviction_max_age(paths: dict[str, Path]) -> None:
    m = _make_monitor(paths)
    m.add_watch(
        mutation_id="m-old",
        parameter="p",
        pre_metrics={"h": 0.5},
        post_metrics_t5={"h": 0.85},
        kept_at_cycle=0,
        original_mark_id="o",
    )
    # Tick way beyond MAX_WATCH_AGE
    far = drift_monitor.MAX_WATCH_AGE + 100
    m.tick(current_cycle=far, current_metrics={"h": 0.85})
    assert m.watch_count() == 0


def test_remove_watch(paths: dict[str, Path]) -> None:
    m = _make_monitor(paths)
    m.add_watch(
        mutation_id="m-rm",
        parameter="p",
        pre_metrics={"h": 0.5},
        post_metrics_t5={"h": 0.85},
        kept_at_cycle=0,
        original_mark_id="o",
    )
    assert m.remove_watch("m-rm") is True
    assert m.watch_count() == 0
    # Removing a missing watch returns False
    assert m.remove_watch("nope") is False


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_no_common_metrics_does_not_crash(paths: dict[str, Path]) -> None:
    m = _make_monitor(paths)
    m.add_watch(
        mutation_id="m-disjoint",
        parameter="p",
        pre_metrics={"a": 0.5},
        post_metrics_t5={"a": 0.8},
        kept_at_cycle=0,
        original_mark_id="o",
    )
    # current has different keys
    produced = m.tick(current_cycle=25, current_metrics={"b": 0.99})
    assert produced == []  # no metrics in common; no fire
