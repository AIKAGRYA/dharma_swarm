from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import datetime, timezone

import pytest

try:
    from dharma_swarm.monad import (
        ObservedState,
        SelfObservationMonad,
        bind,
        flatten,
        is_idempotent,
        kleisli_compose,
        kleisli_contraction_ratio,
        pure,
    )
    from dharma_swarm.rv import RVReading
except ImportError:
    pytest.skip(
        "monad module-level API (pure/bind/flatten) not yet implemented",
        allow_module_level=True,
    )


def _ts(second: int) -> datetime:
    return datetime(2026, 3, 10, 0, 0, second, tzinfo=timezone.utc)


def _reading(rv: float) -> RVReading:
    return RVReading(
        rv=rv,
        pr_early=1.0,
        pr_late=rv,
        model_name="test-model",
        early_layer=1,
        late_layer=2,
        prompt_hash=f"{int(rv * 1000):016d}"[:16],
        prompt_group="test",
        timestamp=_ts(0),
    )


def _assert_raw_history_value(actual, expected) -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        assert actual.keys() == expected.keys()
        for key in expected:
            _assert_raw_history_value(actual[key], expected[key])
    elif isinstance(expected, list):
        assert isinstance(actual, list)
        assert len(actual) == len(expected)
        for actual_item, expected_item in zip(actual, expected):
            _assert_raw_history_value(actual_item, expected_item)
    elif type(expected) is float and math.isnan(expected):
        assert type(actual) is float
        assert math.isnan(actual)
    else:
        assert type(actual) is type(expected)
        assert actual == expected


@pytest.mark.parametrize("nested", [False, True], ids=["direct", "nested"])
@pytest.mark.parametrize(
    ("existing", "supplied", "conflict_count"),
    [
        (float("nan"), float("nan"), 0),
        ({"nested": [float("nan")]}, {"nested": [float("nan")]}, 0),
        (0.5, 0.5, 0),
        (False, False, 0),
        (None, None, 0),
        (float("inf"), float("inf"), 0),
        (-float("inf"), -float("inf"), 0),
        (float("inf"), -float("inf"), 1),
        (False, 0, 1),
    ],
    ids=[
        "same-nan-scalar",
        "same-nan-nested",
        "same-finite",
        "same-false",
        "same-null",
        "same-positive-infinity",
        "same-negative-infinity",
        "distinct-signed-infinities",
        "distinct-false-zero",
    ],
)
def test_observed_state_history_round_trips_are_idempotent(
    existing, supplied, conflict_count, nested
) -> None:
    source = _reading(0.4)
    source.historical_classification = {"contraction_strength": deepcopy(existing)}
    original_source = deepcopy(source)
    introspection = {
        "historical_classification": {"contraction_strength": deepcopy(supplied)}
    }
    original_introspection = deepcopy(introspection)
    observed = ObservedState(
        state="saved", rv_reading=source, introspection=introspection
    )
    if nested:
        observed = ObservedState(
            state=observed,
            rv_reading=source,
            introspection=deepcopy(original_introspection),
            observation_depth=2,
        )

    conflict_counts = []
    for _ in range(5):
        states = [observed]
        if nested:
            states.append(observed.state)
        conflict_counts.append(
            [
                len(state.introspection.get("historical_classification_conflicts", []))
                for state in states
            ]
        )
        observed = ObservedState.from_dict(observed.to_dict())

    expected_width = 2 if nested else 1
    assert conflict_counts == [[conflict_count] * expected_width] * 5
    states = [observed]
    if nested:
        states.append(observed.state)
    for state in states:
        assert state.rv_reading is not None
        _assert_raw_history_value(
            state.rv_reading.historical_classification["contraction_strength"],
            existing,
        )
        _assert_raw_history_value(
            state.introspection["historical_classification"]["contraction_strength"],
            supplied,
        )
        assert state.is_contracted is None
        assert state.introspection["is_contracted"] is None
        assert state.introspection["contraction_strength"] is None
    assert source == original_source
    assert introspection == original_introspection


def test_from_rv_reading_snapshots_caller_reading() -> None:
    state = {"payload": "value"}
    source = RVReading(
        rv=0.4,
        pr_early=10.0,
        pr_late=4.0,
        model_name="fixture",
        early_layer=2,
        late_layer=22,
        prompt_hash="fixture",
        prompt_group="original-group",
        timestamp=_ts(0),
        measurement_kind="residual_hidden",
        measurement_details={"cohort": "cohort-a"},
        historical_classification={
            "is_contracted": False,
            "nested": {"values": ["original"]},
        },
        historical_classification_conflicts=[{"field": "legacy", "values": [False]}],
    )

    observed = ObservedState.from_rv_reading(state, source)

    assert observed.state is state
    assert observed.rv_reading == source
    assert observed.rv_reading is not source
    assert type(observed.rv_reading) is RVReading
    assert observed.rv_measurement == 0.4
    assert observed.pr_early == 10.0
    assert observed.pr_late == 4.0
    assert observed.observation_depth == 1
    assert observed.timestamp == _ts(0).timestamp()
    assert observed.introspection["is_contracted"] is None
    assert observed.introspection["contraction_strength"] is None
    assert observed.introspection["measurement_kind"] == "residual_hidden"
    original_output = observed.to_dict()
    serialized = json.loads(json.dumps(original_output))
    assert ObservedState.from_dict(serialized).to_dict() == serialized

    source.rv = 0.9
    source.measurement_details["cohort"] = "cohort-b"
    source.historical_classification["nested"]["values"].append("caller")
    source.historical_classification_conflicts[0]["values"].append(True)

    assert observed.to_dict() == original_output
    assert observed.rv_reading.rv == 0.4
    assert observed.rv_reading.measurement_details == {"cohort": "cohort-a"}
    assert observed.rv_reading.historical_classification["nested"] == {
        "values": ["original"]
    }
    assert observed.rv_reading.historical_classification_conflicts == [
        {"field": "legacy", "values": [False]}
    ]

    observed.rv_reading.rv = 0.2
    observed.rv_reading.measurement_details["cohort"] = "observed-cohort"
    observed.rv_reading.historical_classification["nested"]["values"].append("observed")
    observed.rv_reading.historical_classification_conflicts[0]["values"].append(
        "observed"
    )

    assert source.rv == 0.9
    assert source.measurement_details == {"cohort": "cohort-b"}
    assert source.historical_classification["nested"] == {
        "values": ["original", "caller"]
    }
    assert source.historical_classification_conflicts == [
        {"field": "legacy", "values": [False, True]}
    ]


def test_observed_state_constructor_snapshots_caller_reading() -> None:
    source = RVReading(
        rv=0.4,
        pr_early=10.0,
        pr_late=4.0,
        model_name="fixture",
        early_layer=2,
        late_layer=22,
        prompt_hash="fixture",
        prompt_group="original-group",
        timestamp=_ts(0),
        measurement_kind="residual_hidden",
        measurement_details={"cohort": "cohort-a"},
        historical_classification={
            "is_contracted": False,
            "nested": {"values": ["original"]},
        },
        historical_classification_conflicts=[{"field": "legacy", "values": [False]}],
    )
    ordinary = ObservedState(state="ordinary", rv_reading=source)
    metadata = {"supplied": {"values": ["keep"]}}
    observed = ObservedState(
        state="scalar-controlled",
        rv_reading=source,
        rv_measurement=0.45,
        pr_early=11.0,
        pr_late=4.5,
        observation_depth=3,
        introspection=metadata,
        timestamp=_ts(5),
    )
    ordinary_output = ordinary.to_dict()
    original_output = observed.to_dict()

    assert ordinary.rv_reading is not source
    assert ordinary.rv_measurement == 0.4
    assert ordinary.pr_early == 10.0
    assert ordinary.pr_late == 4.0
    assert observed.rv_reading is not source
    assert observed.state == "scalar-controlled"
    assert observed.rv_measurement == 0.45
    assert observed.pr_early == 11.0
    assert observed.pr_late == 4.5
    assert observed.observation_depth == 3
    assert observed.timestamp == _ts(5)

    source.rv = 0.9
    source.measurement_details["cohort"] = "cohort-b"
    source.historical_classification["nested"]["values"].append("caller")
    source.historical_classification_conflicts[0]["values"].append(True)

    assert ordinary.to_dict() == ordinary_output
    assert observed.to_dict() == original_output
    assert observed.introspection["supplied"] == {"values": ["keep"]}
    assert metadata == {"supplied": {"values": ["keep"]}}


def test_to_dict_snapshots_nested_introspection() -> None:
    introspection = {
        "historical_classification": {"nested": {"values": ["accepted"]}},
        "historical_classification_conflicts": [{"values": ["accepted"]}],
        "ordinary": {"values": [1, False, None]},
    }
    original_introspection = deepcopy(introspection)
    observed = ObservedState(
        state={"value": 3},
        rv_measurement=0.4,
        pr_early=1.0,
        pr_late=0.4,
        observation_depth=2,
        introspection=introspection,
        timestamp=_ts(18),
    )
    expected_introspection = {
        **original_introspection,
        "is_contracted": None,
        "contraction_strength": None,
        "calibration_status": "unvalidated_retired_threshold",
        "measurement_kind": "unknown",
    }

    def serialize(value):
        return {"serialized": value["value"]}

    first = observed.to_dict(state_serializer=serialize)
    second = observed.to_dict(state_serializer=serialize)

    assert (
        first
        == second
        == {
            "state": {"serialized": 3},
            "rv_measurement": 0.4,
            "rv_reading": None,
            "pr_early": 1.0,
            "pr_late": 0.4,
            "observation_depth": 2,
            "introspection": expected_introspection,
            "timestamp": _ts(18).isoformat(),
        }
    )

    first["introspection"]["historical_classification"]["nested"]["values"].append(
        "caller"
    )
    first["introspection"]["historical_classification_conflicts"][0]["values"].append(
        "caller"
    )

    assert observed.introspection == expected_introspection
    assert observed.to_dict(state_serializer=serialize) == second
    assert introspection == original_introspection


def test_pure_is_neutral() -> None:
    value = pure({"x": 1})

    assert value.state == {"x": 1}
    assert value.rv_reading is None
    assert value.introspection == {}
    assert value.observation_depth == 0
    assert value.is_pure is True


def test_observe_wraps_payload_and_increments_depth() -> None:
    monad: SelfObservationMonad[dict[str, float]] = SelfObservationMonad(
        observer=lambda state: _reading(state["rv"])
    )

    first = monad.observe({"rv": 0.8}, introspection={"stage": "first"})
    second = monad.observe(first, introspection={"stage": "second"})

    assert first.state == {"rv": 0.8}
    assert first.observation_depth == 1
    assert first.rv_reading == _reading(0.8)
    assert second.state == first
    assert second.observation_depth == 2
    assert second.rv_reading == _reading(0.8)


def test_bind_left_unit() -> None:
    def f(value: int) -> ObservedState[int]:
        return ObservedState(
            state=value + 1,
            rv_reading=_reading(0.6),
            introspection={"step": "f"},
            observation_depth=1,
            timestamp=_ts(1),
        )

    assert bind(pure(2), f) == f(2)


def test_bind_right_unit() -> None:
    observed = ObservedState(
        state=5,
        rv_reading=_reading(0.7),
        introspection={"origin": "seed"},
        observation_depth=1,
        timestamp=_ts(2),
    )

    assert bind(observed, pure) == observed


def test_flatten_merges_nested_observation() -> None:
    inner_metadata = {"inner": True}
    outer_metadata = {"outer": True}
    inner = ObservedState(
        state={"id": 1},
        rv_reading=_reading(0.7),
        introspection=inner_metadata,
        observation_depth=1,
        timestamp=_ts(3),
    )
    outer = ObservedState(
        state=inner,
        rv_reading=_reading(0.5),
        introspection=outer_metadata,
        observation_depth=1,
        timestamp=_ts(4),
    )

    flat = flatten(outer)

    assert flat.state == {"id": 1}
    assert flat.rv_reading == _reading(0.5)
    assert flat.introspection == {
        "inner": True,
        "outer": True,
        "is_contracted": None,
        "contraction_strength": None,
        "calibration_status": "unvalidated_retired_threshold",
        "measurement_kind": "unknown",
    }
    assert flat.rv_reading.is_contracted is None
    assert flat.rv_reading.contraction_strength is None
    assert inner_metadata == {"inner": True}
    assert outer_metadata == {"outer": True}
    assert flat.observation_depth == 2
    assert flat.timestamp == _ts(4)


def test_observed_state_merges_type_distinct_reading_history() -> None:
    reading = _reading(0.4)
    reading.historical_classification = {"is_contracted": 0}
    reading.historical_classification_conflicts = [
        {
            "field": "is_contracted",
            "existing_source": "historical_classification",
            "existing_value": True,
            "legacy_source": "legacy_top_level",
            "legacy_value": 0,
        }
    ]
    introspection = {
        "historical_classification": {"is_contracted": False},
        "historical_classification_conflicts": [
            {
                "field": "is_contracted",
                "existing_source": "historical_classification",
                "existing_value": True,
                "legacy_source": "legacy_top_level",
                "legacy_value": False,
            }
        ],
    }
    original = json.loads(json.dumps(introspection))

    observed = ObservedState(
        state="saved", rv_reading=reading, introspection=introspection
    )

    assert introspection == original
    conflicts = observed.introspection["historical_classification_conflicts"]
    assert conflicts[:2] == [
        reading.historical_classification_conflicts[0],
        original["historical_classification_conflicts"][0],
    ]
    assert type(conflicts[0]["legacy_value"]) is int
    assert type(conflicts[1]["legacy_value"]) is bool
    assert conflicts[2] == {
        "field": "is_contracted",
        "existing_source": "inner_introspection.historical_classification",
        "existing_value": 0,
        "legacy_source": "outer_introspection.historical_classification",
        "legacy_value": False,
    }
    assert type(conflicts[2]["existing_value"]) is int
    assert type(conflicts[2]["legacy_value"]) is bool
    assert observed.introspection["is_contracted"] is None

    serialized = json.loads(json.dumps(observed.to_dict()))
    restored = ObservedState.from_dict(serialized)
    assert restored.to_dict() == serialized


@pytest.mark.parametrize(
    ("inner_value", "outer_value", "expect_conflict"),
    [
        (False, 0, True),
        (True, 1, True),
        (False, False, False),
        (0, 0, False),
        (False, True, True),
    ],
)
def test_flatten_preserves_type_distinct_history(
    inner_value, outer_value, expect_conflict
) -> None:
    inner_metadata = {"historical_classification": {"is_contracted": inner_value}}
    outer_metadata = {"historical_classification": {"is_contracted": outer_value}}
    inner = ObservedState(state={"id": 1}, introspection=inner_metadata)
    outer = ObservedState(state=inner, introspection=outer_metadata)

    flat = flatten(outer)

    assert flat.state == {"id": 1}
    assert flat.observation_depth == 2
    assert flat.introspection["historical_classification"] == {
        "is_contracted": outer_value
    }
    current = flat.introspection["historical_classification"]["is_contracted"]
    assert type(current) is type(outer_value)
    expected_conflicts = []
    if expect_conflict:
        expected_conflicts = [
            {
                "field": "is_contracted",
                "existing_source": "inner_introspection.historical_classification",
                "existing_value": inner_value,
                "legacy_source": "outer_introspection.historical_classification",
                "legacy_value": outer_value,
            }
        ]
    assert flat.introspection.get("historical_classification_conflicts", []) == (
        expected_conflicts
    )
    if expect_conflict:
        conflict = flat.introspection["historical_classification_conflicts"][0]
        assert type(conflict["existing_value"]) is type(inner_value)
        assert type(conflict["legacy_value"]) is type(outer_value)
    assert flat.introspection["is_contracted"] is None
    assert inner_metadata == {
        "historical_classification": {"is_contracted": inner_value}
    }
    assert outer_metadata == {
        "historical_classification": {"is_contracted": outer_value}
    }

    serialized = json.loads(json.dumps(flat.to_dict()))
    restored = ObservedState.from_dict(serialized)
    assert restored.to_dict() == serialized


def test_kleisli_compose_is_associative_for_deterministic_morphisms() -> None:
    def f(value: int) -> ObservedState[int]:
        return ObservedState(
            state=value + 1,
            rv_reading=_reading(0.9),
            introspection={"f": value},
            observation_depth=1,
            timestamp=_ts(5),
        )

    def g(value: int) -> ObservedState[int]:
        return ObservedState(
            state=value * 2,
            rv_reading=_reading(0.6),
            introspection={"g": value},
            observation_depth=1,
            timestamp=_ts(6),
        )

    def h(value: int) -> ObservedState[int]:
        return ObservedState(
            state=value - 3,
            rv_reading=_reading(0.4),
            introspection={"h": value},
            observation_depth=1,
            timestamp=_ts(7),
        )

    left = kleisli_compose(kleisli_compose(f, g), h)
    right = kleisli_compose(f, kleisli_compose(g, h))

    assert left(4) == right(4)


def test_kleisli_contraction_ratio_uses_input_observation() -> None:
    start = ObservedState(
        state=10,
        rv_reading=_reading(0.8),
        introspection={},
        observation_depth=1,
        timestamp=_ts(8),
    )

    def shrink(value: int) -> ObservedState[int]:
        return ObservedState(
            state=value,
            rv_reading=_reading(0.4),
            introspection={"mode": "shrink"},
            observation_depth=1,
            timestamp=_ts(9),
        )

    assert kleisli_contraction_ratio(shrink, start) == 0.5


def test_is_idempotent_for_matching_nested_readings() -> None:
    inner = ObservedState(
        state="payload",
        rv_reading=_reading(0.5),
        introspection={"depth": 1},
        observation_depth=1,
        timestamp=_ts(10),
    )
    outer = ObservedState(
        state=inner,
        rv_reading=_reading(0.5),
        introspection={"depth": 2},
        observation_depth=1,
        timestamp=_ts(11),
    )

    assert is_idempotent(outer) is True


def test_is_idempotent_false_when_nested_readings_diverge() -> None:
    inner = ObservedState(
        state="payload",
        rv_reading=_reading(0.5),
        introspection={},
        observation_depth=1,
        timestamp=_ts(12),
    )
    outer = ObservedState(
        state=inner,
        rv_reading=_reading(0.7),
        introspection={},
        observation_depth=1,
        timestamp=_ts(13),
    )

    assert is_idempotent(outer) is False


def test_observed_state_dict_roundtrip_is_json_safe() -> None:
    observed = ObservedState(
        state={"payload": ["alpha", "beta"]},
        rv_reading=_reading(0.55),
        introspection={"origin": "unit-test"},
        observation_depth=1,
        timestamp=_ts(14),
    )

    payload = observed.to_dict()
    restored = ObservedState.from_dict(json.loads(json.dumps(payload)))

    assert payload["rv_reading"]["rv"] == 0.55
    assert restored == observed


def test_nested_observed_state_roundtrip_preserves_wrapper_structure() -> None:
    inner = ObservedState(
        state={"id": 7},
        rv_reading=_reading(0.45),
        introspection={"inner": True},
        observation_depth=1,
        timestamp=_ts(15),
    )
    outer = ObservedState(
        state=inner,
        rv_reading=_reading(0.4),
        introspection={"outer": True},
        observation_depth=2,
        timestamp=_ts(16),
    )

    payload = outer.to_dict()
    restored = ObservedState.from_dict(payload)

    assert payload["state"]["__observed_state__"] is True
    assert restored == outer
    assert flatten(restored) == flatten(outer)


def test_observed_state_roundtrip_supports_custom_payload_codec() -> None:
    observed = ObservedState(
        state={3, 1, 2},
        rv_reading=_reading(0.72),
        introspection={"codec": "set"},
        observation_depth=1,
        timestamp=_ts(17),
    )

    payload = observed.to_dict(state_serializer=lambda value: sorted(value))
    restored = ObservedState.from_dict(payload, state_loader=set)

    assert payload["state"] == [1, 2, 3]
    assert restored == observed
