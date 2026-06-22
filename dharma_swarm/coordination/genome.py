"""OrchestrationGenome — the central abstraction of the orchestration substrate.

Every arena attempt is a genome. Evolution mutates genomes; the arena scores
genomes; the Council verifies genome outcomes; the DPI ranks genome-level
techniques; the (later) learned coordinator learns to *emit* genomes.

Per the LOCKED spec (docs/architecture/LEARNED_AUDITABLE_ORCHESTRATOR_SPEC.md §1),
``OrchestrationGenome`` **EXTENDS / WRAPS** the existing ``TopologyGenome`` rather
than creating a parallel abstraction (honors the SSOT naming rule). It carries a
documented adapter seam — ``from_topology_genome()`` / ``to_topology_genome()`` —
so the two stay reconcilable. ``TopologyGenome`` is currently local-only (absent
from ``origin/main``); the adapters import it lazily so this module loads even if
that base is reshaped during reconciliation.

Design invariants honored here:
  * Quality-diversity, not top-k: every genome carries ``lineage`` and
    ``behavioral_descriptors`` (MAP-Elites bins).
  * Budget parity: ``budget_allocation`` sums are checked against a parity cap.
  * Stable identity: ``genome_id`` is a content hash over the *structural* fields,
    so the same orchestration plan always hashes to the same id regardless of
    lineage/telemetry metadata.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

# ``access_list`` follows the Conductor paper's binary choice (2512.04388):
#   [] (nothing) | "all" (everything) | [idx, ...] (specific upstream subtasks).
AccessList = Union[list[int], Literal["all"], list[Any]]

RosterKind = Literal["model", "tool", "organ", "human"]
AdjudicationRule = Literal["vote", "debate", "moat-gate", "synthesize", "single"]
StopCondition = Literal[
    "accept-on-council-accept",
    "max-turns",
    "budget-exhausted",
]


class Subtask(BaseModel):
    """One decomposed unit of work in the genome."""

    subtask_id: str
    description: str = ""
    depends_on: list[str] = Field(default_factory=list)


class RosterMember(BaseModel):
    """A role bound to a model/tool/organ/human drawn from the existing pool.

    ``member_id`` is a model_id from the existing ``model_pool`` (for ``model``
    kind), a tool name, an organ name, or a human handle. This genome NEVER owns
    the model catalog — it only references it.
    """

    role_id: str
    member_id: str
    kind: RosterKind = "model"


class RoleEdge(BaseModel):
    """Directed communication edge in the role graph (who talks to whom)."""

    source_role_id: str
    target_role_id: str
    channel: str = "default"


class RoleBudget(BaseModel):
    """Per-role compute envelope. Sums are parity-checked across the genome."""

    tokens: int = 0
    latency_ms: int = 0
    compute_units: float = 0.0


class Lineage(BaseModel):
    """MAP-Elites lineage: where this genome came from."""

    parent_genome_id: Optional[str] = None
    mutation_op: Optional[str] = None
    generation: int = 0


class BehavioralDescriptors(BaseModel):
    """MAP-Elites behavioral bins (quality-diversity, not top-k).

    These are the descriptors the archive bins on — NOT fitness. Diversity is
    measured here so DarwinEngine selection can preserve it (transcendence).
    """

    decomposition_depth: int = 0
    roster_size: int = 0
    roster_diversity: int = 0  # distinct member_ids
    topology_shape: str = "single"  # single | star | pipeline | mesh | tree
    adjudication: str = "single"

    def bin_key(self) -> tuple[int, int, int, str, str]:
        """Coarse archive cell coordinate."""
        return (
            self.decomposition_depth,
            self.roster_size,
            self.roster_diversity,
            self.topology_shape,
            self.adjudication,
        )


class VerificationStep(BaseModel):
    """Which Council profile gates which step."""

    step: str
    council_profile: str = "orchestration_trace_verification"


class OrchestrationGenome(BaseModel):
    """The full orchestration plan, scored as a unit by the arena.

    Extends ``TopologyGenome`` via the adapter seam (``from_topology_genome`` /
    ``to_topology_genome``). All fields from spec §1 are present.
    """

    # Identity — computed from structural content unless pinned explicitly.
    genome_id: str = ""

    # Structural plan (these determine identity)
    task_decomposition: list[Subtask] = Field(default_factory=list)
    role_graph: list[RoleEdge] = Field(default_factory=list)
    roster: list[RosterMember] = Field(default_factory=list)
    prompt_fragments: dict[str, str] = Field(default_factory=dict)
    context_plan: dict[str, AccessList] = Field(default_factory=dict)
    budget_allocation: dict[str, RoleBudget] = Field(default_factory=dict)
    verification_plan: list[VerificationStep] = Field(default_factory=list)
    adjudication_rule: AdjudicationRule = "single"
    stop_condition: StopCondition = "budget-exhausted"
    fallback_rules: dict[str, str] = Field(default_factory=dict)
    permissions: dict[str, list[str]] = Field(default_factory=dict)

    # MAP-Elites metadata (NOT part of identity)
    lineage: Lineage = Field(default_factory=Lineage)
    behavioral_descriptors: BehavioralDescriptors = Field(default_factory=BehavioralDescriptors)

    # Receipt references (filled by the arena/orchestrator; not part of identity)
    receipt_refs: list[str] = Field(default_factory=list)

    # ------------------------------------------------------------------ identity
    def _identity_payload(self) -> dict[str, Any]:
        """The structural content that defines genome identity (stable)."""
        return {
            "task_decomposition": [s.model_dump() for s in self.task_decomposition],
            "role_graph": [e.model_dump() for e in self.role_graph],
            "roster": [m.model_dump() for m in self.roster],
            "prompt_fragments": self.prompt_fragments,
            "context_plan": self.context_plan,
            "budget_allocation": {k: v.model_dump() for k, v in self.budget_allocation.items()},
            "verification_plan": [v.model_dump() for v in self.verification_plan],
            "adjudication_rule": self.adjudication_rule,
            "stop_condition": self.stop_condition,
            "fallback_rules": self.fallback_rules,
            "permissions": self.permissions,
        }

    def stable_id(self) -> str:
        """Deterministic content hash. Same plan -> same id."""
        payload = json.dumps(self._identity_payload(), sort_keys=True, default=str)
        return "genome-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @model_validator(mode="after")
    def _assign_id(self) -> "OrchestrationGenome":
        if not self.genome_id:
            self.genome_id = self.stable_id()
        return self

    # ---------------------------------------------------------------- validation
    def validate_structure(self, *, budget_parity_cap: Optional[int] = None) -> "OrchestrationGenome":
        """Validate referential integrity and (optionally) budget parity.

        Raises ``ValueError`` on any structural inconsistency. ``budget_parity_cap``
        — when given — caps the TOTAL token budget across all roles, enforcing the
        spec's budget-parity invariant at the genome level.
        """
        role_ids = {m.role_id for m in self.roster}
        if len(role_ids) != len(self.roster):
            raise ValueError("Duplicate role_id values in roster")

        for edge in self.role_graph:
            if edge.source_role_id not in role_ids:
                raise ValueError(f"role_graph edge references unknown source role {edge.source_role_id}")
            if edge.target_role_id not in role_ids:
                raise ValueError(f"role_graph edge references unknown target role {edge.target_role_id}")

        for role_id in self.prompt_fragments:
            if role_id not in role_ids:
                raise ValueError(f"prompt_fragments references unknown role {role_id}")
        for role_id in self.budget_allocation:
            if role_id not in role_ids:
                raise ValueError(f"budget_allocation references unknown role {role_id}")
        for role_id in self.context_plan:
            if role_id not in role_ids:
                raise ValueError(f"context_plan references unknown role {role_id}")
        for role_id in self.permissions:
            if role_id not in role_ids:
                raise ValueError(f"permissions references unknown role {role_id}")

        seen_sub: set[str] = set()
        for sub in self.task_decomposition:
            if sub.subtask_id in seen_sub:
                raise ValueError(f"Duplicate subtask_id {sub.subtask_id}")
            seen_sub.add(sub.subtask_id)
        for sub in self.task_decomposition:
            for dep in sub.depends_on:
                if dep not in seen_sub:
                    raise ValueError(f"subtask {sub.subtask_id} depends on unknown {dep}")

        # The decomposition is a dependency DAG — reject cycles so a non-DAG can
        # never enter the arena/archive (descriptor depth is otherwise ill-defined).
        cyclic = _first_cycle_subtask(self.task_decomposition)
        if cyclic is not None:
            raise ValueError(f"task_decomposition has a dependency cycle involving {cyclic}")

        if budget_parity_cap is not None:
            total = self.total_token_budget()
            if total > budget_parity_cap:
                raise ValueError(
                    f"budget parity violated: total tokens {total} > cap {budget_parity_cap}"
                )
        return self

    def total_token_budget(self) -> int:
        return sum(b.tokens for b in self.budget_allocation.values())

    def total_compute_units(self) -> float:
        return sum(b.compute_units for b in self.budget_allocation.values())

    # ------------------------------------------------------- behavioral descriptors
    def derive_descriptors(self) -> BehavioralDescriptors:
        """Compute MAP-Elites descriptors from the current structure."""
        depth = _decomposition_depth(self.task_decomposition)
        members = [m.member_id for m in self.roster]
        shape = _topology_shape(self.roster, self.role_graph)
        return BehavioralDescriptors(
            decomposition_depth=depth,
            roster_size=len(self.roster),
            roster_diversity=len(set(members)),
            topology_shape=shape,
            adjudication=self.adjudication_rule,
        )

    def with_descriptors(self) -> "OrchestrationGenome":
        """Return a copy with behavioral_descriptors recomputed."""
        clone = self.model_copy(deep=True)
        clone.behavioral_descriptors = clone.derive_descriptors()
        return clone

    # --------------------------------------------------------- serialization seam
    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str) -> "OrchestrationGenome":
        return cls.model_validate_json(raw)

    # ----------------------------------------------- TopologyGenome adapter seam
    # The genome EXTENDS TopologyGenome. These adapters keep the two reconcilable.
    # TopologyGenome is local-only (absent on origin/main): import lazily so this
    # module never hard-depends on a base that may be reshaped during reconciliation.
    def to_topology_genome(self, name: Optional[str] = None) -> Any:
        """Project this orchestration genome onto a ``TopologyGenome``.

        Roles become nodes; role_graph edges become topology edges. Roster
        membership, prompt fragment, and access list ride in node ``metadata`` so
        the projection is loss-tolerant (round-trippable for the fields the base
        models). Roles without an incoming edge are entrypoints.
        """
        try:
            from dharma_swarm.topology_genome import (
                TopologyEdge,
                TopologyGenome,
                TopologyNode,
            )
        except ImportError as exc:  # pragma: no cover - base not landed
            raise NotImplementedError(
                "TopologyGenome base not importable. TODO: wire adapter once the "
                "local-only TopologyGenome work lands on origin/main (spec §1, Phase 0)."
            ) from exc

        member_by_role = {m.role_id: m for m in self.roster}
        nodes: list[TopologyNode] = []
        for m in self.roster:
            nodes.append(
                TopologyNode(
                    node_id=m.role_id,
                    step_name=m.role_id,
                    metadata={
                        "agent_role": m.kind,
                        "member_id": m.member_id,
                        "prompt_fragment": self.prompt_fragments.get(m.role_id, ""),
                        "access_list": self.context_plan.get(m.role_id, []),
                        "permissions": self.permissions.get(m.role_id, []),
                    },
                )
            )
        edges: list[TopologyEdge] = []
        targets: set[str] = set()
        for i, e in enumerate(self.role_graph):
            edges.append(
                TopologyEdge(
                    edge_id=f"edge-{i}-{e.source_role_id}-{e.target_role_id}",
                    source_node_id=e.source_role_id,
                    target_node_id=e.target_role_id,
                    metadata={"channel": e.channel},
                )
            )
            targets.add(e.target_role_id)
        entrypoints = [m.role_id for m in self.roster if m.role_id not in targets]
        return TopologyGenome(
            genome_id=self.genome_id,
            name=name or f"orchestration-{self.genome_id}",
            nodes=nodes,
            edges=edges,
            entrypoints=entrypoints,
            metadata={
                "orchestration_genome_id": self.genome_id,
                "adjudication_rule": self.adjudication_rule,
                "stop_condition": self.stop_condition,
            },
        )

    @classmethod
    def from_topology_genome(cls, topo: Any) -> "OrchestrationGenome":
        """Lift a ``TopologyGenome`` into an ``OrchestrationGenome``.

        Inverse of :meth:`to_topology_genome` for the fields the base carries.
        Fields not modeled by TopologyGenome (verification_plan, fallback_rules,
        budget parity) default empty and must be filled by the orchestrator.
        """
        try:
            from dharma_swarm.topology_genome import TopologyGenome  # noqa: F401
        except ImportError as exc:  # pragma: no cover - base not landed
            raise NotImplementedError(
                "TopologyGenome base not importable. TODO: wire adapter once the "
                "local-only TopologyGenome work lands on origin/main (spec §1, Phase 0)."
            ) from exc

        roster: list[RosterMember] = []
        prompt_fragments: dict[str, str] = {}
        context_plan: dict[str, AccessList] = {}
        permissions: dict[str, list[str]] = {}
        for node in topo.nodes:
            md = node.metadata or {}
            roster.append(
                RosterMember(
                    role_id=node.node_id,
                    member_id=str(md.get("member_id", node.node_id)),
                    kind=md.get("agent_role") if md.get("agent_role") in ("model", "tool", "organ", "human") else "model",
                )
            )
            if md.get("prompt_fragment"):
                prompt_fragments[node.node_id] = str(md["prompt_fragment"])
            if "access_list" in md:
                context_plan[node.node_id] = md["access_list"]
            if md.get("permissions"):
                permissions[node.node_id] = list(md["permissions"])
        role_graph = [
            RoleEdge(
                source_role_id=e.source_node_id,
                target_role_id=e.target_node_id,
                channel=str((e.metadata or {}).get("channel", "default")),
            )
            for e in topo.edges
        ]
        genome = cls(
            genome_id=topo.genome_id,
            roster=roster,
            role_graph=role_graph,
            prompt_fragments=prompt_fragments,
            context_plan=context_plan,
            permissions=permissions,
            adjudication_rule=(topo.metadata or {}).get("adjudication_rule", "single"),
            stop_condition=(topo.metadata or {}).get("stop_condition", "budget-exhausted"),
        )
        return genome.with_descriptors()


def _first_cycle_subtask(subtasks: list[Subtask]) -> Optional[str]:
    """Return a subtask_id participating in a dependency cycle, or None if the
    decomposition is a DAG. Iterative DFS with a recursion stack."""
    by_id = {s.subtask_id: s for s in subtasks}
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {s.subtask_id: WHITE for s in subtasks}

    def visit(start: str) -> Optional[str]:
        stack: list[tuple[str, int]] = [(start, 0)]
        while stack:
            node, idx = stack[-1]
            if idx == 0:
                color[node] = GREY
            sub = by_id.get(node)
            deps = sub.depends_on if sub else []
            if idx < len(deps):
                stack[-1] = (node, idx + 1)
                dep = deps[idx]
                if dep not in by_id:
                    continue
                if color[dep] == GREY:  # back-edge -> cycle
                    return dep
                if color[dep] == WHITE:
                    stack.append((dep, 0))
            else:
                color[node] = BLACK
                stack.pop()
        return None

    for s in subtasks:
        if color[s.subtask_id] == WHITE:
            found = visit(s.subtask_id)
            if found is not None:
                return found
    return None


def _decomposition_depth(subtasks: list[Subtask]) -> int:
    """Longest dependency chain length in the decomposition DAG."""
    if not subtasks:
        return 0
    by_id = {s.subtask_id: s for s in subtasks}
    memo: dict[str, int] = {}

    def depth(sid: str, stack: frozenset[str]) -> int:
        if sid in memo:
            return memo[sid]
        if sid in stack:  # cycle guard
            return 0
        sub = by_id.get(sid)
        if sub is None or not sub.depends_on:
            memo[sid] = 1
            return 1
        d = 1 + max(depth(dep, stack | {sid}) for dep in sub.depends_on)
        memo[sid] = d
        return d

    return max(depth(s.subtask_id, frozenset()) for s in subtasks)


def _topology_shape(roster: list[RosterMember], edges: list[RoleEdge]) -> str:
    """Classify the role graph into a coarse shape bin."""
    n = len(roster)
    if n <= 1:
        return "single"
    if not edges:
        return "broadcast"
    out_degree: dict[str, int] = {}
    in_degree: dict[str, int] = {}
    for e in edges:
        out_degree[e.source_role_id] = out_degree.get(e.source_role_id, 0) + 1
        in_degree[e.target_role_id] = in_degree.get(e.target_role_id, 0) + 1
    # one hub fanning out to >=2 others (needs >=3 nodes to be a star)
    if n >= 3 and any(v >= n - 1 and v >= 2 for v in out_degree.values()):
        return "star"
    # every node has <=1 in and <=1 out -> a chain
    if all(v <= 1 for v in out_degree.values()) and all(v <= 1 for v in in_degree.values()):
        return "pipeline"
    if len(edges) >= n:
        return "mesh"
    return "tree"


__all__ = [
    "AccessList",
    "AdjudicationRule",
    "BehavioralDescriptors",
    "Lineage",
    "OrchestrationGenome",
    "RoleBudget",
    "RoleEdge",
    "RosterKind",
    "RosterMember",
    "StopCondition",
    "Subtask",
    "VerificationStep",
]
