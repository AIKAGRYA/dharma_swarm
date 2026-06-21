"""Frontier Council verifier (Stage 1): corroboration is earned by decorrelated
agreement on real evidence, never granted by confident prose. A poisoned signal
is quarantined; no receipt ever grants action authority; the verifier is pure
(mutates no owner). Hermetic — deterministic fixture evaluators, no network.
"""
from __future__ import annotations

import json

from dharma_swarm.world_radar.frontier_council import (
    CORROBORATED,
    INSUFFICIENT,
    QUARANTINED,
    REFUTED,
    EvidenceRef,
    FrontierCouncilInput,
    WorldSensemakingReceipt,
    evaluate_boundary_signal,
)


def _inp(refs, *, safe=True, instruction_risk="low", claim="GLM-5 hits 77.8% on SWE-bench"):
    return FrontierCouncilInput(
        claim=claim,
        evidence_refs=refs,
        input_signal_hash="sha256:test",
        safe=safe,
        instruction_risk=instruction_risk,
    )


def test_corroborated_with_two_decorrelated_families():
    refs = [
        EvidenceRef("arxiv", supports=True, quality=0.8),
        EvidenceRef("vendor_blog", supports=True, quality=0.7),
    ]
    r = evaluate_boundary_signal(_inp(refs))
    assert r.verdict == CORROBORATED
    assert r.corroboration_count >= 2
    assert r.source_family_count >= 2


def test_contradicted_is_refuted_or_insufficient():
    refs = [
        EvidenceRef("benchmark_audit", supports=False, quality=0.9),
        EvidenceRef("vendor_blog", supports=True, quality=0.6),
    ]
    assert evaluate_boundary_signal(_inp(refs)).verdict in (REFUTED, INSUFFICIENT)


def test_poisoned_signal_is_quarantined():
    r = evaluate_boundary_signal(_inp([EvidenceRef("x", True, 0.9)], instruction_risk="high"))
    assert r.verdict == QUARANTINED
    # unsafe envelope also quarantines
    assert evaluate_boundary_signal(_inp([EvidenceRef("x", True, 0.9)], safe=False)).verdict == QUARANTINED


def test_no_receipt_grants_action_authority():
    for refs, kw in [
        ([EvidenceRef("a", True, 0.8), EvidenceRef("b", True, 0.8)], {}),
        ([EvidenceRef("a", False, 0.9)], {}),
        ([EvidenceRef("x", True, 0.9)], {"instruction_risk": "high"}),
    ]:
        r = evaluate_boundary_signal(_inp(refs, **kw))
        assert r.no_action_authority is True
        assert r.dispatch_authority is False


def test_single_family_cannot_corroborate():
    # One source family, even high quality + many refs, is NOT corroboration.
    refs = [
        EvidenceRef("vendor_blog", supports=True, quality=0.95),
        EvidenceRef("vendor_blog", supports=True, quality=0.95),
    ]
    assert evaluate_boundary_signal(_inp(refs)).verdict == INSUFFICIENT


def test_confident_prose_cannot_upgrade_missing_corroboration():
    # The claim text is maximally confident; with one supporting family the
    # verdict stays insufficient — structure beats prose.
    refs = [EvidenceRef("press_release", supports=True, quality=1.0)]
    r = evaluate_boundary_signal(_inp(refs, claim="DEFINITIVELY PROVEN BEYOND ALL DOUBT"))
    assert r.verdict == INSUFFICIENT
    assert r.corroboration_count < 2 or r.source_family_count < 2


def test_receipt_serializes_and_replays():
    refs = [EvidenceRef("arxiv", True, 0.8), EvidenceRef("repro", True, 0.7)]
    r = evaluate_boundary_signal(_inp(refs))
    blob = json.loads(r.to_json())
    assert blob["verdict"] == CORROBORATED
    assert blob["no_action_authority"] is True and blob["dispatch_authority"] is False
    # deterministic: same input → same verdict + corroboration count
    r2 = evaluate_boundary_signal(_inp(refs))
    assert (r2.verdict, r2.corroboration_count) == (r.verdict, r.corroboration_count)


def test_verifier_is_pure_and_mutates_no_owner(tmp_path, monkeypatch):
    # Run from an empty cwd; assert the call writes nothing and returns a receipt.
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    r = evaluate_boundary_signal(_inp([EvidenceRef("a", True, 0.8), EvidenceRef("b", True, 0.8)]))
    assert isinstance(r, WorldSensemakingReceipt)
    assert set(tmp_path.iterdir()) == before  # no files written
