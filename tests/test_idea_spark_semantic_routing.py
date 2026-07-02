"""PR 5 verifier — candidate -> Semantic Commons owner route (fail-closed).

Deterministic, no-network. A hermetic temp ontology proves resolution and
persistence; a gibberish candidate proves fail-closed routing; a smoke against
the real ontology proves integration with the live reader.
"""

from __future__ import annotations

import json

import yaml

from dharma_swarm.idea_spark.fixtures import NOTE_FIXTURE
from dharma_swarm.idea_spark.projection import candidate_from_operator_receipt
from dharma_swarm.idea_spark.schemas import IdeaSparkCandidate
from dharma_swarm.idea_spark.semantic_routing import (
    UNRESOLVED_MARKER,
    resolve_owner,
    route_candidate,
)
from dharma_swarm.idea_spark.store import load_lifecycle_receipt
from dharma_swarm.semantic_commons import SemanticCommons, load_semantic_commons

FIXED_NOW = "2026-06-26T00:00:00Z"


def _temp_commons(tmp_path) -> SemanticCommons:
    tmp_path.mkdir(parents=True, exist_ok=True)
    objects = {
        "schema_version": "semantic-commons-v0",
        "owner_track": "idea-spark-test",
        "lifecycle_values": ["seed", "working", "preferred", "canonical", "deprecated", "forbidden"],
        "objects": [
            {
                "id": "semobj.idea_refinery",
                "canonical_name": "Idea Refinery",
                "api_name": "dharma.ingest.IdeaRefinery",
                "lifecycle": "working",
                "owner_surface": "dharma_swarm/idea_spark/",
                "authority_level": "projection",
                "source_path": "dharma_swarm/idea_spark/__init__.py",
                "aliases": ["idea refinery", "memory tool", "governed memory"],
                "forbidden_aliases": [],
                "supersedes": [],
                "superseded_by": [],
            }
        ],
    }
    (tmp_path / "semantic_objects.yaml").write_text(yaml.safe_dump(objects), encoding="utf-8")
    (tmp_path / "semantic_aliases.yaml").write_text(
        yaml.safe_dump({"schema_version": "semantic-commons-v0", "aliases": []}), encoding="utf-8"
    )
    return SemanticCommons.load(tmp_path)


def _empty_commons(tmp_path) -> SemanticCommons:
    tmp_path.mkdir(parents=True, exist_ok=True)
    objects = {
        "schema_version": "semantic-commons-v0",
        "owner_track": "idea-spark-test",
        "lifecycle_values": ["seed", "working", "preferred", "canonical", "deprecated", "forbidden"],
        "objects": [],
    }
    (tmp_path / "semantic_objects.yaml").write_text(yaml.safe_dump(objects), encoding="utf-8")
    (tmp_path / "semantic_aliases.yaml").write_text(
        yaml.safe_dump({"schema_version": "semantic-commons-v0", "aliases": []}), encoding="utf-8"
    )
    return SemanticCommons.load(tmp_path)


def _candidate(claim: str, domain: str = "tooling") -> IdeaSparkCandidate:
    receipt = NOTE_FIXTURE.build_receipt()
    return candidate_from_operator_receipt(receipt, claim=claim, domain=domain, now=FIXED_NOW)


def test_resolves_owner_surface_against_temp_ontology(tmp_path) -> None:
    commons = _temp_commons(tmp_path / "ontology")
    candidate = _candidate(
        "Prototype a governed memory tool for the agent runtime so retrieval is deterministic."
    )
    route, updated = route_candidate(
        candidate, commons=commons, state_root=tmp_path, created_at=FIXED_NOW
    )
    assert route.resolved is True
    assert route.canonical_target == "semobj.idea_refinery"
    assert route.owner_surface == "dharma_swarm/idea_spark/"
    assert route.blocker == ""
    assert updated.routing_status == "routed"
    assert updated.owner_surface == "dharma_swarm/idea_spark/"

    # Routing receipt persisted with evidence.
    receipt_path = tmp_path / "meta" / "idea_spark" / "routing_receipts" / f"{candidate.correlation_id}.json"
    assert receipt_path.exists()
    payload = json.loads(receipt_path.read_text())
    assert payload["schema_version"] == "idea_spark_routing_receipt.v0"
    assert payload["owner_surface"] == "dharma_swarm/idea_spark/"
    assert payload["evidence"]["structural_scope_first"] is True

    # Lifecycle receipt advanced to routed.
    lifecycle = load_lifecycle_receipt(candidate.correlation_id, tmp_path)
    assert lifecycle is not None
    assert lifecycle.status == "routed"
    assert lifecycle.owner_surface == "dharma_swarm/idea_spark/"
    assert lifecycle.semantic_route


def test_unroutable_candidate_fails_closed(tmp_path) -> None:
    commons = _temp_commons(tmp_path / "ontology")
    candidate = _candidate("Zxqwbblplk fnord wibble nonsense gibberish token.", domain="zxqwb")
    route, updated = route_candidate(
        candidate, commons=commons, state_root=tmp_path, created_at=FIXED_NOW
    )
    assert route.resolved is False
    assert route.owner_surface == ""
    assert route.blocker == UNRESOLVED_MARKER
    assert updated.routing_status == "blocked"

    lifecycle = load_lifecycle_receipt(candidate.correlation_id, tmp_path)
    assert lifecycle is not None
    assert UNRESOLVED_MARKER in lifecycle.blockers


def test_resolved_reroute_clears_stale_semantic_blocker(tmp_path) -> None:
    candidate = _candidate("Prototype a governed memory tool for deterministic retrieval.")
    unresolved_route, _unresolved = route_candidate(
        candidate,
        commons=_empty_commons(tmp_path / "empty-ontology"),
        state_root=tmp_path,
        created_at=FIXED_NOW,
    )
    assert unresolved_route.resolved is False

    stale = load_lifecycle_receipt(candidate.correlation_id, tmp_path)
    assert stale is not None
    assert UNRESOLVED_MARKER in stale.blockers

    resolved_route, _resolved = route_candidate(
        candidate,
        commons=_temp_commons(tmp_path / "ontology"),
        state_root=tmp_path,
        created_at=FIXED_NOW,
    )
    assert resolved_route.resolved is True

    lifecycle = load_lifecycle_receipt(candidate.correlation_id, tmp_path)
    assert lifecycle is not None
    assert lifecycle.status == "routed"
    assert lifecycle.blockers == []
    assert lifecycle.owner_surface == "dharma_swarm/idea_spark/"


def test_resolve_owner_against_real_ontology_smoke() -> None:
    # Integration smoke: a candidate about the semantic commons resolves to a
    # real owner surface via the live singleton (read-only, no network).
    commons = load_semantic_commons()
    candidate = _candidate(
        "Improve the semantic commons owner routing surface.", domain="semantic commons"
    )
    route = resolve_owner(candidate, commons, created_at=FIXED_NOW)
    assert route.resolved is True
    assert route.canonical_target.startswith("semobj.")
    assert route.owner_surface
