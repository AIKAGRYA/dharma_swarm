"""Public behavior for retired scientific classification and measurement custody."""

import json
from collections import deque
from copy import deepcopy
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from dharma_swarm.bridge import CorrelationResult, EvolutionBridge, ResearchBridge
from dharma_swarm.monad import ObservedState, SelfObservationMonad, bind, flatten
from dharma_swarm.ouroboros import colony_rv_reading
from dharma_swarm.rv import RV_CALIBRATION_STATUS, EvolutionRVTracker, RVReading

_MISSING = object()


def reading(value=0.6, kind="unknown", **overrides):
    values = dict(
        rv=value, pr_early=10, pr_late=10 * value, model_name="fixture",
        early_layer=2, late_layer=22, prompt_hash="fixture", measurement_kind=kind,
        measurement_details={"cohort": "retraction-fixture"},
    )
    values.update(overrides)
    return RVReading(**values)


def evolution_metadata(kind):
    details = {"cohort": "evolution-fixture"}
    if kind in {"behavioral_proxy", "colony_density"}:
        details["formula"] = f"{kind} fixture formula"
    return {
        "model_name": "fixture",
        "early_layer": 2,
        "late_layer": 22,
        "measurement_details": details,
    }


def test_legacy_reading_round_trip_does_not_invent_provenance():
    legacy = reading().model_dump(mode="json")
    for key in ("measurement_kind", "measurement_details", "calibration_status"):
        legacy.pop(key)
    restored = RVReading.model_validate(legacy)
    assert restored.rv == 0.6
    assert restored.pr_late == 6
    assert restored.measurement_kind == "unknown"
    assert restored.is_contracted is None
    assert restored.contraction_strength is None
    assert restored.historical_classification == {}
    assert restored.historical_classification_conflicts == []
    assert RVReading.model_validate_json(restored.model_dump_json()) == restored


@pytest.mark.parametrize("contracted", [True, False])
def test_legacy_reading_preserves_classification_only_as_history(contracted):
    payload = reading(0.4, "residual_hidden").model_dump(mode="json")
    payload.update(is_contracted=contracted, contraction_strength="strong")
    original = json.loads(json.dumps(payload))

    restored = RVReading.model_validate(payload)

    assert payload == original
    assert restored.rv == 0.4
    assert restored.pr_early == 10
    assert restored.pr_late == 4
    assert restored.measurement_kind == "residual_hidden"
    assert restored.measurement_details == {"cohort": "retraction-fixture"}
    assert restored.is_contracted is None
    assert restored.contraction_strength is None
    assert restored.historical_classification == {
        "is_contracted": contracted,
        "contraction_strength": "strong",
    }
    assert restored.historical_classification_conflicts == []
    serialized = restored.model_dump(mode="json")
    assert "is_contracted" not in serialized
    assert "contraction_strength" not in serialized
    assert RVReading.model_validate_json(restored.model_dump_json()) == restored


def test_legacy_reading_retains_existing_history_and_conflicting_values():
    payload = reading().model_dump(mode="json")
    payload["historical_classification"] = {
        "is_contracted": False,
        "contraction_strength": "weak",
        "raw_legacy_field": {"keep": [1, 2]},
    }
    payload["historical_classification_conflicts"] = [
        {"field": "other", "values": ["keep"]},
    ]
    payload.update(is_contracted=True, contraction_strength="strong")
    original = json.loads(json.dumps(payload))

    restored = RVReading.model_validate(payload)

    assert payload == original
    assert restored.historical_classification == original["historical_classification"]
    assert restored.historical_classification_conflicts == [
        {"field": "other", "values": ["keep"]},
        {
            "field": "is_contracted",
            "existing_source": "historical_classification",
            "existing_value": False,
            "legacy_source": "legacy_top_level",
            "legacy_value": True,
        },
        {
            "field": "contraction_strength",
            "existing_source": "historical_classification",
            "existing_value": "weak",
            "legacy_source": "legacy_top_level",
            "legacy_value": "strong",
        },
    ]
    assert restored.is_contracted is None
    assert restored.contraction_strength is None
    assert RVReading.model_validate_json(restored.model_dump_json()) == restored


def test_nested_observed_state_preserves_legacy_classification_history():
    rv_payload = reading(0.4, "residual_hidden").model_dump(mode="json")
    rv_payload.update(is_contracted=True, contraction_strength="strong")
    payload = {"state": "saved", "rv_reading": rv_payload, "timestamp": 1.0}
    original = json.loads(json.dumps(payload))

    observed = ObservedState.from_dict(payload)
    output = json.loads(json.dumps(observed.to_dict()))
    restored = ObservedState.from_dict(output)

    assert payload == original
    assert restored.rv_measurement == 0.4
    assert restored.rv_reading is not None
    assert restored.rv_reading.historical_classification == {
        "is_contracted": True,
        "contraction_strength": "strong",
    }
    assert restored.rv_reading.is_contracted is None
    assert restored.rv_reading.contraction_strength is None
    assert restored.to_dict() == output


async def test_research_bridge_load_save_preserves_legacy_classification_history(tmp_path):
    path = tmp_path / "legacy-pairs.jsonl"
    seed = ResearchBridge(path)
    paired = await seed.add_measurement(
        "legacy", "L4", "A factual response.",
        rv_reading=reading(0.4, "residual_hidden"),
    )
    payload = paired.model_dump(mode="json")
    payload["rv_reading"].update(is_contracted=False, contraction_strength="strong")
    path.write_text(json.dumps(payload) + "\n")

    bridge = ResearchBridge(path)
    await bridge.load()
    restored = bridge.get_measurements()[0].rv_reading

    assert restored is not None
    assert restored.rv == 0.4
    assert restored.measurement_kind == "residual_hidden"
    assert restored.historical_classification == {
        "is_contracted": False,
        "contraction_strength": "strong",
    }
    assert restored.is_contracted is None
    assert restored.contraction_strength is None

    await bridge.save()
    persisted = json.loads(path.read_text())
    assert persisted["rv_reading"]["historical_classification"] == {
        "is_contracted": False,
        "contraction_strength": "strong",
    }
    assert persisted["rv_reading"]["rv"] == 0.4
    assert "is_contracted" not in persisted["rv_reading"]
    assert "contraction_strength" not in persisted["rv_reading"]

    reloaded = ResearchBridge(path)
    await reloaded.load()
    await reloaded.save()
    assert json.loads(path.read_text()) == persisted


def test_unrecognized_instrument_cannot_assert_a_scientific_verdict():
    with pytest.raises(ValidationError):
        reading(kind="validated-awareness")


def test_old_aggregate_overlap_is_historical_not_current_classification():
    result = CorrelationResult.model_validate({"n": 50, "contraction_recognition_overlap": 0.78})
    current = json.loads(result.model_dump_json())
    assert current["contraction_recognition_overlap"] is None
    assert current["historical_contraction_recognition_overlap"] == 0.78
    assert current["classification_count"] == 0


def test_colony_ratio_stays_an_operational_observation():
    observed = colony_rv_reading(10, 3)
    assert observed.rv == 0.3
    assert observed.measurement_kind == "colony_density"
    assert observed.is_contracted is None
    assert observed.contraction_strength is None


async def test_tracker_separates_proxy_from_residual_and_does_not_pool(tmp_path):
    tracker = EvolutionRVTracker(tmp_path)
    proxy = await tracker.measure_cycle("proxy", 0.8, 5)
    measurer = Mock()
    measurer.is_available.return_value = True
    measurer.measure = AsyncMock(return_value=reading(0.4, "residual_hidden"))
    residual = await tracker.measure_cycle("residual", 0.9, 2, measurer=measurer)
    assert proxy["rv"] == 0.5
    assert proxy["measurement_kind"] == "behavioral_proxy"
    assert residual["rv"] == 0.4
    assert residual["measurement_kind"] == "residual_hidden"
    assert residual["model_name"] == "fixture"
    assert residual["early_layer"] == 2
    assert residual["late_layer"] == 22
    rows = [json.loads(line) for line in (tmp_path / "evolution_rv.jsonl").read_text().splitlines()]
    assert all(row["is_contracted"] is None for row in rows)
    assert tracker.get_rv_fitness_pairs() == []
    assert tracker.get_trend() is None
    assert [r["rv"] for r in tracker.get_readings()] == [0.5, 0.4]


async def test_tracker_historical_classification_is_retained_only_as_history(tmp_path):
    path = tmp_path / "evolution_rv.jsonl"
    before = json.dumps({"rv": 0.4, "best_fitness": 0.8, "rv_source": "geometric",
                         "is_contracted": True, "contraction_strength": "strong"}) + "\n"
    path.write_text(before)
    tracker = EvolutionRVTracker(tmp_path)
    await tracker.load()
    row = tracker.get_readings()[0]
    assert row["rv"] == 0.4
    assert row["measurement_kind"] == "unknown"
    assert row["is_contracted"] is None
    assert row["contraction_strength"] is None
    assert row["historical_classification"] == {"is_contracted": True, "contraction_strength": "strong"}
    assert tracker.get_rv_fitness_pairs() == []
    assert path.read_text() == before  # Loading never rewrites the historical file.


def test_monad_historical_strength_cannot_escape_as_current_classification():
    payload = {"state": "saved", "rv_measurement": 0.4,
               "introspection": {"contraction_strength": "strong"}, "timestamp": 1.0}
    observed = ObservedState.from_dict(payload)
    output = observed.to_dict()
    assert observed.rv == 0.4
    assert observed.is_contracted is None
    assert output["introspection"]["contraction_strength"] is None
    assert output["introspection"]["measurement_kind"] == "unknown"
    assert output["introspection"]["historical_classification"]["contraction_strength"] == "strong"
    assert payload["introspection"] == {"contraction_strength": "strong"}


async def test_tracker_load_preserves_conflicting_legacy_classification(tmp_path):
    record = {
        "rv": 0.4,
        "best_fitness": 0.8,
        "measurement_kind": "residual_hidden",
        **evolution_metadata("residual_hidden"),
        "historical_classification": {
            "is_contracted": False,
            "contraction_strength": "moderate",
            "raw_legacy_field": {"keep": [1, 2]},
        },
        "historical_classification_conflicts": [{"field": "other", "values": ["keep"]}],
        "is_contracted": True,
        "contraction_strength": "strong",
    }
    path = tmp_path / "evolution_rv.jsonl"
    before = json.dumps(record) + "\n"
    path.write_text(before)

    tracker = EvolutionRVTracker(tmp_path)
    await tracker.load()
    rows = tracker.get_readings()

    assert path.read_text() == before
    assert rows[0]["rv"] == 0.4
    assert rows[0]["best_fitness"] == 0.8
    assert rows[0]["is_contracted"] is None
    assert rows[0]["contraction_strength"] is None
    assert rows[0]["historical_classification"] == record["historical_classification"]
    assert rows[0]["historical_classification_conflicts"] == [
        {"field": "other", "values": ["keep"]},
        {
            "field": "is_contracted",
            "existing_source": "historical_classification",
            "existing_value": False,
            "legacy_source": "legacy_top_level",
            "legacy_value": True,
        },
        {
            "field": "contraction_strength",
            "existing_source": "historical_classification",
            "existing_value": "moderate",
            "legacy_source": "legacy_top_level",
            "legacy_value": "strong",
        },
    ]
    assert tracker.get_rv_fitness_pairs() == [(0.4, 0.8)]

    restored_dir = tmp_path / "restored"
    restored_dir.mkdir()
    (restored_dir / "evolution_rv.jsonl").write_text(
        json.dumps(json.loads(json.dumps(rows[0]))) + "\n"
    )
    restored = EvolutionRVTracker(restored_dir)
    await restored.load()
    assert restored.get_readings() == rows


def test_observed_state_preserves_conflicting_introspection_history():
    payload = {
        "state": "saved",
        "rv_measurement": 0.4,
        "introspection": {
            "measurement_kind": "behavioral_proxy",
            "measurement_details": {"cohort": "fixture", "formula": "raw-formula"},
            "historical_classification": {
                "is_contracted": False,
                "contraction_strength": "moderate",
                "raw_legacy_field": {"keep": [1, 2]},
            },
            "historical_classification_conflicts": [{"field": "other", "values": ["keep"]}],
            "is_contracted": True,
            "contraction_strength": "strong",
        },
        "timestamp": 1.0,
    }
    original = json.loads(json.dumps(payload))

    observed = ObservedState.from_dict(payload)
    output = json.loads(json.dumps(observed.to_dict()))
    restored = ObservedState.from_dict(output)

    assert payload == original
    assert observed.rv_measurement == 0.4
    assert observed.is_contracted is None
    assert output["introspection"]["is_contracted"] is None
    assert output["introspection"]["contraction_strength"] is None
    assert output["introspection"]["historical_classification"] == original[
        "introspection"
    ]["historical_classification"]
    assert output["introspection"]["historical_classification_conflicts"][1:] == [
        {
            "field": "is_contracted",
            "existing_source": "historical_classification",
            "existing_value": False,
            "legacy_source": "legacy_top_level",
            "legacy_value": True,
        },
        {
            "field": "contraction_strength",
            "existing_source": "historical_classification",
            "existing_value": "moderate",
            "legacy_source": "legacy_top_level",
            "legacy_value": "strong",
        },
    ]
    assert output["introspection"]["measurement_kind"] == "behavioral_proxy"
    assert output["introspection"]["measurement_details"] == original[
        "introspection"
    ]["measurement_details"]
    assert restored.to_dict() == output


def test_correlation_result_preserves_conflicting_legacy_overlap():
    payload = {
        "n": 50,
        "pearson_r": -0.2,
        "contraction_recognition_overlap": 0.9,
        "historical_contraction_recognition_overlap": 0.1,
        "historical_contraction_recognition_overlap_conflicts": [
            {"field": "other", "values": ["keep"]}
        ],
    }
    original = json.loads(json.dumps(payload))

    result = CorrelationResult.model_validate(payload)
    output = json.loads(result.model_dump_json())
    restored = CorrelationResult.model_validate(output)

    assert payload == original
    assert result.pearson_r == -0.2
    assert result.contraction_recognition_overlap is None
    assert result.historical_contraction_recognition_overlap == 0.1
    assert result.historical_contraction_recognition_overlap_conflicts == [
        {"field": "other", "values": ["keep"]},
        {
            "field": "contraction_recognition_overlap",
            "existing_source": "historical_contraction_recognition_overlap",
            "existing_value": 0.1,
            "legacy_source": "legacy_top_level",
            "legacy_value": 0.9,
        },
    ]
    assert output["classification_count"] == 0
    assert restored == result


def test_legacy_reading_retains_explicit_null_history():
    payload = reading().model_dump(mode="json")
    payload["historical_classification"] = {
        "is_contracted": None,
        "contraction_strength": None,
    }
    payload.update(is_contracted=True, contraction_strength="strong")
    original = json.loads(json.dumps(payload))

    restored = RVReading.model_validate(payload)

    assert payload == original
    assert restored.is_contracted is None
    assert restored.contraction_strength is None
    assert restored.historical_classification == original["historical_classification"]
    assert restored.historical_classification_conflicts == [
        {
            "field": "is_contracted",
            "existing_source": "historical_classification",
            "existing_value": None,
            "legacy_source": "legacy_top_level",
            "legacy_value": True,
        },
        {
            "field": "contraction_strength",
            "existing_source": "historical_classification",
            "existing_value": None,
            "legacy_source": "legacy_top_level",
            "legacy_value": "strong",
        },
    ]
    assert RVReading.model_validate_json(restored.model_dump_json()) == restored


async def test_tracker_and_observed_state_retain_explicit_null_history(tmp_path):
    historical = {"is_contracted": None, "contraction_strength": None}
    legacy = {"is_contracted": True, "contraction_strength": "strong"}
    record = {
        "rv": 0.4,
        "best_fitness": 0.8,
        "historical_classification": historical,
        **legacy,
    }
    path = tmp_path / "evolution_rv.jsonl"
    path.write_text(json.dumps(record) + "\n")
    tracker = EvolutionRVTracker(tmp_path)
    await tracker.load()
    row = tracker.get_readings()[0]

    payload = {
        "state": "saved",
        "rv_measurement": 0.4,
        "introspection": {"historical_classification": historical, **legacy},
        "timestamp": 1.0,
    }
    original = json.loads(json.dumps(payload))
    observed = ObservedState.from_dict(payload)
    output = json.loads(json.dumps(observed.to_dict()))

    assert payload == original
    for introspection in (row, output["introspection"]):
        assert introspection["is_contracted"] is None
        assert introspection["contraction_strength"] is None
        assert introspection["historical_classification"] == historical
        assert [conflict["existing_value"] for conflict in introspection[
            "historical_classification_conflicts"
        ]] == [None, None]
        assert [conflict["legacy_value"] for conflict in introspection[
            "historical_classification_conflicts"
        ]] == [True, "strong"]
    assert ObservedState.from_dict(output).to_dict() == output

    restored_dir = tmp_path / "restored"
    restored_dir.mkdir()
    (restored_dir / "evolution_rv.jsonl").write_text(json.dumps(row) + "\n")
    restored = EvolutionRVTracker(restored_dir)
    await restored.load()
    assert restored.get_readings() == [row]


async def test_malformed_history_is_annotated_without_current_verdicts(tmp_path):
    historical = "corrupt-history"
    raw_conflicts = {"unexpected": "metadata"}
    legacy = {"is_contracted": True, "contraction_strength": "strong"}
    expected_history = {"raw_historical_classification": historical, **legacy}
    expected_conflicts = [{
        "field": "historical_classification_conflicts",
        "existing_source": "historical_classification_conflicts",
        "existing_value": raw_conflicts,
    }]
    values = {
        "historical_classification": historical,
        "historical_classification_conflicts": raw_conflicts,
        **legacy,
    }

    rv_payload = reading().model_dump(mode="json")
    rv_payload.update(values)
    restored_reading = RVReading.model_validate(rv_payload)

    path = tmp_path / "evolution_rv.jsonl"
    path.write_text(json.dumps({"rv": 0.4, "best_fitness": 0.8, **values}) + "\n")
    tracker = EvolutionRVTracker(tmp_path)
    await tracker.load()
    row = tracker.get_readings()[0]

    observed = ObservedState.from_dict({
        "state": "saved",
        "rv_measurement": 0.4,
        "introspection": values,
        "timestamp": 1.0,
    })
    observed_output = json.loads(json.dumps(observed.to_dict()))

    for output in (
        restored_reading.model_dump(mode="json"),
        row,
        observed_output["introspection"],
    ):
        assert output["historical_classification"] == expected_history
        assert output["historical_classification_conflicts"] == expected_conflicts
    assert restored_reading.is_contracted is None
    assert restored_reading.contraction_strength is None
    assert row["is_contracted"] is None
    assert row["contraction_strength"] is None
    assert observed_output["introspection"]["is_contracted"] is None
    assert observed_output["introspection"]["contraction_strength"] is None
    assert RVReading.model_validate_json(restored_reading.model_dump_json()) == restored_reading
    assert ObservedState.from_dict(observed_output).to_dict() == observed_output

    restored_dir = tmp_path / "restored"
    restored_dir.mkdir()
    (restored_dir / "evolution_rv.jsonl").write_text(json.dumps(row) + "\n")
    restored = EvolutionRVTracker(restored_dir)
    await restored.load()
    assert restored.get_readings() == [row]


@pytest.mark.parametrize("historical_overlap", [0.1, 0.0, None])
@pytest.mark.parametrize(
    "initial_conflicts",
    [None, [], [{"field": "other", "values": ["keep"]}]],
)
def test_correlation_result_persists_new_and_existing_conflict_lists(
    historical_overlap, initial_conflicts,
):
    payload = {
        "n": 50,
        "pearson_r": -0.2,
        "contraction_recognition_overlap": 0.9,
        "historical_contraction_recognition_overlap": historical_overlap,
    }
    if initial_conflicts is not None:
        payload["historical_contraction_recognition_overlap_conflicts"] = initial_conflicts
    original = json.loads(json.dumps(payload))

    result = CorrelationResult.model_validate(payload)
    output = json.loads(result.model_dump_json())

    assert payload == original
    assert result.pearson_r == -0.2
    assert result.contraction_recognition_overlap is None
    assert result.historical_contraction_recognition_overlap == historical_overlap
    assert result.historical_contraction_recognition_overlap_conflicts == [
        *(initial_conflicts or []),
        {
            "field": "contraction_recognition_overlap",
            "existing_source": "historical_contraction_recognition_overlap",
            "existing_value": historical_overlap,
            "legacy_source": "legacy_top_level",
            "legacy_value": 0.9,
        },
    ]
    assert CorrelationResult.model_validate(output) == result


def test_correlation_result_same_overlap_adds_no_conflict():
    result = CorrelationResult.model_validate({
        "n": 50,
        "contraction_recognition_overlap": 0.9,
        "historical_contraction_recognition_overlap": 0.9,
    })
    assert result.historical_contraction_recognition_overlap == 0.9
    assert result.historical_contraction_recognition_overlap_conflicts == []
    assert CorrelationResult.model_validate_json(result.model_dump_json()) == result


def test_batch_result_retains_new_nested_overlap_conflict():
    from dharma_swarm.l4_rv_correlator import BatchResult

    batch = BatchResult.model_validate({
        "correlation": {
            "n": 50,
            "contraction_recognition_overlap": 0.9,
            "historical_contraction_recognition_overlap": 0.1,
        },
    })
    output = json.loads(batch.model_dump_json())
    correlation = output["correlation"]

    assert correlation["contraction_recognition_overlap"] is None
    assert correlation["historical_contraction_recognition_overlap"] == 0.1
    assert correlation["historical_contraction_recognition_overlap_conflicts"] == [{
        "field": "contraction_recognition_overlap",
        "existing_source": "historical_contraction_recognition_overlap",
        "existing_value": 0.1,
        "legacy_source": "legacy_top_level",
        "legacy_value": 0.9,
    }]
    assert BatchResult.model_validate(output) == batch


@pytest.mark.parametrize("sequence_factory", [tuple, deque], ids=["tuple", "deque"])
def test_correlation_result_preserves_accepted_conflict_sequences(sequence_factory):
    from dharma_swarm.l4_rv_correlator import BatchResult

    existing = {"field": "other", "values": ["keep"]}
    payload = {
        "n": 50,
        "contraction_recognition_overlap": 0.9,
        "historical_contraction_recognition_overlap": 0.1,
        "historical_contraction_recognition_overlap_conflicts": sequence_factory(
            [existing]
        ),
    }
    original = deepcopy(payload)

    result = CorrelationResult.model_validate(payload)
    batch = BatchResult.model_validate({"correlation": payload})
    expected_conflicts = [
        existing,
        {
            "field": "contraction_recognition_overlap",
            "existing_source": "historical_contraction_recognition_overlap",
            "existing_value": 0.1,
            "legacy_source": "legacy_top_level",
            "legacy_value": 0.9,
        },
    ]

    assert payload == original
    for correlation in (result, batch.correlation):
        assert correlation.contraction_recognition_overlap is None
        assert correlation.historical_contraction_recognition_overlap == 0.1
        assert correlation.historical_contraction_recognition_overlap_conflicts == (
            expected_conflicts
        )
    assert CorrelationResult.model_validate_json(result.model_dump_json()) == result
    restored = BatchResult.model_validate_json(batch.model_dump_json())
    assert restored == batch
    assert restored.model_dump_json() == batch.model_dump_json()


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [("residual_hidden", "residual_hidden"), (None, "unknown"), ("invalid", "unknown")],
)
def test_monad_scalar_round_trip_preserves_only_valid_explicit_kind(supplied, expected):
    introspection = {} if supplied is None else {"measurement_kind": supplied}
    observed = ObservedState(state="saved", rv_measurement=0.4, introspection=introspection)
    restored = ObservedState.from_dict(observed.to_dict())
    assert restored.introspection["measurement_kind"] == expected
    assert restored.introspection["is_contracted"] is None
    assert restored.introspection["contraction_strength"] is None
    assert restored.rv_measurement == 0.4


@pytest.mark.parametrize("kinds", [("residual_hidden", "colony_density"), ("unknown", "unknown")])
async def test_research_bridge_withholds_mixed_or_unknown_statistics(tmp_path, kinds):
    bridge = ResearchBridge(tmp_path / "pairs.jsonl")
    for index, kind in enumerate(kinds):
        await bridge.add_measurement(str(index), "same-group", "A factual response.",
                                     rv_reading=reading(0.4 + index * 0.2, kind))
    result = bridge.compute_correlation()
    assert result.n == 2
    assert result.pearson_r is None
    assert result.contraction_recognition_overlap is None
    assert result.classification_count == 0
    assert sum(result.measurement_kind_counts.values()) == 2
    assert bridge.group_summary()["same-group"]["mean_rv"] is None
    assert [m.rv_reading.rv for m in bridge.get_measurements()] == pytest.approx([0.4, 0.6])


async def test_research_bridge_snapshots_accepted_reading_provenance(tmp_path):
    path = tmp_path / "pairs.jsonl"
    bridge = ResearchBridge(path)
    first = reading(
        0.4,
        "residual_hidden",
        measurement_details={"cohort": "cohort-a"},
        historical_classification={"raw": {"accepted": True}},
    )
    accepted = deepcopy(first)
    await bridge.add_measurement("first", "same", "First response.", rv_reading=first)

    first.rv = 0.99
    first.measurement_details["cohort"] = "cohort-b"
    first.historical_classification["raw"]["accepted"] = False
    for value in (0.6, 0.8):
        await bridge.add_measurement(
            str(value),
            "same",
            "Another response.",
            rv_reading=reading(
                value,
                "residual_hidden",
                measurement_details={"cohort": "cohort-b"},
            ),
        )

    assert bridge.get_measurements()[0].rv_reading == accepted
    assert bridge.compute_correlation().mean_rv_by_group == {}
    assert bridge.group_summary()["same"]["mean_rv"] is None

    restored = ResearchBridge(path)
    await restored.load()
    assert restored.get_measurements()[0].rv_reading == accepted
    assert restored.compute_correlation().mean_rv_by_group == {}

    compatible = ResearchBridge(tmp_path / "compatible.jsonl")
    for value in (0.4, 0.6, 0.8):
        await compatible.add_measurement(
            str(value),
            "same",
            "A factual response.",
            rv_reading=reading(value, "residual_hidden"),
        )
    assert compatible.compute_correlation().mean_rv_by_group["same"] == pytest.approx(0.6)


@pytest.mark.parametrize("accessor", ["add", "all", "filtered"])
async def test_research_bridge_returned_measurements_are_private_snapshots(
    tmp_path, accessor
):
    path = tmp_path / f"{accessor}-pairs.jsonl"
    bridge = ResearchBridge(path)
    first = reading(
        0.4,
        "residual_hidden",
        measurement_details={"cohort": "cohort-a"},
        historical_classification={"raw": {"accepted": True}},
    )
    accepted = deepcopy(first)

    if accessor == "add":
        returned = await bridge.add_measurement(
            "first", "same", "First response.", rv_reading=first
        )
    else:
        await bridge.add_measurement("first", "same", "First response.", rv_reading=first)
        group = None if accessor == "all" else "same"
        returned = bridge.get_measurements(group=group)[0]
    accepted_id = returned.id

    returned.rv_reading.rv = 0.99
    returned.rv_reading.measurement_details["cohort"] = "cohort-b"
    returned.rv_reading.historical_classification["raw"]["accepted"] = False
    for value in (0.6, 0.8):
        await bridge.add_measurement(
            str(value),
            "same",
            "Another response.",
            rv_reading=reading(
                value,
                "residual_hidden",
                measurement_details={"cohort": "cohort-b"},
            ),
        )

    archived = bridge.get_measurements()[0]
    assert archived.id == accepted_id
    assert archived.rv_reading == accepted
    assert first == accepted
    assert bridge.compute_correlation().mean_rv_by_group == {}
    assert bridge.group_summary()["same"]["mean_rv"] is None

    await bridge.save()
    restored = ResearchBridge(path)
    await restored.load()
    assert restored.get_measurements()[0].rv_reading == accepted
    assert restored.compute_correlation().mean_rv_by_group == {}

    compatible = ResearchBridge(tmp_path / f"{accessor}-compatible.jsonl")
    for value in (0.4, 0.6, 0.8):
        await compatible.add_measurement(
            str(value),
            "same",
            "A factual response.",
            rv_reading=reading(value, "residual_hidden"),
        )
    assert compatible.compute_correlation().mean_rv_by_group["same"] == pytest.approx(0.6)


async def test_tracker_returned_record_is_a_private_snapshot(tmp_path):
    tracker = EvolutionRVTracker(tmp_path)
    source = reading(
        0.4,
        "residual_hidden",
        measurement_details={"cohort": "cohort-a"},
    )
    original_source = deepcopy(source)
    measurer = Mock()
    measurer.is_available.return_value = True
    measurer.measure = AsyncMock(return_value=source)
    first = await tracker.measure_cycle("a", 0.8, 1, measurer=measurer)
    accepted = deepcopy(first)

    first["rv"] = 0.2
    first["measurement_details"]["cohort"] = "cohort-b"
    measurer.measure.return_value = reading(
        0.6,
        "residual_hidden",
        measurement_details={"cohort": "cohort-b"},
    )
    await tracker.measure_cycle("b", 0.7, 1, measurer=measurer)

    assert source == original_source
    assert tracker.get_readings()[0] == accepted
    assert tracker.get_rv_fitness_pairs() == []
    assert tracker.get_trend() is None

    restored = EvolutionRVTracker(tmp_path)
    await restored.load()
    restored_first = restored.get_readings()[0]
    for key, value in accepted.items():
        assert restored_first[key] == value
    assert restored.get_rv_fitness_pairs() == []
    assert restored.get_trend() is None

    compatible = EvolutionRVTracker(tmp_path / "compatible")
    compatible_measurer = Mock()
    compatible_measurer.is_available.return_value = True
    compatible_measurer.measure = AsyncMock(return_value=source)
    await compatible.measure_cycle("a", 0.8, 1, measurer=compatible_measurer)
    compatible_measurer.measure.return_value = reading(
        0.6,
        "residual_hidden",
        measurement_details={"cohort": "cohort-a"},
    )
    await compatible.measure_cycle("b", 0.7, 1, measurer=compatible_measurer)
    assert compatible.get_rv_fitness_pairs() == [(0.4, 0.8), (0.6, 0.7)]
    assert compatible.get_trend() == pytest.approx(0.2)


@pytest.mark.parametrize("field", ["rv", "best_fitness"])
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="null"),
        pytest.param("not-a-number", id="nonnumeric"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="positive-infinity"),
        pytest.param(-float("inf"), id="negative-infinity"),
        pytest.param(_MISSING, id="missing"),
    ],
)
async def test_tracker_invalid_or_missing_numbers_make_whole_cohort_unavailable(
    tmp_path, field, value
):
    records = [
        {
            "cycle_id": str(index),
            "rv": rv,
            "best_fitness": 0.9 - index * 0.1,
            "measurement_kind": "residual_hidden",
            **evolution_metadata("residual_hidden"),
        }
        for index, rv in enumerate((0.4, 0.5, 0.6))
    ]
    if value is _MISSING:
        records[1].pop(field)
    else:
        records[1][field] = value
    before = "".join(f"{json.dumps(record)}\n" for record in records).encode()
    path = tmp_path / "evolution_rv.jsonl"
    path.write_bytes(before)
    tracker = EvolutionRVTracker(tmp_path)
    await tracker.load()

    assert tracker.get_rv_fitness_pairs() == []
    assert tracker.get_trend() is None
    assert path.read_bytes() == before
    readings = tracker.get_readings()
    assert [row["cycle_id"] for row in readings] == ["0", "1", "2"]
    unaffected = "best_fitness" if field == "rv" else "rv"
    assert readings[1][unaffected] == records[1][unaffected]
    if value is _MISSING:
        assert field not in readings[1]
    elif isinstance(value, float) and value != value:
        assert readings[1][field] != readings[1][field]
    else:
        assert readings[1][field] == value


async def test_tracker_comparable_finite_legacy_numbers_return_exact_statistics(tmp_path):
    records = [
        {
            "cycle_id": str(index),
            "rv": rv,
            "best_fitness": 0.9 - index * 0.1,
            "measurement_kind": "residual_hidden",
            **evolution_metadata("residual_hidden"),
        }
        for index, rv in enumerate((0.4, 0.5, 0.6))
    ]
    before = "".join(f"{json.dumps(record)}\n" for record in records).encode()
    path = tmp_path / "evolution_rv.jsonl"
    path.write_bytes(before)
    tracker = EvolutionRVTracker(tmp_path)
    await tracker.load()

    assert tracker.get_rv_fitness_pairs() == [(0.4, 0.9), (0.5, 0.8), (0.6, 0.7)]
    assert tracker.get_trend() == pytest.approx(0.1)
    assert [row["rv"] for row in tracker.get_readings()] == [0.4, 0.5, 0.6]
    assert path.read_bytes() == before


@pytest.mark.parametrize("construction", ["embedding", "direct", "deserialized"])
@pytest.mark.parametrize("composition", ["flatten", "multiply", "bind"])
def test_monad_composition_preserves_reading_classification_history(
    construction, composition
):
    inner_conflicts = [{"field": "inner_prior", "values": [False, True]}]
    outer_conflicts = [{"field": "outer_prior", "values": ["weak", "strong"]}]
    inner_reading = reading(
        0.8,
        "residual_hidden",
        historical_classification={
            "is_contracted": False,
            "contraction_strength": None,
            "inner_only": {"keep": [1]},
        },
        historical_classification_conflicts=inner_conflicts,
    )
    outer_reading = reading(
        0.4,
        "residual_hidden",
        historical_classification={
            "is_contracted": True,
            "contraction_strength": "strong",
            "outer_only": 0,
        },
        historical_classification_conflicts=outer_conflicts,
    )
    original_inner = deepcopy(inner_reading)
    original_outer = deepcopy(outer_reading)

    def make_observed(state, source):
        if construction == "embedding":
            return ObservedState.from_rv_reading(state, source)
        if construction == "direct":
            return ObservedState(
                state=state,
                rv_reading=source,
                timestamp=source.timestamp.timestamp(),
            )
        serialized_state = state
        if isinstance(state, ObservedState):
            serialized_state = {**state.to_dict(), "__observed_state__": True}
        return ObservedState.from_dict({
            "state": serialized_state,
            "rv_reading": json.loads(source.model_dump_json()),
            "introspection": {},
            "timestamp": source.timestamp.timestamp(),
        })

    inner = make_observed("core", inner_reading)

    if composition == "bind":
        result = bind(inner, lambda state: make_observed("next", outer_reading))
        assert result.state == "next"
    else:
        outer = make_observed(inner, outer_reading)
        result = flatten(outer) if composition == "flatten" else SelfObservationMonad.multiply(outer)
        assert result.state == "core"

    assert result.rv_reading == outer_reading
    assert result.rv_measurement == 0.4
    assert result.introspection["historical_classification"] == {
        "is_contracted": True,
        "contraction_strength": "strong",
        "inner_only": {"keep": [1]},
        "outer_only": 0,
    }
    assert result.introspection["historical_classification_conflicts"] == [
        *inner_conflicts,
        *outer_conflicts,
        {
            "field": "is_contracted",
            "existing_source": "inner_introspection.historical_classification",
            "existing_value": False,
            "legacy_source": "outer_introspection.historical_classification",
            "legacy_value": True,
        },
        {
            "field": "contraction_strength",
            "existing_source": "inner_introspection.historical_classification",
            "existing_value": None,
            "legacy_source": "outer_introspection.historical_classification",
            "legacy_value": "strong",
        },
    ]
    assert result.introspection["is_contracted"] is None
    assert result.introspection["contraction_strength"] is None
    assert result.rv_reading.is_contracted is None
    assert result.rv_reading.contraction_strength is None
    assert inner_reading == original_inner
    assert outer_reading == original_outer

    output = json.loads(json.dumps(result.to_dict()))
    restored = ObservedState.from_dict(output)
    assert restored == result
    assert restored.to_dict() == output
    assert ObservedState.from_dict(restored.to_dict()).to_dict() == output


async def test_known_instrument_mean_is_descriptive_with_no_classification(tmp_path):
    bridge = ResearchBridge(tmp_path / "pairs.jsonl")
    for value in (0.4, 0.6, 0.8):
        await bridge.add_measurement(str(value), "known", "A factual response.",
                                     rv_reading=reading(value, "residual_hidden"))
    result = bridge.compute_correlation()
    assert result.mean_rv_by_group["known"] == pytest.approx(0.6)
    assert result.contraction_recognition_overlap is None
    assert result.classification_count == 0
    assert result.measurement_kind_counts == {"residual_hidden": 3}
    assert "overlap unavailable" in result.summary
    assert json.loads(result.model_dump_json())["contraction_recognition_overlap"] is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"model_name": "other-model"},
        {"early_layer": 3},
        {"late_layer": 21},
        {"measurement_details": {"cohort": "other-cohort"}},
        {"measurement_details": {}},
    ],
)
async def test_research_bridge_withholds_incompatible_same_kind_statistics(tmp_path, overrides):
    bridge = ResearchBridge(tmp_path / "pairs.jsonl")
    await bridge.add_measurement("one", "same", "First response.", rv_reading=reading(0.4, "residual_hidden"))
    await bridge.add_measurement(
        "two", "same", "Second different response.",
        rv_reading=reading(0.6, "residual_hidden", **overrides),
    )
    result = bridge.compute_correlation()
    assert result.n == 2
    assert result.mean_rv_by_group == {}
    assert bridge.group_summary()["same"]["mean_rv"] is None
    assert [m.rv_reading.rv for m in bridge.get_measurements()] == pytest.approx([0.4, 0.6])


async def test_research_bridge_withholds_different_proxy_formulas(tmp_path):
    bridge = ResearchBridge(tmp_path / "pairs.jsonl")
    for index, formula in enumerate(("formula-a", "formula-b")):
        await bridge.add_measurement(
            str(index), "same", f"Response {index}",
            rv_reading=reading(
                0.4 + index * 0.2, "behavioral_proxy",
                measurement_details={"cohort": "retraction-fixture", "formula": formula},
            ),
        )
    result = bridge.compute_correlation()
    assert result.mean_rv_by_group == {}
    assert bridge.group_summary()["same"]["mean_rv"] is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
async def test_nonfinite_readings_never_become_statistics_or_classifications(tmp_path, value):
    bridge = ResearchBridge(tmp_path / "pairs.jsonl")
    await bridge.add_measurement("bad", "known", "Response.", rv_reading=reading(value, "residual_hidden"))
    result = bridge.compute_correlation()
    assert result.pearson_r is None
    assert result.contraction_recognition_overlap is None
    assert result.mean_rv_by_group == {}


def test_evolution_bridge_keeps_raw_archive_and_refuses_cross_instrument_pooling():
    bridge = EvolutionBridge()
    for index, kind in enumerate(("residual_hidden", "colony_density", "behavioral_proxy")):
        bridge.add_record(
            str(index), 0.4 + index * 0.1, 0.9 - index * 0.1,
            measurement_kind=kind, metadata=evolution_metadata(kind),
        )
    result = bridge.correlate()
    assert result["pearson_r"] is None
    assert result["rv_trend"] is None
    assert result["n"] == 3
    assert [r["rv"] for r in bridge.format_for_archive()] == pytest.approx([0.4, 0.5, 0.6])


def test_evolution_bridge_known_proxy_association_does_not_imply_self_reference():
    bridge = EvolutionBridge()
    for index in range(3):
        bridge.add_record(
            str(index), 0.4 + index * 0.1, 0.9 - index * 0.1,
            measurement_kind="behavioral_proxy",
            metadata=evolution_metadata("behavioral_proxy"),
        )
    result = bridge.correlate()
    assert result["pearson_r"] == pytest.approx(-1)
    assert result["measurement_kind_counts"] == {"behavioral_proxy": 3}
    assert result["calibration_status"] == "unvalidated_retired_threshold"
    assert "does not establish a mechanism or causation" in result["summary"]


@pytest.mark.parametrize("field", ["rv", "fitness"])
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="null"),
        pytest.param("not-a-number", id="nonnumeric"),
        pytest.param(True, id="true"),
        pytest.param(False, id="false"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="positive-infinity"),
        pytest.param(-float("inf"), id="negative-infinity"),
        pytest.param(0.55, id="valid"),
    ],
)
def test_evolution_bridge_numeric_guard_preserves_raw_archive(field, value):
    bridge = EvolutionBridge()
    for index in range(3):
        rv = 0.4 + index * 0.1
        fitness = 0.9 - index * 0.1
        if index == 1:
            if field == "rv":
                rv = value
            else:
                fitness = value
        bridge.add_record(
            str(index), rv, fitness,
            measurement_kind="behavioral_proxy",
            metadata=evolution_metadata("behavioral_proxy"),
        )
    archived = bridge.format_for_archive()

    result = bridge.correlate()

    statistics = ("pearson_r", "spearman_rho", "rv_trend", "fitness_trend")
    if value == 0.55:
        assert all(result[key] is not None for key in statistics)
        assert result["rv_trend"] == pytest.approx(0.1)
        assert result["fitness_trend"] == pytest.approx(-0.1)
    else:
        assert all(result[key] is None for key in statistics)
    assert result["n"] == 3
    assert bridge.format_for_archive() == archived
    actual = archived[1][field]
    if isinstance(value, float) and value != value:
        assert actual != actual
    else:
        assert actual == value
        assert type(actual) is type(value)
    unaffected = "fitness" if field == "rv" else "rv"
    expected = [0.9, 0.8, 0.7] if unaffected == "fitness" else [0.4, 0.5, 0.6]
    assert [row[unaffected] for row in archived] == pytest.approx(expected)


def _restore_evolution_archive(rows):
    bridge = EvolutionBridge()
    identity_fields = ("model_name", "early_layer", "late_layer", "measurement_details")
    for row in rows:
        metadata = {key: row[key] for key in identity_fields if key in row}
        bridge.add_record(
            row["cycle_id"], row["rv"], row["fitness"], row["rv_source"],
            metadata=metadata, measurement_kind=row["measurement_kind"],
        )
    return bridge


@pytest.mark.parametrize("kind", ["residual_hidden", "behavioral_proxy"])
def test_evolution_bridge_archive_round_trip_preserves_comparable_statistics(kind):
    bridge = EvolutionBridge()
    metadata = evolution_metadata(kind)
    for index in range(3):
        bridge.add_record(
            str(index), 0.4 + index * 0.1, 0.9 - index * 0.1,
            measurement_kind=kind, metadata=metadata,
        )
    before = bridge.correlate()
    archived = json.loads(json.dumps(bridge.format_for_archive()))
    restored = _restore_evolution_archive(archived)

    assert before["pearson_r"] == pytest.approx(-1)
    assert restored.correlate() == before
    assert [row["rv"] for row in archived] == pytest.approx([0.4, 0.5, 0.6])
    assert [row["fitness"] for row in archived] == pytest.approx([0.9, 0.8, 0.7])
    for key in ("model_name", "early_layer", "late_layer", "measurement_details"):
        assert archived[0][key] == metadata[key]

    owned_archive = bridge.format_for_archive()
    owned_archive[0]["measurement_details"]["cohort"] = "changed"
    assert bridge.correlate() == before


@pytest.mark.parametrize(
    ("kind", "override"),
    [
        ("residual_hidden", {"measurement_details": {"cohort": "other-cohort"}}),
        ("residual_hidden", {"model_name": "other-model"}),
        ("residual_hidden", {"early_layer": 3}),
        ("residual_hidden", {"late_layer": 21}),
        ("behavioral_proxy", {"measurement_details": {"cohort": "evolution-fixture", "formula": "other"}}),
    ],
)
def test_evolution_bridge_archive_round_trip_withholds_mixed_identity(kind, override):
    bridge = EvolutionBridge()
    for index in range(3):
        metadata = evolution_metadata(kind)
        if index == 2:
            metadata.update(override)
        bridge.add_record(
            str(index), 0.4 + index * 0.1, 0.9 - index * 0.1,
            measurement_kind=kind, metadata=metadata,
        )
    archived = json.loads(json.dumps(bridge.format_for_archive()))
    restored = _restore_evolution_archive(archived)

    assert restored.correlate()["pearson_r"] is None
    assert restored.correlate()["rv_trend"] is None
    assert [row["rv"] for row in restored.format_for_archive()] == pytest.approx([0.4, 0.5, 0.6])
    assert [row["fitness"] for row in restored.format_for_archive()] == pytest.approx([0.9, 0.8, 0.7])


@pytest.mark.parametrize(
    ("kind", "metadata"),
    [
        ("unknown", None),
        ("residual_hidden", {"model_name": "fixture", "measurement_details": {"cohort": "evolution-fixture"}}),
    ],
)
def test_evolution_bridge_archive_round_trip_does_not_invent_missing_identity(kind, metadata):
    bridge = EvolutionBridge()
    for index in range(3):
        bridge.add_record(
            str(index), 0.4 + index * 0.1, 0.9 - index * 0.1,
            measurement_kind=kind, metadata=metadata,
        )
    archived = json.loads(json.dumps(bridge.format_for_archive()))
    restored = _restore_evolution_archive(archived)

    assert restored.correlate()["pearson_r"] is None
    assert all("early_layer" not in row and "late_layer" not in row for row in archived)
    assert [row["rv"] for row in restored.format_for_archive()] == pytest.approx([0.4, 0.5, 0.6])
    assert [row["fitness"] for row in restored.format_for_archive()] == pytest.approx([0.9, 0.8, 0.7])


def test_evolution_bridge_constant_comparable_series_reports_stable_trends():
    bridge = EvolutionBridge()
    for index in range(3):
        bridge.add_record(
            str(index), 0.4, 0.8,
            measurement_kind="behavioral_proxy",
            metadata=evolution_metadata("behavioral_proxy"),
        )
    result = bridge.correlate()
    assert result["rv_trend"] == 0.0
    assert result["fitness_trend"] == 0.0
    assert "R_V trend: +0.0000/cycle (stable)." in result["summary"]
    assert "Fitness trend: +0.0000/cycle (stable)." in result["summary"]


def test_evolution_bridge_rejects_unknown_kind_token():
    bridge = EvolutionBridge()
    with pytest.raises(ValueError):
        bridge.add_record("bad", 0.2, 0.8, measurement_kind="validated-awareness")
    assert bridge.format_for_archive() == []


def test_evolution_bridge_empty_and_short_known_kind_report_insufficient_cycles():
    bridge = EvolutionBridge()
    empty = bridge.correlate()
    assert empty["n"] == 0
    assert empty["pearson_r"] is None
    assert empty["rv_trend"] is None
    assert empty["measurement_kind_counts"] == {}
    assert "have 0" in empty["summary"]
    for index in range(2):
        bridge.add_record(
            str(index), 0.4 + index * 0.1, 0.9 - index * 0.1,
            measurement_kind="residual_hidden",
            metadata=evolution_metadata("residual_hidden"),
        )
    short = bridge.correlate()
    assert short["n"] == 2
    assert short["pearson_r"] is None
    assert short["rv_trend"] is None
    assert short["measurement_kind_counts"] == {"residual_hidden": 2}
    assert "have 2" in short["summary"]


def test_evolution_bridge_short_unknown_kind_is_withheld_not_pooled():
    bridge = EvolutionBridge()
    bridge.add_record("legacy", 0.4, 0.9)
    result = bridge.correlate()
    assert result["n"] == 1
    assert result["pearson_r"] is None
    assert result["measurement_kind_counts"] == {"unknown": 1}
    assert "have 1" not in result["summary"]
    assert "unknown" in result["summary"]


def test_gaia_demo_prints_raw_ratio_and_unavailable_classification(monkeypatch, capsys):
    import socket

    from scripts import gaia_demo

    def refuse(*_args, **_kwargs):
        raise AssertionError("gaia_demo must run offline")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    gaia_demo.main()
    lines = [line.strip() for line in capsys.readouterr().out.splitlines()]

    def value(prefix):
        return next(line for line in lines if line.startswith(prefix))[len(prefix):].strip()

    ratio = float(value("R_V-like reading:"))
    assert 0.0 <= ratio <= 1.0
    assert float(value("PR_early (before observation):")) == 1.0
    assert float(value("PR_late (after observation):")) == pytest.approx(ratio, abs=1e-3)
    assert value("Measurement kind:") == "behavioral_proxy"
    contraction = value("Contraction:")
    assert contraction.startswith("unavailable")
    assert RV_CALIBRATION_STATUS in contraction
    assert value("Strength:").startswith("unavailable")
    assert not any(line.endswith((" YES", " NO")) for line in lines)
    assert "contraction detected" not in "\n".join(lines)


def test_gaia_observe_ledger_carries_behavioral_proxy_provenance():
    from dharma_swarm.gaia_fitness import gaia_observer_function, observe_ledger
    from dharma_swarm.gaia_ledger import GaiaLedger

    ledger = GaiaLedger()
    reading = gaia_observer_function(ledger)
    assert reading.measurement_kind == "behavioral_proxy"
    assert reading.pr_early == 1.0
    assert reading.pr_late == reading.rv
    assert reading.is_contracted is None
    assert reading.contraction_strength is None
    formula = reading.measurement_details["formula"]
    assert all(term in formula for term in
               ("verification_coverage", "oracle_diversity", "violation_rate"))

    observed = observe_ledger(ledger)
    assert observed.rv == pytest.approx(reading.rv)
    assert observed.is_contracted is None
    assert observed.introspection["measurement_kind"] == "behavioral_proxy"
    assert observed.introspection["contraction_strength"] is None
    assert observed.to_dict()["introspection"]["measurement_kind"] == "behavioral_proxy"


def test_historical_analysis_emits_numbers_without_retired_inference(monkeypatch, capsys):
    from analysis import categorical_analysis

    groups = {"L3_deeper": 0.6, "L4_full": 0.5, "champions": 0.7,
              "baseline_factual": 0.8, "baseline_math": 0.9, "baseline_creative": 1.0}
    stats = {"group_rv_means": groups, "group_word_means": {},
             "h2_cohens_d": 0.1, "h2_p_value": 0.8,
             "h1_spearman_r": 0.0, "h1_spearman_p": 1.0, "h1_significant": False,
             "h3_point_biserial_r": 0.0, "h3_point_biserial_p": 1.0, "h3_significant": False}
    monkeypatch.setattr(categorical_analysis, "load_gemma_bridge", lambda: {
        "analysis": {"temp_0.0": stats}, "early_layer": 2, "late_layer": 22, "n_total_prompts": 6,
    })
    categorical_analysis.analyze_gemma_bridge()
    output = capsys.readouterr().out
    assert "0.5000" in output
    assert output.count("unavailable (.737 retired; instrument uncalibrated)") == 6
    assert "No calibrated classifier or fixed-point convergence inference is available" in output
    assert "Estimated iterations to L5" not in output


def test_research_annotation_exposes_retraction_as_contradiction():
    from dharma_swarm.semantic_gravity import ConceptNode, ResearchConnectionType
    from dharma_swarm.semantic_researcher import SemanticResearcher

    node = ConceptNode(id="rv", name="rv", source_file="fixture", category="mathematical",
                       salience=0.9, formal_structures=["rv_contraction"])
    annotations = SemanticResearcher().annotate_concept(node)
    assert len(annotations) == 1
    assert annotations[0].connection_type == ResearchConnectionType.CONTRADICTION
    assert "same-sample calibration lacked held-out validation" in annotations[0].summary


def test_field_graph_marks_rv_record_historical_and_unvalidated():
    from dharma_swarm.field_graph import build_field_graph

    nodes = build_field_graph().find_by_name("dgc-rv-contraction")
    assert len(nodes) == 1
    definition = nodes[0].definition
    assert "Historical, unvalidated" in definition
    assert "AUROC 0.909" in definition
    assert "6 architectures" in definition
    assert ".737 classifier is retired" in definition
    assert "architectures validated" not in definition
    assert "AUROC 0.909 discriminating" not in definition


def test_research_director_prompt_does_not_promote_retired_classification():
    from dharma_swarm.agent_constitution import get_agent_spec

    spec = get_agent_spec("research_director")
    assert spec is not None
    prompt = spec.system_prompt
    assert "Historical reports" in prompt
    assert ".737 classifier is retired" in prompt
    assert "held-out classification is unavailable" in prompt
    assert "calibrated intuitions" not in prompt
    assert "causal validation at L27" not in prompt


def test_shakti_rv_contexts_preserve_history_without_current_validation():
    from scripts.shakti_discovery import build_research_tasks

    tasks = [task for task in build_research_tasks() if task.question.startswith("The R_V paper")]
    assert len(tasks) == 2
    contexts = [task.context_builder() for task in tasks]
    for context in contexts:
        assert "Historical, unvalidated" in context
        assert "AUROC=0.909" in context
        assert ".737 classifier is retired" in context
        assert "Current results:" not in context
        assert "Causal validation:" not in context
        assert "causal validation at L27" not in context
    assert "Bridge hypothesis (untested)" in contexts[0]
    assert "held-out classification is unavailable" in contexts[1]


async def test_telos_seed_marks_rv_abstract_evidence_historical(tmp_path):
    from dharma_swarm.telos_graph import TelosGraph
    from dharma_swarm.telos_substrate import TelosSubstrate

    await TelosSubstrate(state_dir=tmp_path)._seed_telos_graph()
    graph = TelosGraph(telos_dir=tmp_path / "telos")
    await graph.load()
    objective = await graph.get_by_name("RV COLM 2026 Abstract Submission")
    assert objective is not None
    description = objective.description
    assert "Historical, unvalidated" in description
    assert "Hedges g=-1.47, AUROC=0.909" in description
    assert ".737 classifier is retired" in description
    assert "causal at L27" not in description


@pytest.mark.parametrize("with_reading", [False, True], ids=["proxy", "rv-reading"])
def test_observe_retires_merged_caller_classification_and_preserves_history(with_reading):
    supplied = {
        "is_contracted": True,
        "contraction_strength": "strong",
        "raw_metadata": {"keep": [1, 2]},
    }
    original = deepcopy(supplied)
    observer = (lambda _: reading(0.4, "residual_hidden")) if with_reading else None

    observed = SelfObservationMonad(observer).observe("state", introspection=supplied)
    output = json.loads(json.dumps(observed.to_dict()))
    restored = ObservedState.from_dict(output)

    assert supplied == original
    assert observed.is_contracted is None
    assert observed.introspection["is_contracted"] is None
    assert observed.introspection["contraction_strength"] is None
    assert observed.introspection["historical_classification"] == {
        "is_contracted": True,
        "contraction_strength": "strong",
    }
    assert observed.introspection["raw_metadata"] == original["raw_metadata"]
    assert observed.rv_measurement == (0.4 if with_reading else None)
    assert restored.to_dict() == output


@pytest.mark.parametrize("operation", ["flatten", "bind"])
def test_monad_composition_merges_classification_history_without_input_mutation(operation):
    inner_metadata = {
        "shared": "inner",
        "inner_only": "retained",
        "historical_classification": {
            "is_contracted": False,
            "inner_legacy": {"keep": [1]},
        },
        "historical_classification_conflicts": [{"field": "inner", "raw": "keep"}],
    }
    outer_metadata = {
        "shared": "outer",
        "outer_only": "retained",
        "historical_classification": {
            "is_contracted": True,
            "outer_legacy": 0,
        },
        "historical_classification_conflicts": [{"field": "outer", "raw": False}],
    }
    inner_original = deepcopy(inner_metadata)
    outer_original = deepcopy(outer_metadata)
    inner = ObservedState(
        state="core",
        rv_measurement=0.5,
        observation_depth=1,
        introspection=inner_metadata,
        timestamp=1.0,
    )

    if operation == "flatten":
        nested = ObservedState(
            state=inner,
            rv_measurement=0.4,
            observation_depth=2,
            introspection=outer_metadata,
            timestamp=2.0,
        )
        result = flatten(nested)
        assert result.state == "core"
        assert result.timestamp == 2.0
    else:
        result = bind(inner, lambda _: ObservedState(
            state="bound",
            rv_measurement=0.4,
            observation_depth=2,
            introspection=outer_metadata,
            timestamp=3.0,
        ))
        assert result.state == "bound"
        assert result.timestamp == 3.0

    assert inner_metadata == inner_original
    assert outer_metadata == outer_original
    assert result.rv_measurement == 0.4
    assert result.observation_depth == 3
    assert result.is_contracted is None
    assert result.introspection["is_contracted"] is None
    assert result.introspection["contraction_strength"] is None
    assert result.introspection["shared"] == "outer"
    assert result.introspection["inner_only"] == "retained"
    assert result.introspection["outer_only"] == "retained"
    assert result.introspection["historical_classification"] == {
        "is_contracted": True,
        "inner_legacy": {"keep": [1]},
        "outer_legacy": 0,
    }
    assert result.introspection["historical_classification_conflicts"] == [
        {"field": "inner", "raw": "keep"},
        {"field": "outer", "raw": False},
        {
            "field": "is_contracted",
            "existing_source": "inner_introspection.historical_classification",
            "existing_value": False,
            "legacy_source": "outer_introspection.historical_classification",
            "legacy_value": True,
        },
    ]
    output = json.loads(json.dumps(result.to_dict()))
    assert ObservedState.from_dict(output).to_dict() == output


def test_evolution_bridge_snapshots_provenance_before_caller_mutation():
    bridge = EvolutionBridge()
    shared = evolution_metadata("behavioral_proxy")
    shared["measurement_details"]["cohort"] = "cohort-a"
    bridge.add_record(
        "0", 0.4, 0.9, measurement_kind="behavioral_proxy", metadata=shared
    )

    shared["measurement_details"]["cohort"] = "cohort-b"
    for index in (1, 2):
        bridge.add_record(
            str(index), 0.4 + index * 0.1, 0.9 - index * 0.1,
            measurement_kind="behavioral_proxy", metadata=shared,
        )

    archived = json.loads(json.dumps(bridge.format_for_archive()))
    assert archived[0]["measurement_details"]["cohort"] == "cohort-a"
    assert [row["measurement_details"]["cohort"] for row in archived[1:]] == [
        "cohort-b", "cohort-b"
    ]
    assert bridge.correlate()["pearson_r"] is None
    restored = _restore_evolution_archive(archived)
    assert restored.format_for_archive() == archived
    assert restored.correlate()["pearson_r"] is None

    compatible = EvolutionBridge()
    unchanged = evolution_metadata("behavioral_proxy")
    for index in range(3):
        compatible.add_record(
            str(index), 0.4 + index * 0.1, 0.9 - index * 0.1,
            measurement_kind="behavioral_proxy", metadata=unchanged,
        )
    assert compatible.correlate()["pearson_r"] == pytest.approx(-1)


@pytest.mark.parametrize("sequence_factory", [tuple, deque], ids=["tuple", "deque"])
def test_rv_reading_preserves_accepted_conflict_sequences_across_json_boundaries(
    sequence_factory,
):
    from dharma_swarm.l4_rv_correlator import (
        BatchResult,
        L4CompressionResult,
        L4RVPairedResult,
    )

    existing = {"field": "other", "raw": "keep"}
    payload = reading(0.4, "residual_hidden").model_dump(mode="json")
    payload["historical_classification_conflicts"] = sequence_factory([existing])
    original = deepcopy(payload)

    direct = RVReading.model_validate(payload)
    observed = ObservedState.from_dict({
        "state": "saved", "rv_reading": payload, "timestamp": 1.0,
    })
    paired = L4RVPairedResult.model_validate({
        "prompt_text": "prompt",
        "prompt_group": "L4",
        "generated_text": "response",
        "rv_reading": payload,
        "l4_result": L4CompressionResult().model_dump(),
    })
    batch = BatchResult(paired_results=[paired])

    assert payload == original
    for current in (
        direct,
        observed.rv_reading,
        paired.rv_reading,
        batch.paired_results[0].rv_reading,
    ):
        assert current is not None
        assert current.rv == 0.4
        assert current.pr_early == 10
        assert current.pr_late == 4
        assert current.measurement_kind == "residual_hidden"
        assert current.is_contracted is None
        assert current.contraction_strength is None
        assert current.historical_classification_conflicts == [existing]

    direct_json = direct.model_dump_json()
    observed_output = json.loads(json.dumps(observed.to_dict()))
    paired_json = paired.model_dump_json()
    batch_json = batch.model_dump_json()
    assert RVReading.model_validate_json(direct_json).model_dump_json() == direct_json
    assert ObservedState.from_dict(observed_output).to_dict() == observed_output
    assert L4RVPairedResult.model_validate_json(paired_json).model_dump_json() == paired_json
    assert BatchResult.model_validate_json(batch_json).model_dump_json() == batch_json
