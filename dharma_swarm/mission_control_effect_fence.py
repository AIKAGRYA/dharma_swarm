"""Pinned composition and one-transaction governed repository-effect fence."""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import weakref
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.governed_patch_candidate_bundle import CandidateBundle
from dharma_swarm.governed_patch_effect import (
    _classify_prevalidated_effect,
    _perform_prevalidated_effect,
)
from dharma_swarm.mission_control_a2a_candidate import ExactProposalStoreExpectation
from dharma_swarm.mission_control_a2a_owner_readback import (
    observe_exact_proposal_store_from_connection,
)
from dharma_swarm.mission_control_effect_fence_store import (
    collision,
    exact_issued,
    fence_id_for,
    insert_issued,
    quarantine,
    reissue,
    row_binding,
)
from dharma_swarm.mission_control_effect_owner import (
    inspect_owner_stores,
    owner_transaction,
)
from dharma_swarm.mission_control_effect_owner_match import live_owner_matches
from dharma_swarm.mission_control_effect_readback import read_effect_fence
from dharma_swarm.mission_control_effect_records import (
    EffectConsumption,
    EffectRefusal,
)
from dharma_swarm.mission_control_effect_supervisor import (
    SupervisorAuthorityIssuer,
    supervisor_authority_sha256,
)
from dharma_swarm.mission_control_effect_terminal_store import (
    existing_terminal,
    terminal_matches_current_target,
    terminal_record,
    write_terminal,
)
from dharma_swarm.mission_control_effect_verification import IndependentPatchVerifier
from dharma_swarm.mission_control_effect_warrant import (
    EffectBinding,
    EffectWarrant,
    IndependentPatchVerification,
    SupervisorEffectAuthority,
    effect_warrant_evidence_sha256,
    effect_warrant_sha256,
)
from dharma_swarm.runtime_state_effect_fence import EFFECT_FENCE_TABLE

_MAX_TTL_SECONDS = 30
_COMPOSITIONS: dict[int, tuple[object, IndependentPatchVerifier, SupervisorAuthorityIssuer, int]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _time(raw: object) -> datetime:
    value = datetime.fromisoformat(str(raw))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("effect fence timestamp is naive")
    return value


def _effect_binding(verification, authority, owners) -> EffectBinding:
    return EffectBinding(
        verification.binding, owners, canonical_sha256(verification.to_dict()),
        verification.foundry_canary_evidence_sha256,
        verification.foundry_process_receipt_sha256,
        verification.vibe_process_receipt_sha256,
        verification.vibe_patch_receipt_sha256,
        supervisor_authority_sha256(authority), authority.supervisor_id,
        authority.process_boot_id,
    )


def _lifecycle_rows(db: sqlite3.Connection, binding) -> list[sqlite3.Row]:
    values = (
        binding.mission_attempt_id, binding.mission_claim_id,
        binding.packet_id, binding.delivery_id,
    )
    placeholders = ",".join("?" for _ in values)
    clause = " OR ".join(
        f"{column} IN ({placeholders})" for column in (
            "mission_attempt_id", "mission_claim_id", "packet_id", "delivery_id",
        )
    )
    return db.execute(
        f"SELECT * FROM {EFFECT_FENCE_TABLE} WHERE {clause} OR effect_key=?"
        " OR proposal_id=? OR correlation_id=? LIMIT 8",
        (*values, *values, *values, *values, binding.effect_key,
         binding.proposal_id, binding.correlation_id),
    ).fetchall()


class GovernedPatchEffectFence:
    """One host-pinned verifier/supervisor composition; not caller-rooted."""

    def __init__(self, *_args, **_kwargs) -> None:
        raise TypeError("effect fence must come from the trusted composition root")

    def _valid_composition(self) -> bool:
        entry = _COMPOSITIONS.get(id(self))
        return bool(
            entry is not None and entry[0] is self
            and entry[1] is self._verifier
            and entry[2] is self._supervisor_issuer
            and entry[3] == self._creator_pid == os.getpid()
        )

    def _prune_expired_warrants(self) -> None:
        current = _now()
        for tracked_id, (tracked_ref, _) in list(self._warrants.items()):
            tracked = tracked_ref()
            if tracked is None or tracked.expires_at <= current:
                self._warrants.pop(tracked_id, None)

    def _register_warrant(self, warrant: EffectWarrant) -> EffectWarrant:
        if not self._valid_composition():
            raise ValueError("effect fence cannot register across a process boundary")
        object.__setattr__(warrant, "_seal", self._warrant_sentinel)
        digest = effect_warrant_sha256(warrant)
        warrants = self._warrants
        tracked_id = id(warrant)

        def _on_collected(
            ref: "weakref.ReferenceType[EffectWarrant]",
            *, tracked_id: int = tracked_id, warrants: dict = warrants,
        ) -> None:
            if warrants.get(tracked_id, (None,))[0] is ref:
                warrants.pop(tracked_id, None)

        warrants[tracked_id] = (weakref.ref(warrant, _on_collected), digest)
        return warrant

    def _valid_warrant(self, warrant: EffectWarrant) -> bool:
        entry = self._warrants.get(id(warrant))
        try:
            return bool(
                self._valid_composition()
                and entry is not None and entry[0]() is warrant
                and warrant._seal is self._warrant_sentinel  # noqa: SLF001
                and entry[1] == effect_warrant_sha256(warrant)
            )
        except Exception:
            return False

    def issue_effect_warrant(
        self, runtime_database: Path, task_database: Path,
        expected: ExactProposalStoreExpectation, candidate: CandidateBundle,
        verification: IndependentPatchVerification,
        supervisor_authority: SupervisorEffectAuthority, *, ttl_seconds: int = 15,
    ) -> EffectWarrant | EffectRefusal:
        if (
            not self._valid_composition()
            or type(verification) is not IndependentPatchVerification
            or type(supervisor_authority) is not SupervisorEffectAuthority
        ):
            return EffectRefusal(("canonical_effect_issuance_refused",))
        self._prune_expired_warrants()
        try:
            owners = inspect_owner_stores(runtime_database, task_database)
            canary = verification.binding
            if (
                type(ttl_seconds) is not int or not 0 < ttl_seconds <= _MAX_TTL_SECONDS
                or not self._verifier.validates(verification)
            ):
                raise ValueError("canary capability is not pinned")
            binding = _effect_binding(verification, supervisor_authority, owners)
            with owner_transaction(owners) as db:
                live = observe_exact_proposal_store_from_connection(db, expected)
                current = _now()
                if (
                    not self._supervisor_issuer.validates(
                        supervisor_authority, binding=canary,
                        owner_stores=owners,
                    )
                    or not supervisor_authority.issued_at <= current
                    < supervisor_authority.expires_at
                    or not live_owner_matches(canary, expected, live)
                ):
                    raise ValueError("live owner/supervisor authority drifted")
                target = _classify_prevalidated_effect(binding, candidate)
                if target.disposition != "reissuable":
                    raise ValueError("target is not the exact original preimage")
                current = _now()
                if (
                    not self._supervisor_issuer.validates(
                        supervisor_authority, binding=canary,
                        owner_stores=owners,
                    )
                    or not supervisor_authority.issued_at <= current
                    < supervisor_authority.expires_at
                    or current >= live.lease_stale_after
                ):
                    raise ValueError("authority expired during target inspection")
                expires = min(
                    current + timedelta(seconds=ttl_seconds), live.lease_stale_after,
                    supervisor_authority.expires_at,
                )
                if not current < expires:
                    raise ValueError("effect authority has no live interval")
                token = secrets.token_hex(32)
                token_sha = hashlib.sha256(token.encode("ascii")).hexdigest()
                fence_id = fence_id_for(binding.effect_key)
                warrant_sha = effect_warrant_evidence_sha256(
                    fence_id=fence_id, binding=binding, issued_at=current,
                    expires_at=expires, warrant_token_sha256=token_sha,
                )
                rows = _lifecycle_rows(db, binding)
                if rows:
                    fresh_rotation = bool(
                        len(rows) == 1
                        and binding.supervisor_authority_sha256
                        != rows[0]["supervisor_authority_sha256"]
                        and supervisor_authority.issued_at
                        >= _time(rows[0]["warrant_expires_at"])
                    )
                    if not fresh_rotation or not reissue(
                        db, rows[0], binding, current, expires, token_sha, warrant_sha,
                    ):
                        db.rollback()
                        return EffectRefusal(("effect_fence_occupied",))
                else:
                    insert_issued(db, binding, current, expires, token_sha, warrant_sha)
                db.commit()
            return self._register_warrant(
                EffectWarrant(fence_id, binding, current, expires, token)
            )
        except (ValueError, sqlite3.Error, OSError, RuntimeError):
            return EffectRefusal(("canonical_effect_issuance_refused",))

    def consume_effect_slot(
        self, runtime_database: Path, task_database: Path,
        expected: ExactProposalStoreExpectation, warrant: EffectWarrant,
        candidate: CandidateBundle, *, claimed_by: str,
    ) -> EffectConsumption:
        self._prune_expired_warrants()
        if (
            not self._valid_composition()
            or not self._valid_warrant(warrant)
            or claimed_by != warrant.binding.supervisor_id
        ):
            return EffectRefusal(("fresh_registered_effect_warrant_required",))
        try:
            owners = inspect_owner_stores(runtime_database, task_database)
            if owners != warrant.binding.owner_stores:
                raise ValueError("owner store binding drifted")
            with owner_transaction(owners) as db:
                live = observe_exact_proposal_store_from_connection(db, expected)
                current = _now()
                row = db.execute(
                    f"SELECT * FROM {EFFECT_FENCE_TABLE} WHERE fence_id=?",
                    (warrant.fence_id,),
                ).fetchone()
                if row is None or row_binding(row) != warrant.binding:
                    raise ValueError("effect fence binding drifted")
                if row["state"] == "consumed":
                    result = existing_terminal(db, row)
                    if not terminal_matches_current_target(
                        result, _classify_prevalidated_effect(warrant.binding, candidate),
                    ):
                        raise ValueError("current target drifted after terminal effect")
                    db.commit()
                    return result
                token_sha = hashlib.sha256(warrant.warrant_token.encode("ascii")).hexdigest()
                if (
                    not exact_issued(row, warrant.binding)
                    or _time(row["warrant_issued_at"]) != warrant.issued_at
                    or _time(row["warrant_expires_at"]) != warrant.expires_at
                    or row["warrant_token_sha256"] != token_sha
                    or row["warrant_sha256"] != effect_warrant_sha256(warrant)
                    or not live_owner_matches(warrant.binding.canary, expected, live)
                    or not current < min(warrant.expires_at, live.lease_stale_after)
                ):
                    raise ValueError("effect warrant is stale or consumed")
                observed = _classify_prevalidated_effect(warrant.binding, candidate)
                receipt_id = "rr_governed_patch_effect_" + hashlib.sha256(
                    warrant.binding.effect_key.encode()
                ).hexdigest()
                idem = "idem_" + receipt_id
                if observed.disposition == "recovery_finalizable":
                    db.rollback()
                    return EffectRefusal(("fresh_recovery_supervisor_required",))
                terminal_collision = collision(
                    db, warrant.binding.effect_key, receipt_id, idem,
                )
                if observed.disposition == "quarantine" or terminal_collision:
                    reason = (
                        "terminal_triple_collision" if terminal_collision
                        else observed.reason
                    )
                    quarantine(db, row, reason, observed.observed_sha256)
                    db.commit()
                    return EffectRefusal(("effect_slot_quarantined", reason))
                generation = int(row["claim_generation"]) + 1
                claim_token_sha = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
                consuming = current
                claim_expires = min(warrant.expires_at, live.lease_stale_after)
                cursor = db.execute(
                    f"UPDATE {EFFECT_FENCE_TABLE} SET state='consuming',"
                    "claim_generation=?,claim_token_sha256=?,claimed_by=?,"
                    "claim_expires_at=?,consuming_at=? WHERE fence_id=? AND state='issued'"
                    " AND binding_sha256=? AND warrant_token_sha256=?",
                    (generation, claim_token_sha, claimed_by, claim_expires.isoformat(),
                     consuming.isoformat(), row["fence_id"], row["binding_sha256"], token_sha),
                )
                if cursor.rowcount != 1 or _now() >= claim_expires:
                    raise ValueError("effect claim CAS or last-moment freshness failed")
                mutation = _perform_prevalidated_effect(warrant.binding, candidate)
                if _now() >= claim_expires:
                    raise ValueError("effect authority expired across mutation")
                terminal = terminal_record(
                    row, warrant.binding, mutation, claimed_by=claimed_by,
                    generation=generation, consuming=consuming, recovery_authority=None,
                )
                if terminal.consumed_at >= claim_expires:
                    raise ValueError("effect terminal crossed claim expiry")
                result = write_terminal(db, row, warrant.binding, terminal, claim_token_sha)
                db.commit()
                return result
        except (ValueError, sqlite3.Error, OSError, RuntimeError):
            return EffectRefusal(("effect_consumption_failed_closed",))

    def recover_effect_slot(
        self, runtime_database: Path, task_database: Path,
        expected: ExactProposalStoreExpectation, effect_key: str,
        candidate: CandidateBundle, recovery_authority: SupervisorEffectAuthority,
        *, claimed_by: str,
    ) -> EffectConsumption:
        from dharma_swarm.mission_control_effect_recovery import _recover_effect_slot

        return _recover_effect_slot(
            self,
            runtime_database,
            task_database,
            expected,
            effect_key,
            candidate,
            recovery_authority,
            claimed_by=claimed_by,
        )


def _compose_pinned_effect_fence(
    verifier: IndependentPatchVerifier,
    supervisor_issuer: SupervisorAuthorityIssuer,
) -> GovernedPatchEffectFence:
    """Host composition seam; arbitrary same-process introspection is out of scope.

    Production bootstrap must call this once with host-pinned roots before it
    exposes the returned fence.  It is deliberately absent from ``__all__``;
    the durable nonce/CAS remains the effect authority boundary.
    """

    if (
        type(verifier) is not IndependentPatchVerifier
        or type(supervisor_issuer) is not SupervisorAuthorityIssuer
        or verifier._creator_pid != os.getpid()  # noqa: SLF001
        or supervisor_issuer._creator_pid != os.getpid()  # noqa: SLF001
        or supervisor_issuer._public_key in (  # noqa: SLF001
            verifier._foundry | verifier._vibe  # noqa: SLF001
        )
    ):
        raise ValueError("same-process pinned verifier and supervisor are required")
    fence = object.__new__(GovernedPatchEffectFence)
    fence._verifier = verifier  # noqa: SLF001
    fence._supervisor_issuer = supervisor_issuer  # noqa: SLF001
    fence._creator_pid = os.getpid()  # noqa: SLF001
    fence._warrant_sentinel = object()  # noqa: SLF001
    fence._warrants = {}  # noqa: SLF001
    _COMPOSITIONS[id(fence)] = (fence, verifier, supervisor_issuer, os.getpid())
    return fence


__all__ = ["GovernedPatchEffectFence", "read_effect_fence"]
