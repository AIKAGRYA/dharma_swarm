"""State schema and checkpointing for LangGraph parity modes."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

Mode = Literal["swarm", "supervisor"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ChatMessage:
    """JSON-safe chat message with optional agent/tool name."""

    role: str
    content: str
    name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "name": self.name,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChatMessage":
        return cls(
            role=str(raw.get("role") or ""),
            content=str(raw.get("content") or ""),
            name=str(raw.get("name") or ""),
            metadata=dict(raw.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class AgentManifest:
    """Hard manifest for one agent's domain, tools, and peer transfers."""

    name: str
    domain: str
    instructions: str
    tools: tuple[str, ...] = ()
    handoff_targets: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain,
            "instructions": self.instructions,
            "tools": list(self.tools),
            "handoff_targets": list(self.handoff_targets),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AgentManifest":
        return cls(
            name=str(raw["name"]),
            domain=str(raw["domain"]),
            instructions=str(raw.get("instructions") or ""),
            tools=tuple(str(value) for value in raw.get("tools") or ()),
            handoff_targets=tuple(
                str(value) for value in raw.get("handoff_targets") or ()
            ),
        )


@dataclass(slots=True)
class HandoffTrailEntry:
    """One accepted or rejected control transfer."""

    from_agent: str
    to_agent: str
    tool_name: str
    reason: str = ""
    accepted: bool = True
    created_at: str = field(default_factory=utc_now_iso)
    receipt_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "tool_name": self.tool_name,
            "reason": self.reason,
            "accepted": self.accepted,
            "created_at": self.created_at,
            "receipt_id": self.receipt_id,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "HandoffTrailEntry":
        return cls(
            from_agent=str(raw.get("from_agent") or ""),
            to_agent=str(raw.get("to_agent") or ""),
            tool_name=str(raw.get("tool_name") or ""),
            reason=str(raw.get("reason") or ""),
            accepted=bool(raw.get("accepted", True)),
            created_at=str(raw.get("created_at") or utc_now_iso()),
            receipt_id=str(raw.get("receipt_id") or ""),
        )


@dataclass(slots=True)
class ConversationState:
    """Restart-safe conversation state shared by parity runtimes."""

    session_id: str
    mode: Mode
    default_active_agent: str
    active_agent: str
    supervisor_authority: bool = False
    mission_id: str = ""
    messages: list[ChatMessage] = field(default_factory=list)
    handoff_trail: list[HandoffTrailEntry] = field(default_factory=list)
    filtered_visible_history: dict[str, list[dict[str, Any]]] = field(
        default_factory=dict
    )
    receipts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    schema_version: str = "dharma.langgraph_parity.state.v1"

    @classmethod
    def new(
        cls,
        *,
        session_id: str,
        mode: Mode,
        default_active_agent: str,
        mission_id: str = "",
        supervisor_authority: bool = False,
    ) -> "ConversationState":
        return cls(
            session_id=session_id,
            mode=mode,
            default_active_agent=default_active_agent,
            active_agent=default_active_agent,
            supervisor_authority=supervisor_authority,
            mission_id=mission_id,
        )

    def append_message(
        self,
        role: str,
        content: str,
        *,
        name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessage:
        message = ChatMessage(role=role, content=content, name=name, metadata=metadata or {})
        self.messages.append(message)
        self.updated_at = utc_now_iso()
        return message

    def set_visible_history(self, agent_name: str, messages: list[ChatMessage]) -> None:
        self.filtered_visible_history[agent_name] = [
            message.to_dict() for message in messages
        ]
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "mode": self.mode,
            "default_active_agent": self.default_active_agent,
            "active_agent": self.active_agent,
            "supervisor_authority": self.supervisor_authority,
            "mission_id": self.mission_id,
            "messages": [message.to_dict() for message in self.messages],
            "handoff_trail": [entry.to_dict() for entry in self.handoff_trail],
            "filtered_visible_history": self.filtered_visible_history,
            "receipts": list(self.receipts),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ConversationState":
        return cls(
            session_id=str(raw["session_id"]),
            mode=str(raw["mode"]),  # type: ignore[arg-type]
            default_active_agent=str(raw["default_active_agent"]),
            active_agent=str(raw["active_agent"]),
            supervisor_authority=bool(raw.get("supervisor_authority", False)),
            mission_id=str(raw.get("mission_id") or ""),
            messages=[
                ChatMessage.from_dict(message) for message in raw.get("messages") or []
            ],
            handoff_trail=[
                HandoffTrailEntry.from_dict(entry)
                for entry in raw.get("handoff_trail") or []
            ],
            filtered_visible_history=dict(raw.get("filtered_visible_history") or {}),
            receipts=list(raw.get("receipts") or []),
            metadata=dict(raw.get("metadata") or {}),
            created_at=str(raw.get("created_at") or utc_now_iso()),
            updated_at=str(raw.get("updated_at") or utc_now_iso()),
            schema_version=str(
                raw.get("schema_version") or "dharma.langgraph_parity.state.v1"
            ),
        )


class JsonCheckpointStore:
    """Small JSON checkpointer with one file per conversation session."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, session_id: str) -> Path:
        safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in session_id)
        return self.root / f"{safe}.json"

    def load(self, session_id: str) -> ConversationState | None:
        path = self.path_for(session_id)
        if not path.exists():
            return None
        return ConversationState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, state: ConversationState) -> Path:
        path = self.path_for(state.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)
        return path
