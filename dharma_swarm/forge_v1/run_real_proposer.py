"""Live model proposer for Forge real SWE-bench runs."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

from dharma_swarm.forge_v1.providers import PoolCompletion
from dharma_swarm.forge_v1.run_real_patch import (
    apply_edit_blocks,
    build_repair_prompt,
    compute_unified_diff,
    parse_edit_blocks,
    parse_full_files,
)


@dataclass
class Proposal:
    model: str
    patch: str
    tokens: int
    error: str | None = None
    # Diagnostics so a failed proposal is never opaque to the research loop.
    raw_text: str = ""           # the model's full raw response
    stop_reason: str | None = None  # 'stop' | 'length'(truncated) | provider-specific
    prompt_chars: int = 0
    n_edit_blocks: int = 0


# SEARCH/REPLACE output is small (just the changed lines), so the cap can be
# modest — but Gemini still spends "thinking" tokens against it, so keep headroom.
DIFF_MAX_TOKENS = 16384


class SweBenchProposer:
    """Wraps a live provider to propose a fix for a SWE-bench instance. The model
    returns compact SEARCH/REPLACE edits; WE apply them to the real base content
    by exact string match and compute a guaranteed-applicable unified diff with
    difflib. The diff is what swebench grades. (Full-file `path=` blocks are a
    back-compat fallback if a model ignores the edit format.)

    Overridable temperature supports the single-family decorrelation stand-in. A
    proposer NEVER raises into the arm: a provider error (503, rate-limit, or a
    per-call timeout on a stalled provider) is captured and returned as an errored
    Proposal so one transient failure cannot kill a multi-hour run."""

    def __init__(self, model_id: str, temperature: float = 0.2, max_tokens: int = DIFF_MAX_TOKENS,
                 timeout_s: int | None = None, continue_rounds: int = 3):
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        # MODEL_CALL_TIMEOUT_S is defined below this class; resolve at call time.
        self._completion = _DiffCompletion(
            model_id, temperature, max_tokens,
            timeout_s=timeout_s if timeout_s is not None else MODEL_CALL_TIMEOUT_S,
            continue_rounds=continue_rounds,
        )

    def propose(self, instance: dict, file_context: dict[str, str],
                prompt_context: dict[str, str] | None = None) -> Proposal:
        # `prompt_context` is what the MODEL sees (optionally a windowed slice for
        # small-context endpoints that hang on the full file). Edits are always
        # applied against the FULL `file_context` — the window is a verbatim
        # substring of it, so a SEARCH block from the window still matches.
        prompt = build_repair_prompt(instance, prompt_context or file_context)
        try:
            text, tokens = self._completion.complete(prompt)
        except Exception as e:  # transient/timeout provider error -> errored sample, not crash
            return Proposal(model=self.model_id, patch="", tokens=0,
                            error=f"{type(e).__name__}: {e}",
                            prompt_chars=len(prompt))

        stop_reason = getattr(self._completion, "last_stop_reason", None)

        def _mk(patch: str, error: str | None, n_blocks: int) -> Proposal:
            return Proposal(model=self.model_id, patch=patch, tokens=tokens, error=error,
                            raw_text=text, stop_reason=stop_reason,
                            prompt_chars=len(prompt), n_edit_blocks=n_blocks)

        # Primary path: SEARCH/REPLACE edit blocks applied to base content.
        edits = parse_edit_blocks(text)
        if edits:
            new_files, err = apply_edit_blocks(file_context, edits)
            if err:
                return _mk("", err, len(edits))
        else:
            # Fallback: model returned whole `path=` files instead.
            new_files = parse_full_files(text)
            if not new_files:
                # Distinguish a truncated response (model ran out of output budget
                # mid-block) from a genuine format miss — they need different fixes.
                if (stop_reason or "").lower() in ("length", "max_tokens", "max_output_tokens"):
                    err = (f"truncated at max_tokens (stop_reason={stop_reason}); "
                           f"no complete edit block in {len(text)} chars")
                elif not text.strip():
                    err = f"empty response (stop_reason={stop_reason})"
                else:
                    err = "no SEARCH/REPLACE or path= block in response"
                return _mk("", err, 0)

        patch = compute_unified_diff(file_context, new_files)
        if not patch.strip():
            return _mk("", "edits produced no change vs base", len(edits))
        return _mk(patch, None, len(edits))


# Hard wall-clock cap on ONE live model call. Without it, a stalled provider
# (observed: GLM-5.1 on Ollama Cloud leaving the SSL socket in CLOSE_WAIT with the
# process at 0% CPU) hangs the whole run forever — provider.complete has no
# client-side timeout. asyncio.wait_for turns a hang into a TimeoutError that the
# proposer catches and records as an errored (unresolved) sample.
MODEL_CALL_TIMEOUT_S = 600

# Rate-limit (HTTP 429) repair: free/throttled tiers (e.g. gemini-2.5-flash free
# tier ~RPM cap) return 429 with a "retry in Ns" / retryDelay hint. Rather than
# burning the sample, wait the hinted delay (capped) and retry a few times.
_RATE_LIMIT_RETRIES = 3
_RATE_LIMIT_MAX_WAIT_S = 65

# Quota/billing exhaustion looks like a 429 to most SDKs but no amount of
# waiting fixes it — retrying just burns the sample budget.
_NON_RETRYABLE_QUOTA_MARKERS = (
    "insufficient balance",
    "no resource package",
    "please recharge",
    "insufficient_quota",
    "insufficient quota",
    "exceeded your current quota",
    "credit balance",
    "billing hard limit",
    "payment required",
    "insufficient credits",
    "quota_exhausted",
    "billing_exhausted",
    "error code: 402",
    "http error 402",
)


def _is_non_retryable_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _NON_RETRYABLE_QUOTA_MARKERS)


def _rate_limit_wait_s(exc: Exception) -> float | None:
    """If `exc` is a rate-limit (429) error, return how long to wait before retry
    (seconds), parsed from the provider's hint; else None. Looks for 429 /
    RESOURCE_EXHAUSTED and a 'retry in Ns' or retryDelay '...s' figure."""
    msg = str(exc)
    if _is_non_retryable_quota_error(exc):
        return None
    is_429 = (
        "429" in msg
        or "RESOURCE_EXHAUSTED" in msg
        or "rate limit" in msg.lower()
        or "rate-limit" in msg.lower()
        or type(exc).__name__ in ("RateLimitError", "ResourceExhausted")
    )
    if not is_429:
        return None
    m = re.search(r"retry in ([\d.]+)\s*s", msg) or re.search(r"retryDelay'?:?\s*'?([\d.]+)s", msg)
    delay = float(m.group(1)) if m else 20.0
    return min(delay + 1.5, _RATE_LIMIT_MAX_WAIT_S)


class _DiffCompletion(PoolCompletion):
    """PoolCompletion with overridable temperature + max_tokens (long diffs) and
    a hard per-call timeout so a hung provider can't stall the whole run."""

    def __init__(self, model_id: str, temperature: float, max_tokens: int,
                 timeout_s: int = MODEL_CALL_TIMEOUT_S, continue_rounds: int = 3):
        super().__init__(model_id)
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_s = timeout_s
        # How many extra "finish the block" turns to grant when the first
        # response yields no usable edit block. This is the per-model wall-repair
        # for reasoning families (GLM, kimi): they truncate at max_tokens OR
        # narrate the fix and end the turn with "I'll now produce the edit." and
        # never emit it. Either way we push the SAME conversation to emit ONLY
        # the block. Tokens accumulate honestly toward the budget.
        self._continue_rounds = continue_rounds
        # Last-call diagnostics, read back by the proposer so a non-parsing
        # response is inspectable (truncation vs format-miss vs empty).
        self.last_stop_reason: str | None = None
        self.last_raw: str = ""
        self.last_rounds: int = 0

    def complete(self, prompt: str):
        import asyncio

        from dharma_swarm.models import LLMRequest
        from dharma_swarm.forge_v1.providers import _usage_tokens

        messages = [{"role": "user", "content": prompt}]
        accumulated = ""
        total_tokens = 0
        last_stop: str | None = None

        for rnd in range(self._continue_rounds + 1):
            request = LLMRequest(
                model=self._wire_model,
                messages=list(messages),
                max_tokens=self._max_tokens,
                temperature=self._temperature,
            )

            response = self._complete_once(request)
            text = response.content or ""
            last_stop = getattr(response, "stop_reason", None)
            total_tokens += _usage_tokens(response.usage)
            accumulated += (("\n" if accumulated else "") + text)
            self.last_rounds = rnd + 1

            # Stop the moment the accumulated transcript yields a usable block.
            if parse_edit_blocks(accumulated) or parse_full_files(accumulated):
                break
            if rnd >= self._continue_rounds:
                break

            truncated = (last_stop or "").lower() in ("length", "max_tokens", "max_output_tokens")
            if truncated:
                nudge = (
                    "Your previous message was cut off before the edit block was "
                    "complete. Continue EXACTLY from where you stopped and finish the "
                    "SEARCH/REPLACE block(s). Output only the remaining characters, "
                    "nothing else — do not restart or repeat."
                )
            else:
                nudge = (
                    "You explained the fix but did NOT output an edit block. Now output "
                    "ONLY the SEARCH/REPLACE block(s), in exactly this format and nothing "
                    "else (no prose, no code fences, no 'I will'):\n"
                    "<<<<<<< SEARCH path=<file path>\n<exact original lines, verbatim>\n"
                    "=======\n<replacement lines>\n>>>>>>> REPLACE"
                )
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": nudge})

        self.last_stop_reason = last_stop
        self.last_raw = accumulated
        return accumulated, total_tokens

    def _complete_once(self, request):
        """One provider call with hard timeout + 429-aware retry. On a rate-limit
        error, sleep the provider's hinted delay (capped) and retry a few times so
        a free-tier RPM throttle costs latency, not the whole sample."""
        import asyncio
        import time as _time

        async def _call():
            return await asyncio.wait_for(
                self._provider.complete(request), timeout=self._timeout_s
            )

        last_exc: Exception | None = None
        for attempt in range(_RATE_LIMIT_RETRIES + 1):
            try:
                return asyncio.run(_call())
            except Exception as e:
                wait = _rate_limit_wait_s(e)
                if wait is None or attempt >= _RATE_LIMIT_RETRIES:
                    raise
                last_exc = e
                _time.sleep(wait)
        if last_exc:
            raise last_exc
