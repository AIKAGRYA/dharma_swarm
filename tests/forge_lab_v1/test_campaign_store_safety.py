from __future__ import annotations

from copy import deepcopy
import inspect
import sqlite3

from dharma_swarm.forge_lab.campaign_contract import build_manifest
from dharma_swarm.forge_lab.campaign_store import CampaignStore
from test_campaign_store_contract import (
    _Clock,
    _accounting,
    _assert_code,
    _attempt,
    _definition,
    _digest,
    _prepare_powered,
    _raises,
    _settle_success,
)


def test_mutations_are_holder_bound_and_clock_is_constructor_scoped(tmp_path) -> None:
    clock = _Clock()
    store = CampaignStore(tmp_path, clock=clock)
    manifest = build_manifest(_definition())
    campaign = manifest["campaign_name"]
    store.create_campaign(manifest, request_id="create-clock", actor="manager")
    first = store.acquire_lease(
        campaign,
        request_id="lease-clock",
        holder="manager",
        ttl_seconds=3,
    )
    token = first["fencing_token"]
    with _raises() as exc:
        store.apply_action(
            campaign,
            request_id="wrong-holder",
            action="advance",
            actor="intruder",
            target_state="PREFLIGHTING",
            fencing_token=token,
        )
    _assert_code(exc, "LEASE_HOLDER_MISMATCH")
    store.apply_action(
        campaign,
        request_id="right-holder",
        action="advance",
        actor="manager",
        target_state="PREFLIGHTING",
        fencing_token=token,
    )
    with _raises() as exc:
        store.checkpoint(
            campaign,
            checkpoint_id="wrong-checkpoint",
            actor="intruder",
            fencing_token=token,
            payload={"cursor": 0},
        )
    _assert_code(exc, "LEASE_HOLDER_MISMATCH")
    clock.advance(4)
    with _raises() as exc:
        store.checkpoint(
            campaign,
            checkpoint_id="expired-checkpoint",
            actor="manager",
            fencing_token=token,
            payload={"cursor": 0},
        )
    _assert_code(exc, "LEASE_EXPIRED")
    second = store.acquire_lease(
        campaign,
        request_id="lease-takeover",
        holder="successor",
        ttl_seconds=30,
    )
    assert second["fencing_token"] == token + 1
    assert store.has_active_lease()
    clock.advance(31)
    assert not store.has_active_lease()
    for method in (
        CampaignStore.acquire_lease,
        CampaignStore.authorize_campaign,
        CampaignStore.reserve_request,
        CampaignStore.active_leases,
    ):
        assert "now" not in inspect.signature(method).parameters


def test_terminal_attempt_requires_exact_successful_nonempty_proofs(tmp_path) -> None:
    store, manifest, token = _prepare_powered(tmp_path)
    campaign = manifest["campaign_name"]
    with _raises() as exc:
        store.terminal_attempt(
            campaign,
            **_attempt(
                store,
                manifest,
                token,
                "attempt-empty",
                _accounting(),
                evaluation_digest=_digest("c"),
            ),
        )
    _assert_code(exc, "INCOMPLETE_ACCOUNTING")
    accounting = _settle_success(store, campaign, token, "request-one")
    kwargs = _attempt(
        store,
        manifest,
        token,
        "attempt-one",
        accounting,
        evaluation_digest=_digest("c"),
    )
    malformed = deepcopy(kwargs)
    malformed["terminal_receipt"]["attempt_id"] = "attempt-other"
    with _raises() as exc:
        store.terminal_attempt(campaign, **malformed)
    _assert_code(exc, "INVALID_TERMINAL_RECEIPT")
    receipt = store.terminal_attempt(campaign, **kwargs)
    assert store.terminal_attempt(campaign, **kwargs) == receipt
    assert store.get_campaign(campaign)["terminal_attempts"] == 1


def test_request_and_evaluation_proofs_are_single_use(tmp_path) -> None:
    store, manifest, token = _prepare_powered(tmp_path)
    campaign = manifest["campaign_name"]
    first = _settle_success(store, campaign, token, "request-first")
    second = _settle_success(store, campaign, token, "request-second")
    store.terminal_attempt(
        campaign,
        **_attempt(
            store,
            manifest,
            token,
            "attempt-first",
            first,
            evaluation_digest=_digest("c"),
        ),
    )
    with _raises() as exc:
        store.terminal_attempt(
            campaign,
            **_attempt(
                store,
                manifest,
                token,
                "attempt-reuses-request",
                first,
                evaluation_digest=_digest("d"),
            ),
        )
    _assert_code(exc, "ATTEMPT_PROOF_ALREADY_CONSUMED")
    with _raises() as exc:
        store.terminal_attempt(
            campaign,
            **_attempt(
                store,
                manifest,
                token,
                "attempt-reuses-evaluation",
                second,
                evaluation_digest=_digest("c"),
            ),
        )
    _assert_code(exc, "ATTEMPT_PROOF_ALREADY_CONSUMED")
    with sqlite3.connect(store.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM attempt_proof_consumptions"
        ).fetchone()[0] == 2
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
