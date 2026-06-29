"""Deterministic LangGraph-style supervisor runtime.

This module intentionally avoids importing LangGraph. It models the supervisor
message-flow contract that the repo needs to test: user input enters a
supervisor, the supervisor delegates to subagents, subagent outputs return to
the supervisor, and only the supervisor emits the user-visible final answer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from .state import (
    ParityMessage,
    SupervisorParityState,
    is_routing_message,
    message_from_mapping,
)
from .tools import (
    create_handoff_back_messages,
    create_handoff_messages,
    forward_message,
)

OutputMode = Literal["last_message", "full_history"]
AgentReturn = (
    str
    | ParityMessage
    | Mapping[str, object]
    | Sequence[str | ParityMessage | Mapping[str, object]]
)
AgentHandler = Callable[[Sequence[ParityMessage]], AgentReturn]
Finalizer = Callable[[SupervisorParityState], str | ParityMessage]


@dataclass(frozen=True, slots=True)
class DeterministicSubagent:
    name: str
    handler: AgentHandler

    def invoke(self, messages: Sequence[ParityMessage]) -> list[ParityMessage]:
        return _normalize_agent_return(self.handler(messages), agent_name=self.name)


@dataclass(frozen=True, slots=True)
class SupervisorResult:
    state: SupervisorParityState
    final_message: ParityMessage
    user_visible_messages: tuple[ParityMessage, ...]
    delegated_agents: tuple[str, ...]

    @property
    def output(self) -> str:
        return self.final_message.content


class DeterministicSupervisorRuntime:
    """A small deterministic runtime for supervisor parity checks."""

    def __init__(
        self,
        agents: Sequence[DeterministicSubagent],
        *,
        supervisor_name: str = "supervisor",
        add_handoff_messages: bool = True,
        output_mode: OutputMode = "last_message",
        finalizer: Finalizer | None = None,
    ) -> None:
        if len(agents) < 2:
            raise ValueError("supervisor parity requires at least two subagents")
        if output_mode not in {"last_message", "full_history"}:
            raise ValueError("output_mode must be 'last_message' or 'full_history'")

        names = [agent.name for agent in agents]
        if len(set(names)) != len(names):
            raise ValueError("subagent names must be unique")

        self._agents = tuple(agents)
        self.supervisor_name = supervisor_name
        self.add_handoff_messages = add_handoff_messages
        self.output_mode = output_mode
        self._finalizer = finalizer

    def invoke(
        self,
        user_input: str | ParityMessage | Mapping[str, object] | Sequence[ParityMessage],
        *,
        supervisor_mode: bool = True,
        forward_from: str | None = None,
    ) -> SupervisorResult:
        state = SupervisorParityState.from_user_input(user_input)
        delegated_agents: list[str] = []

        for sequence, agent in enumerate(self._agents, start=1):
            delegated_agents.append(agent.name)
            if self.add_handoff_messages:
                state.extend(
                    create_handoff_messages(
                        supervisor_name=self.supervisor_name,
                        agent_name=agent.name,
                        sequence=sequence,
                    )
                )

            visible = state.visible_for_subagent(
                add_handoff_messages=self.add_handoff_messages
            )
            state.subagent_visible_state[agent.name] = list(visible)

            agent_messages = agent.invoke(tuple(visible))
            state.subagent_messages[agent.name] = list(agent_messages)
            state.extend(_select_agent_output(agent_messages, self.output_mode))

            if self.add_handoff_messages:
                state.extend(
                    create_handoff_back_messages(
                        agent_name=agent.name,
                        supervisor_name=self.supervisor_name,
                        sequence=sequence,
                    )
                )

        final_message = self._final_message(state, forward_from=forward_from)
        state.append(final_message)

        if supervisor_mode:
            user_visible = (final_message,)
        else:
            user_visible = tuple(
                message
                for message in state.messages
                if message.role == "assistant" and message.name != self.supervisor_name
                and not is_routing_message(message)
            ) + (final_message,)

        return SupervisorResult(
            state=state,
            final_message=final_message,
            user_visible_messages=user_visible,
            delegated_agents=tuple(delegated_agents),
        )

    def _final_message(
        self,
        state: SupervisorParityState,
        *,
        forward_from: str | None,
    ) -> ParityMessage:
        if forward_from is not None:
            return forward_message(
                state,
                from_agent=forward_from,
                supervisor_name=self.supervisor_name,
            )

        if self._finalizer is None:
            content = _default_supervisor_summary(state)
            return ParityMessage(
                role="assistant",
                content=content,
                name=self.supervisor_name,
            )

        finalized = self._finalizer(state)
        if isinstance(finalized, ParityMessage):
            return finalized.with_name(self.supervisor_name)
        return ParityMessage(
            role="assistant",
            content=str(finalized),
            name=self.supervisor_name,
        )


def _select_agent_output(
    messages: Sequence[ParityMessage],
    output_mode: OutputMode,
) -> list[ParityMessage]:
    if not messages:
        raise ValueError("subagent returned no messages")
    if output_mode == "last_message":
        return [messages[-1]]
    return list(messages)


def _normalize_agent_return(
    value: AgentReturn,
    *,
    agent_name: str,
) -> list[ParityMessage]:
    if isinstance(value, str):
        return [ParityMessage(role="assistant", content=value, name=agent_name)]
    if isinstance(value, ParityMessage):
        return [_ensure_agent_name(value, agent_name)]
    if isinstance(value, Mapping):
        return [_ensure_agent_name(message_from_mapping(value), agent_name)]

    messages = [_coerce_message(item, agent_name=agent_name) for item in value]
    if not messages:
        raise ValueError(f"agent {agent_name!r} returned no messages")
    return messages


def _coerce_message(
    value: str | ParityMessage | Mapping[str, object],
    *,
    agent_name: str,
) -> ParityMessage:
    if isinstance(value, str):
        return ParityMessage(role="assistant", content=value, name=agent_name)
    if isinstance(value, ParityMessage):
        return _ensure_agent_name(value, agent_name)
    if isinstance(value, Mapping):
        return _ensure_agent_name(message_from_mapping(value), agent_name)
    raise TypeError(f"unsupported agent message type: {type(value)!r}")


def _ensure_agent_name(message: ParityMessage, agent_name: str) -> ParityMessage:
    if message.role == "assistant" and message.name is None:
        return message.with_name(agent_name)
    return message


def _default_supervisor_summary(state: SupervisorParityState) -> str:
    lines: list[str] = []
    for agent_name, messages in state.subagent_messages.items():
        last = next(
            (message for message in reversed(messages) if message.role == "assistant"),
            None,
        )
        if last is not None:
            lines.append(f"{agent_name}: {last.content}")
    return "\n".join(lines)
