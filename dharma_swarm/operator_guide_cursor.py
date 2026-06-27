"""Operator Guide Cursor — persistent Cursor-harness operator relay."""

from __future__ import annotations

from pathlib import Path

AGENT_UID = "operator_guide_cursor"
CALLSIGN = "operator-guide-cursor"
DISPLAY_NAME = "Operator Guide (Cursor)"
NATS_SUBJECT = "dharma.agent.operator_guide_cursor.inbox"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DHARMA_HOME = Path.home() / ".dharma"
ALIGNED_APEX_OBJECT = "semobj.sarathi"


def build_external_worker_registration(
    *,
    dharma_home: Path | str | None = None,
    repo_root: Path | str = REPO_ROOT,
):
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
    return ExternalRoamingWorker(
        agent_uid=AGENT_UID,
        callsign=CALLSIGN,
        display_name=DISPLAY_NAME,
        harness="cursor_ide",
        model_identity="cursor/composer-selected",
        department="command",
        role="cursor_apex_operator_relay",
        squad_id="operator_relay",
        team_id="dharma_swarm",
        endpoint=f"cursor://{AGENT_UID}/ide",
        mailbox=f"nats://{NATS_SUBJECT}",
        authority=ExternalAgentAuthority.EXTERNAL_WORKER_EVIDENCE_ONLY,
        autonomy_policy=AutonomyPolicy(
            mode="supervised_cursor_operator_relay",
            requires_approval=True,
            explicit_task_assignment_required=False,
        ),
        workspace_policy=WorkspacePolicy(
            sandbox_root=str(external_agent_sandbox_root(home) / AGENT_UID),
            repo_writes_allowed=False,
            canonical_dharma_dir_writes_allowed=False,
        ),
        memory_namespace=f"agent:{AGENT_UID}",
        trace_identity=f"trace:{AGENT_UID}",
        status=ExternalAgentStatus.REGISTERED,
        notes=(
            "Persistent Cursor-harness operator relay and teaching seat. "
            "Functionally equivalent to the reserved Sarathi apex holon within "
            "the Cursor environment only; does not claim semobj.sarathi. "
            "Mission: teach the operator, synthesize fleet truth, triage workspace "
            "sprawl, and dispatch bounded lower agents."
        ),
        registration_source="operator_request_2026_06_25_operator_guide_cursor",
        capabilities=(
            "operator_teaching",
            "feynman_explanation",
            "workspace_triage",
            "fleet_synthesis",
            "active_track_briefing",
            "worktree_orientation",
            "semantic_commons_translation",
            "agent_hierarchy_briefing",
            "mission_envelope_drafting",
            "bounded_worker_dispatch",
            "a2a_correspondence",
            "aerie_projection_read",
            "trans_chat_continuity",
        ),
        metadata={
            "operator": "AmitabhainArunachala/Dhyana",
            "title": "@OPERATOR_GUIDE",
            "operating_title": "Operator Guide (Cursor)",
            "surface": "Cursor IDE (persistent operator relay + teaching seat)",
            "primary_repo": str(repo),
            "default_operator_desk": str(repo),
            "aligned_apex_object": ALIGNED_APEX_OBJECT,
            "topology_note": (
                "This agent is the Cursor-harness equivalent of the reserved "
                "Sarathi apex holon. It relays toward semobj.sarathi but is not "
                "Sarathi."
            ),
            "d_level_target": "D3",
            "d_level_current": "D2_seed",
            "transport_preference": "nats_jetstream",
            "canonical_transport_subject": NATS_SUBJECT,
            "required_first_reads": (
                "make onboard output",
                "docs/ops/OPERATOR_GUIDE_CURSOR_ONBOARDING_MAP.md",
                "docs/agents/operator_guide_cursor/OPERATOR_GUIDE_CURSOR_CONTRACT.md",
                "docs/architecture/AGENT_HIERARCHY_MATURITY_MAP.md",
                "docs/governance/ACTIVE_TRACK.yaml",
            ),
            "operational_route": "docs/ops/OPERATOR_GUIDE_CURSOR_ONBOARDING_MAP.md",
            "orientation_route": "route.seat_operator_guide_cursor",
            "summon_phrase": "@OPERATOR_GUIDE",
            "summon_aliases": (
                "@operator_guide_cursor",
                "@CURSOR_GUIDE",
                "@cursor_guide",
            ),
            "summon_contract": (
                "Assume the operator_guide_cursor identity, run make onboard, load "
                "route.seat_operator_guide_cursor context, and answer as the "
                "operator's persistent Cursor relay. Teach in Feynman style when "
                "the operator is learning; brief fleet truth when executing. Do "
                "not claim to be semobj.sarathi. Do not merge, approve, push, "
                "mutate protected surfaces, or bypass governance without explicit "
                "operator authorization."
            ),
            "living_dock": str(home / "agents" / AGENT_UID),
            "dialogue_receipts": str(
                home / "agents" / AGENT_UID / "dialogue" / "conversation_receipts"
            ),
            "automatic_authority_inheritance": False,
        },
    )
