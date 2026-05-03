"""Governed task execution pipeline for AgentRunner.

This module owns the ordered completion path:
Telos check -> prompt/context preparation -> provider call -> semantic repair
-> honors/quality validation -> artifact contract check.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from dharma_swarm.agent_runner_quality import (
    CompletionAssessment,
    assess_completion_semantics,
    assess_honors_checkpoint,
    build_semantic_repair_request,
    semantic_attempt_timeout_seconds,
    semantic_repair_attempts,
)
from dharma_swarm.models import AgentConfig, GateDecision, LLMRequest, LLMResponse, Task
from dharma_swarm.telos_gates import check_with_reflective_reroute

_ERROR_PREFIXES = (
    "error",
    "api error:",
    "timeout: exceeded limit",
    "not logged in · please run /login",
    "openrouter error:",
    "no openrouter_api_key set",
    "credit balance is too low",
    "credit balance",
    "insufficient_quota",
    "rate_limit_exceeded",
    "you exceeded your current quota",
    "billing hard limit",
)

CompletionAttempt = tuple[Any | None, Any | None, LLMResponse, str, float]
PromptBuilder = Callable[[Task, AgentConfig, str], LLMRequest]
StigmergyInjector = Callable[[LLMRequest, Task, AgentConfig], Awaitable[None]]
UserRequestRecorder = Callable[[Task, LLMRequest], Awaitable[None]]
MemoryContextProvider = Callable[[], Awaitable[str]]
RequiresTooling = Callable[[Task, AgentConfig], bool]
EnsureLocalToolSandbox = Callable[[Task], Awaitable[None]]
TaskPredicate = Callable[[Task], bool]
LocalToolingCapability = Callable[[], bool]
ActiveInferenceStarter = Callable[[Task], tuple[Any | None, Any | None]]
CompletionAttemptExecutor = Callable[[Task, LLMRequest, int], Awaitable[CompletionAttempt]]
DeepResearchRunner = Callable[[Task], Awaitable[tuple[str, float]]]
ArtifactPathResolver = Callable[[Task], list[Path]]
GateChecker = Callable[..., Any]


def task_metadata(task: Task) -> dict[str, Any]:
    return task.metadata if isinstance(task.metadata, dict) else {}


def looks_like_provider_failure(content: str | None) -> bool:
    """Heuristic guard against error strings being marked as completed work."""
    normalized = (content or "").strip().lower()
    if not normalized:
        return True
    if len(normalized) < 200:
        if any(prefix in normalized for prefix in _ERROR_PREFIXES):
            return True
    return any(normalized.startswith(prefix) for prefix in _ERROR_PREFIXES)


def required_artifact_paths(task: Task) -> list[Path]:
    """Return required artifact paths declared in task metadata."""
    metadata = task_metadata(task)
    raw_values: list[Any] = []
    for key in ("target_file", "target_path", "artifact_path", "required_artifact"):
        value = metadata.get(key)
        if value:
            raw_values.append(value)
    for key in ("required_artifacts", "artifact_paths", "target_files"):
        value = metadata.get(key)
        if isinstance(value, list):
            raw_values.extend(value)
        elif value:
            raw_values.append(value)

    out: list[Path] = []
    seen: set[str] = set()
    for raw in raw_values:
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if not text:
            continue
        path = Path(text).expanduser()
        norm = str(path)
        if norm in seen:
            continue
        seen.add(norm)
        out.append(path)
    return out


@dataclass(slots=True)
class PipelineResult:
    result: str
    request: LLMRequest | None
    response: LLMResponse | None
    route_request: Any | None
    route_decision: Any | None
    latency_ms: float
    quality_score: float | None
    active_inference_engine: Any | None
    active_inference_prediction: Any | None


class PipelineError(RuntimeError):
    """Structured pipeline failure with partial execution context."""

    def __init__(
        self,
        message: str,
        *,
        request: LLMRequest | None = None,
        response: LLMResponse | None = None,
        route_request: Any | None = None,
        route_decision: Any | None = None,
        latency_ms: float = 0.0,
        quality_score: float | None = None,
        active_inference_engine: Any | None = None,
        active_inference_prediction: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.request = request
        self.response = response
        self.route_request = route_request
        self.route_decision = route_decision
        self.latency_ms = latency_ms
        self.quality_score = quality_score
        self.active_inference_engine = active_inference_engine
        self.active_inference_prediction = active_inference_prediction


@dataclass(slots=True)
class TaskExecutionPipeline:
    config: AgentConfig
    has_provider: bool
    build_prompt: PromptBuilder
    inject_stigmergy_context: StigmergyInjector
    requires_tooling: RequiresTooling
    ensure_local_tool_sandbox: EnsureLocalToolSandbox
    requires_local_side_effects: TaskPredicate
    can_execute_local_tooling: LocalToolingCapability
    start_active_inference: ActiveInferenceStarter
    execute_completion_attempt: CompletionAttemptExecutor
    run_deep_research_task: DeepResearchRunner
    record_user_request: UserRequestRecorder | None = None
    memory_context_provider: MemoryContextProvider | None = None
    artifact_path_resolver: ArtifactPathResolver = required_artifact_paths
    gate_checker: GateChecker = check_with_reflective_reroute

    async def run(self, task: Task) -> PipelineResult:
        request: LLMRequest | None = None
        route_request: Any | None = None
        route_decision: Any | None = None
        response: LLMResponse | None = None
        completion_latency_ms = 0.0
        active_inference_engine: Any | None = None
        active_inference_prediction: Any | None = None
        observed_quality_score: float | None = None

        try:
            metadata = task_metadata(task)
            task_type = str(metadata.get("task_type", "general") or "general")
            spec_ref = str(metadata.get("spec_ref", "")).strip() or None
            req_refs_raw = metadata.get("requirement_refs", [])
            if isinstance(req_refs_raw, str):
                req_refs = [req_refs_raw]
            elif isinstance(req_refs_raw, list):
                req_refs = [str(r) for r in req_refs_raw if str(r).strip()]
            else:
                req_refs = []
            seed_reflection = str(metadata.get("think_notes", "")).strip()
            if not seed_reflection:
                seed_reflection = (
                    f"Task={task.title}. Goal: execute safely with bounded changes."
                )

            gate = self.gate_checker(
                action=task.title,
                content=task.description,
                tool_name="agent_runner",
                think_phase="before_complete",
                reflection=seed_reflection,
                max_reroutes=2,
                spec_ref=spec_ref,
                requirement_refs=req_refs,
            )
            if gate.result.decision == GateDecision.BLOCK:
                raise RuntimeError(f"Telos block: {gate.result.reason}")

            plan_context = ""
            if gate.attempts:
                plan_context = (
                    "## Reflective Reroute Context\n"
                    f"- Reroute attempts: {gate.attempts}\n"
                    f"- Gate reason: {gate.result.reason}\n"
                    "- Apply these lenses before execution:\n"
                    + "\n".join(f"  - {s}" for s in gate.suggestions)
                )
            request = self.build_prompt(task, self.config, plan_context)
            await self.inject_stigmergy_context(request, task, self.config)
            if self.record_user_request is not None:
                await self.record_user_request(task, request)

            if self.memory_context_provider is not None:
                memory_ctx = await self.memory_context_provider()
                if memory_ctx.strip():
                    request.system = request.system + "\n\n" + memory_ctx

            if self.requires_tooling(task, self.config):
                await self.ensure_local_tool_sandbox(task)

            if self.requires_local_side_effects(task) and not self.can_execute_local_tooling():
                raise RuntimeError(
                    f"Provider {self.config.provider.value} cannot execute local tooling task "
                    "without a subprocess agent or attached sandbox"
                )

            active_inference_engine, active_inference_prediction = (
                self.start_active_inference(task)
            )

            if task_type == "deep_research":
                result, completion_latency_ms = await self.run_deep_research_task(task)
                observed_quality_score = 1.0
            elif self.has_provider:
                current_request = request
                attempts_remaining = semantic_repair_attempts(task, self.config)
                attempt_index = 1
                accepted_checkpoint: Any | None = None
                while True:
                    attempt_timeout_seconds = semantic_attempt_timeout_seconds(
                        task,
                        self.config,
                        attempts_remaining=attempts_remaining,
                    )
                    try:
                        attempt_result = self.execute_completion_attempt(
                            task,
                            current_request,
                            attempt_index,
                        )
                        if attempt_timeout_seconds is not None:
                            (
                                route_request,
                                route_decision,
                                response,
                                result,
                                attempt_latency_ms,
                            ) = await asyncio.wait_for(
                                attempt_result,
                                timeout=attempt_timeout_seconds,
                            )
                        else:
                            (
                                route_request,
                                route_decision,
                                response,
                                result,
                                attempt_latency_ms,
                            ) = await attempt_result
                    except asyncio.TimeoutError:
                        attempt_label = (
                            f"{attempt_timeout_seconds:.2f}s"
                            if attempt_timeout_seconds is not None
                            else "the attempt budget"
                        )
                        completion_latency_ms += (
                            max(0.0, attempt_timeout_seconds) * 1000.0
                            if attempt_timeout_seconds is not None
                            else 0.0
                        )
                        assessment = CompletionAssessment(
                            accepted=False,
                            quality_score=0.0,
                            reason=(
                                "Semantic acceptance failed: attempt timeout, timed out after "
                                f"{attempt_label}"
                            ),
                        )
                        observed_quality_score = 0.0
                        if attempts_remaining <= 0:
                            raise RuntimeError(assessment.reason)
                        current_request = build_semantic_repair_request(
                            current_request,
                            failed_result=f"ATTEMPT TIMED OUT after {attempt_label}",
                            assessment=assessment,
                            attempt_index=attempt_index,
                        )
                        attempts_remaining -= 1
                        attempt_index += 1
                        continue
                    completion_latency_ms += attempt_latency_ms
                    if looks_like_provider_failure(result):
                        raise RuntimeError(result or "Provider returned empty response")
                    assessment = await assess_completion_semantics(
                        task,
                        self.config,
                        result,
                        requires_tooling=self.requires_tooling(task, self.config),
                        requires_local_side_effects=self.requires_local_side_effects(task),
                    )
                    accepted_checkpoint = None
                    if assessment.accepted:
                        assessment, accepted_checkpoint = assess_honors_checkpoint(
                            task,
                            result,
                            semantic_quality_score=assessment.quality_score,
                        )
                    observed_quality_score = assessment.quality_score
                    if assessment.accepted:
                        if accepted_checkpoint is not None:
                            updated_meta = task_metadata(task)
                            updated_meta["honors_checkpoint"] = accepted_checkpoint.model_dump(mode="json")
                            task.metadata = updated_meta
                        break
                    if attempts_remaining <= 0:
                        raise RuntimeError(assessment.reason)
                    current_request = build_semantic_repair_request(
                        current_request,
                        failed_result=result,
                        assessment=assessment,
                        attempt_index=attempt_index,
                    )
                    attempts_remaining -= 1
                    attempt_index += 1
            else:
                result = f"[mock] Agent {self.config.name} completed: {task.title}"
                observed_quality_score = 1.0

            required_artifacts = self.artifact_path_resolver(task)
            missing_artifacts = [path for path in required_artifacts if not path.exists()]
            if missing_artifacts:
                missing_str = ", ".join(str(path) for path in missing_artifacts[:5])
                raise RuntimeError(
                    f"Completion contract failed: required artifact missing ({missing_str})"
                )

            return PipelineResult(
                result=result,
                request=request,
                response=response,
                route_request=route_request,
                route_decision=route_decision,
                latency_ms=completion_latency_ms,
                quality_score=observed_quality_score,
                active_inference_engine=active_inference_engine,
                active_inference_prediction=active_inference_prediction,
            )
        except PipelineError:
            raise
        except Exception as exc:
            raise PipelineError(
                str(exc),
                request=request,
                response=response,
                route_request=route_request,
                route_decision=route_decision,
                latency_ms=completion_latency_ms,
                quality_score=observed_quality_score,
                active_inference_engine=active_inference_engine,
                active_inference_prediction=active_inference_prediction,
            ) from exc
