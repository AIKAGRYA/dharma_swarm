"""Tests for scripts/governance/assurance_boundary.py (Sattva boundary V0).

Two layers of evidence:

1. Synthetic-tree tests — each detector matches exactly its contract's
   shape on a fabricated boundary, including the negative space (code
   that LOOKS like a violation but witnesses/raises/holds correctly must
   not be flagged — false positives are how gates lose credibility).
2. Live-tree tests — pinned only to facts that are stable by design:
   the manifest parses to the three declared spine layers, contracts
   that are at zero stay at zero, and any hold-at-zero violation must be
   one of the KNOWN, tracked danglers (so the test fails loudly when a
   NEW violation appears, and keeps passing as known ones are drained).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ab = _load("assurance_boundary", REPO_ROOT / "scripts/governance/assurance_boundary.py")


# ---------------------------------------------------------------------------
# Synthetic boundary
# ---------------------------------------------------------------------------

RECORDS_SOURCE = '''\
from dataclasses import dataclass

@dataclass(frozen=True)
class GoodReceipt:
    schema_version: str
    value: int

@dataclass
class LooseReceipt:          # AB-01: not frozen, no schema_version (2 findings)
    value: int

@dataclass(frozen=True, slots=True)
class TightRecord:           # frozen with extra kwargs is fine
    schema_version: str

@dataclass(frozen=True)
class BareIdentity:          # Identity: frozen required, schema_version not
    run_id: str

class PlainHelper:           # not a record name: ignored entirely
    pass
'''

SWALLOWS_SOURCE = '''\
import asyncio
import logging
logger = logging.getLogger(__name__)

def witnessed():
    try:
        work()
    except Exception:
        logger.exception("seen")        # witnesses: OK

def reraised():
    try:
        work()
    except Exception as exc:
        raise RuntimeError("up") from exc   # re-raises: OK

def narrow():
    try:
        work()
    except ValueError:
        cleanup()                       # narrow handler: out of AB-02 scope

def swallowed():
    try:
        work()
    except Exception:
        cleanup()                       # AB-02: continues, no witness

def receipted():
    try:
        work()
    except (ValueError, Exception):
        emit_receipt("failure")         # witnesses via receipt: OK

async def spawns():
    asyncio.create_task(work())         # AB-03: handle discarded
    task = asyncio.create_task(work())  # held: OK
    await task
'''

PROVIDER_SOURCE = '''\
import anthropic                         # AB-04: direct SDK import
from openai import OpenAI                # AB-04: direct SDK import
from dharma_swarm.runtime_provider import create_runtime_provider  # the door: OK
import anthropic_helpers                 # prefix collision, NOT the SDK: OK
'''


def _synthetic_boundary(tmp_path: Path) -> Path:
    for package in ab.BOUNDARY_PACKAGES:
        (tmp_path / package).mkdir(parents=True)
    spine = tmp_path / "dharma_swarm" / "spine"
    (spine / "records.py").write_text(RECORDS_SOURCE)
    (spine / "handlers.py").write_text(SWALLOWS_SOURCE)
    (tmp_path / "dharma_swarm" / "a2a" / "client.py").write_text(PROVIDER_SOURCE)
    (tmp_path / "dharma_swarm" / "runtime_state.py").write_text("state = {}\n")
    # The door itself may import SDKs freely.
    (tmp_path / "dharma_swarm" / "runtime_provider.py").write_text("import anthropic\n")
    (tmp_path / "ACTIVE_SURFACE_MANIFEST.yaml").write_text(MANIFEST_SOURCE)
    return tmp_path


MANIFEST_SOURCE = '''\
correlation_spine:
  schema_version: 1
  layers:
    - id: good_layer
      receipt_class: GoodReceipt
      receipt_module: dharma_swarm.spine.records
      identity_field: value
    - id: aliased_layer
      receipt_class: PublicName
      receipt_module: dharma_swarm.spine.aliased
      identity_field: correlation_id
    - id: dangling_layer
      receipt_class: GhostReceipt
      receipt_module: dharma_swarm.spine.records
      identity_field: correlation_id
  guard: scripts/uplift_guards/check_spine_ownership.py
'''

ALIASED_SOURCE = '''\
from dataclasses import dataclass

@dataclass(frozen=True)
class RealName:
    schema_version: str
    correlation_id: str

PublicName = RealName
'''


@pytest.fixture()
def boundary(tmp_path):
    repo = _synthetic_boundary(tmp_path)
    (repo / "dharma_swarm" / "spine" / "aliased.py").write_text(ALIASED_SOURCE)
    return repo


def test_record_discipline_flags_exactly_the_loose_record(boundary):
    report = ab.run_boundary(boundary)
    findings = [v.detail for v in report.measured["AB-01"]]
    assert sum("LooseReceipt" in d for d in findings) == 2  # unfrozen + no schema_version
    assert not any("GoodReceipt" in d or "TightRecord" in d or "PlainHelper" in d for d in findings)
    # Identity classes need frozen but not schema_version.
    assert not any("BareIdentity" in d for d in findings)


def test_broad_swallow_flags_only_the_unwitnessed_handler(boundary):
    report = ab.run_boundary(boundary)
    locations = [v.location for v in report.measured["AB-02"]]
    assert len(locations) == 1
    assert "handlers.py" in locations[0]
    line = int(locations[0].rsplit(":", 1)[1])
    text = (boundary / "dharma_swarm/spine/handlers.py").read_text().splitlines()
    assert "except Exception" in text[line - 1]  # points at swallowed(), not the witnessed ones


def test_unsupervised_spawn_flags_only_the_discarded_handle(boundary):
    report = ab.run_boundary(boundary)
    assert len(report.measured["AB-03"]) == 1
    assert "create_task" in report.measured["AB-03"][0].detail


def test_provider_door_flags_sdk_imports_but_not_the_door_or_lookalikes(boundary):
    violations = [v for v in ab.run_boundary(boundary).hold_at_zero if v.contract == "AB-04"]
    details = [v.detail for v in violations]
    assert len(violations) == 2
    assert any("'anthropic'" in d for d in details)
    assert any("'openai'" in d for d in details)
    assert not any("anthropic_helpers" in d for d in details)
    assert not any(ab.PROVIDER_DOOR in v.location for v in violations)


def test_spine_layer_check_resolves_aliases_and_catches_ghosts(boundary):
    violations = [v for v in ab.run_boundary(boundary).hold_at_zero if v.contract == "AB-05"]
    assert len(violations) == 1
    assert "GhostReceipt" in violations[0].detail
    assert "dangling_layer" in violations[0].location


def test_missing_boundary_package_is_broken_not_silent(tmp_path):
    with pytest.raises(ab.BrokenBoundary):
        ab.run_boundary(tmp_path)


def test_zero_parsed_layers_is_broken_not_vacuously_green(boundary):
    (boundary / "ACTIVE_SURFACE_MANIFEST.yaml").write_text("correlation_spine:\n  layers:\n")
    with pytest.raises(ab.BrokenBoundary):
        ab.run_boundary(boundary)


# ---------------------------------------------------------------------------
# Live tree
# ---------------------------------------------------------------------------

# Hold-at-zero violations currently known and tracked. Draining them is
# reconciliation-track work; a NEW name appearing here must fail loudly.
KNOWN_DANGLING_LAYERS = {"request_response"}


def test_live_manifest_parses_three_spine_layers():
    layers = ab.parse_spine_layers(REPO_ROOT)
    assert {layer["id"] for layer in layers} == {
        "request_response", "dispatch_invocation", "test_acceptance",
    }


def test_live_hold_at_zero_violations_are_a_subset_of_known_danglers():
    report = ab.run_boundary(REPO_ROOT)
    unknown = [
        v.render() for v in report.hold_at_zero
        if not any(known in v.location for known in KNOWN_DANGLING_LAYERS)
    ]
    assert unknown == [], f"new boundary contract violations: {unknown}"


def test_live_boundary_has_no_unsupervised_spawns_or_provider_leaks():
    report = ab.run_boundary(REPO_ROOT)
    assert report.measured["AB-03"] == ()
    assert [v for v in report.hold_at_zero if v.contract == "AB-04"] == []
