from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from dharma_swarm.context_compiler import ContextCompiler
from dharma_swarm.memory_kernel import (
    AuthorityLevel,
    AdapterMode,
    CensusConfig,
    MemoryAtom,
    MemoryAtomType,
    MemoryContextBudget,
    MemoryKernel,
    MemoryKernelConfig,
    MemoryLane,
    MemoryScope,
    MemorySurface,
    MemorySurfaceHealth,
    MemorySurfaceRole,
    ReadMode,
    RiskLevel,
    SurfaceCategory,
    SurfaceStatus,
    TruthState,
    WriteMode,
    preview_memory_pack,
)
from dharma_swarm.memory_kernel.adapters import ReadOnlyAdapterConfig
from dharma_swarm.memory_kernel.default_context import (
    build_memory_kernel_default_context,
    memory_kernel_isolation_policy_from_metadata,
)


def _compiler(memory_kernel: object) -> ContextCompiler:
    runtime = MagicMock()
    runtime.init_db = AsyncMock()
    runtime.get_session = AsyncMock(return_value=None)
    runtime.list_delegation_runs = AsyncMock(return_value=[])
    runtime.list_memory_facts = AsyncMock(return_value=[])
    runtime.list_artifacts = AsyncMock(return_value=[])
    runtime.list_workspace_leases = AsyncMock(return_value=[])
    runtime.new_bundle_id = MagicMock(return_value="bnd_memory_kernel")
    runtime.record_context_bundle = AsyncMock(side_effect=lambda bundle: bundle)

    lattice = MagicMock()
    lattice.init_db = AsyncMock()
    lattice.replay_session = AsyncMock(return_value=[])
    lattice.recall = AsyncMock(return_value=[])
    lattice.always_on_context = AsyncMock(return_value="")

    return ContextCompiler(
        runtime_state=runtime,
        memory_lattice=lattice,
        memory_kernel=memory_kernel,  # type: ignore[arg-type]
    )


def _pack() -> SimpleNamespace:
    admitted = SimpleNamespace(
        admitted=True,
        rank=1,
        surface_id="home.witness",
        atom_type="witness_event",
        truth_state="observed",
        authority_level="medium",
        content_snippet="safe witness note",
        selection_reasons=("context_admissible_override", "truth_state:observed"),
        source_refs=("memory_kernel:home.witness",),
    )
    omitted = SimpleNamespace(
        admitted=False,
        rank=None,
        surface_id="home.lancedb",
        atom_type="source_chunk",
        truth_state="derived",
        authority_level="none",
        content_snippet=None,
        selection_reasons=(),
        omission_reasons=("truth_state_not_allowed", "projection_blocked"),
        source_refs=(),
    )
    return SimpleNamespace(
        pack_id="memory_context_pack:test",
        candidate_count=2,
        admitted_count=1,
        omitted_count=1,
        candidate_truncated=False,
        warnings=("preview_only_no_runtime_prompt_injection",),
        items=(admitted, omitted),
    )


class _FakeMemoryKernel:
    def __init__(self, pack: SimpleNamespace | None = None, error: Exception | None = None) -> None:
        self.pack = pack
        self.error = error
        self.kwargs: dict[str, object] = {}

    def preview_memory_pack(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        assert self.pack is not None
        return self.pack


class _AdmissionMemoryKernel:
    def __init__(self, atoms: tuple[MemoryAtom, ...]) -> None:
        self.atoms = atoms
        self.kwargs: dict[str, object] = {}

    def preview_memory_pack(self, **kwargs: object):
        self.kwargs = kwargs
        query = kwargs["query"]
        budget = kwargs["budget"]
        filtered_atoms = tuple(atom for atom in self.atoms if query.allows_atom(atom))
        return preview_memory_pack(filtered_atoms, budget=budget)


class _BudgetOnlyAdmissionMemoryKernel(_AdmissionMemoryKernel):
    def preview_memory_pack(self, **kwargs: object):
        self.kwargs = kwargs
        return preview_memory_pack(self.atoms, budget=kwargs["budget"])


def _memory_surface() -> MemorySurface:
    return MemorySurface(
        surface_id="agent.memory",
        path="/tmp/agent-memory.jsonl",
        owner_module="tests",
        role=MemorySurfaceRole.MEMORY_PLANE,
        category=SurfaceCategory.RAW_EVIDENCE,
        authority_level=AuthorityLevel.MEDIUM,
        write_mode=WriteMode.READ_ONLY,
        adapter_mode=AdapterMode.READ_ONLY,
        active_status=SurfaceStatus.ACTIVE,
        health=MemorySurfaceHealth(exists=True, path_type="file"),
        provenance_quality="test",
        canon_risk=RiskLevel.LOW,
        pii_secrets_risk=RiskLevel.LOW,
    )


def _memory_atom(
    content: str,
    *,
    scope: MemoryScope,
    agent_id: str | None = None,
    freshness: str = "current_or_live_snapshot",
    valid_until: str | None = None,
    metadata: dict[str, object] | None = None,
) -> MemoryAtom:
    atom_metadata: dict[str, object] = dict(metadata or {})
    if agent_id:
        atom_metadata["agent_id"] = agent_id
    return MemoryAtom.build(
        surface=_memory_surface(),
        atom_type=MemoryAtomType.WITNESS_EVENT,
        content_ref=f"agent-memory:{content}",
        content=content,
        timestamp="2026-05-12T01:00:00Z",
        source_path="/tmp/agent-memory.jsonl",
        adapter_name="test",
        read_mode=ReadMode.READ_ONLY,
        metadata=atom_metadata,
        source_row_key=f"row:{content}",
        memory_lane=MemoryLane.PROVENANCE,
        scope=scope,
        truth_state=TruthState.OBSERVED,
        freshness=freshness,
        valid_until=valid_until,
        context_admissible=True,
    )


@pytest.mark.asyncio
async def test_context_compiler_adds_memory_kernel_default_section() -> None:
    kernel = _FakeMemoryKernel(_pack())
    compiler = _compiler(kernel)

    bundle = await compiler.compile_bundle(
        session_id="sess_memory_kernel",
        task_id="task_memory_kernel",
        task_description="Use governed memory.",
        query="governed memory",
        token_budget=1200,
    )

    assert "## Memory Kernel" in bundle.rendered_text
    assert "safe witness note" in bundle.rendered_text
    assert "projection_blocked" in bundle.rendered_text
    metadata = bundle.metadata["memory_kernel_default"]
    assert metadata["status"] == "used"
    assert metadata["text_query_applied"] is True
    assert metadata["pack_id"] == "memory_context_pack:test"
    assert metadata["admitted_count"] == 1
    assert metadata["omitted_count"] == 1
    query = kernel.kwargs["query"]
    assert getattr(query, "text_query") == "governed memory"
    budget = kernel.kwargs["budget"]
    assert getattr(budget, "require_context_admissible") is False
    assert getattr(budget, "allow_projections") is False
    assert getattr(budget, "allow_high_risk") is False


@pytest.mark.asyncio
async def test_context_compiler_uses_memory_kernel_text_query_for_live_context(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    witness = home / ".dharma/witness/2026-05-12.jsonl"
    witness.parent.mkdir(parents=True, exist_ok=True)
    witness.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "content": "alpha governed memory for live graph context",
                        "timestamp": "2026-05-12T01:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "content": "unrelated operational note",
                        "timestamp": "2026-05-12T01:01:00Z",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home, include_discovered=False),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )
    compiler = _compiler(kernel)

    bundle = await compiler.compile_bundle(
        session_id="sess_memory_kernel_live",
        task_id="task_memory_kernel_live",
        task_description="Use governed memory.",
        query="alpha governed memory",
        token_budget=1200,
        metadata={"topology": "supervisor"},
    )

    assert "## Memory Kernel" in bundle.rendered_text
    assert "alpha governed memory for live graph context" in bundle.rendered_text
    assert "unrelated operational note" not in bundle.rendered_text
    assert "memory_kernel:home.witness" in bundle.source_refs
    metadata = bundle.metadata["memory_kernel_default"]
    assert metadata["status"] == "used"
    assert metadata["text_query_applied"] is True
    assert metadata["admitted_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "topology",
    [
        "swarm",
        "supervisor",
        "subagents_as_tools",
        "fan_out",
        "fan_in",
        "pipeline",
        "broadcast",
    ],
)
async def test_context_compiler_applies_live_topology_agent_memory_isolation(
    topology: str,
) -> None:
    kernel = _AdmissionMemoryKernel(
        (
            _memory_atom(
                "alpha governed memory for the active agent",
                scope=MemoryScope.AGENT,
                agent_id="agent-alpha",
            ),
            _memory_atom(
                "beta private memory for another agent",
                scope=MemoryScope.AGENT,
                agent_id="agent-beta",
            ),
            _memory_atom(
                "ownerless agent scoped memory",
                scope=MemoryScope.AGENT,
            ),
            _memory_atom(
                "shared project memory for the graph",
                scope=MemoryScope.PROJECT,
            ),
        )
    )
    compiler = _compiler(kernel)

    bundle = await compiler.compile_bundle(
        session_id=f"sess_{topology}",
        task_id=f"task_{topology}",
        task_description="Use governed memory.",
        query="memory",
        token_budget=4000,
        metadata={"topology": topology, "agent_id": "agent-alpha"},
    )

    assert "alpha governed memory for the active agent" in bundle.rendered_text
    assert "shared project memory for the graph" in bundle.rendered_text
    assert "beta private memory for another agent" not in bundle.rendered_text
    assert "ownerless agent scoped memory" not in bundle.rendered_text
    assert "agent_not_allowed" in bundle.rendered_text
    assert "agent_owner_unknown" in bundle.rendered_text

    metadata = bundle.metadata["memory_kernel_default"]
    assert metadata["status"] == "used"
    assert metadata["isolation_applied"] is True
    assert metadata["isolation_topology"] == topology
    assert metadata["isolation_agent_id"] == "agent-alpha"
    assert metadata["allowed_agent_ids"] == ["agent-alpha"]
    assert "agent" in metadata["allowed_scopes"]
    assert "project" in metadata["allowed_scopes"]
    expected_semantics = (
        "supervisor_scoped" if topology == "supervisor" else "worker_scoped"
    )
    assert metadata["isolation_semantics"] == expected_semantics
    assert metadata["isolation_warnings"] == []
    assert ("session" in metadata["allowed_scopes"]) == (topology == "supervisor")
    assert metadata["admitted_count"] == 2
    assert metadata["omitted_count"] == 2
    budget = kernel.kwargs["budget"]
    assert getattr(budget, "allowed_agent_ids") == ("agent-alpha",)
    assert getattr(budget, "isolation_mode") == "scoped"


@pytest.mark.asyncio
@pytest.mark.parametrize("topology", ["dispatch", "warlock_mode", None])
async def test_context_compiler_fails_closed_on_unknown_topology(
    topology: str | None,
) -> None:
    kernel = _AdmissionMemoryKernel(
        (
            _memory_atom(
                "alpha governed memory for the active agent",
                scope=MemoryScope.AGENT,
                agent_id="agent-alpha",
            ),
            _memory_atom(
                "beta private memory for another agent",
                scope=MemoryScope.AGENT,
                agent_id="agent-beta",
            ),
            _memory_atom(
                "shared project memory for the graph",
                scope=MemoryScope.PROJECT,
            ),
        )
    )
    compiler = _compiler(kernel)

    metadata_in: dict[str, object] = {"agent_id": "agent-alpha"}
    if topology is not None:
        metadata_in["topology"] = topology
    bundle = await compiler.compile_bundle(
        session_id="sess_unknown_topology",
        task_id="task_unknown_topology",
        task_description="Use governed memory.",
        query="memory",
        token_budget=4000,
        metadata=metadata_in,
    )

    metadata = bundle.metadata["memory_kernel_default"]
    assert metadata["isolation_applied"] is True
    assert metadata["isolation_semantics"] == "fail_closed_minimal"
    assert metadata["allowed_scopes"] == ["project", "repo"]
    assert metadata["allowed_memory_lanes"] == ["semantic", "procedural"]
    expected_warning = (
        "topology_missing_fail_closed"
        if topology is None
        else f"unknown_topology_fail_closed:{topology}"
    )
    assert metadata["isolation_warnings"] == [expected_warning]
    # PROVENANCE-lane fixtures are outside the minimal curated lanes; the
    # unknown-topology bundle admits nothing instead of everything.
    assert metadata["admitted_count"] == 0
    assert "alpha governed memory for the active agent" not in bundle.rendered_text
    assert "beta private memory for another agent" not in bundle.rendered_text
    assert "shared project memory for the graph" not in bundle.rendered_text
    budget = kernel.kwargs["budget"]
    assert getattr(budget, "isolation_mode") == "scoped"


@pytest.mark.asyncio
@pytest.mark.parametrize("topology", ["fan_out", "supervisor"])
async def test_worker_topologies_exclude_session_scope(topology: str) -> None:
    kernel = _AdmissionMemoryKernel(
        (
            _memory_atom(
                "session memory from the originating run",
                scope=MemoryScope.SESSION,
            ),
            _memory_atom(
                "shared project memory for the graph",
                scope=MemoryScope.PROJECT,
            ),
        )
    )
    compiler = _compiler(kernel)

    bundle = await compiler.compile_bundle(
        session_id=f"sess_session_scope_{topology}",
        task_id=f"task_session_scope_{topology}",
        task_description="Use governed memory.",
        query="memory",
        token_budget=4000,
        metadata={"topology": topology, "agent_id": "agent-alpha"},
    )

    assert "shared project memory for the graph" in bundle.rendered_text
    session_visible = "session memory from the originating run" in bundle.rendered_text
    assert session_visible == (topology == "supervisor")
    if topology != "supervisor":
        assert "scope_not_allowed" in bundle.rendered_text


@pytest.mark.asyncio
async def test_scoped_isolation_hides_other_agents_atoms_in_shared_scopes() -> None:
    kernel = _AdmissionMemoryKernel(
        (
            _memory_atom(
                "beta owned note shared into the swarm scope",
                scope=MemoryScope.SWARM,
                agent_id="agent-beta",
            ),
            _memory_atom(
                "ownerless swarm coordination note",
                scope=MemoryScope.SWARM,
            ),
        )
    )
    compiler = _compiler(kernel)

    bundle = await compiler.compile_bundle(
        session_id="sess_cross_scope_ownership",
        task_id="task_cross_scope_ownership",
        task_description="Use governed memory.",
        query="swarm",
        token_budget=4000,
        metadata={"topology": "fan_out", "agent_id": "agent-alpha"},
    )

    assert "ownerless swarm coordination note" in bundle.rendered_text
    assert "beta owned note shared into the swarm scope" not in bundle.rendered_text
    assert "agent_not_allowed" in bundle.rendered_text


@pytest.mark.asyncio
async def test_isolation_legacy_env_restores_pre_typed_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DHARMA_MEMORY_KERNEL_ISOLATION_LEGACY", "1")
    kernel = _AdmissionMemoryKernel(
        (
            _memory_atom(
                "beta private memory for another agent",
                scope=MemoryScope.AGENT,
                agent_id="agent-beta",
            ),
        )
    )
    compiler = _compiler(kernel)

    bundle = await compiler.compile_bundle(
        session_id="sess_legacy_escape_hatch",
        task_id="task_legacy_escape_hatch",
        task_description="Use governed memory.",
        query="memory",
        token_budget=4000,
        metadata={"topology": "fan_out"},
    )

    metadata = bundle.metadata["memory_kernel_default"]
    assert metadata["isolation_applied"] is False
    assert metadata["isolation_semantics"] == "legacy"
    assert "beta private memory for another agent" in bundle.rendered_text
    budget = kernel.kwargs["budget"]
    assert getattr(budget, "isolation_mode") == "unrestricted"


def test_isolation_semantics_map_is_total_over_topology_type() -> None:
    from dharma_swarm.memory_kernel.topology_policy import ISOLATION_SEMANTICS
    from dharma_swarm.models import TopologyType

    assert set(ISOLATION_SEMANTICS) == set(TopologyType)


def test_resolve_unmapped_topology_member_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dharma_swarm.memory_kernel import topology_policy
    from dharma_swarm.models import TopologyType

    monkeypatch.delitem(
        topology_policy.ISOLATION_SEMANTICS, TopologyType.FAN_OUT
    )
    semantics, warnings = topology_policy.resolve(TopologyType.FAN_OUT)
    assert semantics is topology_policy.FAIL_CLOSED_MINIMAL
    assert warnings == ("unmapped_topology_fail_closed:fan_out",)
    semantics, warnings = topology_policy.resolve("fan_out")
    assert semantics is topology_policy.FAIL_CLOSED_MINIMAL
    assert warnings == ("unmapped_topology_fail_closed:fan_out",)


def test_scoped_budget_denies_on_empty_allowances() -> None:
    budget = MemoryContextBudget(
        isolation_mode="scoped",
        allowed_scopes=(),
        allowed_memory_lanes=(),
    )
    pack = preview_memory_pack(
        (_memory_atom("orphaned atom", scope=MemoryScope.PROJECT),),
        budget=budget,
    )
    assert pack.admitted_count == 0
    reasons = pack.items[0].omission_reasons
    assert "scope_denied_fail_closed" in reasons
    assert "memory_lane_denied_fail_closed" in reasons


def test_budget_rejects_unknown_isolation_mode() -> None:
    with pytest.raises(ValueError, match="isolation_mode"):
        MemoryContextBudget(isolation_mode="scopedd")


def test_explicit_allowance_override_stamps_warning() -> None:
    from dharma_swarm.memory_kernel.default_context import (
        memory_kernel_isolation_policy_from_metadata,
    )

    policy = memory_kernel_isolation_policy_from_metadata(
        {
            "topology": "fan_out",
            "agent_id": "agent-alpha",
            "memory_kernel_allowed_scopes": ["session"],
        }
    )
    assert policy.semantics == "worker_scoped"
    assert policy.allowed_scopes == (MemoryScope.SESSION,)
    assert "explicit_scopes_override_topology_semantics" in policy.warnings


def test_enum_topology_metadata_stamps_enum_value() -> None:
    from dharma_swarm.memory_kernel.default_context import (
        memory_kernel_isolation_policy_from_metadata,
    )
    from dharma_swarm.models import TopologyType

    policy = memory_kernel_isolation_policy_from_metadata(
        {"topology": TopologyType.FAN_OUT, "agent_id": "agent-alpha"}
    )
    assert policy.topology == "fan_out"
    assert policy.semantics == "worker_scoped"
    assert policy.warnings == ()


@pytest.mark.asyncio
async def test_context_compiler_rejects_stale_memory_with_retrieval_telemetry() -> None:
    kernel = _AdmissionMemoryKernel(
        (
            _memory_atom(
                "alpha governed memory current enough for live graph context",
                scope=MemoryScope.PROJECT,
            ),
            _memory_atom(
                "alpha governed memory stale snapshot from old context",
                scope=MemoryScope.PROJECT,
                freshness="snapshot",
            ),
            _memory_atom(
                "alpha governed memory expired operational note",
                scope=MemoryScope.PROJECT,
                valid_until="2000-01-01T00:00:00Z",
            ),
        )
    )
    compiler = _compiler(kernel)

    bundle = await compiler.compile_bundle(
        session_id="sess_memory_kernel_stale",
        task_id="task_memory_kernel_stale",
        task_description="Use governed memory.",
        query="alpha governed memory",
        token_budget=4000,
        metadata={"topology": "swarm", "agent_id": "agent-alpha"},
    )

    assert "alpha governed memory current enough for live graph context" in bundle.rendered_text
    assert "alpha governed memory stale snapshot from old context" not in bundle.rendered_text
    assert "alpha governed memory expired operational note" not in bundle.rendered_text
    assert "stale_memory_rejected" in bundle.rendered_text
    assert "valid_until_expired" in bundle.rendered_text

    metadata = bundle.metadata["memory_kernel_default"]
    assert metadata["admitted_count"] == 1
    assert metadata["omitted_count"] == 2
    assert metadata["retrieval_telemetry"]["candidate_count"] == 3
    assert metadata["retrieval_telemetry"]["omission_reason_counts"] == {
        "stale_memory_rejected": 1,
        "valid_until_expired": 1,
    }
    assert metadata["retrieval_telemetry"]["admitted_surface_ids"] == ["agent.memory"]
    budget = kernel.kwargs["budget"]
    assert getattr(budget, "reject_stale") is True


@pytest.mark.asyncio
async def test_context_compiler_enforces_curated_source_and_tool_exposure_isolation() -> None:
    current_atom = _memory_atom(
        "alpha curated source memory for live graph context",
        scope=MemoryScope.PROJECT,
    )
    missing_digest_atom = replace(
        _memory_atom(
            "alpha missing digest memory must not enter context",
            scope=MemoryScope.PROJECT,
        ),
        source_digest=None,
    )
    missing_row_key_atom = replace(
        _memory_atom(
            "alpha missing row key memory must not enter context",
            scope=MemoryScope.PROJECT,
        ),
        source_row_key=None,
    )
    tool_exposure_atom = _memory_atom(
        "alpha tool exposure memory must not enter context",
        scope=MemoryScope.PROJECT,
        metadata={
            "visible_tools": ["apply_patch", "write_file"],
            "tool_calls": [{"name": "apply_patch", "arguments": {}}],
        },
    )
    kernel = _BudgetOnlyAdmissionMemoryKernel(
        (current_atom, missing_digest_atom, missing_row_key_atom, tool_exposure_atom)
    )
    compiler = _compiler(kernel)

    bundle = await compiler.compile_bundle(
        session_id="sess_memory_kernel_curated_tool_isolation",
        task_id="task_memory_kernel_curated_tool_isolation",
        task_description="Use governed memory.",
        query="alpha",
        token_budget=4000,
        metadata={"topology": "swarm", "agent_id": "agent-alpha"},
    )

    assert "alpha curated source memory for live graph context" in bundle.rendered_text
    assert "alpha missing digest memory must not enter context" not in bundle.rendered_text
    assert "alpha missing row key memory must not enter context" not in bundle.rendered_text
    assert "alpha tool exposure memory must not enter context" not in bundle.rendered_text
    assert "source_digest_required" in bundle.rendered_text
    assert "source_row_key_required" in bundle.rendered_text
    assert "tool_exposure_blocked" in bundle.rendered_text

    metadata = bundle.metadata["memory_kernel_default"]
    assert metadata["admitted_count"] == 1
    assert metadata["omitted_count"] == 3
    assert metadata["retrieval_telemetry"]["omission_reason_counts"] == {
        "source_digest_required": 1,
        "source_row_key_required": 1,
        "tool_exposure_blocked": 1,
    }
    query = kernel.kwargs["query"]
    assert getattr(query, "require_source_digest") is True
    assert getattr(query, "require_source_row_key") is True
    budget = kernel.kwargs["budget"]
    assert getattr(budget, "require_source_digest") is True
    assert getattr(budget, "require_source_row_key") is True
    assert getattr(budget, "block_tool_exposure") is True


@pytest.mark.asyncio
async def test_context_compiler_falls_back_when_memory_kernel_fails() -> None:
    compiler = _compiler(_FakeMemoryKernel(error=RuntimeError("kernel unavailable")))

    bundle = await compiler.compile_bundle(
        session_id="sess_memory_kernel_fail",
        task_description="Continue with legacy context.",
        token_budget=1200,
    )

    assert "# DGC Context Bundle" in bundle.rendered_text
    assert "## Memory Kernel" not in bundle.rendered_text
    metadata = bundle.metadata["memory_kernel_default"]
    assert metadata["status"] == "failed"
    assert metadata["error_type"] == "RuntimeError"


class _ShadowRankedMemoryKernel(_FakeMemoryKernel):
    def __init__(
        self,
        pack: SimpleNamespace,
        *,
        candidates: tuple[SimpleNamespace, ...] = (),
        shadow_atoms: tuple[MemoryAtom, ...] = (),
        query_error: Exception | None = None,
    ) -> None:
        super().__init__(pack)
        self.candidates = candidates
        self.shadow_atoms = shadow_atoms
        self.query_error = query_error
        self.query_calls: list[tuple[str, int]] = []

    def query(self, text: str, *, top_k: int = 10, **_: object) -> SimpleNamespace:
        self.query_calls.append((text, top_k))
        if self.query_error is not None:
            raise self.query_error
        return SimpleNamespace(candidates=self.candidates)

    def atoms_for_candidates(self, candidates: object) -> tuple[MemoryAtom, ...]:
        return self.shadow_atoms


@pytest.mark.asyncio
async def test_memory_kernel_shadow_unavailable_when_ranked_door_missing() -> None:
    compiler = _compiler(_FakeMemoryKernel(_pack()))

    bundle = await compiler.compile_bundle(
        session_id="sess_shadow_unavailable",
        task_id="task_shadow_unavailable",
        task_description="Use governed memory.",
        query="governed memory",
        token_budget=1200,
    )

    metadata = bundle.metadata["memory_kernel_default"]
    assert metadata["status"] == "used"
    assert metadata["memory_kernel_candidate_source"] == "legacy_scan+ranked_shadow"
    assert metadata["shadow_overlap_at_k"] is None
    assert metadata["shadow_admitted_delta"] is None
    assert metadata["ranked_shadow"]["status"] == "unavailable"
    assert metadata["ranked_shadow"]["reason"] == "ranked_door_unavailable"
    assert "shadow_error" not in metadata


def test_memory_kernel_shadow_records_divergence_metrics() -> None:
    overlapping = SimpleNamespace(
        doc_id="doc-overlap",
        source="memory_kernel:home.witness",
        metadata={},
    )
    novel = SimpleNamespace(
        doc_id="doc-novel",
        source="receipt:unrelated-lane",
        metadata={},
    )
    kernel = _ShadowRankedMemoryKernel(
        _pack(),
        candidates=(overlapping, novel),
        shadow_atoms=(
            _memory_atom(
                "shadow ranked project memory alpha", scope=MemoryScope.PROJECT
            ),
            _memory_atom(
                "shadow ranked project memory beta", scope=MemoryScope.PROJECT
            ),
        ),
    )
    policy = memory_kernel_isolation_policy_from_metadata(
        {"topology": "supervisor", "agent_id": "agent-alpha"}
    )

    section, metadata = build_memory_kernel_default_context(
        kernel,
        recall_query="governed memory",
        token_budget=1200,
        isolation_policy=policy,
    )

    assert section is not None
    # Legacy still serves: the rendered section comes from the legacy pack
    # only; shadow atoms never reach prompt content in the shadow phase.
    assert "safe witness note" in section.content
    assert "shadow ranked project memory alpha" not in section.content
    assert metadata["memory_kernel_candidate_source"] == "legacy_scan+ranked_shadow"
    assert metadata["shadow_overlap_at_k"] == 0.5
    assert metadata["shadow_admitted_delta"] == 1
    assert "shadow_error" not in metadata
    detail = metadata["ranked_shadow"]
    assert detail["status"] == "recorded"
    assert detail["top_k"] == 12
    assert detail["candidate_count"] == 2
    assert detail["overlap_count"] == 1
    assert detail["shadow_admitted_count"] == 2
    assert detail["legacy_admitted_count"] == 1
    assert detail["shadow_omission_reason_counts"] == {}
    assert kernel.query_calls == [("governed memory", 12)]


def test_memory_kernel_shadow_kill_switch_disables_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DHARMA_MEMORY_KERNEL_RANKED_SHADOW", "0")
    kernel = _ShadowRankedMemoryKernel(_pack())

    section, metadata = build_memory_kernel_default_context(
        kernel,
        recall_query="governed memory",
        token_budget=1200,
    )

    assert section is not None
    assert metadata["memory_kernel_candidate_source"] == "legacy_scan+ranked_shadow"
    assert metadata["shadow_overlap_at_k"] is None
    assert metadata["shadow_admitted_delta"] is None
    assert metadata["ranked_shadow"]["status"] == "disabled"
    assert kernel.query_calls == []


def test_memory_kernel_shadow_skips_empty_recall_query() -> None:
    kernel = _ShadowRankedMemoryKernel(_pack())

    section, metadata = build_memory_kernel_default_context(
        kernel,
        recall_query="",
        token_budget=1200,
    )

    assert section is not None
    assert metadata["shadow_overlap_at_k"] is None
    assert metadata["shadow_admitted_delta"] is None
    assert metadata["ranked_shadow"]["status"] == "skipped"
    assert metadata["ranked_shadow"]["reason"] == "empty_recall_query"
    assert kernel.query_calls == []


@pytest.mark.asyncio
async def test_memory_kernel_shadow_error_never_breaks_compile() -> None:
    kernel = _ShadowRankedMemoryKernel(
        _pack(),
        query_error=RuntimeError("ranked door down"),
    )
    compiler = _compiler(kernel)

    bundle = await compiler.compile_bundle(
        session_id="sess_shadow_error",
        task_id="task_shadow_error",
        task_description="Use governed memory.",
        query="governed memory",
        token_budget=1200,
    )

    assert "## Memory Kernel" in bundle.rendered_text
    assert "safe witness note" in bundle.rendered_text
    metadata = bundle.metadata["memory_kernel_default"]
    assert metadata["status"] == "used"
    assert metadata["memory_kernel_candidate_source"] == "legacy_scan+ranked_shadow"
    assert metadata["shadow_overlap_at_k"] is None
    assert metadata["shadow_admitted_delta"] is None
    assert metadata["shadow_error"].startswith("RuntimeError")
    assert metadata["ranked_shadow"]["status"] == "error"
