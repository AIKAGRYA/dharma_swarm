"""Verified campaign authority binding behind the durable executor fuse."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, Mapping

from .campaign_contract import (
    CampaignContractError,
    content_digest,
    verify_operator_envelope,
)
from .campaign_store_schema import (
    StoreError,
    action_receipt,
    action_replay,
    append_event,
    assert_executor_enabled,
    assert_fence,
    assert_holder,
    campaign_row,
    format_time,
    json_object,
    save_action,
    text,
)

if TYPE_CHECKING:
    from .campaign_store import CampaignStore


def authorize_campaign(
    store: CampaignStore,
    campaign: str,
    *,
    request_id: str,
    actor: str,
    envelope: Mapping[str, Any] | str | None,
    trusted_public_keys: Mapping[str, str | bytes] | Iterable[str | bytes],
    expected_host: str,
    fencing_token: int,
) -> dict[str, Any]:
    """Persist one exact, signature-verified, manifest-specific authority."""

    with store._write() as db:
        row = campaign_row(db, campaign)
        observed = store._observed()
        now = format_time(observed)
        assert_fence(
            row,
            fencing_token,
            required=True,
            observed=observed,
        )
        assert_holder(row, actor)
        if row["lease_mode"] != "active":
            raise StoreError("AUTHORITY_MODE_VIOLATION", "active lease is required")
        assert_executor_enabled(db, campaign)
        if row["state"] not in {"CREATED", "PREFLIGHTING"}:
            raise StoreError(
                "AUTHORITY_GATE_CLOSED",
                "authority must be bound before the campaign becomes ready",
            )
        manifest = json_object(row["manifest_json"])
        try:
            verified = verify_operator_envelope(
                envelope,
                manifest,
                trusted_public_keys=trusted_public_keys,
                expected_host=expected_host,
                now=observed,
            )
        except CampaignContractError as exc:
            raise StoreError(exc.code, str(exc)) from exc
        authority_digest = content_digest(verified)
        claim = content_digest(
            {
                "action": "authorize",
                "actor": actor,
                "authority_digest": authority_digest,
                "fencing_token": fencing_token,
            }
        )
        replay = action_replay(db, campaign, request_id, claim)
        if replay:
            return replay
        if row["authority_digest"] and row["authority_digest"] != authority_digest:
            raise StoreError("AUTHORITY_ALREADY_BOUND", "campaign authority is immutable")
        event = append_event(
            db,
            campaign,
            "authority.bound",
            request_id,
            actor,
            row["state"],
            row["state"],
            fencing_token,
            {"authority_digest": authority_digest},
            recorded_at=now,
        )
        receipt = action_receipt(
            campaign,
            request_id,
            "authorize",
            actor,
            row["manifest_digest"],
            fencing_token,
            row["state"],
            event,
            payload={"authority_digest": authority_digest},
            recorded_at=now,
        )
        authority_json = text(verified)
        authority = db.execute(
            """SELECT authority_digest,authority_json FROM authorities
            WHERE campaign_id=?""",
            (campaign,),
        ).fetchone()
        if authority and (
            authority["authority_digest"] != authority_digest
            or authority["authority_json"] != authority_json
        ):
            raise StoreError(
                "AUTHORITY_ALREADY_BOUND",
                "campaign verification record is immutable",
            )
        if not authority:
            db.execute(
                """INSERT INTO authorities(
                campaign_id,manifest_digest,authority_digest,authority_json,
                verified_at,fencing_token,event_sequence)
                VALUES(?,?,?,?,?,?,?)""",
                (
                    campaign,
                    row["manifest_digest"],
                    authority_digest,
                    authority_json,
                    now,
                    fencing_token,
                    event["sequence"],
                ),
            )
        db.execute(
            """UPDATE campaigns SET authority_digest=?,authority_json=?,updated_at=?
            WHERE campaign_id=?""",
            (authority_digest, authority_json, now, campaign),
        )
        save_action(db, campaign, request_id, claim, receipt)
        return receipt
