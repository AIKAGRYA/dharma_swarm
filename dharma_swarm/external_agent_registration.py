"""Stage-1 external roaming worker registration.

This module is a thin, narrowly-scoped layer over
``dharma_swarm.roaming_onboarding`` that adds:

- An explicit ``ExternalAgentAuthority`` ladder, with the lowest rung
  ``EXTERNAL_WORKER_EVIDENCE_ONLY`` as the only level safe to grant
  unattended.
- An ``ExternalRoamingWorker`` Pydantic model with the LivingAgent
  onboarding-contract fields (agent_uid / callsign, harness, model_identity,
  department, role, endpoint, autonomy_policy, authority, workspace policy,
  memory_namespace, trace_identity, status timestamps, registration_source).
- An autonomy_policy validator that refuses to encode runtime authority an
  external worker is not yet trusted with: PR approval, source writes
  outside an explicit assignment, mutation of Meta-Dharma / telos /
  dharma_kernel / DGM-protected files, or context-bundle authoring.
- A canonical Kimi 2.6 registration record (``KIMI_2_6_REGISTRATION``) for
  the returning historical roaming embodiment, marked external-evidence-only
  with no automatic authority inheritance.

It does NOT add a Kimi/Moonshot ``ProviderType`` — provider integration is
deliberately out of scope for Stage 1. The model_identity here is metadata
attached to the registration record, not a router binding.

Sandbox path conventions
------------------------
External-worker artifacts are written under
``$DHARMA_HOME/external_agents/{agent_uid}/`` (default
``~/.dharma/external_agents/{agent_uid}/``). Paths under the repository
working tree, ``.dharma/`` at the repo root, or any DGM-protected file
are rejected by :func:`validate_sandbox_path`.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from dharma_swarm import model_pool as _model_pool
from dharma_swarm.dgm_loop import DGM_PROTECTED_FILES
from dharma_swarm.operator_core.identity_invariant import build_identity_invariant, canonical_serial
from dharma_swarm.roaming_onboarding import (
    OnboardingReceipt,
    RoamingAgentRegistration,
    _dharma_home as _roaming_dharma_home,
    onboard_roaming_agent,
)


def _kimi_2_6_model_identity() -> str:
    """The Kimi 2.6 registration model_identity string, sourced from the pool.

    This is registration metadata, not a router binding (see the module
    docstring), but the model-id string still lives in exactly ONE place: the
    ONE model pool, at the K2.6 FLOOR. ``_model_pool`` owns the vendor-prefixed
    ``moonshotai/kimi-k2.6`` route; we project it so this record can never drift
    from (or sink below) the floor the pool defines.
    """
    entry = _model_pool.get_entry("kimi-k2.6")
    if entry is not None:
        for mid in entry.model_ids:
            if mid.startswith("moonshotai/"):
                return mid
    raise AssertionError("model_pool has no moonshotai route for the K2.6 floor")


# ---------------------------------------------------------------------------
# Authority ladder
# ---------------------------------------------------------------------------


class ExternalAgentAuthority(str, Enum):
    """Coarse authority levels for external roaming workers.

    Only ``EXTERNAL_WORKER_EVIDENCE_ONLY`` is granted by default at Stage 1.
    Higher rungs require an explicit, separately-reviewed PR that wires the
    runtime side; this module refuses to emit them.
    """

    EXTERNAL_WORKER_EVIDENCE_ONLY = "external_worker_evidence_only"
    SANDBOX_WRITE = "sandbox_write"
    ASSIGNED_TASK_ONLY = "assigned_task_only"
    FULL_RUNTIME = "full_runtime"


STAGE_1_ALLOWED_AUTHORITIES: frozenset[ExternalAgentAuthority] = frozenset(
    {
        ExternalAgentAuthority.EXTERNAL_WORKER_EVIDENCE_ONLY,
        ExternalAgentAuthority.SANDBOX_WRITE,
    }
)


# Forbidden mutation targets — names, not paths, mirroring DGM precedent.
FORBIDDEN_MUTATION_FILES: frozenset[str] = (
    DGM_PROTECTED_FILES
    | frozenset(
        {
            # Meta-dharma surfaces; never mutated by external workers.
            "meta_dharma.py",
            "telos_gates.py",
            "dharma_kernel.py",
            # Context bundles and canonical-doc stack.
            "context_bundle.py",
            "context_bundles.py",
        }
    )
)


# Status surface ----------------------------------------------------------


class ExternalAgentStatus(str, Enum):
    REGISTERED = "registered"
    PROVISIONAL = "provisional"
    SUSPENDED = "suspended"
    HISTORICAL = "historical"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_CALLSIGN_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{1,62}[a-z0-9]$")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def external_agent_sandbox_root(dharma_home: Path | None = None) -> Path:
    """Sandbox root under which external-worker artifacts may be written.

    Defers ``$DHARMA_HOME`` resolution to ``roaming_onboarding`` so this
    module does not own a separate slice of ``~/.dharma`` — external-agent
    artifacts live under the same canonical state root that the roaming
    onboarding pipeline already governs.
    """

    return (dharma_home or _roaming_dharma_home()) / "external_agents"


# ---------------------------------------------------------------------------
# Autonomy policy
# ---------------------------------------------------------------------------


class AutonomyPolicy(BaseModel):
    """Concrete refusal flags for an external worker.

    These are encoded as positive refusals so a registration record
    self-documents what the worker may *not* do, without depending on
    runtime enforcement code reading the same fields back.
    """

    mode: str = "manual"
    requires_approval: bool = True
    can_approve_prs: bool = False
    can_write_source: bool = False
    can_mutate_meta_dharma: bool = False
    can_mutate_telos: bool = False
    can_mutate_dharma_kernel: bool = False
    can_mutate_dgm_protected: bool = False
    can_author_context_bundles: bool = False
    explicit_task_assignment_required: bool = True

    @model_validator(mode="after")
    def _refuse_escalation(self) -> "AutonomyPolicy":
        forbidden = [
            ("can_approve_prs", self.can_approve_prs),
            ("can_write_source", self.can_write_source),
            ("can_mutate_meta_dharma", self.can_mutate_meta_dharma),
            ("can_mutate_telos", self.can_mutate_telos),
            ("can_mutate_dharma_kernel", self.can_mutate_dharma_kernel),
            ("can_mutate_dgm_protected", self.can_mutate_dgm_protected),
            ("can_author_context_bundles", self.can_author_context_bundles),
        ]
        offenders = [name for name, val in forbidden if val]
        if offenders:
            raise ValueError(
                "External roaming workers may not be granted: "
                + ", ".join(offenders)
                + " — these require a separate, explicitly-reviewed runtime PR."
            )
        if not self.requires_approval:
            raise ValueError(
                "External roaming workers must require approval in Stage 1."
            )
        return self


class WorkspacePolicy(BaseModel):
    """Where the worker may write artifacts."""

    sandbox_root: str
    repo_writes_allowed: bool = False
    canonical_dharma_dir_writes_allowed: bool = False  # ~/.dharma/ginko/...

    @field_validator("sandbox_root")
    @classmethod
    def _must_be_under_external_agents(cls, value: str) -> str:
        path = Path(value).expanduser()
        if "external_agents" not in path.parts:
            raise ValueError(
                "sandbox_root must live under an 'external_agents/' tree; "
                f"got {value!r}"
            )
        return str(path)

    @model_validator(mode="after")
    def _refuse_non_sandbox_writes(self) -> "WorkspacePolicy":
        forbidden = [
            ("repo_writes_allowed", self.repo_writes_allowed),
            (
                "canonical_dharma_dir_writes_allowed",
                self.canonical_dharma_dir_writes_allowed,
            ),
        ]
        offenders = [name for name, val in forbidden if val]
        if offenders:
            raise ValueError(
                "External roaming workers may not be granted workspace writes: "
                + ", ".join(offenders)
                + " in Stage 1."
            )
        return self


# ---------------------------------------------------------------------------
# External roaming worker schema
# ---------------------------------------------------------------------------


class ExternalRoamingWorker(BaseModel):
    """Stage-1 registration record for an external roaming worker.

    Field selection mirrors the LivingAgent onboarding contract where the
    fields exist canonically; runtime-only fields (e.g. ``provider`` enum
    binding) are intentionally omitted at this stage.
    """

    agent_uid: str
    callsign: str
    display_name: str
    harness: str
    model_identity: str = ""
    department: str = "swarm"
    role: str = "external_worker"
    squad_id: str = "general"
    team_id: str = "dharma_swarm"
    endpoint: str = "pending://manual"
    mailbox: str = ""
    authority: ExternalAgentAuthority = (
        ExternalAgentAuthority.EXTERNAL_WORKER_EVIDENCE_ONLY
    )
    autonomy_policy: AutonomyPolicy = Field(default_factory=AutonomyPolicy)
    workspace_policy: WorkspacePolicy
    memory_namespace: str
    trace_identity: str
    status: ExternalAgentStatus = ExternalAgentStatus.REGISTERED
    is_returning_historical_embodiment: bool = False
    notes: str = ""
    registration_source: str = "external_agent_registration"
    capabilities: tuple[str, ...] = ()
    identity_invariant: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)
    last_seen_at: str = ""

    @field_validator("callsign")
    @classmethod
    def _callsign_shape(cls, value: str) -> str:
        if not _CALLSIGN_RE.match(value):
            raise ValueError(
                f"callsign {value!r} must be lowercase alnum with -/_ separators"
            )
        return value

    @field_validator("agent_uid")
    @classmethod
    def _agent_uid_shape(cls, value: str) -> str:
        if not _CALLSIGN_RE.match(value):
            raise ValueError(
                f"agent_uid {value!r} must be lowercase alnum with -/_ separators"
            )
        return value

    @model_validator(mode="after")
    def _authority_within_stage_1(self) -> "ExternalRoamingWorker":
        if self.authority not in STAGE_1_ALLOWED_AUTHORITIES:
            raise ValueError(
                f"authority {self.authority.value!r} is not permitted in Stage-1 "
                "external registration — only "
                f"{sorted(a.value for a in STAGE_1_ALLOWED_AUTHORITIES)}."
            )
        return self

    @model_validator(mode="after")
    def _memory_namespace_scoped(self) -> "ExternalRoamingWorker":
        expected_prefix = f"agent:{self.agent_uid}"
        if self.memory_namespace != expected_prefix and not self.memory_namespace.startswith(
            expected_prefix + ":"
        ):
            raise ValueError(
                f"memory_namespace must start with {expected_prefix!r}; "
                f"got {self.memory_namespace!r}"
            )
        return self

    @model_validator(mode="after")
    def _attach_identity_invariant(self) -> "ExternalRoamingWorker":
        if not self.identity_invariant:
            self.identity_invariant = build_identity_invariant(
                agent_uid=self.agent_uid,
                authority_floor=self.authority.value,
                memory_namespace=self.memory_namespace,
                trace_identity=self.trace_identity,
                serial=canonical_serial(self.agent_uid),
                created_at=self.created_at,
            )
        return self


# ---------------------------------------------------------------------------
# Forbidden-mutation guard
# ---------------------------------------------------------------------------


def assert_mutation_allowed(target: str | Path) -> None:
    """Raise PermissionError if *target* names a forbidden mutation file.

    External workers must not modify Meta-Dharma / telos / dharma_kernel /
    DGM-protected files or context-bundle authoring modules. Match is by
    basename, mirroring ``dgm_loop._is_protected_dgm_target``.
    """

    name = Path(str(target)).name
    if name in FORBIDDEN_MUTATION_FILES:
        raise PermissionError(
            f"External roaming worker may not mutate {name!r} — "
            "Meta-Dharma / telos / dharma_kernel / DGM-protected surface."
        )


def validate_sandbox_path(
    target: str | Path,
    *,
    dharma_home: Path | None = None,
) -> Path:
    """Resolve *target* and confirm it lies under the external-agent sandbox.

    Returns the resolved Path on success, raises PermissionError otherwise.
    Repo working-tree paths and ``.dharma/`` paths at the repo root are
    rejected.
    """

    sandbox = external_agent_sandbox_root(dharma_home).resolve()
    candidate = Path(str(target)).expanduser().resolve()

    try:
        candidate.relative_to(sandbox)
    except ValueError as exc:
        raise PermissionError(
            f"Path {candidate} is outside the external-agent sandbox {sandbox}."
        ) from exc
    return candidate


# ---------------------------------------------------------------------------
# Registration helper (writes to ~/.dharma/external_agents/{uid}/...)
# ---------------------------------------------------------------------------


def _record_path(worker: ExternalRoamingWorker, dharma_home: Path | None) -> Path:
    return external_agent_sandbox_root(dharma_home) / worker.agent_uid / "registration.json"


async def register_external_worker(
    worker: ExternalRoamingWorker,
    *,
    dharma_home: Path | None = None,
    write_canonical_onboarding: bool = True,
) -> dict[str, Any]:
    """Persist an external-worker registration and (optionally) onboard it.

    Writes ``$DHARMA_HOME/external_agents/{agent_uid}/registration.json`` and,
    if *write_canonical_onboarding* is True, also calls the canonical
    :func:`onboard_roaming_agent` so identity surfaces and telemetry know about
    the worker. The canonical onboarding receives the autonomy_policy / authority
    metadata so downstream code can read the registration's intent.

    Returns a dict with ``record_path``, the worker payload, and (when
    canonical onboarding ran) the ``OnboardingReceipt`` as a dict.
    """

    import json

    record_path = _record_path(worker, dharma_home)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    payload = worker.model_dump()
    payload["last_seen_at"] = payload["last_seen_at"] or _utc_now_iso()
    payload["updated_at"] = _utc_now_iso()
    record_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    result: dict[str, Any] = {
        "record_path": str(record_path),
        "worker": payload,
    }

    if write_canonical_onboarding:
        canonical = RoamingAgentRegistration(
            callsign=worker.callsign,
            harness=worker.harness,
            role=worker.role,
            department=worker.department,
            squad_id=worker.squad_id,
            team_id=worker.team_id,
            model=worker.model_identity,
            provider="",  # intentionally empty — Stage 1 has no provider binding
            endpoint=worker.endpoint,
            description=worker.notes or worker.display_name,
            capabilities=tuple(worker.capabilities),
            registration_source=worker.registration_source,
            agent_uid=worker.agent_uid,
            metadata={
                "authority": worker.authority.value,
                "autonomy_policy": worker.autonomy_policy.model_dump(),
                "workspace_policy": worker.workspace_policy.model_dump(),
                "memory_namespace": worker.memory_namespace,
                "trace_identity": worker.trace_identity,
                "identity_invariant": worker.identity_invariant,
                "identity_invariant_digest": worker.identity_invariant.get("digest"),
                "status": worker.status.value,
                "is_returning_historical_embodiment": (
                    worker.is_returning_historical_embodiment
                ),
                "registration_stage": "stage_1_external_evidence_only",
                **dict(worker.metadata),
            },
        )
        receipt: OnboardingReceipt = await onboard_roaming_agent(
            canonical,
            dharma_home=dharma_home,
        )
        result["onboarding_receipt"] = receipt.to_dict()

    return result


# ---------------------------------------------------------------------------
# Kimi 2.6 — returning historical roaming embodiment
# ---------------------------------------------------------------------------


def _kimi_workspace_policy(dharma_home: Path | None = None) -> WorkspacePolicy:
    return WorkspacePolicy(
        sandbox_root=str(
            external_agent_sandbox_root(dharma_home) / "kimi_2_6_claw"
        ),
        repo_writes_allowed=False,
        canonical_dharma_dir_writes_allowed=False,
    )


def kimi_2_6_registration(
    *,
    dharma_home: Path | None = None,
) -> ExternalRoamingWorker:
    """Construct the Kimi 2.6 registration record.

    The record is intentionally evidence-only: no automatic authority
    inheritance from prior historical embodiments (notably ``kimi-claw-phone``)
    is encoded here. Heartbeat/artifact paths, if any, sit under the
    ``external_agents/kimi_2_6_claw/`` sandbox.
    """

    return ExternalRoamingWorker(
        agent_uid="kimi_2_6_claw",
        callsign="kimi-claw-phone",
        display_name="Kimi 2.6 (Claw, returning roaming embodiment)",
        harness="moonshot_kimi_2_6",
        model_identity=_kimi_2_6_model_identity(),
        department="research",
        role="external_evidence_worker",
        squad_id="transit",
        team_id="dharma_swarm",
        endpoint="pending://kimi-2-6-manual",
        mailbox="roaming_mailbox://kimi-claw-phone",
        authority=ExternalAgentAuthority.EXTERNAL_WORKER_EVIDENCE_ONLY,
        autonomy_policy=AutonomyPolicy(
            mode="manual",
            requires_approval=True,
            explicit_task_assignment_required=True,
        ),
        workspace_policy=_kimi_workspace_policy(dharma_home),
        memory_namespace="agent:kimi_2_6_claw",
        trace_identity="trace:kimi_2_6_claw",
        status=ExternalAgentStatus.REGISTERED,
        is_returning_historical_embodiment=True,
        notes=(
            "Returning historical roaming embodiment. Stage-1 external "
            "registration only — evidence/notes contributions via roaming "
            "mailbox. No runtime/provider integration, no PR approval, no "
            "source-tree writes, no Meta-Dharma / telos / dharma_kernel "
            "mutation."
        ),
        registration_source="stage_1_external_agent_registration",
        capabilities=("research_evidence", "synthesis_notes"),
        metadata={
            "prior_callsigns": ["kimi-claw-phone"],
            "automatic_authority_inheritance": False,
            "mailbox_is_transport_only": True,
        },
    )


KIMI_2_6_REGISTRATION = kimi_2_6_registration()


__all__ = [
    "AutonomyPolicy",
    "ExternalAgentAuthority",
    "ExternalAgentStatus",
    "ExternalRoamingWorker",
    "FORBIDDEN_MUTATION_FILES",
    "KIMI_2_6_REGISTRATION",
    "STAGE_1_ALLOWED_AUTHORITIES",
    "WorkspacePolicy",
    "assert_mutation_allowed",
    "external_agent_sandbox_root",
    "kimi_2_6_registration",
    "register_external_worker",
    "validate_sandbox_path",
]
