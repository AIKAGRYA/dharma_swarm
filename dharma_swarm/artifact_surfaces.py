"""Registry for brief, X-Ray, and proof-artifact surfaces.

The registry keeps similarly named artifacts from becoming parallel systems.
It is descriptive, not a router: each surface keeps its own implementation,
while this module records ownership, audience, and replacement boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactSurface:
    """One human or machine-facing artifact surface."""

    surface_id: str
    label: str
    role: str
    audience: str
    status: str
    owns: str
    python_api: str = ""
    output_pattern: str = ""
    may_read: tuple[str, ...] = ()
    wraps: tuple[str, ...] = ()
    must_not_replace: tuple[str, ...] = ()
    next_action: str = ""


@dataclass(frozen=True)
class SurfaceRegistryViolation:
    """A boundary problem in the artifact surface map."""

    surface_id: str
    detail: str


ARTIFACT_SURFACES: tuple[ArtifactSurface, ...] = (
    ArtifactSurface(
        surface_id="agent_role_briefings",
        label="Agent role briefings",
        role="prompt_context",
        audience="agents",
        status="active_prompt_fuel",
        owns="role identity and cognitive division-of-labor hints for spawned agents",
        python_api="dharma_swarm.daemon_config.ROLE_BRIEFINGS",
        may_read=("ecosystem_bridge", "signal_map"),
        must_not_replace=("insight_brief", "daily_operating_brief", "immune_mission_xray"),
        next_action="keep as agent context only; do not promote to user-facing truth",
    ),
    ArtifactSurface(
        surface_id="insight_brief",
        label="Daily Insight Brief",
        role="daily_private_brief",
        audience="dhyana",
        status="canonical",
        owns="private daily ontology-cited Outcome projection",
        python_api="dharma_swarm.insight_brief",
        output_pattern="~/dharma_briefs/<YYYY-MM-DD>-brief.md",
        may_read=("ontology_outcomes", "ontology_claims", "ontology_questions"),
        must_not_replace=("agent_role_briefings", "daily_operating_brief", "repo_xray", "immune_mission_xray"),
        next_action="harden feedback from human read/decision back into ontology or Shakti",
    ),
    ArtifactSurface(
        surface_id="operator_brief",
        label="Operator Brief PR57",
        role="daily_private_brief",
        audience="dhyana",
        status="parked",
        owns="historical alternate operator-brief experiment",
        output_pattern="disabled by DHARMA_OPERATOR_BRIEF_ENABLED",
        must_not_replace=("insight_brief",),
        next_action="remain parked unless explicitly promoted with a separate ontology contract",
    ),
    ArtifactSurface(
        surface_id="daily_operating_brief",
        label="Daily Operating Brief",
        role="operator_projection",
        audience="operator",
        status="projection",
        owns="operating-fact synthesis: AgentOps, Kaizen, burn, YDS, revenue",
        python_api="dharma_swarm.daily_operating_brief",
        may_read=("agentops", "kaizen_review", "human_yds", "burn_cost", "revenue"),
        must_not_replace=("insight_brief", "repo_xray", "immune_mission_xray"),
        next_action="use as an input to mission diagnostics, not as the canonical daily brief",
    ),
    ArtifactSurface(
        surface_id="repo_xray",
        label="Repo X-Ray",
        role="static_code_diagnostic",
        audience="engineer_or_buyer",
        status="active_evidence_surface",
        owns="static codebase risk, complexity, dependency, and hotspot evidence",
        python_api="dharma_swarm.xray",
        output_pattern="xray_report.md / xray_report.json",
        must_not_replace=("insight_brief", "daily_operating_brief", "proof_artifact"),
        next_action="feed evidence into Immune Mission X-Ray packets when code risk matters",
    ),
    ArtifactSurface(
        surface_id="immune_mission_xray",
        label="Immune Mission X-Ray",
        role="mission_trust_diagnostic",
        audience="founder_lab_or_system_owner",
        status="wrapper",
        owns="mission trust diagnosis: claims, evidence tiers, correction, permissions, rollback, next proof packet",
        python_api="dharma_swarm.immune_mission_xray",
        output_pattern="reports/immune_mission_xray_<date>_<slug>/",
        may_read=("repo_xray", "insight_brief", "daily_operating_brief", "proof_artifact"),
        wraps=("repo_xray", "check_claim_redlines", "proof_artifact_to_spec"),
        must_not_replace=("insight_brief", "daily_operating_brief", "repo_xray", "proof_artifact"),
        next_action="produce a ProofArtifact-bound packet; never become another generic brief",
    ),
    ArtifactSurface(
        surface_id="proof_artifact",
        label="ProofArtifact",
        role="causal_closure_packet",
        audience="system_human_witness",
        status="active_contract",
        owns="claim/evidence/gate/witness/challenge/correction/next-action binding",
        python_api="tools.build_protocol.proof_artifact_to_spec",
        output_pattern="proof_artifact_contract.json",
        may_read=("immune_mission_xray", "redline_preflight", "telos_reviews", "sabp_claims"),
        wraps=("dharma_build_plan", "dharma_build_seal", "darwin_shadow_apply"),
        must_not_replace=("insight_brief", "repo_xray", "daily_operating_brief"),
        next_action="remain the bridge into Build Protocol and Darwin shadow evolution",
    ),
)


def artifact_surface_map() -> dict[str, ArtifactSurface]:
    """Return surfaces keyed by stable ID."""

    return {surface.surface_id: surface for surface in ARTIFACT_SURFACES}


def canonical_daily_brief_surface() -> ArtifactSurface:
    """Return the one canonical daily private brief surface."""

    canonical = [
        surface
        for surface in ARTIFACT_SURFACES
        if surface.role == "daily_private_brief" and surface.status == "canonical"
    ]
    if len(canonical) != 1:
        raise ValueError(f"expected one canonical daily brief surface, found {len(canonical)}")
    return canonical[0]


def surfaces_by_role(role: str) -> tuple[ArtifactSurface, ...]:
    """Return all surfaces with a registry role."""

    return tuple(surface for surface in ARTIFACT_SURFACES if surface.role == role)


def validate_artifact_surface_registry() -> tuple[SurfaceRegistryViolation, ...]:
    """Check the registry for the overlap failures that caused confusion."""

    violations: list[SurfaceRegistryViolation] = []
    seen: set[str] = set()
    for surface in ARTIFACT_SURFACES:
        if surface.surface_id in seen:
            violations.append(
                SurfaceRegistryViolation(surface.surface_id, "duplicate surface_id")
            )
        seen.add(surface.surface_id)

    try:
        canonical_daily_brief_surface()
    except ValueError as exc:
        violations.append(SurfaceRegistryViolation("daily_private_brief", str(exc)))

    surfaces = artifact_surface_map()
    for surface in ARTIFACT_SURFACES:
        for replaced in surface.must_not_replace:
            if replaced not in surfaces:
                violations.append(
                    SurfaceRegistryViolation(
                        surface.surface_id,
                        f"must_not_replace references unknown surface: {replaced}",
                    )
                )
        for wrapped in surface.wraps:
            if wrapped in surfaces and wrapped not in surface.must_not_replace:
                continue
            if wrapped not in surfaces and wrapped not in {
                "check_claim_redlines",
                "proof_artifact_to_spec",
                "dharma_build_plan",
                "dharma_build_seal",
                "darwin_shadow_apply",
            }:
                violations.append(
                    SurfaceRegistryViolation(
                        surface.surface_id,
                        f"wraps references unknown surface or adapter: {wrapped}",
                    )
                )

    immune = surfaces.get("immune_mission_xray")
    if immune is not None:
        required_wrappers = {"repo_xray", "check_claim_redlines", "proof_artifact_to_spec"}
        missing = required_wrappers.difference(immune.wraps)
        if missing:
            violations.append(
                SurfaceRegistryViolation(
                    "immune_mission_xray",
                    "missing wrapper binding(s): " + ", ".join(sorted(missing)),
                )
            )
        if "insight_brief" not in immune.must_not_replace:
            violations.append(
                SurfaceRegistryViolation(
                    "immune_mission_xray",
                    "must not replace the canonical Daily Insight Brief",
                )
            )

    return tuple(violations)
