"""Ed25519 trust-root loading and signature checks for provider probes."""

from __future__ import annotations

import base64
from collections.abc import Mapping
import json
import os
from pathlib import Path
import stat
from typing import Any, Callable

from dharma_swarm.forge_lab.provider_attestation_contract import (
    KEY_ID_RE,
    PROVIDER_PROBE_TRUST_SCHEMA,
    SIGNATURE_RE,
    ProviderAttestationError,
    canonical_json,
    fail,
)


ProviderSignatureVerifier = Callable[[str, bytes, bytes], bool]


def decode_public_key(value: str | bytes) -> bytes:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        encoded = value.removeprefix("ed25519:").strip()
        try:
            raw = bytes.fromhex(encoded)
        except ValueError:
            try:
                raw = base64.b64decode(encoded, validate=True)
            except Exception as exc:
                raise ProviderAttestationError(
                    "PROVIDER_TRUST_ROOT_INVALID",
                    "provider probe public key is not raw hex or base64",
                ) from exc
    else:
        fail("PROVIDER_TRUST_ROOT_INVALID", "unsupported provider probe key type")
    if len(raw) != 32:
        fail(
            "PROVIDER_TRUST_ROOT_INVALID",
            "provider probe Ed25519 public key must contain 32 bytes",
        )
    return raw


def load_trusted_provider_probe_keys(
    path: str | os.PathLike[str],
) -> dict[str, str | bytes]:
    """Load a bounded, root-owned trust file without following its final link."""

    candidate = Path(path)
    if not candidate.is_absolute() or ".." in candidate.parts:
        fail(
            "PROVIDER_TRUST_ROOT_UNTRUSTED",
            "provider probe trust path must be absolute and normalized",
        )
    try:
        before = candidate.lstat()
    except OSError as exc:
        raise ProviderAttestationError(
            "PROVIDER_TRUST_ROOT_MISSING",
            f"provider probe trust file is unavailable: {type(exc).__name__}",
        ) from exc
    unsafe = (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or before.st_uid != 0
        or bool(before.st_mode & 0o022)
        or before.st_nlink != 1
    )
    if unsafe:
        fail(
            "PROVIDER_TRUST_ROOT_UNTRUSTED",
            "provider probe trust file must be root-owned, regular, single-linked, "
            "and not group/world-writable",
        )

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(candidate, flags)
    except OSError as exc:
        raise ProviderAttestationError(
            "PROVIDER_TRUST_ROOT_UNTRUSTED",
            f"provider probe trust file cannot be opened safely: {type(exc).__name__}",
        ) from exc
    try:
        opened = os.fstat(descriptor)
        changed = (
            opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != 0
            or bool(opened.st_mode & 0o022)
            or opened.st_nlink != 1
            or opened.st_size > 65_536
        )
        if changed:
            fail(
                "PROVIDER_TRUST_ROOT_UNTRUSTED",
                "provider probe trust file changed or violates ownership constraints",
            )
        raw = b""
        while len(raw) <= 65_536:
            chunk = os.read(descriptor, min(8192, 65_537 - len(raw)))
            if not chunk:
                break
            raw += chunk
        if len(raw) > 65_536:
            fail("PROVIDER_TRUST_ROOT_UNTRUSTED", "probe trust file exceeds 64 KiB")
    finally:
        os.close(descriptor)

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderAttestationError(
            "PROVIDER_TRUST_ROOT_INVALID",
            "provider probe trust file is not valid UTF-8 JSON",
        ) from exc
    valid_shape = (
        isinstance(payload, Mapping)
        and set(payload) == {"schema", "keys"}
        and payload.get("schema") == PROVIDER_PROBE_TRUST_SCHEMA
        and isinstance(payload.get("keys"), Mapping)
        and bool(payload["keys"])
    )
    if not valid_shape:
        fail(
            "PROVIDER_TRUST_ROOT_INVALID",
            "provider probe trust file must contain only schema and nonempty keys",
        )
    keys = dict(payload["keys"])
    for key_id, public_key in keys.items():
        if not isinstance(key_id, str) or not KEY_ID_RE.fullmatch(key_id):
            fail("PROVIDER_TRUST_ROOT_INVALID", "provider probe key id is invalid")
        decode_public_key(public_key)
    return keys


def attestation_signing_bytes(receipt: Mapping[str, Any]) -> bytes:
    payload = dict(receipt)
    payload.pop("signature", None)
    return canonical_json(payload)


def verify_attestation_signature(
    receipt: Mapping[str, Any],
    *,
    trusted_public_keys: Mapping[str, str | bytes] | None,
    signature_verifier: ProviderSignatureVerifier | None,
) -> str:
    signer = receipt.get("signer")
    if (
        not isinstance(signer, Mapping)
        or set(signer) != {"algorithm", "key_id"}
        or signer.get("algorithm") != "ed25519"
        or not KEY_ID_RE.fullmatch(str(signer.get("key_id") or ""))
    ):
        fail("INVALID_PROVIDER_PROBE_SIGNER", "provider probe signer is malformed")
    key_id = str(signer["key_id"])
    signature_hex = str(receipt.get("signature") or "")
    if not SIGNATURE_RE.fullmatch(signature_hex):
        fail("PROVIDER_ATTESTATION_UNSIGNED", "attestation has no valid signature")
    signature = bytes.fromhex(signature_hex)
    message = attestation_signing_bytes(receipt)

    if signature_verifier is not None:
        try:
            accepted = signature_verifier(key_id, message, signature)
        except Exception as exc:
            raise ProviderAttestationError(
                "ATTESTATION_SIGNATURE_INVALID",
                f"provider probe verifier refused signature: {type(exc).__name__}",
            ) from exc
        if accepted is not True:
            fail("ATTESTATION_SIGNATURE_INVALID", "probe verifier rejected signature")
        return key_id
    if not isinstance(trusted_public_keys, Mapping) or not trusted_public_keys:
        fail("PROVIDER_TRUST_ROOT_MISSING", "explicit trusted probe key is required")
    if key_id not in trusted_public_keys:
        fail("UNTRUSTED_PROVIDER_PROBE_KEY", f"probe key id {key_id!r} is not trusted")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        public_key = decode_public_key(trusted_public_keys[key_id])
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
    except ProviderAttestationError:
        raise
    except Exception as exc:
        raise ProviderAttestationError(
            "ATTESTATION_SIGNATURE_INVALID",
            "provider attestation Ed25519 signature is invalid",
        ) from exc
    return key_id


def signing_public_key(signing_key: Any) -> bytes | None:
    try:
        from cryptography.hazmat.primitives import serialization

        return signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    except (AttributeError, TypeError, ValueError):
        return None
