#!/usr/bin/env python3
"""One-shot CLI for the non-authorizing governed-patch provider lane."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from dharma_swarm.api_keys import bootstrap_runtime_env
from dharma_swarm.governed_patch_evidence import (
    GovernedPatchEvidenceError,
    NativePatchBindings,
    _canonical_json_bytes,
    _parse_json,
    _read_regular_bounded,
    parse_governed_patch_request,
)
from dharma_swarm.governed_patch_provider_authorship import (
    REQUESTED_MODEL,
    REQUESTED_PROVIDER,
    REQUESTED_TRANSPORT,
    REQUESTED_WIRE_MODEL,
    ProviderSession,
    author_governed_patch,
)
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.ollama_config import OLLAMA_CLOUD_BASE_URL
from dharma_swarm.runtime_provider import (
    create_runtime_provider,
    resolve_runtime_provider_config,
    runtime_provider_transport_identity,
)

_BINDING_FIELDS = frozenset(
    """mission_id task_id attempt_id lease_id packet_id correlation_id
    delivery_id proposal_id base_sha executor_agent_uid executor_run_id
    executor_process_boot_id""".split()
)


class _ExactOllamaCloudClient:
    """One HTTP request to one wire model, with no frontier fallback."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if request.model != REQUESTED_MODEL or request.tools:
            raise GovernedPatchEvidenceError(
                "strict Ollama dispatch requires exact model and no tools"
            )
        client = self._provider._get_client()
        headers = self._provider._headers_or_raise()
        headers["Content-Type"] = "application/json"
        response = await client.post(
            f"{OLLAMA_CLOUD_BASE_URL}/v1/chat/completions",
            json={
                "model": REQUESTED_WIRE_MODEL,
                "messages": self._provider._build_messages(request),
                "max_tokens": max(request.max_tokens, 4096),
                "temperature": request.temperature,
                "stream": False,
            },
            headers=headers,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Ollama cloud error {response.status_code}: {response.text[:300]}"
            )
        data = response.json()
        choices = data.get("choices") if type(data) is dict else None
        if type(choices) is not list or len(choices) != 1:
            raise RuntimeError("Ollama cloud returned an invalid choice set")
        choice = choices[0]
        message = choice.get("message") if type(choice) is dict else None
        if type(message) is not dict or type(message.get("content")) is not str:
            raise RuntimeError("Ollama cloud returned invalid message content")
        usage = data.get("usage") if type(data.get("usage")) is dict else {}
        return LLMResponse(
            content=message["content"],
            model=str(data.get("model") or ""),
            provider=REQUESTED_PROVIDER,
            usage={
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
            },
            tool_calls=list(message.get("tool_calls") or []),
            stop_reason=str(choice.get("finish_reason") or ""),
        )

    async def close(self) -> None:
        await self._provider.close()


def bootstrap_exact_ollama_provider() -> ProviderSession:
    """Resolve the canonical cloud config, then disable provider fallback."""

    bootstrap_runtime_env()
    config = resolve_runtime_provider_config(
        ProviderType.OLLAMA,
        model=REQUESTED_MODEL,
        base_url=OLLAMA_CLOUD_BASE_URL,
    )
    if (
        not config.available
        or config.provider != ProviderType.OLLAMA
        or config.base_url != OLLAMA_CLOUD_BASE_URL
        or config.default_model != REQUESTED_MODEL
        or config.transport_mode != REQUESTED_TRANSPORT
    ):
        raise GovernedPatchEvidenceError(
            "exact Ollama cloud glm-5.2 provider is unavailable"
        )
    return ProviderSession(
        client=_ExactOllamaCloudClient(create_runtime_provider(config)),
        endpoint_identity=runtime_provider_transport_identity(config),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("command", choices=("once",))
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--expected-bindings-json", required=True)
    parser.add_argument("--expected-semantic-intent-file", required=True)
    parser.add_argument("--expected-task-snapshot-sha256", required=True)
    parser.add_argument("--semantic-artifact-sha256", required=True)
    parser.add_argument("--provider-call-id")
    parser.add_argument("--timeout-s", type=float, default=600.0)
    return parser


def _canonical_bindings(raw: str) -> NativePatchBindings:
    value = _parse_json(raw, surface="expected bindings")
    if type(value) is not dict or frozenset(value) != _BINDING_FIELDS:
        raise GovernedPatchEvidenceError(
            "expected bindings must have the closed native shape"
        )
    if raw.encode("utf-8") != _canonical_json_bytes(
        value,
        surface="expected bindings",
    ):
        raise GovernedPatchEvidenceError("expected bindings must be canonical JSON")
    try:
        return NativePatchBindings(**value)
    except TypeError as exc:
        raise GovernedPatchEvidenceError("expected bindings are malformed") from exc


def _bounded_text(path: str, *, field: str, max_bytes: int) -> str:
    raw = _read_regular_bounded(
        Path(path),
        field=field,
        max_bytes=max_bytes,
    )
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GovernedPatchEvidenceError(f"{field} is not UTF-8") from exc


async def _run_once(args: argparse.Namespace) -> dict[str, Any]:
    bindings = _canonical_bindings(args.expected_bindings_json)
    request_content = _bounded_text(
        args.request_json,
        field="governed patch request",
        max_bytes=128 * 1024,
    )
    intent = _bounded_text(
        args.expected_semantic_intent_file,
        field="semantic intent",
        max_bytes=32 * 1024,
    )
    request = parse_governed_patch_request(
        request_content,
        repo_root=Path(args.repo_root),
        expected=bindings,
        accepted_base_sha=bindings.base_sha,
        expected_content_sha256=hashlib.sha256(
            request_content.encode("utf-8")
        ).hexdigest(),
        expected_semantic_intent=intent,
        expected_task_snapshot_sha256=args.expected_task_snapshot_sha256,
    )
    result = await author_governed_patch(
        request,
        evidence_root=Path(args.evidence_root),
        semantic_artifact_sha256=args.semantic_artifact_sha256,
        provider_call_id=args.provider_call_id,
        timeout_seconds=args.timeout_s,
    )
    return result.to_dict()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        payload = asyncio.run(_run_once(args))
    except (GovernedPatchEvidenceError, OSError, RuntimeError) as exc:
        raise SystemExit(f"governed patch provider refused input: {exc}") from exc
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
