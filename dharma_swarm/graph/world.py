"""WorldV1 replay identity: pure, canonical, and fail-closed.

This module does not execute or persist a simulation.  It records the six
inputs that bound a replay claim as domain-separated digests, then verifies
that a proposed replay presents the same inputs.  A matching record means
only "same declared replay boundary"; it is not a correctness or authority
claim.

Canonical values are strict JSON: ``null``/bool/int/finite-float/string,
lists, and string-keyed dictionaries.  Rejecting Python-only conveniences is
intentional.  In particular, ``json.dumps`` silently maps the integer key
``0`` and the string key ``"0"`` to the same bytes; a replay identity must not.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

WORLD_V1_SCHEMA: Final[str] = "dharma_swarm.graph.world.v1"

WorldV1Component = Literal[
    "code",
    "world",
    "config",
    "fixture",
    "oracle",
    "action_sequence",
]

_COMPONENTS: Final[tuple[WorldV1Component, ...]] = (
    "code",
    "world",
    "config",
    "fixture",
    "oracle",
    "action_sequence",
)
_DIGEST_PREFIX: Final[str] = "sha256:"
_DIGEST_HEX_LENGTH: Final[int] = 64

__all__ = [
    "WORLD_V1_SCHEMA",
    "WorldV1CanonicalizationError",
    "WorldV1Record",
    "WorldV1ReplayMismatch",
    "canonical_digest",
]


class WorldV1CanonicalizationError(ValueError):
    """A replay-boundary value cannot be represented as strict JSON."""


class WorldV1ReplayMismatch(ValueError):
    """A replay record or one of its declared inputs does not match."""

    def __init__(self, components: Sequence[str]) -> None:
        self.components = tuple(components)
        super().__init__("WorldV1 replay mismatch: " + ", ".join(self.components))


def _strict_json(value: Any, *, path: str) -> Any:
    """Return a canonicalizable copy or fail on non-JSON/lossy values."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise WorldV1CanonicalizationError(
                f"{path} contains an unpaired Unicode surrogate"
            ) from exc
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WorldV1CanonicalizationError(f"{path} contains a non-finite float")
        return value
    if isinstance(value, list):
        return [
            _strict_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise WorldV1CanonicalizationError(
                    f"{path} contains non-string mapping key {key!r}"
                )
        return {
            key: _strict_json(
                value[key],
                path=f"{path}[{json.dumps(key, ensure_ascii=False)}]",
            )
            for key in sorted(value)
        }
    raise WorldV1CanonicalizationError(
        f"{path} contains non-JSON value of type {type(value).__name__}"
    )


def _canonical_json(value: Any, *, path: str) -> str:
    return json.dumps(
        _strict_json(value, path=path),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256_uri(canonical_json: str) -> str:
    return _DIGEST_PREFIX + hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def canonical_digest(component: WorldV1Component, value: Any) -> str:
    """Digest one WorldV1 component with schema and domain separation."""
    if component not in _COMPONENTS:
        raise ValueError(f"unknown WorldV1 component {component!r}")
    envelope = {
        "component": component,
        "schema": WORLD_V1_SCHEMA,
        "value": value,
    }
    return _sha256_uri(_canonical_json(envelope, path=f"$.{component}"))


def _aggregate_digest(component_digests: Mapping[str, str]) -> str:
    envelope = {
        "component_digests": dict(component_digests),
        "schema": WORLD_V1_SCHEMA,
    }
    return _sha256_uri(_canonical_json(envelope, path="$.record"))


def _is_digest(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith(_DIGEST_PREFIX):
        return False
    hexadecimal = value[len(_DIGEST_PREFIX) :]
    return len(hexadecimal) == _DIGEST_HEX_LENGTH and all(
        character in "0123456789abcdef" for character in hexadecimal
    )


@dataclass(frozen=True)
class WorldV1Record:
    """Serializable identity of one bounded record/replay experiment."""

    schema: str
    code_digest: str
    world_digest: str
    config_digest: str
    fixture_digest: str
    oracle_digest: str
    action_sequence_digest: str
    record_digest: str

    @classmethod
    def capture(
        cls,
        *,
        code: Any,
        world: Any,
        config: Any,
        fixture: Any,
        oracle: Any,
        action_sequence: Sequence[Any],
    ) -> WorldV1Record:
        """Capture six declared replay inputs without executing or writing."""
        if isinstance(action_sequence, (str, bytes, bytearray)) or not isinstance(
            action_sequence, Sequence
        ):
            raise WorldV1CanonicalizationError(
                "$.action_sequence must be an ordered sequence of actions"
            )
        actions = list(action_sequence)
        component_digests = {
            "code": canonical_digest("code", code),
            "world": canonical_digest("world", world),
            "config": canonical_digest("config", config),
            "fixture": canonical_digest("fixture", fixture),
            "oracle": canonical_digest("oracle", oracle),
            "action_sequence": canonical_digest("action_sequence", actions),
        }
        return cls(
            schema=WORLD_V1_SCHEMA,
            code_digest=component_digests["code"],
            world_digest=component_digests["world"],
            config_digest=component_digests["config"],
            fixture_digest=component_digests["fixture"],
            oracle_digest=component_digests["oracle"],
            action_sequence_digest=component_digests["action_sequence"],
            record_digest=_aggregate_digest(component_digests),
        )

    @property
    def component_digests(self) -> dict[str, str]:
        return {
            "code": self.code_digest,
            "world": self.world_digest,
            "config": self.config_digest,
            "fixture": self.fixture_digest,
            "oracle": self.oracle_digest,
            "action_sequence": self.action_sequence_digest,
        }

    def to_dict(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            **{
                f"{component}_digest": digest
                for component, digest in self.component_digests.items()
            },
            "record_digest": self.record_digest,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> WorldV1Record:
        expected = {
            "schema",
            "code_digest",
            "world_digest",
            "config_digest",
            "fixture_digest",
            "oracle_digest",
            "action_sequence_digest",
            "record_digest",
        }
        keys = set(payload)
        if keys != expected:
            missing = sorted(expected - keys)
            extra = sorted(repr(key) for key in keys - expected)
            raise ValueError(
                f"invalid WorldV1 record fields: missing={missing}, extra={extra}"
            )
        if payload["schema"] != WORLD_V1_SCHEMA:
            raise WorldV1ReplayMismatch(("schema",))
        for field_name in expected - {"schema"}:
            if not _is_digest(payload[field_name]):
                raise ValueError(f"invalid WorldV1 digest in {field_name}")
        record = cls(
            schema=str(payload["schema"]),
            code_digest=str(payload["code_digest"]),
            world_digest=str(payload["world_digest"]),
            config_digest=str(payload["config_digest"]),
            fixture_digest=str(payload["fixture_digest"]),
            oracle_digest=str(payload["oracle_digest"]),
            action_sequence_digest=str(payload["action_sequence_digest"]),
            record_digest=str(payload["record_digest"]),
        )
        record._verify_record_integrity()
        return record

    def verify_replay(
        self,
        *,
        code: Any,
        world: Any,
        config: Any,
        fixture: Any,
        oracle: Any,
        action_sequence: Sequence[Any],
    ) -> None:
        """Fail unless every replay-boundary component matches the record."""
        self._verify_record_integrity()
        candidate = self.capture(
            code=code,
            world=world,
            config=config,
            fixture=fixture,
            oracle=oracle,
            action_sequence=action_sequence,
        )
        mismatches = [
            component
            for component in _COMPONENTS
            if self.component_digests[component]
            != candidate.component_digests[component]
        ]
        if mismatches:
            raise WorldV1ReplayMismatch(mismatches)

    def _verify_record_integrity(self) -> None:
        mismatches: list[str] = []
        if self.schema != WORLD_V1_SCHEMA:
            mismatches.append("schema")
        if self.record_digest != _aggregate_digest(self.component_digests):
            mismatches.append("record_digest")
        if mismatches:
            raise WorldV1ReplayMismatch(mismatches)
