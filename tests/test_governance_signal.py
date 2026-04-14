"""Tests for governance_signal — the Shakti executive → dispatch binding overlay."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from dharma_swarm.governance_signal import (
    GovernanceSnapshot,
    governance_multiplier,
    invalidate_cache,
    load_governance,
    reorder_by_governance,
)


class StubTask:
    """Minimal duck-type of dharma_swarm.models.Task."""

    def __init__(
        self,
        tid: str,
        title: str = "",
        description: str = "",
        domain: str | None = None,
        linked_promise: str | None = None,
        directed: bool = False,
    ) -> None:
        self.id = tid
        self.title = title
        self.description = description
        self.metadata: dict[str, object] = {}
        if domain:
            self.metadata["domain"] = domain
        if linked_promise:
            self.metadata["linked_promise"] = linked_promise
        if directed:
            self.metadata["directed"] = True


@pytest.fixture
def meta_dir(tmp_path: Path) -> Path:
    d = tmp_path / "meta"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _flush_cache():
    invalidate_cache()
    yield
    invalidate_cache()


def _write_alloc(meta_dir: Path, per_domain: dict[str, float], **extra) -> None:
    payload = {"per_domain": per_domain, **extra}
    (meta_dir / "allocation_weights.json").write_text(json.dumps(payload))


def test_load_governance_missing_returns_neutral_snapshot(meta_dir: Path) -> None:
    snap = load_governance(meta_dir=meta_dir, force=True)
    assert snap.is_stale is True
    assert snap.per_domain["research"] == pytest.approx(0.125)


def test_load_governance_populates_all_fields(meta_dir: Path) -> None:
    _write_alloc(
        meta_dir,
        {"reliability": 0.25, "internal_maintenance": 0.05},
        starvation_boosts={"reliability": 0.15},
        churn_penalties={"internal_maintenance": 0.20},
    )
    (meta_dir / "disagreement_quarantine.json").write_text(
        json.dumps({"topics": ["eval_probe_loop"]}),
    )
    (meta_dir / "promise_pressure.json").write_text(
        json.dumps({"promises": [{"id": "promise_x", "urgency": 0.5}]}),
    )
    (meta_dir / "challenge_pressure.json").write_text(
        json.dumps({"per_domain": {"artifact_publication": 0.4}}),
    )
    (meta_dir / "active_campaigns.json").write_text(
        json.dumps([{"campaign_id": "c1", "domain": "productization"}]),
    )

    snap = load_governance(meta_dir=meta_dir, force=True)
    assert snap.is_stale is False
    assert snap.starvation_boosts["reliability"] == pytest.approx(0.15)
    assert "eval_probe_loop" in snap.quarantine_topics
    assert snap.promise_pressure["promise_x"] == pytest.approx(0.5)
    assert snap.challenge_multiplier["artifact_publication"] == pytest.approx(0.4)
    assert "productization" in snap.active_campaign_domains


def test_multiplier_directed_override_wins(meta_dir: Path) -> None:
    _write_alloc(meta_dir, {d: 0.125 for d in [
        "internal_maintenance", "reliability", "research",
        "artifact_publication", "productization", "ecosystem_scan",
        "revenue_exploration", "strategic_infrastructure",
    ]})
    snap = load_governance(meta_dir=meta_dir, force=True)
    task = StubTask("t", "x", directed=True)
    m, reasons = governance_multiplier(task, snap)
    assert math.isinf(m)
    assert "directed_override" in reasons


def test_multiplier_quarantine_yields_zero(meta_dir: Path) -> None:
    _write_alloc(meta_dir, {d: 0.125 for d in [
        "internal_maintenance", "reliability", "research",
        "artifact_publication", "productization", "ecosystem_scan",
        "revenue_exploration", "strategic_infrastructure",
    ]})
    (meta_dir / "disagreement_quarantine.json").write_text(
        json.dumps({"topics": ["latent_followup_loop"]}),
    )
    snap = load_governance(meta_dir=meta_dir, force=True)
    task = StubTask("q", title="reopen latent_followup_loop synthesis")
    m, reasons = governance_multiplier(task, snap)
    assert m == 0.0
    assert "quarantine_skip" in reasons


def test_multiplier_clamped_to_bounds(meta_dir: Path) -> None:
    _write_alloc(
        meta_dir,
        {"reliability": 0.8, "internal_maintenance": 0.01,
         "research": 0.125, "artifact_publication": 0.125,
         "productization": 0.125, "ecosystem_scan": 0.125,
         "revenue_exploration": 0.125, "strategic_infrastructure": 0.125},
        starvation_boosts={"reliability": 1.0},
        churn_penalties={"internal_maintenance": 2.0},
    )
    snap = load_governance(meta_dir=meta_dir, force=True)

    hi = governance_multiplier(StubTask("hi", domain="reliability"), snap)[0]
    lo = governance_multiplier(StubTask("lo", domain="internal_maintenance"), snap)[0]
    assert hi == pytest.approx(2.0)  # clamp max
    assert lo == pytest.approx(0.5)  # clamp min


def test_active_campaign_suppresses_starvation_boost(meta_dir: Path) -> None:
    _write_alloc(
        meta_dir,
        {d: 0.125 for d in ["internal_maintenance", "reliability", "research",
                             "artifact_publication", "productization",
                             "ecosystem_scan", "revenue_exploration",
                             "strategic_infrastructure"]} | {"reliability": 0.05},
        starvation_boosts={"reliability": 0.20},
    )
    (meta_dir / "active_campaigns.json").write_text(
        json.dumps([{"campaign_id": "cov", "domain": "reliability"}]),
    )
    snap = load_governance(meta_dir=meta_dir, force=True)
    m, reasons = governance_multiplier(StubTask("r", domain="reliability"), snap)
    assert "campaign_active_no_starve_boost" in reasons
    # No starvation-boost reason should appear (the suppression message is distinct).
    assert not any(r.startswith("starv(") for r in reasons)
    assert m <= 1.0  # no boost → below neutral


def test_promise_linked_boost(meta_dir: Path) -> None:
    _write_alloc(meta_dir, {d: 0.125 for d in [
        "internal_maintenance", "reliability", "research",
        "artifact_publication", "productization", "ecosystem_scan",
        "revenue_exploration", "strategic_infrastructure",
    ]})
    (meta_dir / "promise_pressure.json").write_text(
        json.dumps({"promises": [{"id": "promise_p", "urgency": 0.4}]}),
    )
    snap = load_governance(meta_dir=meta_dir, force=True)
    linked = StubTask("p", domain="research", linked_promise="promise_p")
    unlinked = StubTask("u", domain="research")
    ml = governance_multiplier(linked, snap)[0]
    mu = governance_multiplier(unlinked, snap)[0]
    assert ml > mu


def test_reorder_disabled_when_flag_off(meta_dir: Path, monkeypatch) -> None:
    monkeypatch.setenv("DGC_GOVERNANCE_OVERLAY", "0")
    _write_alloc(meta_dir, {d: 0.125 for d in [
        "internal_maintenance", "reliability", "research",
        "artifact_publication", "productization", "ecosystem_scan",
        "revenue_exploration", "strategic_infrastructure",
    ]})
    tasks = [StubTask(str(i), domain="research") for i in range(3)]
    out, reasons = reorder_by_governance(tasks)
    assert [t.id for t in out] == ["0", "1", "2"]
    assert reasons == []


def test_reorder_enabled_respects_priority(meta_dir: Path, monkeypatch) -> None:
    monkeypatch.setenv("DGC_GOVERNANCE_OVERLAY", "1")
    _write_alloc(
        meta_dir,
        {"reliability": 0.25, "internal_maintenance": 0.05,
         "research": 0.125, "artifact_publication": 0.125,
         "productization": 0.125, "ecosystem_scan": 0.125,
         "revenue_exploration": 0.125, "strategic_infrastructure": 0.125},
        starvation_boosts={"reliability": 0.10},
        churn_penalties={"internal_maintenance": 0.15},
    )
    snap = load_governance(meta_dir=meta_dir, force=True)
    tasks = [
        StubTask("lo", domain="internal_maintenance"),
        StubTask("mid", domain="research"),
        StubTask("hi", domain="reliability"),
        StubTask("dir", directed=True),
    ]
    out, reasons = reorder_by_governance(tasks, snap)
    assert out[0].id == "dir"
    assert out[1].id == "hi"
    # internal_maintenance should be last (most penalised of the non-directed)
    assert out[-1].id == "lo"
    assert any("directed" in r for r in reasons)


def test_reorder_never_drops_quarantined(meta_dir: Path, monkeypatch) -> None:
    monkeypatch.setenv("DGC_GOVERNANCE_OVERLAY", "1")
    _write_alloc(meta_dir, {d: 0.125 for d in [
        "internal_maintenance", "reliability", "research",
        "artifact_publication", "productization", "ecosystem_scan",
        "revenue_exploration", "strategic_infrastructure",
    ]})
    (meta_dir / "disagreement_quarantine.json").write_text(
        json.dumps({"topics": ["blocked_topic"]}),
    )
    snap = load_governance(meta_dir=meta_dir, force=True)
    tasks = [
        StubTask("normal", domain="research"),
        StubTask("q", title="resolve blocked_topic disagreement"),
    ]
    out, _ = reorder_by_governance(tasks, snap)
    assert {t.id for t in out} == {"normal", "q"}  # invariant: no drops
    assert out[-1].id == "q"  # quarantined demoted, not dropped


def test_cache_reuses_snapshot(meta_dir: Path, monkeypatch) -> None:
    _write_alloc(meta_dir, {d: 0.125 for d in [
        "internal_maintenance", "reliability", "research",
        "artifact_publication", "productization", "ecosystem_scan",
        "revenue_exploration", "strategic_infrastructure",
    ]})
    s1 = load_governance(meta_dir=meta_dir, force=True)
    s2 = load_governance(meta_dir=meta_dir)  # cached path
    assert s1 is s2
