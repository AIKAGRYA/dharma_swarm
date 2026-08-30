"""Pure route catalog and activation-plan contract for RSI Lab model roles.

This module only projects the canonical source-owned model pool.  It never
loads credentials, calls providers, mutates host state, or grants promotion
authority.  Stateful activation and rollback live in ``model_onboarding``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from dharma_swarm.forge_lab.state_io import content_digest, validate_digest
from dharma_swarm.model_pool import all_entries
from dharma_swarm.models import ProviderType

CATALOG_SCHEMA = "rsi_lab.model_route_catalog.v1"
PLAN_SCHEMA = "rsi_lab.model_role_activation_plan.v1"
PROFILE_SCHEMA = "rsi_lab.model_role_activation_profile.v1"
RECEIPT_SCHEMA = "rsi_lab.model_role_activation_receipt.v1"
STATUS_SCHEMA = "rsi_lab.model_role_activation_status.v1"
RESULT_SCHEMA = "rsi_lab.model_role_activation_result.v1"


class ModelRole(str, Enum):
    MUTATOR = "mutator"
    SOLVER = "solver"
    VERIFIER = "verifier"


ROLE_ORDER = (ModelRole.MUTATOR, ModelRole.SOLVER, ModelRole.VERIFIER)
ROLE_VALUES = tuple(role.value for role in ROLE_ORDER)

CLAIM_BOUNDARY: dict[str, Any] = {
    "authority": "role_selection_only",
    "credentials_loaded": False,
    "provider_calls": False,
    "source_edits": False,
    "weights_changed": False,
    "availability_attested": False,
    "quality_attested": False,
    "promotion_authority": False,
}


class ModelOnboardingError(RuntimeError):
    """A model-role activation operation failed closed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class RoleBinding:
    """Operator-requested exact route for one RSI Lab role."""

    role: ModelRole
    provider: str
    model_id: str

    @classmethod
    def from_value(cls, value: RoleBinding | Mapping[str, Any]) -> RoleBinding:
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise ModelOnboardingError(
                "INVALID_BINDING", "each role binding must be an object"
            )
        try:
            role = ModelRole(str(value.get("role") or "").strip().casefold())
        except ValueError as exc:
            raise ModelOnboardingError(
                "INVALID_ROLE", f"role must be one of {', '.join(ROLE_VALUES)}"
            ) from exc
        provider = _clean_route_token(value.get("provider"), field="provider")
        model_id = _clean_route_token(value.get("model_id"), field="model_id")
        return cls(role=role, provider=provider.casefold(), model_id=model_id)


def _clean_route_token(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 256 or any(ord(char) < 32 for char in text):
        raise ModelOnboardingError(
            "INVALID_BINDING", f"{field} must be a non-empty route token"
        )
    return text


def _unsigned(payload: Mapping[str, Any], digest_field: str) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != digest_field}


def _signed(payload: Mapping[str, Any], digest_field: str) -> dict[str, Any]:
    unsigned = dict(payload)
    return {**unsigned, digest_field: content_digest(unsigned)}


def _catalog_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in all_entries():
        tier = getattr(entry.tier, "value", str(entry.tier))
        for route in entry.routes:
            rows.append(
                {
                    "provider": route.provider.value,
                    "model_id": route.model_id,
                    "logical_model_id": entry.id,
                    "tier": tier,
                    "below_floor": bool(entry.below_floor),
                }
            )
    providers_by_model: dict[str, set[str]] = {}
    for row in rows:
        providers_by_model.setdefault(str(row["model_id"]), set()).add(
            str(row["provider"])
        )
    for row in rows:
        providers = sorted(providers_by_model[str(row["model_id"])])
        row["runtime_selectable"] = len(providers) == 1
        row["runtime_providers"] = providers
        row["runtime_blocker"] = (
            None if len(providers) == 1 else "provider_qualified_execution_required"
        )
    return sorted(
        rows,
        key=lambda row: (
            str(row["provider"]),
            str(row["model_id"]),
            str(row["logical_model_id"]),
        ),
    )


def list_supported_routes() -> dict[str, Any]:
    """Return the deterministic, credential-free exact-route projection."""

    unsigned = {
        "schema": CATALOG_SCHEMA,
        "source": "dharma_swarm.model_pool",
        "roles": list(ROLE_VALUES),
        "routes": _catalog_rows(),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return {**unsigned, "catalog_digest": content_digest(unsigned)}


def _route_index() -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row["provider"]), str(row["model_id"])): row
        for row in list_supported_routes()["routes"]
    }


def _ordered_unique_models(bindings: Iterable[Mapping[str, Any]]) -> list[str]:
    by_role = {str(binding["role"]): binding for binding in bindings}
    models: list[str] = []
    for role in ROLE_VALUES:
        binding = by_role.get(role)
        if binding is None:
            continue
        model_id = str(binding["model_id"])
        if model_id not in models:
            models.append(model_id)
    return models


def plan_activation(
    bindings: Iterable[RoleBinding | Mapping[str, Any]],
    *,
    expected_current_digest: str | None = None,
) -> dict[str, Any]:
    """Purely plan one exact role profile; no filesystem or provider writes."""

    if expected_current_digest is not None:
        try:
            validate_digest(expected_current_digest)
        except ValueError as exc:
            raise ModelOnboardingError("INVALID_DIGEST", str(exc)) from exc

    requested = [RoleBinding.from_value(binding) for binding in bindings]
    seen_roles: set[ModelRole] = set()
    duplicate_roles: list[str] = []
    for binding in requested:
        if binding.role in seen_roles:
            duplicate_roles.append(binding.role.value)
        seen_roles.add(binding.role)

    route_index = _route_index()
    known_providers = {provider.value for provider in ProviderType}
    planned: list[dict[str, Any]] = []
    blockers: list[str] = []
    unknown_transport = unknown_route = runtime_ambiguity = False
    for binding in requested:
        supported = route_index.get((binding.provider, binding.model_id))
        if binding.provider not in known_providers:
            unknown_transport = True
            blockers.append(
                f"implementation_required:{binding.role.value}:{binding.provider}"
            )
        elif supported is None:
            unknown_route = True
            blockers.append(
                "source_change_required:"
                f"{binding.role.value}:{binding.provider}:{binding.model_id}"
            )
        elif not supported.get("runtime_selectable"):
            runtime_ambiguity = True
            blockers.append(
                "implementation_required:provider_qualified_execution:"
                f"{binding.role.value}:{binding.provider}:{binding.model_id}"
            )
        planned.append(
            {
                "role": binding.role.value,
                "provider": binding.provider,
                "model_id": binding.model_id,
                "logical_model_id": (
                    supported.get("logical_model_id") if supported else None
                ),
                "tier": supported.get("tier") if supported else None,
                "below_floor": supported.get("below_floor") if supported else None,
                "runtime_selectable": (
                    supported.get("runtime_selectable") if supported else None
                ),
                "runtime_blocker": (
                    supported.get("runtime_blocker") if supported else None
                ),
            }
        )

    requested_roles = {binding.role.value for binding in requested}
    missing_roles = [role for role in ROLE_VALUES if role not in requested_roles]
    blockers.extend(f"missing_role:{role}" for role in missing_roles)
    blockers.extend(f"duplicate_role:{role}" for role in sorted(set(duplicate_roles)))
    planned.sort(
        key=lambda row: (
            ROLE_VALUES.index(str(row["role"])),
            str(row["provider"]),
            str(row["model_id"]),
        )
    )
    blockers = sorted(set(blockers))
    if unknown_transport or runtime_ambiguity:
        outcome = "implementation_required"
    elif unknown_route:
        outcome = "source_change_required"
    elif missing_roles or duplicate_roles:
        outcome = "invalid_request"
    else:
        outcome = "ready"

    catalog = list_supported_routes()
    unsigned = {
        "schema": PLAN_SCHEMA,
        "base_profile_digest": expected_current_digest,
        "catalog_digest": catalog["catalog_digest"],
        "role_order": list(ROLE_VALUES),
        "bindings": planned,
        "staged_models": _ordered_unique_models(planned),
        "outcome": outcome,
        "blockers": blockers,
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return {**unsigned, "plan_digest": content_digest(unsigned)}


def _validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(plan)
    if payload.get("schema") != PLAN_SCHEMA:
        raise ModelOnboardingError("INVALID_PLAN", "unsupported activation plan schema")
    claimed = str(payload.get("plan_digest") or "")
    if claimed != content_digest(_unsigned(payload, "plan_digest")):
        raise ModelOnboardingError("PLAN_TAMPERED", "activation plan digest mismatch")
    raw_bindings = payload.get("bindings")
    if not isinstance(raw_bindings, list):
        raise ModelOnboardingError("INVALID_PLAN", "activation plan bindings are invalid")
    replay = plan_activation(
        [
            {
                "role": row.get("role"),
                "provider": row.get("provider"),
                "model_id": row.get("model_id"),
            }
            for row in raw_bindings
            if isinstance(row, Mapping)
        ],
        expected_current_digest=payload.get("base_profile_digest"),
    )
    if replay != payload:
        if replay.get("catalog_digest") != payload.get("catalog_digest"):
            raise ModelOnboardingError(
                "STALE_ROUTE_CATALOG",
                "canonical exact-route catalog changed after planning",
            )
        raise ModelOnboardingError("INVALID_PLAN", "activation plan is not canonical")
    return payload


def _validate_profile(payload: Mapping[str, Any]) -> dict[str, Any]:
    profile = dict(payload)
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ModelOnboardingError("PROFILE_INVALID", "unsupported profile schema")
    claimed = str(profile.get("profile_digest") or "")
    if claimed != content_digest(_unsigned(profile, "profile_digest")):
        raise ModelOnboardingError("PROFILE_INVALID", "profile digest mismatch")
    bindings = profile.get("bindings")
    if (
        not isinstance(bindings, list)
        or not all(isinstance(row, Mapping) for row in bindings)
        or [row.get("role") for row in bindings] != list(ROLE_VALUES)
    ):
        raise ModelOnboardingError(
            "PROFILE_INVALID", "profile role bindings are incomplete"
        )
    route_index = _route_index()
    for row in bindings:
        canonical = route_index.get((str(row.get("provider")), str(row.get("model_id"))))
        compared_fields = (
            "logical_model_id",
            "tier",
            "below_floor",
            "runtime_selectable",
            "runtime_blocker",
        )
        if canonical is None or any(
            row.get(field) != canonical.get(field) for field in compared_fields
        ):
            raise ModelOnboardingError(
                "PROFILE_ROUTE_UNSUPPORTED",
                "profile no longer resolves to exact routes",
            )
    if profile.get("staged_models") != _ordered_unique_models(bindings):
        raise ModelOnboardingError(
            "PROFILE_INVALID", "profile staged model order drifted"
        )
    if profile.get("claim_boundary") != CLAIM_BOUNDARY:
        raise ModelOnboardingError("PROFILE_INVALID", "profile claim boundary drifted")
    return profile


__all__ = [
    "CATALOG_SCHEMA",
    "CLAIM_BOUNDARY",
    "ModelOnboardingError",
    "ModelRole",
    "PLAN_SCHEMA",
    "PROFILE_SCHEMA",
    "RECEIPT_SCHEMA",
    "RESULT_SCHEMA",
    "ROLE_ORDER",
    "RoleBinding",
    "STATUS_SCHEMA",
    "list_supported_routes",
    "plan_activation",
]
