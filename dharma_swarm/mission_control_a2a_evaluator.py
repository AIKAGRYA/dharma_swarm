"""Projection-only promotion evaluator for exact Mission Control A2A evidence."""

from __future__ import annotations

from typing import Any, Mapping

from dharma_swarm.mission_control_a2a import (
    _SHA256,
    A2AEvidencePhase,
    A2AExecutionObservation,
    _identity_matches_expected,
)
from dharma_swarm.mission_control_a2a_projection import MissionControlA2AProjection
from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.mission_control_verification import (
    ExpectedPromotionBindings,
    PatchPromotionVerifier,
    PatchPromotionWarrant,
    PromotionRefusal,
)


class A2APatchPromotionEvaluator:
    """Revalidate and return only a projection-only in-process warrant."""

    def __init__(
        self,
        projection: MissionControlA2AProjection,
        *,
        verifier: PatchPromotionVerifier,
    ) -> None:
        if type(verifier) is not PatchPromotionVerifier:
            raise TypeError("verifier must be an exact PatchPromotionVerifier")
        self._projection = projection
        self._verifier = verifier

    async def issue_warrant(
        self,
        observation: A2AExecutionObservation,
        *,
        expected: ExpectedPromotionBindings,
        signed_patch_verification: Mapping[str, Any] | None,
        vibe_halt_receipt: Mapping[str, Any] | None,
    ) -> PatchPromotionWarrant | PromotionRefusal:
        if not observation or observation.phase != A2AEvidencePhase.VERIFYING:
            return PromotionRefusal(("unsealed_or_nonverifying_a2a_observation",))
        try:
            current = await self._projection.observe(
                expected.mission_id,
                expected.task_id,
                expected=expected,
            )
        except MissionControlError:
            return PromotionRefusal(("a2a_observation_revalidation_failed",))
        if not current or current != observation:
            return PromotionRefusal(("a2a_observation_changed_before_evaluation",))
        if (
            current.candidate_digest != expected.candidate_digest
            or current.diff_sha256 != expected.diff_sha256
            or current.base_sha != expected.base_sha
            or current.authorized_source_files != expected.authorized_source_files
            or current.executor_run_id != expected.executor_run_id
            or not current.proposal_receipt_id
            or not _SHA256.fullmatch(current.proposal_receipt_sha256)
        ):
            return PromotionRefusal(("a2a_candidate_observation_mismatch",))
        try:
            durable_foundry = self._projection._execution_identity(  # noqa: SLF001
                expected.foundry_verifier.run_id,
            )
        except MissionControlError:
            return PromotionRefusal(("invalid_durable_foundry_identity",))
        if durable_foundry is None or not _identity_matches_expected(
            durable_foundry, expected, role="foundry"
        ):
            return PromotionRefusal(("missing_exact_durable_foundry_identity",))
        try:
            durable_vibe = self._projection._execution_identity(  # noqa: SLF001
                expected.vibe_verifier.run_id,
            )
        except MissionControlError:
            return PromotionRefusal(("invalid_durable_vibe_identity",))
        if durable_vibe is None or not _identity_matches_expected(
            durable_vibe, expected, role="vibe_halt"
        ):
            return PromotionRefusal(("missing_exact_durable_vibe_identity",))
        result = self._verifier.evaluate(
            signed_patch_verification,
            expected=expected,
            vibe_halt_receipt=vibe_halt_receipt,
        )
        if isinstance(result, PromotionRefusal):
            return result
        if not result:
            return PromotionRefusal(("unsealed_promotion_warrant",))
        return result


__all__ = ["A2APatchPromotionEvaluator"]
