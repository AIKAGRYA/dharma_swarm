"""External-worker registration builder for the Cybernetics Codex steward."""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.cybernetics_codex import (
    A2A_INBOX_ROUTE,
    AGENT_ID,
    CALLSIGN,
    CONTEXT_ENGINEERING_FILE,
    DEFAULT_STATE_DIR,
    NATS_SUBJECT,
    REPO_AGENT_HOME,
    REPO_ROOT,
    SEED_FILE,
    SOUL_FILE,
)


def build_external_worker_registration(
    *,
    dharma_home: Path | str | None = None,
    repo_root: Path | str = REPO_ROOT,
):
    """Construct the Stage-1 registration record for the steward."""
    from dharma_swarm.external_agent_registration import (
        AutonomyPolicy,
        ExternalAgentAuthority,
        ExternalAgentStatus,
        ExternalRoamingWorker,
        WorkspacePolicy,
        external_agent_sandbox_root,
    )

    home = Path(dharma_home) if dharma_home else DEFAULT_STATE_DIR
    repo = Path(repo_root)
    return ExternalRoamingWorker(
        agent_uid=AGENT_ID,
        callsign=CALLSIGN,
        display_name="Cybernetics Codex Steward",
        harness="codex",
        model_identity="codex",
        department="cybernetics",
        role="closure_ledger_steward",
        squad_id="loop_closure",
        team_id="dharma_swarm",
        endpoint="pending://manual",
        mailbox=f"nats://{NATS_SUBJECT}",
        authority=ExternalAgentAuthority.EXTERNAL_WORKER_EVIDENCE_ONLY,
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
            "Read-only cybernetic loop closure steward. Evidence-only: audits "
            "loop closure claims, One Wire invariants, provider health receipts, "
            "and VSM/cybernetic stewardship surfaces. No provider calls, source "
            "writes, dispatch, PR approval, spend, or live external account action."
        ),
        registration_source="cybernetics_codex_registration",
        capabilities=(
            "cybernetic_loop_audit",
            "closure_ledger",
            "vsm_mapping",
            "one_wire_guardian_review",
            "receipt_integrity",
            "context_engineering",
        ),
        metadata={
            "repo_home": str(repo / REPO_AGENT_HOME),
            "seed_path": str(repo / SEED_FILE),
            "soul_file": str(repo / SOUL_FILE),
            "context_engineering_desk": str(repo / CONTEXT_ENGINEERING_FILE),
            "charter": str(repo / "docs/ops/CYBERNETICS_CODEX.md"),
            "manifest_agent_id": AGENT_ID,
            "a2a_route": A2A_INBOX_ROUTE,
            "nats_subject": NATS_SUBJECT,
            "nats_runtime_status": "declared_not_started",
            "a2a_transport_status": "card_registered_only_after_onboarding",
            "authority_boundary": "external_worker_evidence_only",
            "no_provider_calls": True,
            "no_autonomous_dispatch": True,
            "one_wire_invariant": (
                "internal artifacts never touch archive fitness; only "
                "countersigned external acted receipts above quorum do"
            ),
        },
    )
