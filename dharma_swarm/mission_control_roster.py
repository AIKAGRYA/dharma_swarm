"""Hash-pinned campaign roster admission and idempotent runtime spawning.

Roster membership is execution eligibility only.  It grants no task lease,
effect warrant, completion status, or semantic acceptance.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from dharma_swarm.models import AgentRole, AgentState, AgentStatus, ProviderType


ROSTER_SCHEMA = "dharma.sadhana.agent_roster.v1"
CATALOG_ENDPOINT = "https://ollama.com/v1/models"
_MAX_ROSTER_BYTES = 256 * 1024
_MAX_CLOCK_SKEW = timedelta(minutes=5)
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,99}")
_CLOUD_MODEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}:cloud")
_ROOT_KEYS = frozenset(
    {
        "schema",
        "campaign_id",
        "objective_sha256",
        "activation_at",
        "expires_at",
        "cash_ceiling_usd",
        "concurrency_ceiling",
        "provider_catalog",
        "agents",
        "claims",
    }
)
_CATALOG_KEYS = frozenset(
    {"provider", "endpoint", "authentication", "observed_at", "models"}
)
_AGENT_KEYS = frozenset(
    {"name", "role", "provider", "model", "family", "thread", "system_prompt"}
)


class CampaignRosterError(RuntimeError):
    """The roster or its live identity reconciliation failed closed."""


class CampaignRosterSwarm(Protocol):
    """Minimum SwarmManager surface used by roster reconciliation."""

    async def list_agents(self) -> list[AgentState]: ...

    async def spawn_agent(
        self,
        name: str,
        role: AgentRole = AgentRole.GENERAL,
        model: str = "claude-code",
        provider_type: ProviderType = ProviderType.CLAUDE_CODE,
        system_prompt: str = "",
        thread: str | None = None,
    ) -> AgentState: ...


@dataclass(frozen=True, slots=True)
class CampaignAgentSeat:
    name: str
    role: AgentRole
    provider: ProviderType
    model: str
    family: str
    thread: str
    system_prompt: str


@dataclass(frozen=True, slots=True)
class CampaignAgentRoster:
    campaign_id: str
    objective_sha256: str
    activation_at: datetime
    expires_at: datetime
    catalog_observed_at: datetime
    catalog_models: tuple[str, ...]
    seats: tuple[CampaignAgentSeat, ...]
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class CampaignAgentBinding:
    name: str
    agent_id: str
    role: str
    provider: str
    model: str
    family: str
    disposition: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "agent_id": self.agent_id,
            "role": self.role,
            "provider": self.provider,
            "model": self.model,
            "family": self.family,
            "disposition": self.disposition,
        }


@dataclass(frozen=True, slots=True)
class CampaignRosterReceipt:
    campaign_id: str
    manifest_sha256: str
    bindings: tuple[CampaignAgentBinding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "dharma.sadhana.agent_roster_receipt.v1",
            "campaign_id": self.campaign_id,
            "manifest_sha256": self.manifest_sha256,
            "dispatch_ready": False,
            "authority_state": "unbound",
            "bindings": [binding.to_dict() for binding in self.bindings],
            "claims": {
                "proves": [
                    "Each manifest name resolved to exactly one live process-local AgentState.",
                    "Each bound state matched the requested role, provider, and model.",
                ],
                "does_not_prove": [
                    "Provider reachability, useful work, task authority, or independent acceptance."
                ],
            },
        }


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CampaignRosterError(f"roster JSON contains duplicate key {key!r}")
        result[key] = value
    return result


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    observed = frozenset(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise CampaignRosterError(
            f"{label} keys are not exact (missing={missing}, extra={extra})"
        )


def _required_text(
    value: object,
    label: str,
    *,
    maximum: int = 4096,
) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CampaignRosterError(f"{label} must be non-empty exact text")
    if "\x00" in value or len(value.encode("utf-8")) > maximum:
        raise CampaignRosterError(f"{label} is unsafe or exceeds its size bound")
    return value


def _utc_timestamp(value: object, label: str) -> datetime:
    raw = _required_text(value, label, maximum=64)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CampaignRosterError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise CampaignRosterError(f"{label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _secure_manifest_read(path: Path) -> bytes:
    if not path.is_absolute():
        raise CampaignRosterError("roster manifest path must be absolute")
    try:
        parent = path.parent.resolve(strict=True)
    except OSError as exc:
        raise CampaignRosterError("roster manifest parent is unavailable") from exc
    if parent != path.parent:
        raise CampaignRosterError("roster manifest parent must not traverse symlinks")
    try:
        parent_identity = parent.stat()
        entry = path.lstat()
    except OSError as exc:
        raise CampaignRosterError("roster manifest cannot be inspected") from exc
    if (
        not stat.S_ISDIR(parent_identity.st_mode)
        or parent_identity.st_uid not in {0, os.geteuid()}
        or stat.S_IMODE(parent_identity.st_mode) & 0o022
    ):
        raise CampaignRosterError("roster manifest parent lacks private custody")
    if (
        not stat.S_ISREG(entry.st_mode)
        or entry.st_uid != os.geteuid()
        or stat.S_IMODE(entry.st_mode) != 0o600
        or entry.st_nlink != 1
        or not 0 < entry.st_size <= _MAX_ROSTER_BYTES
    ):
        raise CampaignRosterError(
            "roster manifest must be one bounded same-uid mode-0600 regular file"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (entry.st_dev, entry.st_ino):
            raise CampaignRosterError("roster manifest identity changed before read")
        chunks: list[bytes] = []
        remaining = _MAX_ROSTER_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        after = os.fstat(descriptor)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity or len(content) != after.st_size:
            raise CampaignRosterError("roster manifest changed during read")
        if remaining == 0:
            raise CampaignRosterError("roster manifest exceeds its size bound")
        return content
    except OSError as exc:
        raise CampaignRosterError("roster manifest cannot be opened securely") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def load_campaign_agent_roster(
    path: Path | str,
    *,
    expected_sha256: str,
    campaign_id: str,
    objective_sha256: str,
    now: datetime | None = None,
) -> CampaignAgentRoster:
    """Load and validate one exact immutable roster before any spawn effect."""
    if not _SHA256_RE.fullmatch(expected_sha256):
        raise CampaignRosterError("expected roster SHA-256 must be lowercase and full")
    if not _SHA256_RE.fullmatch(objective_sha256):
        raise CampaignRosterError("objective SHA-256 must be lowercase and full")
    content = _secure_manifest_read(Path(path))
    observed_sha256 = hashlib.sha256(content).hexdigest()
    if observed_sha256 != expected_sha256:
        raise CampaignRosterError("roster manifest SHA-256 does not match")
    try:
        payload = json.loads(content, object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CampaignRosterError("roster manifest is not strict UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise CampaignRosterError("roster manifest root must be an object")
    _exact_keys(payload, _ROOT_KEYS, "roster manifest")
    if payload["schema"] != ROSTER_SCHEMA:
        raise CampaignRosterError("roster manifest schema is unsupported")
    if payload["campaign_id"] != campaign_id:
        raise CampaignRosterError("roster manifest campaign identity does not match")
    if payload["objective_sha256"] != objective_sha256:
        raise CampaignRosterError("roster manifest objective identity does not match")
    if type(payload["cash_ceiling_usd"]) is not int or payload["cash_ceiling_usd"] != 0:
        raise CampaignRosterError("roster cash ceiling must be exactly zero")
    if (
        type(payload["concurrency_ceiling"]) is not int
        or payload["concurrency_ceiling"] != 7
    ):
        raise CampaignRosterError("roster concurrency ceiling must be exactly seven")

    activation_at = _utc_timestamp(payload["activation_at"], "activation_at")
    expires_at = _utc_timestamp(payload["expires_at"], "expires_at")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise CampaignRosterError("roster admission clock must be timezone-aware")
    current = current.astimezone(timezone.utc)
    if not activation_at <= current < expires_at:
        raise CampaignRosterError("roster is not inside its exact campaign timebox")

    catalog = payload["provider_catalog"]
    if not isinstance(catalog, Mapping):
        raise CampaignRosterError("provider_catalog must be an object")
    _exact_keys(catalog, _CATALOG_KEYS, "provider_catalog")
    if (
        catalog["provider"] != ProviderType.OLLAMA.value
        or catalog["endpoint"] != CATALOG_ENDPOINT
        or catalog["authentication"] != "account_authenticated"
    ):
        raise CampaignRosterError("provider catalog authority is unsupported")
    catalog_observed_at = _utc_timestamp(catalog["observed_at"], "catalog.observed_at")
    if catalog_observed_at > current + _MAX_CLOCK_SKEW:
        raise CampaignRosterError("provider catalog observation is in the future")
    raw_models = catalog["models"]
    if not isinstance(raw_models, list) or not raw_models:
        raise CampaignRosterError("provider catalog models must be a non-empty list")
    catalog_models = tuple(
        _required_text(model, "provider catalog model", maximum=200)
        for model in raw_models
    )
    if len(set(catalog_models)) != len(catalog_models) or tuple(sorted(catalog_models)) != catalog_models:
        raise CampaignRosterError("provider catalog models must be unique and sorted")

    raw_agents = payload["agents"]
    if not isinstance(raw_agents, list) or len(raw_agents) != 7:
        raise CampaignRosterError("roster must contain exactly seven agent seats")
    seats: list[CampaignAgentSeat] = []
    for index, raw in enumerate(raw_agents):
        if not isinstance(raw, Mapping):
            raise CampaignRosterError(f"agents[{index}] must be an object")
        _exact_keys(raw, _AGENT_KEYS, f"agents[{index}]")
        name = _required_text(raw["name"], f"agents[{index}].name", maximum=100)
        family = _required_text(raw["family"], f"agents[{index}].family", maximum=100)
        model = _required_text(raw["model"], f"agents[{index}].model", maximum=200)
        if not _IDENTIFIER_RE.fullmatch(name) or not _IDENTIFIER_RE.fullmatch(family):
            raise CampaignRosterError("agent names and families must be bounded identifiers")
        if raw["provider"] != ProviderType.OLLAMA.value:
            raise CampaignRosterError("campaign roster currently admits only Ollama seats")
        if not _CLOUD_MODEL_RE.fullmatch(model):
            raise CampaignRosterError("campaign model must be an explicit cloud route")
        if model[:-6] not in catalog_models:
            raise CampaignRosterError("campaign model is absent from the observed catalog")
        try:
            role = AgentRole(_required_text(raw["role"], f"agents[{index}].role"))
        except ValueError as exc:
            raise CampaignRosterError("campaign agent role is unsupported") from exc
        seats.append(
            CampaignAgentSeat(
                name=name,
                role=role,
                provider=ProviderType.OLLAMA,
                model=model,
                family=family,
                thread=_required_text(raw["thread"], f"agents[{index}].thread"),
                system_prompt=_required_text(
                    raw["system_prompt"], f"agents[{index}].system_prompt"
                ),
            )
        )
    for label, values in (
        ("names", [seat.name for seat in seats]),
        ("models", [seat.model for seat in seats]),
        ("families", [seat.family for seat in seats]),
    ):
        if len(set(values)) != 7:
            raise CampaignRosterError(f"campaign agent {label} must be seven-way distinct")

    claims = payload["claims"]
    if not isinstance(claims, Mapping) or set(claims) != {"proves", "does_not_prove"}:
        raise CampaignRosterError("roster claims boundary must be explicit")
    for label in ("proves", "does_not_prove"):
        rows = claims[label]
        if not isinstance(rows, list) or not rows or not all(isinstance(row, str) and row for row in rows):
            raise CampaignRosterError(f"roster claims.{label} must be non-empty text")

    return CampaignAgentRoster(
        campaign_id=campaign_id,
        objective_sha256=objective_sha256,
        activation_at=activation_at,
        expires_at=expires_at,
        catalog_observed_at=catalog_observed_at,
        catalog_models=catalog_models,
        seats=tuple(seats),
        manifest_sha256=observed_sha256,
    )


def _state_matches(seat: CampaignAgentSeat, state: AgentState) -> bool:
    return bool(
        state.name == seat.name
        and state.role is seat.role
        and state.provider == seat.provider.value
        and state.model == seat.model
        and state.status not in {AgentStatus.DEAD, AgentStatus.STOPPING}
    )


async def ensure_campaign_agent_roster(
    swarm: CampaignRosterSwarm,
    roster: CampaignAgentRoster,
) -> CampaignRosterReceipt:
    """Reconcile all names before effects, then spawn only missing exact seats."""
    states = await swarm.list_agents()
    by_name: dict[str, list[AgentState]] = {}
    for state in states:
        by_name.setdefault(state.name, []).append(state)

    existing: dict[str, AgentState] = {}
    missing: list[CampaignAgentSeat] = []
    for seat in roster.seats:
        matches = by_name.get(seat.name, [])
        if len(matches) > 1:
            raise CampaignRosterError(
                f"campaign roster name {seat.name!r} resolves to multiple live states"
            )
        if not matches:
            missing.append(seat)
            continue
        state = matches[0]
        if not _state_matches(seat, state):
            raise CampaignRosterError(
                f"campaign roster name {seat.name!r} resolves to a mismatched state"
            )
        existing[seat.name] = state

    spawned: dict[str, AgentState] = {}
    for seat in missing:
        state = await swarm.spawn_agent(
            name=seat.name,
            role=seat.role,
            model=seat.model,
            provider_type=seat.provider,
            system_prompt=seat.system_prompt,
            thread=seat.thread,
        )
        if not _state_matches(seat, state):
            raise CampaignRosterError(
                f"spawned campaign roster seat {seat.name!r} did not match"
            )
        spawned[seat.name] = state

    final_states = await swarm.list_agents()
    final_by_name: dict[str, list[AgentState]] = {}
    for state in final_states:
        final_by_name.setdefault(state.name, []).append(state)
    bindings: list[CampaignAgentBinding] = []
    for seat in roster.seats:
        matches = final_by_name.get(seat.name, [])
        if len(matches) != 1 or not _state_matches(seat, matches[0]):
            raise CampaignRosterError(
                f"campaign roster seat {seat.name!r} lost exact identity after reconciliation"
            )
        state = matches[0]
        bindings.append(
            CampaignAgentBinding(
                name=seat.name,
                agent_id=state.id,
                role=state.role.value,
                provider=state.provider,
                model=state.model,
                family=seat.family,
                disposition="existing" if seat.name in existing else "spawned",
            )
        )
    return CampaignRosterReceipt(
        campaign_id=roster.campaign_id,
        manifest_sha256=roster.manifest_sha256,
        bindings=tuple(bindings),
    )


__all__ = [
    "CampaignAgentBinding",
    "CampaignAgentRoster",
    "CampaignAgentSeat",
    "CampaignRosterError",
    "CampaignRosterReceipt",
    "ensure_campaign_agent_roster",
    "load_campaign_agent_roster",
]
