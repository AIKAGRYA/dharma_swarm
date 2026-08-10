"""Build and verify signed, manifest-bound provider-route attestations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from dharma_swarm.forge_lab.provider_attestation_contract import (
    DEFAULT_ATTESTATION_TTL_SECONDS,
    DIGEST_RE,
    KEY_ID_RE,
    NONCE_RE,
    PROVIDER_ATTESTATION_SCHEMA,
    PROVIDER_PROBE_AUTHORITY_SCHEMA,
    UNATTENDED_MIN_INDEPENDENT_TRANSPORTS,
    ProviderAttestationError,
    attestation_policy,
    definition,
    fail,
    format_timestamp,
    normalized_model_identity,
    parse_timestamp,
    physical_transport_digest,
    provider_attestation_digest,
    provider_route_config_digest,
    role_bindings,
    utc_now,
    verified_manifest_digest,
)
from dharma_swarm.forge_lab.provider_probe_trust import (
    ProviderSignatureVerifier,
    attestation_signing_bytes,
    signing_public_key,
    verify_attestation_signature,
)


_TOP_KEYS = {
    "schema",
    "profile",
    "manifest_digest",
    "release",
    "config_digest",
    "checked_at",
    "expires_at",
    "probe_authority",
    "roles",
    "callable_count",
    "independent_transport_count",
    "route_diversity",
    "unattended",
    "signer",
    "attestation_digest",
    "signature",
}
_ROLE_KEYS = {
    "binding",
    "requested_model",
    "served_model",
    "model_family",
    "provider",
    "provider_family",
    "physical_transport_digest",
    "callable",
    "live",
    "stage",
    "fallback",
}


def _model_family(model_id: str) -> str:
    from dharma_swarm.forge_v1.forge_v2.critic import _family

    return _family(model_id)


def _route_diversity(roles: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    callable_rows = [row for row in roles.values() if row.get("callable") is True]
    return {
        "distinct_physical_transport_count": len(
            {row.get("physical_transport_digest") for row in callable_rows}
        ),
        "distinct_model_family_count": len(
            {row.get("model_family") for row in callable_rows}
        ),
        "distinct_provider_family_count": len(
            {row.get("provider_family") for row in callable_rows}
        ),
        "decorrelation_claimed": False,
    }


def build_provider_attestation(
    manifest: Mapping[str, Any],
    *,
    role_rows: Mapping[str, Mapping[str, Any]],
    probe_request_nonce: str,
    probe_fencing_token: int,
    signing_key_id: str,
    signing_key: Any,
    probe_authority_id: str | None = None,
    checked_at: datetime | None = None,
    ttl_seconds: int = DEFAULT_ATTESTATION_TTL_SECONDS,
    unattended: bool = True,
    validate: bool = True,
    trusted_public_keys: Mapping[str, str | bytes] | None = None,
) -> dict[str, Any]:
    """Build a signed, redacted receipt inside the governed probe broker."""

    manifest_id = verified_manifest_digest(manifest)
    policy = attestation_policy(manifest)
    bindings = role_bindings(manifest)
    if set(role_rows) != set(policy["required_roles"]):
        fail("ROLE_BINDING_MISMATCH", "probe rows do not exactly cover required roles")
    if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or ttl_seconds < 1:
        fail("INVALID_ATTESTATION_TIME", "attestation TTL must be positive")
    authority = probe_authority_id or policy["required_probe_authority"]
    if authority != policy["required_probe_authority"]:
        fail("PROBE_AUTHORITY_MISMATCH", "probe authority disagrees with policy")
    if not NONCE_RE.fullmatch(str(probe_request_nonce or "")):
        fail("PROBE_NONCE_INVALID", "provider probe request nonce is malformed")
    if (
        not isinstance(probe_fencing_token, int)
        or isinstance(probe_fencing_token, bool)
        or probe_fencing_token <= 0
    ):
        fail("PROBE_FENCE_INVALID", "provider probe fence must be positive")
    if not KEY_ID_RE.fullmatch(str(signing_key_id or "")):
        fail("INVALID_PROVIDER_PROBE_SIGNER", "provider probe key id is invalid")
    sign = getattr(signing_key, "sign", signing_key)
    if not callable(sign):
        fail("INVALID_PROVIDER_PROBE_SIGNER", "provider probe signer is not callable")

    roles: dict[str, dict[str, Any]] = {}
    for role in policy["required_roles"]:
        row = role_rows[role]
        if not isinstance(row, Mapping):
            fail("ROLE_BINDING_MISMATCH", f"provider row for {role} is not an object")
        requested = str(row.get("requested_model") or "").strip()
        served = str(row.get("served_model") or "").strip()
        provider = str(row.get("provider") or "").strip()
        roles[role] = {
            "binding": bindings[role],
            "requested_model": requested,
            "served_model": served,
            "model_family": str(row.get("model_family") or _model_family(served)).strip(),
            "provider": provider,
            "provider_family": str(row.get("provider_family") or provider).strip(),
            "physical_transport_digest": physical_transport_digest(row),
            "callable": row.get("callable") is True,
            "live": row.get("live") is True,
            "stage": str(row.get("stage") or ""),
            "fallback": row.get("fallback") is True,
        }

    observed = checked_at or utc_now()
    if observed.tzinfo is None or observed.utcoffset() is None:
        fail("INVALID_ATTESTATION_TIME", "checked_at must be timezone-aware")
    observed = observed.astimezone(timezone.utc).replace(microsecond=0)
    source = definition(manifest).get("source")
    if not isinstance(source, Mapping):
        fail("RELEASE_MISMATCH", "manifest source identity is absent")
    diversity = _route_diversity(roles)
    receipt: dict[str, Any] = {
        "schema": PROVIDER_ATTESTATION_SCHEMA,
        "profile": str(definition(manifest).get("campaign_name") or ""),
        "manifest_digest": manifest_id,
        "release": {
            "commit": source.get("release_commit"),
            "tree": source.get("release_tree"),
        },
        "config_digest": provider_route_config_digest(roles),
        "checked_at": format_timestamp(observed),
        "expires_at": format_timestamp(observed + timedelta(seconds=ttl_seconds)),
        "probe_authority": {
            "schema": PROVIDER_PROBE_AUTHORITY_SCHEMA,
            "authority_id": authority,
            "request_nonce": probe_request_nonce,
            "fencing_token": probe_fencing_token,
        },
        "roles": roles,
        "callable_count": sum(row["callable"] is True for row in roles.values()),
        "independent_transport_count": diversity["distinct_physical_transport_count"],
        "route_diversity": diversity,
        "unattended": bool(unattended),
        "signer": {"algorithm": "ed25519", "key_id": signing_key_id},
    }
    receipt["attestation_digest"] = provider_attestation_digest(receipt)
    try:
        signature = sign(attestation_signing_bytes(receipt))
    except Exception as exc:
        raise ProviderAttestationError(
            "INVALID_PROVIDER_PROBE_SIGNER",
            f"provider probe signer failed: {type(exc).__name__}",
        ) from exc
    if not isinstance(signature, bytes) or len(signature) != 64:
        fail("INVALID_PROVIDER_PROBE_SIGNER", "signer did not return 64 bytes")
    receipt["signature"] = signature.hex()
    if validate:
        validation_keys = trusted_public_keys
        if validation_keys is None and (derived := signing_public_key(signing_key)):
            validation_keys = {signing_key_id: derived}
        verify_provider_attestation(
            manifest,
            receipt,
            now=observed,
            unattended=unattended,
            trusted_public_keys=validation_keys,
            expected_probe_request_nonce=probe_request_nonce,
            expected_probe_fencing_token=probe_fencing_token,
        )
    return receipt


def _verified_probe_binding(
    receipt: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    unattended: bool,
    expected_nonce: str | None,
    expected_fence: int | None,
) -> dict[str, Any]:
    probe = receipt.get("probe_authority")
    if (
        not isinstance(probe, Mapping)
        or set(probe) != {"schema", "authority_id", "request_nonce", "fencing_token"}
        or probe.get("schema") != PROVIDER_PROBE_AUTHORITY_SCHEMA
    ):
        fail("PROBE_AUTHORITY_INVALID", "provider probe binding is malformed")
    if probe.get("authority_id") != policy["required_probe_authority"]:
        fail("PROBE_AUTHORITY_MISMATCH", "provider probe authority disagrees")
    nonce = str(probe.get("request_nonce") or "")
    fence = probe.get("fencing_token")
    if not NONCE_RE.fullmatch(nonce):
        fail("PROBE_NONCE_INVALID", "provider probe request nonce is malformed")
    if not isinstance(fence, int) or isinstance(fence, bool) or fence <= 0:
        fail("PROBE_FENCE_INVALID", "provider probe fence must be positive")
    if unattended and (not expected_nonce or expected_fence is None):
        fail("PROBE_BINDING_REQUIRED", "expected probe nonce and fence are required")
    if unattended and nonce != expected_nonce:
        fail("PROBE_NONCE_MISMATCH", "provider probe receipt belongs to another request")
    if unattended and fence != expected_fence:
        fail("PROBE_FENCE_MISMATCH", "provider probe receipt belongs to another fence")
    return dict(probe)


def _verified_roles(
    receipt: Mapping[str, Any],
    policy: Mapping[str, Any],
    bindings: Mapping[str, str],
) -> tuple[dict[str, dict[str, str]], Mapping[str, Mapping[str, Any]]]:
    roles = receipt.get("roles")
    if not isinstance(roles, Mapping) or set(roles) != set(policy["required_roles"]):
        fail("ROLE_BINDING_MISMATCH", "attested roles do not exactly match policy")
    safe: dict[str, dict[str, str]] = {}
    for role in policy["required_roles"]:
        row = roles[role]
        if not isinstance(row, Mapping) or set(row) != _ROLE_KEYS:
            fail("ROLE_BINDING_MISMATCH", f"attested role {role} shape disagrees")
        if row.get("binding") != bindings[role]:
            fail("ROLE_BINDING_MISMATCH", f"attested binding for {role} disagrees")
        requested, served = str(row.get("requested_model") or "").strip(), str(
            row.get("served_model") or ""
        ).strip()
        model_family = str(row.get("model_family") or "").strip()
        provider, provider_family = str(row.get("provider") or "").strip(), str(
            row.get("provider_family") or ""
        ).strip()
        transport = str(row.get("physical_transport_digest") or "")
        if not all((requested, served, model_family, provider, provider_family)) or not DIGEST_RE.fullmatch(transport):
            fail("ZERO_OR_INCOMPLETE_ROUTES", f"attested route for {role} is incomplete")
        if normalized_model_identity(requested) != normalized_model_identity(served):
            fail("SERVED_MODEL_MISMATCH", f"served identity for {role} disagrees")
        if not (
            row.get("callable") is True
            and row.get("live") is True
            and row.get("stage") == "complete"
            and row.get("fallback") is False
        ):
            fail("ZERO_OR_INCOMPLETE_ROUTES", f"attested route for {role} is not callable")
        safe[role] = {
            "requested_model": requested,
            "served_model": served,
            "model_family": model_family,
            "provider": provider,
            "provider_family": provider_family,
            "physical_transport_digest": transport,
        }
    return safe, roles


def verify_provider_attestation(
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    now: datetime | None = None,
    unattended: bool = True,
    trusted_public_keys: Mapping[str, str | bytes] | None = None,
    signature_verifier: ProviderSignatureVerifier | None = None,
    expected_probe_request_nonce: str | None = None,
    expected_probe_fencing_token: int | None = None,
) -> dict[str, Any]:
    """Verify authenticity, freshness, request binding, and route evidence."""

    if not isinstance(receipt, Mapping):
        fail("INVALID_PROVIDER_ATTESTATION", "provider attestation is not an object")
    manifest_id = verified_manifest_digest(manifest)
    policy, bindings = attestation_policy(manifest), role_bindings(manifest)
    if receipt.get("schema") != PROVIDER_ATTESTATION_SCHEMA:
        fail("INVALID_PROVIDER_ATTESTATION", "provider attestation schema is unsupported")
    if "signature" not in receipt or not receipt.get("signature"):
        fail("PROVIDER_ATTESTATION_UNSIGNED", "provider attestation has no signature")
    if set(receipt) != _TOP_KEYS:
        fail("INVALID_PROVIDER_ATTESTATION", "provider attestation shape is not exact")
    declared = receipt.get("attestation_digest")
    if not DIGEST_RE.fullmatch(str(declared or "")) or declared != provider_attestation_digest(receipt):
        fail("ATTESTATION_DIGEST_MISMATCH", "provider attestation digest disagrees")
    key_id = verify_attestation_signature(
        receipt,
        trusted_public_keys=trusted_public_keys,
        signature_verifier=signature_verifier,
    )
    if receipt.get("manifest_digest") != manifest_id:
        fail("MANIFEST_DIGEST_MISMATCH", "provider attestation targets another manifest")
    expected_profile = str(definition(manifest).get("campaign_name") or "")
    if receipt.get("profile") != expected_profile:
        fail("MANIFEST_DIGEST_MISMATCH", "provider attestation profile disagrees")
    source, release = definition(manifest).get("source"), receipt.get("release")
    expected_release = {
        "commit": source.get("release_commit") if isinstance(source, Mapping) else None,
        "tree": source.get("release_tree") if isinstance(source, Mapping) else None,
    }
    if not isinstance(release, Mapping) or release != expected_release:
        fail("RELEASE_MISMATCH", "provider attestation release identity disagrees")
    probe = _verified_probe_binding(
        receipt,
        policy,
        unattended=unattended,
        expected_nonce=expected_probe_request_nonce,
        expected_fence=expected_probe_fencing_token,
    )

    checked = parse_timestamp(receipt.get("checked_at"), field="checked_at")
    expires = parse_timestamp(receipt.get("expires_at"), field="expires_at")
    observed = now or utc_now()
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("attestation verification time must be timezone-aware")
    observed = observed.astimezone(timezone.utc)
    if checked > observed:
        fail("ATTESTATION_FROM_FUTURE", "provider attestation is from the future")
    if expires <= observed:
        fail("ATTESTATION_EXPIRED", "provider attestation has expired")
    lifetime = (expires - checked).total_seconds()
    if lifetime <= 0 or lifetime > policy["max_age_seconds"]:
        fail("ATTESTATION_TTL_EXCEEDED", "provider attestation TTL exceeds policy")

    safe_roles, roles = _verified_roles(receipt, policy, bindings)
    config_digest = provider_route_config_digest(roles)
    if receipt.get("config_digest") != config_digest:
        fail("CONFIG_DIGEST_MISMATCH", "attested route configuration disagrees")
    if policy.get("config_digest") not in (None, config_digest):
        fail("CONFIG_DIGEST_MISMATCH", "attestation differs from pinned configuration")
    if receipt.get("callable_count") != len(safe_roles) or not safe_roles:
        fail("ZERO_OR_INCOMPLETE_ROUTES", "provider attestation has no callable routes")
    diversity = _route_diversity(roles)
    transports = diversity["distinct_physical_transport_count"]
    if receipt.get("independent_transport_count") != transports:
        fail("INDEPENDENT_TRANSPORT_COUNT_MISMATCH", "transport count disagrees")
    if receipt.get("route_diversity") != diversity:
        fail("ROUTE_DIVERSITY_MISMATCH", "provider/model diversity counts disagree")
    if unattended and receipt.get("unattended") is not True:
        fail("UNATTENDED_ATTESTATION_REQUIRED", "interactive receipt cannot power work")
    minimum = max(UNATTENDED_MIN_INDEPENDENT_TRANSPORTS, policy["min_independent_transports"])
    if unattended and transports < minimum:
        fail(
            "INSUFFICIENT_INDEPENDENT_TRANSPORTS",
            f"independent physical transports: {transports}/{minimum}",
        )
    return {
        "schema": PROVIDER_ATTESTATION_SCHEMA,
        "attestation_digest": declared,
        "manifest_digest": manifest_id,
        "config_digest": config_digest,
        "release": dict(release),
        "checked_at": receipt["checked_at"],
        "expires_at": receipt["expires_at"],
        "independent_transport_count": transports,
        "route_diversity": diversity,
        "transport_independence_scope": "distinct physical transport digests only",
        "probe_authority": probe,
        "signing_key_id": key_id,
        "roles": safe_roles,
    }
