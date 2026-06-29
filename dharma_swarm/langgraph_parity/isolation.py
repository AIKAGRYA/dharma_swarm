"""Per-agent domain and tool isolation for deterministic parity harnesses."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from dharma_swarm.langgraph_parity.tools import transfer_tool_name


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A deterministic tool descriptor exposed to an isolated agent view."""

    name: str
    domain: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "domain": self.domain,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class DomainPack:
    """Instructions and tools for one distractor benchmark domain."""

    domain: str
    agent_name: str
    instructions: str
    tools: tuple[ToolSpec, ...]
    keywords: tuple[str, ...] = field(default_factory=tuple)

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(tool.name for tool in self.tools)

    def to_dict(self) -> dict[str, object]:
        return {
            "domain": self.domain,
            "agent_name": self.agent_name,
            "instructions": self.instructions,
            "tools": [tool.to_dict() for tool in self.tools],
            "keywords": list(self.keywords),
        }


@dataclass(frozen=True, slots=True)
class MemoryFact:
    """Simulated Memory Kernel item with an owning domain."""

    domain: str
    content: str
    source: str = "memory_kernel"

    def to_dict(self) -> dict[str, str]:
        return {
            "domain": self.domain,
            "content": self.content,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class AdmissionTrace:
    """What the isolation policy admitted and rejected for one agent view."""

    selected_domains: tuple[str, ...]
    requested_domains: tuple[str, ...]
    admitted_domains: tuple[str, ...]
    rejected_domains: tuple[str, ...]

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "selected_domains": list(self.selected_domains),
            "requested_domains": list(self.requested_domains),
            "admitted_domains": list(self.admitted_domains),
            "rejected_domains": list(self.rejected_domains),
        }


@dataclass(frozen=True, slots=True)
class AgentIsolationView:
    """The complete tool/instruction surface visible to one agent turn."""

    agent_name: str
    domain: str
    instructions: tuple[str, ...]
    tools: tuple[ToolSpec, ...]
    handoff_tools: tuple[ToolSpec, ...]
    memory_facts: tuple[MemoryFact, ...]
    admission: AdmissionTrace

    @property
    def visible_domains(self) -> tuple[str, ...]:
        domains: list[str] = []
        for tool in self.tools:
            if tool.domain != "handoff" and tool.domain not in domains:
                domains.append(tool.domain)
        for fact in self.memory_facts:
            if fact.domain not in domains:
                domains.append(fact.domain)
        return tuple(domains)

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(tool.name for tool in self.tools)

    @property
    def instruction_text(self) -> str:
        return "\n".join(self.instructions)

    def to_dict(self) -> dict[str, object]:
        return {
            "agent_name": self.agent_name,
            "domain": self.domain,
            "instructions": list(self.instructions),
            "tools": [tool.to_dict() for tool in self.tools],
            "handoff_tools": [tool.to_dict() for tool in self.handoff_tools],
            "memory_facts": [fact.to_dict() for fact in self.memory_facts],
            "admission": self.admission.to_dict(),
        }


class SimulatedSemanticCommons:
    """Noisy domain-pack retriever used to test admission filtering."""

    def __init__(self, packs: Sequence[DomainPack], *, return_all: bool = True) -> None:
        self._packs = tuple(packs)
        self.return_all = return_all

    def retrieve(self, prompt: str) -> tuple[DomainPack, ...]:
        if self.return_all:
            return self._packs

        lowered = prompt.lower()
        matched = [
            pack
            for pack in self._packs
            if any(keyword.lower() in lowered for keyword in pack.keywords)
        ]
        return tuple(matched)


class SimulatedMemoryKernel:
    """Noisy memory retriever used to test domain admission filtering."""

    def __init__(self, facts: Sequence[MemoryFact]) -> None:
        self._facts = tuple(facts)

    @classmethod
    def from_packs(cls, packs: Sequence[DomainPack]) -> "SimulatedMemoryKernel":
        return cls(
            tuple(
                MemoryFact(
                    domain=pack.domain,
                    content=(
                        f"{pack.domain} standing memory is reserved for "
                        f"{pack.agent_name} when that domain is selected."
                    ),
                )
                for pack in packs
            )
        )

    def retrieve(self, _prompt: str) -> tuple[MemoryFact, ...]:
        return self._facts


class IsolationPolicy:
    """Build strict per-agent views from noisy commons and memory candidates."""

    def __init__(
        self,
        packs: Sequence[DomainPack],
        *,
        allowed_handoffs: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        if not packs:
            raise ValueError("at least one domain pack is required")

        self.packs = tuple(packs)
        self._pack_by_domain = _unique_by(self.packs, "domain")
        self._pack_by_agent = _unique_by(self.packs, "agent_name")
        self.domains = tuple(pack.domain for pack in self.packs)
        self.agent_names = tuple(pack.agent_name for pack in self.packs)
        self._validate_tools()
        self._allowed_handoffs = self._normalize_handoffs(allowed_handoffs or {})

    def pack_for_domain(self, domain: str) -> DomainPack:
        try:
            return self._pack_by_domain[domain]
        except KeyError as exc:
            raise ValueError(f"unknown domain: {domain!r}") from exc

    def pack_for_agent(self, agent_name: str) -> DomainPack:
        try:
            return self._pack_by_agent[agent_name]
        except KeyError as exc:
            raise ValueError(f"unknown agent: {agent_name!r}") from exc

    def agent_for_domain(self, domain: str) -> str:
        return self.pack_for_domain(domain).agent_name

    def domain_for_agent(self, agent_name: str) -> str:
        return self.pack_for_agent(agent_name).domain

    def allowed_targets(self, agent_name: str) -> tuple[str, ...]:
        self.pack_for_agent(agent_name)
        return self._allowed_handoffs.get(agent_name, ())

    def handoff_tools_for_agent(self, agent_name: str) -> tuple[ToolSpec, ...]:
        self.pack_for_agent(agent_name)
        return tuple(
            ToolSpec(
                name=transfer_tool_name(target),
                domain="handoff",
                description=f"Transfer active work from {agent_name} to {target}.",
            )
            for target in self.allowed_targets(agent_name)
        )

    def prepare_agent_view(
        self,
        *,
        agent_name: str,
        prompt: str,
        selected_domains: Sequence[str] | None = None,
        semantic_commons: SimulatedSemanticCommons | None = None,
        memory_kernel: SimulatedMemoryKernel | None = None,
    ) -> AgentIsolationView:
        pack = self.pack_for_agent(agent_name)
        selected = self._normalize_selected_domains(selected_domains, default=pack.domain)
        selected_set = set(selected)

        semantic_candidates = (
            semantic_commons.retrieve(prompt) if semantic_commons is not None else ()
        )
        memory_candidates = (
            memory_kernel.retrieve(prompt) if memory_kernel is not None else ()
        )
        requested_domains = _ordered_unique(
            [candidate.domain for candidate in semantic_candidates]
            + [candidate.domain for candidate in memory_candidates]
        )

        domain_is_selected = pack.domain in selected_set
        admitted_packs = (pack,) if domain_is_selected else ()
        instructions = tuple(admitted.instructions for admitted in admitted_packs)
        tools = tuple(tool for admitted in admitted_packs for tool in admitted.tools)
        admitted_memory = tuple(
            fact
            for fact in memory_candidates
            if fact.domain == pack.domain and fact.domain in selected_set
        )
        handoff_tools = self.handoff_tools_for_agent(agent_name)
        admitted_domains = (pack.domain,) if domain_is_selected else ()
        rejected_domains = tuple(
            domain
            for domain in requested_domains
            if domain not in admitted_domains
        )

        return AgentIsolationView(
            agent_name=agent_name,
            domain=pack.domain,
            instructions=instructions,
            tools=tools + handoff_tools,
            handoff_tools=handoff_tools,
            memory_facts=admitted_memory,
            admission=AdmissionTrace(
                selected_domains=selected,
                requested_domains=requested_domains,
                admitted_domains=admitted_domains,
                rejected_domains=rejected_domains,
            ),
        )

    def _normalize_selected_domains(
        self,
        selected_domains: Sequence[str] | None,
        *,
        default: str,
    ) -> tuple[str, ...]:
        domains = tuple(selected_domains or (default,))
        if not domains:
            raise ValueError("at least one selected domain is required")
        unknown = [domain for domain in domains if domain not in self._pack_by_domain]
        if unknown:
            raise ValueError(f"unknown selected domains: {unknown!r}")
        return _ordered_unique(domains)

    def _normalize_handoffs(
        self,
        allowed_handoffs: Mapping[str, Sequence[str]],
    ) -> dict[str, tuple[str, ...]]:
        normalized: dict[str, tuple[str, ...]] = {}
        for source in self.agent_names:
            raw_targets = tuple(allowed_handoffs.get(source, ()))
            unknown = [
                target for target in raw_targets if target not in self._pack_by_agent
            ]
            if unknown:
                raise ValueError(
                    f"unknown handoff targets for {source!r}: {unknown!r}"
                )
            normalized[source] = tuple(
                target
                for target in self.agent_names
                if target in raw_targets and target != source
            )
        return normalized

    def _validate_tools(self) -> None:
        tool_names: set[str] = set()
        for pack in self.packs:
            if not pack.instructions.strip():
                raise ValueError(f"domain pack {pack.domain!r} has empty instructions")
            if not pack.tools:
                raise ValueError(f"domain pack {pack.domain!r} has no tools")
            for tool in pack.tools:
                if tool.domain != pack.domain:
                    raise ValueError(
                        f"tool {tool.name!r} domain {tool.domain!r} does not "
                        f"match pack domain {pack.domain!r}"
                    )
                if tool.name in tool_names:
                    raise ValueError(f"duplicate tool name: {tool.name!r}")
                tool_names.add(tool.name)


def collect_isolation_failures(view: AgentIsolationView) -> tuple[str, ...]:
    """Return stable failure classes for any visible cross-domain leakage."""

    failures: list[str] = []
    for tool in view.tools:
        if tool.domain not in {view.domain, "handoff"}:
            failures.append("irrelevant_tool_visible")
            break
    if any(fact.domain != view.domain for fact in view.memory_facts):
        failures.append("irrelevant_memory_visible")
    if any(domain != view.domain for domain in view.visible_domains):
        failures.append("irrelevant_domain_visible")
    if failures:
        failures.append("isolation_leak")
    return tuple(_ordered_unique(failures))


def default_distractor_packs() -> tuple[DomainPack, ...]:
    from dharma_swarm.langgraph_parity.isolation_defaults import (
        default_distractor_packs as _default_distractor_packs,
    )

    return _default_distractor_packs()


def default_isolation_policy() -> IsolationPolicy:
    from dharma_swarm.langgraph_parity.isolation_defaults import (
        default_isolation_policy as _default_isolation_policy,
    )

    return _default_isolation_policy()


def default_semantic_commons() -> SimulatedSemanticCommons:
    from dharma_swarm.langgraph_parity.isolation_defaults import (
        default_semantic_commons as _default_semantic_commons,
    )

    return _default_semantic_commons()


def default_memory_kernel() -> SimulatedMemoryKernel:
    from dharma_swarm.langgraph_parity.isolation_defaults import (
        default_memory_kernel as _default_memory_kernel,
    )

    return _default_memory_kernel()


def _unique_by(packs: Sequence[DomainPack], attr: str) -> dict[str, DomainPack]:
    values: dict[str, DomainPack] = {}
    for pack in packs:
        key = getattr(pack, attr)
        if key in values:
            raise ValueError(f"duplicate domain pack {attr}: {key!r}")
        values[key] = pack
    return values


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return tuple(unique)
