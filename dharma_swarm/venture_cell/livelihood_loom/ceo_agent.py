"""Persistent Livelihood Loom CEO identity and registration helpers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from dharma_swarm.agent_registry import AgentRegistry
from dharma_swarm.venture_cell.domain_ceo import load_domain_ceo_contract


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DHARMA_HOME = Path.home() / ".dharma"

AGENT_ID = "livelihood_loom_ceo"
CALLSIGN = "livelihood-loom-ceo"
DISPLAY_NAME = "Livelihood Loom CEO"
NATS_SUBJECT = "dharma.a2a.livelihood-loom-ceo"
ROLE = "livelihood_loom_ceo"
DEPARTMENT = "venture_cell"
SQUAD_ID = "livelihood_loom"
TEAM_ID = "dharma_swarm"

REPO_AGENT_HOME = Path("docs/agents/livelihood_loom_ceo")
SEED_FILE = REPO_AGENT_HOME / "agent.seed.yaml"
SOUL_FILE = REPO_AGENT_HOME / "SOUL.md"
PROTOCOLS_FILE = REPO_AGENT_HOME / "PROTOCOLS.md"
WAKE_CONTEXT_FILE = REPO_AGENT_HOME / "WAKE_CONTEXT.md"
CHARTER_FILE = Path("dharma_swarm/venture_cell/livelihood_loom/charter.yaml")
ORG_FILE = Path("dharma_swarm/venture_cell/livelihood_loom/org.yaml")
DEFAULT_RECEIPT_DIR = Path("reports/livelihood_loom/bootstrap")


def build_system_prompt(*, repo_root: Path | str = REPO_ROOT) -> str:
    """Build the AgentRegistry prompt for the CEO seat."""
    repo = Path(repo_root)
    return "\n".join(
        [
            "You are Livelihood Loom CEO, a persistent governed VentureCell identity.",
            "",
            "Mandate:",
            "- Increase real livelihood opportunity for informal workers and micro-businesses.",
            "- Serve jagat_kalyan first; Dharma Capital may receive only read-only aggregated signals.",
            "- Convert public research into safe enablement packets, proofs, and approval-gated actions.",
            "",
            "Authority boundary:",
            "- You may plan missions, spawn bounded internal lanes, score public candidates, and write receipts.",
            "- You may draft external actions only through the human-governed approval queue.",
            "- You may not contact people, publish claims, move funds, use private data, or make capital decisions.",
            "- You may not weaken AHIMSA, SATYA, telos, consent, privacy, or non-extraction gates.",
            "",
            "Operating inputs:",
            f"- Charter: {repo / CHARTER_FILE}",
            f"- Org map: {repo / ORG_FILE}",
            f"- Agent seed: {repo / SEED_FILE}",
            f"- Wake context: {repo / WAKE_CONTEXT_FILE}",
            "",
            "Definition of progress:",
            "- Every mission step leaves a replayable receipt.",
            "- Public proofs are aggregate, non-sensitive, and source-backed.",
            "- External-world action remains drafted until human_governor approval and execution receipts exist.",
        ]
    )


def build_runtime_fields(
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    repo_root: Path | str = REPO_ROOT,
) -> list[dict[str, Any]]:
    """Runtime fields that make the CEO identity tunable and inspectable."""
    home = Path(dharma_home).expanduser()
    repo = Path(repo_root)
    contract = _load_contract_for_metadata(repo)
    return [
        {
            "name": "system_prompt",
            "path": "system_prompt",
            "value_type": "str",
            "current_value": build_system_prompt(repo_root=repo),
        },
        {
            "name": "authority_floor",
            "path": "metadata['authority_floor']",
            "value_type": "str",
            "current_value": "sandbox_write_human_approved_external_actions",
        },
        {
            "name": "cell_id",
            "path": "metadata['cell_id']",
            "value_type": "str",
            "current_value": contract.cell_id,
        },
        {
            "name": "mission_id",
            "path": "metadata['mission_id']",
            "value_type": "str",
            "current_value": contract.mission_id,
        },
        {
            "name": "budget_policy",
            "path": "metadata['budget_policy']",
            "value_type": "dict",
            "current_value": contract.budget_policy.__dict__,
        },
        {
            "name": "external_action_policy",
            "path": "metadata['external_action_policy']",
            "value_type": "dict",
            "current_value": {
                "external_action_mode": contract.external_action_policy.external_action_mode,
                "approval_required_for": list(
                    contract.external_action_policy.approval_required_for
                ),
                "forbidden_actions": list(
                    contract.external_action_policy.forbidden_actions
                ),
            },
        },
        {
            "name": "proof_contract",
            "path": "metadata['proof_contract']",
            "value_type": "list",
            "current_value": list(contract.proof_contract),
        },
        {
            "name": "charter_path",
            "path": "metadata['charter_path']",
            "value_type": "str",
            "current_value": str(repo / CHARTER_FILE),
        },
        {
            "name": "registration_command",
            "path": "metadata['registration_command']",
            "value_type": "str",
            "current_value": (
                "python -m dharma_swarm.venture_cell.livelihood_loom.cli "
                "register-ceo --json"
            ),
        },
        {
            "name": "safe_bootstrap_command",
            "path": "metadata['safe_bootstrap_command']",
            "value_type": "str",
            "current_value": (
                "python -m dharma_swarm.venture_cell.livelihood_loom.cli "
                "run-bootstrap --json"
            ),
        },
        {
            "name": "cultivation_cycle_command",
            "path": "metadata['cultivation_cycle_command']",
            "value_type": "str",
            "current_value": (
                "python -m dharma_swarm.venture_cell.livelihood_loom.cli "
                "run-cultivation-cycle --json"
            ),
        },
        {
            "name": "internal_lane_commands",
            "path": "metadata['internal_lane_commands']",
            "value_type": "list",
            "current_value": [
                "top-50",
                "safety-review",
                "build-packets",
                "draft-demand",
                "status --json",
                "run-cultivation-cycle --json",
            ],
        },
        {
            "name": "memory_namespace",
            "path": "metadata['memory_namespace']",
            "value_type": "str",
            "current_value": f"agent:{AGENT_ID}",
        },
        {
            "name": "a2a_subject",
            "path": "metadata['a2a_subject']",
            "value_type": "str",
            "current_value": NATS_SUBJECT,
        },
        {
            "name": "sandbox_receipts",
            "path": "metadata['sandbox_receipts']",
            "value_type": "str",
            "current_value": str(home / "external_agents" / AGENT_ID / "receipts"),
        },
    ]


def _load_contract_for_metadata(repo_root: Path):
    charter_path = repo_root / CHARTER_FILE
    if not charter_path.exists():
        charter_path = Path(__file__).resolve().parent / "charter.yaml"
    return load_domain_ceo_contract(charter_path)


def build_external_worker_registration(
    *,
    dharma_home: Path | str | None = None,
    repo_root: Path | str = REPO_ROOT,
):
    """Construct the Stage-1 registration record for the CEO identity."""
    from dharma_swarm.external_agent_registration import (
        AutonomyPolicy,
        ExternalAgentAuthority,
        ExternalAgentStatus,
        ExternalRoamingWorker,
        WorkspacePolicy,
        external_agent_sandbox_root,
    )

    home = Path(dharma_home).expanduser() if dharma_home else DEFAULT_DHARMA_HOME
    repo = Path(repo_root)
    contract = _load_contract_for_metadata(repo)
    return ExternalRoamingWorker(
        agent_uid=AGENT_ID,
        callsign=CALLSIGN,
        display_name=DISPLAY_NAME,
        harness="codex",
        model_identity="codex",
        department=DEPARTMENT,
        role=ROLE,
        squad_id=SQUAD_ID,
        team_id=TEAM_ID,
        endpoint="pending://manual",
        mailbox=f"nats://{NATS_SUBJECT}",
        authority=ExternalAgentAuthority.SANDBOX_WRITE,
        autonomy_policy=AutonomyPolicy(
            mode="manual",
            requires_approval=True,
            explicit_task_assignment_required=True,
        ),
        workspace_policy=WorkspacePolicy(
            sandbox_root=str(external_agent_sandbox_root(home) / AGENT_ID),
            repo_writes_allowed=False,
            canonical_dharma_dir_writes_allowed=False,
        ),
        memory_namespace=f"agent:{AGENT_ID}",
        trace_identity=f"trace:{AGENT_ID}",
        status=ExternalAgentStatus.REGISTERED,
        is_returning_historical_embodiment=False,
        notes=(
            "Persistent CEO identity for the Livelihood Loom VentureCell. "
            "It can coordinate bounded internal lanes, ingest public enabler "
            "research, score candidates, write receipts, and draft approval-gated "
            "external actions. It cannot contact people, publish, spend, move "
            "funds, run live accounts, or make capital decisions without the "
            "human_governor approval path."
        ),
        registration_source="livelihood_loom_ceo_registration",
        capabilities=(
            "venture_cell_strategy",
            "informal_economy_research",
            "public_candidate_scoring",
            "approval_gated_action_drafting",
            "receipt_backed_bootstrap_execution",
            "jagat_kalyan_alignment_review",
        ),
        metadata={
            "cell_id": contract.cell_id,
            "fractal_cell_id": "livelihood-loom",
            "mission_id": contract.mission_id,
            "human_governor": contract.human_governor,
            "parent_plane": contract.parent_plane,
            "capital_boundary": contract.capital_boundary,
            "first_metric": contract.first_metric,
            "allowed_agent_roles": list(contract.allowed_agent_roles),
            "allowed_internal_tools": list(contract.allowed_internal_tools),
            "approval_required_for": list(
                contract.external_action_policy.approval_required_for
            ),
            "forbidden_actions": list(contract.external_action_policy.forbidden_actions),
            "proof_contract": list(contract.proof_contract),
            "repo_home": str(repo / REPO_AGENT_HOME),
            "seed_path": str(repo / SEED_FILE),
            "soul_file": str(repo / SOUL_FILE),
            "protocols_file": str(repo / PROTOCOLS_FILE),
            "wake_context": str(repo / WAKE_CONTEXT_FILE),
            "charter": str(repo / CHARTER_FILE),
            "org_map": str(repo / ORG_FILE),
            "manifest_agent_id": AGENT_ID,
            "nats_subject": NATS_SUBJECT,
            "nats_runtime_status": "declared_not_started",
            "a2a_transport_status": "card_registered_only_after_onboarding",
            "authority_boundary": "sandbox_write_human_approved_external_actions",
            "external_authority": "none_without_approval",
            "external_action_mode": "human_approved_only",
            "no_provider_secret_access": True,
            "no_autonomous_external_action": True,
            "no_autonomous_capital_decision": True,
            "first_receipt_dir": str(repo / DEFAULT_RECEIPT_DIR),
            "cultivation_cycle_command": (
                "python -m dharma_swarm.venture_cell.livelihood_loom.cli "
                "run-cultivation-cycle --json"
            ),
            "internal_lane_commands": [
                "top-50",
                "safety-review",
                "build-packets",
                "draft-demand",
                "status --json",
                "run-cultivation-cycle --json",
            ],
        },
    )


async def register_livelihood_loom_ceo(
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    repo_root: Path | str = REPO_ROOT,
    agents_dir: Path | str | None = None,
    write_canonical_onboarding: bool = True,
) -> dict[str, Any]:
    """Register the CEO in both external onboarding and the AgentRegistry."""
    from dharma_swarm.external_agent_registration import register_external_worker

    home = Path(dharma_home).expanduser()
    repo = Path(repo_root)
    worker = build_external_worker_registration(dharma_home=home, repo_root=repo)
    external_result = await register_external_worker(
        worker,
        dharma_home=home,
        write_canonical_onboarding=write_canonical_onboarding,
    )

    registry = AgentRegistry(
        agents_dir=Path(agents_dir).expanduser()
        if agents_dir is not None
        else home / "ginko" / "agents"
    )
    identity = registry.register_agent(
        AGENT_ID,
        ROLE,
        "local_control_plane",
        build_system_prompt(repo_root=repo),
        runtime_fields=build_runtime_fields(dharma_home=home, repo_root=repo),
    )

    return {
        "agent_uid": AGENT_ID,
        "callsign": CALLSIGN,
        "external_registration": external_result,
        "agent_registry_identity": identity,
        "agent_registry_path": str(registry.agents_dir / AGENT_ID / "identity.json"),
        "runtime_fields_path": str(registry.agents_dir / AGENT_ID / "runtime_fields.json"),
    }


def register_livelihood_loom_ceo_sync(
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    repo_root: Path | str = REPO_ROOT,
    agents_dir: Path | str | None = None,
    write_canonical_onboarding: bool = True,
) -> dict[str, Any]:
    """Synchronous wrapper for CLI and local bootstrap execution."""
    return asyncio.run(
        register_livelihood_loom_ceo(
            dharma_home=dharma_home,
            repo_root=repo_root,
            agents_dir=agents_dir,
            write_canonical_onboarding=write_canonical_onboarding,
        )
    )


__all__ = [
    "AGENT_ID",
    "CALLSIGN",
    "DEFAULT_DHARMA_HOME",
    "DEFAULT_RECEIPT_DIR",
    "DISPLAY_NAME",
    "NATS_SUBJECT",
    "ROLE",
    "build_external_worker_registration",
    "build_runtime_fields",
    "build_system_prompt",
    "register_livelihood_loom_ceo",
    "register_livelihood_loom_ceo_sync",
]
