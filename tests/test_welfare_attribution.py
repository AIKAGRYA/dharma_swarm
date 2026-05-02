"""Tests for dharma_swarm.welfare_attribution (Component 1.6).

Covers:
1. Cold-path: empty proposals -> empty attribution, full unattributed.
2. Single high-overlap proposal -> attribution.weight = 1.0.
3. Multiple proposals normalized to weights summing to 1.0.
4. Attribution-floor filters low-directness candidates.
5. Negative welfare score (carbon went up) -> negative delta_applied.
6. Delta clamp prevents single-cert from swinging fitness > 0.10.
7. Persistence + apply_attribution_to_proposals mutates fitness field.
8. Goodhart firewall: register_link alone caps at 20% directness.
9. Robustness: missing fields, bad timestamps don't crash.
10. JSON round-trip via to_dict.

Run: pytest tests/test_welfare_attribution.py -q
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm import welfare_attribution


# ---------------------------------------------------------------------------
# Test doubles (duck-typed Certificate / Proposal)
# ---------------------------------------------------------------------------


@dataclass
class MockCertificate:
    certificate_id: str
    issued_at: str
    domain: str = "composite"
    project_id: str = "PROJ-001"
    project_code_paths: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    outcome: dict[str, float] = field(default_factory=dict)


@dataclass
class MockProposal:
    id: str
    component: str = ""
    description: str = ""
    affected_files: list[str] = field(default_factory=list)
    decision_at: str = ""
    fitness_after_deployment: list[dict] = field(default_factory=list)
    jagat_kalyan_register_links: list[str] = field(default_factory=list)


def _now_iso(offset_days: float = 0.0) -> str:
    base = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(days=offset_days)).isoformat()


# ---------------------------------------------------------------------------
# 1. Empty proposals
# ---------------------------------------------------------------------------


def test_empty_proposals_full_unattributed() -> None:
    cert = MockCertificate(
        certificate_id="CERT-001",
        issued_at=_now_iso(0),
        outcome={"carbon_kgco2e": 1500.0},
    )
    record = welfare_attribution.attribute_certificate(
        cert,
        candidate_proposals=[],
        now=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert record.attributions == []
    # Welfare score is positive (carbon reduction), so unattributed_delta > 0
    assert record.unattributed_delta == pytest.approx(record.total_welfare_score)
    assert record.total_welfare_score > 0


# ---------------------------------------------------------------------------
# 2. Single high-overlap proposal
# ---------------------------------------------------------------------------


def test_single_high_overlap_full_weight() -> None:
    cert = MockCertificate(
        certificate_id="CERT-002",
        issued_at=_now_iso(0),
        project_code_paths=["dharma_swarm/foo.py"],
        outcome={"carbon_kgco2e": 800.0},
    )
    prop = MockProposal(
        id="PROP-A",
        affected_files=["dharma_swarm/foo.py"],
        decision_at=_now_iso(-5),
    )
    record = welfare_attribution.attribute_certificate(
        cert,
        candidate_proposals=[prop],
        now=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert len(record.attributions) == 1
    assert record.attributions[0].weight == pytest.approx(1.0, abs=0.01)
    assert record.attributions[0].directness > welfare_attribution.ATTRIBUTION_FLOOR


# ---------------------------------------------------------------------------
# 3. Multiple proposals normalized
# ---------------------------------------------------------------------------


def test_multiple_proposals_weights_sum_to_one() -> None:
    cert = MockCertificate(
        certificate_id="CERT-003",
        issued_at=_now_iso(0),
        project_code_paths=["dharma_swarm/bar.py"],
        outcome={"livelihood_usd": 6000.0},
    )
    p1 = MockProposal(
        id="P1",
        affected_files=["dharma_swarm/bar.py"],
        decision_at=_now_iso(-3),
    )
    p2 = MockProposal(
        id="P2",
        affected_files=["dharma_swarm/bar.py"],
        decision_at=_now_iso(-10),
    )
    record = welfare_attribution.attribute_certificate(
        cert,
        candidate_proposals=[p1, p2],
        now=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert len(record.attributions) == 2
    total_weight = sum(a.weight for a in record.attributions)
    assert total_weight == pytest.approx(1.0, abs=0.01)
    # P1 closer in time -> larger weight
    p1_attr = next(a for a in record.attributions if a.proposal_id == "P1")
    p2_attr = next(a for a in record.attributions if a.proposal_id == "P2")
    assert p1_attr.weight > p2_attr.weight


# ---------------------------------------------------------------------------
# 4. Attribution floor filters
# ---------------------------------------------------------------------------


def test_attribution_floor_drops_low_directness() -> None:
    cert = MockCertificate(
        certificate_id="CERT-004",
        issued_at=_now_iso(0),
        project_code_paths=["dharma_swarm/exact_match_path.py"],
        outcome={"carbon_kgco2e": 1000.0},
    )
    # Decision is OLD (low temporal_proximity) and unrelated path
    weak = MockProposal(
        id="WEAK",
        affected_files=["dashboard/something_unrelated.tsx"],
        decision_at=_now_iso(-180),
    )
    record = welfare_attribution.attribute_certificate(
        cert,
        candidate_proposals=[weak],
        now=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert record.attributions == []
    assert "below attribution_floor" in (record.notes[0] if record.notes else "")


# ---------------------------------------------------------------------------
# 5. Negative outcome propagates negative delta
# ---------------------------------------------------------------------------


def test_negative_carbon_outcome_negative_delta() -> None:
    # Negative carbon_kgco2e (sign convention: + = reduction) means emissions
    # increased. After applying DIMENSION_SIGNS this should yield a NEGATIVE
    # signed score.
    cert = MockCertificate(
        certificate_id="CERT-NEG",
        issued_at=_now_iso(0),
        project_code_paths=["dharma_swarm/baz.py"],
        outcome={"carbon_kgco2e": -2000.0},  # emissions WORSENED
    )
    prop = MockProposal(
        id="P-NEG",
        affected_files=["dharma_swarm/baz.py"],
        decision_at=_now_iso(-2),
    )
    record = welfare_attribution.attribute_certificate(
        cert,
        candidate_proposals=[prop],
        now=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert record.total_welfare_score < 0
    assert record.attributions[0].delta_applied < 0


# ---------------------------------------------------------------------------
# 6. Delta clamp (Goodhart firewall)
# ---------------------------------------------------------------------------


def test_delta_clamped_to_floor_ceiling() -> None:
    # Massive welfare score; verify single attribution is clamped to ±DELTA_CLAMP
    cert = MockCertificate(
        certificate_id="CERT-BIG",
        issued_at=_now_iso(0),
        project_code_paths=["dharma_swarm/big.py"],
        outcome={
            "carbon_kgco2e": 999_999.0,
            "livelihood_usd": 999_999.0,
        },
    )
    prop = MockProposal(
        id="P-BIG",
        affected_files=["dharma_swarm/big.py"],
        decision_at=_now_iso(0),
        # All four signals max
        jagat_kalyan_register_links=["PROJ-001"],
    )
    cert.evidence = ["P-BIG"]  # cited
    record = welfare_attribution.attribute_certificate(
        cert,
        candidate_proposals=[prop],
        now=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert len(record.attributions) == 1
    assert abs(record.attributions[0].delta_applied) <= welfare_attribution.DELTA_CLAMP + 1e-6


# ---------------------------------------------------------------------------
# 7. apply_attribution_to_proposals + persistence
# ---------------------------------------------------------------------------


def test_apply_attribution_mutates_fitness_field() -> None:
    cert = MockCertificate(
        certificate_id="CERT-AP",
        issued_at=_now_iso(0),
        project_code_paths=["dharma_swarm/qux.py"],
        outcome={"carbon_kgco2e": 1200.0},
    )
    prop = MockProposal(
        id="P-AP",
        affected_files=["dharma_swarm/qux.py"],
        decision_at=_now_iso(-5),
    )
    record = welfare_attribution.attribute_certificate(
        cert,
        candidate_proposals=[prop],
        now=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    mutated = welfare_attribution.apply_attribution_to_proposals(
        record, {"P-AP": prop},
    )
    assert mutated == ["P-AP"]
    assert len(prop.fitness_after_deployment) == 1
    entry = prop.fitness_after_deployment[0]
    assert entry["certificate_id"] == "CERT-AP"
    assert "delta_applied" in entry


def test_apply_attribution_skips_missing_proposals() -> None:
    cert = MockCertificate(
        certificate_id="CERT-MISS",
        issued_at=_now_iso(0),
        project_code_paths=["dharma_swarm/x.py"],
        outcome={"carbon_kgco2e": 500.0},
    )
    prop = MockProposal(
        id="P-MISS",
        affected_files=["dharma_swarm/x.py"],
        decision_at=_now_iso(0),
    )
    record = welfare_attribution.attribute_certificate(
        cert,
        candidate_proposals=[prop],
        now=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    # Empty proposals_by_id map
    mutated = welfare_attribution.apply_attribution_to_proposals(record, {})
    assert mutated == []


def test_persist_attribution_round_trip(tmp_path: Path) -> None:
    log = tmp_path / "attribution_log.jsonl"
    cert = MockCertificate(
        certificate_id="CERT-PERSIST",
        issued_at=_now_iso(0),
        outcome={"carbon_kgco2e": 1000.0},
    )
    record = welfare_attribution.attribute_certificate(
        cert,
        candidate_proposals=[],
        now=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    ok = welfare_attribution.persist_attribution(record, log_path=log)
    assert ok is True
    line = log.read_text().strip()
    parsed = json.loads(line)
    assert parsed["certificate_id"] == "CERT-PERSIST"


# ---------------------------------------------------------------------------
# 8. Goodhart firewall: register_link alone is bounded
# ---------------------------------------------------------------------------


def test_register_link_alone_below_floor() -> None:
    # Only register_link signal fires (weight 0.20 in composite). With
    # zero on the other three components, directness = 0.20.
    # ATTRIBUTION_FLOOR = 0.15, so it BARELY qualifies. Verify weight
    # is bounded.
    cert = MockCertificate(
        certificate_id="CERT-RL",
        issued_at=_now_iso(0),
        project_id="PROJ-RL",
        project_code_paths=["dharma_swarm/unrelated.py"],  # no overlap
        outcome={"carbon_kgco2e": 1000.0},
    )
    prop = MockProposal(
        id="P-RL",
        affected_files=["other/path.py"],  # zero topical overlap
        decision_at=_now_iso(-200),  # negligible temporal proximity
        jagat_kalyan_register_links=["PROJ-RL"],  # this fires
    )
    record = welfare_attribution.attribute_certificate(
        cert,
        candidate_proposals=[prop],
        now=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    # Even if it qualifies, its directness should not exceed 0.20 + tiny
    # temporal contribution
    if record.attributions:
        assert record.attributions[0].directness <= 0.21


# ---------------------------------------------------------------------------
# 9. Robustness
# ---------------------------------------------------------------------------


def test_bad_timestamp_skipped() -> None:
    cert = MockCertificate(
        certificate_id="CERT-BAD",
        issued_at=_now_iso(0),
        project_code_paths=["dharma_swarm/y.py"],
        outcome={"carbon_kgco2e": 500.0},
    )
    prop = MockProposal(
        id="P-BAD",
        affected_files=["dharma_swarm/y.py"],
        decision_at="not a timestamp",
    )
    record = welfare_attribution.attribute_certificate(
        cert,
        candidate_proposals=[prop],
        now=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    # Bad ts dropped silently
    assert record.attributions == []


def test_unknown_outcome_dimension_skipped() -> None:
    cert = MockCertificate(
        certificate_id="CERT-UNK",
        issued_at=_now_iso(0),
        outcome={"unknown_metric": 999.0},
    )
    record = welfare_attribution.attribute_certificate(
        cert,
        candidate_proposals=[],
        now=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    # Unknown dimensions yield 0 score
    assert record.total_welfare_score == 0.0


# ---------------------------------------------------------------------------
# 10. JSON round-trip
# ---------------------------------------------------------------------------


def test_to_dict_json_safe() -> None:
    cert = MockCertificate(
        certificate_id="CERT-JSON",
        issued_at=_now_iso(0),
        project_code_paths=["dharma_swarm/z.py"],
        outcome={"carbon_kgco2e": 1000.0, "biodiversity_index": 0.10},
    )
    prop = MockProposal(
        id="P-JSON",
        affected_files=["dharma_swarm/z.py"],
        decision_at=_now_iso(-3),
    )
    record = welfare_attribution.attribute_certificate(
        cert,
        candidate_proposals=[prop],
        now=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    s = json.dumps(record.to_dict())
    parsed = json.loads(s)
    assert parsed["certificate_id"] == "CERT-JSON"
    assert "attributions" in parsed
