"""RUDRA live Codex app-server binding (spec section 11, Gate 1/3).

``LiveCodexDriver`` implements the frozen ``CodexDriver`` seam over a real
``codex app-server --listen stdio://`` process. The security posture is the
one pinned by ``codex_driver.py`` and is not negotiable:

- outgoing methods stay inside ``ALLOWED_METHODS`` (no ``thread/shellCommand``,
  no ``command/exec``, no filesystem/MCP/auth/config/account RPCs);
- unexpected server-initiated requests are explicitly denied and stop the run
  (``ServerRequestDenied``);
- mutation-capable RPCs are never transport-retried after any request byte
  may have been written; a lost response is reconcile-only;
- every turn reapplies the admitted containment fields (``approvalPolicy:
  never``, exact workcell cwd, and the section 11 ``workspaceWrite``
  ``sandboxPolicy`` with ``networkAccess: false``).

Process authority stays with ``ProcessOwner``: the driver never calls
``subprocess`` directly, never signals a pid, and proves the former tree dead
(through the owner) before any respawn. ``DriverBindError`` marks bind-time
capability failures (missing binary, handshake refusal, containment echo
mismatch); MissionRunner seals those as ``BLOCKED_ENVIRONMENT`` per invariant
9. Mid-turn protocol failures propagate so the crash lands in the journal and
the adopt/recover path reconciles instead of double-executing.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from dharma_swarm.rudra.codex_driver import (
    JsonRpcPeer,
    ProtocolError,
    ServerRequestDenied,
    deterministic_message_id,
)
from dharma_swarm.rudra.contracts import ProcessHandle, TurnObservation
from dharma_swarm.rudra.process_owner import ProcessOwner

LIVE_DRIVER_NAME = "codex_app_server_stdio"
LIVE_DRIVER_ENV = "DHARMA_RUDRA_LIVE_DRIVER"
APP_SERVER_ARGV = ("app-server", "--listen", "stdio://")
SPAWN_ENV_ALLOWLIST = (
    "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "USER", "LOGNAME", "CODEX_HOME",
)

TERMINAL_NOTIFICATION = "turn/completed"
TOKEN_NOTIFICATION = "thread/tokenUsage/updated"
DIFF_NOTIFICATION = "turn/diff/updated"
AGENT_DELTA_NOTIFICATION = "item/agentMessage/delta"

MAX_RESPONSE_CHARS = 1 << 16  # bounded observation, never the acceptance lane
CALL_TIMEOUT_SECONDS = 30.0


class DriverBindError(ProtocolError):
    """Bind-time capability failure: the runner seals BLOCKED_ENVIRONMENT."""


def build_spawn_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Minimal shell-environment allowlist for app-server (spec section 11).

    Provider credentials are never copied here: app-server reads its own
    ``$CODEX_HOME``/``$HOME`` auth surface. Anything outside the allowlist —
    API keys, tokens, agent harness variables — does not cross the spawn."""
    source = os.environ if environ is None else environ
    env = {key: source[key] for key in SPAWN_ENV_ALLOWLIST if key in source}
    env.setdefault("LANG", "C.UTF-8")
    env.setdefault("LC_ALL", "C.UTF-8")
    return env


class _TurnState:
    """Accumulates protocol observations for one in-flight turn."""

    def __init__(self) -> None:
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None
        self.diff_sha256: str | None = None
        self.response_parts: list[str] = []
        self.response_chars = 0
        self.terminal_status: str | None = None

    def response_sha256(self) -> str | None:
        if not self.response_parts:
            return None
        digest = hashlib.sha256()
        for part in self.response_parts:
            digest.update(part.encode())
        return digest.hexdigest()

    def response_text(self) -> str | None:
        return "".join(self.response_parts) or None


class LiveCodexDriver:
    """Bounded stdio JSON-RPC client over a ProcessOwner-spawned app-server."""

    def __init__(
        self,
        *,
        binary_path: str,
        worktree: Path,
        owner: ProcessOwner,
        model: str | None,
        model_provider: str | None,
        reasoning_effort: str | None,
        service_tier: str | None,
        contract_digest: str,
        attempt_key: str,
        argv_suffix: Sequence[str] = APP_SERVER_ARGV,
        spawn_env: Mapping[str, str] | None = None,
        initialize_timeout: float = CALL_TIMEOUT_SECONDS,
    ) -> None:
        self.binary_path = binary_path
        self.worktree = Path(worktree)
        self.owner = owner
        self.model = model
        self.model_provider = model_provider
        self.reasoning_effort = reasoning_effort
        self.service_tier = service_tier
        self.contract_digest = contract_digest
        self.attempt_key = attempt_key
        self.argv_suffix = tuple(argv_suffix)
        self.spawn_env = dict(spawn_env) if spawn_env is not None else None
        self.initialize_timeout = initialize_timeout
        # MissionRunner journals every handle this driver ever spawned.
        self.process_handles: list[ProcessHandle] = []
        # Witness log: undeliverable interrupts/closes are evidence, never
        # silently dropped (process_owner.signal_failures precedent).
        self.witness: list[str] = []
        self.server_agent: str | None = None
        self.last_response_text: str | None = None
        self.thread_id: str | None = None
        self.active_turn_id: str | None = None
        self.handle: ProcessHandle | None = None
        self.closed = False
        self._peer: JsonRpcPeer | None = None
        self._peer_dead = False
        self._proc: subprocess.Popen[Any] | None = None
        self._rpc_seq = 0

    # --- Protocol parameter shapes (codex-cli 0.151.0 v2 schema) -----------

    def sandbox_policy(self) -> dict[str, Any]:
        """The section 11 containment object reapplied to every turn."""
        return {
            "type": "workspaceWrite",
            "writableRoots": [str(self.worktree)],
            "networkAccess": False,
            "excludeSlashTmp": True,
            "excludeTmpdirEnvVar": True,
        }

    def _thread_policy(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "approvalPolicy": "never",
            "cwd": str(self.worktree),
            "sandbox": "workspace-write",
        }
        if self.model is not None:
            params["model"] = self.model
        if self.model_provider is not None:
            params["modelProvider"] = self.model_provider
        if self.service_tier is not None:
            params["serviceTier"] = self.service_tier
        return params

    def _rpc_id(self, method: str) -> str:
        msg_id = deterministic_message_id(
            self.contract_digest, self.attempt_key, method, self._rpc_seq
        )
        self._rpc_seq += 1
        return msg_id

    # --- Lifecycle ----------------------------------------------------------

    def _spawn(self) -> None:
        argv = [self.binary_path, *self.argv_suffix]
        try:
            proc, handle = self.owner.spawn(
                argv,
                env=self.spawn_env if self.spawn_env is not None else build_spawn_env(),
                cwd=self.worktree,
                stdin=subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            raise DriverBindError(f"app-server spawn failed: {exc!r}") from exc
        if proc.stdout is None or proc.stdin is None:
            raise DriverBindError("app-server channel pipes unavailable")
        self._proc = proc
        self.handle = handle
        self.process_handles.append(handle)
        self._peer = JsonRpcPeer(proc.stdout, proc.stdin)
        self._peer_dead = False
        try:
            result, _ = self._peer.call(
                "initialize",
                {"clientInfo": {"name": "rudra", "version": "v0"}},
                timeout_seconds=self.initialize_timeout,
                msg_id=self._rpc_id("initialize"),
            )
            self._peer.send_notification("initialized", {})
        except (ProtocolError, OSError) as exc:
            self._peer_dead = True
            raise DriverBindError(f"app-server handshake failed: {exc}") from exc
        self.server_agent = str(result.get("userAgent", "unknown"))

    def _prove_former_tree_dead(self) -> None:
        """Single mutation owner: no new session while the old one may live."""
        if self.handle is None:
            return
        if not self.owner.prove_dead(self.handle):
            self.owner.terminate_tree(self.handle)
        if not self.owner.prove_dead(self.handle):
            raise DriverBindError(
                "former app-server tree unresolved; refusing a second session"
            )

    def _check_thread_echo(self, result: dict[str, Any]) -> str:
        """Containment/model echo must match the admitted fields (no silent
        downgrade; a reroute is BLOCKED_ENVIRONMENT, never accepted)."""
        thread = result.get("thread")
        if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
            raise DriverBindError("thread start/resume returned no thread id")
        approval = result.get("approvalPolicy")
        if approval is not None and approval != "never":
            raise DriverBindError(f"server approvalPolicy echo {approval!r} != never")
        sandbox = result.get("sandbox")
        if isinstance(sandbox, str) and sandbox != "workspace-write":
            raise DriverBindError(f"server sandbox echo {sandbox!r} != workspace-write")
        if isinstance(sandbox, dict) and sandbox.get("type") != "workspaceWrite":
            raise DriverBindError(f"server sandboxPolicy echo {sandbox!r} rejected")
        if self.model is not None and result.get("model") not in (None, self.model):
            raise DriverBindError(
                f"model reroute: admitted {self.model!r}, server {result.get('model')!r}"
            )
        if self.model_provider is not None and result.get("modelProvider") not in (
            None,
            self.model_provider,
        ):
            raise DriverBindError(
                f"provider reroute: admitted {self.model_provider!r}, "
                f"server {result.get('modelProvider')!r}"
            )
        return thread["id"]

    def start_or_resume(self, *, thread_id: str | None = None) -> str:
        if self.closed:
            raise ProtocolError("driver closed")
        if (
            self._peer is not None
            and not self._peer_dead
            and self.thread_id is not None
            and (thread_id is None or thread_id == self.thread_id)
        ):
            return self.thread_id  # one thread working across turns
        self._prove_former_tree_dead()
        self._spawn()
        assert self._peer is not None
        wanted = thread_id or self.thread_id
        try:
            if wanted is not None:
                result, _ = self._peer.call(
                    "thread/resume",
                    {"threadId": wanted, **self._thread_policy()},
                    timeout_seconds=self.initialize_timeout,
                    msg_id=self._rpc_id("thread/resume"),
                )
            else:
                result, _ = self._peer.call(
                    "thread/start",
                    self._thread_policy(),
                    timeout_seconds=self.initialize_timeout,
                    msg_id=self._rpc_id("thread/start"),
                )
        except (ProtocolError, OSError) as exc:
            self._peer_dead = True
            raise DriverBindError(f"thread start/resume failed: {exc}") from exc
        self.thread_id = self._check_thread_echo(result)
        return self.thread_id

    # --- Turns --------------------------------------------------------------

    def start_turn(
        self, *, prompt: str, logical_seq: int, deadline_seconds: float
    ) -> TurnObservation:
        if self._peer is None or self._peer_dead or self.thread_id is None:
            raise ProtocolError("turn before thread start")
        msg_key = deterministic_message_id(
            self.contract_digest, self.attempt_key, "turn/start", logical_seq
        )
        params: dict[str, Any] = {
            "threadId": self.thread_id,
            "input": [{"type": "text", "text": prompt}],
            "approvalPolicy": "never",
            "cwd": str(self.worktree),
            "sandboxPolicy": self.sandbox_policy(),
            "clientUserMessageId": msg_key,
        }
        if self.model is not None:
            params["model"] = self.model
        if self.reasoning_effort is not None:
            params["effort"] = self.reasoning_effort
        if self.service_tier is not None:
            params["serviceTier"] = self.service_tier
        started = time.monotonic()
        try:
            result, early = self._peer.call(
                "turn/start",
                params,
                timeout_seconds=deadline_seconds,
                msg_id=self._rpc_id("turn/start"),
            )
        except (ProtocolError, OSError) as exc:
            # Mutation RPC: no transport retry after bytes were written. The
            # deterministic clientUserMessageId is the reconciliation key.
            self._peer_dead = True
            raise ProtocolError(f"turn/start lost after write: {exc}") from exc
        turn = result.get("turn")
        if not isinstance(turn, dict) or not isinstance(turn.get("id"), str):
            raise ProtocolError("turn/start returned no turn id")
        self.active_turn_id = turn["id"]
        state = _TurnState()
        try:
            for note in early:
                self._handle_notification(note, self.active_turn_id, state)
            while state.terminal_status is None:
                message = self._peer.read_message(started + deadline_seconds)
                self._handle_in_turn_message(message, self.active_turn_id, state)
        except ProtocolError as exc:
            if "timeout" in str(exc) or "deadline" in str(exc):
                self.interrupt()  # best effort; the turn may keep running
            if "EOF" in str(exc):
                self._peer_dead = True
            raise
        self.active_turn_id = None
        self.last_response_text = state.response_text()
        return TurnObservation(
            thread_id=self.thread_id,
            turn_id=turn["id"],
            terminal_event=TERMINAL_NOTIFICATION,
            input_tokens=state.input_tokens,
            output_tokens=state.output_tokens,
            aggregate_diff_sha256=state.diff_sha256,
            response_sha256=state.response_sha256(),
            reported_complete=state.terminal_status == "completed",
        )

    def _handle_notification(
        self, message: dict[str, Any], turn_id: str, state: _TurnState
    ) -> None:
        method = message.get("method", "")
        params = message.get("params")
        if not isinstance(params, dict):
            raise ProtocolError(f"notification without params object: {message!r}")
        if method == TOKEN_NOTIFICATION:
            usage = params.get("tokenUsage")
            last = usage.get("last") if isinstance(usage, dict) else None
            if isinstance(last, dict):
                input_tokens = last.get("inputTokens")
                output_tokens = last.get("outputTokens")
                if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                    state.input_tokens = input_tokens
                    state.output_tokens = output_tokens
        elif method == DIFF_NOTIFICATION:
            diff = params.get("diff")
            if isinstance(diff, str):
                state.diff_sha256 = hashlib.sha256(diff.encode()).hexdigest()
        elif method == AGENT_DELTA_NOTIFICATION:
            delta = params.get("delta")
            if isinstance(delta, str) and state.response_chars < MAX_RESPONSE_CHARS:
                state.response_parts.append(delta)
                state.response_chars += len(delta)
        elif method == TERMINAL_NOTIFICATION:
            turn = params.get("turn")
            if not isinstance(turn, dict):
                raise ProtocolError("turn/completed without turn object")
            if params.get("threadId") != self.thread_id or turn.get("id") != turn_id:
                raise ProtocolError(
                    f"terminal notification for foreign turn: {message!r}"
                )
            status = turn.get("status")
            if state.terminal_status is not None and status != state.terminal_status:
                raise ProtocolError("conflicting terminal notifications")
            if not isinstance(status, str):
                raise ProtocolError("turn/completed without status")
            state.terminal_status = status
        # Every other notification is an observation the spike did not
        # require; it is ignored, never acted on.

    def _handle_in_turn_message(
        self, message: dict[str, Any], turn_id: str, state: _TurnState
    ) -> None:
        is_response = "result" in message or "error" in message
        if "method" in message and not is_response:
            if "id" in message:
                assert self._peer is not None
                self._peer.send_error_response(
                    message["id"], "RUDRA denies server-initiated requests"
                )
                raise ServerRequestDenied(
                    f"server request {message.get('method')!r} denied mid-turn"
                )
            self._handle_notification(message, turn_id, state)
            return
        raise ProtocolError(f"unexpected message during turn: {message!r}")

    # --- Interrupt and close --------------------------------------------------

    def interrupt(self) -> None:
        if (
            self._peer is None
            or self._peer_dead
            or self.thread_id is None
            or self.active_turn_id is None
        ):
            return
        try:
            self._peer.call(
                "turn/interrupt",
                {"threadId": self.thread_id, "turnId": self.active_turn_id},
                timeout_seconds=10.0,
                msg_id=self._rpc_id("turn/interrupt"),
            )
        except (ProtocolError, OSError) as exc:
            self.witness.append(f"turn/interrupt undeliverable: {exc!r}")

    def close(self) -> None:
        """Best-effort channel close plus owner-mediated tree teardown.

        Never raises: MissionRunner independently proves every journaled
        handle dead and seals FAILED_INVARIANT when it cannot."""
        if self.closed:
            return
        self.closed = True
        peer, self._peer = self._peer, None
        if peer is not None:
            try:
                peer.writer.close()
            except (BrokenPipeError, OSError) as exc:
                self.witness.append(f"channel close failed: {exc!r}")
        if self.handle is not None and not self.owner.prove_dead(self.handle):
            if not self.owner.terminate_tree(self.handle):
                self.witness.append("app-server tree survived close teardown")


def live_driver_factory(
    owner: ProcessOwner,
) -> Callable[[Any, Path], LiveCodexDriver]:
    """Map an admitted mission's executor spec onto the live binding.

    The contract is the config path: binary, model, provider, effort, and
    tier come from the admitted executor spec, never from ambient state."""

    def factory(admitted: Any, worktree: Path) -> LiveCodexDriver:
        executor = admitted.contract.executor
        if executor.driver != LIVE_DRIVER_NAME:
            raise ProtocolError(
                f"executor.driver {executor.driver!r} is not {LIVE_DRIVER_NAME!r}"
            )
        return LiveCodexDriver(
            binary_path=executor.binary.path,
            worktree=worktree,
            owner=owner,
            model=executor.model,
            model_provider=executor.model_provider,
            reasoning_effort=executor.reasoning_effort,
            service_tier=executor.service_tier,
            contract_digest=admitted.contract_digest,
            attempt_key=admitted.attempt_key,
        )

    return factory
