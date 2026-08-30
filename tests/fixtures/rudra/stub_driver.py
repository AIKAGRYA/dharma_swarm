"""Deterministic offline executor for RUDRA tests (v0 smoke lane).

Test scaffolding only — moved out of ``dharma_swarm.rudra.codex_driver``
per the 2026-08-30 deletion review (spec section 6 names that module the
narrow app-server JSON-RPC driver). The stub applies scripted writes only
inside the admitted workcell and only to paths matching the admitted
allowed set — but GoalGate never trusts it; the gate independently
re-verifies every byte.
"""

from __future__ import annotations

import hashlib
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Sequence

from dharma_swarm.rudra.codex_driver import ProtocolError, deterministic_message_id
from dharma_swarm.rudra.contracts import TurnObservation, sha256_json


class StubTurn:
    """One scripted deterministic turn: file writes inside the workcell."""

    def __init__(
        self,
        writes: dict[str, str] | None = None,
        *,
        reported_complete: bool = False,
        input_tokens: int = 1000,
        output_tokens: int = 500,
    ) -> None:
        self.writes = writes or {}
        self.reported_complete = reported_complete
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class StubCodexDriver:
    """Deterministic executor for offline tests. No process, no network."""

    def __init__(
        self,
        workcell_root: Path,
        plan: Sequence[StubTurn],
        *,
        allowed_changed_paths: Sequence[str] = ("**",),
        attempt_key: str = "stub",
        contract_digest: str = "stub",
    ) -> None:
        self.workcell_root = Path(workcell_root)
        self.plan = list(plan)
        self.allowed = list(allowed_changed_paths)
        self.attempt_key = attempt_key
        self.contract_digest = contract_digest
        self.thread_id: str | None = None
        self.turns_taken = 0
        self.closed = False

    def start_or_resume(self, *, thread_id: str | None = None) -> str:
        if self.closed:
            raise ProtocolError("driver closed")
        self.thread_id = thread_id or f"stub-thread-{self.attempt_key}"
        return self.thread_id

    def start_turn(
        self, *, prompt: str, logical_seq: int, deadline_seconds: float
    ) -> TurnObservation:
        if self.thread_id is None:
            raise ProtocolError("turn before thread start")
        # The plan is indexed by the supervisor's logical sequence so a
        # restarted driver replays deterministically (writes are idempotent).
        if logical_seq >= len(self.plan):
            self.turns_taken += 1
            return TurnObservation(
                thread_id=self.thread_id,
                turn_id=f"stub-turn-{logical_seq}",
                terminal_event="turn/completed",
                input_tokens=0,
                output_tokens=0,
                aggregate_diff_sha256=None,
                response_sha256=None,
                reported_complete=True,
            )
        turn = self.plan[logical_seq]
        self.turns_taken += 1
        digest = hashlib.sha256()
        for rel_path, content in sorted(turn.writes.items()):
            if not any(fnmatchcase(rel_path, pat) for pat in self.allowed):
                raise ProtocolError(
                    f"stub write outside admitted set: {rel_path}"
                )
            target = self.workcell_root / rel_path
            if target.is_symlink() or not target.resolve().is_relative_to(
                self.workcell_root.resolve()
            ):
                raise ProtocolError(f"stub write escapes workcell: {rel_path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            digest.update(rel_path.encode() + b"\x00" + content.encode())
        turn_id = deterministic_message_id(
            self.contract_digest, self.attempt_key, "turn/start", logical_seq
        )
        return TurnObservation(
            thread_id=self.thread_id,
            turn_id=turn_id,
            terminal_event="turn/completed",
            input_tokens=turn.input_tokens,
            output_tokens=turn.output_tokens,
            aggregate_diff_sha256=digest.hexdigest() if turn.writes else None,
            response_sha256=sha256_json({"prompt": prompt, "seq": logical_seq}),
            reported_complete=turn.reported_complete,
        )

    def interrupt(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True
