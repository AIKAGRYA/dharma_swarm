"""A2A model-council E2E receipt harness.

The live path uses DharmaSwarm's A2A local control plane:
``CardRegistry`` -> ``A2AServer`` -> ``A2AClient`` -> per-agent handlers. Each
handler constructs its model runtime through ``resolve_runtime_provider_config``
and ``create_runtime_provider`` before making a bounded LLM call.

Dry-run mode plans the same A2A route without constructing providers or making
model calls.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Iterable

from dharma_swarm.a2a.a2a_client import A2AClient
from dharma_swarm.a2a.a2a_server import (
    A2AArtifact,
    A2APart,
    A2AServer,
    A2ATask,
    A2ATaskStatus,
)
from dharma_swarm.a2a.agent_card import AgentCapability, AgentCard, CardRegistry
from dharma_swarm.model_routing_live_probe import (
    LiveProbeSpec,
    build_probe_plan,
    classify_live_failure,
)
from dharma_swarm.model_status import LIVE_MODEL_E2E_ENV, ModelStatusProjection, floor_model_status
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.runtime_provider import (
    RuntimeProviderConfig,
    create_runtime_provider,
    resolve_runtime_provider_config,
)

MODEL_COUNCIL_SCHEMA_VERSION = "dharma.model_council_e2e.v1"
COUNCIL_STAGE_NAMES = ("draft", "critique", "synthesis")
MIN_COUNCIL_MODELS = 3

Resolver = Callable[..., RuntimeProviderConfig]
ProviderFactory = Callable[[RuntimeProviderConfig], Any]


@dataclass(frozen=True, slots=True)
class CouncilAgentSpec:
    stage: str
    agent_name: str
    capability: str
    route: LiveProbeSpec


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _preview(value: str, *, limit: int = 220) -> str:
    return " ".join(str(value).split())[:limit]


def _message_text(task: A2ATask) -> str:
    if not task.history or not task.history[-1].parts:
        return ""
    return str(task.history[-1].parts[0].content)


def _config_summary(config: RuntimeProviderConfig) -> dict[str, Any]:
    return {
        "provider": config.provider.value,
        "default_model": config.default_model,
        "base_url": config.base_url,
        "transport_mode": config.transport_mode,
        "working_dir": config.working_dir,
        "timeout_seconds": config.timeout_seconds,
        "binary_path": config.binary_path,
        "available": config.available,
        "source": config.source,
        "api_key_present": bool(config.api_key),
    }


async def _maybe_close_provider(provider: Any) -> None:
    close = getattr(provider, "close", None)
    if not callable(close):
        return
    result = close()
    if inspect.isawaitable(result):
        await result


async def _complete_once(
    spec: CouncilAgentSpec,
    prompt: str,
    *,
    resolver: Resolver,
    provider_factory: ProviderFactory,
    timeout_seconds: int,
    working_dir: str | None,
) -> dict[str, Any]:
    started_at = _utc_now()
    monotonic_started = time.monotonic()
    try:
        config = resolver(
            spec.route.provider,
            model=spec.route.model_id,
            timeout_seconds=timeout_seconds,
            working_dir=working_dir,
        )
    except Exception as exc:
        return {
            "status": "failed",
            "failure_class": classify_live_failure(exc),
            "started_at": started_at,
            "elapsed_ms": int((time.monotonic() - monotonic_started) * 1000),
            "live_call_attempted": False,
            "error": _preview(exc),
        }
    config_data = _config_summary(config)
    if not config.available:
        return {
            "status": "failed",
            "failure_class": "routing_bug",
            "started_at": started_at,
            "elapsed_ms": int((time.monotonic() - monotonic_started) * 1000),
            "live_call_attempted": False,
            "runtime_config": config_data,
            "error": "model-status projection marked route live, but runtime config is unavailable",
        }
    try:
        provider = provider_factory(config)
    except Exception as exc:
        return {
            "status": "failed",
            "failure_class": classify_live_failure(exc),
            "started_at": started_at,
            "elapsed_ms": int((time.monotonic() - monotonic_started) * 1000),
            "live_call_attempted": False,
            "runtime_config": config_data,
            "error": _preview(exc),
        }
    try:
        request = LLMRequest(
            model=spec.route.model_id,
            system=(
                "You are a model-council participant inside DharmaSwarm. "
                "Answer only the assigned council stage. Do not use tools."
            ),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=900,
            temperature=0.2,
        )
        try:
            response: LLMResponse = await asyncio.wait_for(
                provider.complete(request),
                timeout=timeout_seconds,
            )
        except Exception as exc:
            return {
                "status": "failed",
                "failure_class": classify_live_failure(exc),
                "started_at": started_at,
                "elapsed_ms": int((time.monotonic() - monotonic_started) * 1000),
                "live_call_attempted": True,
                "runtime_config": config_data,
                "error": _preview(exc),
            }
        content = str(response.content or "").strip()
        if not content:
            return {
                "status": "failed",
                "failure_class": "schema_failure",
                "started_at": started_at,
                "elapsed_ms": int((time.monotonic() - monotonic_started) * 1000),
                "live_call_attempted": True,
                "runtime_config": config_data,
                "served_provider": response.provider or None,
                "served_model": response.model,
                "error": "empty council response",
            }
        return {
            "status": "ok",
            "failure_class": None,
            "started_at": started_at,
            "elapsed_ms": int((time.monotonic() - monotonic_started) * 1000),
            "live_call_attempted": True,
            "runtime_config": config_data,
            "served_provider": response.provider or None,
            "served_model": response.model,
            "usage": dict(response.usage),
            "stop_reason": response.stop_reason,
            "content": content,
            "content_sha256": _hash_text(content),
            "content_preview": _preview(content),
        }
    finally:
        await _maybe_close_provider(provider)


def select_council_agents(
    projection: ModelStatusProjection | None = None,
    *,
    model_ids: Iterable[str] | None = None,
) -> tuple[list[CouncilAgentSpec], list[dict[str, Any]], dict[str, Any]]:
    """Pick up to three live floor routes, preferring provider diversity."""

    specs, skipped, projection_data = build_probe_plan(
        projection or floor_model_status(),
        model_ids=model_ids,
    )
    selected: list[LiveProbeSpec] = []
    seen_providers: set[ProviderType] = set()
    for spec in specs:
        if spec.provider in seen_providers:
            continue
        selected.append(spec)
        seen_providers.add(spec.provider)
        if len(selected) >= MIN_COUNCIL_MODELS:
            break
    if len(selected) < MIN_COUNCIL_MODELS:
        for spec in specs:
            if spec in selected:
                continue
            selected.append(spec)
            if len(selected) >= MIN_COUNCIL_MODELS:
                break
    agents = [
        CouncilAgentSpec(
            stage=stage,
            agent_name=f"model-council-{stage}",
            capability=f"model_council_{stage}",
            route=route,
        )
        for stage, route in zip(COUNCIL_STAGE_NAMES, selected, strict=False)
    ]
    return agents, skipped, projection_data


def _route_to_dict(spec: LiveProbeSpec) -> dict[str, Any]:
    return {
        "logical_model_id": spec.logical_model_id,
        "display_name": spec.display_name,
        "provider": spec.provider.value,
        "model_id": spec.model_id,
        "route": spec.route,
        "rank": spec.rank,
        "max_context": spec.max_context,
        "strengths": list(spec.strengths),
    }


def _agent_to_dict(agent: CouncilAgentSpec) -> dict[str, Any]:
    return {
        "stage": agent.stage,
        "agent_name": agent.agent_name,
        "capability": agent.capability,
        "route": _route_to_dict(agent.route),
    }


def _build_stage_prompt(stage: str, topic: str, transcript: list[dict[str, Any]]) -> str:
    if stage == "draft":
        return (
            f"Council topic: {topic}\n\n"
            "Stage: draft. Produce a concrete draft answer with assumptions, "
            "risks, and one measurable success criterion."
        )
    if stage == "critique":
        draft = transcript[-1]["content"] if transcript else "(no draft)"
        return (
            f"Council topic: {topic}\n\n"
            f"Draft to critique:\n{draft}\n\n"
            "Stage: critique. Identify the strongest issue in the draft, one "
            "missing test or receipt, and a concrete correction."
        )
    draft = transcript[0]["content"] if transcript else "(no draft)"
    critique = transcript[-1]["content"] if transcript else "(no critique)"
    return (
        f"Council topic: {topic}\n\n"
        f"Draft:\n{draft}\n\n"
        f"Critique:\n{critique}\n\n"
        "Stage: synthesis. Produce the final council artifact. Include the "
        "decision, evidence needed, and next action."
    )


def _task_to_dict(task: A2ATask | None) -> dict[str, Any] | None:
    if task is None:
        return None
    return {
        "id": task.id,
        "context_id": task.context_id,
        "from_agent": task.from_agent,
        "to_agent": task.to_agent,
        "capability": task.capability,
        "status": task.status.value,
        "trace_id": task.trace_id,
        "metadata": task.metadata,
        "artifact_count": len(task.artifacts),
        "result_sha256": _hash_text(task.result) if task.result else None,
        "result_preview": _preview(task.result) if task.result else "",
        "error": task.error,
    }


def _run_coro_blocking(coro: Any) -> Any:
    # Handlers run synchronously inside A2AServer._dispatch, which the spine
    # adapter now drives from a running event loop (submit_task_via_spine).
    # asyncio.run() would raise there; mirror spine_adapter's sync bridge and
    # give the coroutine its own loop on a worker thread instead.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _make_handler(
    spec: CouncilAgentSpec,
    *,
    resolver: Resolver,
    provider_factory: ProviderFactory,
    timeout_seconds: int,
    working_dir: str | None,
    call_log: list[dict[str, Any]],
) -> Callable[[A2ATask], A2ATask]:
    def _handler(task: A2ATask) -> A2ATask:
        prompt = _message_text(task)
        completion = _run_coro_blocking(
            _complete_once(
                spec,
                prompt,
                resolver=resolver,
                provider_factory=provider_factory,
                timeout_seconds=timeout_seconds,
                working_dir=working_dir,
            )
        )
        call_log.append(
            {
                "stage": spec.stage,
                "agent_name": spec.agent_name,
                "task_id": task.id,
                "route": spec.route.route,
                **completion,
            }
        )
        task.metadata.update(
            {
                "model_council_stage": spec.stage,
                "planned_provider": spec.route.provider.value,
                "planned_model_id": spec.route.model_id,
                "planned_route": spec.route.route,
                "live_call_attempted": bool(completion.get("live_call_attempted")),
            }
        )
        if completion.get("status") == "ok":
            content = str(completion.get("content") or "")
            task.status = A2ATaskStatus.COMPLETED
            task.result = content
            task.artifacts.append(
                A2AArtifact(
                    name=f"{spec.stage}_artifact",
                    description=f"Model council {spec.stage} output",
                    parts=[A2APart.text(content)],
                    metadata={
                        "content_sha256": completion.get("content_sha256"),
                        "planned_route": spec.route.route,
                    },
                )
            )
        else:
            task.status = A2ATaskStatus.FAILED
            task.error = str(completion.get("error") or completion.get("failure_class") or "unknown failure")
        return task

    return _handler


def _run_live_a2a_council(
    agents: list[CouncilAgentSpec],
    *,
    topic: str,
    timeout_seconds: int,
    working_dir: str | None,
    resolver: Resolver,
    provider_factory: ProviderFactory,
    cards_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    call_log: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="model_council_cards_") as tmp:
        registry = CardRegistry(cards_dir=cards_dir or Path(tmp))
        server = A2AServer(persist=False)
        for agent in agents:
            registry.register(
                AgentCard(
                    name=agent.agent_name,
                    description=f"Model council {agent.stage} participant",
                    capabilities=[
                        AgentCapability(
                            agent.capability,
                            f"Performs model council {agent.stage} over A2A",
                        )
                    ],
                    endpoint="local://",
                    provider=agent.route.provider.value,
                    model=agent.route.model_id,
                    role=agent.stage,
                    metadata={"route": agent.route.route},
                )
            )
            server.register_handler(
                agent.capability,
                _make_handler(
                    agent,
                    resolver=resolver,
                    provider_factory=provider_factory,
                    timeout_seconds=timeout_seconds,
                    working_dir=working_dir,
                    call_log=call_log,
                ),
            )
        client = A2AClient(registry=registry, server=server, default_from="model-council-orchestrator")
        transcript: list[dict[str, Any]] = []
        context_id = f"model-council-{_utc_now()}"
        previous_agent = "model-council-orchestrator"
        for agent in agents:
            prompt = _build_stage_prompt(agent.stage, topic, transcript)
            result = client.delegate_to(
                agent.agent_name,
                prompt,
                capability=agent.capability,
                from_agent=previous_agent,
                metadata={
                    "model_council": True,
                    "stage": agent.stage,
                    "planned_route": agent.route.route,
                },
                context_id=context_id,
            )
            task = result.task
            transcript.append(
                {
                    "stage": agent.stage,
                    "agent_name": agent.agent_name,
                    "a2a_task": _task_to_dict(task),
                    "success": result.success,
                    "content": result.result_text if result.success else "",
                    "content_sha256": _hash_text(result.result_text) if result.result_text else None,
                    "content_preview": _preview(result.result_text) if result.result_text else "",
                    "failure_class": None if result.success else classify_live_failure(result.error),
                    "error": result.error,
                    "route": _route_to_dict(agent.route),
                }
            )
            if not result.success:
                break
            previous_agent = agent.agent_name
        summary = {
            "a2a_path": "local_in_process",
            "a2a_server_tasks": server.summary(),
            "registered_cards": [card.name for card in registry.list_all()],
        }
        return transcript, call_log, summary


def build_model_council_receipt(
    *,
    projection: ModelStatusProjection | None = None,
    live_calls_enabled: bool = False,
    topic: str = "Assess whether DharmaSwarm model routing is ready to advertise current floor models.",
    timeout_seconds: int = 120,
    working_dir: str | None = None,
    model_ids: Iterable[str] | None = None,
    resolver: Resolver = resolve_runtime_provider_config,
    provider_factory: ProviderFactory = create_runtime_provider,
) -> dict[str, Any]:
    agents, skipped, projection_data = select_council_agents(projection, model_ids=model_ids)
    enough_agents = len(agents) >= MIN_COUNCIL_MODELS
    transcript: list[dict[str, Any]] = []
    call_log: list[dict[str, Any]] = []
    a2a_summary: dict[str, Any] = {
        "a2a_path": "local_in_process",
        "a2a_server_tasks": {},
        "registered_cards": [],
    }

    if live_calls_enabled and enough_agents:
        transcript, call_log, a2a_summary = _run_live_a2a_council(
            agents,
            topic=topic,
            timeout_seconds=timeout_seconds,
            working_dir=working_dir,
            resolver=resolver,
            provider_factory=provider_factory,
        )

    live_attempted = sum(1 for call in call_log if call.get("live_call_attempted"))
    failed_calls = [call for call in call_log if call.get("status") != "ok"]
    completed_stages = [row for row in transcript if row.get("success")]
    final_artifact = transcript[-1]["content"] if transcript and transcript[-1].get("success") else ""
    if not enough_agents:
        status = "blocked"
    elif not live_calls_enabled:
        status = "planned"
    elif len(completed_stages) == MIN_COUNCIL_MODELS and not failed_calls:
        status = "passed"
    else:
        status = "failed"

    return {
        "schema_version": MODEL_COUNCIL_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "mode": "live" if live_calls_enabled else "dry-run",
        "live_env": LIVE_MODEL_E2E_ENV,
        "live_calls_enabled": live_calls_enabled,
        "status": status,
        "topic": topic,
        "requirements": {
            "min_models": MIN_COUNCIL_MODELS,
            "stages": list(COUNCIL_STAGE_NAMES),
            "different_providers_when_available": True,
            "transport": "DharmaSwarm A2A local control plane",
        },
        "projection": {
            "schema_version": projection_data["schema_version"],
            "generated_at": projection_data["generated_at"],
            "oracle_state": projection_data["oracle_state"],
            "live_providers": projection_data["live_providers"],
        },
        "counts": {
            "planned_agents": len(agents),
            "skipped_models": len(skipped),
            "unique_planned_providers": len({agent.route.provider.value for agent in agents}),
            "live_calls_attempted": live_attempted,
            "completed_stages": len(completed_stages),
            "failed_stages": len(failed_calls),
        },
        "planned_agents": [_agent_to_dict(agent) for agent in agents],
        "skipped_models": skipped,
        "a2a": a2a_summary,
        "transcript": transcript,
        "provider_call_log": call_log,
        "final_artifact": {
            "status": "available" if final_artifact else "not_available",
            "content_sha256": _hash_text(final_artifact) if final_artifact else None,
            "content_preview": _preview(final_artifact) if final_artifact else "",
        },
    }


def write_model_council_receipt(payload: dict[str, Any], output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


__all__ = [
    "COUNCIL_STAGE_NAMES",
    "MIN_COUNCIL_MODELS",
    "MODEL_COUNCIL_SCHEMA_VERSION",
    "CouncilAgentSpec",
    "build_model_council_receipt",
    "select_council_agents",
    "write_model_council_receipt",
]
