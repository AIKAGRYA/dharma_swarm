"""Side-effect-free admission gates for governed Forge Lab campaigns."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.campaign_contract import (
    CampaignContractError,
    verify_operator_envelope,
)
from dharma_swarm.forge_lab.version import source_commit, source_tree_state


def _gate(name: str, passed: bool, code: str, detail: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "code": "PASS" if passed else code,
        "detail": detail,
    }


def _read_json(path: str | None, *, label: str) -> tuple[dict[str, Any] | None, str | None]:
    if not path:
        return None, f"{label}_receipt_missing"
    candidate = Path(path)
    try:
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        return None, f"{label}_receipt_unreadable:{type(exc).__name__}"
    if not isinstance(value, dict):
        return None, f"{label}_receipt_not_object"
    result = value.get("result")
    if isinstance(result, dict):
        value = result
    return value, None


def _definition(manifest: dict[str, Any]) -> dict[str, Any]:
    value = manifest.get("definition")
    return value if isinstance(value, dict) else manifest


def _identity_gate(
    manifest: dict[str, Any],
    receipt_path: str | None,
) -> dict[str, Any]:
    definition = _definition(manifest)
    source = definition.get("source") or {}
    expected_commit = source.get("release_commit")
    expected_tree = source.get("release_tree")
    receipt, error = _read_json(receipt_path, label="identity")
    if error:
        return _gate("code_identity", False, "IDENTITY_RECEIPT_MISSING", error)

    failures: list[str] = []
    canonical = receipt.get("canonical") or {}
    if canonical.get("commit") != expected_commit:
        failures.append("github_commit")
    canonical_tree = canonical.get("tree")
    if canonical_tree not in (None, expected_tree):
        failures.append("github_tree")
    for node in ("mac", "meghadharma"):
        identity = (receipt.get(node) or {}).get("identity") or {}
        if identity.get("commit") != expected_commit:
            failures.append(f"{node}_commit")
        if identity.get("tree") != expected_tree:
            failures.append(f"{node}_tree")
        if identity.get("repo_clean") is not True:
            failures.append(f"{node}_clean")
    if receipt.get("in_sync") is not True:
        failures.append("in_sync")
    # The current sync-status payload is useful semantic evidence, but it is
    # not yet a signed, nonce-bound attestation. Never promote it to authority.
    failures.append("signed_identity_attestation_unimplemented")
    return _gate(
        "code_identity",
        not failures,
        "CODE_IDENTITY_MISMATCH",
        {"expected_commit": expected_commit, "expected_tree": expected_tree, "failures": failures},
    )


def _source_gate(manifest: dict[str, Any]) -> dict[str, Any]:
    source = _definition(manifest).get("source") or {}
    actual_commit = source_commit()
    actual_state = source_tree_state()
    passed = actual_commit == source.get("release_commit") and actual_state == "clean"
    return _gate(
        "controller_source",
        passed,
        "CONTROLLER_SOURCE_NOT_EXACT",
        {
            "expected_commit": source.get("release_commit"),
            "actual_commit": actual_commit,
            "tree_state": actual_state,
        },
    )


def _provider_gate(
    manifest: dict[str, Any],
    receipt_path: str | None,
    *,
    now: datetime | None = None,
    trusted_public_keys: dict[str, str | bytes] | None = None,
    signature_verifier: Any = None,
    expected_probe_request_nonce: str | None = None,
    expected_probe_fencing_token: int | None = None,
) -> dict[str, Any]:
    receipt, error = _read_json(receipt_path, label="provider")
    if error:
        gate_name = (
            "exact_provider_route"
            if "exact_route" in (_definition(manifest).get("gates") or {})
            else "provider_attestation"
        )
        return _gate(gate_name, False, "PROVIDER_RECEIPT_MISSING", error)

    gates = _definition(manifest).get("gates") or {}
    if "exact_route" in gates:
        requested = gates.get("exact_route")
        provider = requested.split(":", 1)[0] if isinstance(requested, str) else None
        exact_rows = [
            row
            for row in receipt.get("rows") or []
            if isinstance(row, dict)
            and row.get("requested_model") == requested
            and row.get("provider") == provider
            and row.get("live") is True
            and row.get("callable") is True
            and row.get("stage") == "complete"
            and not row.get("fallback")
        ]
        # Preserve the historical fail-closed semantics: its old unsigned row
        # format can describe exact Moonshot routing but can never authorize it.
        return _gate(
            "exact_provider_route",
            False,
            "EXACT_PROVIDER_ROUTE_UNPROVEN",
            {
                "requested_model": requested,
                "provider": provider,
                "matching_rows": len(exact_rows),
                "signed_route_attestation": "unimplemented_for_historical_profile",
            },
        )

    from dharma_swarm.forge_lab.provider_selftest import (
        ProviderAttestationError,
        load_trusted_provider_probe_keys,
        verify_provider_attestation,
    )

    trust = trusted_public_keys
    if trust is None and signature_verifier is None:
        trust_path = os.environ.get("RSI_LAB_TRUSTED_PROVIDER_PROBE_KEYS", "").strip()
        if not trust_path:
            return _gate(
                "provider_attestation",
                False,
                "PROVIDER_TRUST_ROOT_MISSING",
                "RSI_LAB_TRUSTED_PROVIDER_PROBE_KEYS is not configured",
            )
        try:
            trust = load_trusted_provider_probe_keys(trust_path)
        except ProviderAttestationError as exc:
            return _gate("provider_attestation", False, exc.code, str(exc))

    try:
        verified = verify_provider_attestation(
            manifest,
            receipt,
            now=now,
            unattended=True,
            trusted_public_keys=trust,
            signature_verifier=signature_verifier,
            expected_probe_request_nonce=expected_probe_request_nonce,
            expected_probe_fencing_token=expected_probe_fencing_token,
        )
    except ProviderAttestationError as exc:
        return _gate("provider_attestation", False, exc.code, str(exc))
    return _gate("provider_attestation", True, "PROVIDER_ATTESTATION_INVALID", verified)


def _active_provider_probe_binding(
    manifest: dict[str, Any], state_root: Path
) -> tuple[str | None, int | None]:
    """Bind a probe receipt to the campaign's live, non-reusable lease fence."""

    from dharma_swarm.forge_lab.campaign_store import CampaignStore
    from dharma_swarm.forge_lab.provider_selftest import provider_probe_request_nonce

    definition = _definition(manifest)
    campaign = str(definition.get("campaign_name") or "")
    manifest_id = str(manifest.get("manifest_digest") or "")
    try:
        active = [
            lease
            for lease in CampaignStore(state_root).active_leases()
            if lease.get("campaign_id") == campaign
            and lease.get("manifest_digest") == manifest_id
        ]
    except Exception:
        return None, None
    if len(active) != 1:
        return None, None
    fence = active[0].get("active_fence")
    if not isinstance(fence, int) or isinstance(fence, bool) or fence <= 0:
        return None, None
    try:
        return provider_probe_request_nonce(manifest_id, fence), fence
    except ValueError:
        return None, None


def _state_gate(state_root: Path, expected_host: str) -> dict[str, Any]:
    logical = Path(os.path.abspath(state_root))
    resolved = state_root.resolve()
    allowed_logical = {
        Path("/root/rsi-lab/state"),
        Path("/root/rsi-lab/current/state"),
    }
    expected = Path("/root/rsi-lab/state").resolve()
    passed = (
        expected_host == "meghadharma"
        and logical in allowed_logical
        and resolved == expected
    )
    return _gate(
        "canonical_state",
        passed,
        "NONCANONICAL_STATE_ROOT",
        {
            "allowed_logical": sorted(str(path) for path in allowed_logical),
            "expected_target": str(expected),
            "actual_logical": str(logical),
            "actual_target": str(resolved),
            "host": expected_host,
        },
    )


def _acceptance_gate() -> dict[str, Any]:
    receipt, error = _read_json(
        os.environ.get("RSI_LAB_LIFECYCLE_ACCEPTANCE_RECEIPT"),
        label="lifecycle_acceptance",
    )
    passed = bool(receipt and receipt.get("ok") is True and not error)
    return _gate(
        "lifecycle_acceptance",
        passed,
        "LIFECYCLE_ACCEPTANCE_UNPROVEN",
        error or {"receipt_schema": receipt.get("schema") if receipt else None},
    )


def _prerequisite_gate(stage: str) -> dict[str, Any]:
    env_name = f"RSI_LAB_{stage.upper()}_CLOSEOUT_RECEIPT"
    receipt, error = _read_json(os.environ.get(env_name), label=stage)
    passed = bool(
        receipt
        and receipt.get("lifecycle_state") == "COMPLETED"
        and receipt.get("clean_closeout") is True
        and not error
    )
    return _gate(
        f"{stage}_clean_closeout",
        passed,
        "PREREQUISITE_CLOSEOUT_MISSING",
        error or {"digest": receipt.get("digest") if receipt else None},
    )


def _envelope_gate(
    manifest: dict[str, Any],
    envelope_path: str | None,
    *,
    expected_host: str,
) -> dict[str, Any]:
    envelope, error = _read_json(envelope_path, label="operator_envelope")
    if error:
        return _gate("operator_envelope", False, "MISSING_OPERATOR_ENVELOPE", error)
    configured_keys = os.environ.get("RSI_LAB_TRUSTED_OPERATOR_KEYS")
    protected_keys = Path(
        "/root/rsi-lab/state/.dharma/forge_lab/trust/operator_keys.json"
    )
    if configured_keys != str(protected_keys):
        return _gate(
            "operator_envelope",
            False,
            "TRUST_ROOT_UNTRUSTED",
            {
                "required_path": str(protected_keys),
                "configured_path": configured_keys,
            },
        )
    try:
        key_stat = protected_keys.lstat()
    except OSError as exc:
        return _gate(
            "operator_envelope",
            False,
            "TRUST_ROOT_MISSING",
            type(exc).__name__,
        )
    if protected_keys.is_symlink() or key_stat.st_uid != 0 or key_stat.st_mode & 0o022:
        return _gate(
            "operator_envelope",
            False,
            "TRUST_ROOT_UNTRUSTED",
            {
                "symlink": protected_keys.is_symlink(),
                "uid": key_stat.st_uid,
                "mode": oct(key_stat.st_mode & 0o777),
            },
        )
    keys, keys_error = _read_json(str(protected_keys), label="trusted_operator_keys")
    if keys_error:
        return _gate("operator_envelope", False, "TRUST_ROOT_MISSING", keys_error)
    trusted = keys.get("keys") if isinstance(keys.get("keys"), dict) else keys
    try:
        verified = verify_operator_envelope(
            envelope,
            manifest,
            trusted_public_keys=trusted,
            expected_host=expected_host,
        )
    except (CampaignContractError, ValueError, TypeError) as exc:
        return _gate(
            "operator_envelope",
            False,
            getattr(exc, "code", "INVALID_OPERATOR_ENVELOPE"),
            str(exc),
        )
    return _gate(
        "operator_envelope",
        True,
        "INVALID_OPERATOR_ENVELOPE",
        {
            "key_id": (verified.get("signer") or {}).get("key_id"),
            "deadline": verified.get("deadline_utc"),
        },
    )


def evaluate_preflight(
    manifest: dict[str, Any],
    *,
    state_root: Path,
    expected_host: str,
    envelope_path: str | None,
    identity_receipt_path: str | None,
    provider_receipt_path: str | None,
) -> list[dict[str, Any]]:
    """Evaluate every non-live gate; this function never imports provider code."""

    probe_nonce, probe_fence = _active_provider_probe_binding(manifest, state_root)
    return [
        _state_gate(state_root, expected_host),
        _source_gate(manifest),
        _identity_gate(manifest, identity_receipt_path),
        _provider_gate(
            manifest,
            provider_receipt_path,
            expected_probe_request_nonce=probe_nonce,
            expected_probe_fencing_token=probe_fence,
        ),
        _acceptance_gate(),
        _prerequisite_gate("canary"),
        _prerequisite_gate("n30"),
        _envelope_gate(manifest, envelope_path, expected_host=expected_host),
    ]
