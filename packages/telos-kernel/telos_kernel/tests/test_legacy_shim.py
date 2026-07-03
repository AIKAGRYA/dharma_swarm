"""Verify the `dharma_swarm.merkle_log` shim preserves legacy API contracts.

Legacy callers expect:
  * `MerkleLog(log_file=...)` constructor
  * `append(dict) -> hex str`
  * `verify_chain(data_store=None) -> (bool, int)` where int == len(hashes) on success
  * `verify_with_data(data_store) -> (bool, int)`
  * `get_root()`, `get_chain_length()`
  * top-level `verify_merkle_inclusion(...)`

The kernel MerkleLog changed the `verify_chain` success return shape to
`(True, None)` per spec §U5; the shim class overrides `verify_chain` to
preserve the legacy shape.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Legacy import path: dharma_swarm/merkle_log.py — put dharma_swarm on sys.path.
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))


def test_legacy_import_still_works():
    from dharma_swarm.merkle_log import MerkleLog, verify_merkle_inclusion  # noqa: F401


def test_legacy_verify_chain_returns_len_on_success(tmp_path):
    from dharma_swarm.merkle_log import MerkleLog
    log = MerkleLog(log_file=tmp_path / "chain.json")
    log.append({"n": 1})
    log.append({"n": 2})
    ok, idx = log.verify_chain()
    assert ok
    # Legacy shape: idx == len(hashes) on success.
    assert idx == 2


def test_legacy_verify_chain_returns_break_index_on_tamper(tmp_path):
    from dharma_swarm.merkle_log import MerkleLog
    log = MerkleLog(log_file=tmp_path / "chain.json")
    log.append({"n": 1})
    log.append({"n": 2})
    log.hashes[0] = b"\xff" * 32
    ok, idx = log.verify_chain()
    assert not ok
    assert idx == 0


def test_legacy_verify_with_data(tmp_path):
    from dharma_swarm.merkle_log import MerkleLog
    log = MerkleLog(log_file=tmp_path / "chain.json")
    log.append({"n": 1})
    log.append({"n": 2})
    ok, idx = log.verify_with_data([{"n": 1}, {"n": 2}])
    assert ok
    assert idx == 2


def test_legacy_get_root_and_length(tmp_path):
    from dharma_swarm.merkle_log import MerkleLog
    log = MerkleLog(log_file=tmp_path / "chain.json")
    assert log.get_root() is None
    assert log.get_chain_length() == 0
    r = log.append({"n": 1})
    assert log.get_root() == r
    assert log.get_chain_length() == 1
