"""MerkleLog must fail verify on a truncated or corrupt on-disk log.

Previously ``_load`` caught any parse error and silently reset the chain to
empty, after which ``verify_chain`` reported ``(True, 0)`` — a clean bill of
health for an erased or truncated evolution ledger. That violates the
Certificate Transparency / Sigstore "no silent truncation" pedigree the
module's own docstring claims. A corrupt log must now fail closed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.merkle_log import MerkleLog


def _populated_log(path: Path) -> MerkleLog:
    log = MerkleLog(path)
    log.append({"mutation": "add docstring", "id": "001"})
    log.append({"mutation": "optimize loop", "id": "002"})
    log.append({"mutation": "add type hints", "id": "003"})
    return log


def test_absent_log_is_valid_empty(tmp_path: Path) -> None:
    log = MerkleLog(tmp_path / "never_written.json")
    valid, idx = log.verify_chain()
    assert valid and idx == 0


def test_byte_truncated_log_fails_verify(tmp_path: Path) -> None:
    path = tmp_path / "merkle.json"
    _populated_log(path)
    raw = path.read_bytes()
    # Chop the tail so the on-disk JSON no longer parses (a torn write).
    path.write_bytes(raw[: len(raw) // 2])

    reloaded = MerkleLog(path)
    valid, idx = reloaded.verify_chain()
    assert valid is False and idx == 0, "truncated log must fail closed, not clean-empty"


def test_nonjson_corrupt_log_fails_verify(tmp_path: Path) -> None:
    path = tmp_path / "merkle.json"
    _populated_log(path)
    path.write_text("this is not json at all", encoding="utf-8")

    reloaded = MerkleLog(path)
    assert reloaded.verify_chain() == (False, 0)


def test_entry_truncation_with_stale_count_fails_verify(tmp_path: Path) -> None:
    path = tmp_path / "merkle.json"
    _populated_log(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    # Valid JSON, but trailing entries were dropped while the recorded count was
    # left intact — the silent-truncation case a plain JSON parse cannot catch.
    data["hashes"] = data["hashes"][:-1]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    reloaded = MerkleLog(path)
    assert reloaded.verify_chain() == (False, 0)


def test_append_to_corrupt_log_does_not_overwrite_evidence(tmp_path: Path) -> None:
    path = tmp_path / "merkle.json"
    _populated_log(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["hashes"] = data["hashes"][:-1]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    corrupt_bytes = path.read_bytes()

    reloaded = MerkleLog(path)
    assert reloaded.verify_chain() == (False, 0)
    with pytest.raises(ValueError, match="cannot append to corrupt Merkle log"):
        reloaded.append({"mutation": "erase corrupt state"})

    assert path.read_bytes() == corrupt_bytes
    assert MerkleLog(path).verify_chain() == (False, 0)


def test_bad_hex_hash_fails_verify(tmp_path: Path) -> None:
    path = tmp_path / "merkle.json"
    _populated_log(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["hashes"][1] = "zzzz"  # not valid hex
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    reloaded = MerkleLog(path)
    assert reloaded.verify_chain() == (False, 0)


def test_intact_reloaded_log_still_verifies(tmp_path: Path) -> None:
    path = tmp_path / "merkle.json"
    original = _populated_log(path)
    reloaded = MerkleLog(path)
    assert reloaded.get_chain_length() == 3
    assert reloaded.get_root() == original.get_root()
    valid, idx = reloaded.verify_chain()
    assert valid and idx == 3
