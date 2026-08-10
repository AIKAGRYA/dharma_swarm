"""Two-phase, fenced provider-probe challenges for paired campaigns."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from dharma_swarm.forge_lab.campaign_contract import content_digest
from dharma_swarm.forge_lab.provider_attestation_contract import (
    provider_probe_request_nonce,
)


CHALLENGE_SCHEMA = "forge_lab.provider_probe_challenge.v1"


class CampaignChallengeError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _campaign_root(state_root: Path, campaign: str) -> Path:
    return state_root / ".dharma" / "forge_lab" / "campaigns" / campaign


def _challenge_path(state_root: Path, campaign: str, request_id: str) -> Path:
    suffix = content_digest(
        {"campaign": campaign, "request_id": request_id, "kind": "provider_probe"}
    ).removeprefix("sha256:")
    return _campaign_root(state_root, campaign) / "control" / f"challenge-{suffix}.json"


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid4().hex}")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def _projection(state_root: Path, campaign: str) -> None:
    root = _campaign_root(state_root, campaign)
    for category in ("control", "receipts", "events", "checkpoints"):
        (root / category).mkdir(parents=True, exist_ok=True, mode=0o700)


def _active_lease(store: Any, campaign: str, manifest_id: str) -> dict[str, Any]:
    active = [
        lease
        for lease in store.active_leases()
        if lease.get("campaign_id") == campaign
        and lease.get("manifest_digest") == manifest_id
    ]
    if len(active) != 1:
        raise CampaignChallengeError(
            "PROVIDER_CHALLENGE_EXPIRED",
            "paired provider challenge has no unique active lease",
        )
    return active[0]


def _read_challenge(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CampaignChallengeError(
            "PROVIDER_CHALLENGE_REQUIRED",
            "prepare the paired campaign before supplying a provider receipt",
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CampaignChallengeError(
            "PROVIDER_CHALLENGE_CORRUPT",
            f"provider challenge is unreadable: {type(exc).__name__}",
        ) from exc
    if not isinstance(value, dict):
        raise CampaignChallengeError(
            "PROVIDER_CHALLENGE_CORRUPT", "provider challenge is not an object"
        )
    declared = value.get("challenge_digest")
    body = dict(value)
    body.pop("challenge_digest", None)
    if declared != content_digest(body):
        raise CampaignChallengeError(
            "PROVIDER_CHALLENGE_CORRUPT", "provider challenge digest disagrees"
        )
    return value


def resume_prepared_campaign(
    store: Any,
    manifest: Mapping[str, Any],
    *,
    state_root: Path,
    request_id: str,
    actor: str,
) -> dict[str, Any]:
    campaign = str(manifest["campaign_name"])
    manifest_id = str(manifest["manifest_digest"])
    challenge = _read_challenge(_challenge_path(state_root, campaign, request_id))
    expected_keys = {
        "schema",
        "campaign_name",
        "manifest_digest",
        "request_id",
        "probe_authority",
        "probe_request_nonce",
        "fencing_token",
        "lease_holder",
        "issued_at",
        "expires_at",
        "dispatch_enabled",
        "challenge_digest",
    }
    if set(challenge) != expected_keys or challenge.get("schema") != CHALLENGE_SCHEMA:
        raise CampaignChallengeError(
            "PROVIDER_CHALLENGE_CORRUPT", "provider challenge shape is not exact"
        )
    status = store.get_campaign(campaign)
    lease = _active_lease(store, campaign, manifest_id)
    fence = lease.get("active_fence")
    expected_nonce = provider_probe_request_nonce(manifest_id, fence)
    gates = manifest.get("gates") or {}
    attestation = gates.get("provider_attestation") or {}
    if (
        status.get("state") != "PREFLIGHTING"
        or lease.get("lease_holder") != actor
        or challenge.get("campaign_name") != campaign
        or challenge.get("manifest_digest") != manifest_id
        or challenge.get("request_id") != request_id
        or challenge.get("probe_authority")
        != attestation.get("required_probe_authority")
        or challenge.get("fencing_token") != fence
        or challenge.get("lease_holder") != actor
        or challenge.get("probe_request_nonce") != expected_nonce
        or challenge.get("issued_at") != status.get("updated_at")
        or challenge.get("expires_at") != lease.get("lease_expires")
        or challenge.get("dispatch_enabled") is not False
    ):
        raise CampaignChallengeError(
            "PROVIDER_CHALLENGE_MISMATCH",
            "provider challenge is not bound to the active preflight lease",
        )
    return {**challenge, "challenge_path": str(_challenge_path(state_root, campaign, request_id))}


def prepare_paired_campaign(
    store: Any,
    manifest: Mapping[str, Any],
    *,
    state_root: Path,
    request_id: str,
    actor: str,
    ttl_seconds: int = 300,
) -> dict[str, Any]:
    """Create a PREFLIGHTING lease and return its provider-probe challenge."""

    campaign = str(manifest["campaign_name"])
    manifest_id = str(manifest["manifest_digest"])
    path = _challenge_path(state_root, campaign, request_id)
    if path.exists():
        challenge = resume_prepared_campaign(
            store,
            manifest,
            state_root=state_root,
            request_id=request_id,
            actor=actor,
        )
        return {**challenge, "replayed": True}
    created = False
    try:
        status = store.get_campaign(campaign)
    except Exception as exc:
        if getattr(exc, "code", None) != "CAMPAIGN_NOT_FOUND":
            raise
        store.create_campaign(manifest, request_id=f"{request_id}.create", actor=actor)
        _projection(state_root, campaign)
        created = True
    else:
        active = [
            lease
            for lease in store.active_leases()
            if lease.get("campaign_id") == campaign
        ]
        if (
            status.get("manifest_digest") != manifest_id
            or status.get("state") != "PREFLIGHTING"
            or active
        ):
            raise CampaignChallengeError(
                "CAMPAIGN_RUN_INCOMPLETE",
                "paired campaign is not an expired preflight eligible for a new challenge",
            )

    lease_receipt = store.acquire_lease(
        campaign,
        request_id=f"{request_id}.lease",
        holder=actor,
        mode="active",
        ttl_seconds=ttl_seconds,
    )
    fence = lease_receipt["fencing_token"]
    if created:
        store.apply_action(
            campaign,
            request_id=f"{request_id}.preflight",
            action="begin-preflight",
            actor=actor,
            target_state="PREFLIGHTING",
            fencing_token=fence,
        )
    status = store.get_campaign(campaign)
    gates = manifest.get("gates") or {}
    attestation = gates.get("provider_attestation") or {}
    challenge: dict[str, Any] = {
        "schema": CHALLENGE_SCHEMA,
        "campaign_name": campaign,
        "manifest_digest": manifest_id,
        "request_id": request_id,
        "probe_authority": attestation.get("required_probe_authority"),
        "probe_request_nonce": provider_probe_request_nonce(manifest_id, fence),
        "fencing_token": fence,
        "lease_holder": actor,
        "issued_at": status["updated_at"],
        "expires_at": status["lease"]["expires_at"],
        "dispatch_enabled": False,
    }
    challenge["challenge_digest"] = content_digest(challenge)
    _atomic_json(path, challenge)
    return {**challenge, "challenge_path": str(path), "replayed": False}


def start_historical_preflight(
    store: Any,
    manifest: Mapping[str, Any],
    *,
    state_root: Path,
    request_id: str,
    actor: str,
) -> int:
    campaign = str(manifest["campaign_name"])
    try:
        existing = store.get_campaign(campaign)
    except Exception as exc:
        if getattr(exc, "code", None) != "CAMPAIGN_NOT_FOUND":
            raise
    else:
        raise CampaignChallengeError(
            "CAMPAIGN_RUN_INCOMPLETE",
            "canonical campaign state exists without a replayable blocked receipt "
            f"(state={existing.get('state')!r}); reconciliation is required",
        )
    store.create_campaign(manifest, request_id=f"{request_id}.create", actor=actor)
    _projection(state_root, campaign)
    lease = store.acquire_lease(
        campaign,
        request_id=f"{request_id}.lease",
        holder=actor,
        mode="active",
        ttl_seconds=90,
    )
    fence = lease["fencing_token"]
    store.apply_action(
        campaign,
        request_id=f"{request_id}.preflight",
        action="begin-preflight",
        actor=actor,
        target_state="PREFLIGHTING",
        fencing_token=fence,
    )
    return fence
