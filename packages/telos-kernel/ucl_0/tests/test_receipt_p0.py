from __future__ import annotations

import ast
import random
from pathlib import Path

import pytest

from ucl_0.genesis import make_genesis
from ucl_0.receipt.identity import canonical_receipt_bytes, receipt_id, receipt_id_uri
from ucl_0.receipt.jcs import canonicalize
from ucl_0.receipt.lfp import least_fixed_point, phi_step
from ucl_0.receipt.types import (
    EvidenceRecord,
    Receipt,
    ValidityRecord,
    is_well_formed,
    parse_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
VALIDITY = ValidityRecord("2026-07-05T00:00:00Z", 3600)
EXPECTED_10K_DIGEST = "sha256:6f4957c9d530cbc0e16fb90c61f2d4f3cbb0bc98adfef815252ab100de0ae930"


def _bytes(rng: random.Random, size: int) -> bytes:
    return bytes(rng.getrandbits(8) for _ in range(size))


def _receipt(rng: random.Random, predecessor_count: int = 0) -> Receipt:
    predecessors = [_bytes(rng, 32) for _ in range(predecessor_count)]
    evidence = [
        EvidenceRecord(
            method=_bytes(rng, 6),
            trust_base=_bytes(rng, 6),
            independence_class=_bytes(rng, 6),
            body=_bytes(rng, 16),
        )
    ]
    return Receipt(_bytes(rng, 24), evidence, predecessors, VALIDITY)


def test_jcs_basic_vectors() -> None:
    assert canonicalize({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert canonicalize("a\nb") == b'"a\\nb"'
    assert canonicalize(1e-6) == b"0.000001"
    assert canonicalize(1e-7) == b"1e-7"
    assert canonicalize(1e21) == b"1e+21"
    with pytest.raises(ValueError):
        canonicalize(float("nan"))


def test_jcs_determinism_10k_random_receipts() -> None:
    rng = random.Random(8785)
    aggregate = b""
    for _ in range(10_000):
        receipt = _receipt(rng, predecessor_count=rng.randrange(3))
        first = canonical_receipt_bytes(receipt)
        second = canonical_receipt_bytes(receipt)
        assert first == second
        aggregate = receipt_id(Receipt(aggregate + first, [], [], VALIDITY))
    assert receipt_id_uri(Receipt(aggregate, [], [], VALIDITY)) == EXPECTED_10K_DIGEST


def test_receipt_id_no_collisions_in_100k_random_receipts() -> None:
    rng = random.Random(100_000)
    seen: set[bytes] = set()
    for index in range(100_000):
        receipt = _receipt(rng, predecessor_count=index % 3)
        digest = receipt_id(receipt)
        assert digest not in seen
        seen.add(digest)


def _chain(length: int) -> list[Receipt]:
    receipts: list[Receipt] = []
    predecessors: list[bytes] = []
    for index in range(length):
        receipt = Receipt(f"claim-{index}".encode(), [], predecessors, VALIDITY)
        receipts.append(receipt)
        predecessors = [receipt_id(receipt)]
    return receipts


@pytest.mark.parametrize("length", [1, 10, 100])
def test_lfp_converges_for_chains(length: int) -> None:
    receipts = _chain(length)
    admitted = least_fixed_point(receipts)
    assert admitted == {receipt_id(receipt) for receipt in receipts}


def test_phi_is_monotone() -> None:
    receipts = _chain(5)
    small = {receipt_id(receipts[0])}
    large = {receipt_id(receipts[0]), receipt_id(receipts[1])}
    assert small <= large
    assert phi_step(receipts, small) <= phi_step(receipts, large)


def test_genesis_is_unsigned_by_default_and_forkable(caplog: pytest.LogCaptureFixture) -> None:
    first = make_genesis(b"fable-seed")
    second = make_genesis(b"rival-seed")
    assert first.evidence == []
    assert second.evidence == []
    assert first.predecessors == []
    assert second.predecessors == []
    assert is_well_formed(first)
    assert is_well_formed(second)
    assert not receipt_id(first) == receipt_id(second)
    assert least_fixed_point([first, second]) == {receipt_id(first), receipt_id(second)}
    assert "genesis is mandatorily forkable per L7" in caplog.text


def test_threshold_signature_is_ordinary_evidence() -> None:
    receipt = make_genesis(b"seed", threshold_signature=b"sig")
    assert len(receipt.evidence) == 1
    assert is_well_formed(receipt)


def test_parser_rejects_extra_seed_fields() -> None:
    valid = {
        "claim": "00",
        "evidence": [],
        "predecessors": [],
        "validity": {"issued_at": "2026-07-05T00:00:00Z", "ttl_seconds": 1},
    }
    assert parse_receipt(valid) == Receipt(b"\x00", [], [], ValidityRecord("2026-07-05T00:00:00Z", 1))
    for forbidden in ("receipt_id", "signatures", "trust_base", "moda" + "lity"):
        payload = dict(valid)
        payload[forbidden] = "00"
        with pytest.raises(ValueError):
            parse_receipt(payload)


def test_no_forbidden_seed_field_token_except_allowed_docstring() -> None:
    needle = "moda" + "lity"
    hits: list[str] = []
    for path in ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if needle in line:
                hits.append(f"{path.relative_to(ROOT)}:{line_number}:{line.strip()}")
    expected = "receipt/types.py:4:" + needle
    expected += " is derived from evidence records and is never serialized as a"
    assert hits == [expected]


def test_no_forbidden_calls_or_dynamic_imports() -> None:
    forbidden = {"eval", "exec", "compile", "__import__"}
    for path in ROOT.rglob("*.py"):
        if "/tests/" in path.as_posix():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name.split(".")[0] for alias in node.names]
                if isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module.split(".")[0])
                assert "dharma_swarm" not in names


def test_import_allow_list_for_ucl_0_sources() -> None:
    allowed = {
        "__future__",
        "collections",
        "dataclasses",
        "hashlib",
        "logging",
        "math",
        "re",
        "typing",
        "ucl_0",
    }
    for path in ROOT.rglob("*.py"):
        if "/tests/" in path.as_posix():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                names = [node.module.split(".")[0]]
            else:
                continue
            for name in names:
                assert name in allowed


def test_p0_loc_budget_under_800() -> None:
    total = 0
    for path in ROOT.rglob("*.py"):
        if "/tests/" in path.as_posix():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                total += 1
    assert total <= 800
