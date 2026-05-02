"""Interface contract tests — structural enforcement for dharma_swarm.

Each test verifies that a known cross-module call site has a matching
method signature on the callee side.  When a refactor changes a method
signature, the contract test fails BEFORE the change ships.

These tests replace INTERFACE_MISMATCH_MAP.md with code that cannot drift.
Run: pytest tests/test_contracts.py -q  (< 2 seconds)
"""

from __future__ import annotations

import importlib
import inspect

import pytest


# ── Helpers ──────────────────────────────────────────────────────────

def _has_method(module_path: str, class_name: str, method_name: str) -> bool:
    """Check that class_name.method_name exists in module_path."""
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name, None)
    if cls is None:
        return False
    return callable(getattr(cls, method_name, None))


def _get_params(module_path: str, class_name: str, method_name: str) -> set[str]:
    """Return parameter names (excluding 'self') for a method."""
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    method = getattr(cls, method_name)
    sig = inspect.signature(method)
    return {p for p in sig.parameters if p != "self"}


def _get_init_params(module_path: str, class_name: str) -> set[str]:
    """Return __init__ parameter names (excluding 'self')."""
    return _get_params(module_path, class_name, "__init__")


def _param_has_default(module_path: str, class_name: str, method_name: str, param: str) -> bool:
    """Check if a specific parameter has a default value."""
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    method = getattr(cls, method_name)
    sig = inspect.signature(method)
    p = sig.parameters.get(param)
    return p is not None and p.default is not inspect.Parameter.empty


# ── MISMATCH-02/03: PersistentAgent constructor requires enums ──────

class TestPersistentAgentContract:
    """orchestrate_live.py passes role/provider_type to PersistentAgent.
    PersistentAgent.__init__ requires AgentRole and ProviderType enums.
    """

    def test_init_has_role_param(self):
        assert "role" in _get_init_params("dharma_swarm.persistent_agent", "PersistentAgent")

    def test_init_has_provider_type_param(self):
        assert "provider_type" in _get_init_params("dharma_swarm.persistent_agent", "PersistentAgent")

    def test_init_has_name_param(self):
        assert "name" in _get_init_params("dharma_swarm.persistent_agent", "PersistentAgent")

    def test_role_typed_as_enum(self):
        mod = importlib.import_module("dharma_swarm.persistent_agent")
        sig = inspect.signature(mod.PersistentAgent.__init__)
        role_param = sig.parameters["role"]
        ann = role_param.annotation
        assert ann is not inspect.Parameter.empty
        assert "AgentRole" in str(ann) or hasattr(ann, "__members__")


# ── MISMATCH-05: message_bus.receive → consume_events ───────────────

class TestMessageBusContract:
    """orchestrate_live uses consume_events; old receive/mark_read is deprecated."""

    def test_consume_events_exists(self):
        assert _has_method("dharma_swarm.message_bus", "MessageBus", "consume_events")

    def test_consume_events_has_event_type_param(self):
        params = _get_params("dharma_swarm.message_bus", "MessageBus", "consume_events")
        assert "event_type" in params

    def test_consume_events_has_limit_param(self):
        params = _get_params("dharma_swarm.message_bus", "MessageBus", "consume_events")
        assert "limit" in params


# ── MISMATCH-07: AutoProposer accepts optional stigmergy ────────────

class TestAutoProposerContract:
    """swarm.py passes stigmergy=self._stigmergy (can be None)."""

    def test_init_has_stigmergy_param(self):
        assert "stigmergy" in _get_init_params("dharma_swarm.auto_proposer", "AutoProposer")

    def test_stigmergy_has_default(self):
        assert _param_has_default(
            "dharma_swarm.auto_proposer", "AutoProposer", "__init__", "stigmergy"
        )

    def test_cycle_returns(self):
        """AutoProposer.cycle() must exist (called by swarm.py:2316)."""
        assert _has_method("dharma_swarm.auto_proposer", "AutoProposer", "cycle")


# ── MISMATCH-09: orchestrator private methods called from swarm ─────

class TestOrchestratorContract:
    """swarm.py calls _classify_failure and _resolve_retry_policy.
    These are private methods called across class boundaries — a contract
    violation. Until refactored, we at least verify they exist.
    """

    def test_classify_failure_exists(self):
        assert _has_method("dharma_swarm.orchestrator", "Orchestrator", "_classify_failure")

    def test_classify_failure_params(self):
        params = _get_params("dharma_swarm.orchestrator", "Orchestrator", "_classify_failure")
        assert "error" in params
        assert "source" in params

    def test_resolve_retry_policy_exists(self):
        assert _has_method("dharma_swarm.orchestrator", "Orchestrator", "_resolve_retry_policy")

    def test_resolve_retry_policy_takes_task(self):
        params = _get_params("dharma_swarm.orchestrator", "Orchestrator", "_resolve_retry_policy")
        assert "task" in params


# ── MISMATCH-11/12: StigmergyStore shared instance ──────────────────

class TestStigmergyContract:
    """Multiple subsystems must accept a shared StigmergyStore, not create their own."""

    def test_subconscious_accepts_stigmergy(self):
        assert "stigmergy" in _get_init_params("dharma_swarm.subconscious", "SubconsciousStream")

    def test_shakti_accepts_stigmergy(self):
        params = _get_init_params("dharma_swarm.shakti", "ShaktiLoop")
        assert "stigmergy" in params or "store" in params

    def test_stigmergy_store_singleton_path(self):
        """StigmergyStore uses a well-known path."""
        mod = importlib.import_module("dharma_swarm.stigmergy")
        assert hasattr(mod, "StigmergyStore")


# ── MISMATCH-13: WitnessAuditor provider interface ──────────────────

class TestWitnessAuditorContract:
    """swarm.py passes ModelRouter as provider. WitnessAuditor needs .complete()."""

    def test_init_has_provider_param(self):
        params = _get_init_params("dharma_swarm.witness", "WitnessAuditor")
        assert "provider" in params

    def test_witness_has_stop(self):
        assert _has_method("dharma_swarm.witness", "WitnessAuditor", "stop")

    def test_witness_has_get_stats(self):
        assert _has_method("dharma_swarm.witness", "WitnessAuditor", "get_stats")


# ── MISMATCH-18: ThinkodynamicDirector init contract ────────────────

class TestThinkodynamicContract:
    """swarm.py calls ThinkodynamicDirector(state_dir=..., swarm=...)."""

    def test_init_has_state_dir(self):
        assert "state_dir" in _get_init_params(
            "dharma_swarm.thinkodynamic_director", "ThinkodynamicDirector"
        )

    def test_init_has_swarm(self):
        assert "swarm" in _get_init_params(
            "dharma_swarm.thinkodynamic_director", "ThinkodynamicDirector"
        )


# ── MISMATCH-23: AgentPool import guard ─────────────────────────────

class TestAgentPoolContract:
    """AgentPool must be importable from agent_runner."""

    def test_agent_pool_importable(self):
        mod = importlib.import_module("dharma_swarm.agent_runner")
        assert hasattr(mod, "AgentPool")

    def test_agent_pool_has_spawn(self):
        assert _has_method("dharma_swarm.agent_runner", "AgentPool", "spawn")


# ── DarwinEngine: swarm.py constructor contract ─────────────────────

class TestDarwinEngineContract:
    """swarm.py passes archive_path, traces_path, predictor_path."""

    def test_init_has_archive_path(self):
        assert "archive_path" in _get_init_params("dharma_swarm.evolution", "DarwinEngine")

    def test_init_has_traces_path(self):
        assert "traces_path" in _get_init_params("dharma_swarm.evolution", "DarwinEngine")

    def test_get_fitness_trend_exists(self):
        assert _has_method("dharma_swarm.evolution", "DarwinEngine", "get_fitness_trend")


# ── Signal bus: canonical event type constant ────────────────────────

class TestSignalBusContract:
    """Event types must use canonical constants, not bare strings."""

    def test_ecc_instinct_signal_constant_exists(self):
        mod = importlib.import_module("dharma_swarm.signal_bus")
        assert hasattr(mod, "SIGNAL_ECC_INSTINCT"), (
            "SIGNAL_ECC_INSTINCT constant missing — bare string event types cause silent data loss"
        )
