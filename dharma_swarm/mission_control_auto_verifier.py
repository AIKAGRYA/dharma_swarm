"""Leader-only automatic candidate verification for durable campaigns."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.mission_control_campaign import CampaignSnapshot
from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.mission_control_evidence import (
    IndependentAcceptance,
    candidate_output_digest,
)
from dharma_swarm.mission_control_execution import OwnerExecutionObservation
from dharma_swarm.mission_control_held_out_oracle import (
    G10_GOAL_ID,
    G10_REQUIRED_EVIDENCE_IDS,
    HeldOutOracleError,
    HeldOutOracleIndeterminate,
    collect_g10_evidence,
    load_held_out_oracle_manifest,
    run_held_out_oracle,
)
from dharma_swarm.mission_control_oracle_launcher import OracleSandboxLauncher
from dharma_swarm.mission_control_roster import CampaignAgentRoster
from dharma_swarm.mission_control_verifier import (
    CompletionProvider,
    ModelVerifierError,
    run_verifier,
)
from dharma_swarm.models import Task, TaskStatus
from dharma_swarm.runtime_state import DelegationRun, RuntimeStateStore
from dharma_swarm.task_board import TaskBoard


MAX_VERIFIER_ATTEMPTS = 5
_RUN_SCAN_LIMIT = 1_000


@dataclass(frozen=True, slots=True)
class CandidateReconcileOutcome:
    status: str
    task_id: str = ""
    attempt: int = 0
    acceptance: IndependentAcceptance | None = None
    error: str = ""


class AutomaticCandidateVerifier:
    """Perform at most one exact verifier attempt per leader cycle."""

    def __init__(
        self,
        *,
        runtime: RuntimeStateStore,
        board: TaskBoard,
        roster: CampaignAgentRoster,
        model_provider: CompletionProvider,
        verifier_seat_name: str,
        model_lock_root: Path | str,
        held_out_manifest_path: Path | str,
        held_out_manifest_digest: str,
        oracle_work_root: Path | str,
        oracle_launcher: OracleSandboxLauncher,
    ) -> None:
        self._runtime = runtime
        self._board = board
        self._roster = roster
        self._provider = model_provider
        self._verifier_seat_name = verifier_seat_name
        self._model_lock_root = Path(model_lock_root).expanduser().absolute()
        self._held_manifest_path = Path(held_out_manifest_path).expanduser().absolute()
        self._held_manifest_digest = held_out_manifest_digest
        self._oracle_work_root = Path(oracle_work_root).expanduser().absolute()
        self._oracle_launcher = oracle_launcher

    async def reconcile(
        self,
        snapshot: CampaignSnapshot,
        *,
        effect_ready: Callable[[], None] | None = None,
    ) -> CandidateReconcileOutcome:
        if snapshot.mission_id != self._roster.campaign_id:
            raise MissionControlError("candidate verifier snapshot is foreign to roster")
        if not snapshot.candidate_task_ids:
            return CandidateReconcileOutcome("no_candidate")
        cycle_sequence = snapshot.cycle_sequence
        if type(cycle_sequence) is not int or cycle_sequence < 0:
            raise MissionControlError("candidate verifier cycle sequence is invalid")
        candidate_ids = sorted(snapshot.candidate_task_ids)
        cursor = max(0, cycle_sequence - 1) % len(candidate_ids)
        task_id = candidate_ids[cursor]
        observations = [
            item for item in snapshot.owner_executions if item.ref.task_id == task_id
        ]
        task = await self._board.get(task_id)
        if (
            len(observations) != 1
            or task is None
            or task.status is not TaskStatus.COMPLETED
            or task.metadata.get("mission_id") != snapshot.mission_id
            or not observations[0].terminal
            or not observations[0].succeeded
        ):
            return CandidateReconcileOutcome(
                "blocked", task_id=task_id, error="candidate coordinates are not exact"
            )
        candidate = observations[0]
        goal_id = task.metadata.get("goal_id")
        if goal_id == G10_GOAL_ID:
            return await self._held_out(task, candidate, effect_ready=effect_ready)
        return await self._model(task, candidate, effect_ready=effect_ready)

    async def _held_out(
        self,
        task: Task,
        candidate: OwnerExecutionObservation,
        *,
        effect_ready: Callable[[], None] | None,
    ) -> CandidateReconcileOutcome:
        try:
            manifest = load_held_out_oracle_manifest(
                self._held_manifest_path,
                expected_digest=self._held_manifest_digest,
            )
            producer = await self._runtime.get_delegation_run(candidate.ref.run_id)
            if producer is None or producer.completed_at is None:
                raise HeldOutOracleError("G10 producer lifecycle is incomplete")
            bundle = collect_g10_evidence(
                manifest,
                producer_run_id=candidate.ref.run_id,
                producer_completed_at=producer.completed_at,
            )
            attempt = await self._next_attempt(
                task,
                producer_run_id=candidate.ref.run_id,
                assigned_by="mission-control-held-out-oracle",
                attempt_key="attempt_number",
                output_key="candidate_output_sha256",
                output_digest=candidate_output_digest(candidate.result),
                lineage_key="evidence_bundle_sha256",
                lineage_digest=bundle.digest,
                retry_marker_key="missing_evidence_ids",
            )
        except HeldOutOracleError as exc:
            return CandidateReconcileOutcome(
                "blocked", task_id=task.id, error=str(exc)
            )
        if attempt is None:
            return CandidateReconcileOutcome("exhausted", task_id=task.id)
        try:
            outcome = await run_held_out_oracle(
                runtime=self._runtime,
                manifest_path=self._held_manifest_path,
                expected_manifest_digest=self._held_manifest_digest,
                task=task,
                candidate=candidate,
                work_root=self._oracle_work_root,
                sandbox_launcher=self._oracle_launcher,
                attempt_number=attempt,
                expected_evidence_bundle_sha256=bundle.digest,
                effect_ready=effect_ready,
            )
        except HeldOutOracleIndeterminate as exc:
            return CandidateReconcileOutcome(
                "pending", task_id=task.id, attempt=attempt, error=str(exc)
            )
        except HeldOutOracleError as exc:
            return CandidateReconcileOutcome(
                "blocked", task_id=task.id, attempt=attempt, error=str(exc)
            )
        return CandidateReconcileOutcome(
            outcome.status,
            task_id=task.id,
            attempt=attempt,
            acceptance=outcome.acceptance,
        )

    async def _model(
        self,
        task: Task,
        candidate: OwnerExecutionObservation,
        *,
        effect_ready: Callable[[], None] | None,
    ) -> CandidateReconcileOutcome:
        policy_digest = task.metadata.get("goal_contract_sha256")
        if not isinstance(policy_digest, str):
            return CandidateReconcileOutcome(
                "blocked", task_id=task.id, error="task policy digest is absent"
            )
        attempt = await self._next_attempt(
            task,
            producer_run_id=candidate.ref.run_id,
            assigned_by="mission-control-verifier",
            attempt_key="attempt",
            output_key="producer_output_digest",
            output_digest=candidate_output_digest(candidate.result),
        )
        if attempt is None:
            return CandidateReconcileOutcome("exhausted", task_id=task.id)
        lock_parent = self._model_lock_root
        lock_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock_path = lock_parent / f"{task.id}.{attempt}.lock"
        try:
            acceptance = await run_verifier(
                runtime=self._runtime,
                provider=self._provider,
                roster=self._roster,
                verifier_seat_name=self._verifier_seat_name,
                task=task,
                candidate=candidate,
                policy_digest=policy_digest,
                lock_path=lock_path,
                attempt_number=attempt,
                effect_ready=effect_ready,
            )
        except ModelVerifierError as exc:
            return CandidateReconcileOutcome(
                "failed", task_id=task.id, attempt=attempt, error=str(exc)
            )
        return CandidateReconcileOutcome(
            "accepted" if acceptance.accepted else "rejected",
            task_id=task.id,
            attempt=attempt,
            acceptance=acceptance,
        )

    async def _next_attempt(
        self,
        task: Task,
        *,
        producer_run_id: str,
        assigned_by: str,
        attempt_key: str,
        output_key: str,
        output_digest: str,
        lineage_key: str = "",
        lineage_digest: str = "",
        retry_marker_key: str = "",
    ) -> int | None:
        runs = await self._runtime.list_delegation_runs(
            session_id=f"mission_verifier:{self._roster.campaign_id}",
            task_id=task.id,
            limit=_RUN_SCAN_LIMIT,
        )
        if len(runs) >= _RUN_SCAN_LIMIT:
            raise MissionControlError("candidate verifier run scan saturated")
        relevant = [
            run
            for run in runs
            if run.assigned_by == assigned_by
            and run.parent_run_id == producer_run_id
        ]
        by_attempt: dict[int, DelegationRun] = {}
        for run in relevant:
            value = run.metadata.get(attempt_key)
            if (
                run.metadata.get(output_key) != output_digest
                or type(value) is not int
                or not 1 <= value <= MAX_VERIFIER_ATTEMPTS
                or value in by_attempt
            ):
                raise MissionControlError("candidate verifier attempt history conflicts")
            by_attempt[value] = run
        if not by_attempt:
            return 1
        attempts = sorted(by_attempt)
        if attempts != list(range(1, attempts[-1] + 1)):
            raise MissionControlError("candidate verifier attempt history has a gap")
        for attempt in attempts[:-1]:
            prior = by_attempt[attempt]
            prior_retryable = self._retryable_completed(
                prior,
                lineage_key=lineage_key,
                retry_marker_key=retry_marker_key,
            )
            if prior.status.lower() != "failed" and not prior_retryable:
                raise MissionControlError("candidate verifier lifecycle is out of order")
        latest_attempt = attempts[-1]
        latest_status = by_attempt[latest_attempt].status.lower()
        if lineage_key:
            stored_lineage = by_attempt[latest_attempt].metadata.get(lineage_key)
            if stored_lineage != lineage_digest:
                if latest_status == "completed" and self._retryable_completed(
                    by_attempt[latest_attempt],
                    lineage_key=lineage_key,
                    retry_marker_key=retry_marker_key,
                ):
                    if latest_attempt == MAX_VERIFIER_ATTEMPTS:
                        return None
                    return latest_attempt + 1
                if latest_status in {"running", "completed"}:
                    raise MissionControlError(
                        "candidate verifier evidence lineage conflicts"
                    )
        if latest_status in {"running", "completed"}:
            return latest_attempt
        if latest_status != "failed":
            raise MissionControlError("candidate verifier lifecycle is foreign")
        if latest_attempt == MAX_VERIFIER_ATTEMPTS:
            return None
        return latest_attempt + 1

    @staticmethod
    def _retryable_completed(
        run: DelegationRun,
        *,
        lineage_key: str,
        retry_marker_key: str,
    ) -> bool:
        if not lineage_key or not retry_marker_key or run.status.lower() != "completed":
            return False
        lineage = run.metadata.get(lineage_key)
        missing = run.metadata.get(retry_marker_key)
        return bool(
            isinstance(lineage, str)
            and lineage.startswith("sha256:")
            and type(missing) is list
            and bool(missing)
            and len(missing) == len(set(missing))
            and set(missing) <= set(G10_REQUIRED_EVIDENCE_IDS)
        )


__all__ = [
    "MAX_VERIFIER_ATTEMPTS",
    "AutomaticCandidateVerifier",
    "CandidateReconcileOutcome",
]
