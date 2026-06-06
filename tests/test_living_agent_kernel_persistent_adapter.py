from __future__ import annotations

import sys

import pytest

from dharma_swarm.models import AgentRole, ProviderType
from dharma_swarm.operator_core.governed_work_admission import WorkKind
from dharma_swarm.operator_core.living_agent_kernel import (
    KernelRunStore,
    LivingAgentKernel,
)
from dharma_swarm.operator_core.living_agent_kernel_persistent_adapter import (
    build_persistent_wake_payload,
)
from dharma_swarm.persistent_agent import PersistentAgent


def _agent(tmp_path, *, name: str = "conductor_unit") -> PersistentAgent:
    return PersistentAgent(
        name=name,
        role=AgentRole.CONDUCTOR,
        provider_type=ProviderType.ANTHROPIC,
        model="claude-opus-4",
        state_dir=tmp_path / "agent",
        wake_interval_seconds=1800.0,
    )


# -- unit -------------------------------------------------------------------


def test_payload_maps_real_persistent_agent_identity_surface(tmp_path):
    agent = _agent(tmp_path)
    payload = build_persistent_wake_payload(
        agent,
        task="reconcile control surface rows",
        correlation_id="corr-xyz",
    )

    assert payload["name"] == agent.name
    assert payload["task"] == "reconcile control surface rows"
    assert payload["wake_interval_seconds"] == agent.wake_interval
    assert payload["witness_log"] == str(agent._witness_log)
    assert payload["correlation_id"] == "corr-xyz"


def test_default_correlation_id_is_deterministic(tmp_path):
    agent = _agent(tmp_path)
    first = build_persistent_wake_payload(agent, task="same task")["correlation_id"]
    second = build_persistent_wake_payload(agent, task="same task")["correlation_id"]
    other = build_persistent_wake_payload(agent, task="other task")["correlation_id"]

    assert first == second
    assert first != other
    assert first.startswith("persistent-self-wake-conductor_unit-")


def test_payload_round_trips_through_normalize_wake_source(tmp_path):
    agent = _agent(tmp_path)
    payload = build_persistent_wake_payload(agent, task="inspect runtime state")

    envelope = LivingAgentKernel().normalize_wake_source(
        "persistent_self_wake", payload
    )

    assert envelope.agent_uid == agent.name
    assert envelope.trigger.source == "persistent_self_wake"
    assert envelope.task.text == "inspect runtime state"
    assert envelope.task.source == "persistent_self_wake"
    assert envelope.memory.read_namespaces == ["agent:conductor_unit:working"]


def test_default_authority_is_read_only_manual(tmp_path):
    agent = _agent(tmp_path)
    payload = build_persistent_wake_payload(agent, task="just look")

    envelope = LivingAgentKernel().normalize_wake_source(
        "persistent_self_wake", payload
    )

    assert envelope.authority.work_kind == WorkKind.READ_ONLY
    assert envelope.authority.autonomy_level == "manual"
    assert envelope.authority.allowed_files == []


def test_code_write_promotes_work_kind_and_allowed_files(tmp_path):
    agent = _agent(tmp_path)
    payload = build_persistent_wake_payload(
        agent,
        task="edit two files",
        work_kind="code_write",
        allowed_files=["a.py", "b.py"],
    )

    envelope = LivingAgentKernel().normalize_wake_source(
        "persistent_self_wake", payload
    )

    assert envelope.authority.work_kind == WorkKind.CODE_WRITE
    assert envelope.authority.allowed_files == ["a.py", "b.py"]


# -- integration ------------------------------------------------------------


def test_smoke_seam_payload_to_kernel_run(tmp_path):
    agent = _agent(tmp_path)
    payload = build_persistent_wake_payload(agent, task="inspect runtime state")

    kernel = LivingAgentKernel(
        store=KernelRunStore(tmp_path / "kernel"),
        workspace_root=tmp_path,
        persist=True,
    )
    envelope = kernel.normalize_wake_source("persistent_self_wake", payload)
    result = kernel.run(envelope)

    assert type(result).__name__ == "KernelRunResult"
    assert result.did_persist is True
    assert result.proof_ledger_entry.entry_hash.startswith("sha256:")
    assert result.runtime_truth_packet
    assert result.runtime_truth_packet.get("correlation_id") == payload["correlation_id"]


# -- adversarial ------------------------------------------------------------


def test_missing_witness_log_raises_clear_attribute_error(tmp_path):
    class MissingWitness:
        name = "broken"
        wake_interval = 60.0

    with pytest.raises(AttributeError, match="_witness_log"):
        build_persistent_wake_payload(MissingWitness(), task="t")


def test_missing_wake_interval_raises_clear_attribute_error(tmp_path):
    class MissingInterval:
        name = "broken"
        _witness_log = "/tmp/w.jsonl"

    with pytest.raises(AttributeError, match="wake_interval"):
        build_persistent_wake_payload(MissingInterval(), task="t")


def test_importing_adapter_does_not_construct_provider_client():
    sys.modules.pop("anthropic", None)
    sys.modules.pop("openai", None)
    sys.modules.pop(
        "dharma_swarm.operator_core.living_agent_kernel_persistent_adapter", None
    )

    import importlib

    importlib.import_module(
        "dharma_swarm.operator_core.living_agent_kernel_persistent_adapter"
    )

    assert "anthropic" not in sys.modules
    assert "openai" not in sys.modules


@pytest.mark.parametrize("bad_task", ["", "   ", "\t\n"])
def test_empty_or_whitespace_task_raises(tmp_path, bad_task):
    agent = _agent(tmp_path)
    with pytest.raises(ValueError, match="non-empty task"):
        build_persistent_wake_payload(agent, task=bad_task)


def test_whitespace_padded_task_is_normalized_not_empty(tmp_path):
    agent = _agent(tmp_path)
    payload = build_persistent_wake_payload(agent, task="  real work  ")

    envelope = LivingAgentKernel().normalize_wake_source(
        "persistent_self_wake", payload
    )

    assert envelope.task.text == "real work"
