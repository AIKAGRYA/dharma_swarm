"""The real proposer — an LLM turns a target file into a candidate diff.

The second missing muscle from the readiness audit. Given a pinned target and
an objective, build a prompt carrying the CURRENT contents of the evolve file,
call a live model lane, extract a unified diff from the reply, and verify it
applies cleanly (``git apply --check``) — with one retry that feeds the
failure reason back to the model. A proposal that still fails returns a
deliberately empty-diff candidate, which the ``no_op_diff`` tripwire zeroes:
malformed output costs the model its turn, never the loop its integrity.

v1 routing note: the roster's :class:`~dharma_swarm.foundry.army.ArmyModel`
ids are logical; this proposer routes every call through the first live
OpenAI-compatible lane (same provider chain as the heartbeat) and records the
ACTUAL model used in ``Candidate.metadata`` alongside the logical id. Mapping
each roster id to its own route is v2; the receipts stay honest either way.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable

from dharma_swarm.foundry.army import ArmyModel
from dharma_swarm.foundry.evaluator import Candidate
from dharma_swarm.foundry.live import (
    ProviderExhausted,
    ProviderPool,
    _typed_provider_error,
)
from dharma_swarm.foundry.loop import ProposeFn

_DIFF_FENCE_RE = re.compile(r"```(?:diff|patch)?\s*\n(.*?)```", re.DOTALL)
_HUNK_START_RE = re.compile(r"^(--- |\+\+\+ |@@ )", re.MULTILINE)

PROPOSAL_MAX_TOKENS = 2048

PROMPT_TEMPLATE = """You are a code-optimization engine. Improve the file below toward this objective:

OBJECTIVE: {objective}

Rules:
- Reply with ONE unified diff in a ```diff fenced block, nothing else.
- The diff must use exactly these headers: `--- a/{rel_path}` and `+++ b/{rel_path}`.
- Include correct @@ hunk headers with accurate line numbers and 3 lines of context.
- Change ONLY {rel_path}. Keep the change small and focused (one idea per diff).
- The code must remain correct: it will be verified against the target's own test oracle.

CURRENT FILE ({rel_path}):
```{lang}
{file_contents}
```
{feedback}"""


def extract_unified_diff(text: str) -> str:
    """Pull a unified diff out of a model reply (fenced block preferred)."""
    fenced = _DIFF_FENCE_RE.search(text)
    body = fenced.group(1) if fenced else text
    if not _HUNK_START_RE.search(body):
        return ""
    # Trim any prose before the first diff header.
    start = _HUNK_START_RE.search(body)
    return body[start.start():].strip() + "\n"


def check_applies(tree: Path, diff: str,
                  runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> str | None:
    """Verify the diff applies (same appliers as the evaluator: git, then
    fuzz-tolerant patch). None on success, reason on failure."""
    from dharma_swarm.foundry.oracle_evaluator import apply_diff

    if not diff.strip():
        return "no unified diff found in reply"
    return apply_diff(tree, diff, runner, check_only=True)


def real_proposer(
    *,
    target_id: str,
    pinned_root: Path,
    evolve_file: str,
    objective: str,
    lang: str = "python",
    caller: Callable[[str, str], str] | None = None,
    env: dict | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> ProposeFn:
    """Build a :data:`ProposeFn` that asks a live model for a verified-to-apply diff.

    ``caller(model_hint, prompt) -> reply`` is injectable for hermetic tests;
    the default resolves the first live provider lane once and reuses it.
    """
    pinned_root = Path(pinned_root)
    resolved: dict[str, str] = {}
    usage = {"tokens": 0, "calls": 0, "failed_calls": 0, "tokens_by_provider": {}}
    pool = ProviderPool(env=env) if caller is None else None

    def _default_caller(model_hint: str, prompt: str) -> str:
        assert pool is not None
        before = dict(pool.tokens_by_provider)
        try:
            response = pool.call(
                prompt,
                max_tokens=PROPOSAL_MAX_TOKENS,
                temperature=0.7,
                timeout=120.0,
            )
        finally:
            # Include every route attempted, not only the route that finally
            # succeeded. A provider may report billable tokens before failover.
            by_provider = usage["tokens_by_provider"]
            for provider, total in pool.tokens_by_provider.items():
                delta = total - before.get(provider, 0)
                if delta > 0:
                    by_provider[provider] = by_provider.get(provider, 0) + delta
                    usage["tokens"] += delta
        resolved["provider"] = response.provider
        resolved["model"] = response.model
        usage["calls"] += 1
        return response.content

    call = caller or _default_caller

    def propose(model: ArmyModel, parent_id: str | None, seed: int) -> Candidate:
        contents = (pinned_root / evolve_file).read_text(encoding="utf-8")
        feedback = ""
        diff = ""
        for _attempt in range(2):  # one retry with failure feedback
            prompt = PROMPT_TEMPLATE.format(
                objective=objective, rel_path=evolve_file, lang=lang,
                file_contents=contents, feedback=feedback,
            )
            try:
                reply = call(model.id, prompt)
            except ProviderExhausted as exc:
                usage["failed_calls"] += 1
                if pool is None:
                    usage["tokens"] += exc.billable_tokens
                    by_provider = usage["tokens_by_provider"]
                    for failure in exc.failures:
                        by_provider[failure.provider] = (
                            by_provider.get(failure.provider, 0)
                            + failure.billable_tokens
                        )
                return Candidate(candidate_id=f"{model.id}-{seed}", target_id=target_id,
                                 diff="", origin_model=model.id, parent_id=parent_id,
                                 metadata={
                                     "proposal_status": "provider_error",
                                     "provider_error": "routes_exhausted",
                                     "provider_failures": tuple(
                                         f"{failure.provider}:{failure.category}"
                                         for failure in exc.failures
                                     ),
                                     "billable_tokens": exc.billable_tokens,
                                     "budget_chargeable": exc.billable_tokens > 0,
                                 })
            except Exception as exc:  # injected callers still become typed evidence
                usage["failed_calls"] += 1
                failure = _typed_provider_error("injected", exc)
                usage["tokens"] += failure.billable_tokens
                by_provider = usage["tokens_by_provider"]
                by_provider[failure.provider] = (
                    by_provider.get(failure.provider, 0) + failure.billable_tokens
                )
                return Candidate(candidate_id=f"{model.id}-{seed}", target_id=target_id,
                                 diff="", origin_model=model.id, parent_id=parent_id,
                                 metadata={
                                     "proposal_status": "provider_error",
                                     "provider_error": failure.category,
                                     "provider_failures": (
                                         f"{failure.provider}:{failure.category}",
                                     ),
                                     "billable_tokens": failure.billable_tokens,
                                     "budget_chargeable": failure.billable_tokens > 0,
                                 })
            diff = extract_unified_diff(reply)
            failure = check_applies(pinned_root, diff, runner)
            if failure is None:
                return Candidate(
                    candidate_id=f"{model.id}-{seed}", target_id=target_id,
                    diff=diff, origin_model=model.id, parent_id=parent_id,
                    metadata={"routed_model": resolved.get("model", "injected"),
                              "provider": resolved.get("provider", "injected"),
                              "proposal_status": "ok",
                              "budget_chargeable": True},
                )
            feedback = (f"\nYOUR PREVIOUS DIFF FAILED TO APPLY: {failure}\n"
                        "Re-emit a corrected unified diff with accurate context lines.")
        # Both attempts failed: empty diff -> no_op_diff tripwire zeroes it.
        return Candidate(candidate_id=f"{model.id}-{seed}", target_id=target_id,
                         diff="", origin_model=model.id, parent_id=parent_id,
                         metadata={"proposer_failed": "diff did not apply after retry",
                                   "proposal_status": "invalid_diff",
                                   "budget_chargeable": True})

    # Honest spend accounting: the campaign CLI reads these after the run and
    # prices tokens at the provider's upper-bound rate (same doctrine as the
    # heartbeat lane — real usage is never invisible to the budget).
    propose.usage = usage  # type: ignore[attr-defined]
    propose.resolved = resolved  # type: ignore[attr-defined]
    return propose
