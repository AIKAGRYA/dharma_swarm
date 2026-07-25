"""Bounded operator lifecycle actions for the minimum campaign controller."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.campaign_contract import resolve_state_root
from dharma_swarm.forge_lab.campaign_control import (
    CampaignControlError,
    _control_root,
    _store_error,
)
from dharma_swarm.forge_lab.campaign_store import CampaignStore
from dharma_swarm.forge_lab.campaign_store_schema import StoreError


def lifecycle_action(
    action: str,
    campaign_id: str,
    *,
    request_id: str | None = None,
    actor: str = "codex-rsi-lab-manager",
    state_root: Path | None = None,
) -> dict[str, Any]:
    """Apply a bounded operator action without ever opening dispatch."""

    if action not in {"pause", "resume", "stop"}:
        raise CampaignControlError("INVALID_ACTION", f"unsupported action: {action}")
    root = state_root or resolve_state_root()
    store = CampaignStore(root)
    try:
        status = store.get_campaign(campaign_id)
    except StoreError as exc:
        raise _store_error(exc) from exc
    stable = request_id or f"{action}-{campaign_id}"
    state = status["state"]

    if state in {"COMPLETED", "FAILED"}:
        if action != "stop":
            raise CampaignControlError(
                "INVALID_TRANSITION", f"{action} is invalid for terminal state {state}"
            )
        receipts = sorted(
            (
                _control_root(root) / "campaigns" / campaign_id / "receipts"
            ).glob("blocked-*.json")
        )
        return {
            "schema": "forge_lab.operator_action_result.v1",
            "action": action,
            "campaign": campaign_id,
            "state": state,
            "idempotent_terminal": True,
            "closeout_receipts": [str(path) for path in receipts],
        }

    if action == "resume":
        if state != "PAUSED":
            raise CampaignControlError(
                "INVALID_TRANSITION", f"resume requires PAUSED, observed {state}"
            )
        raise CampaignControlError(
            "GOVERNED_EXECUTOR_NOT_IMPLEMENTED",
            "resume remains closed until the scientific executor is governed",
        )

    lease = status["lease"]
    fence = lease.get("fencing_token")
    if fence is None:
        try:
            acquired = store.acquire_lease(
                campaign_id,
                request_id=f"{stable}.lease",
                holder=actor,
                mode="terminal_only" if action == "stop" else "active",
                ttl_seconds=90,
            )
            fence = acquired["fencing_token"]
        except StoreError as exc:
            raise _store_error(exc) from exc

    try:
        if action == "pause":
            if state != "RUNNING":
                raise CampaignControlError(
                    "INVALID_TRANSITION", f"pause requires RUNNING, observed {state}"
                )
            first = store.apply_action(
                campaign_id,
                request_id=f"{stable}.request",
                action="pause",
                actor=actor,
                target_state="PAUSING",
                fencing_token=fence,
            )
            store.checkpoint(
                campaign_id,
                checkpoint_id=f"{stable}.quiesced",
                actor=actor,
                fencing_token=fence,
                payload={
                    "dispatch_enabled": False,
                    "inflight_effects": [],
                    "terminal_intent": None,
                },
            )
            final = store.apply_action(
                campaign_id,
                request_id=f"{stable}.paused",
                action="pause-quiesced",
                actor=actor,
                target_state="PAUSED",
                fencing_token=fence,
            )
            return {"requested": first, "result": final}

        first = store.apply_action(
            campaign_id,
            request_id=f"{stable}.request",
            action="stop",
            actor=actor,
            target_state="DRAINING",
            fencing_token=fence,
            payload={"dispatch_enabled": False},
        )
        current = store.get_campaign(campaign_id)
        if current["usage"]["reserved_requests"] or current["terminal_attempts"]:
            raise CampaignControlError(
                "STOP_REQUIRES_RECONCILIATION",
                "campaign remains DRAINING until request/attempt reconciliation",
                result=first,
            )
        store.checkpoint(
            campaign_id,
            checkpoint_id=f"{stable}.precleanup",
            actor=actor,
            fencing_token=fence,
            payload={
                "terminal_intent": "operator_stop",
                "cleanup_state": "pending",
                "residuals": [],
            },
        )
        store.apply_action(
            campaign_id,
            request_id=f"{stable}.closing",
            action="drain-complete",
            actor=actor,
            target_state="CLOSING",
            fencing_token=fence,
            payload={"cleanup_state": "not_required"},
        )
        final = store.apply_action(
            campaign_id,
            request_id=f"{stable}.completed",
            action="cleanup-complete",
            actor=actor,
            target_state="COMPLETED",
            fencing_token=fence,
            payload={"scratch_created": False, "residuals": []},
        )
        return {"requested": first, "result": final}
    except StoreError as exc:
        raise _store_error(exc) from exc
