from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from dharma_swarm.forge_lab import campaign_gates, provider_selftest
from dharma_swarm.forge_lab.campaign_contract import manifest_digest


NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
KEY_ID = "test-provider-probe"
NONCE = "provider-probe-request-0001"
FENCE = 7
TRUSTED_KEY = Ed25519PrivateKey.generate()
WRONG_KEY = Ed25519PrivateKey.generate()


def _public(key: Ed25519PrivateKey = TRUSTED_KEY) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _trust(key: Ed25519PrivateKey = TRUSTED_KEY) -> dict[str, bytes]:
    return {KEY_ID: _public(key)}


def _manifest() -> dict[str, object]:
    manifest: dict[str, object] = {
        "schema": "forge_lab.campaign_manifest.v1",
        "definition": {
            "campaign_name": "forge-lab-attestation-test",
            "source": {
                "release_commit": "1" * 40,
                "release_tree": "2" * 40,
            },
            "bootstrap": {
                "role_routes": {
                    "solver": "forge.high_slot.solver",
                    "verifier": "forge.high_slot.verifier",
                    "mutator": "forge.high_slot.mutator",
                }
            },
            "gates": {
                "provider_attestation": {
                    "required_roles": ["solver", "verifier", "mutator"],
                    "min_independent_transports": 2,
                    "max_age_seconds": 300,
                    "required_probe_authority": "rsi-lab-provider-probe-v1",
                }
            },
        },
    }
    manifest["manifest_digest"] = manifest_digest(manifest)
    return manifest


def _role_rows() -> dict[str, dict[str, object]]:
    return {
        "solver": {
            "requested_model": "solver-v1",
            "served_model": "solver-v1",
            "model_family": "solver-family",
            "provider": "provider-a-route",
            "provider_family": "provider-a",
            "physical_transport_identity": "provider:https://a.example/v1",
            "callable": True,
            "live": True,
            "stage": "complete",
            "fallback": False,
        },
        "verifier": {
            "requested_model": "verifier-v1",
            "served_model": "verifier-v1",
            "model_family": "verifier-family",
            "provider": "provider-b-route",
            "provider_family": "provider-b",
            "physical_transport_identity": "provider:https://b.example/v1",
            "callable": True,
            "live": True,
            "stage": "complete",
            "fallback": False,
        },
        "mutator": {
            "requested_model": "mutator-v1",
            "served_model": "mutator-v1",
            "model_family": "solver-family",
            "provider": "provider-a-alias",
            "provider_family": "provider-a",
            "physical_transport_identity": "provider:https://a.example/v1",
            "callable": True,
            "live": True,
            "stage": "complete",
            "fallback": False,
        },
    }


def _attestation(
    *, key: Ed25519PrivateKey = TRUSTED_KEY, validate: bool = True
) -> tuple[dict[str, object], dict[str, object]]:
    manifest = _manifest()
    receipt = provider_selftest.build_provider_attestation(
        manifest,
        role_rows=_role_rows(),
        probe_request_nonce=NONCE,
        probe_fencing_token=FENCE,
        signing_key_id=KEY_ID,
        signing_key=key,
        checked_at=NOW,
        ttl_seconds=300,
        unattended=True,
        validate=validate,
    )
    return manifest, receipt


def _resign(
    receipt: dict[str, object], key: Ed25519PrivateKey = TRUSTED_KEY
) -> None:
    receipt["attestation_digest"] = provider_selftest.provider_attestation_digest(
        receipt
    )
    receipt["signature"] = key.sign(
        provider_selftest._attestation_signing_bytes(receipt)
    ).hex()


def _verify(
    manifest: dict[str, object],
    receipt: dict[str, object],
    *,
    trust: dict[str, bytes] | None = None,
    nonce: str = NONCE,
    fence: int = FENCE,
    now: datetime | None = None,
) -> dict[str, object]:
    return provider_selftest.verify_provider_attestation(
        manifest,
        receipt,
        now=now or NOW + timedelta(seconds=1),
        unattended=True,
        trusted_public_keys=trust or _trust(),
        expected_probe_request_nonce=nonce,
        expected_probe_fencing_token=fence,
    )


def test_attestation_binds_manifest_release_config_roles_and_transports() -> None:
    manifest, receipt = _attestation()

    verified = _verify(manifest, receipt)

    assert verified["manifest_digest"] == manifest["manifest_digest"]
    assert verified["config_digest"] == receipt["config_digest"]
    assert verified["independent_transport_count"] == 2
    assert verified["route_diversity"] == {
        "distinct_physical_transport_count": 2,
        "distinct_model_family_count": 2,
        "distinct_provider_family_count": 2,
        "decorrelation_claimed": False,
    }
    assert verified["transport_independence_scope"] == (
        "distinct physical transport digests only"
    )
    assert verified["signing_key_id"] == KEY_ID
    assert set(verified["roles"]) == {"solver", "verifier", "mutator"}
    assert verified["roles"]["solver"] == {
        "requested_model": "solver-v1",
        "served_model": "solver-v1",
        "model_family": "solver-family",
        "provider": "provider-a-route",
        "provider_family": "provider-a",
        "physical_transport_digest": receipt["roles"]["solver"][
            "physical_transport_digest"
        ],
    }


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            lambda value: value["release"].__setitem__("commit", "3" * 40),
            "RELEASE_MISMATCH",
        ),
        (
            lambda value: value.__setitem__("config_digest", "sha256:" + "0" * 64),
            "CONFIG_DIGEST_MISMATCH",
        ),
        (
            lambda value: value["roles"]["solver"].__setitem__(
                "served_model", "fallback-v2"
            ),
            "SERVED_MODEL_MISMATCH",
        ),
        (
            lambda value: value["roles"]["solver"].__setitem__("callable", False),
            "ZERO_OR_INCOMPLETE_ROUTES",
        ),
        (lambda value: value["roles"].pop("mutator"), "ROLE_BINDING_MISMATCH"),
    ],
)
def test_signed_attestation_semantic_tampering_fails_closed(mutation, code: str) -> None:
    manifest, receipt = _attestation()
    mutation(receipt)
    _resign(receipt)

    with pytest.raises(provider_selftest.ProviderAttestationError) as raised:
        _verify(manifest, receipt)

    assert raised.value.code == code


def test_unsigned_forged_and_wrong_key_attestations_fail_closed() -> None:
    manifest, receipt = _attestation()
    receipt.pop("signature")
    with pytest.raises(provider_selftest.ProviderAttestationError) as unsigned:
        _verify(manifest, receipt)
    assert unsigned.value.code == "PROVIDER_ATTESTATION_UNSIGNED"

    manifest, forged = _attestation()
    forged["roles"]["solver"]["provider"] = "attacker-controlled"
    forged["attestation_digest"] = provider_selftest.provider_attestation_digest(forged)
    with pytest.raises(provider_selftest.ProviderAttestationError) as tampered:
        _verify(manifest, forged)
    assert tampered.value.code == "ATTESTATION_SIGNATURE_INVALID"

    manifest, wrong_key = _attestation(key=WRONG_KEY, validate=False)
    with pytest.raises(provider_selftest.ProviderAttestationError) as wrong:
        _verify(manifest, wrong_key)
    assert wrong.value.code == "ATTESTATION_SIGNATURE_INVALID"


def test_caller_transport_identity_is_not_authority_without_trusted_signature() -> None:
    manifest, attacker_receipt = _attestation(key=WRONG_KEY, validate=False)
    assert attacker_receipt["independent_transport_count"] == 2

    with pytest.raises(provider_selftest.ProviderAttestationError) as raised:
        _verify(manifest, attacker_receipt)

    assert raised.value.code == "ATTESTATION_SIGNATURE_INVALID"


def test_manifest_digest_and_signature_are_both_load_bearing() -> None:
    manifest, receipt = _attestation()
    receipt["roles"]["solver"]["provider"] = "tampered"

    with pytest.raises(provider_selftest.ProviderAttestationError) as raised:
        _verify(manifest, receipt)
    assert raised.value.code == "ATTESTATION_DIGEST_MISMATCH"

    clean_manifest, clean_receipt = _attestation()
    clean_manifest["definition"]["campaign_name"] = "substituted"
    with pytest.raises(provider_selftest.ProviderAttestationError) as raised:
        _verify(clean_manifest, clean_receipt)
    assert raised.value.code == "MANIFEST_DIGEST_MISMATCH"


def test_probe_nonce_and_fence_prevent_cross_request_replay() -> None:
    manifest, receipt = _attestation()

    with pytest.raises(provider_selftest.ProviderAttestationError) as nonce:
        _verify(manifest, receipt, nonce="provider-probe-request-9999")
    assert nonce.value.code == "PROBE_NONCE_MISMATCH"

    with pytest.raises(provider_selftest.ProviderAttestationError) as fence:
        _verify(manifest, receipt, fence=FENCE + 1)
    assert fence.value.code == "PROBE_FENCE_MISMATCH"

    with pytest.raises(provider_selftest.ProviderAttestationError) as missing:
        provider_selftest.verify_provider_attestation(
            manifest,
            receipt,
            now=NOW + timedelta(seconds=1),
            unattended=True,
            trusted_public_keys=_trust(),
        )
    assert missing.value.code == "PROBE_BINDING_REQUIRED"


def test_probe_fence_must_be_positive_even_when_signed() -> None:
    manifest = _manifest()
    with pytest.raises(provider_selftest.ProviderAttestationError) as build_error:
        provider_selftest.build_provider_attestation(
            manifest,
            role_rows=_role_rows(),
            probe_request_nonce=NONCE,
            probe_fencing_token=0,
            signing_key_id=KEY_ID,
            signing_key=TRUSTED_KEY,
            checked_at=NOW,
        )
    assert build_error.value.code == "PROBE_FENCE_INVALID"

    manifest, receipt = _attestation()
    receipt["probe_authority"]["fencing_token"] = 0
    _resign(receipt)
    with pytest.raises(provider_selftest.ProviderAttestationError) as verify_error:
        _verify(manifest, receipt)
    assert verify_error.value.code == "PROBE_FENCE_INVALID"


def test_expired_future_or_overlong_attestation_is_rejected() -> None:
    manifest, receipt = _attestation()

    with pytest.raises(provider_selftest.ProviderAttestationError) as expired:
        _verify(manifest, receipt, now=NOW + timedelta(seconds=301))
    assert expired.value.code == "ATTESTATION_EXPIRED"

    receipt["checked_at"] = (NOW + timedelta(seconds=5)).isoformat().replace(
        "+00:00", "Z"
    )
    receipt["expires_at"] = (NOW + timedelta(seconds=305)).isoformat().replace(
        "+00:00", "Z"
    )
    _resign(receipt)
    with pytest.raises(provider_selftest.ProviderAttestationError) as future:
        _verify(manifest, receipt, now=NOW)
    assert future.value.code == "ATTESTATION_FROM_FUTURE"

    receipt = provider_selftest.build_provider_attestation(
        manifest,
        role_rows=_role_rows(),
        probe_request_nonce=NONCE,
        probe_fencing_token=FENCE,
        signing_key_id=KEY_ID,
        signing_key=TRUSTED_KEY,
        checked_at=NOW,
        ttl_seconds=301,
        unattended=False,
        validate=False,
    )
    with pytest.raises(provider_selftest.ProviderAttestationError) as overlong:
        provider_selftest.verify_provider_attestation(
            manifest,
            receipt,
            now=NOW,
            unattended=False,
            trusted_public_keys=_trust(),
        )
    assert overlong.value.code == "ATTESTATION_TTL_EXCEEDED"


def test_unattended_attestation_requires_two_physical_not_logical_routes() -> None:
    manifest = _manifest()
    rows = _role_rows()
    for row in rows.values():
        row["provider"] = f"logical-{row['requested_model']}"
        row["provider_family"] = f"logical-family-{row['requested_model']}"
        row["physical_transport_identity"] = "provider:https://shared.example/v1"

    with pytest.raises(provider_selftest.ProviderAttestationError) as raised:
        provider_selftest.build_provider_attestation(
            manifest,
            role_rows=rows,
            probe_request_nonce=NONCE,
            probe_fencing_token=FENCE,
            signing_key_id=KEY_ID,
            signing_key=TRUSTED_KEY,
            checked_at=NOW,
            unattended=True,
        )

    assert raised.value.code == "INSUFFICIENT_INDEPENDENT_TRANSPORTS"


def test_attestation_is_redacted_and_gate_accepts_explicit_verifier(tmp_path) -> None:
    manifest = _manifest()
    rows = _role_rows()
    rows["solver"]["api_key"] = "KEY_SENTINEL_MUST_NOT_PERSIST"
    rows["solver"]["base_url"] = "https://a.example/v1?token=SECRET"
    receipt = provider_selftest.build_provider_attestation(
        manifest,
        role_rows=rows,
        probe_request_nonce=NONCE,
        probe_fencing_token=FENCE,
        signing_key_id=KEY_ID,
        signing_key=TRUSTED_KEY,
        checked_at=NOW,
        unattended=True,
    )
    rendered = json.dumps(receipt, sort_keys=True)
    assert "KEY_SENTINEL" not in rendered
    assert "token=SECRET" not in rendered
    assert "physical_transport_identity" not in rendered
    assert "public_key" not in rendered

    path = tmp_path / "provider-attestation.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    def verifier(key_id: str, message: bytes, signature: bytes) -> bool:
        assert key_id == KEY_ID
        TRUSTED_KEY.public_key().verify(signature, message)
        return True

    gate = campaign_gates._provider_gate(
        manifest,
        str(path),
        now=NOW + timedelta(seconds=1),
        signature_verifier=verifier,
        expected_probe_request_nonce=NONCE,
        expected_probe_fencing_token=FENCE,
    )
    assert gate["passed"] is True
    assert gate["detail"]["independent_transport_count"] == 2


def test_campaign_gate_loads_only_protected_explicit_trust_file(
    tmp_path, monkeypatch
) -> None:
    manifest, receipt = _attestation()
    receipt_path = tmp_path / "provider-attestation.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    trust_path = tmp_path / "provider-probe-keys.json"
    trust_path.write_text(
        json.dumps(
            {
                "schema": provider_selftest.PROVIDER_PROBE_TRUST_SCHEMA,
                "keys": {KEY_ID: _public().hex()},
            }
        ),
        encoding="utf-8",
    )
    trust_path.chmod(0o600)
    monkeypatch.setenv("RSI_LAB_TRUSTED_PROVIDER_PROBE_KEYS", str(trust_path))
    gate = campaign_gates._provider_gate(
        manifest,
        str(receipt_path),
        now=NOW + timedelta(seconds=1),
        expected_probe_request_nonce=NONCE,
        expected_probe_fencing_token=FENCE,
    )
    assert gate["passed"] is True

    trust_path.chmod(0o622)
    refused = campaign_gates._provider_gate(
        manifest,
        str(receipt_path),
        now=NOW + timedelta(seconds=1),
        expected_probe_request_nonce=NONCE,
        expected_probe_fencing_token=FENCE,
    )
    assert refused["passed"] is False
    assert refused["code"] == "PROVIDER_TRUST_ROOT_UNTRUSTED"


def test_campaign_gate_fails_closed_without_trust_root(tmp_path, monkeypatch) -> None:
    manifest, receipt = _attestation()
    path = tmp_path / "provider-attestation.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.delenv("RSI_LAB_TRUSTED_PROVIDER_PROBE_KEYS", raising=False)

    gate = campaign_gates._provider_gate(manifest, str(path), now=NOW)

    assert gate["passed"] is False
    assert gate["code"] == "PROVIDER_TRUST_ROOT_MISSING"


def test_environment_cannot_substitute_for_live_probe_binding(
    tmp_path, monkeypatch
) -> None:
    manifest, receipt = _attestation()
    path = tmp_path / "provider-attestation.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setenv("RSI_LAB_PROVIDER_PROBE_REQUEST_NONCE", NONCE)
    monkeypatch.setenv("RSI_LAB_PROVIDER_PROBE_FENCING_TOKEN", str(FENCE))

    gate = campaign_gates._provider_gate(
        manifest,
        str(path),
        now=NOW + timedelta(seconds=1),
        trusted_public_keys=_trust(),
    )

    assert gate["passed"] is False
    assert gate["code"] == "PROBE_BINDING_REQUIRED"


def test_provider_probe_trust_loader_rejects_symlink(tmp_path) -> None:
    target = tmp_path / "real-provider-probe-keys.json"
    target.write_text(
        json.dumps(
            {
                "schema": provider_selftest.PROVIDER_PROBE_TRUST_SCHEMA,
                "keys": {KEY_ID: _public().hex()},
            }
        ),
        encoding="utf-8",
    )
    target.chmod(0o600)
    link = tmp_path / "provider-probe-keys.json"
    link.symlink_to(target)

    with pytest.raises(provider_selftest.ProviderAttestationError) as raised:
        provider_selftest.load_trusted_provider_probe_keys(link)

    assert raised.value.code == "PROVIDER_TRUST_ROOT_UNTRUSTED"
