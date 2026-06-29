"""Serializable state for the deterministic LangGraph parity swarm."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


CHECKPOINT_VERSION = 1
TransferStatus = Literal["accepted", "rejected"]


@dataclass(frozen=True)
class AgentManifest:
    """Hard manifest for an agent's domain, tools, and allowed handoffs."""

    name: str
    domain: str
    instructions: str
    tools: tuple[str, ...] = field(default_factory=tuple)
    handoff_targets: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ParityMessage:
    """Small JSON-safe message object for supervisor parity checks."""

    role: str
    content: str
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_name(self, name: str) -> "ParityMessage":
        return ParityMessage(
            role=self.role,
            content=self.content,
            name=name,
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "name": self.name,
            "metadata": dict(self.metadata),
        }


def message_from_mapping(payload: Mapping[str, object]) -> ParityMessage:
    return ParityMessage(
        role=str(payload.get("role") or "assistant"),
        content=str(payload.get("content") or ""),
        name=None if payload.get("name") is None else str(payload.get("name") or ""),
        metadata=dict(payload.get("metadata") or {}),
    )


def is_routing_message(message: ParityMessage) -> bool:
    return bool(
        message.metadata.get("routing_clutter")
        or message.metadata.get("__is_handoff_back")
        or message.role == "tool"
    )


@dataclass
class SupervisorParityState:
    """Message state for deterministic supervisor delegation tests."""

    messages: list[ParityMessage] = field(default_factory=list)
    subagent_visible_state: dict[str, list[ParityMessage]] = field(default_factory=dict)
    subagent_messages: dict[str, list[ParityMessage]] = field(default_factory=dict)

    @classmethod
    def from_user_input(
        cls,
        user_input: str | ParityMessage | Mapping[str, object] | Sequence[ParityMessage],
    ) -> "SupervisorParityState":
        state = cls()
        if isinstance(user_input, str):
            state.append(ParityMessage(role="user", content=user_input))
            return state
        if isinstance(user_input, ParityMessage):
            state.append(user_input)
            return state
        if isinstance(user_input, Mapping):
            state.append(message_from_mapping(user_input))
            return state
        state.extend(tuple(user_input))
        return state

    def append(self, message: ParityMessage) -> None:
        self.messages.append(message)

    def extend(self, messages: Sequence[ParityMessage]) -> None:
        self.messages.extend(messages)

    def visible_for_subagent(
        self,
        *,
        add_handoff_messages: bool,
    ) -> tuple[ParityMessage, ...]:
        if add_handoff_messages:
            return tuple(self.messages)
        return tuple(
            message for message in self.messages if not is_routing_message(message)
        )


@dataclass(frozen=True)
class TransferReceipt:
    """Durable record for an attempted active-agent handoff."""

    id: str
    status: TransferStatus
    from_agent: str
    requested_agent: str | None
    tool_name: str
    reason: str
    active_agent_before: str
    active_agent_after: str
    visible_tools: tuple[str, ...] = field(default_factory=tuple)
    turn_index: int = 0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TransferReceipt":
        data = dict(payload)
        data["visible_tools"] = tuple(data.get("visible_tools", ()))
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["visible_tools"] = list(self.visible_tools)
        return data


@dataclass
class SwarmState:
    """Checkpointable runtime state.

    The `active_agent` field is intentionally first-class because LangGraph-style
    handoff parity depends on resuming the previously active subagent.
    """

    active_agent: str
    default_agent: str
    turn_index: int = 0
    messages: list[dict[str, Any]] = field(default_factory=list)
    receipts: list[TransferReceipt] = field(default_factory=list)
    version: int = CHECKPOINT_VERSION

    @classmethod
    def fresh(cls, default_agent: str) -> "SwarmState":
        return cls(active_agent=default_agent, default_agent=default_agent)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SwarmState":
        version = int(payload.get("version", 0))
        if version != CHECKPOINT_VERSION:
            raise ValueError(
                f"Unsupported swarm checkpoint version {version}; "
                f"expected {CHECKPOINT_VERSION}"
            )

        active_agent = str(payload["active_agent"])
        default_agent = str(payload.get("default_agent") or active_agent)
        receipts = [
            TransferReceipt.from_dict(item)
            for item in payload.get("receipts", [])
        ]
        messages = list(payload.get("messages", []))
        turn_index = int(payload.get("turn_index", len(messages)))
        return cls(
            active_agent=active_agent,
            default_agent=default_agent,
            turn_index=turn_index,
            messages=messages,
            receipts=receipts,
            version=version,
        )

    @classmethod
    def load(cls, path: Path) -> "SwarmState":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def load_or_fresh(cls, path: Path, default_agent: str) -> "SwarmState":
        if not path.exists():
            return cls.fresh(default_agent)
        return cls.load(path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "active_agent": self.active_agent,
            "default_agent": self.default_agent,
            "turn_index": self.turn_index,
            "messages": list(self.messages),
            "receipts": [receipt.to_dict() for receipt in self.receipts],
        }

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.tmp")
        temp_path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(path)
        return path

    def next_receipt_id(self) -> str:
        return f"transfer-{len(self.receipts) + 1:04d}"

    def record_user_message(self, content: str, agent: str) -> None:
        self.messages.append(
            {
                "role": "user",
                "agent": agent,
                "content": content,
                "turn_index": self.turn_index,
            }
        )

    def record_agent_message(self, content: str, agent: str) -> None:
        self.messages.append(
            {
                "role": "assistant",
                "agent": agent,
                "content": content,
                "turn_index": self.turn_index,
            }
        )

    def record_receipt(self, receipt: TransferReceipt) -> None:
        self.receipts.append(receipt)
        self.messages.append(
            {
                "role": "tool",
                "agent": receipt.from_agent,
                "tool_name": receipt.tool_name,
                "content": receipt.reason,
                "receipt": receipt.to_dict(),
                "turn_index": self.turn_index,
            }
        )
