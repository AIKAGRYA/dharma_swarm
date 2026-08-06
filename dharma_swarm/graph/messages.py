"""Message accumulation, replacement, removal, and formatting (LG11).

The neutral graph core keeps state in JSON-domain channels: every write is
proved stably JSON-serializable BEFORE any channel commits
(``GraphState._validate_grouped_writes``).  Message state therefore travels
as plain dicts (``GraphMessage.to_dict()`` / ``RemoveMessage.to_dict()``)
while the reducer itself works on typed objects.

Semantics are a deliberate port of ``langgraph.graph.message.add_messages``
(installed 1.2.4, ``site-packages/langgraph/graph/message.py:60``):

* new messages append, ids are minted when missing;
* a same-id message REPLACES in place (position preserved);
* ``RemoveMessage(id=X)`` deletes X;
* ``RemoveMessage(id=REMOVE_ALL_MESSAGES)`` clears, and messages that follow
  it in the same batch survive (they append onto the cleared list);
* removing an unknown id raises ``ValueError`` — fail closed, never a
  silent no-op;
* ``format="langchain-openai"`` normalizes content blocks (text-only block
  lists collapse to text, image blocks become ``image_url`` blocks) and, as
  in langgraph, drops ids; any other ``format`` value raises ``ValueError``.

:class:`MessagesChannel` binds the reducer to the two-phase channel
protocol, so an illegal batch (unknown remove id) raises in the VALIDATE
phase and the superstep commits nothing.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, replace
from typing import Annotated, Any, Literal, Mapping, Sequence, TypedDict

from dharma_swarm.graph.channels import Channel, ChannelWrite, EmptyChannelError

__all__ = [
    "REMOVE_ALL_MESSAGES",
    "AnyUIMessage",
    "GraphMessage",
    "MessagesChannel",
    "MessagesState",
    "RemoveMessage",
    "RemoveUIMessage",
    "UIMessage",
    "add_message_dicts",
    "add_messages",
    "coerce_message",
    "ui_message_reducer",
]


# langgraph parity: the sentinel is a plain string, so it round-trips through
# JSON channel state and checkpoints unchanged.
REMOVE_ALL_MESSAGES = "__remove_all__"

MESSAGE_TYPES = frozenset({"human", "ai", "system", "tool"})

_ROLE_ALIASES = {
    "user": "human",
    "human": "human",
    "assistant": "ai",
    "ai": "ai",
    "system": "system",
    "tool": "tool",
}


class MessageFormatError(ValueError):
    """An unrecognized ``format`` argument or an unconvertible content block."""


@dataclass(frozen=True)
class GraphMessage:
    """One immutable chat message in the JSON domain.

    ``role`` accepts the OpenAI spellings (``user`` / ``assistant``) and
    normalizes to the langchain ``type`` vocabulary (``human`` / ``ai`` /
    ``system`` / ``tool``), which is what :attr:`type` reports.
    """

    content: str | list[Any]
    role: str = "human"
    id: str | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        normalized = _ROLE_ALIASES.get(str(self.role))
        if normalized is None:
            raise ValueError(
                f"unsupported message role {self.role!r}; expected one of "
                f"{sorted(set(_ROLE_ALIASES))} (fail closed)"
            )
        object.__setattr__(self, "role", normalized)

    @property
    def type(self) -> str:
        """langchain-compatible message type (``human``/``ai``/...)."""
        return self.role

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe projection stored in channels and checkpoints."""
        return {
            "type": self.role,
            "content": copy.deepcopy(self.content),
            "id": self.id,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> GraphMessage:
        role = payload.get("type") or payload.get("role") or "human"
        return cls(
            content=copy.deepcopy(payload.get("content", "")),
            role=str(role),
            id=payload.get("id"),
            name=payload.get("name"),
        )

    def to_openai(self) -> dict[str, Any]:
        """``{"role", "content"}`` projection in OpenAI wire vocabulary."""
        wire = {"human": "user", "ai": "assistant"}.get(self.role, self.role)
        return {"role": wire, "content": _openai_content(self.content)}


@dataclass(frozen=True)
class RemoveMessage:
    """Sentinel removing the message carrying ``id`` from the list.

    ``RemoveMessage(id=REMOVE_ALL_MESSAGES)`` clears the whole list.
    """

    id: str

    @property
    def type(self) -> str:
        return "remove"

    def to_dict(self) -> dict[str, Any]:
        return {"type": "remove", "id": self.id}


AnyGraphMessage = GraphMessage | RemoveMessage


def coerce_message(value: Any) -> AnyGraphMessage:
    """Normalize a message-like value into a typed message object.

    Accepts :class:`GraphMessage` / :class:`RemoveMessage`, JSON dicts (as
    produced by ``to_dict()``, or ``{"role": ..., "content": ...}``),
    ``(role, content)`` tuples, and bare strings (a human message).
    """
    if isinstance(value, (GraphMessage, RemoveMessage)):
        return value
    if isinstance(value, Mapping):
        kind = value.get("type") or value.get("role")
        if kind == "remove":
            identifier = value.get("id")
            if identifier is None:
                raise ValueError("remove message requires an 'id' (fail closed)")
            return RemoveMessage(id=str(identifier))
        return GraphMessage.from_dict(value)
    if isinstance(value, tuple) and len(value) == 2:
        role, content = value
        return GraphMessage(content=content, role=str(role))
    if isinstance(value, str):
        return GraphMessage(content=value)
    raise TypeError(
        f"cannot coerce {type(value).__name__!r} into a graph message "
        "(expected GraphMessage, RemoveMessage, mapping, 2-tuple, or str)"
    )


def _coerce_all(value: Any) -> list[AnyGraphMessage]:
    if value is None:
        return []
    if isinstance(value, (GraphMessage, RemoveMessage, str, Mapping)):
        value = [value]
    elif isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
        value = [value]
    elif not isinstance(value, Sequence):
        value = [value]
    return [coerce_message(item) for item in value]


def _with_ids(messages: Sequence[AnyGraphMessage]) -> list[AnyGraphMessage]:
    """langgraph parity: mint a uuid4 id for every message that lacks one."""
    minted: list[AnyGraphMessage] = []
    for message in messages:
        if isinstance(message, GraphMessage) and message.id is None:
            minted.append(replace(message, id=str(uuid.uuid4())))
        else:
            minted.append(message)
    return minted


def _openai_content(content: Any) -> Any:
    """Normalize content blocks to the OpenAI shape (langchain-openai parity).

    A block list whose entries are all text collapses to a newline-joined
    string; mixed lists keep converted blocks with ``image_url`` images.
    """
    if not isinstance(content, list):
        return content
    blocks: list[dict[str, Any]] = []
    for raw in content:
        if isinstance(raw, str):
            blocks.append({"type": "text", "text": raw})
            continue
        if not isinstance(raw, Mapping):
            raise MessageFormatError(
                f"cannot format content block of type {type(raw).__name__!r}"
            )
        kind = raw.get("type")
        if kind == "text":
            blocks.append({"type": "text", "text": raw.get("text", "")})
        elif kind == "image_url":
            url = raw.get("image_url")
            url = dict(url) if isinstance(url, Mapping) else {"url": url}
            blocks.append({"type": "image_url", "image_url": url})
        elif kind == "image":
            source = raw.get("source") or {}
            if source.get("type") == "base64":
                url_value = (
                    f"data:{source.get('media_type')};base64,{source.get('data')}"
                )
            else:
                url_value = str(source.get("url", ""))
            blocks.append({"type": "image_url", "image_url": {"url": url_value}})
        else:
            raise MessageFormatError(
                f"unrecognized content block type {kind!r}; expected one of "
                "'text', 'image', 'image_url' (fail closed)"
            )
    if blocks and all(block["type"] == "text" for block in blocks):
        return "\n".join(block["text"] for block in blocks)
    return blocks


def _format_messages(messages: Sequence[GraphMessage]) -> list[GraphMessage]:
    """``format="langchain-openai"`` projection (ids are dropped, as upstream)."""
    return [
        GraphMessage(
            content=_openai_content(message.content),
            role=message.role,
            id=None,
            name=message.name,
        )
        for message in messages
    ]


def add_messages(
    left: Any,
    right: Any,
    *,
    format: Literal["langchain-openai"] | None = None,
) -> list[GraphMessage]:
    """Merge two message lists, updating existing messages by id.

    Port of ``langgraph.graph.message.add_messages`` (1.2.4). ``left`` and
    ``right`` may hold typed messages or their JSON dict projections; the
    result is always a list of :class:`GraphMessage`.
    """
    left_messages = _with_ids(_coerce_all(left))
    right_messages = _with_ids(_coerce_all(right))

    remove_all_idx: int | None = None
    for index, message in enumerate(right_messages):
        if isinstance(message, RemoveMessage) and message.id == REMOVE_ALL_MESSAGES:
            remove_all_idx = index
    if remove_all_idx is not None:
        # langgraph parity: the clear wins and later messages of the same
        # batch survive; formatting is not applied on this path.
        return [
            message
            for message in right_messages[remove_all_idx + 1 :]
            if isinstance(message, GraphMessage)
        ]

    merged: list[GraphMessage] = [
        message for message in left_messages if isinstance(message, GraphMessage)
    ]
    merged_by_id = {message.id: index for index, message in enumerate(merged)}
    ids_to_remove: set[str | None] = set()
    for message in right_messages:
        existing_idx = merged_by_id.get(message.id)
        if existing_idx is not None:
            if isinstance(message, RemoveMessage):
                ids_to_remove.add(message.id)
            else:
                ids_to_remove.discard(message.id)
                merged[existing_idx] = message
        else:
            if isinstance(message, RemoveMessage):
                raise ValueError(
                    "Attempting to delete a message with an ID that doesn't "
                    f"exist ('{message.id}')"
                )
            merged_by_id[message.id] = len(merged)
            merged.append(message)
    merged = [message for message in merged if message.id not in ids_to_remove]

    if format == "langchain-openai":
        return _format_messages(merged)
    if format:
        raise MessageFormatError(
            f"Unrecognized format={format!r}. Expected one of "
            "'langchain-openai', None."
        )
    return merged


def add_message_dicts(
    left: Any,
    right: Any,
    *,
    format: Literal["langchain-openai"] | None = None,
) -> list[dict[str, Any]]:
    """:func:`add_messages` in the JSON domain (usable as a channel reducer)."""
    return [message.to_dict() for message in add_messages(left, right, format=format)]


class MessagesChannel(Channel[list[dict[str, Any]]]):
    """Channel whose write groups fold through :func:`add_messages`.

    Declared like any other channel
    (``GraphBuilder.add_channel("messages", MessagesChannel)``); values are
    JSON message dicts, so the channel checkpoints and resumes unchanged.
    Multiple same-superstep writes are legal and fold in canonical order.
    """

    def __init__(self, *, format: Literal["langchain-openai"] | None = None) -> None:
        super().__init__()
        self._messages: list[dict[str, Any]] = []
        self._format = format

    def _fold(
        self, start: Sequence[Mapping[str, Any]], writes: Sequence[ChannelWrite]
    ) -> list[dict[str, Any]]:
        value: list[Any] = [dict(item) for item in start]
        for write in writes:
            value = add_message_dicts(value, write.value, format=self._format)
        return value

    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        """Stage the fold so an illegal batch (unknown remove id, bad format)
        raises BEFORE any channel commits — the superstep stays atomic."""
        if not writes:
            return None
        self._fold(self._messages, writes)
        return None

    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        if not writes:
            return False
        self._messages = self._fold(self._messages, writes)
        self.version += 1
        return True

    def get(self) -> list[dict[str, Any]]:
        if self.is_empty:
            raise EmptyChannelError(self.name or "<unbound>")
        return [dict(message) for message in self._messages]

    def typed(self) -> list[GraphMessage]:
        """Committed value as typed messages (convenience for node code)."""
        return [GraphMessage.from_dict(message) for message in self.get()]

    def checkpoint(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "messages": [dict(message) for message in self._messages],
        }

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        super().restore(snapshot)
        self._messages = [dict(message) for message in snapshot.get("messages", [])]


class MessagesState(TypedDict, total=False):
    """Typed-schema convenience (langgraph ``MessagesState`` parity)."""

    messages: Annotated[list[dict[str, Any]], add_message_dicts]


# ---------------------------------------------------------------------------
# UI messages (langgraph.graph.ui parity, reducer slice).
# ---------------------------------------------------------------------------


class UIMessage(TypedDict):
    """A UI component update carried in graph state."""

    type: Literal["ui"]
    id: str
    name: str
    props: dict[str, Any]
    metadata: dict[str, Any]


class RemoveUIMessage(TypedDict):
    """Removal marker for a previously pushed :class:`UIMessage`."""

    type: Literal["remove-ui"]
    id: str


AnyUIMessage = UIMessage | RemoveUIMessage


def ui_message_reducer(
    left: list[Any] | Mapping[str, Any],
    right: list[Any] | Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Merge UI message lists, honoring ``remove-ui`` and ``metadata.merge``.

    Port of ``langgraph.graph.ui.ui_message_reducer`` (1.2.4): same-id
    messages replace in place (props merge when ``metadata.merge`` is set),
    ``remove-ui`` deletes, and removing an unknown id raises ``ValueError``.
    """
    if isinstance(left, Mapping):
        left = [left]
    if isinstance(right, Mapping):
        right = [right]

    merged: list[dict[str, Any]] = [dict(item) for item in left]
    merged_by_id = {item.get("id"): index for index, item in enumerate(merged)}
    ids_to_remove: set[Any] = set()

    for raw in right:
        message = dict(raw)
        message_id = message.get("id")
        existing_idx = merged_by_id.get(message_id)
        if existing_idx is not None:
            if message.get("type") == "remove-ui":
                ids_to_remove.add(message_id)
            else:
                ids_to_remove.discard(message_id)
                if message.get("metadata", {}).get("merge", False):
                    previous = merged[existing_idx]
                    message["props"] = {
                        **previous.get("props", {}),
                        **message.get("props", {}),
                    }
                merged[existing_idx] = message
        else:
            if message.get("type") == "remove-ui":
                raise ValueError(
                    "Attempting to delete an UI message with an ID that "
                    f"doesn't exist ('{message_id}')"
                )
            merged_by_id[message_id] = len(merged)
            merged.append(message)

    return [item for item in merged if item.get("id") not in ids_to_remove]
