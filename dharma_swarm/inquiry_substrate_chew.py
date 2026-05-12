"""Read-only inquiry chewing through the TelicSeam metabolic loop."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from dharma_swarm.models import (
    GateDecision,
    LLMRequest,
    LLMResponse,
    ProviderType,
    Task,
    TaskPriority,
)
from dharma_swarm.runtime_provider import (
    RuntimeProviderConfig,
    create_runtime_provider,
    preferred_runtime_provider_configs,
    probe_runtime_provider,
    resolve_runtime_provider_config,
)
from dharma_swarm.telic_seam import TelicSeam
from dharma_swarm.telos_gates import TelosGatekeeper

FAILURE_CLASS_OK = "ok"
FAILURE_CLASS_GATE_BLOCK = "gate_block"
FAILURE_CLASS_GATE_REVIEW = "gate_review"
FAILURE_CLASS_PROBE_FAILED = "probe_failed"
FAILURE_CLASS_PROVIDER_EXCEPTION = "provider_exception"
FAILURE_CLASS_TIMEOUT = "timeout"
FAILURE_CLASS_EMPTY_CONTENT = "empty_content"

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED_PATH = REPO_ROOT / "docs/inquiry/2026-05-09-llm-substrate-want.md"
DEFAULT_INLET_PATH = REPO_ROOT / "docs/inquiry/INLET.md"
DEFAULT_OUTPUT_DIR = Path.home() / ".dharma/inquiry/chews"
DEFAULT_WITNESS_PATH = Path.home() / ".dharma/witness/inquiry_substrate_chew.jsonl"
CLI_PROVIDERS = {ProviderType.CLAUDE_CODE, ProviderType.CODEX}
DEFAULT_API_PROVIDER_ORDER = tuple(
    provider
    for provider in (
        ProviderType.OLLAMA,
        ProviderType.NVIDIA_NIM,
        ProviderType.GROQ,
        ProviderType.CEREBRAS,
        ProviderType.SILICONFLOW,
        ProviderType.SAMBANOVA,
        ProviderType.TOGETHER,
        ProviderType.FIREWORKS,
        ProviderType.OPENROUTER_FREE,
        ProviderType.MISTRAL,
        ProviderType.GOOGLE_AI,
        ProviderType.CHUTES,
        ProviderType.OPENROUTER,
        ProviderType.ANTHROPIC,
        ProviderType.OPENAI,
    )
    if provider not in CLI_PROVIDERS
)


class ProviderLike(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        ...


class GatekeeperLike(Protocol):
    def check(
        self,
        action: str,
        content: str = "",
        tool_name: str = "",
        trust_mode: str | None = None,
        think_phase: str | None = None,
        reflection: str = "",
    ) -> Any:
        ...


@dataclass(frozen=True)
class ChewConfig:
    seed_path: Path = DEFAULT_SEED_PATH
    inlet_path: Path = DEFAULT_INLET_PATH
    output_dir: Path = DEFAULT_OUTPUT_DIR
    witness_path: Path = DEFAULT_WITNESS_PATH
    ontology_path: Path | None = None
    provider_type: ProviderType | None = None
    model: str | None = None
    prompt_class: str = "seed_chew"
    max_tokens: int = 4096
    max_seed_chars: int = 24_000
    timeout_seconds: float = 120.0
    block_on_review: bool = False
    dry_run: bool = False
    reasoning_effort: str | None = None
    probe: bool = False
    probe_timeout_seconds: float = 5.0
    chunk_size: int = 0
    chunk_index: int = 1


@dataclass(frozen=True)
class ChewResult:
    success: bool
    blocked: bool
    provider_label: str
    output_path: Path | None
    witness_path: Path | None
    proposal_id: str | None
    gate_decision_id: str | None
    outcome_id: str | None
    value_event_id: str | None
    contribution_id: str | None
    gate_decision: str
    gate_reason: str
    task_id: str
    artifact_sha256: str = ""
    error: str = ""
    failure_class: str = FAILURE_CLASS_OK
    model: str = ""
    stop_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["output_path"] = str(self.output_path) if self.output_path else ""
        data["witness_path"] = str(self.witness_path) if self.witness_path else ""
        return data


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in cleaned.split("-") if part)[:80] or "inquiry-seed"


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return "", text
    return f"{parts[0]}\n---\n", parts[1]


def _split_example_sections(body: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^###\s+(E\d+)\s*$", body))
    examples: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        examples.append((match.group(1), body[match.start():end].strip()))
    return examples


def select_seed_chunk(
    seed_text: str,
    *,
    chunk_size: int = 0,
    chunk_index: int = 1,
) -> tuple[str, str]:
    """Select an example chunk from a target-blind labeling packet."""

    if chunk_size <= 0:
        return seed_text, ""
    frontmatter, body = _split_frontmatter(seed_text)
    examples = _split_example_sections(body)
    if not examples:
        return seed_text, ""
    total_chunks = (len(examples) + chunk_size - 1) // chunk_size
    if chunk_index < 1 or chunk_index > total_chunks:
        raise ValueError(
            f"chunk_index must be between 1 and {total_chunks}; got {chunk_index}"
        )
    start = (chunk_index - 1) * chunk_size
    selected = examples[start:start + chunk_size]
    ids = ", ".join(example_id for example_id, _ in selected)
    chunk_header = (
        f"\n# Chunk {chunk_index}/{total_chunks}\n\n"
        f"Label only these example ids: {ids}.\n\n"
    )
    chunk_text = frontmatter + chunk_header + "\n\n---\n\n".join(
        section for _, section in selected
    )
    return chunk_text, f"chunk {chunk_index}/{total_chunks}: {ids}"


def build_prompt(
    *,
    inlet_text: str,
    seed_text: str,
    seed_path: Path,
    prompt_class: str = "seed_chew",
    max_seed_chars: int = 24_000,
) -> tuple[str, str]:
    seed_slice = seed_text[:max_seed_chars]
    if len(seed_text) > max_seed_chars:
        seed_slice += (
            "\n\n[TRUNCATED FOR CONTEXT BUDGET: continue from visible material; "
            "do not imply you read omitted text.]"
        )
    system = (
        "You are a read-only resident inquiry organ inside dharma_swarm. "
        "You are not adjacent to the repo and you are not editing files. "
        "Your answer will be recorded as an Outcome in the TelicSeam. "
        "Do not claim runtime metabolism happened unless this prompt tells you "
        "which ActionProposal/GateDecision/Outcome records were created."
    )
    if prompt_class == "blind_calibration_label":
        prompt = f"""Label this target-blind calibration packet.

Return only a JSON array. Each item must have exactly:
{{"id": "E01", "label": "padded|grounded|mixed|unclear", "justification": "one sentence"}}

Do not return markdown. Do not summarize the packet. Do not add sections.
Use every example id present in the seed exactly once.

SEED PATH: {seed_path}
SEED SHA256: {_sha256_text(seed_text)}
SEED CONTENT:
{seed_slice}
"""
        return system, prompt

    prompt = f"""Read the inquiry inlet protocol and then chew the seed.

Return exactly these sections:
1. Substrate Signal
2. What I Disagree With
3. What Should Be Tested Next
4. Possible Bhed Gnan Failure Modes
5. Smallest Next Runtime Move
6. Confidence And Unknowns

Keep it dense. No praise, no performance of certainty, no sales framing.

INLET PROTOCOL:
{inlet_text}

SEED PATH: {seed_path}
SEED SHA256: {_sha256_text(seed_text)}
SEED CONTENT:
{seed_slice}
"""
    return system, prompt


def build_task(
    seed_path: Path,
    seed_sha256: str,
    prompt_class: str = "seed_chew",
    *,
    chunk_size: int = 0,
    chunk_index: int = 1,
    chunk_label: str = "",
) -> Task:
    return Task(
        title=f"Chew inquiry seed: {seed_path.name}",
        description=(
            "Read-only resident inquiry chew. The provider analyzes the seed "
            "and returns a candidate metabolism artifact; it does not edit repo docs."
        ),
        priority=TaskPriority.NORMAL,
        created_by="inquiry_substrate_chew",
        metadata={
            "task_type": "inquiry_chew",
            "prompt_class": prompt_class,
            "seed_path": str(seed_path),
            "seed_sha256": seed_sha256,
            "chunk_size": chunk_size,
            "chunk_index": chunk_index,
            "chunk_label": chunk_label,
        },
    )


def resolve_provider_config(config: ChewConfig) -> RuntimeProviderConfig:
    if config.provider_type is not None:
        if config.provider_type in CLI_PROVIDERS:
            raise ValueError(
                f"{config.provider_type.value} is a CLI provider; use API/local "
                "providers so provider calls cannot edit the repo."
            )
        resolved = resolve_runtime_provider_config(
            config.provider_type,
            model=config.model,
            working_dir=str(REPO_ROOT),
            timeout_seconds=int(config.timeout_seconds),
        )
        if not resolved.available:
            raise RuntimeError(f"Provider unavailable: {config.provider_type.value}")
        return resolved
    configs = preferred_runtime_provider_configs(
        provider_order=DEFAULT_API_PROVIDER_ORDER,
        model_overrides={ProviderType.OPENROUTER_FREE: config.model},
        working_dir=str(REPO_ROOT),
        timeout_seconds=int(config.timeout_seconds),
    )
    if not configs:
        raise RuntimeError("No API/local runtime providers are available")
    return configs[0]


def _resolve_reasoning_effort(model: str | None, configured: str | None) -> str | None:
    if configured:
        return configured
    normalized = (model or "").strip().lower()
    if normalized.startswith("gpt-5"):
        # Default to "low" for the inquiry runner so the visible-content
        # budget isn't entirely consumed by hidden reasoning tokens.
        return "low"
    return None


# --- Phase 1 route witness (2026-05-10) ---------------------------------
# See docs/plans/2026-05-10-phase1-routing-witness.md.

_FAILURE_CLASS_TO_OUTCOME = {
    FAILURE_CLASS_OK: "success",
    FAILURE_CLASS_GATE_BLOCK: "gate_block",
    FAILURE_CLASS_GATE_REVIEW: "gate_block",
    FAILURE_CLASS_PROBE_FAILED: "no_route",
    FAILURE_CLASS_PROVIDER_EXCEPTION: "all_failed",
    FAILURE_CLASS_TIMEOUT: "timeout",
    FAILURE_CLASS_EMPTY_CONTENT: "empty_content",
}


async def _emit_chew_route_witness(
    *,
    decision_id: str,
    config: ChewConfig,
    provider_type: ProviderType | None,
    model: str,
    failure_class: str,
    duration_ms: float,
    response_obj: Any | None = None,
    error_detail: str = "",
    task_id: str = "",
) -> None:
    """Best-effort canonical route witness for one chew run.

    Emits exactly one RoutingDecisionRecord. For the provider-call branch,
    emits one ProviderAttemptRecord. For gate-block / probe-fail branches,
    emits no attempts (no provider was called).
    """
    try:
        from dharma_swarm.route_witness import (
            build_provider_attempt,
            emit_routing_decision,
        )
    except Exception:  # noqa: BLE001
        return

    outcome = _FAILURE_CLASS_TO_OUTCOME.get(failure_class, "unknown")
    success = failure_class == FAILURE_CLASS_OK
    chain = [provider_type] if provider_type is not None else []

    attempts = []
    if failure_class in {
        FAILURE_CLASS_OK,
        FAILURE_CLASS_PROVIDER_EXCEPTION,
        FAILURE_CLASS_TIMEOUT,
        FAILURE_CLASS_EMPTY_CONTENT,
    } and provider_type is not None:
        usage = {}
        stop_reason = ""
        if response_obj is not None:
            usage = dict(getattr(response_obj, "usage", {}) or {})
            stop_reason = getattr(response_obj, "stop_reason", "") or ""
        attempts.append(
            build_provider_attempt(
                decision_id=decision_id,
                attempt_idx=0,
                provider=provider_type,
                model=model,
                success=success,
                duration_ms=duration_ms,
                error=error_detail or None,
                stop_reason=stop_reason or None,
                usage=usage or None,
            )
        )

    decision_class = "pinned" if config.provider_type is not None else "widened"

    try:
        await emit_routing_decision(
            decision_id=decision_id,
            action_name="inquiry_chew",
            route_path="deliberative",
            selected_provider=provider_type or "",
            selected_model=model or "",
            candidate_chain=chain,
            decision_class=decision_class,
            caller="inquiry_substrate_chew",
            duration_ms=duration_ms,
            attempts=attempts,
            task_type="chew",
            task_signature=f"inquiry_chew:{config.prompt_class}",
            confidence=0.7 if success else 0.2,
            reasons=[f"failure_class={failure_class}"],
            task_id=task_id,
            outcome=outcome,
        )
    except Exception:  # noqa: BLE001
        pass


async def _call_provider(
    provider: ProviderLike,
    *,
    model: str,
    system: str,
    prompt: str,
    max_tokens: int,
    timeout_seconds: float,
    reasoning_effort: str | None = None,
) -> LLMResponse:
    request = LLMRequest(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        system=system,
        max_tokens=max_tokens,
        temperature=0.4,
        reasoning_effort=reasoning_effort,
    )
    return await asyncio.wait_for(provider.complete(request), timeout=timeout_seconds)


def _write_artifact(
    *,
    output_dir: Path,
    seed_path: Path,
    provider_label: str,
    response_text: str,
    task: Task,
    ids: dict[str, str | None],
) -> tuple[Path, str]:
    timestamp = _utc_now().strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"{timestamp}-{_safe_slug(seed_path.stem)}-{_safe_slug(provider_label)}.md"
    output_dir.mkdir(parents=True, exist_ok=True)
    body = f"""---
seed_path: {seed_path}
provider: {provider_label}
task_id: {task.id}
proposal_id: {ids.get("proposal_id") or ""}
gate_decision_id: {ids.get("gate_decision_id") or ""}
outcome_id: {ids.get("outcome_id") or ""}
prompt_class: {ids.get("prompt_class") or ""}
chunk_size: {task.metadata.get("chunk_size", 0)}
chunk_index: {task.metadata.get("chunk_index", 1)}
chunk_label: {task.metadata.get("chunk_label", "")}
recorded_at: {_utc_now().isoformat()}
---

{response_text.rstrip()}
"""
    path.write_text(body, encoding="utf-8")
    return path, _sha256_text(body)


def append_witness(
    *,
    witness_path: Path,
    result: ChewResult,
    seed_path: Path,
    seed_sha256: str,
    prompt_class: str,
    chunk_size: int = 0,
    chunk_index: int = 1,
    chunk_label: str = "",
) -> None:
    witness_path.expanduser().parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp_utc": _utc_now().isoformat(),
        "source": "inquiry_substrate_chew",
        "prompt_class": prompt_class,
        "seed_path": str(seed_path),
        "seed_sha256": seed_sha256,
        "chunk_size": chunk_size,
        "chunk_index": chunk_index,
        "chunk_label": chunk_label,
        **result.to_json(),
    }
    with witness_path.expanduser().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


async def _close_provider(provider: Any) -> None:
    close = getattr(provider, "close", None)
    if callable(close):
        close_result = close()
        if inspect.isawaitable(close_result):
            await close_result


def _blocked_result(
    *,
    task: Task,
    provider_label: str,
    proposal_id: str | None,
    gate_decision_id: str | None,
    outcome_id: str | None,
    decision: str,
    reason: str,
    witness_path: Path,
    failure_class: str = FAILURE_CLASS_GATE_BLOCK,
    model: str = "",
) -> ChewResult:
    return ChewResult(
        success=False,
        blocked=True,
        provider_label=provider_label,
        output_path=None,
        witness_path=witness_path,
        proposal_id=proposal_id,
        gate_decision_id=gate_decision_id,
        outcome_id=outcome_id,
        value_event_id=None,
        contribution_id=None,
        gate_decision=decision,
        gate_reason=reason,
        task_id=task.id,
        error=f"{failure_class}: {reason}",
        failure_class=failure_class,
        model=model,
    )


async def run_chew(
    config: ChewConfig,
    *,
    provider: ProviderLike | None = None,
    provider_label: str | None = None,
    seam: TelicSeam | None = None,
    gatekeeper: GatekeeperLike | None = None,
) -> ChewResult:
    seed_path = config.seed_path.expanduser()
    inlet_text = config.inlet_path.expanduser().read_text(encoding="utf-8")
    raw_seed_text = seed_path.read_text(encoding="utf-8")
    seed_text, chunk_label = select_seed_chunk(
        raw_seed_text,
        chunk_size=config.chunk_size,
        chunk_index=config.chunk_index,
    )
    seed_sha = _sha256_text(seed_text)
    task = build_task(
        seed_path,
        seed_sha,
        config.prompt_class,
        chunk_size=config.chunk_size,
        chunk_index=config.chunk_index,
        chunk_label=chunk_label,
    )
    system, prompt = build_prompt(
        inlet_text=inlet_text,
        seed_text=seed_text,
        seed_path=seed_path,
        prompt_class=config.prompt_class,
        max_seed_chars=config.max_seed_chars,
    )
    if config.dry_run:
        return ChewResult(True, False, "dry-run", None, None, None, None, None, None, None, "not_run", "dry run", task.id)

    # Phase 1 route witness: stable per-chew decision id, emitted in every
    # exit branch so the routing chain is auditable end-to-end.
    decision_id = uuid.uuid4().hex

    seam = seam or TelicSeam(path=config.ontology_path)
    gatekeeper = gatekeeper or TelosGatekeeper()
    resolved_provider = None
    provider_config = None
    if provider is None:
        provider_config = resolve_provider_config(config)
        resolved_provider = create_runtime_provider(provider_config)
        provider = resolved_provider
        provider_label = f"{provider_config.provider.value}:{provider_config.default_model or config.model or 'default'}"
    provider_label = provider_label or "injected-provider"
    assert provider is not None

    agent_id = f"resident-inquiry:{provider_label}"
    proposal_id = seam.record_dispatch(task, agent_id, topology="manual")
    gate_result = gatekeeper.check(
        action=f"read-only inquiry chew for {seed_path}",
        content=(
            f"seed_sha256={seed_sha}; seed_path={seed_path}; no repo mutation. "
            "Mechanistic frame: provider mechanism and architecture are wrapped "
            "by TelicSeam records. "
            "Phenomenological frame: witness and recognition claims are treated "
            "as uncertain inquiry outputs, not doctrine. Systems frame: feedback "
            "returns through Outcome, ValueEvent, Contribution, and witness JSONL."
        ),
        tool_name="inquiry_substrate_chew",
        trust_mode="external_strict",
        think_phase="before_complete",
        reflection=(
            "Risk: the provider output may overclaim or perform the register. "
            "Test: the run must record proposal, gate, outcome, value, contribution, "
            "and witness artifacts before any repo edit can cite it. Rollback: the "
            "chew artifact is additive and repo docs remain unchanged. Unknown: one "
            "provider is not enough for substrate-confirmed convergence evidence."
        ),
    )
    gate_decision_id = seam.record_gate_decision(proposal_id, gate_result)
    blocked = gate_result.decision == GateDecision.BLOCK or (
        config.block_on_review and gate_result.decision == GateDecision.REVIEW
    )
    route_provider_type = (
        provider_config.provider
        if provider_config is not None
        else config.provider_type
    )
    model = config.model or getattr(provider_config, "default_model", None) or "default"
    if blocked:
        failure_class = (
            FAILURE_CLASS_GATE_BLOCK
            if gate_result.decision == GateDecision.BLOCK
            else FAILURE_CLASS_GATE_REVIEW
        )
        outcome_id = seam.record_outcome(
            task,
            agent_id,
            success=False,
            error=f"{failure_class}: {gate_result.reason}",
            fitness_score=0.0,
        )
        result = _blocked_result(
            task=task,
            provider_label=provider_label,
            proposal_id=proposal_id,
            gate_decision_id=gate_decision_id,
            outcome_id=outcome_id,
            decision=gate_result.decision.value,
            reason=gate_result.reason,
            witness_path=config.witness_path,
            failure_class=failure_class,
            model=model,
        )
        append_witness(
            witness_path=config.witness_path,
            result=result,
            seed_path=seed_path,
            seed_sha256=seed_sha,
            prompt_class=config.prompt_class,
            chunk_size=config.chunk_size,
            chunk_index=config.chunk_index,
            chunk_label=chunk_label,
        )
        await _emit_chew_route_witness(
            decision_id=decision_id,
            config=config,
            provider_type=route_provider_type,
            model=model,
            failure_class=failure_class,
            duration_ms=0.0,
            error_detail=gate_result.reason,
            task_id=task.id,
        )
        return result

    if config.probe and provider_config is not None:
        probe_ok, probe_reason = await probe_runtime_provider(
            provider_config,
            timeout_seconds=config.probe_timeout_seconds,
        )
        if not probe_ok:
            await _close_provider(resolved_provider)
            error = f"{FAILURE_CLASS_PROBE_FAILED}: {probe_reason}"
            outcome_id = seam.record_outcome(
                task,
                agent_id,
                success=False,
                error=error,
                duration_ms=0.0,
                fitness_score=0.0,
            )
            result = ChewResult(
                success=False,
                blocked=False,
                provider_label=provider_label,
                output_path=None,
                witness_path=config.witness_path,
                proposal_id=proposal_id,
                gate_decision_id=gate_decision_id,
                outcome_id=outcome_id,
                value_event_id=None,
                contribution_id=None,
                gate_decision=gate_result.decision.value,
                gate_reason=gate_result.reason,
                task_id=task.id,
                error=error,
                failure_class=FAILURE_CLASS_PROBE_FAILED,
                model=model,
            )
            print(
                f"[inquiry_substrate_chew] probe failed for {provider_label}: "
                f"{probe_reason}",
                file=sys.stderr,
            )
            append_witness(
                witness_path=config.witness_path,
                result=result,
                seed_path=seed_path,
                seed_sha256=seed_sha,
                prompt_class=config.prompt_class,
                chunk_size=config.chunk_size,
                chunk_index=config.chunk_index,
                chunk_label=chunk_label,
            )
            await _emit_chew_route_witness(
                decision_id=decision_id,
                config=config,
                provider_type=route_provider_type,
                model=model,
                failure_class=FAILURE_CLASS_PROBE_FAILED,
                duration_ms=0.0,
                error_detail=f"probe_failed: {probe_reason}",
                task_id=task.id,
            )
            return result

    started = time.monotonic()
    response_text = ""
    response_obj: LLMResponse | None = None
    error = ""
    success = False
    failure_class = FAILURE_CLASS_OK
    try:
        reasoning_effort = _resolve_reasoning_effort(model, config.reasoning_effort)
        response_obj = await _call_provider(
            provider,
            model=model,
            system=system,
            prompt=prompt,
            max_tokens=config.max_tokens,
            timeout_seconds=config.timeout_seconds,
            reasoning_effort=reasoning_effort,
        )
        response_text = response_obj.content.strip()
        success = bool(response_text)
        if not success:
            failure_class = FAILURE_CLASS_EMPTY_CONTENT
    except asyncio.TimeoutError as exc:
        error = f"{FAILURE_CLASS_TIMEOUT}: TimeoutError after {config.timeout_seconds}s"
        failure_class = FAILURE_CLASS_TIMEOUT
    except Exception as exc:  # noqa: BLE001
        error = f"{FAILURE_CLASS_PROVIDER_EXCEPTION}: {type(exc).__name__}: {exc}"
        failure_class = FAILURE_CLASS_PROVIDER_EXCEPTION
    finally:
        await _close_provider(resolved_provider)

    duration_ms = (time.monotonic() - started) * 1000.0
    stop_reason = ""
    usage: dict[str, int] = {}
    response_model = ""
    if response_obj is not None:
        stop_reason = response_obj.stop_reason or ""
        usage = dict(response_obj.usage or {})
        response_model = response_obj.model or ""

    if failure_class == FAILURE_CLASS_EMPTY_CONTENT and not error:
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        error = (
            f"{FAILURE_CLASS_EMPTY_CONTENT}: stop_reason={stop_reason or 'unknown'}; "
            f"completion_tokens={completion_tokens}; prompt_tokens={prompt_tokens}; "
            f"visible=0"
        )
        hint = ""
        if (model or "").strip().lower().startswith("gpt-5"):
            hint = (
                "  hint: gpt-5 reasoning may have consumed max_completion_tokens; "
                "raise --max-tokens (>=4096) or pass --reasoning-effort low"
            )
        print(
            f"[inquiry_substrate_chew] empty content from {provider_label} "
            f"({response_model or model}): stop_reason={stop_reason or 'unknown'} "
            f"completion_tokens={completion_tokens}{hint}",
            file=sys.stderr,
        )

    outcome_id = seam.record_outcome(
        task,
        agent_id,
        success=success,
        result_summary=response_text[:500],
        error=error,
        duration_ms=duration_ms,
        fitness_score=0.5 if success else 0.0,
    )
    ids = {
        "proposal_id": proposal_id,
        "gate_decision_id": gate_decision_id,
        "outcome_id": outcome_id,
        "prompt_class": config.prompt_class,
    }
    output_path = None
    artifact_sha = ""
    if success:
        output_path, artifact_sha = _write_artifact(
            output_dir=config.output_dir.expanduser(),
            seed_path=seed_path,
            provider_label=provider_label,
            response_text=response_text,
            task=task,
            ids=ids,
        )
    value_event_id = seam.record_value_event(outcome_id, task, agent_id, result_text=response_text, success=success, duration_ms=duration_ms) if outcome_id else None
    value_obj = seam.registry.get_object(value_event_id) if value_event_id else None
    raw_value = value_obj.properties.get("composite_value", 0.0) if value_obj else 0.0
    composite_value = float(raw_value) if isinstance(raw_value, (int, float)) else 0.0
    contribution_id = (
        seam.record_contribution(value_event_id, agent_id, composite_value=composite_value, task_type="inquiry_chew")
        if value_event_id else None
    )
    result = ChewResult(
        success=success,
        blocked=False,
        provider_label=provider_label,
        output_path=output_path,
        witness_path=config.witness_path,
        proposal_id=proposal_id,
        gate_decision_id=gate_decision_id,
        outcome_id=outcome_id,
        value_event_id=value_event_id,
        contribution_id=contribution_id,
        gate_decision=gate_result.decision.value,
        gate_reason=gate_result.reason,
        task_id=task.id,
        artifact_sha256=artifact_sha,
        error=error,
        failure_class=failure_class,
        model=response_model or model,
        stop_reason=stop_reason,
        usage=usage,
        duration_ms=duration_ms,
    )
    append_witness(
        witness_path=config.witness_path,
        result=result,
        seed_path=seed_path,
        seed_sha256=seed_sha,
        prompt_class=config.prompt_class,
        chunk_size=config.chunk_size,
        chunk_index=config.chunk_index,
        chunk_label=chunk_label,
    )
    await _emit_chew_route_witness(
        decision_id=decision_id,
        config=config,
        provider_type=route_provider_type,
        model=response_model or model,
        failure_class=failure_class,
        duration_ms=duration_ms,
        response_obj=response_obj,
        error_detail=error,
        task_id=task.id,
    )
    return result
