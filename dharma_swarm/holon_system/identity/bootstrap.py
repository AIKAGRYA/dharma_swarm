"""Idempotent materialization of a canonical sovereign-holon identity.

This module composes the existing agent registry, roaming onboarding, and
``load_holon`` runtime door.  It creates no second registry or runtime.  A plan
is read-only; apply writes only missing/matching canonical files and refuses to
overwrite conflicting identity claims.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.agent_registry import AgentRegistry
from dharma_swarm.holon_bridge import RunningHolon, load_holon
from dharma_swarm.models import ProviderType
from dharma_swarm.roaming_onboarding import (
    RoamingAgentRegistration,
    onboard_roaming_agent,
)


AGENT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
AUTHORITY_MODE = "read_only_until_execution_lease"
BOOTSTRAP_ACTION = "holon_bootstrap"


class HolonBootstrapError(RuntimeError):
    """Raised when a bootstrap plan cannot be safely materialized."""


@dataclass(frozen=True)
class HolonBootstrapSpec:
    name: str
    role: str
    provider: str
    model: str
    system_prompt: str
    harness: str = "codex"
    endpoint: str = "local://dgc-agent"
    description: str = ""
    department: str = "swarm"
    squad_id: str = "general"
    team_id: str = "dharma_swarm"
    capabilities: tuple[str, ...] = ("reason", "plan")


@dataclass(frozen=True)
class HolonBootstrapPlan:
    schema_version: str
    action: str
    name: str
    provider: str
    model: str
    agents_root: str
    identity_path: str
    active_prompt_path: str
    living_dock_path: str
    card_path: str
    prompt_sha256: str
    required_writes: tuple[str, ...]
    conflicts: tuple[str, ...]
    ready_to_apply: bool
    authority_mode: str = AUTHORITY_MODE
    secret_material_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_spec(spec: HolonBootstrapSpec) -> ProviderType:
    if not AGENT_NAME_RE.fullmatch(spec.name or ""):
        raise HolonBootstrapError("invalid holon name")
    if not spec.role.strip():
        raise HolonBootstrapError("role is required")
    if not spec.model.strip():
        raise HolonBootstrapError("model is required")
    if not spec.system_prompt.strip():
        raise HolonBootstrapError("system prompt is required")
    if "\x00" in spec.system_prompt:
        raise HolonBootstrapError("system prompt contains a NUL byte")
    try:
        return ProviderType(spec.provider.strip().lower())
    except ValueError as exc:
        choices = ", ".join(item.value for item in ProviderType)
        raise HolonBootstrapError(
            f"unsupported provider {spec.provider!r}; choose one of: {choices}"
        ) from exc


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HolonBootstrapError(f"cannot read canonical identity: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise HolonBootstrapError(f"canonical identity is not an object: {path}")
    return payload


def _reject_symlink_components(path: Path, root: Path) -> None:
    """Keep canonical writes inside ``root`` even when parents already exist."""
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise HolonBootstrapError(f"bootstrap path is outside canonical home: {path}") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise HolonBootstrapError(f"canonical bootstrap path contains a symlink: {current}")


def _atomic_write(path: Path, content: str, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, mode)
    finally:
        if tmp.exists():
            tmp.unlink()


def _identity_claims(spec: HolonBootstrapSpec) -> dict[str, str]:
    return {
        "name": spec.name,
        "agent_uid": spec.name,
        "callsign": spec.name,
        "role": spec.role,
        "provider": spec.provider.strip().lower(),
        "model": spec.model,
        "system_prompt": spec.system_prompt,
        "authority_mode": AUTHORITY_MODE,
    }


def plan_holon_bootstrap(
    spec: HolonBootstrapSpec,
    *,
    dharma_home: Path | None = None,
) -> HolonBootstrapPlan:
    """Return a read-only, redacted materialization plan."""
    _validate_spec(spec)
    home = (dharma_home or (Path.home() / ".dharma")).expanduser().resolve()
    agents_root = home / "agents"
    agent_dir = agents_root / spec.name
    identity_path = agent_dir / "identity.json"
    active_path = agent_dir / "prompt_variants" / "active.txt"
    living_path = agent_dir / "living_agent.json"
    card_path = home / "a2a" / "cards" / f"{spec.name}.json"
    for canonical_path in (identity_path, active_path, living_path, card_path):
        _reject_symlink_components(canonical_path, home)

    writes: list[str] = []
    conflicts: list[str] = []
    existing = _read_json(identity_path)
    claims = _identity_claims(spec)
    if existing is None:
        writes.extend([str(identity_path), str(active_path)])
    else:
        for key, wanted in claims.items():
            observed = existing.get(key)
            # Once active.txt exists it is the canonical evolved prompt.  The
            # identity's creation-time system_prompt may legitimately lag it.
            if key == "system_prompt" and active_path.exists():
                continue
            if observed in (None, ""):
                if str(identity_path) not in writes:
                    writes.append(str(identity_path))
            elif str(observed) != str(wanted):
                conflicts.append(f"identity.{key} conflicts with requested bootstrap claim")
        if not active_path.exists():
            writes.append(str(active_path))
        else:
            active = active_path.read_text(encoding="utf-8-sig")
            if active != spec.system_prompt:
                conflicts.append("prompt_variants/active.txt conflicts with requested system prompt")

    if not living_path.exists():
        writes.append(str(living_path))
    if not card_path.exists():
        writes.append(str(card_path))

    return HolonBootstrapPlan(
        schema_version="dharma.holon_bootstrap.plan.v1",
        action="noop" if not writes and not conflicts else "materialize",
        name=spec.name,
        provider=spec.provider.strip().lower(),
        model=spec.model,
        agents_root=str(agents_root),
        identity_path=str(identity_path),
        active_prompt_path=str(active_path),
        living_dock_path=str(living_path),
        card_path=str(card_path),
        prompt_sha256=hashlib.sha256(spec.system_prompt.encode("utf-8")).hexdigest(),
        required_writes=tuple(dict.fromkeys(writes)),
        conflicts=tuple(conflicts),
        ready_to_apply=not conflicts,
    )


def _merge_missing_identity(
    identity_path: Path,
    spec: HolonBootstrapSpec,
) -> None:
    existing = _read_json(identity_path) or {}
    merged = dict(existing)
    for key, value in _identity_claims(spec).items():
        if merged.get(key) in (None, ""):
            merged[key] = value
    _atomic_write(
        identity_path,
        json.dumps(merged, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )


async def apply_holon_bootstrap(
    spec: HolonBootstrapSpec,
    *,
    dharma_home: Path | None = None,
    telemetry_db_path: Path | None = None,
) -> dict[str, Any]:
    """Materialize the plan, round-trip the runtime loader, and return proof.

    No model call is made and no provider secret is read or copied.
    """
    plan = plan_holon_bootstrap(spec, dharma_home=dharma_home)
    if not plan.ready_to_apply:
        raise HolonBootstrapError("bootstrap conflicts: " + "; ".join(plan.conflicts))

    home = Path(plan.agents_root).parent
    agents_root = Path(plan.agents_root)
    identity_path = Path(plan.identity_path)
    active_path = Path(plan.active_prompt_path)
    living_path = Path(plan.living_dock_path)
    card_path = Path(plan.card_path)

    if not plan.required_writes:
        holon = load_holon(spec.name, agents_root=agents_root)
        return _result(plan, holon, status="already_materialized", onboarding_receipt=None)

    if not identity_path.exists():
        registry = AgentRegistry(agents_dir=agents_root)
        registry.register_agent(
            spec.name,
            spec.role,
            spec.model,
            spec.system_prompt,
        )
    _merge_missing_identity(identity_path, spec)
    if not active_path.exists():
        _atomic_write(active_path, spec.system_prompt)

    onboarding_receipt = None
    if not living_path.exists() or not card_path.exists():
        onboarding_receipt = await onboard_roaming_agent(
            RoamingAgentRegistration(
                callsign=spec.name,
                harness=spec.harness,
                role=spec.role,
                department=spec.department,
                squad_id=spec.squad_id,
                team_id=spec.team_id,
                model=spec.model,
                provider=spec.provider.strip().lower(),
                endpoint=spec.endpoint,
                description=spec.description or f"{spec.name} sovereign holon",
                capabilities=spec.capabilities,
                registration_source="dgc_agent_bootstrap",
                agent_uid=spec.name,
                metadata={
                    "authority_mode": AUTHORITY_MODE,
                    "bootstrap_action": BOOTSTRAP_ACTION,
                    "secret_material_required": False,
                },
            ),
            dharma_home=home,
            telemetry_db_path=telemetry_db_path,
        )

    holon = load_holon(spec.name, agents_root=agents_root)
    return _result(
        plan,
        holon,
        status="materialized",
        onboarding_receipt=(
            onboarding_receipt.to_dict() if onboarding_receipt is not None else None
        ),
    )


def _result(
    plan: HolonBootstrapPlan,
    holon: RunningHolon,
    *,
    status: str,
    onboarding_receipt: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema_version": "dharma.holon_bootstrap.result.v1",
        "ok": True,
        "status": status,
        "name": holon.name,
        "provider": holon.provider_type,
        "model": holon.model,
        "authority_mode": AUTHORITY_MODE,
        "runtime_roundtrip": True,
        "secret_material_read": False,
        "plan": plan.to_dict(),
        "onboarding_receipt": onboarding_receipt,
    }
