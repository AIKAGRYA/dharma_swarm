"""Shared fakes, builders, and adversarial cases for Kimi Code adapter tests."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from dharma_swarm.model_hierarchy import DEFAULT_MODELS
from dharma_swarm.models import ProviderType
from dharma_swarm.tui.engine.adapters.base import CompletionRequest
from dharma_swarm.tui.engine.adapters.kimi_code import KimiCodeAdapter
from dharma_swarm.tui.engine.events import (
    ErrorEvent,
    SessionEnd,
    SessionStart,
    TextComplete,
    UsageReport,
)

MODEL_ID = DEFAULT_MODELS[ProviderType.KIMI_CODE]
ENV_TOKEN = "unit-test-kimi-token"


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: Any,
        *,
        text: str = "",
        json_error: Exception | None = None,
        chunk_size: int | None = None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        if json_error is not None:
            self.content = b"{malformed-json"
        elif isinstance(payload, bytes):
            self.content = payload
        elif isinstance(payload, str):
            self.content = payload.encode("utf-8")
        else:
            self.content = json.dumps(payload).encode("utf-8")
        self._chunk_size = chunk_size or max(len(self.content), 1)
        self.close_count = 0

    async def aiter_bytes(self):
        for offset in range(0, len(self.content), self._chunk_size):
            yield self.content[offset : offset + self._chunk_size]

    async def aclose(self) -> None:
        self.close_count += 1


class FakeClient:
    def __init__(
        self,
        response: FakeResponse | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self._response = response
        self._error = error
        self.exit_count = 0
        self.posts: list[dict[str, Any]] = []

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exit_count += 1
        return None

    def build_request(
        self, method: str, url: str, headers: dict, json: dict
    ) -> dict[str, Any]:
        assert method == "POST"
        self.posts.append({"url": url, "headers": headers, "json": json})
        return self.posts[-1]

    async def send(
        self, request: dict[str, Any], *, stream: bool
    ) -> FakeResponse:
        assert request is self.posts[-1]
        assert stream is True
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


class ClientFactory:
    def __init__(self, client: Any) -> None:
        self.client = client
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.client


class BlockingClient:
    def __init__(self) -> None:
        self.post_started = asyncio.Event()
        self.post_cancelled = asyncio.Event()
        self.exited = asyncio.Event()
        self.exit_count = 0

    async def __aenter__(self) -> BlockingClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exit_count += 1
        self.exited.set()
        return None

    def build_request(
        self, method: str, url: str, headers: dict, json: dict
    ) -> dict[str, Any]:
        return {"method": method, "url": url, "headers": headers, "json": json}

    async def send(
        self, request: dict[str, Any], *, stream: bool
    ) -> FakeResponse:
        del request, stream
        self.post_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.post_cancelled.set()
            raise


class GatedClient(FakeClient):
    def __init__(self, response: FakeResponse) -> None:
        super().__init__(response)
        self.post_started = asyncio.Event()
        self.release_response = asyncio.Event()

    async def send(
        self, request: dict[str, Any], *, stream: bool
    ) -> FakeResponse:
        assert request is self.posts[-1]
        assert stream is True
        self.post_started.set()
        await self.release_response.wait()
        assert self._response is not None
        return self._response


def success_payload(content: str = "PONG") -> dict[str, Any]:
    return {
        "model": MODEL_ID,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": {
            "prompt_tokens": 3,
            "completion_tokens": 1,
            "total_tokens": 4,
        },
    }


def completion_request(**overrides: Any) -> CompletionRequest:
    values: dict[str, Any] = {
        "messages": [{"role": "user", "content": "PING"}],
        "model": MODEL_ID,
        "tools": [],
        "tool_choice": "none",
    }
    values.update(overrides)
    return CompletionRequest(**values)


async def collect_events(
    adapter: KimiCodeAdapter,
    request: CompletionRequest | None = None,
    *,
    session_id: str = "kimi-session",
) -> list[object]:
    return [
        event
        async for event in adapter.stream(
            request or completion_request(), session_id=session_id
        )
    ]


def assert_failed_before_route_evidence(
    events: list[object],
    expected_code: str,
) -> None:
    assert [type(event) for event in events] == [ErrorEvent, SessionEnd]
    error, end = events
    assert isinstance(error, ErrorEvent)
    assert isinstance(end, SessionEnd)
    assert error.code == expected_code
    assert end.success is False
    assert end.error_code == expected_code
    assert not any(isinstance(event, SessionStart) for event in events)
    assert not any(isinstance(event, TextComplete) for event in events)
    assert not any(isinstance(event, UsageReport) for event in events)


__all__ = [
    "BlockingClient",
    "ClientFactory",
    "ENV_TOKEN",
    "FakeClient",
    "FakeResponse",
    "GatedClient",
    "MODEL_ID",
    "assert_failed_before_route_evidence",
    "collect_events",
    "completion_request",
    "success_payload",
]
