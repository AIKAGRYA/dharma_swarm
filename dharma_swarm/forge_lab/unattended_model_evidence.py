"""Exact model-profile and provider-receipt binding for unattended runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class ModelEvidenceError(RuntimeError):
    """Internal typed refusal translated by the unattended runner."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def binding_core(rows: Any) -> list[dict[str, str]]:
    """Return the stable identity-bearing fields from ordered role bindings."""

    if not isinstance(rows, list):
        return []
    bindings: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            return []
        bindings.append(
            {
                "role": str(row.get("role") or "").strip().casefold(),
                "provider": str(row.get("provider") or "").strip().casefold(),
                "model_id": str(row.get("model_id") or "").strip(),
            }
        )
    return bindings


def selected_model_evidence(
    provider_check: dict[str, Any],
    *,
    model_roles: tuple[str, ...],
    activation_status_fn: Callable[[], dict[str, Any]],
    validate_provider_receipt_fn: Callable[..., list[str]],
    safe_json_fn: Callable[[Path], dict[str, Any] | None],
) -> dict[str, Any]:
    """Bind active role assignments to one fresh, exact provider receipt."""

    receipt_path = provider_check.get("receipt")
    path = Path(str(receipt_path)) if receipt_path else None
    payload = safe_json_fn(path) if path is not None else None
    if payload is None or path is None:
        raise ModelEvidenceError(
            "PROVIDER_RECEIPT_MISSING",
            "fresh provider receipt is unreadable",
        )
    failures = validate_provider_receipt_fn(payload, path=path)
    if failures:
        raise ModelEvidenceError("PROVIDER_RECEIPT_INVALID", ",".join(failures))
    if payload.get("profile") != "staged" or not payload.get("live") or not payload.get("ok"):
        raise ModelEvidenceError(
            "PROVIDER_RECEIPT_SCOPE",
            "unattended execution requires a successful live staged receipt",
        )

    try:
        activation = activation_status_fn()
    except Exception as exc:
        raise ModelEvidenceError("MODEL_PROFILE_INVALID", str(exc)) from exc
    if not activation.get("active") or activation.get("integrity") != "verified":
        raise ModelEvidenceError(
            "MODEL_PROFILE_MISSING",
            "an integrity-verified model-role profile is required",
        )
    profile_digest = str(activation.get("current_profile_digest") or "")
    bindings = binding_core(activation.get("role_bindings"))
    if [binding["role"] for binding in bindings] != list(model_roles):
        raise ModelEvidenceError(
            "MODEL_PROFILE_INCOMPLETE",
            "active profile must bind mutator, solver, and verifier",
        )

    policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
    configuration = (
        policy.get("configuration")
        if isinstance(policy.get("configuration"), dict)
        else {}
    )
    selection = (
        configuration.get("model_selection")
        if isinstance(configuration.get("model_selection"), dict)
        else {}
    )
    if (
        selection.get("source") != "active_model_role_profile"
        or selection.get("activation_profile_digest") != profile_digest
        or binding_core(selection.get("role_bindings")) != bindings
    ):
        raise ModelEvidenceError(
            "PROVIDER_RECEIPT_PROFILE_MISMATCH",
            "provider receipt is not bound to the current role profile",
        )

    callable_routes: set[tuple[str, str]] = set()
    for row in payload.get("rows") or []:
        if not isinstance(row, dict) or not row.get("callable"):
            continue
        provider = str(row.get("provider") or "").strip().casefold()
        model = str(row.get("requested_model") or row.get("model_id") or "").strip()
        if provider and model:
            callable_routes.add((provider, model))
    missing = [
        binding["role"]
        for binding in bindings
        if (binding["provider"], binding["model_id"]) not in callable_routes
    ]
    if missing:
        raise ModelEvidenceError(
            "ROLE_ROUTE_NOT_CALLABLE",
            "receipt lacks exact callable roles: " + ",".join(missing),
        )
    by_role = {binding["role"]: binding for binding in bindings}
    if by_role["solver"]["provider"] == by_role["verifier"]["provider"]:
        raise ModelEvidenceError(
            "SOLVER_VERIFIER_NOT_INDEPENDENT",
            "solver and verifier must use independently attested providers",
        )

    routes: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for binding in bindings:
        route = (binding["provider"], binding["model_id"])
        if route not in seen:
            seen.add(route)
            routes.append({"provider": route[0], "model_id": route[1]})
    providers = {route["provider"] for route in routes}
    if len(providers) < 2:
        raise ModelEvidenceError(
            "TWO_PROVIDER_POLICY",
            f"callable independent providers: {len(providers)}/2",
        )
    return {
        "role_bindings": {binding["role"]: binding for binding in bindings},
        "routes": routes,
        "model_profile_digest": profile_digest,
        "provider_receipt_digest": payload.get("receipt_digest"),
    }


__all__ = ["ModelEvidenceError", "binding_core", "selected_model_evidence"]
