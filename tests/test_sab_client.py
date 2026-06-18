from __future__ import annotations

import json

from dharma_swarm.connectors.sab_client import (
    SABClient,
    build_post_run_contribution,
    build_submit_payload,
    content_sha256,
    post_run_shadow_hook,
)


class _NoNetworkOpener:
    def open(self, request, timeout=None):  # pragma: no cover - should never run
        raise AssertionError("shadow mode must not open network")


class _Response:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body


class _CapturingOpener:
    def __init__(self):
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append((request, timeout))
        return _Response(b'{"spark_id":"spark_123","status":"accepted"}')


def test_shadow_mode_does_not_touch_network():
    contribution = build_post_run_contribution(
        run_id="run_1",
        agent_uid="codex_composer",
        summary="Loop 1 bounded batch completed",
        evidence={"served_provider": "openai", "served_model": "gpt-5"},
    )
    client = SABClient(enabled=False, opener=_NoNetworkOpener())

    result = client.submit_spark(contribution)

    assert result["submitted"] is False
    assert result["mode"] == "shadow"
    assert result["content"]["run_id"] == "run_1"
    assert result["content_sha256"] == content_sha256(result["content"])


def test_live_mode_requires_signature():
    contribution = build_post_run_contribution(
        run_id="run_2",
        agent_uid="codex_composer",
        summary="missing signature",
    )
    client = SABClient(enabled=True, opener=_NoNetworkOpener())

    result = client.submit_spark(contribution)

    assert result["submitted"] is False
    assert result["mode"] == "blocked"
    assert "requires author_id" in result["error"]


def test_live_mode_posts_signed_payload():
    contribution = build_post_run_contribution(
        run_id="run_3",
        agent_uid="codex_composer",
        summary="signed shadow promotion",
    )
    opener = _CapturingOpener()
    client = SABClient(base_url="https://sab.example", enabled=True, opener=opener)

    result = client.submit_spark(
        contribution,
        author_id="agent_author",
        signature="sig_hex",
    )

    assert result["submitted"] is True
    assert result["response"]["spark_id"] == "spark_123"
    assert len(opener.requests) == 1
    request, timeout = opener.requests[0]
    assert request.full_url == "https://sab.example/api/spark/submit"
    assert timeout == 5.0
    payload = json.loads(request.data.decode("utf-8"))
    assert payload == build_submit_payload(
        contribution,
        author_id="agent_author",
        signature="sig_hex",
    )


def test_post_run_shadow_hook_builds_contribution():
    result = post_run_shadow_hook(
        run_id="run_4",
        agent_uid="cybernetics_codex",
        summary="audit packet rendered",
        evidence={"loop": 1},
    )

    assert result["submitted"] is False
    assert result["mode"] == "shadow"
    assert result["content"]["agent_uid"] == "cybernetics_codex"
