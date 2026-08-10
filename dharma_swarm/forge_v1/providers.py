"""L1 — the real-model adapter. Behind the SAME propose(task, sample_idx) ->
Candidate interface the stubs use, so swapping a stub for a real frontier model
is a one-line change in a SwarmConfig (use LiveModel instead of QualityModel).

LiveModel: build a repair prompt from the task's buggy file -> call a Completion
backend -> parse the patched file out of the response -> Candidate(patch, tokens).

Backends:
- FakeCompletion: returns canned text (tests the prompt->parse plumbing offline).
- PoolCompletion: the LIVE swap-in (gpt-5.5 / opus-4.8 via dharma_swarm's pool).
  It raises a clear error rather than ever silently faking a live call — wire its
  body to runtime_provider when going live (that's when it starts costing tokens).
"""
from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass

from .harness import Candidate, RepairTask

_PATCH_RE = re.compile(r"```(?:python)?\n(.*?)```", re.DOTALL)


def _provider_for_model(model_id: str):
    """Resolve a live dharma_swarm provider + concrete model id for `model_id`.

    Returns (provider, model_id). Routes by the model-id prefix to the right
    ProviderType, then goes through the canonical runtime_provider path
    (resolve_runtime_provider_config -> create_runtime_provider). Keeping the
    routing here means PoolCompletion.__init__ stays a one-liner.
    """
    from dharma_swarm.api_keys import bootstrap_runtime_env
    from dharma_swarm.model_pool import MODEL_POWER_FLOOR, entry_for_model_id
    from dharma_swarm.runtime_provider import (
        ProviderType,
        create_runtime_provider,
        resolve_runtime_provider_config,
    )

    # Make keys from ~/.dharma/agent_keys.env visible (idempotent, no overwrite).
    bootstrap_runtime_env()

    mid = (model_id or "").strip().lower()
    pool_entry = entry_for_model_id(model_id)
    if pool_entry is not None:
        if pool_entry.below_floor and os.environ.get("DHARMA_ALLOW_SUB_FLOOR_MODEL") != "1":
            raise RuntimeError(
                f"model {model_id!r} is below the {MODEL_POWER_FLOOR} floor "
                "and is allowed only with DHARMA_ALLOW_SUB_FLOOR_MODEL=1 for "
                "explicit grunt work"
            )
        exact_route = next((r for r in pool_entry.routes if r.model_id == model_id), None)
        provider_type = (exact_route or pool_entry.routes[0]).provider
    elif mid.startswith("gpt") or mid.startswith("o1") or mid.startswith("o3"):
        provider_type = ProviderType.OPENAI
    elif mid.startswith("claude") or mid.startswith("opus") or mid.startswith("sonnet"):
        provider_type = ProviderType.ANTHROPIC
    elif mid.startswith("gemini"):
        provider_type = ProviderType.GOOGLE_AI
    elif mid.startswith("moonshot:"):
        # RSI-LAB travel route: force the Moonshot OpenAI-compatible lane
        # (api.moonshot.ai) with the accessible id after the prefix, e.g.
        # "moonshot:kimi-k2.7-code". The default kimi-* ids route to Ollama
        # Cloud / kimi-for-coding which are not reachable/entitled here.
        provider_type = ProviderType.MOONSHOT
        model_id = model_id.split(":", 1)[1]
        mid = model_id.lower()
    elif mid in {"kimi-for-coding", "kimi-code"} or mid.startswith("kimi_code/") or mid.startswith("kimi-code/"):
        provider_type = ProviderType.KIMI_CODE
    elif mid.startswith("glm-5.2") or mid.startswith("zai/") or mid.startswith("z-ai/"):
        provider_type = ProviderType.ZHIPU
    elif mid.endswith(":cloud") or mid.startswith("glm") or mid.startswith("kimi"):
        provider_type = ProviderType.OLLAMA  # Ollama Cloud frontier chain
    elif mid.startswith("meta/") or mid.startswith("nvidia/") or "llama" in mid:
        provider_type = ProviderType.NVIDIA_NIM
    elif "/" in mid:  # e.g. moonshotai/kimi-k2.5 -> OpenRouter
        provider_type = ProviderType.OPENROUTER
    else:
        provider_type = ProviderType.OPENAI

    # Pass model only when the caller named a concrete id; otherwise let the
    # provider config supply its canonical default (e.g. gemini-2.5-flash).
    pass_model = model_id if mid not in ("", "default") else None
    model_timeout = int(os.environ.get("FORGE_MODEL_CALL_TIMEOUT_S", "240"))
    config = resolve_runtime_provider_config(
        provider_type,
        model=pass_model,
        timeout_seconds=model_timeout,
    )
    if not config.available:
        raise RuntimeError(
            f"PoolCompletion(model={model_id}) resolved provider "
            f"{provider_type.value} but no live key/config is available "
            "(run `dkeys` to confirm the key)."
        )
    provider = create_runtime_provider(config)
    # config.default_model carries the resolved concrete id (e.g. 'gpt-5').
    return provider, (config.default_model or model_id)


def _usage_tokens(usage: dict) -> int:
    """Sum prompt+completion tokens across both naming conventions.

    OpenAI-family providers report prompt_tokens/completion_tokens; Anthropic
    reports input_tokens/output_tokens. Total over whichever pair is present.
    """
    if not usage:
        return 0
    inp = usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
    out = usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
    total = inp + out
    if total == 0:  # last resort: a provider that only reports total
        total = usage.get("total_tokens", 0) or 0
    return int(total)


async def _complete_and_close(
    provider: object,
    request: object,
    *,
    timeout_s: float | None = None,
):
    """Complete one Forge call and close the provider on the same event loop.

    Forge exposes synchronous adapters over asynchronous providers.  Closing a
    cached HTTP client after ``asyncio.run`` returns leaves its transport bound
    to an already-closed loop; the SDK finalizer then emits ``Event loop is
    closed`` during a later call.  Keep completion, timeout cancellation, and
    cleanup inside one owned loop instead.
    """
    primary_error: BaseException | None = None
    try:
        completion = provider.complete(request)
        if timeout_s is None:
            return await completion
        return await asyncio.wait_for(completion, timeout=timeout_s)
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            try:
                await close()
            except Exception:
                # Preserve the provider/timeout failure when cleanup also fails.
                # A cleanup failure after a successful call remains load-bearing.
                if primary_error is None:
                    raise


class FakeCompletion:
    """Offline backend: cycles through canned responses. complete(prompt) ->
    (text, tokens). Used to validate the prompt-build / patch-parse plumbing
    without any live call."""

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.i = 0

    def complete(self, prompt: str) -> tuple[str, int]:
        text = self.responses[self.i % len(self.responses)]
        self.i += 1
        tokens = max(1, len(prompt) // 4 + len(text) // 4)
        return text, tokens


class PoolCompletion:
    """LIVE backend (the flip). Calls a real frontier model through dharma_swarm's
    canonical provider stack (runtime_provider.resolve/create -> provider.complete).
    This is where real tokens are spent — offline runs use FakeCompletion.

    __init__ resolves the right provider for `model_id` (gpt* -> OpenAI,
    claude/opus/sonnet -> Anthropic, vendor/model -> OpenRouter) and refuses to
    construct if no live key is available, so a live run never silently no-ops.
    complete() is SYNC (the harness interface) but provider.complete is ASYNC, so
    we bridge with asyncio.run.
    """

    def __init__(self, model_id: str = "gpt-5"):
        self.model_id = model_id
        self._provider, self._wire_model = _provider_for_model(model_id)

    def complete(
        self,
        prompt: str,
        *,
        max_total_tokens: int | None = None,
    ) -> tuple[str, int]:
        from dharma_swarm.models import LLMRequest

        max_output_tokens = 2048
        if max_total_tokens is not None:
            if (
                not isinstance(max_total_tokens, int)
                or isinstance(max_total_tokens, bool)
                or max_total_tokens < 1
            ):
                raise ValueError("max_total_tokens must be a positive integer")
            # UTF-8 bytes are a conservative upper bound for ordinary BPE input
            # tokenization. Reserve an additional fixed allowance for chat framing
            # so a mutation is refused *before* dispatch when its declared total
            # ceiling cannot contain both prompt and completion.
            input_upper_bound = len(prompt.encode("utf-8")) + 512
            remaining = max_total_tokens - input_upper_bound
            if remaining < 1:
                raise RuntimeError(
                    "mutation prompt cannot fit inside the declared total-token ceiling"
                )
            max_output_tokens = min(max_output_tokens, remaining)
        request = LLMRequest(
            model=self._wire_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_output_tokens,
            temperature=0.2,
        )
        response = asyncio.run(_complete_and_close(self._provider, request))
        tokens = _usage_tokens(response.usage)
        if max_total_tokens is not None and tokens > max_total_tokens:
            raise RuntimeError("provider usage exceeded the declared total-token ceiling")
        return response.content or "", tokens


@dataclass
class LiveModel:
    """Real-model adapter: prompt -> completion -> parse -> Candidate. Same
    interface as the stubs; drops straight into a SwarmConfig. Single-file tasks."""

    completion: object
    name: str = "live"

    def _filename(self, task: RepairTask) -> str:
        return next(iter(task.files))

    def _prompt(self, task: RepairTask) -> str:
        fn = self._filename(task)
        return (
            f"Fix the bug in `{fn}`. Return ONLY the full corrected file in a "
            f"single python code block.\n\n```python\n{task.files[fn]}```\n"
        )

    def propose(self, task: RepairTask, sample_idx: int) -> Candidate:
        text, tokens = self.completion.complete(self._prompt(task))
        match = _PATCH_RE.search(text or "")
        content = match.group(1) if match else (text or "")
        return Candidate(patch={self._filename(task): content}, tokens=tokens)
