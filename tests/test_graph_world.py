"""Bounded WorldV1 identity and replay-contract tests."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dharma_swarm.graph.world import (
    WORLD_V1_SCHEMA,
    WorldV1CanonicalizationError,
    WorldV1Record,
    WorldV1ReplayMismatch,
    canonical_digest,
)


def _record(**overrides):
    inputs = {
        "code": {"commit": "abc123"},
        "world": {"clock": "simulated", "seed": 7},
        "config": {"superstep_cap": 5},
        "fixture": {"model": "fixture-v1", "responses": ["ok"]},
        "oracle": {"name": "final-state", "version": 1},
        "action_sequence": [
            {"action": "dispatch", "node": "a"},
            {"action": "advance_clock", "seconds": 1},
        ],
    }
    inputs.update(overrides)
    return WorldV1Record.capture(**inputs)


def test_world_v1_captures_six_domain_separated_canonical_digests():
    payload = {"z": [2, 1], "a": "same payload"}
    record = WorldV1Record.capture(
        code=payload,
        world=payload,
        config=payload,
        fixture=payload,
        oracle=payload,
        action_sequence=[payload],
    )
    reordered = {"a": "same payload", "z": [2, 1]}
    replay = WorldV1Record.capture(
        code=reordered,
        world=reordered,
        config=reordered,
        fixture=reordered,
        oracle=reordered,
        action_sequence=[reordered],
    )

    assert record == replay
    assert record.schema == WORLD_V1_SCHEMA
    assert len(record.component_digests) == 6
    assert len(set(record.component_digests.values())) == 6
    assert all(
        value.startswith("sha256:") for value in record.component_digests.values()
    )
    assert record.record_digest.startswith("sha256:")


def test_world_v1_record_round_trips_and_verifies_exact_replay():
    record = _record()
    restored = WorldV1Record.from_dict(record.to_dict())

    assert restored == record
    restored.verify_replay(
        code={"commit": "abc123"},
        world={"seed": 7, "clock": "simulated"},
        config={"superstep_cap": 5},
        fixture={"responses": ["ok"], "model": "fixture-v1"},
        oracle={"version": 1, "name": "final-state"},
        action_sequence=(
            {"node": "a", "action": "dispatch"},
            {"seconds": 1, "action": "advance_clock"},
        ),
    )


def test_world_v1_golden_digest_vector_is_stable():
    assert _record().to_dict() == {
        "schema": "dharma_swarm.graph.world.v1",
        "code_digest": "sha256:720b8296c7f7f091a4adf797bf06049c8d2aa5fc6bf1491f83463095b62005cc",
        "world_digest": "sha256:171fcec9faa16903e59e52f28809f0aba43e0c20c57fb7281967ef1ee88af05a",
        "config_digest": "sha256:c91c9874efe8cb4f5610252e7610dc4c5ae92a98689945353082df5589732142",
        "fixture_digest": "sha256:af47312a59ba2e37695f46f6b740d1ac33e0169368618c792d161d8df6ecdd15",
        "oracle_digest": "sha256:ae11fc5bf44b6b6899398b4e873fc1c6180b04c50ead8bfdc53f77c523a1a541",
        "action_sequence_digest": "sha256:2ae1c3d8c69b38472df72d66d8d6a57891e7479f9fc16c596a8095eb3c3b8189",
        "record_digest": "sha256:42667b679a784a4b81b63aff6d5cbd028ec88549176b1461ba63e3f2e095be14",
    }


def test_world_v1_replay_reports_changed_components_in_contract_order():
    record = _record()

    with pytest.raises(WorldV1ReplayMismatch) as caught:
        record.verify_replay(
            code={"commit": "different"},
            world={"clock": "simulated", "seed": 7},
            config={"superstep_cap": 5},
            fixture={"model": "fixture-v1", "responses": ["ok"]},
            oracle={"name": "final-state", "version": 1},
            action_sequence=[{"action": "dispatch", "node": "b"}],
        )

    assert caught.value.components == ("code", "action_sequence")


def test_world_v1_rejects_tampered_aggregate_record_digest():
    payload = _record().to_dict()
    payload["record_digest"] = "sha256:" + "0" * 64

    with pytest.raises(WorldV1ReplayMismatch) as caught:
        WorldV1Record.from_dict(payload)

    assert caught.value.components == ("record_digest",)


def test_world_v1_rejects_hypothesis_minimized_key_coercion_collision():
    # Promoted ordinary regression. Hypothesis 6.155.7 `find(st.integers(), ...)`
    # minimized the stdlib-JSON collision to 0: {0: None} and {"0": None}
    # both encode as {"0":null}. WorldV1 must fail instead of minting one id.
    with pytest.raises(
        WorldV1CanonicalizationError,
        match=r"non-string mapping key 0",
    ):
        canonical_digest("world", {0: None})


json_text = st.text(
    alphabet=st.characters(exclude_categories=("Cs",)),
    max_size=20,
)
json_key = st.text(
    alphabet=st.characters(exclude_categories=("Cs",)),
    max_size=12,
)
json_scalar = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    json_text,
)
json_value = st.recursive(
    json_scalar,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(json_key, children, max_size=5),
    ),
    max_leaves=20,
)


@given(payload=st.dictionaries(json_key, json_value, max_size=8))
@settings(max_examples=100, deadline=None)
def test_world_v1_digest_is_deterministic_and_mapping_order_independent(payload):
    forward = dict(payload)
    reverse = {key: payload[key] for key in reversed(payload)}

    assert canonical_digest("config", forward) == canonical_digest("config", reverse)
