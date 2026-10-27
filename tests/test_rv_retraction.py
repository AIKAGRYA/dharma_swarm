"""Public behavior for retired scientific classification and measurement custody."""

import json
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from dharma_swarm.bridge import CorrelationResult, EvolutionBridge, ResearchBridge
from dharma_swarm.monad import ObservedState
from dharma_swarm.ouroboros import colony_rv_reading
from dharma_swarm.rv import EvolutionRVTracker, RVReading


def reading(value=0.6, kind="unknown"):
    return RVReading(
        rv=value, pr_early=10, pr_late=10 * value, model_name="fixture",
        early_layer=2, late_layer=22, prompt_hash="fixture", measurement_kind=kind,
    )


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
    assert RVReading.model_validate_json(restored.model_dump_json()) == restored


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
    assert json.loads(result.model_dump_json())["contraction_recognition_overlap"] is None


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
        bridge.add_record(str(index), 0.4 + index * 0.1, 0.9 - index * 0.1, measurement_kind=kind)
    result = bridge.correlate()
    assert result["pearson_r"] is None
    assert result["rv_trend"] is None
    assert result["n"] == 3
    assert [r["rv"] for r in bridge.format_for_archive()] == pytest.approx([0.4, 0.5, 0.6])


def test_evolution_bridge_known_proxy_association_does_not_imply_self_reference():
    bridge = EvolutionBridge()
    for index in range(3):
        bridge.add_record(str(index), 0.4 + index * 0.1, 0.9 - index * 0.1,
                          measurement_kind="behavioral_proxy")
    result = bridge.correlate()
    assert result["pearson_r"] == pytest.approx(-1)
    assert result["measurement_kind_counts"] == {"behavioral_proxy": 3}
    assert result["calibration_status"] == "unvalidated_retired_threshold"
    assert "does not establish a mechanism or causation" in result["summary"]


def test_evolution_bridge_rejects_unknown_kind_token():
    bridge = EvolutionBridge()
    with pytest.raises(ValueError):
        bridge.add_record("bad", 0.2, 0.8, measurement_kind="validated-awareness")
    assert bridge.format_for_archive() == []


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
