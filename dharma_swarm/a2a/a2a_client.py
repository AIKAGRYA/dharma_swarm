"""A2A Client -- delegates tasks to other agents.

Discovers agent skills via cards, selects the best agent,
sends tasks, and monitors completion. This is the outbound half
of the A2A protocol.

A2A 1.0 features:
- Cycle detection on dispatch chains (monotonic-progress guard)
- context_id threading across related delegations
- Uses spec-standard /tasks endpoint (falls back to /a2a/tasks)

Local agents: direct dispatch via A2AServer (in-process).
Remote agents: HTTP dispatch via node gateways.

Usage::

    client = A2AClient(registry=card_registry, server=a2a_server)

    # Find who can do code review
    agents = client.discover("code_review")

    # Delegate to best match (auto-routes local vs remote)
    result = client.delegate("code_review", "Please review auth module")

    # Or delegate to a specific agent
    result = client.delegate_to("reviewer-1", "Review this PR")

    # Async remote delegation
    result = await client.delegate_to_async("agni-coder", "Fix the bug")
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from dharma_swarm.a2a.agent_card import AgentCard, CardRegistry
from dharma_swarm.a2a.spine_adapter import submit_task_via_spine_sync
from dharma_swarm.a2a.a2a_server import (
    A2AMessage,
    A2AServer,
    A2ATask,
    A2ATaskStatus,
)

logger = logging.getLogger(__name__)

# Max depth before cycle detection rejects a delegation chain
_MAX_DELEGATION_DEPTH = 10


class DelegationResult:
    """Result of a task delegation attempt.

    Attributes:
        success: Whether the task completed successfully.
        task: The A2ATask (with full lifecycle data).
        agent_name: Name of the agent that handled the task.
        result_text: The text result (convenience accessor).
        error: Error message if failed.
    """

    __slots__ = ("success", "task", "agent_name", "result_text", "error")

    def __init__(
        self,
        success: bool,
        task: A2ATask | None = None,
        agent_name: str = "",
        result_text: str = "",
        error: str = "",
    ) -> None:
        self.success = success
        self.task = task
        self.agent_name = agent_name
        self.result_text = result_text
        self.error = error

    def __repr__(self) -> str:
        status = "ok" if self.success else "FAILED"
        return f"DelegationResult({status}, agent={self.agent_name!r})"


class A2AClient:
    """Client for discovering agents and delegating tasks via A2A.

    Requires a CardRegistry for discovery and an A2AServer for dispatch.
    Both are injected -- the client does not own their lifecycle.

    Args:
        registry: Card registry for agent discovery.
        server: A2A server for task dispatch.
        default_from: Default requester agent name.
    """

    def __init__(
        self,
        registry: CardRegistry,
        server: A2AServer,
        default_from: str = "client",
        node_registry: Any | None = None,
        max_depth: int = _MAX_DELEGATION_DEPTH,
    ) -> None:
        self._registry = registry
        self._server = server
        self._default_from = default_from
        self._node_registry = node_registry
        self._max_depth = max_depth
        # Track active delegation chains: context_id -> set of (from_agent, to_agent, capability)
        self._active_chains: dict[str, set[tuple[str, str, str]]] = {}
        self._chain_depth: dict[str, int] = {}

    # -- discovery -----------------------------------------------------------

    def discover(self, capability: str) -> list[AgentCard]:
        """Find agents with a matching capability.

        Args:
            capability: Search string matched against capability names/descriptions.

        Returns:
            List of AgentCards that match, sorted by name.
        """
        return self._registry.discover(capability)

    def discover_available(self, capability: str) -> list[AgentCard]:
        """Find available agents (not busy/dead) with a matching capability.

        Args:
            capability: Search string.

        Returns:
            List of available matching AgentCards.
        """
        matches = self._registry.discover(capability)
        return [c for c in matches if c.status in ("idle", "starting")]

    # -- delegation ----------------------------------------------------------

    def _check_cycle(
        self,
        context_id: str,
        from_agent: str,
        to_agent: str,
        capability: str,
    ) -> str | None:
        """Check for cycles in the delegation chain.

        Returns an error message if a cycle or depth limit is detected,
        None if the delegation is safe.
        """
        if not context_id:
            return None

        chain_key = (from_agent, to_agent, capability)
        chain = self._active_chains.setdefault(context_id, set())
        depth = self._chain_depth.get(context_id, 0)

        if chain_key in chain:
            return (
                f"Cycle detected: {from_agent} -> {to_agent} "
                f"(capability={capability!r}) already in chain for context {context_id}"
            )

        if depth >= self._max_depth:
            return (
                f"Delegation depth limit ({self._max_depth}) reached "
                f"for context {context_id}"
            )

        chain.add(chain_key)
        self._chain_depth[context_id] = depth + 1
        return None

    def reset_chains(self, context_id: str | None = None) -> None:
        """Clear cycle detection state for a context (or all if None)."""
        if context_id is None:
            self._active_chains.clear()
            self._chain_depth.clear()
        else:
            self._active_chains.pop(context_id, None)
            self._chain_depth.pop(context_id, None)

    def notify_terminal(self, context_id: str, from_agent: str,
                        to_agent: str, capability: str) -> None:
        """Release a specific chain entry when its task reaches terminal state.

        Called after a delegation completes, fails, or is cancelled.
        This prevents false-positive cycle detection in long-lived
        contexts where earlier chains have already finished.
        """
        if not context_id:
            return
        chain = self._active_chains.get(context_id)
        if chain is None:
            return
        chain_key = (from_agent, to_agent, capability)
        chain.discard(chain_key)
        depth = self._chain_depth.get(context_id, 0)
        if depth > 0:
            self._chain_depth[context_id] = depth - 1
        else:
            # Floor at zero — prevent negative drift from stray calls
            self._chain_depth[context_id] = 0

    def delegate(
        self,
        capability: str,
        message: str,
        from_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
        context_id: str = "",
    ) -> DelegationResult:
        """Discover the best agent for a capability and delegate a task.

        Includes cycle detection: rejects if the same (from, to, capability)
        triple already exists in the context's delegation chain, or if
        the chain depth exceeds the configured maximum.

        Args:
            capability: The capability needed.
            message: Task description / instruction text.
            from_agent: Requester name (defaults to self._default_from).
            metadata: Optional metadata to attach to the task.
            context_id: A2A 1.0 context for grouping related tasks.

        Returns:
            DelegationResult with the outcome.
        """
        agents = self.discover_available(capability)
        if not agents:
            agents = self.discover(capability)

        if not agents:
            logger.warning("No agent found for capability: %s", capability)
            return DelegationResult(
                success=False,
                error=f"No agent found with capability: {capability!r}",
            )

        card = agents[0]
        return self.delegate_to(
            card.name,
            message,
            capability=capability,
            from_agent=from_agent,
            metadata=metadata,
            context_id=context_id,
        )

    def delegate_to(
        self,
        agent_name: str,
        message: str,
        capability: str = "",
        from_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
        context_id: str = "",
    ) -> DelegationResult:
        """Delegate a task to a specific named agent.

        Routes automatically: local dispatch for local:// agents,
        synchronous HTTP for remote agents. Includes cycle detection.

        Args:
            agent_name: Target agent name.
            message: Task description / instruction text.
            capability: Capability being requested (optional).
            from_agent: Requester name.
            metadata: Optional metadata.
            context_id: A2A 1.0 context for grouping related tasks.

        Returns:
            DelegationResult with the outcome.
        """
        sender = from_agent or self._default_from
        card = self._registry.get(agent_name)
        if card is None:
            return DelegationResult(
                success=False,
                error=f"Agent not found in registry: {agent_name!r}",
            )

        cycle_err = self._check_cycle(context_id, sender, agent_name, capability)
        if cycle_err:
            logger.warning("Cycle guard: %s", cycle_err)
            return DelegationResult(success=False, error=cycle_err)

        if _is_remote(card):
            return self._dispatch_remote_sync(
                card, message, capability, sender, metadata, context_id,
            )
        return self._dispatch_local(
            card, message, capability, sender, metadata, context_id,
        )

    async def delegate_to_async(
        self,
        agent_name: str,
        message: str,
        capability: str = "",
        from_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
        timeout: float = 60.0,
        context_id: str = "",
    ) -> DelegationResult:
        """Async version of delegate_to for remote agents.

        Preferred for remote dispatch — non-blocking HTTP.
        Falls back to local dispatch for local agents.
        Includes cycle detection.
        """
        sender = from_agent or self._default_from
        card = self._registry.get(agent_name)
        if card is None:
            return DelegationResult(
                success=False,
                error=f"Agent not found in registry: {agent_name!r}",
            )

        cycle_err = self._check_cycle(context_id, sender, agent_name, capability)
        if cycle_err:
            logger.warning("Cycle guard: %s", cycle_err)
            return DelegationResult(success=False, error=cycle_err)

        if _is_remote(card):
            return await self._dispatch_remote_async(
                card, message, capability, sender, metadata, timeout, context_id,
            )
        return self._dispatch_local(
            card, message, capability, sender, metadata, context_id,
        )

    # -- internal dispatch ---------------------------------------------------

    def _dispatch_local(
        self,
        card: AgentCard,
        message: str,
        capability: str,
        from_agent: str,
        metadata: dict[str, Any] | None,
        context_id: str = "",
    ) -> DelegationResult:
        """Dispatch to local A2AServer through the Runtime Truth Spine.

        Spine-adopted: every in-process delegation flows through
        ``invoke_agent()`` and emits exactly one ``EvidenceReceipt``.
        """
        trace_id = _current_trace_id()
        task = A2ATask(
            from_agent=from_agent,
            to_agent=card.name,
            capability=capability,
            context_id=context_id,
            history=[A2AMessage.text(message)],
            trace_id=trace_id,
            metadata=metadata or {},
        )
        logger.info(
            "Local delegation to %s: capability=%s, message=%s...",
            card.name, capability, message[:80],
        )
        result_task, receipt = submit_task_via_spine_sync(
            self._server, task, router_name="a2a_client",
        )
        if receipt.status == "failed" and not receipt.provider_attempted:
            # submit() itself errored before dispatch: no task lifecycle to
            # report — surface the failure as an unsuccessful delegation.
            return DelegationResult(
                success=False,
                task=result_task,
                agent_name=card.name,
                error=receipt.error_detail or "spine dispatch failed",
            )
        # Auto-release chain entry when task reaches terminal state
        if result_task.is_terminal():
            self.notify_terminal(context_id, from_agent, card.name, capability)
        return DelegationResult(
            success=result_task.status == A2ATaskStatus.COMPLETED,
            task=result_task,
            agent_name=card.name,
            result_text=result_task.result,
            error=result_task.error,
        )

    def _dispatch_remote_sync(
        self,
        card: AgentCard,
        message: str,
        capability: str,
        from_agent: str,
        metadata: dict[str, Any] | None,
        context_id: str = "",
    ) -> DelegationResult:
        """Synchronous HTTP dispatch to a remote node gateway."""
        url = f"{card.endpoint.rstrip('/')}/tasks"
        headers = {"Content-Type": "application/json"}
        api_key = card.metadata.get("api_key", "")
        if api_key:
            headers["X-A2A-Key"] = api_key

        body: dict[str, Any] = {
            "from_agent": from_agent,
            "capability": capability,
            "messages": [{"role": "user", "content": message}],
            "metadata": metadata or {},
        }
        trace_id = _current_trace_id()
        if trace_id:
            body["trace_id"] = trace_id
        if context_id:
            body["context_id"] = context_id

        logger.info(
            "Remote delegation to %s at %s: capability=%s",
            card.name, card.endpoint, capability,
        )

        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
            status_str = data.get("status", "failed")
            return DelegationResult(
                success=status_str in ("completed", "working", "submitted"),
                agent_name=card.name,
                result_text=data.get("result", "") or "",
                error=data.get("error", "") or "",
            )
        except Exception as exc:
            logger.error("Remote delegation to %s failed: %s", card.name, exc)
            return DelegationResult(
                success=False,
                agent_name=card.name,
                error=f"Remote dispatch failed: {exc}",
            )

    async def _dispatch_remote_async(
        self,
        card: AgentCard,
        message: str,
        capability: str,
        from_agent: str,
        metadata: dict[str, Any] | None,
        timeout: float = 60.0,
        context_id: str = "",
    ) -> DelegationResult:
        """Async HTTP dispatch to a remote node gateway."""
        url = f"{card.endpoint.rstrip('/')}/tasks"
        headers = {"Content-Type": "application/json"}
        api_key = card.metadata.get("api_key", "")
        if api_key:
            headers["X-A2A-Key"] = api_key

        body: dict[str, Any] = {
            "from_agent": from_agent,
            "capability": capability,
            "messages": [{"role": "user", "content": message}],
            "metadata": metadata or {},
        }
        trace_id = _current_trace_id()
        if trace_id:
            body["trace_id"] = trace_id
        if context_id:
            body["context_id"] = context_id

        logger.info(
            "Remote async delegation to %s at %s: capability=%s",
            card.name, card.endpoint, capability,
        )

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            status_str = data.get("status", "failed")
            return DelegationResult(
                success=status_str in ("completed", "working", "submitted"),
                agent_name=card.name,
                result_text=data.get("result", "") or "",
                error=data.get("error", "") or "",
            )
        except Exception as exc:
            logger.error("Remote async delegation to %s failed: %s", card.name, exc)
            return DelegationResult(
                success=False,
                agent_name=card.name,
                error=f"Remote dispatch failed: {exc}",
            )

    def get_task_status(self, task_id: str) -> A2ATaskStatus | None:
        """Check the status of a previously delegated task.

        Args:
            task_id: The task ID returned from delegation.

        Returns:
            Current task status, or None if not found.
        """
        return self._server.get_status(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a previously delegated task.

        Returns True if cancellation was successful.
        """
        return self._server.cancel(task_id)


def _is_remote(card: AgentCard) -> bool:
    """Check if an agent card points to a remote endpoint."""
    return card.endpoint.startswith(("http://", "https://"))


def _current_trace_id() -> str:
    """Read trace_id from CorrelationContext if available."""
    try:
        from dharma_swarm.correlation_context import get_correlation
        corr = get_correlation()
        if corr.trace_id:
            return corr.trace_id
    except Exception:
        pass
    return ""
