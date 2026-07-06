"""U5 falsification benchmark — leaf tampering must be caught.

This is the Phase 0 acceptance test called out in
`specs/TITANIUM_TELOS_GATES_SPEC_v3.md` §U5 and §8 Phase 0.
"""
from __future__ import annotations

import random

from telos_kernel.merkle_log import MemoryBackend, MerkleLog


def test_random_leaf_tamper_always_caught():
    """For every index k, tampering leaf k must yield (False, k) from verify."""
    rng = random.Random(1729)
    for trial in range(20):
        log = MerkleLog(backend=MemoryBackend())
        n = rng.randint(3, 15)
        for i in range(n):
            log.append({"trial": trial, "i": i, "salt": rng.randint(0, 1_000_000)})

        # Pre-tamper: chain valid.
        ok, first_broken = log.verify_chain()
        assert ok and first_broken is None

        # Tamper at a random index.
        k = rng.randint(0, n - 1)
        original = log.hashes[k]
        tampered = bytes((b ^ 0xFF) for b in original)
        log.hashes[k] = tampered

        ok, first_broken = log.verify_chain()
        assert not ok, f"trial={trial}: tamper at {k} was NOT detected"
        assert first_broken == k, (
            f"trial={trial}: expected first_broken={k}, got {first_broken}"
        )


def test_payload_tamper_caught():
    """Modifying a stored payload must break the chain at that index."""
    log = MerkleLog(backend=MemoryBackend())
    for i in range(5):
        log.append({"i": i})
    log._payloads[3] = {"i": 999}
    ok, first_broken = log.verify_chain()
    assert not ok
    assert first_broken == 3


def test_reorder_tamper_caught():
    """Swapping two stored payloads must break the chain at the earliest swap."""
    log = MerkleLog(backend=MemoryBackend())
    for i in range(5):
        log.append({"i": i})
    log._payloads[1], log._payloads[3] = log._payloads[3], log._payloads[1]
    ok, first_broken = log.verify_chain()
    assert not ok
    assert first_broken == 1
