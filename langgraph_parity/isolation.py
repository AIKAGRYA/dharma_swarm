"""Per-agent domain and tool isolation for parity benchmarks."""

from __future__ import annotations

from dataclasses import dataclass

from dharma_swarm.langgraph_parity.state import AgentManifest
from dharma_swarm.langgraph_parity.tools import allowed_tool_names


@dataclass(frozen=True, slots=True)
class DomainPack:
    domain: str
    instructions: str
    tools: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "domain": self.domain,
            "instructions": self.instructions,
            "tools": list(self.tools),
        }


@dataclass(frozen=True, slots=True)
class ContextEnvelope:
    agent_name: str
    visible_domains: tuple[str, ...]
    instructions: tuple[str, ...]
    tools: tuple[str, ...]
    rejected_domains: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "agent_name": self.agent_name,
            "visible_domains": list(self.visible_domains),
            "instructions": list(self.instructions),
            "tools": list(self.tools),
            "rejected_domains": list(self.rejected_domains),
        }


DEFAULT_DISTRACTOR_DOMAINS: tuple[DomainPack, ...] = (
    DomainPack("research", "Inspect factual source snippets only.", ("search_notes",)),
    DomainPack("math", "Compute exact arithmetic and show compact work.", ("calculator",)),
    DomainPack("travel", "Plan trips, visas, and itineraries.", ("flight_lookup",)),
    DomainPack("legal", "Summarize legal risks without giving legal advice.", ("case_lookup",)),
    DomainPack("medical", "Triage health information without diagnosis.", ("symptom_lookup",)),
    DomainPack("finance", "Estimate budgets and financial scenarios.", ("budget_sheet",)),
    DomainPack("culinary", "Adapt recipes and pantry constraints.", ("recipe_search",)),
    DomainPack("code", "Inspect code snippets and test commands.", ("repo_search",)),
)


def default_domain_pack_map() -> dict[str, DomainPack]:
    return {pack.domain: pack for pack in DEFAULT_DISTRACTOR_DOMAINS}


def filter_agent_context(
    manifest: AgentManifest,
    all_agents: dict[str, AgentManifest],
    *,
    domain_packs: dict[str, DomainPack] | None = None,
    selected_domains: tuple[str, ...] = (),
    include_handoff_tools: bool = True,
) -> ContextEnvelope:
    packs = domain_packs or default_domain_pack_map()
    allowed_domains = {manifest.domain, *selected_domains}
    visible = tuple(domain for domain in packs if domain in allowed_domains)
    rejected = tuple(domain for domain in packs if domain not in allowed_domains)
    instructions = tuple(packs[domain].instructions for domain in visible)
    domain_tools: list[str] = []
    for domain in visible:
        domain_tools.extend(packs[domain].tools)
    handoff_tools = (
        allowed_tool_names(manifest, all_agents) if include_handoff_tools else ()
    )
    return ContextEnvelope(
        agent_name=manifest.name,
        visible_domains=visible,
        instructions=instructions,
        tools=tuple(domain_tools) + tuple(handoff_tools),
        rejected_domains=rejected,
    )


def semantic_memory_admission(
    manifest: AgentManifest,
    candidate_domains: tuple[str, ...],
    *,
    explicitly_selected_domains: tuple[str, ...] = (),
) -> dict[str, tuple[str, ...]]:
    """Simulate Semantic Commons/Memory Kernel domain admission."""

    accepted: list[str] = []
    rejected: list[str] = []
    explicit = set(explicitly_selected_domains)
    for domain in candidate_domains:
        if domain == manifest.domain or domain in explicit:
            accepted.append(domain)
        else:
            rejected.append(domain)
    return {"accepted": tuple(accepted), "rejected": tuple(rejected)}
