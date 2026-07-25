"""Minimum fail-closed controller for content-addressed Forge Lab campaigns."""

from __future__ import annotations

import json
import os
import re
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from dharma_swarm.forge_lab.campaign_contract import (
    CampaignContractError,
    build_manifest,
    canonical_json,
    manifest_digest,
    resolve_state_root,
    validate_manifest,
)
from dharma_swarm.forge_lab.campaign_gates import evaluate_preflight
from dharma_swarm.forge_lab.campaign_profile import PROFILE, campaign_definition
from dharma_swarm.forge_lab.campaign_receipts import (
    BlockedReceiptError,
    build_blocked_receipt as _blocked_receipt,
    terminal_state_problem as _terminal_state_problem,
    validate_blocked_receipt,
)


_DIGEST_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
_PROJECTION_CATEGORIES = ("control", "receipts", "events", "checkpoints")


class CampaignControlError(RuntimeError):
    """Machine-classifiable control-plane refusal."""

    def __init__(self, code: str, message: str, *, result: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.result = result


def _control_root(state_root: Path) -> Path:
    return state_root / ".dharma" / "forge_lab"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid4().hex}")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
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


def _manifest_path(state_root: Path, digest: str) -> Path:
    match = _DIGEST_RE.fullmatch(digest)
    if not match:
        raise CampaignControlError(
            "INVALID_MANIFEST_DIGEST", "manifest must be sha256:<64 lowercase hex>"
        )
    return _control_root(state_root) / "manifests" / f"{match.group(1)}.json"


def plan_campaign(profile: str, *, state_root: Path | None = None) -> dict[str, Any]:
    """Build and store a deterministic manifest without provider imports/calls."""

    if profile != PROFILE:
        raise CampaignControlError(
            "UNSUPPORTED_GOVERNED_PROFILE",
            f"implemented governed profile is {PROFILE!r}, not {profile!r}",
        )
    root = state_root or resolve_state_root()
    manifest = build_manifest(campaign_definition(profile))
    digest = manifest["manifest_digest"]
    path = _manifest_path(root, digest)
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CampaignControlError(
                "MANIFEST_CAS_CORRUPT", f"stored manifest is unreadable: {exc}"
            ) from exc
        if canonical_json(existing) != canonical_json(manifest):
            raise CampaignControlError(
                "MANIFEST_CAS_CONFLICT", "manifest digest path contains different bytes"
            )
    else:
        _atomic_json(path, manifest)
    return {
        "schema": "forge_lab.campaign_plan.v1",
        "campaign_name": manifest["campaign_name"],
        "manifest_digest": digest,
        "manifest_path": str(path),
        "powered": all(value is not None for value in manifest["limits"].values()),
        "provider_calls": 0,
        "manifest": manifest,
    }


def load_manifest(digest: str, *, state_root: Path | None = None) -> dict[str, Any]:
    root = state_root or resolve_state_root()
    path = _manifest_path(root, digest)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CampaignControlError(
            "MANIFEST_NOT_FOUND", f"stored manifest does not exist: {digest}"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CampaignControlError(
            "MANIFEST_CAS_CORRUPT", f"stored manifest is unreadable: {exc}"
        ) from exc
    try:
        validated = validate_manifest(value)
    except CampaignContractError as exc:
        raise CampaignControlError(exc.code, str(exc)) from exc
    if validated["manifest_digest"] != digest or manifest_digest(validated) != digest:
        raise CampaignControlError(
            "MANIFEST_DIGEST_MISMATCH", "requested digest does not match manifest bytes"
        )
    return validated


def _receipt_path(state_root: Path, campaign_id: str, request_id: str) -> Path:
    suffix = sha256(
        canonical_json(
            {"campaign_id": campaign_id, "request_id": request_id, "kind": "blocked"}
        )
    ).hexdigest()
    return (
        _control_root(state_root)
        / "campaigns"
        / campaign_id
        / "receipts"
        / f"blocked-{suffix}.json"
    )


def _ensure_campaign_projection(state_root: Path, campaign_id: str) -> None:
    campaign_root = _control_root(state_root) / "campaigns" / campaign_id
    try:
        for category in _PROJECTION_CATEGORIES:
            (campaign_root / category).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CampaignControlError(
            "CAMPAIGN_PROJECTION_FAILURE",
            f"cannot create canonical campaign projection: {exc}",
        ) from exc


def _validate_blocked_receipt(
    receipt: Any,
    *,
    campaign_id: str,
    manifest_digest_value: str,
    request_id: str,
) -> dict[str, Any]:
    try:
        return validate_blocked_receipt(
            receipt,
            campaign_id=campaign_id,
            manifest_digest=manifest_digest_value,
            request_id=request_id,
        )
    except BlockedReceiptError as exc:
        raise CampaignControlError(
            "BLOCKED_RECEIPT_INVALID", str(exc)
        ) from exc


def _store_error(exc: Exception) -> CampaignControlError:
    return CampaignControlError(
        getattr(exc, "code", "CAMPAIGN_STORE_FAILURE"),
        str(exc),
    )


def run_campaign(
    digest: str,
    *,
    request_id: str | None = None,
    actor: str = "codex-rsi-lab-manager",
    expected_host: str = "meghadharma",
    envelope_path: str | None = None,
    identity_receipt_path: str | None = None,
    provider_receipt_path: str | None = None,
    state_root: Path | None = None,
) -> dict[str, Any]:
    """Instantiate, preflight, and durably block an unpowered campaign.

    This minimum controller intentionally has no scientific executor import.
    Even forged gate evidence therefore cannot open provider dispatch.
    """

    from dharma_swarm.forge_lab.campaign_store import CampaignStore
    from dharma_swarm.forge_lab.campaign_store_schema import StoreError

    root = state_root or resolve_state_root()
    manifest = load_manifest(digest, state_root=root)
    campaign_id = manifest["campaign_name"]
    stable_request = request_id or f"campaign-run-{digest[-16:]}"
    receipt_path = _receipt_path(root, campaign_id, stable_request)
    prior: dict[str, Any] | None = None
    if receipt_path.exists():
        try:
            prior = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CampaignControlError(
                "BLOCKED_RECEIPT_CORRUPT", f"cannot replay blocked receipt: {exc}"
            ) from exc
        prior = _validate_blocked_receipt(
            prior,
            campaign_id=campaign_id,
            manifest_digest_value=digest,
            request_id=stable_request,
        )

    try:
        store = CampaignStore(root)
    except Exception as exc:
        raise _store_error(exc) from exc

    if prior is not None:
        try:
            status = store.get_campaign(campaign_id)
        except StoreError as exc:
            raise CampaignControlError(
                "BLOCKED_RECEIPT_INVALID",
                f"canonical campaign state cannot validate replay: {exc}",
            ) from exc
        problem = _terminal_state_problem(
            status,
            campaign_id=campaign_id,
            manifest_digest=digest,
        )
        if problem is not None:
            raise CampaignControlError("BLOCKED_RECEIPT_INVALID", problem)
        return {**prior, "receipt_path": str(receipt_path), "replayed": True}

    try:
        existing = store.get_campaign(campaign_id)
    except StoreError as exc:
        if exc.code != "CAMPAIGN_NOT_FOUND":
            raise _store_error(exc) from exc
    else:
        raise CampaignControlError(
            "CAMPAIGN_RUN_INCOMPLETE",
            "canonical campaign state exists without a replayable blocked receipt "
            f"(state={existing.get('state')!r}); reconciliation is required",
        )

    try:
        store.create_campaign(
            manifest,
            request_id=f"{stable_request}.create",
            actor=actor,
        )
        _ensure_campaign_projection(root, campaign_id)
        lease = store.acquire_lease(
            campaign_id,
            request_id=f"{stable_request}.lease",
            holder=actor,
            mode="active",
            ttl_seconds=90,
        )
        fence = lease["fencing_token"]
        store.apply_action(
            campaign_id,
            request_id=f"{stable_request}.preflight",
            action="begin-preflight",
            actor=actor,
            target_state="PREFLIGHTING",
            fencing_token=fence,
        )
    except StoreError as exc:
        raise _store_error(exc) from exc

    gates = evaluate_preflight(
        manifest,
        state_root=root,
        expected_host=expected_host,
        envelope_path=envelope_path,
        identity_receipt_path=identity_receipt_path,
        provider_receipt_path=provider_receipt_path,
    )
    gates.append(
        {
            "name": "governed_scientific_executor",
            "passed": False,
            "code": "GOVERNED_EXECUTOR_NOT_IMPLEMENTED",
            "detail": "minimum controller cannot dispatch provider or mutation work",
        }
    )
    receipt = _blocked_receipt(
        manifest,
        campaign_id=campaign_id,
        request_id=stable_request,
        gates=gates,
    )
    try:
        store.checkpoint(
            campaign_id,
            checkpoint_id=f"{stable_request}.blocked-checkpoint",
            actor=actor,
            fencing_token=fence,
            payload={
                "manifest_digest": digest,
                "terminal_intent": "preflight_blocked",
                "blocked_receipt_digest": receipt["receipt_digest"],
                "dispatch_enabled": False,
                "cleanup_state": "not_required",
            },
        )
        store.apply_action(
            campaign_id,
            request_id=f"{stable_request}.drain",
            action="preflight-blocked",
            actor=actor,
            target_state="DRAINING",
            fencing_token=fence,
            payload={"blocked_receipt_digest": receipt["receipt_digest"]},
        )
        store.apply_action(
            campaign_id,
            request_id=f"{stable_request}.closing",
            action="precleanup-closeout",
            actor=actor,
            target_state="CLOSING",
            fencing_token=fence,
            payload={"cleanup_state": "not_required", "scratch_created": False},
        )
        store.apply_action(
            campaign_id,
            request_id=f"{stable_request}.failed",
            action="blocked-closeout",
            actor=actor,
            target_state="FAILED",
            fencing_token=fence,
            payload={"blocked_receipt_digest": receipt["receipt_digest"]},
        )
        store.release_lease(
            campaign_id,
            request_id=f"{stable_request}.release",
            holder=actor,
            fencing_token=fence,
        )
        status = store.get_campaign(campaign_id)
    except StoreError as exc:
        raise _store_error(exc) from exc

    problem = _terminal_state_problem(
        status,
        campaign_id=campaign_id,
        manifest_digest=digest,
    )
    if problem is not None:
        raise CampaignControlError("CAMPAIGN_RUN_INCOMPLETE", problem)
    try:
        _atomic_json(receipt_path, receipt)
    except Exception as exc:
        raise CampaignControlError(
            "BLOCKED_RECEIPT_WRITE_FAILED",
            f"terminal state is durable but blocked receipt materialization failed: {exc}",
        ) from exc
    return {
        **receipt,
        "receipt_path": str(receipt_path),
        "replayed": False,
    }


def list_campaigns(
    *, state: str | None = None, state_root: Path | None = None
) -> list[dict[str, Any]]:
    from dharma_swarm.forge_lab.campaign_store import CampaignStore

    return CampaignStore(state_root or resolve_state_root()).list_campaigns(state)


def campaign_status(
    campaign_id: str | None, *, state_root: Path | None = None
) -> dict[str, Any]:
    if not campaign_id:
        raise CampaignControlError("CAMPAIGN_ID_REQUIRED", "campaign id is required")
    from dharma_swarm.forge_lab.campaign_store import CampaignStore
    from dharma_swarm.forge_lab.campaign_store_schema import StoreError

    try:
        return CampaignStore(state_root or resolve_state_root()).get_campaign(campaign_id)
    except StoreError as exc:
        raise _store_error(exc) from exc


def campaign_events(
    campaign_id: str,
    *,
    after: int = 0,
    state_root: Path | None = None,
) -> list[dict[str, Any]]:
    from dharma_swarm.forge_lab.campaign_store import CampaignStore
    from dharma_swarm.forge_lab.campaign_store_schema import StoreError

    try:
        return CampaignStore(state_root or resolve_state_root()).events(
            campaign_id, after=after
        )
    except StoreError as exc:
        raise _store_error(exc) from exc


def campaign_progress(
    campaign_id: str | None, *, state_root: Path | None = None
) -> dict[str, Any]:
    status = campaign_status(campaign_id, state_root=state_root)
    return {
        "schema": "forge_lab.campaign_progress.v1",
        "campaign": status["campaign"],
        "manifest_digest": status["manifest_digest"],
        "state": status["state"],
        "primary_attempts": {
            "target": status["attempt_budget"],
            "terminal": status["terminal_attempts"],
            "remaining": status["remaining_attempts"],
            "seed_counted": False,
        },
        "usage": status["usage"],
        "lease": status["lease"],
    }
