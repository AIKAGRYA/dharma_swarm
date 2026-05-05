"""Tests for dharma_swarm.algedonic_activation — pain/pleasure bypass signals.

Validates:
- AlgedonicAction model construction
- All five pain signal checkers with threshold boundaries
- evaluate() aggregation of multiple signals
- apply() logging and organism memory recording
- recent_activations property
- Non-fatal error handling in checkers
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from dharma_swarm.algedonic_activation import (
    AlgedonicAction,
    AlgedonicActivation,
)


def _make_pulse(**kwargs) -> SimpleNamespace:
    """Build a pulse-like object with configurable attributes."""
    defaults = {
        "audit_failure_rate": 0.0,
        "fleet_health": 1.0,
        "identity_coherence": 1.0,
        "anomalous_gate_patterns": 0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# AlgedonicAction model
# ---------------------------------------------------------------------------


class TestAlgedonicAction:
    def test_construction(self):
        action = AlgedonicAction(
            signal_type="failure_rate",
            severity="high",
            description="Rate at 60%",
            action="recalibrate_routing",
        )
        assert action.signal_type == "failure_rate"
        assert action.severity == "high"
        assert action.metadata == {}

    def test_metadata_default_factory(self):
        a1 = AlgedonicAction(signal_type="x", severity="low", description="d", action="a")
        a2 = AlgedonicAction(signal_type="y", severity="low", description="d", action="a")
        a1.metadata["key"] = "value"
        assert "key" not in a2.metadata


# ---------------------------------------------------------------------------
# Individual pain signal checkers
# ---------------------------------------------------------------------------


class TestFailureRateChecker:
    def test_below_threshold_no_action(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(audit_failure_rate=0.3)
        assert activation._check_failure_rate(pulse) is None

    def test_at_threshold_no_action(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(audit_failure_rate=0.5)
        assert activation._check_failure_rate(pulse) is None

    def test_above_threshold_triggers(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(audit_failure_rate=0.7)
        action = activation._check_failure_rate(pulse)
        assert action is not None
        assert action.signal_type == "failure_rate"
        assert action.severity == "high"
        assert action.action == "recalibrate_routing"

    def test_missing_attribute_safe(self):
        activation = AlgedonicActivation(organism=None)
        pulse = SimpleNamespace()
        assert activation._check_failure_rate(pulse) is None


class TestOmegaDivergenceChecker:
    def test_small_divergence_no_action(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(fleet_health=0.8, identity_coherence=0.7)
        assert activation._check_omega_divergence(pulse) is None

    def test_at_threshold_no_action(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(fleet_health=0.8, identity_coherence=0.4)
        assert activation._check_omega_divergence(pulse) is None

    def test_above_threshold_triggers(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(fleet_health=0.9, identity_coherence=0.3)
        action = activation._check_omega_divergence(pulse)
        assert action is not None
        assert action.signal_type == "omega_divergence"
        assert action.action == "rebalance_priorities"
        assert "lagging" in action.metadata

    def test_identifies_lagging_subscore(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(fleet_health=0.3, identity_coherence=0.9)
        action = activation._check_omega_divergence(pulse)
        assert action is not None
        assert action.metadata["lagging"] == "fleet_health"


class TestOntologicalDriftChecker:
    def test_few_patterns_no_action(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(anomalous_gate_patterns=3)
        assert activation._check_ontological_drift(pulse) is None

    def test_at_threshold_no_action(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(anomalous_gate_patterns=5)
        assert activation._check_ontological_drift(pulse) is None

    def test_above_threshold_triggers(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(anomalous_gate_patterns=10)
        action = activation._check_ontological_drift(pulse)
        assert action is not None
        assert action.signal_type == "ontological_drift"
        assert action.action == "enforce_glossary"


class TestSelfModelGapChecker:
    def test_no_organism_no_action(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse()
        assert activation._check_self_model_gap(pulse) is None

    def test_organism_without_memory_no_action(self):
        organism = SimpleNamespace(memory=None)
        activation = AlgedonicActivation(organism=organism)
        pulse = _make_pulse()
        assert activation._check_self_model_gap(pulse) is None

    def test_high_accuracy_no_action(self):
        memory = MagicMock()
        memory.self_model_accuracy.return_value = 0.8
        organism = SimpleNamespace(memory=memory)
        activation = AlgedonicActivation(organism=organism)
        pulse = _make_pulse()
        assert activation._check_self_model_gap(pulse) is None

    def test_low_accuracy_triggers(self):
        memory = MagicMock()
        memory.self_model_accuracy.return_value = 0.3
        organism = SimpleNamespace(memory=memory)
        activation = AlgedonicActivation(organism=organism)
        pulse = _make_pulse()
        action = activation._check_self_model_gap(pulse)
        assert action is not None
        assert action.signal_type == "self_model_gap"
        assert action.action == "recalibrate_from_metrics"

    def test_memory_exception_non_fatal(self):
        memory = MagicMock()
        memory.self_model_accuracy.side_effect = RuntimeError("boom")
        organism = SimpleNamespace(memory=memory)
        activation = AlgedonicActivation(organism=organism)
        pulse = _make_pulse()
        assert activation._check_self_model_gap(pulse) is None


class TestTelosDriftChecker:
    def test_healthy_coherence_no_action(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(identity_coherence=0.8, fleet_health=0.9)
        assert activation._check_telos_drift(pulse) is None

    def test_low_coherence_low_fleet_no_action(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(identity_coherence=0.3, fleet_health=0.3)
        assert activation._check_telos_drift(pulse) is None

    def test_low_coherence_healthy_fleet_triggers(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(identity_coherence=0.2, fleet_health=0.8)
        action = activation._check_telos_drift(pulse)
        assert action is not None
        assert action.signal_type == "telos_drift"
        assert action.severity == "critical"
        assert action.action == "gnani_checkpoint"


# ---------------------------------------------------------------------------
# evaluate() integration
# ---------------------------------------------------------------------------


class TestEvaluate:
    def test_healthy_pulse_no_actions(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse()
        actions = activation.evaluate(pulse)
        assert actions == []

    def test_multiple_signals_aggregated(self):
        activation = AlgedonicActivation(organism=None)
        pulse = _make_pulse(
            audit_failure_rate=0.8,
            fleet_health=0.9,
            identity_coherence=0.2,
            anomalous_gate_patterns=10,
        )
        actions = activation.evaluate(pulse)
        signal_types = {a.signal_type for a in actions}
        assert "failure_rate" in signal_types
        assert "ontological_drift" in signal_types

    def test_checker_exception_non_fatal(self):
        activation = AlgedonicActivation(organism=None)
        pulse = "not a namespace"
        actions = activation.evaluate(pulse)
        assert isinstance(actions, list)


# ---------------------------------------------------------------------------
# apply() and logging
# ---------------------------------------------------------------------------


class TestApply:
    def test_apply_logs_activation(self):
        activation = AlgedonicActivation(organism=None)
        action = AlgedonicAction(
            signal_type="failure_rate",
            severity="high",
            description="Rate at 80%",
            action="recalibrate_routing",
        )
        activation.apply(action)
        assert len(activation.recent_activations) == 1
        log = activation.recent_activations[0]
        assert log["signal"] == "failure_rate"
        assert log["severity"] == "high"
        assert "timestamp" in log

    def test_apply_records_to_organism_memory(self):
        memory = MagicMock()
        organism = SimpleNamespace(memory=memory)
        activation = AlgedonicActivation(organism=organism)
        action = AlgedonicAction(
            signal_type="telos_drift",
            severity="critical",
            description="Drift detected",
            action="gnani_checkpoint",
        )
        activation.apply(action)
        memory.record_event.assert_called_once()
        call_kwargs = memory.record_event.call_args
        assert call_kwargs[1]["entity_type"] == "algedonic_event" or \
               call_kwargs.kwargs.get("entity_type") == "algedonic_event"

    def test_recent_activations_capped_at_20(self):
        activation = AlgedonicActivation(organism=None)
        for i in range(25):
            action = AlgedonicAction(
                signal_type="test",
                severity="low",
                description=f"Entry {i}",
                action="noop",
            )
            activation.apply(action)
        assert len(activation.recent_activations) == 20

    def test_apply_with_no_memory_no_crash(self):
        organism = SimpleNamespace(memory=None)
        activation = AlgedonicActivation(organism=organism)
        action = AlgedonicAction(
            signal_type="test",
            severity="low",
            description="Test",
            action="noop",
        )
        activation.apply(action)
        assert len(activation.recent_activations) == 1
