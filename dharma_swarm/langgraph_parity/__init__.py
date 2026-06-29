"""Deterministic LangGraph parity harness."""

from importlib import import_module

from dharma_swarm.langgraph_parity.isolation import (
    AgentIsolationView,
    AdmissionTrace,
    DomainPack,
    IsolationPolicy,
    MemoryFact,
    SimulatedMemoryKernel,
    SimulatedSemanticCommons,
    ToolSpec,
    collect_isolation_failures,
    default_distractor_packs,
    default_isolation_policy,
    default_memory_kernel,
    default_semantic_commons,
)
from dharma_swarm.langgraph_parity.state import (
    AgentManifest,
    ParityMessage,
    SupervisorParityState,
    SwarmState,
    TransferReceipt,
)
from dharma_swarm.langgraph_parity.supervisor_runtime import (
    DeterministicSubagent,
    DeterministicSupervisorRuntime,
)
from dharma_swarm.langgraph_parity.swarm_runtime import (
    AgentContext,
    AgentDecision,
    DeterministicAgent,
    DeterministicSwarmRuntime,
)
from dharma_swarm.langgraph_parity.tools import HandoffTool, handoff_tool_name, transfer_tool_name

__all__ = [
    "AdmissionTrace",
    "AgentContext",
    "AgentDecision",
    "AgentIsolationView",
    "AgentManifest",
    "DeterministicAgent",
    "DeterministicSubagent",
    "DeterministicSupervisorRuntime",
    "DeterministicSwarmRuntime",
    "DomainPack",
    "HandoffTool",
    "IsolationPolicy",
    "MemoryFact",
    "ParityMessage",
    "SimulatedMemoryKernel",
    "SimulatedSemanticCommons",
    "SupervisorParityState",
    "SwarmState",
    "ToolSpec",
    "TransferReceipt",
    "collect_isolation_failures",
    "default_distractor_packs",
    "default_isolation_policy",
    "default_memory_kernel",
    "default_semantic_commons",
    "handoff_tool_name",
    "record_benchmark_runtime_receipt",
    "run_benchmark",
    "transfer_tool_name",
    "write_report",
]


def __getattr__(name: str) -> object:
    if name in {"record_benchmark_runtime_receipt", "run_benchmark", "write_report"}:
        benchmark = import_module("dharma_swarm.langgraph_parity.benchmark")
        return getattr(benchmark, name)
    raise AttributeError(name)
