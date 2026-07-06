"""Drift test: `to_canonical_dict()` must agree with `model_dump()` on every
field the Pydantic model exposes.

If either side gains/loses a field or changes a serialization convention,
this test fails immediately so the divergence cannot ship silently.

This is the safety net that lets us take Pydantic reflection off the hot
signing path without giving up its schema-enforcement guarantees.
"""
from __future__ import annotations

import uuid

import pytest
import yaml

from telos_kernel.canonical import canonicalize
from telos_kernel.manifest import Manifest, load_manifest
from telos_kernel.receipt import (
    Leaf,
    SCHEMA_VERSION,
    SignatureStatus,
    Tier,
    Verdict,
    now_iso_utc,
)


def _sample_leaf() -> Leaf:
    return Leaf(
        schema_version=SCHEMA_VERSION,
        gate="U5_merkle_binding",
        tier=Tier.A,
        proposal_id=str(uuid.uuid4()),
        prev_merkle_root="a" * 64,
        measure={"chain_length": 42, "tag": "x"},
        threshold={"min_length": 1},
        verdict=Verdict.ALLOW,
        signature_status=SignatureStatus.STUB,
        capability_signature="",
        signer_key_id="STUB_SIGNER_0",
        timestamp=now_iso_utc(),
    )


def test_leaf_canonical_dict_matches_model_dump():
    leaf = _sample_leaf()
    ours = leaf.to_canonical_dict()
    theirs = leaf.model_dump()

    # Pydantic emits enums as `Enum` instances by default; our projection
    # emits `.value` strings. Normalize before comparing.
    for k in ("tier", "verdict", "signature_status"):
        if hasattr(theirs[k], "value"):
            theirs[k] = theirs[k].value

    assert set(ours.keys()) == set(theirs.keys()), (
        f"field-set drift: ours={set(ours.keys())} theirs={set(theirs.keys())}"
    )
    for k in ours:
        assert ours[k] == theirs[k], f"field {k!r} diverged: ours={ours[k]!r} theirs={theirs[k]!r}"


def test_manifest_canonical_dict_matches_model_dump():
    manifest = load_manifest()
    ours = manifest.to_canonical_dict()
    theirs = manifest.model_dump()

    # Normalize enum values on the Pydantic side.
    for inv in theirs["invariants"]:
        if hasattr(inv["enforcement_status"], "value"):
            inv["enforcement_status"] = inv["enforcement_status"].value

    # signer_set 'stub' flag: our projection derives it from public_key_hex
    # when absent; Pydantic keeps whatever was in the YAML. Normalize both
    # to the derived form.
    for s in theirs["signer_set"]["signers"]:
        s["stub"] = bool(s.get("stub", s["public_key_hex"] == "STUB"))
    for s in ours["signer_set"]["signers"]:
        s["stub"] = bool(s.get("stub", s["public_key_hex"] == "STUB"))

    assert set(ours.keys()) == set(theirs.keys())
    assert ours["schema_version"] == theirs["schema_version"]
    assert ours["version"] == theirs["version"]
    assert len(ours["invariants"]) == len(theirs["invariants"])
    for i, (a, b) in enumerate(zip(ours["invariants"], theirs["invariants"])):
        assert set(a.keys()) == set(b.keys()), (
            f"invariant {i} field-set drift: ours={set(a.keys())} theirs={set(b.keys())}"
        )
        for k in a:
            assert a[k] == b[k], f"invariant {i} field {k!r} diverged"


def test_leaf_signing_bytes_are_deterministic():
    """Hot-path signing produces identical bytes on repeat calls."""
    leaf = _sample_leaf()
    b1 = leaf.signing_bytes()
    b2 = leaf.signing_bytes()
    assert b1 == b2
    # And the canonical projection round-trips through canonicalize.
    payload = leaf.to_canonical_dict()
    payload["capability_signature"] = ""
    assert canonicalize(payload) == b1


def test_leaf_signing_bytes_do_not_go_through_model_dump():
    """Regression: signing_bytes() must call to_canonical_dict, not model_dump.

    If someone reintroduces `model_dump()` on the signing path, this test
    detects it by monkey-patching model_dump to raise and confirming the
    signing path still works.
    """
    leaf = _sample_leaf()

    def _boom(*a, **kw):
        raise AssertionError(
            "signing_bytes() must not call model_dump() \u2014 use to_canonical_dict()"
        )

    original = Leaf.model_dump
    Leaf.model_dump = _boom  # type: ignore[assignment]
    try:
        leaf.signing_bytes()  # must succeed without touching model_dump
    finally:
        Leaf.model_dump = original  # type: ignore[assignment]


def test_manifest_content_hash_does_not_use_model_dump():
    manifest = load_manifest()

    def _boom(*a, **kw):
        raise AssertionError(
            "Manifest.content_hash() must not call model_dump()"
        )

    original = Manifest.model_dump
    Manifest.model_dump = _boom  # type: ignore[assignment]
    try:
        manifest.content_hash()
    finally:
        Manifest.model_dump = original  # type: ignore[assignment]
