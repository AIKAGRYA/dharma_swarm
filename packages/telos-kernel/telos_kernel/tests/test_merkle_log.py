"""Merkle chain: append, verify, prev-root binding, backends."""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from telos_kernel.merkle_log import (
    GENESIS_HASH,
    FileBackend,
    MemoryBackend,
    MerkleLog,
    _compute_leaf_hash,
    verify_merkle_inclusion,
)


class TestAppendAndVerify:
    def test_empty_chain_verifies(self, memory_log):
        ok, first_broken = memory_log.verify_chain()
        assert ok
        assert first_broken is None

    def test_single_append(self, memory_log):
        root = memory_log.append({"gate": "test", "n": 1})
        assert len(root) == 64
        assert memory_log.head_hash() == root
        ok, first_broken = memory_log.verify_chain()
        assert ok
        assert first_broken is None

    def test_multiple_appends_chain(self, memory_log):
        roots = [memory_log.append({"n": i}) for i in range(5)]
        assert len(set(roots)) == 5  # all distinct
        ok, first_broken = memory_log.verify_chain()
        assert ok
        assert first_broken is None
        assert memory_log.get_chain_length() == 5

    def test_prev_root_binding(self, memory_log):
        """h_i = SHA-256(h_{i-1} || JCS(payload_i)) — verify explicitly."""
        from telos_kernel.canonical import canonicalize

        memory_log.append({"n": 1})
        expected = _compute_leaf_hash(GENESIS_HASH, canonicalize({"n": 1}))
        assert memory_log.hashes[0] == expected

        memory_log.append({"n": 2})
        expected2 = _compute_leaf_hash(expected, canonicalize({"n": 2}))
        assert memory_log.hashes[1] == expected2

    def test_verify_with_data_legacy_path(self, memory_log):
        memory_log.append({"n": 1})
        memory_log.append({"n": 2})
        ok, idx = memory_log.verify_with_data([{"n": 1}, {"n": 2}])
        assert ok
        assert idx == 2

    def test_verify_with_data_length_mismatch(self, memory_log):
        memory_log.append({"n": 1})
        with pytest.raises(ValueError):
            memory_log.verify_with_data([{"n": 1}, {"n": 2}])


class TestTamperDetection:
    """Falsification for U5 — spec §U5 explicitly requires this test."""

    def test_tamper_at_index_zero_caught(self, memory_log):
        memory_log.append({"n": 1})
        memory_log.append({"n": 2})
        # Directly mutate the stored hash. `verify_chain` uses the internally
        # stored payloads; changing a stored hash must break at index 0.
        memory_log.hashes[0] = b"\xff" * 32
        ok, first_broken = memory_log.verify_chain()
        assert not ok
        assert first_broken == 0

    def test_tamper_at_middle_index_caught(self, memory_log):
        for i in range(5):
            memory_log.append({"n": i})
        memory_log.hashes[2] = b"\xaa" * 32
        ok, first_broken = memory_log.verify_chain()
        assert not ok
        assert first_broken == 2

    def test_tamper_via_payload_swap(self, memory_log):
        memory_log.append({"n": 1})
        memory_log.append({"n": 2})
        memory_log._payloads[0] = {"n": 999}
        ok, first_broken = memory_log.verify_chain()
        assert not ok
        assert first_broken == 0

    def test_load_quarantines_broken_chain(self, tmp_path):
        # Build a chain, tamper the file, reload — must enter quarantine.
        p = tmp_path / "chain.json"
        log = MerkleLog(backend=FileBackend(p))
        log.append({"n": 1})
        log.append({"n": 2})

        # Corrupt the on-disk hash directly.
        import json
        with open(p) as f:
            data = json.load(f)
        data["hashes"][0] = "ff" * 32
        with open(p, "w") as f:
            json.dump(data, f)

        # Reload — kernel must set quarantined=True (not raise).
        log2 = MerkleLog(backend=FileBackend(p))
        assert log2.quarantined is True


class TestFileBackendRoundtrip:
    def test_persists_and_reloads(self, tmp_path):
        p = tmp_path / "chain.json"
        log = MerkleLog(backend=FileBackend(p))
        r1 = log.append({"n": 1})
        r2 = log.append({"n": 2})

        log2 = MerkleLog(backend=FileBackend(p))
        assert log2.hashes[-1].hex() == r2
        assert not log2.quarantined
        ok, _ = log2.verify_chain()
        assert ok


class TestInclusion:
    def test_valid_inclusion(self, memory_log):
        r = memory_log.append({"n": 1})
        assert verify_merkle_inclusion({"n": 1}, 0, r, memory_log)

    def test_wrong_index_rejected(self, memory_log):
        r = memory_log.append({"n": 1})
        assert not verify_merkle_inclusion({"n": 1}, 5, r, memory_log)

    def test_wrong_root_rejected(self, memory_log):
        memory_log.append({"n": 1})
        assert not verify_merkle_inclusion({"n": 1}, 0, "f" * 64, memory_log)


class TestPropertyRoundtrip:
    """Hypothesis: appending N distinct payloads to an empty chain always
    yields a fully-verifiable chain of length N with N distinct roots."""

    @given(st.lists(
        st.dictionaries(
            st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122),
                    min_size=1, max_size=6),
            st.integers(min_value=-100, max_value=100),
            max_size=4,
        ),
        min_size=1, max_size=15,
    ))
    @settings(max_examples=50, deadline=None)
    def test_append_verify_property(self, payloads):
        log = MerkleLog(backend=MemoryBackend())
        roots = [log.append(p) for p in payloads]
        assert len(roots) == len(payloads)
        ok, first_broken = log.verify_chain()
        assert ok, f"chain broke at {first_broken}"
