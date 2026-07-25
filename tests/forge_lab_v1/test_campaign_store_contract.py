from __future__ import annotations

import sqlite3
from copy import deepcopy
from datetime import datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dharma_swarm.forge_lab.campaign_contract import (
    CANONICAL_REPOSITORY,
    CampaignContractError,
    build_manifest,
    canonical_json,
    manifest_digest,
    resolve_state_root,
    verify_operator_envelope,
)
from dharma_swarm.forge_lab.campaign_store import CampaignStore, StoreError


class _Clock:
    def __init__(self, value: str = "2026-07-26T00:00:00Z") -> None:
        self.value = datetime.fromisoformat(value.replace("Z", "+00:00"))

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def _definition(*, powered: bool = False) -> dict:
    limits = {
        "total_tokens": None,
        "total_usd_micros": None,
        "total_requests": None,
        "deadline_utc": None,
        "host_caps": None,
    }
    if powered:
        limits = {
            "total_tokens": 100,
            "total_usd_micros": 1000,
            "total_requests": 2,
            "deadline_utc": "2099-01-01T00:00:00Z",
            "host_caps": {
                "host": "meghadharma",
                "cpu_count_max": 2,
                "memory_bytes_max": 4_000_000_000,
            },
        }
    return {
        "schema": "forge_lab.campaign_definition.v1",
        "campaign_name": "forge-lab-n30-to-1000-v1",
        "source": {
            "repository": CANONICAL_REPOSITORY,
            "release_commit": "309650d5604768a8c90d987170fccf50af6a0536",
            "release_tree": "9648611c3522be11aa69a11c590dd4d06afaec3a",
            "required_identity_hosts": ["github", "mac", "meghadharma"],
            "bootstrap_prior": {
                "run_id": "rsi-n30-20260718T131907Z",
                "type": "MostEvolvedBy",
                "metric": "maximum_generation",
                "generation": 30,
                "budget_valid_rows": 31,
                "budget_total_rows": 31,
                "complete_receipts": True,
                "evidence_scope": "bootstrap_prior_only",
            },
        },
        "bootstrap": {
            "children": 1,
            "tasks_per_generation": 3,
            "novelty_pressure": 0.7,
            "solver_model": "moonshot:kimi-k2.7-code",
            "verifier_model": "moonshot:kimi-k2.7-code",
            "mutator_model": "moonshot:kimi-k2.7-code",
            "per_candidate_token_ceiling": 300000,
            "rng_seed": 20260706,
        },
        "stages": {
            "canary": {"primary_attempts": 1, "required_closeout_digest": None},
            "n30_reproduction": {
                "primary_attempts": 30,
                "required_closeout_digest": None,
            },
            "primary": {
                "primary_attempts": 1000,
                "seed_counts_as_attempt": False,
                "terminal_states": [
                    "accepted",
                    "rejected",
                    "blocked",
                    "failed",
                    "quarantined",
                ],
                "terminal_requirements": [
                    "parent_digest",
                    "mutation_result",
                    "evaluation_digest",
                    "accounting",
                    "terminal_receipt",
                ],
                "non_counting": [
                    "retries",
                    "provider_requests",
                    "tasks",
                    "evaluation_replicates",
                ],
            },
        },
        "limits": limits,
        "claims": {
            "mode": "shadow",
            "evidence_class": "EXPLORE",
            "bootstrap_prior_is_fitness_evidence": False,
            "forbidden": [
                "positive_lift",
                "recursive_self_improvement",
                "promotion",
                "production_fitness",
            ],
        },
        "gates": {
            "operator_envelope_required": True,
            "exact_route": "moonshot:kimi-k2.7-code",
            "canonical_state_required": True,
            "code_identity_hosts": ["github", "mac", "meghadharma"],
            "lifecycle_required": [
                "plan",
                "run",
                "status",
                "progress",
                "pause",
                "resume",
                "stop",
                "checkpoint",
                "idempotent_resume",
                "external_watchdog",
                "reconcile",
                "cleanup",
            ],
        },
    }


def _signed_envelope(manifest: dict) -> tuple[dict, dict[str, str]]:
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    limits = manifest["limits"]
    body = {
        "schema": "forge_lab.operator_envelope.v1",
        "campaign_name": manifest["campaign_name"],
        "manifest_digest": manifest["manifest_digest"],
        "total_tokens": limits["total_tokens"],
        "total_usd_micros": limits["total_usd_micros"],
        "total_requests": limits["total_requests"],
        "deadline_utc": limits["deadline_utc"],
        "host_caps": limits["host_caps"],
        "issued_at": "2026-07-25T00:00:00Z",
        "nonce": "synthetic-offline-nonce-0001",
        "signer": {
            "algorithm": "ed25519",
            "key_id": "test-operator",
            "public_key": public,
        },
    }
    return {**body, "signature": key.sign(canonical_json(body)).hex()}, {
        "test-operator": public
    }


def _assert_code(exc: pytest.ExceptionInfo, code: str) -> None:
    assert exc.value.code == code


def _raises() -> pytest.RaisesExc:
    return pytest.raises((CampaignContractError, StoreError), match=".*")


def _digest(char: str) -> str:
    return "sha256:" + char * 64


def _accounting(
    request_id: str | None = None,
    *,
    tokens: int = 0,
    usd: int = 0,
) -> dict:
    ids = [] if request_id is None else [request_id]
    return {
        "settled": True,
        "request_ids": ids,
        "requests": len(ids),
        "tokens": tokens,
        "usd_micros": usd,
        "lineage_digest": _digest("4"),
        "task_accounting_digest": _digest("5"),
        "usage_digest": _digest("6"),
    }


def _enable_test_executor(store: CampaignStore, campaign: str) -> None:
    """Simulate a future trusted fuse controller; no public opening API exists."""
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "UPDATE executor_fuses SET state='open' WHERE campaign_id=?",
            (campaign,),
        )


def _prepare_powered(tmp_path) -> tuple[CampaignStore, dict, int]:
    store = CampaignStore(tmp_path, clock=_Clock())
    manifest = build_manifest(_definition(powered=True))
    campaign = manifest["campaign_name"]
    store.create_campaign(manifest, request_id="create-powered", actor="manager")
    token = store.acquire_lease(
        campaign,
        request_id="lease-powered",
        holder="manager",
    )["fencing_token"]
    store.apply_action(
        campaign,
        request_id="preflight-powered",
        action="advance",
        actor="manager",
        target_state="PREFLIGHTING",
        fencing_token=token,
    )
    _enable_test_executor(store, campaign)
    envelope, trust = _signed_envelope(manifest)
    store.authorize_campaign(
        campaign,
        request_id="authorize-powered",
        actor="manager",
        envelope=envelope,
        trusted_public_keys=trust,
        expected_host="meghadharma",
        fencing_token=token,
    )
    for state in ("READY", "RUNNING"):
        store.apply_action(
            campaign,
            request_id=f"advance-{state.lower()}",
            action="advance",
            actor="manager",
            target_state=state,
            fencing_token=token,
        )
    return store, manifest, token


def _settle_success(
    store: CampaignStore,
    campaign: str,
    token: int,
    request_id: str,
    *,
    tokens: int = 10,
    usd: int = 20,
) -> dict:
    store.reserve_request(
        campaign,
        request_id=request_id,
        stage="evaluation",
        token_ceiling=tokens,
        usd_micros_ceiling=usd,
        fencing_token=token,
    )
    store.settle_request(
        campaign,
        request_id=request_id,
        status="succeeded",
        actual_tokens=tokens,
        actual_usd_micros=usd,
        fencing_token=token,
    )
    return _accounting(request_id, tokens=tokens, usd=usd)


def _attempt(
    store: CampaignStore,
    manifest: dict,
    token: int,
    attempt_id: str,
    accounting: dict,
    *,
    evaluation_digest: str,
) -> dict:
    mutation = {"outcome": "candidate", "candidate_digest": _digest("b")}
    parent = _digest("a")
    authority = store.get_campaign(manifest["campaign_name"])["authority_digest"]
    terminal = {
        "schema": "forge_lab.primary_attempt_terminal.v1",
        "campaign": manifest["campaign_name"],
        "manifest_digest": manifest["manifest_digest"],
        "attempt_id": attempt_id,
        "status": "accepted",
        "parent_digest": parent,
        "mutation_result": mutation,
        "evaluation_digest": evaluation_digest,
        "accounting_digest": manifest_digest(accounting),
        "authority_digest": authority,
        "fencing_token": token,
    }
    return {
        "attempt_id": attempt_id,
        "status": "accepted",
        "parent_digest": parent,
        "mutation_result": mutation,
        "evaluation_digest": evaluation_digest,
        "accounting": accounting,
        "terminal_receipt": terminal,
        "fencing_token": token,
    }


def test_manifest_is_canonical_strict_and_preserves_unpowered_nulls() -> None:
    manifest = build_manifest(_definition())
    assert manifest["manifest_digest"] == manifest_digest(manifest)
    assert manifest["limits"]["total_tokens"] is None
    assert build_manifest(_definition()) == manifest
    drifted = _definition()
    drifted["bootstrap"]["children"] = 2
    with _raises() as exc:
        build_manifest(drifted)
    _assert_code(exc, "INVALID_N30_PROFILE")
    unknown = _definition()
    unknown["untyped"] = True
    with _raises() as exc:
        build_manifest(unknown)
    _assert_code(exc, "INVALID_SHAPE")


def test_state_resolver_never_falls_back_to_home(tmp_path) -> None:
    with _raises() as exc:
        resolve_state_root({"HOME": str(tmp_path)})
    _assert_code(exc, "STATE_ROOT_UNBOUND")
    assert resolve_state_root({"RSI_LAB_BASE": str(tmp_path)}) == tmp_path / "state"
    assert resolve_state_root({"RSI_LAB_STATE": str(tmp_path / "canonical")}) == (
        tmp_path / "canonical"
    )


def test_operator_envelope_is_exact_trusted_and_fail_closed() -> None:
    manifest = build_manifest(_definition(powered=True))
    envelope, trust = _signed_envelope(manifest)
    verified = verify_operator_envelope(
        envelope,
        manifest,
        trusted_public_keys=trust,
        expected_host="meghadharma",
        now="2026-07-26T00:00:00Z",
    )
    assert verified == envelope
    tampered = deepcopy(envelope)
    tampered["total_requests"] = 1
    with _raises() as exc:
        verify_operator_envelope(
            tampered,
            manifest,
            trusted_public_keys=trust,
            expected_host="meghadharma",
            now="2026-07-26T00:00:00Z",
        )
    _assert_code(exc, "ENVELOPE_BINDING_MISMATCH")


def test_executor_fuse_denies_authorization_and_spend_by_default(tmp_path) -> None:
    store = CampaignStore(tmp_path, clock=_Clock())
    manifest = build_manifest(_definition(powered=True))
    campaign = manifest["campaign_name"]
    store.create_campaign(manifest, request_id="create-fused", actor="manager")
    token = store.acquire_lease(
        campaign,
        request_id="lease-fused",
        holder="manager",
    )["fencing_token"]
    envelope, trust = _signed_envelope(manifest)
    with _raises() as exc:
        store.authorize_campaign(
            campaign,
            request_id="authorize-fused",
            actor="manager",
            envelope=envelope,
            trusted_public_keys=trust,
            expected_host="meghadharma",
            fencing_token=token,
        )
    _assert_code(exc, "GOVERNED_EXECUTOR_NOT_IMPLEMENTED")
    with _raises() as exc:
        store.reserve_request(
            campaign,
            request_id="request-fused",
            stage="evaluation",
            token_ceiling=1,
            usd_micros_ceiling=1,
            fencing_token=token,
        )
    _assert_code(exc, "GOVERNED_EXECUTOR_NOT_IMPLEMENTED")
    assert store.get_campaign(campaign)["authority_digest"] is None


def test_ready_and_running_require_persisted_powered_authority(tmp_path) -> None:
    store = CampaignStore(tmp_path / "powered", clock=_Clock())
    manifest = build_manifest(_definition(powered=True))
    campaign = manifest["campaign_name"]
    store.create_campaign(manifest, request_id="create-ready", actor="manager")
    token = store.acquire_lease(
        campaign, request_id="lease-ready", holder="manager"
    )["fencing_token"]
    store.apply_action(
        campaign,
        request_id="preflight-ready",
        action="advance",
        actor="manager",
        target_state="PREFLIGHTING",
        fencing_token=token,
    )
    _enable_test_executor(store, campaign)
    with _raises() as exc:
        store.apply_action(
            campaign,
            request_id="ready-without-authority",
            action="advance",
            actor="manager",
            target_state="READY",
            fencing_token=token,
        )
    _assert_code(exc, "MISSING_OPERATOR_ENVELOPE")
    envelope, trust = _signed_envelope(manifest)
    store.authorize_campaign(
        campaign,
        request_id="authorize-ready",
        actor="manager",
        envelope=envelope,
        trusted_public_keys=trust,
        expected_host="meghadharma",
        fencing_token=token,
    )
    for state in ("READY", "RUNNING"):
        store.apply_action(
            campaign,
            request_id=f"to-{state.lower()}",
            action="advance",
            actor="manager",
            target_state=state,
            fencing_token=token,
        )
    with sqlite3.connect(store.db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM authorities").fetchone()[0] == 1

    unpowered = CampaignStore(tmp_path / "unpowered", clock=_Clock())
    plain = build_manifest(_definition())
    unpowered.create_campaign(plain, request_id="create-plain", actor="manager")
    plain_token = unpowered.acquire_lease(
        campaign, request_id="lease-plain", holder="manager"
    )["fencing_token"]
    unpowered.apply_action(
        campaign,
        request_id="preflight-plain",
        action="advance",
        actor="manager",
        target_state="PREFLIGHTING",
        fencing_token=plain_token,
    )
    _enable_test_executor(unpowered, campaign)
    with _raises() as exc:
        unpowered.apply_action(
            campaign,
            request_id="ready-plain",
            action="advance",
            actor="manager",
            target_state="READY",
            fencing_token=plain_token,
        )
    _assert_code(exc, "MISSING_SPEND_AUTHORITY")
