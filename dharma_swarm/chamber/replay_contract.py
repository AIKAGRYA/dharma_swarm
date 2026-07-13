"""Strict data contract for Hyperbolic Chamber replay bundles.

The contract accepts data only: registered identifiers, fixtures, ordered
choices, explicit faults/properties, and exact file digests.  It never
deserializes a callable, command, provider, or authority capability.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, cast

from dharma_swarm.chamber.traces import stable_digest

WORLD_SCHEMA = "dharma_world.v1"
REPLAY_BUNDLE_SCHEMA = "dharma_replay_bundle.v1"
SINGLE_REPLAY_SCHEMA = "dharma_single_process_replay.v1"
FRESH_REPLAY_SCHEMA = "dharma_fresh_process_verification.v1"
FORK_SCENARIO_ID = "dharmagraph.run_checkpoint.fork_alias.v1"
FORK_PROPERTY_ID = "dharmagraph.checkpoint.fork_parent_isolated.v1"
FORK_BUNDLE_ID = "dharmagraph-fork-alias-current-main-v1"
FORK_SPECIMEN_CANDIDATE_ID = "dharmagraph.run_checkpoint.current-fork-specimen.v1"
FORK_CONTROL_CANDIDATE_ID = "dharmagraph.run_checkpoint.deepcopy-control-fixture.v1"

REQUIRED_MANIFEST_PATHS = (
    "dharma_swarm/chamber/proof.py",
    "dharma_swarm/chamber/replay.py",
    "dharma_swarm/chamber/replay_contract.py",
    "dharma_swarm/chamber/replay_worker.py",
    "dharma_swarm/chamber/verification.py",
    "dharma_swarm/chamber/traces.py",
    "dharma_swarm/graph/types.py",
)

# Every repository source file executed by the isolated replay worker.  The
# manifest is a deliberate superset because it also binds proof.py, whose
# evaluator consumes the resulting claim but is not needed to replay it.
REPLAY_EXECUTED_SOURCE_PATHS = (
    "dharma_swarm/chamber/replay.py",
    "dharma_swarm/chamber/replay_contract.py",
    "dharma_swarm/chamber/replay_worker.py",
    "dharma_swarm/chamber/traces.py",
    "dharma_swarm/chamber/verification.py",
    "dharma_swarm/graph/types.py",
)


class ReplayValidationError(ValueError):
    """A world, bundle, manifest, or replay result failed closed."""


def _exact_keys(payload: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(payload)
    if actual != expected:
        raise ReplayValidationError(
            f"{label}: fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ReplayValidationError(f"world: {label} must be a list of strings")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReplayValidationError(f"{label} must be a non-empty string")
    return value


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        ch in "0123456789abcdef" for ch in value
    )


@dataclass(frozen=True, slots=True)
class ChoiceV1:
    name: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": copy.deepcopy(self.value)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ChoiceV1:
        _exact_keys(payload, {"name", "value"}, "choice")
        name = _string(payload["name"], "choice name")
        return cls(name=name, value=copy.deepcopy(payload["value"]))


@dataclass(frozen=True, slots=True)
class WorldV1:
    scenario_id: str
    fixtures: dict[str, Any]
    choices: tuple[ChoiceV1, ...]
    faults: tuple[str, ...]
    activated_properties: tuple[str, ...]
    declared_nondeterminism: tuple[str, ...]
    schema: str = WORLD_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "scenario_id": self.scenario_id,
            "fixtures": copy.deepcopy(self.fixtures),
            "choices": [choice.to_dict() for choice in self.choices],
            "faults": list(self.faults),
            "activated_properties": list(self.activated_properties),
            "declared_nondeterminism": list(self.declared_nondeterminism),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> WorldV1:
        _exact_keys(
            payload,
            {
                "schema",
                "scenario_id",
                "fixtures",
                "choices",
                "faults",
                "activated_properties",
                "declared_nondeterminism",
            },
            "world",
        )
        if payload["schema"] != WORLD_SCHEMA:
            raise ReplayValidationError(f"world: unsupported schema {payload['schema']!r}")
        fixtures, choices = payload["fixtures"], payload["choices"]
        if not isinstance(fixtures, dict) or not isinstance(choices, list):
            raise ReplayValidationError("world: fixtures must be an object and choices a list")
        if not all(isinstance(item, Mapping) for item in choices):
            raise ReplayValidationError("world: each choice must be an object")
        return cls(
            scenario_id=_string(payload["scenario_id"], "world scenario_id"),
            fixtures=copy.deepcopy(fixtures),
            choices=tuple(ChoiceV1.from_dict(item) for item in choices),
            faults=tuple(_string_list(payload["faults"], "faults")),
            activated_properties=tuple(
                _string_list(payload["activated_properties"], "activated_properties")
            ),
            declared_nondeterminism=tuple(
                _string_list(payload["declared_nondeterminism"], "declared_nondeterminism")
            ),
        )


@dataclass(frozen=True, slots=True)
class ManifestEntryV1:
    path: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ManifestEntryV1:
        _exact_keys(payload, {"path", "sha256"}, "manifest entry")
        path = _string(payload["path"], "manifest path")
        digest = _string(payload["sha256"], "manifest sha256")
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise ReplayValidationError(f"manifest entry escapes repository: {path!r}")
        if not _is_sha256(digest):
            raise ReplayValidationError(f"manifest entry has invalid sha256: {path!r}")
        return cls(path=path, sha256=digest)


@dataclass(frozen=True, slots=True)
class ReplayExpectationV1:
    property_id: str
    scenario_semantic_digest: str
    control_semantic_digest: str
    scenario_verdict: bool
    control_verdict: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "property_id": self.property_id,
            "scenario_semantic_digest": self.scenario_semantic_digest,
            "control_semantic_digest": self.control_semantic_digest,
            "scenario_verdict": self.scenario_verdict,
            "control_verdict": self.control_verdict,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReplayExpectationV1:
        _exact_keys(
            payload,
            {
                "property_id",
                "scenario_semantic_digest",
                "control_semantic_digest",
                "scenario_verdict",
                "control_verdict",
            },
            "expectation",
        )
        for key in ("scenario_semantic_digest", "control_semantic_digest"):
            if not _is_sha256(payload[key]):
                raise ReplayValidationError(f"expectation: {key} is not sha256")
        if not isinstance(payload["scenario_verdict"], bool) or not isinstance(
            payload["control_verdict"], bool
        ):
            raise ReplayValidationError("expectation: property verdicts must be booleans")
        return cls(
            property_id=_string(payload["property_id"], "expectation property_id"),
            scenario_semantic_digest=payload["scenario_semantic_digest"],
            control_semantic_digest=payload["control_semantic_digest"],
            scenario_verdict=payload["scenario_verdict"],
            control_verdict=payload["control_verdict"],
        )


@dataclass(frozen=True, slots=True)
class ReplayBundleV1:
    bundle_id: str
    scenario_candidate_id: str
    control_candidate_id: str
    source_revision: str
    world: WorldV1
    control_world: WorldV1
    manifest: tuple[ManifestEntryV1, ...]
    expectation: ReplayExpectationV1
    schema: str = REPLAY_BUNDLE_SCHEMA

    @property
    def scope_digest(self) -> str:
        return stable_digest(self.body_dict())

    def body_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "bundle_id": self.bundle_id,
            "scenario_candidate_id": self.scenario_candidate_id,
            "control_candidate_id": self.control_candidate_id,
            "source_revision": self.source_revision,
            "world": self.world.to_dict(),
            "control_world": self.control_world.to_dict(),
            "manifest": [entry.to_dict() for entry in self.manifest],
            "expectation": self.expectation.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        body = self.body_dict()
        return {**body, "bundle_digest": stable_digest(body)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReplayBundleV1:
        _exact_keys(
            payload,
            {
                "schema",
                "bundle_id",
                "scenario_candidate_id",
                "control_candidate_id",
                "source_revision",
                "world",
                "control_world",
                "manifest",
                "expectation",
                "bundle_digest",
            },
            "bundle",
        )
        body = {key: copy.deepcopy(value) for key, value in payload.items() if key != "bundle_digest"}
        if payload["schema"] != REPLAY_BUNDLE_SCHEMA:
            raise ReplayValidationError(f"bundle: unsupported schema {payload['schema']!r}")
        if stable_digest(body) != payload["bundle_digest"]:
            raise ReplayValidationError("bundle: digest mismatch")
        manifest = payload["manifest"]
        if not isinstance(manifest, list) or not all(
            isinstance(item, Mapping) for item in manifest
        ):
            raise ReplayValidationError("bundle: manifest must be a list")
        world = payload["world"]
        control_world = payload["control_world"]
        expectation = payload["expectation"]
        if not all(
            isinstance(item, Mapping) for item in (world, control_world, expectation)
        ):
            raise ReplayValidationError("bundle: worlds and expectation must be objects")
        bundle = cls(
            bundle_id=_string(payload["bundle_id"], "bundle id"),
            scenario_candidate_id=_string(
                payload["scenario_candidate_id"], "scenario candidate id"
            ),
            control_candidate_id=_string(
                payload["control_candidate_id"], "control candidate id"
            ),
            source_revision=_string(payload["source_revision"], "source revision"),
            world=WorldV1.from_dict(cast(Mapping[str, Any], world)),
            control_world=WorldV1.from_dict(cast(Mapping[str, Any], control_world)),
            manifest=tuple(ManifestEntryV1.from_dict(item) for item in manifest),
            expectation=ReplayExpectationV1.from_dict(cast(Mapping[str, Any], expectation)),
        )
        validate_bundle_contract(bundle)
        return bundle


def validate_world_contract(world: WorldV1) -> None:
    if (
        type(world) is not WorldV1
        or type(world.fixtures) is not dict
        or type(world.choices) is not tuple
        or not all(type(choice) is ChoiceV1 for choice in world.choices)
        or type(world.faults) is not tuple
        or type(world.activated_properties) is not tuple
        or type(world.declared_nondeterminism) is not tuple
    ):
        raise ReplayValidationError("world: direct object has invalid field types")
    if world.schema != WORLD_SCHEMA or world.scenario_id != FORK_SCENARIO_ID:
        raise ReplayValidationError("world: only the registered fork-alias scenario is allowed")
    if world.declared_nondeterminism:
        raise ReplayValidationError("world: V0 refuses declared nondeterminism")
    if world.faults:
        raise ReplayValidationError("world: fork-alias V0 accepts no injected faults")
    if world.activated_properties != (FORK_PROPERTY_ID,):
        raise ReplayValidationError("world: activated property set is not exact")
    if tuple(choice.name for choice in world.choices) != ("fork_strategy", "append_value"):
        raise ReplayValidationError("world: choices must be exact and ordered")
    if type(world.choices[0].value) is not str or world.choices[0].value not in {
        "production",
        "deepcopy_control",
    }:
        raise ReplayValidationError("world: fork_strategy is not registered")
    if type(world.choices[1].value) is not str or world.choices[1].value != "child-only":
        raise ReplayValidationError("world: append_value differs from registered fixture")
    _exact_keys(world.fixtures, {"checkpoint", "child_run_id"}, "world fixtures")
    checkpoint = world.fixtures.get("checkpoint")
    if not isinstance(checkpoint, dict):
        raise ReplayValidationError("world: checkpoint fixture must be an object")
    _exact_keys(
        checkpoint,
        {"graph_run_id", "graph_id", "superstep", "state_digest", "channels", "versions_seen"},
        "checkpoint fixture",
    )
    expected_checkpoint = {
        "graph_run_id": "parent-run",
        "graph_id": "fixture-graph",
        "superstep": 1,
        "state_digest": "fixture-state-digest",
        "channels": {"messages": {"values": ["parent-only"]}},
        "versions_seen": {"node-a": {"messages": 1}},
    }
    try:
        checkpoint_matches = stable_digest(checkpoint) == stable_digest(expected_checkpoint)
    except (TypeError, ValueError) as exc:
        raise ReplayValidationError("world: checkpoint fixture is not canonical JSON") from exc
    if (
        not checkpoint_matches
        or type(world.fixtures["child_run_id"]) is not str
        or world.fixtures["child_run_id"] != "child-run"
    ):
        raise ReplayValidationError("world: fixture values differ from registered scenario")


def validate_bundle_contract(bundle: ReplayBundleV1) -> None:
    if (
        type(bundle) is not ReplayBundleV1
        or type(bundle.manifest) is not tuple
        or not all(type(entry) is ManifestEntryV1 for entry in bundle.manifest)
        or type(bundle.expectation) is not ReplayExpectationV1
    ):
        raise ReplayValidationError("bundle direct object has invalid field types")
    if bundle.schema != REPLAY_BUNDLE_SCHEMA:
        raise ReplayValidationError("bundle schema is not registered")
    if bundle.bundle_id != FORK_BUNDLE_ID:
        raise ReplayValidationError("bundle id is not the registered V0 bundle")
    if bundle.scenario_candidate_id != FORK_SPECIMEN_CANDIDATE_ID:
        raise ReplayValidationError("bundle scenario candidate is not registered")
    if bundle.control_candidate_id != FORK_CONTROL_CANDIDATE_ID:
        raise ReplayValidationError("bundle control candidate is not registered")
    if bundle.scenario_candidate_id == bundle.control_candidate_id:
        raise ReplayValidationError("bundle candidate arms must be distinct")
    if not isinstance(bundle.source_revision, str):
        raise ReplayValidationError("bundle source revision must be a string")
    if bundle.source_revision != "WORKTREE" and not (
        len(bundle.source_revision) == 40
        and all(ch in "0123456789abcdef" for ch in bundle.source_revision)
    ):
        raise ReplayValidationError("bundle source revision is not a commit or WORKTREE")
    validate_world_contract(bundle.world)
    validate_world_contract(bundle.control_world)
    if bundle.world.choices[0].value != "production":
        raise ReplayValidationError("bundle: scenario world must exercise production fork")
    if bundle.control_world.choices[0].value != "deepcopy_control":
        raise ReplayValidationError("bundle: control world must use deep-copy correction")
    expected = bundle.expectation
    if expected.property_id != FORK_PROPERTY_ID:
        raise ReplayValidationError("bundle: expectation proposition is not registered")
    if not _is_sha256(expected.scenario_semantic_digest) or not _is_sha256(
        expected.control_semantic_digest
    ):
        raise ReplayValidationError("bundle: expectation digest is not sha256")
    if expected.scenario_verdict is not False or expected.control_verdict is not True:
        raise ReplayValidationError("bundle: V0 requires a failing specimen and passing control")


__all__ = [
    "FORK_BUNDLE_ID",
    "FORK_CONTROL_CANDIDATE_ID",
    "FORK_PROPERTY_ID",
    "FORK_SCENARIO_ID",
    "FORK_SPECIMEN_CANDIDATE_ID",
    "FRESH_REPLAY_SCHEMA",
    "REPLAY_EXECUTED_SOURCE_PATHS",
    "REQUIRED_MANIFEST_PATHS",
    "SINGLE_REPLAY_SCHEMA",
    "ChoiceV1",
    "ManifestEntryV1",
    "ReplayBundleV1",
    "ReplayExpectationV1",
    "ReplayValidationError",
    "WorldV1",
    "validate_bundle_contract",
    "validate_world_contract",
]
