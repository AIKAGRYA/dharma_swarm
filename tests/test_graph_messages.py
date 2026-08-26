"""Message accumulation / replacement / removal / formatting (LG11).

Unit coverage for ``dharma_swarm.graph.messages``: the pure reducer, the
channel binding (two-phase, fail-closed), checkpoint round-trip, and the UI
reducer slice. No LangGraph imports here — the two-arm differential lives in
tests/oracle_support/dharmagraph_gauntlet.py behind the test-oracle extra.
"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping

import pytest

from dharma_swarm.graph.channels import ChannelWrite
from dharma_swarm.graph.compiler import GraphBuilder
from dharma_swarm.graph.effects import SimulatedEffects
from dharma_swarm.graph.messages import (
    REMOVE_ALL_MESSAGES,
    GraphMessage,
    MessagesChannel,
    RemoveMessage,
    add_message_dicts,
    add_messages,
    coerce_message,
    ui_message_reducer,
)
from dharma_swarm.graph.types import END, START


def _projection(messages: Any) -> list[tuple[str, Any, str | None]]:
    return [(m.type, m.content, m.id) for m in messages]


def _writes(*values: Any) -> list[ChannelWrite]:
    return [
        ChannelWrite("node", "messages", value, index)
        for index, value in enumerate(values)
    ]


# -- reducer semantics --------------------------------------------------


def test_add_messages_appends_and_assigns_ids():
    merged = add_messages(
        [GraphMessage("hi", "human", id="h1")],
        [GraphMessage("yo", "ai"), GraphMessage("more", "ai")],
    )
    assert [m.content for m in merged] == ["hi", "yo", "more"]
    minted = [m.id for m in merged[1:]]
    assert all(isinstance(i, str) and i for i in minted)
    assert len(set(minted)) == 2


def test_add_messages_replaces_by_id_in_place():
    merged = add_messages(
        [
            GraphMessage("hi", "human", id="h1"),
            GraphMessage("yo", "ai", id="a1"),
        ],
        [GraphMessage("hi-edited", "human", id="h1")],
    )
    assert _projection(merged) == [
        ("human", "hi-edited", "h1"),
        ("ai", "yo", "a1"),
    ]


def test_remove_message_by_id():
    merged = add_messages(
        [
            GraphMessage("hi", "human", id="h1"),
            GraphMessage("yo", "ai", id="a1"),
        ],
        [RemoveMessage("h1")],
    )
    assert _projection(merged) == [("ai", "yo", "a1")]


def test_remove_all_sentinel_clears_then_appends():
    merged = add_messages(
        [
            GraphMessage("hi", "human", id="h1"),
            GraphMessage("yo", "ai", id="a1"),
        ],
        [RemoveMessage(REMOVE_ALL_MESSAGES), GraphMessage("fresh", "ai", id="f1")],
    )
    assert _projection(merged) == [("ai", "fresh", "f1")]


def test_invalid_remove_id_fails_closed():
    with pytest.raises(ValueError, match="doesn't exist"):
        add_messages([GraphMessage("hi", "human", id="h1")], [RemoveMessage("ghost")])


def test_openai_format_projection_collapses_text_and_drops_ids():
    formatted = add_messages(
        [],
        [
            GraphMessage(
                [
                    {"type": "text", "text": "A", "cache_control": {"type": "x"}},
                    {"type": "text", "text": "B"},
                ],
                "human",
                id="t1",
            ),
            GraphMessage(
                [
                    {"type": "text", "text": "look"},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": "1234",
                        },
                    },
                ],
                "human",
                id="i1",
            ),
        ],
        format="langchain-openai",
    )
    assert formatted[0].content == "A\nB"
    assert formatted[1].content == [
        {"type": "text", "text": "look"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,1234"}},
    ]
    assert all(message.id is None for message in formatted)


def test_unrecognized_format_rejected():
    with pytest.raises(ValueError, match="Unrecognized format"):
        add_messages([], [GraphMessage("hi")], format="openai")


def test_coercion_accepts_dicts_tuples_and_strings():
    assert coerce_message(("user", "hi")).type == "human"
    assert coerce_message("bare").content == "bare"
    assert coerce_message({"role": "assistant", "content": "ok"}).type == "ai"
    assert coerce_message({"type": "remove", "id": "x"}) == RemoveMessage("x")
    merged = add_messages([{"type": "human", "content": "hi", "id": "h1"}], "next")
    assert [m.content for m in merged] == ["hi", "next"]


def test_message_dict_round_trip():
    message = GraphMessage("hi", "user", id="h1", name="dhyana")
    payload = message.to_dict()
    assert payload == {
        "type": "human",
        "content": "hi",
        "id": "h1",
        "name": "dhyana",
    }
    assert GraphMessage.from_dict(payload) == message
    assert message.to_openai() == {"role": "user", "content": "hi"}


# -- channel binding ----------------------------------------------------


def test_messages_channel_folds_write_group_in_order():
    channel = MessagesChannel()
    channel.name = "messages"
    writes = _writes(
        [GraphMessage("hi", "human", id="h1").to_dict()],
        [
            GraphMessage("hi-edited", "human", id="h1").to_dict(),
            GraphMessage("yo", "ai", id="a1").to_dict(),
        ],
    )
    channel.validate(writes, 1)
    assert channel.commit(writes, 1) is True
    assert channel.version == 1
    assert [row["content"] for row in channel.get()] == ["hi-edited", "yo"]
    assert [m.type for m in channel.typed()] == ["human", "ai"]


def test_messages_channel_rejects_unknown_remove_before_commit():
    channel = MessagesChannel()
    channel.name = "messages"
    seed = _writes([GraphMessage("hi", "human", id="h1").to_dict()])
    channel.commit(seed, 1)
    bad = _writes([RemoveMessage("ghost").to_dict()])
    with pytest.raises(ValueError, match="doesn't exist"):
        channel.validate(bad, 2)
    assert [row["id"] for row in channel.get()] == ["h1"]
    assert channel.version == 1


def test_messages_channel_checkpoint_round_trip():
    channel = MessagesChannel()
    channel.name = "messages"
    channel.commit(_writes([GraphMessage("hi", "human", id="h1").to_dict()]), 1)
    snapshot = channel.checkpoint()
    restored = MessagesChannel()
    restored.name = "messages"
    restored.restore(snapshot)
    assert restored.version == channel.version
    assert restored.get() == channel.get()


def test_message_channel_graph_run_accumulates_replaces_and_removes():
    compiled = (
        GraphBuilder("messages-graph")
        .add_channel("messages", MessagesChannel)
        .add_node(
            "greet",
            lambda state: {"messages": [GraphMessage("hi", "human", id="h1").to_dict()]},
        )
        .add_node(
            "reply",
            lambda state: {"messages": [GraphMessage("yo", "ai", id="a1").to_dict()]},
        )
        .add_node(
            "amend",
            lambda state: {
                "messages": [
                    GraphMessage("hi-edited", "human", id="h1").to_dict(),
                    RemoveMessage("a1").to_dict(),
                ]
            },
        )
        .add_edge(START, "greet")
        .add_edge("greet", "reply")
        .add_edge("reply", "amend")
        .add_edge("amend", END)
        .compile()
    )
    result = asyncio.run(
        compiled.invoke(
            input={"messages": [GraphMessage("sys", "system", id="s1").to_dict()]},
            effects=SimulatedEffects(11),
        )
    )
    assert [
        (row["type"], row["content"], row["id"]) for row in result.state["messages"]
    ] == [
        ("system", "sys", "s1"),
        ("human", "hi-edited", "h1"),
    ]


def test_add_message_dicts_is_json_domain_and_batching_stable():
    left: list[Mapping[str, Any]] = []
    first = add_message_dicts(left, [GraphMessage("a", "human", id="1").to_dict()])
    second = add_message_dicts(first, [GraphMessage("b", "ai", id="2").to_dict()])
    one_shot = add_message_dicts(
        left,
        [
            GraphMessage("a", "human", id="1").to_dict(),
            GraphMessage("b", "ai", id="2").to_dict(),
        ],
    )
    assert second == one_shot
    assert all(isinstance(row, dict) for row in second)


# -- UI reducer ---------------------------------------------------------


def test_ui_message_reducer_add_replace_merge_and_remove():
    base = [{"type": "ui", "id": "u1", "name": "Chat", "props": {"a": 1}, "metadata": {}}]
    merged = ui_message_reducer(
        base,
        [
            {
                "type": "ui",
                "id": "u1",
                "name": "Chat",
                "props": {"b": 2},
                "metadata": {"merge": True},
            },
            {"type": "ui", "id": "u2", "name": "Side", "props": {}, "metadata": {}},
        ],
    )
    assert merged[0]["props"] == {"a": 1, "b": 2}
    assert [item["id"] for item in merged] == ["u1", "u2"]
    assert ui_message_reducer(merged, [{"type": "remove-ui", "id": "u1"}]) == [
        merged[1]
    ]


def test_ui_message_reducer_unknown_remove_fails_closed():
    with pytest.raises(ValueError, match="doesn't exist"):
        ui_message_reducer([], [{"type": "remove-ui", "id": "ghost"}])
