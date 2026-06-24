"""Stage execution — the spine path (Slice A).

Each stage is dispatched through ``spine.invoke_agent()`` — the swarm's single
blessed dispatch path — producing one ``EvidenceReceipt``. Context is bounded to
the stage's declared Inputs (the token firewall); the agent role resolves against
the existing ``skills/`` registry; stage output is handed to the next stage via
``handoff.py``.

Why route a "mere file pipeline" through invoke_agent: bypassing it would create
exactly the bypass debt the sibling spine-adoption track is draining to zero, and
would emit no receipt. Going through the spine means this slice raises
substrate-nativeness as a side effect instead of leaking it.
"""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.fs_substrate.stage_contracts import StageContract, StageWorkspace
from dharma_swarm.handoff import Artifact, ArtifactType, HandoffProtocol
from dharma_swarm.spine.invoke import AgentInvoker, invoke_agent
from dharma_swarm.spine.receipt import EvidenceReceipt
from dharma_swarm.spine.routing import RoutingDecision

# The 2k-8k token band where models perform best (ICM). Applied as a char cap
# on the bounded-Inputs context. Memory-derived inputs (a later refinement)
# would route through MemoryContextBudget instead; plain files use this cap.
_INPUT_CHAR_BUDGET = 8000


def _extract_section(text: str, scope: str) -> str:
    """Return only the named markdown section if scope names one, else all text."""
    scope = (scope or "full").strip().strip('"')
    if scope.lower() in ("", "full"):
        return text
    target = scope.lower().lstrip("#").strip()
    out: list[str] = []
    capturing = False
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            heading = line.lstrip("#").strip().lower()
            if capturing:
                break
            if target in heading:
                capturing = True
                out.append(line)
                continue
        elif capturing:
            out.append(line)
    return "\n".join(out) if out else text


def assemble_input_context(
    contract: StageContract, *, char_budget: int = _INPUT_CHAR_BUDGET
) -> str:
    """Build the bounded context for a stage from ONLY its Inputs table.

    Nothing outside the declared Inputs enters the window — this is the token
    firewall the whole power is about. Missing input files are reported inline
    rather than silently skipped.
    """
    base = Path(contract.path).parent
    parts: list[str] = []
    used = 0
    for inp in contract.inputs:
        if not inp.location:
            continue
        target = (base / inp.location).resolve()
        files = (
            sorted(target.glob("*")) if target.is_dir() else [target]
        )
        for f in files:
            if not f.is_file():
                parts.append(f"<!-- missing input: {inp.location} ({inp.why}) -->")
                continue
            section = _extract_section(f.read_text(encoding="utf-8"), inp.scope)
            header = f"\n### Input: {inp.source or f.name} — {inp.why}\n"
            chunk = header + section
            if used + len(chunk) > char_budget:
                parts.append(chunk[: max(0, char_budget - used)] + "\n... [truncated]")
                return "\n".join(parts)
            parts.append(chunk)
            used += len(chunk)
    return "\n".join(parts)


def _resolve_agent(role: str | None) -> tuple[str, str, str, str]:
    """Resolve a stage's agent role against the skills/ registry.

    Returns (agent_id, provider, model, system_prompt). Falls back gracefully to
    the bare role name if the skill is not found — convergence, not a hard dep.
    """
    if not role:
        return ("generalist", "", "", "")
    try:
        from dharma_swarm.skills import SkillRegistry

        skill = SkillRegistry().get(role)
        if skill is not None:
            return (skill.name, skill.provider, skill.model, getattr(skill, "description", ""))
    except Exception:
        pass
    return (role, "", "", "")


async def dispatch_stage(
    contract: StageContract,
    *,
    invoker: AgentInvoker,
    context_id: str = "",
    char_budget: int = _INPUT_CHAR_BUDGET,
) -> EvidenceReceipt:
    """Dispatch one stage through the spine, returning its EvidenceReceipt.

    Stage provenance (stage_id + contract hash) rides on the RoutingDecision so
    the canonical receipt joins back to it via ``routing_decision_id`` — the
    read-models-project-truth doctrine: we annotate the projection, we do not
    mint a second receipt.
    """
    agent_id, provider, model, _sys = _resolve_agent(contract.agent_role)
    context_text = assemble_input_context(contract, char_budget=char_budget)

    routing = RoutingDecision(
        agent_id=agent_id,
        provider=provider,
        model=model,
        reason=f"fs_substrate stage {contract.stage_id}",
        router_name="fs_substrate.stage",
        context_id=context_id,
        task_id=contract.stage_id,
        attributes={
            "stage_id": contract.stage_id,
            "stage_contract_sha256": contract.contract_sha256,
            "stage_title": contract.title,
        },
    )
    task: dict[str, object] = {
        "id": contract.stage_id,
        "title": contract.title or contract.stage_id,
        "description": "\n".join(contract.process),
        "context": context_text,
        "stage_id": contract.stage_id,
        "stage_contract_sha256": contract.contract_sha256,
    }
    return await invoke_agent(
        task, agent_id=agent_id, context_id=context_id, routing=routing, invoker=invoker
    )


async def run_workspace(
    ws: StageWorkspace,
    *,
    invoker: AgentInvoker,
    context_id: str = "",
    handoff: HandoffProtocol | None = None,
) -> list[EvidenceReceipt]:
    """Run every stage in order, handing each stage's output to the next.

    Slice A executes stages in declared order (the workspace is already sorted by
    the derived DAG). Each transition emits a typed Handoff so the stage chain is
    visible to the rest of the organism, not just to the filesystem.
    """
    handoff = handoff or HandoffProtocol()
    receipts: list[EvidenceReceipt] = []
    prev: StageContract | None = None
    for contract in ws.stages:
        receipt = await dispatch_stage(
            contract, invoker=invoker, context_id=context_id
        )
        receipts.append(receipt)
        if prev is not None:
            await handoff.create_handoff(
                from_agent=prev.agent_role or prev.stage_id,
                to_agent=contract.agent_role or contract.stage_id,
                task_context=f"{prev.stage_id} -> {contract.stage_id}",
                artifacts=[
                    Artifact(
                        artifact_type=ArtifactType.CONTEXT,
                        content=", ".join(o.location for o in prev.outputs),
                        summary=f"outputs of stage {prev.stage_id}",
                        metadata={"stage_id": prev.stage_id},
                    )
                ],
            )
        prev = contract
    return receipts
