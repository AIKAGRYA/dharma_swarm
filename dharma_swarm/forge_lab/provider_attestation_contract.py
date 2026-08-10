"""Pure schemas, bindings, and digests for provider-probe attestations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any


PROVIDER_ATTESTATION_SCHEMA = "rsi_lab.provider_attestation.v1"
PROVIDER_ROUTE_CONFIG_SCHEMA = "rsi_lab.provider_route_config.v1"
PROVIDER_PROBE_AUTHORITY_SCHEMA = "rsi_lab.provider_probe_authority.v1"
PROVIDER_PROBE_TRUST_SCHEMA = "rsi_lab.provider_probe_trust.v1"
DEFAULT_ATTESTATION_TTL_SECONDS = 300
UNATTENDED_MIN_INDEPENDENT_TRANSPORTS = 2

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
KEY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,95}$")
AUTHORITY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
NONCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,255}$")
SIGNATURE_RE = re.compile(r"^[0-9a-f]{128}$")


class ProviderAttestationError(ValueError):
    """A typed, secret-free provider attestation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise ProviderAttestationError(code, message)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def format_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def parse_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        fail("INVALID_ATTESTATION_TIME", f"{field} must be an RFC3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ProviderAttestationError(
            "INVALID_ATTESTATION_TIME", f"{field} is not an RFC3339 timestamp"
        ) from exc
    if parsed.utcoffset() != timedelta(0):
        fail("INVALID_ATTESTATION_TIME", f"{field} must use UTC")
    return parsed


def canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProviderAttestationError(
            "ATTESTATION_NOT_CANONICAL", "provider attestation is not canonical JSON"
        ) from exc


def sha256_digest(value: str | bytes) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def definition(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    value = manifest.get("definition")
    return value if isinstance(value, Mapping) else manifest


def role_bindings(manifest: Mapping[str, Any]) -> dict[str, str]:
    bootstrap = definition(manifest).get("bootstrap")
    routes = bootstrap.get("role_routes") if isinstance(bootstrap, Mapping) else None
    if isinstance(routes, Mapping) and routes:
        bindings = {str(role): str(binding) for role, binding in routes.items()}
    elif isinstance(bootstrap, Mapping):
        exact = {
            "solver": bootstrap.get("solver_model"),
            "verifier": bootstrap.get("verifier_model"),
            "mutator": bootstrap.get("mutator_model"),
        }
        if any(not isinstance(item, str) or not item for item in exact.values()):
            fail("ROLE_BINDING_MISMATCH", "manifest has no role-bound provider policy")
        bindings = {role: str(binding) for role, binding in exact.items()}
    else:
        fail("ROLE_BINDING_MISMATCH", "manifest has no role-bound provider policy")
    if any(not role or not binding for role, binding in bindings.items()):
        fail("ROLE_BINDING_MISMATCH", "manifest role bindings must be non-empty")
    return bindings


def attestation_policy(manifest: Mapping[str, Any]) -> dict[str, Any]:
    gates = definition(manifest).get("gates")
    policy = gates.get("provider_attestation") if isinstance(gates, Mapping) else None
    if not isinstance(policy, Mapping):
        fail("ATTESTATION_POLICY_MISSING", "manifest has no provider attestation policy")
    bindings = role_bindings(manifest)
    required = policy.get("required_roles")
    if not isinstance(required, list) or not required:
        fail("ATTESTATION_POLICY_INVALID", "required provider roles are absent")
    required_roles = [str(role) for role in required]
    if len(set(required_roles)) != len(required_roles) or set(required_roles) != set(
        bindings
    ):
        fail("ATTESTATION_POLICY_INVALID", "required roles disagree with route bindings")
    try:
        minimum = int(policy.get("min_independent_transports"))
        maximum_age = int(policy.get("max_age_seconds"))
    except (TypeError, ValueError) as exc:
        raise ProviderAttestationError(
            "ATTESTATION_POLICY_INVALID", "provider attestation limits must be integers"
        ) from exc
    authority = str(policy.get("required_probe_authority") or "").strip()
    if minimum < 1 or maximum_age < 1 or not AUTHORITY_ID_RE.fullmatch(authority):
        fail("ATTESTATION_POLICY_INVALID", "provider attestation policy is incomplete")
    config_digest = policy.get("config_digest")
    if config_digest is not None and not DIGEST_RE.fullmatch(str(config_digest)):
        fail("ATTESTATION_POLICY_INVALID", "pinned config digest is malformed")
    return {
        "required_roles": required_roles,
        "min_independent_transports": minimum,
        "max_age_seconds": maximum_age,
        "required_probe_authority": authority,
        "config_digest": config_digest,
    }


def verified_manifest_digest(manifest: Mapping[str, Any]) -> str:
    from dharma_swarm.forge_lab.campaign_contract import manifest_digest

    declared = manifest.get("manifest_digest")
    if not DIGEST_RE.fullmatch(str(declared or "")):
        fail("MANIFEST_DIGEST_MISMATCH", "manifest digest is absent or malformed")
    if declared != manifest_digest(manifest):
        fail("MANIFEST_DIGEST_MISMATCH", "manifest content does not match its digest")
    return str(declared)


def provider_route_config_digest(roles: Mapping[str, Mapping[str, Any]]) -> str:
    projection = {
        role: {
            key: row.get(key)
            for key in (
                "binding",
                "requested_model",
                "served_model",
                "model_family",
                "provider",
                "provider_family",
                "physical_transport_digest",
            )
        }
        for role, row in sorted(roles.items())
    }
    return sha256_digest(
        canonical_json({"schema": PROVIDER_ROUTE_CONFIG_SCHEMA, "roles": projection})
    )


def provider_attestation_digest(receipt: Mapping[str, Any]) -> str:
    payload = dict(receipt)
    payload.pop("attestation_digest", None)
    payload.pop("signature", None)
    return sha256_digest(canonical_json(payload))


def provider_probe_request_nonce(manifest_id: str, fencing_token: int) -> str:
    if not DIGEST_RE.fullmatch(str(manifest_id or "")):
        fail("MANIFEST_DIGEST_MISMATCH", "probe challenge needs a manifest digest")
    if not isinstance(fencing_token, int) or isinstance(fencing_token, bool) or fencing_token <= 0:
        fail("PROBE_FENCE_INVALID", "probe challenge needs a positive fence")
    digest = sha256_digest(
        canonical_json(
            {
                "schema": PROVIDER_PROBE_AUTHORITY_SCHEMA,
                "manifest_digest": manifest_id,
                "fencing_token": fencing_token,
            }
        )
    ).removeprefix("sha256:")
    return f"forge-provider-probe-{digest}"


def physical_transport_digest(row: Mapping[str, Any]) -> str:
    declared = str(row.get("physical_transport_digest") or "")
    if DIGEST_RE.fullmatch(declared):
        return declared
    identity = str(row.get("physical_transport_identity") or "").strip()
    if not identity:
        fail("PHYSICAL_TRANSPORT_UNPROVEN", "route has no physical transport identity")
    return sha256_digest(identity)


def normalized_model_identity(model_id: object) -> str:
    normalized = str(model_id or "").strip().casefold()
    for suffix in (":cloud", "-cloud"):
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized
