"""Falsifiable Holarchy primitive — deterministic E2E proof.

These tests use injected FAKE stateless workers (no live providers) so the whole
coordinator -> workers -> independent-receipts -> cross-falsify-verifier loop
runs deterministically and fast. The live path (provider_worker) is exercised
separately behind DHARMA_LIVE_MODEL_E2E.
"""

from __future__ import annotations

import pytest

from dharma_swarm.holarchy import (
    CrossFalsifyVerdict,
    default_normalize,
    provider_worker,
    run_cross_falsify,
)
from dharma_swarm.spine.receipt import EvidenceReceipt


def _ok_worker(worker_id: str, answer: str):
    async def _w(packet):
        return answer, EvidenceReceipt(
            agent_id=worker_id, status="ok", attributes={"worker_id": worker_id}
        )

    return worker_id, _w


def _failing_worker(worker_id: str):
    async def _w(packet):
        raise RuntimeError("provider unreachable")

    return worker_id, _w


async def test_converged_when_decorrelated_workers_agree():
    # Three decorrelated workers, different phrasings, same checkable answer.
    workers = [
        _ok_worker("a", "The answer is 42."),
        _ok_worker("b", "42"),
        _ok_worker("c", "Final answer: 42"),
    ]
    v = await run_cross_falsify("17*19 minus 281?", workers, quorum=2)
    assert v.verdict == "CONVERGED"
    assert v.converged is True
    assert v.modal_answer == "42"
    assert v.agreement == 1.0
    assert v.ok_count == 3 and v.failed_count == 0
    assert len(v.receipts) == 3


async def test_diverged_when_workers_disagree_holons_falsify_each_other():
    # Quorum returned ok, but they disagree -> the holons caught each other.
    workers = [
        _ok_worker("a", "42"),
        _ok_worker("b", "41"),
        _ok_worker("c", "43"),
    ]
    v = await run_cross_falsify("a contested question", workers, quorum=2)
    assert v.verdict == "DIVERGED"
    assert v.converged is False
    assert v.ok_count == 3
    # No answer reaches the agreement threshold -> not converged, but it is a
    # complete, honest run (the cross-check did its job).
    assert v.agreement < 0.66


async def test_inconclusive_is_not_a_coherence_claim_on_infra_failure():
    # Only one worker returns ok; the check could not run with enough sources.
    workers = [
        _ok_worker("a", "42"),
        _failing_worker("b"),
        _failing_worker("c"),
    ]
    v = await run_cross_falsify("anything", workers, quorum=2)
    assert v.verdict == "INCONCLUSIVE"
    assert v.converged is False
    assert v.ok_count == 1 and v.failed_count == 2
    # The failing workers still produced independent receipts (auditable).
    assert sum(1 for r in v.receipts if r.status == "failed") == 2


async def test_majority_converges_over_a_single_dissenter():
    workers = [
        _ok_worker("a", "yes"),
        _ok_worker("b", "yes"),
        _ok_worker("c", "yes"),
        _ok_worker("d", "no"),
    ]
    v = await run_cross_falsify("majority case", workers, quorum=2)
    assert v.verdict == "CONVERGED"
    assert v.modal_answer == "yes"
    assert v.agreement == pytest.approx(0.75)


async def test_quorum_below_two_is_rejected():
    with pytest.raises(ValueError):
        await run_cross_falsify("x", [_ok_worker("a", "1")], quorum=1)


def test_normalize_collapses_decorrelated_phrasings():
    assert default_normalize("The integer result is 323") == "323"
    assert default_normalize("  PONG  ") == "pong"
    assert default_normalize("Answer: yes.") == "yes"


def test_provider_worker_builds_a_labeled_stateless_worker():
    # Construction only (no live call): proves the live factory wires a worker id.
    wid, worker = provider_worker("nvidia/nemotron-3-ultra-550b-a55b")
    assert wid == "nim:nvidia/nemotron-3-ultra-550b-a55b"
    assert callable(worker)
