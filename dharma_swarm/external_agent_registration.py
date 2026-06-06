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

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from dharma_swarm.dgm_loop import DGM_PROTECTED_FILES
from dharma_swarm.roaming_onboarding import (
    OnboardingReceipt,
    RoamingAgentRegistration,
    _dharma_home as _roaming_dharma_home,
    onboard_roaming_agent,
)


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
# Identity invariant — the continuity anchor shared by every identity surface
# ---------------------------------------------------------------------------

IDENTITY_INVARIANT_SCHEMA_VERSION = "dharma_identity_invariant.v1"

# The ordered tuple of fields that defines an agent's continuity. The digest is
# computed over exactly these keys (schema_version is included). Any surface
# that carries the identity (registration.json, identity_manifest.normalized,
# living_agent.json, the a2a card metadata, the runtime.db row metadata) must
# carry the same digest, or the agent's identity has drifted.
IDENTITY_INVARIANT_DIGEST_FIELDS: tuple[str, ...] = (
    "schema_version",
    "agent_uid",
    "authority_floor",
    "memory_namespace",
    "trace_identity",
    "serial",
    "created_at",
)


def compute_identity_invariant_digest(fields: dict[str, Any]) -> str:
    """Recompute the canonical sha256 digest over the invariant tuple.

    This is the *producer* that no existing surface owned: every persisted
    record carried a ``digest`` value but nothing in-repo could recompute it,
    so drift was undetectable. The canonical pre-image is the JSON object of
    the :data:`IDENTITY_INVARIANT_DIGEST_FIELDS` keys serialised with
    ``json.dumps(..., sort_keys=True)`` (the SDK default separators, i.e.
    ``", "`` / ``": "``). The result is prefixed ``sha256:`` to match the
    stored form.

    Reproducing the pre-image exactly is load-bearing: it means the digest of
    every already-registered agent stays stable, so this producer can *verify*
    historical records rather than silently rewriting them.
    """

    payload = {key: fields[key] for key in IDENTITY_INVARIANT_DIGEST_FIELDS}
    preimage = json.dumps(payload, sort_keys=True)
    return "sha256:" + hashlib.sha256(preimage.encode("utf-8")).hexdigest()


class IdentityInvariant(BaseModel):
    """The owning type for an external worker's continuity anchor.

    The seven fields below are the *only* facts that define identity across
    embodiments: who (``agent_uid`` / ``serial``), the floor of authority that
    may never be exceeded unattended (``authority_floor``), where memory and
    traces are scoped (``memory_namespace`` / ``trace_identity``), and the birth
    timestamp (``created_at``). ``digest`` is derived, never authored: it is
    recomputed from the other fields and frozen so two surfaces can be compared
    for drift by digest alone.
    """

    schema_version: str = IDENTITY_INVARIANT_SCHEMA_VERSION
    agent_uid: str
    authority_floor: str
    memory_namespace: str
    trace_identity: str
    serial: str
    created_at: str
    digest: str = ""

    @model_validator(mode="after")
    def _seal_digest(self) -> "IdentityInvariant":
        computed = compute_identity_invariant_digest(self.model_dump())
        if self.digest and self.digest != computed:
            raise ValueError(
                "IdentityInvariant digest mismatch: stored "
                f"{self.digest!r} != recomputed {computed!r}. The invariant "
                "fields do not produce the stored digest — identity has drifted."
            )
        object.__setattr__(self, "digest", computed)
        return self

    def to_record(self) -> dict[str, Any]:
        """Serialise in the canonical key order used by every persisted copy."""

        ordered = {key: getattr(self, key) for key in IDENTITY_INVARIANT_DIGEST_FIELDS}
        ordered["digest"] = self.digest
        return ordered

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "IdentityInvariant":
        """Load a persisted invariant and re-verify its digest on the way in."""

        return cls(**{k: record.get(k) for k in (*IDENTITY_INVARIANT_DIGEST_FIELDS, "digest")})


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

    def serial(self) -> str:
        """Canonical serial derived from the agent_uid (AGT-<UID>)."""

        return f"AGT-{self.agent_uid.replace('-', '_').upper()}"

    def to_identity_invariant(
        self,
        *,
        created_at: str | None = None,
    ) -> IdentityInvariant:
        """Derive this record's continuity anchor.

        ``created_at`` defaults to the record's own creation time so the digest
        is stable across re-registrations of the same seat; pass an explicit
        value only when reconciling against an already-persisted invariant whose
        birth timestamp predates this record.
        """

        return IdentityInvariant(
            agent_uid=self.agent_uid,
            authority_floor=ExternalAgentAuthority.EXTERNAL_WORKER_EVIDENCE_ONLY.value,
            memory_namespace=self.memory_namespace,
            trace_identity=self.trace_identity,
            serial=self.serial(),
            created_at=created_at or self.created_at,
        )


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
        model_identity="moonshotai/kimi-k2.6",
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


# ---------------------------------------------------------------------------
# Loader — read a persisted registration back into the typed schema
# ---------------------------------------------------------------------------


def load_external_worker(
    agent_uid: str,
    *,
    dharma_home: Path | None = None,
) -> ExternalRoamingWorker:
    """Load ``external_agents/{agent_uid}/registration.json`` as a typed record.

    This is the loader the schema lacked: the registration was written by
    :func:`register_external_worker` but only ever read as raw JSON. Loading it
    back through :class:`ExternalRoamingWorker` re-runs every validator
    (authority floor, callsign shape, memory-namespace scoping), so a tampered
    or drifted file fails loudly instead of being trusted blindly.
    """

    path = _record_path(
        ExternalRoamingWorker.model_construct(agent_uid=agent_uid),  # path only
        dharma_home,
    )
    if not path.exists():
        raise FileNotFoundError(f"No registration.json for {agent_uid!r} at {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("identity_invariant", None)  # derived, not a constructor field
    return ExternalRoamingWorker.model_validate(raw)


# ---------------------------------------------------------------------------
# verify_identity — assert every surface carries the same continuity anchor
# ---------------------------------------------------------------------------


def _dig(value: Any) -> str | None:
    """Pull a digest out of either a nested invariant dict or a flat string."""

    if isinstance(value, dict):
        return value.get("digest")
    if isinstance(value, str):
        return value
    return None


def verify_identity(
    agent_uid: str,
    *,
    dharma_home: Path | None = None,
    telemetry_db_path: Path | None = None,
) -> dict[str, Any]:
    """Assert that every identity surface agrees on one continuity anchor.

    Surfaces checked (each is OPTIONAL — absent surfaces are reported, not
    failed, so this works for partially-onboarded agents):

    - ``external_agents/{uid}/registration.json``        (canonical record)
    - ``external_agents/{uid}/identity_invariant.json``  (flat invariant)
    - ``external_agents/{uid}/identity_manifest.normalized.json``
    - ``agents/{uid}/living_agent.json``                 (home dock)
    - ``a2a/cards/{uid}.json``                            (A2A card)
    - ``state/runtime.db`` ``agent_identity`` row metadata

    Returns a report dict with ``ok`` (bool), the ``expected`` digest recomputed
    from the canonical record, a per-surface ``surfaces`` map, and a list of
    ``mismatches``. Raises nothing on drift — the caller decides what a failed
    ``ok`` means. The canonical record's own digest is recomputed and compared
    to its stored value first, so a self-inconsistent registration is caught.
    """

    home = dharma_home or _roaming_dharma_home()
    base = home / "external_agents" / agent_uid
    surfaces: dict[str, Any] = {}
    mismatches: list[str] = []

    # 1. Canonical record + recomputed expected digest.
    worker = load_external_worker(agent_uid, dharma_home=home)
    reg_raw = json.loads((base / "registration.json").read_text(encoding="utf-8"))
    stored_inv = reg_raw.get("identity_invariant") or {}
    created_at = stored_inv.get("created_at") or worker.created_at
    expected = worker.to_identity_invariant(created_at=created_at)
    expected_digest = expected.digest
    surfaces["registration.json"] = {
        "present": True,
        "digest": _dig(stored_inv),
        "role": reg_raw.get("role"),
        "model_identity": reg_raw.get("model_identity"),
        "memory_namespace": reg_raw.get("memory_namespace"),
    }
    if _dig(stored_inv) != expected_digest:
        mismatches.append(
            f"registration.json digest {_dig(stored_inv)!r} != recomputed "
            f"{expected_digest!r}"
        )

    # Field-level coherence the digest does NOT cover (role/model live outside
    # the invariant tuple but must still be consistent across surfaces).
    expected_role = reg_raw.get("role")
    expected_model = reg_raw.get("model_identity")
    expected_ns = expected.memory_namespace

    def _check_digest(label: str, payload: dict[str, Any], digest_value: Any) -> None:
        d = _dig(digest_value)
        surfaces[label] = {"present": True, "digest": d}
        if d != expected_digest:
            mismatches.append(f"{label} digest {d!r} != expected {expected_digest!r}")

    # 2. Flat identity_invariant.json
    inv_path = base / "identity_invariant.json"
    if inv_path.exists():
        flat = json.loads(inv_path.read_text(encoding="utf-8"))
        _check_digest("identity_invariant.json", flat, flat.get("digest"))
    else:
        surfaces["identity_invariant.json"] = {"present": False}

    # 3. Normalized manifest
    man_path = base / "identity_manifest.normalized.json"
    if man_path.exists():
        man = json.loads(man_path.read_text(encoding="utf-8"))
        _check_digest("identity_manifest.normalized.json", man, man.get("identity_invariant"))
        if man.get("role") not in (None, expected_role):
            mismatches.append(
                f"manifest role {man.get('role')!r} != {expected_role!r}"
            )
        if man.get("model_identity") not in (None, expected_model):
            mismatches.append(
                f"manifest model {man.get('model_identity')!r} != {expected_model!r}"
            )
    else:
        surfaces["identity_manifest.normalized.json"] = {"present": False}

    # 4. Home dock living_agent.json
    dock_path = home / "agents" / agent_uid / "living_agent.json"
    if dock_path.exists():
        dock = json.loads(dock_path.read_text(encoding="utf-8"))
        dock_inv = dock.get("identity_invariant") or (dock.get("metadata") or {}).get(
            "identity_invariant"
        )
        _check_digest("living_agent.json", dock, dock_inv)
        dock_ns = dock.get("memory_namespace")
        if dock_ns not in (None, expected_ns):
            mismatches.append(
                f"living_agent.json memory_namespace {dock_ns!r} != {expected_ns!r}"
            )
    else:
        surfaces["living_agent.json"] = {"present": False}

    # 5. A2A card
    card_path = home / "a2a" / "cards" / f"{agent_uid}.json"
    if card_path.exists():
        card = json.loads(card_path.read_text(encoding="utf-8"))
        card_meta = card.get("metadata") or {}
        _check_digest("a2a_card", card, card_meta.get("identity_invariant"))
        if card.get("role") not in (None, expected_role):
            mismatches.append(f"a2a card role {card.get('role')!r} != {expected_role!r}")
        if card.get("model") not in (None, expected_model):
            mismatches.append(f"a2a card model {card.get('model')!r} != {expected_model!r}")
    else:
        surfaces["a2a_card"] = {"present": False}

    # 6. runtime.db agent_identity row metadata
    db_path = telemetry_db_path or (home / "state" / "runtime.db")
    if db_path.exists():
        import sqlite3

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT specialization, status, metadata_json FROM agent_identity"
                " WHERE agent_id = ?",
                (agent_uid,),
            ).fetchone()
            conn.close()
        except sqlite3.Error as exc:  # pragma: no cover - defensive
            row = None
            surfaces["runtime_db"] = {"present": False, "error": str(exc)}
        if row is not None:
            meta = json.loads(row["metadata_json"] or "{}")
            db_inv = meta.get("identity_invariant") or meta.get(
                "identity_invariant_digest"
            )
            surfaces["runtime_db"] = {
                "present": True,
                "digest": _dig(db_inv),
                "status": row["status"],
                "specialization": row["specialization"],
            }
            if _dig(db_inv) != expected_digest:
                mismatches.append(
                    f"runtime_db digest {_dig(db_inv)!r} != expected "
                    f"{expected_digest!r}"
                )
            if row["specialization"] not in (None, "", expected_role):
                mismatches.append(
                    f"runtime_db specialization {row['specialization']!r} != "
                    f"{expected_role!r}"
                )
    else:
        surfaces["runtime_db"] = {"present": False}

    return {
        "agent_uid": agent_uid,
        "ok": not mismatches,
        "expected_digest": expected_digest,
        "expected_role": expected_role,
        "expected_model": expected_model,
        "expected_memory_namespace": expected_ns,
        "surfaces": surfaces,
        "mismatches": mismatches,
    }


__all__ = [
    "AutonomyPolicy",
    "ExternalAgentAuthority",
    "ExternalAgentStatus",
    "ExternalRoamingWorker",
    "FORBIDDEN_MUTATION_FILES",
    "IDENTITY_INVARIANT_DIGEST_FIELDS",
    "IDENTITY_INVARIANT_SCHEMA_VERSION",
    "IdentityInvariant",
    "KIMI_2_6_REGISTRATION",
    "STAGE_1_ALLOWED_AUTHORITIES",
    "WorkspacePolicy",
    "assert_mutation_allowed",
    "compute_identity_invariant_digest",
    "external_agent_sandbox_root",
    "kimi_2_6_registration",
    "load_external_worker",
    "register_external_worker",
    "validate_sandbox_path",
    "verify_identity",
]
