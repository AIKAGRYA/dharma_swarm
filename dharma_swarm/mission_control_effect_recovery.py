"""Fresh-supervisor recovery of one issued governed-patch effect slot."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from dharma_swarm.governed_patch_candidate_bundle import CandidateBundle
from dharma_swarm.governed_patch_effect import (
    _classify_prevalidated_effect,
    _durably_classify_prevalidated_effect,
)
from dharma_swarm.mission_control_a2a_candidate import ExactProposalStoreExpectation
from dharma_swarm.mission_control_a2a_owner_readback import (
    observe_exact_proposal_store_from_connection,
)
from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.mission_control_effect_fence_store import (
    collision,
    exact_issued,
    quarantine,
    row_binding,
)
from dharma_swarm.mission_control_effect_owner import (
    inspect_owner_stores,
    owner_transaction,
)
from dharma_swarm.mission_control_effect_owner_match import (
    expired_recovery_matches,
    live_owner_matches,
    recovery_owner_evidence,
)
from dharma_swarm.mission_control_effect_owner_recovery import (
    observe_expired_proposal_for_effect_recovery_from_connection,
)
from dharma_swarm.mission_control_effect_records import (
    EffectConsumption,
    EffectRefusal,
)
from dharma_swarm.mission_control_effect_supervisor import (
    supervisor_authority_sha256,
)
from dharma_swarm.mission_control_effect_terminal_store import (
    existing_terminal,
    recovery_result,
    terminal_matches_current_target,
    terminal_record,
    write_terminal,
)
from dharma_swarm.mission_control_effect_warrant import SupervisorEffectAuthority
from dharma_swarm.runtime_state_effect_fence import EFFECT_FENCE_TABLE

if TYPE_CHECKING:
    from dharma_swarm.mission_control_effect_fence import GovernedPatchEffectFence


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _time(raw: object) -> datetime:
    value = datetime.fromisoformat(str(raw))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("effect fence timestamp is naive")
    return value


def _recover_effect_slot(
    fence: GovernedPatchEffectFence,
    runtime_database: Path,
    task_database: Path,
    expected: ExactProposalStoreExpectation,
    effect_key: str,
    candidate: CandidateBundle,
    recovery_authority: SupervisorEffectAuthority,
    *,
    claimed_by: str,
) -> EffectConsumption:
    """Finalize only an exact durable postimage under fresh recovery authority."""

    from dharma_swarm.mission_control_effect_fence import GovernedPatchEffectFence

    if (
        type(fence) is not GovernedPatchEffectFence
        or not fence._valid_composition()  # noqa: SLF001
        or type(recovery_authority) is not SupervisorEffectAuthority
        or claimed_by != recovery_authority.supervisor_id
    ):
        return EffectRefusal(("recovery_supervisor_identity_required",))
    try:
        owners = inspect_owner_stores(runtime_database, task_database)
        with owner_transaction(owners) as db:
            row = db.execute(
                f"SELECT * FROM {EFFECT_FENCE_TABLE} WHERE effect_key=?", (effect_key,),
            ).fetchone()
            if row is None:
                raise ValueError("effect fence is absent")
            binding = row_binding(row)
            current = _now()
            original_expires = _time(row["warrant_expires_at"])
            historical = False
            try:
                owner = observe_exact_proposal_store_from_connection(db, expected)
                owner_matches = live_owner_matches(binding.canary, expected, owner)
            except MissionControlError:
                if (
                    row["state"] != "issued"
                    or not exact_issued(row, binding)
                    or original_expires > current
                ):
                    raise
                observed = _classify_prevalidated_effect(binding, candidate)
                if observed.disposition != "recovery_finalizable":
                    raise ValueError("expired owner cannot authorize preimage mutation")
                owner = observe_expired_proposal_for_effect_recovery_from_connection(
                    db,
                    expected,
                    mission_attempt_id=binding.mission_attempt_id,
                    mission_claim_id=binding.mission_claim_id,
                    proposal_receipt_id=binding.proposal_receipt_id,
                    proposal_receipt_sha256=binding.proposal_receipt_sha256,
                )
                owner_matches = expired_recovery_matches(binding, expected, owner)
                historical = True
            current = _now()
            terminal_history = bool(
                historical and owner.owner_transition == "canonical_terminal"
            )
            historical_boundary_required = historical and not terminal_history
            fresh_after = (
                original_expires
                if terminal_history
                else max(
                    original_expires,
                    owner.lease_stale_after if historical else original_expires,
                )
            )
            owner_deadline = (
                recovery_authority.expires_at
                if historical
                else min(recovery_authority.expires_at, owner.lease_stale_after)
            )
            valid_recovery = bool(
                binding.owner_stores == owners
                and owner_matches
                and (
                    not historical_boundary_required
                    or original_expires <= owner.lease_stale_after
                )
                and recovery_authority.issued_at >= fresh_after
                and supervisor_authority_sha256(recovery_authority)
                != binding.supervisor_authority_sha256
                and fence._supervisor_issuer.validates(  # noqa: SLF001
                    recovery_authority,
                    binding=binding.canary,
                    owner_stores=owners,
                )
                and recovery_authority.issued_at <= current < owner_deadline
            )
            if not valid_recovery:
                raise ValueError("fresh exact recovery authority is required")
            if row["state"] == "consumed":
                result = existing_terminal(db, row)
                if not terminal_matches_current_target(
                    result, _classify_prevalidated_effect(binding, candidate),
                ):
                    raise ValueError("current target drifted after terminal effect")
                db.commit()
                return result
            if not exact_issued(row, binding) or original_expires > current:
                raise ValueError("expired issued fence and recovery authority required")
            observed = _classify_prevalidated_effect(binding, candidate)
            if observed.disposition == "reissuable":
                db.rollback()
                return EffectRefusal(("exact_preimage_requires_fresh_reissue",))
            if observed.disposition != "recovery_finalizable":
                quarantine(db, row, observed.reason, observed.observed_sha256)
                db.commit()
                return EffectRefusal(("effect_slot_quarantined", observed.reason))
            digest = hashlib.sha256(effect_key.encode()).hexdigest()
            receipt_id = "rr_governed_patch_effect_" + digest
            idem = "idem_rr_governed_patch_effect_" + digest
            if collision(db, effect_key, receipt_id, idem):
                quarantine(db, row, "terminal_triple_collision", observed.observed_sha256)
                db.commit()
                return EffectRefusal(("effect_slot_quarantined",))
            generation = int(row["claim_generation"]) + 1
            claim_sha = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
            claim_expires = owner_deadline
            cursor = db.execute(
                f"UPDATE {EFFECT_FENCE_TABLE} SET state='consuming',claim_generation=?,"
                "claim_token_sha256=?,claimed_by=?,claim_expires_at=?,consuming_at=?"
                " WHERE fence_id=? AND state='issued' AND binding_sha256=?"
                " AND warrant_expires_at=?",
                (
                    generation, claim_sha, claimed_by, claim_expires.isoformat(),
                    current.isoformat(), row["fence_id"], row["binding_sha256"],
                    row["warrant_expires_at"],
                ),
            )
            if cursor.rowcount != 1 or _now() >= claim_expires:
                raise ValueError("recovery claim CAS failed")
            observed = _durably_classify_prevalidated_effect(binding, candidate)
            if observed.disposition != "recovery_finalizable":
                raise ValueError("durable recovery postimage is not exact")
            if _now() >= claim_expires:
                raise ValueError("recovery authority expired across durability sync")
            owner_basis, owner_sha256 = recovery_owner_evidence(owner)
            terminal = terminal_record(
                row,
                binding,
                recovery_result(binding, observed),
                claimed_by=claimed_by,
                generation=generation,
                consuming=current,
                recovery_authority=recovery_authority,
                recovery_owner_basis=owner_basis,
                recovery_owner_observation_sha256=owner_sha256,
            )
            if terminal.consumed_at >= claim_expires:
                raise ValueError("recovery terminal crossed claim expiry")
            result = write_terminal(db, row, binding, terminal, claim_sha)
            db.commit()
            return result
    except (ValueError, sqlite3.Error, OSError, RuntimeError):
        return EffectRefusal(("effect_recovery_failed_closed",))


__all__: list[str] = []
