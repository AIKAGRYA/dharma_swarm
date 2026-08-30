"""RUDRA MissionRunner: the sole lifecycle writer and bounded state loop.

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md section 12.

    PROPOSED → ADMITTED → RUNNING ↔ VERIFYING
                             |
                             +→ RECOVERING → RUNNING | terminal

GoalGate runs before the first turn, after every turn, after recovery, and
after the local candidate commit. A model ``reported_complete`` event only
requests immediate verification; it never constructs a terminal.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from dharma_swarm.rudra.codex_driver import CodexDriver, deterministic_message_id
from dharma_swarm.rudra.contracts import (
    BudgetSpec,
    DerivedStatus,
    ProcessHandle,
    Terminal,
    derive_mission_key,
    parse_mission,
)
from dharma_swarm.rudra.goal_gate import (
    AdmittedMission,
    CandidateRejected,
    GoalGate,
    GoalGateError,
    GoalGatePassed,
    _fsync_file,
)
from dharma_swarm.rudra.workcell import (
    Journal,
    JournalConflict,
    MissionLock,
    ProcessOwner,
    Workcell,
    rudra_state_root,
)

DriverFactory = Callable[[AdmittedMission, Path], CodexDriver]


class MissionRunner:
    """Single-authority supervisor. One loop, one lock, one journal."""

    def __init__(
        self,
        repo_path: Path,
        state_dir: Path | None = None,
        driver_factory: DriverFactory | None = None,
    ) -> None:
        self.state_root = rudra_state_root(state_dir)
        self.gate = GoalGate(repo_path, state_dir=self.state_root.parent)
        self.owner: ProcessOwner = self.gate.owner
        self.driver_factory = driver_factory

    # --- Entry point --------------------------------------------------------

    def run(self, mission_path: Path) -> dict[str, Any]:
        proposal_text = Path(mission_path).read_text()
        contract = parse_mission(proposal_text)  # cheap parse for keying only
        mission_key = derive_mission_key(
            contract.repository.canonical_remote,
            contract.repository.base_sha,
            contract.digest(),
        )
        mission_dir = self.state_root / "missions" / mission_key
        mission_dir.mkdir(parents=True, exist_ok=True)
        with MissionLock(mission_dir):
            pointer = mission_dir / "current-attempt"
            admitted_path = mission_dir / "admitted.json"
            if admitted_path.exists() and pointer.exists():
                admitted = self._adopt(mission_dir, proposal_text)
            else:
                admitted = self.gate.admit(proposal_text)
                pointer.write_text(admitted.attempt_key + "\n")
                _fsync_file(pointer)
            return self._loop(admitted)

    # --- Recovery (spec 13): no new turn until the former tree is proven dead

    def _adopt(self, mission_dir: Path, proposal_text: str) -> AdmittedMission:
        raw = (mission_dir / "admitted.json").read_bytes().strip()
        contract = parse_mission(proposal_text)
        contract_digest = contract.digest()
        if hashlib.sha256(raw).hexdigest() != contract_digest:
            raise JournalConflict("admitted.json digest drift; quarantining replay")
        mission_key = derive_mission_key(
            contract.repository.canonical_remote,
            contract.repository.base_sha,
            contract_digest,
        )
        pointer = (mission_dir / "current-attempt").read_text().strip()
        attempt_dir = mission_dir / "attempts" / pointer
        attempt_meta = json.loads((attempt_dir / "attempt.json").read_text())
        journal = Journal(attempt_dir / "run.jsonl", mission_key, pointer)
        if journal.has_torn_tail():
            journal.repair_torn_tail()
        journal.rows()  # raises JournalCorrupt on middle-row damage
        if journal.post_seal_violation():
            raise JournalConflict("lifecycle row found after the seal")
        admitted = AdmittedMission(
            contract=contract,
            contract_digest=contract_digest,
            mission_key=mission_key,
            attempt_key=pointer,
            attempt_uuid=attempt_meta["attempt_uuid"],
            mission_dir=str(mission_dir),
            attempt_dir=str(attempt_dir),
            base_digests=attempt_meta["base_digests"],
            git_pointer_sha256=attempt_meta["git_pointer_sha256"],
        )
        if journal.terminal() is not None:
            return admitted  # sealed: relaunch returns the immutable terminal
        if not self.gate.prove_base_preserved(admitted):
            raise RecoveryRequired("base checkout digest drift during downtime")
        handles = [
            ProcessHandle(**row["payload"]["handle"])
            for row in journal.rows()
            if row.get("event") == "PROCESS_SPAWNED"
        ]
        blocked = self.owner.status_for_recovery(handles)
        if blocked is not None:
            raise RecoveryRequired(
                f"former process tree unresolved: {blocked}"
            )
        journal.append("RECOVERED", {"handles": len(handles)})
        return admitted

    # --- Core loop (spec 12) -------------------------------------------------

    @staticmethod
    def _restore_budgets(
        journal: Journal, budgets: BudgetSpec
    ) -> tuple[int, int, float, str | None]:
        """Cumulative budget state rebuilt from the fsynced journal.

        Turns are re-charged from TURN_OBSERVED rows; a turn with missing
        token counts is charged at the conservative per-turn ceiling, exactly
        as the live loop charges it. Wall time runs from the first journaled
        row of the attempt, so downtime counts against the mission instead of
        resetting the clock. The no-delta streak is rebuilt from consecutive
        GATE_RESULT digests (the first pair is excluded: the opening turn is
        never a no-delta turn, matching live-loop semantics). A turn whose
        post-turn digest was never measured by a later gate row is charged
        conservatively as a no-delta turn.
        """
        tokens_used = 0
        turns_observed = 0
        gate_digests: list[str] = []
        attempt_started: float | None = None
        for row in journal.rows():
            if attempt_started is None:
                attempt_started = float(row.get("at", time.time()))
            event = row.get("event")
            if event == "TURN_OBSERVED":
                turns_observed += 1
                observation = row["payload"].get("observation", {})
                if (
                    observation.get("input_tokens") is None
                    or observation.get("output_tokens") is None
                ):
                    tokens_used += budgets.max_tokens_per_turn
                else:
                    tokens_used += (
                        observation["input_tokens"] + observation["output_tokens"]
                    )
            elif event == "GATE_RESULT":
                gate_digests.append(row["payload"].get("digest"))
        no_delta = 0
        for previous, current in zip(gate_digests[1:], gate_digests[2:]):
            no_delta = no_delta + 1 if current == previous else 0
        if turns_observed and turns_observed >= len(gate_digests):
            # A turn completed after the last gate check; its post-turn
            # digest was never measured. Conservative charge (spec 12).
            no_delta += 1
        last_digest = gate_digests[-1] if gate_digests else None
        return (
            tokens_used,
            no_delta,
            attempt_started if attempt_started is not None else time.time(),
            last_digest,
        )

    def _loop(self, admitted: AdmittedMission) -> dict[str, Any]:
        contract = admitted.contract
        budgets = contract.budgets
        attempt_dir = Path(admitted.attempt_dir)
        journal = Journal(
            attempt_dir / "run.jsonl", admitted.mission_key, admitted.attempt_key
        )
        sealed = journal.terminal()
        if sealed is not None:
            return sealed["payload"]  # relaunch returns the immutable terminal

        workcell = Workcell(
            attempt_dir, Path(self.gate.repo_path),
            contract.repository.base_sha, self.state_root,
        )
        mission_stop = Path(admitted.mission_dir) / "stop.request"
        # Spec 12: budget accounting is never optimistically reconstructed.
        # A supervisor restart must not zero cumulative budgets; they are
        # rebuilt from the fsynced journal before the loop resumes.
        tokens_used, no_delta, attempt_started, last_digest = self._restore_budgets(
            journal, budgets
        )

        if self.driver_factory is None:
            return self._seal(
                journal, Terminal.BLOCKED_ENVIRONMENT,
                {"reason": "no executor driver bound (live binding is a later gate)"},
            )
        driver = self.driver_factory(admitted, workcell.worktree)

        turns_used = sum(
            1 for row in journal.rows() if row.get("event") == "TURN_OBSERVED"
        )
        while True:
            # Operator stop wins over any in-flight work (spec 12).
            if mission_stop.exists():
                driver.interrupt()
                return self._seal(
                    journal, Terminal.CANCELLED_OPERATOR, {"reason": "stop.request"}
                )
            if turns_used >= budgets.max_turns:
                return self._seal(journal, Terminal.FAILED_BUDGET, {"budget": "turns"})
            if time.time() - attempt_started >= budgets.max_wall_seconds:
                return self._seal(journal, Terminal.FAILED_BUDGET, {"budget": "wall"})
            if no_delta >= budgets.max_consecutive_no_delta_turns:
                return self._seal(
                    journal, Terminal.FAILED_BUDGET, {"budget": "no-delta"}
                )

            self.gate.rehash_admitted(admitted)
            gate = self.gate.evaluate(admitted)
            journal.append(
                "GATE_RESULT",
                {"green": gate.green, "digest": gate.subject_digest,
                 "reasons": gate.reasons},
            )
            if gate.green:
                return self._freeze_and_reproduce(
                    admitted, journal, driver, workcell, gate
                )

            driver.start_or_resume()
            for handle in getattr(driver, "process_handles", []):
                journal.append("PROCESS_SPAWNED", {"handle": handle.model_dump()})
            seq = turns_used
            msg_id = deterministic_message_id(
                admitted.contract_digest, admitted.attempt_key, "turn/start", seq
            )
            journal.append("TURN_INTENT", {"message_id": msg_id, "seq": seq})
            prompt = self._compact_context(admitted, gate, tokens_used, seq)
            observation = driver.start_turn(
                prompt=prompt,
                logical_seq=seq,
                deadline_seconds=float(budgets.max_turn_seconds),
            )
            if observation.input_tokens is None or observation.output_tokens is None:
                tokens_used += budgets.max_tokens_per_turn  # conservative charge
            else:
                tokens_used += observation.input_tokens + observation.output_tokens
            journal.append(
                "TURN_OBSERVED",
                {"message_id": msg_id, "seq": seq,
                 "observation": observation.model_dump(mode="json")},
            )
            turns_used += 1
            if tokens_used >= budgets.max_total_tokens:
                return self._seal(
                    journal, Terminal.FAILED_BUDGET, {"budget": "tokens"}
                )
            _, _, digest = self.gate.workspace_snapshot(
                workcell.worktree, contract.repository.base_sha
            )
            if digest == last_digest:
                no_delta += 1
            else:
                no_delta = 0
            last_digest = digest

    # --- Freeze, reproduce, seal (spec 8 candidate freeze; requirements 4-8)

    def _freeze_and_reproduce(
        self,
        admitted: AdmittedMission,
        journal: Journal,
        driver: CodexDriver,
        workcell: Workcell,
        gate: Any,
    ) -> dict[str, Any]:
        contract = admitted.contract
        driver.interrupt()
        driver.close()
        for handle in getattr(driver, "process_handles", []):
            if not self.owner.prove_dead(handle):
                self.owner.terminate_tree(handle)
                if not self.owner.prove_dead(handle):
                    return self._seal(
                        journal, Terminal.FAILED_INVARIANT,
                        {"reason": "model process tree alive at freeze"},
                    )
        self.gate.rehash_admitted(admitted)
        journal.effect_intent("candidate-freeze", {"digest": gate.subject_digest})
        head = workcell.head_sha()
        if head != contract.repository.base_sha:
            # R16: candidate committed before the terminal event. The
            # immutable commit is reused; verifiers rerun against it fresh.
            candidate = head
        else:
            try:
                candidate = self.gate.freeze_candidate(admitted, gate)
            except GoalGateError as exc:
                return self._seal(
                    journal, Terminal.FAILED_INVARIANT, {"reason": str(exc)}
                )
        journal.effect_result("candidate-freeze", {"candidate_sha": candidate})
        journal.append("CANDIDATE_FROZEN", {"candidate_sha": candidate})
        try:
            passed: GoalGatePassed = self.gate.verify_candidate(admitted, candidate)
        except CandidateRejected as exc:
            journal.append("CANDIDATE_REJECTED", {"reason": str(exc)})
            return self._seal(
                journal, Terminal.FAILED_INVARIANT,
                {"reason": f"final verification red: {exc}",
                 "candidate_sha": candidate},
            )
        _, _, current_digest = self.gate.workspace_snapshot(
            workcell.worktree, contract.repository.base_sha
        )
        reproduced = self.gate.promote(
            None, passed, admitted, current_digest
        )
        if not self.gate.prove_base_preserved(admitted):
            return self._seal(
                journal, Terminal.FAILED_INVARIANT,
                {"reason": "base checkout digest drift during mission"},
            )
        return self._seal(
            journal, Terminal.COMPLETE_REPRODUCED,
            {"candidate_sha": candidate,
             "reproduced": reproduced.model_dump(mode="json")},
        )

    def _seal(
        self, journal: Journal, terminal: Terminal, payload: dict[str, Any]
    ) -> dict[str, Any]:
        row = journal.compare_and_seal_terminal(str(terminal), payload)
        return row["payload"]

    def _compact_context(
        self,
        admitted: AdmittedMission,
        gate: Any,
        tokens_used: int,
        seq: int,
    ) -> str:
        """Bounded handoff: objective, digests, fresh failures, budgets."""
        budgets = admitted.contract.budgets
        parts = [
            f"OBJECTIVE: {admitted.contract.objective}",
            f"CONTRACT_DIGEST: {admitted.contract_digest}",
            f"BASE_SHA: {admitted.contract.repository.base_sha}",
            "FRESH_VERIFIER_FAILURES: " + ("; ".join(gate.reasons) or "none"),
            f"BUDGETS: turn {seq + 1}/{budgets.max_turns}, "
            f"tokens {tokens_used}/{budgets.max_total_tokens}",
        ]
        if seq > 0:
            parts.append("CONTEXT_DISCONTINUITY: prior thread state is not assumed")
        return "\n".join(parts)

    # --- Read-only status and durable stop request ---------------------------

    def _sealed_terminal(self, mission_dir: Path) -> dict[str, Any] | None:
        """Sealed terminal payload for the current attempt, if any."""
        pointer = mission_dir / "current-attempt"
        if not pointer.exists():
            return None
        journal = Journal(
            mission_dir / "attempts" / pointer.read_text().strip() / "run.jsonl",
            "?", "?",
        )
        sealed = journal.terminal()
        return sealed["payload"] if sealed else None

    def status(self, mission_id: str) -> dict[str, Any]:
        mission_dir = self._find_mission_dir(mission_id)
        if mission_dir is None:
            return {"mission_id": mission_id, "status": "UNKNOWN"}
        try:
            terminal = self._sealed_terminal(mission_dir)
        except Exception:
            return {"mission_id": mission_id, "status": "RECOVERY_REQUIRED"}
        if terminal is not None:
            return {
                "mission_id": mission_id, "status": terminal.get("terminal"),
                "terminal": terminal,
            }
        # Liveness requires the kernel lock, never stale files.
        probe = mission_dir / "supervisor.lock"
        running = False
        if probe.exists():
            fd = os.open(probe, os.O_RDWR)
            try:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    running = False  # lock free: no live supervisor
                except OSError:
                    running = True
            finally:
                os.close(fd)
        return {
            "mission_id": mission_id,
            "status": "RUNNING" if running else str(DerivedStatus.RECOVERY_REQUIRED),
        }

    def stop(self, mission_id: str, reason: str) -> dict[str, Any]:
        mission_dir = self._find_mission_dir(mission_id)
        if mission_dir is None:
            return {"mission_id": mission_id, "result": "UNKNOWN"}
        terminal = self._sealed_terminal(mission_dir)
        if terminal is not None:
            return {
                "mission_id": mission_id,
                "result": "ALREADY_SEALED",
                "terminal": terminal,
            }
        stop_file = mission_dir / "stop.request"
        stop_file.write_text(json.dumps({"reason": reason, "at": time.time()}) + "\n")
        _fsync_file(stop_file)
        return {"mission_id": mission_id, "result": "STOP_REQUESTED"}

    def _find_mission_dir(self, mission_id: str) -> Path | None:
        missions = self.state_root / "missions"
        if not missions.exists():
            return None
        for child in sorted(missions.iterdir()):
            identity = child / "identity.json"
            if not identity.exists():
                continue
            try:
                data = json.loads(identity.read_text())
            except json.JSONDecodeError:
                continue
            if data.get("mission_id") == mission_id:
                return child
        return None


class RecoveryRequired(RuntimeError):
    """Derived status while the lifecycle remains RECOVERING."""
