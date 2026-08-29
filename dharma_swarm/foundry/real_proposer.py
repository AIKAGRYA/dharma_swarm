"""The real proposer — an LLM turns a target file into a candidate diff.

The second missing muscle from the readiness audit. Given a pinned target and
an objective, build a prompt carrying the CURRENT contents of the evolve file,
call a live model lane, extract a unified diff from the reply, and verify it
applies cleanly (``git apply --check``) — with one retry that feeds the
failure reason back to the model. A proposal that still fails returns a
deliberately empty-diff candidate, which the ``no_op_diff`` tripwire zeroes:
malformed output costs the model its turn, never the loop its integrity.

The roster's :class:`~dharma_swarm.foundry.army.ArmyModel` IDs are logical
mutation roles. Actual execution uses the first admissible pinned provider
route and records the exact model, endpoint, tariff window, and logical origin
separately. No logical roster ID is presented as provider routing evidence.
"""

from __future__ import annotations

import re
import subprocess
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from dharma_swarm.foundry.army import ArmyModel
from dharma_swarm.foundry.evaluator import Candidate
from dharma_swarm.foundry.live import (
    ProviderExhausted,
    ProviderPool,
    _typed_provider_error,
    conservative_total_tokens,
    estimate_cost_usd,
)
from dharma_swarm.foundry.loop import ProposeFn
from dharma_swarm.foundry.tripwires import has_effective_change, validate_diff_paths

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
                  runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                  *, expected_path: str | None = None) -> str | None:
    """Verify the diff applies (same appliers as the evaluator: git, then
    fuzz-tolerant patch). None on success, reason on failure."""
    from dharma_swarm.foundry.oracle_evaluator import apply_diff

    safety = validate_diff_paths(
        diff,
        expected_path=expected_path,
        allowed_paths=[expected_path] if expected_path else None,
        tree_root=Path(tree),
    )
    if not safety.clean:
        return f"{safety.category}: {safety.detail}"
    return apply_diff(
        tree,
        diff,
        runner,
        check_only=True,
        expected_path=expected_path,
        allowed_paths=[expected_path] if expected_path else None,
    )


def _materialize_applied_source(
    tree: Path,
    evolve_file: str,
    diff: str,
    runner: Callable[..., subprocess.CompletedProcess],
) -> str:
    """Apply one already path-validated diff to a private one-file tree."""
    from dharma_swarm.foundry.oracle_evaluator import apply_diff

    with tempfile.TemporaryDirectory(prefix="foundry_static_source_") as temp:
        root = Path(temp)
        target = root / evolve_file
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(tree) / evolve_file, target)
        failure = apply_diff(
            root,
            diff,
            runner,
            expected_path=evolve_file,
            allowed_paths=[evolve_file],
        )
        if failure is not None:
            raise ValueError(f"static materialization failed: {failure}")
        return target.read_text(encoding="utf-8")


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
    provider_circuit_state: Path | None = None,
    provider_budget_cap_usd: float | None = None,
) -> ProposeFn:
    """Build a :data:`ProposeFn` that asks a live model for a verified-to-apply diff.

    ``caller(model_hint, prompt) -> reply`` is injectable for hermetic tests;
    the default resolves the first live provider lane once and reuses it.
    """
    pinned_root = Path(pinned_root)
    resolved: dict[str, Any] = {}
    usage = {
        "tokens": 0,
        "calls": 0,
        "failed_calls": 0,
        "tokens_by_provider": {},
        "provider_attempts": [],
        "provider_route_provenance": {},
        "usage_verified": True,
    }
    pool = (
        ProviderPool(
            env=env,
            circuit_state_path=provider_circuit_state,
            budget_cap_usd=provider_budget_cap_usd,
        )
        if caller is None else None
    )
    if pool is not None:
        usage["provider_route_provenance"] = dict(pool.route_provenance)

    def _default_caller(model_hint: str, prompt: str) -> str:
        assert pool is not None
        before = dict(pool.tokens_by_provider)
        attempts_before = len(pool.attempt_history)
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
            usage["provider_attempts"].extend(
                attempt.to_dict()
                for attempt in pool.attempt_history[attempts_before:]
            )
            usage["usage_verified"] = pool.usage_verified
            resolved["last_attempts"] = [
                attempt.to_dict()
                for attempt in pool.attempt_history[attempts_before:]
            ]
        resolved["provider"] = response.provider
        resolved["model"] = response.model
        usage["calls"] += 1
        return response.content

    call = caller or _default_caller

    def propose(model: ArmyModel, parent_id: str | None, seed: int) -> Candidate:
        contents = (pinned_root / evolve_file).read_text(encoding="utf-8")

        def candidate_id(diff_text: str, status: str) -> str:
            identity = {
                "target_id": target_id,
                "evolve_file": evolve_file,
                "base_sha256": hashlib.sha256(contents.encode("utf-8")).hexdigest(),
                "diff_sha256": hashlib.sha256(diff_text.encode("utf-8")).hexdigest(),
                "status": status,
                "origin_model": model.id,
            }
            digest = hashlib.sha256(json.dumps(
                identity, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")).hexdigest()
            return f"cand-{digest}"
        feedback = ""
        diff = ""
        candidate_attempts: list[dict] = []
        for _attempt in range(2):  # one retry with failure feedback
            prompt = PROMPT_TEMPLATE.format(
                objective=objective, rel_path=evolve_file, lang=lang,
                file_contents=contents, feedback=feedback,
            )
            try:
                reply = call(model.id, prompt)
                candidate_attempts.extend(resolved.get("last_attempts", []))
            except ProviderExhausted as exc:
                candidate_attempts.extend(resolved.get("last_attempts", []))
                usage["failed_calls"] += 1
                if pool is None:
                    usage["tokens"] += exc.billable_tokens
                    by_provider = usage["tokens_by_provider"]
                    for failure in exc.failures:
                        by_provider[failure.provider] = (
                            by_provider.get(failure.provider, 0)
                            + failure.billable_tokens
                        )
                return Candidate(candidate_id=candidate_id("", "provider_error"), target_id=target_id,
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
                                     "provider_attempts": tuple(
                                         candidate_attempts
                                     ),
                                     "provider_route_provenance": dict(
                                         usage["provider_route_provenance"]
                                     ),
                                     "usage_verified": pool.usage_verified if pool else False,
                                 })
            except Exception as exc:  # injected callers still become typed evidence
                usage["failed_calls"] += 1
                failure = _typed_provider_error(
                    "injected",
                    exc,
                    conservative_tokens=conservative_total_tokens(
                        prompt, PROPOSAL_MAX_TOKENS
                    ),
                )
                usage["usage_verified"] = (
                    usage["usage_verified"] and failure.usage_verified
                )
                usage["tokens"] += failure.billable_tokens
                by_provider = usage["tokens_by_provider"]
                by_provider[failure.provider] = (
                    by_provider.get(failure.provider, 0) + failure.billable_tokens
                )
                return Candidate(candidate_id=candidate_id("", "provider_error"), target_id=target_id,
                                 diff="", origin_model=model.id, parent_id=parent_id,
                                 metadata={
                                     "proposal_status": "provider_error",
                                     "provider_error": failure.category,
                                     "provider_failures": (
                                         f"{failure.provider}:{failure.category}",
                                     ),
                                     "billable_tokens": failure.billable_tokens,
                                     "budget_chargeable": failure.billable_tokens > 0,
                                     "provider_attempts": ({
                                         "provider": failure.provider,
                                         "category": failure.category,
                                         "tokens": failure.billable_tokens,
                                         "usage_basis": (
                                            "conservative_total_liability"
                                             if failure.billable_tokens
                                             else "verified_zero_pre_rejection"
                                         ),
                                         "prompt_bytes": len(
                                             prompt.encode("utf-8")
                                         ),
                                         "liability_tokens": (
                                             failure.billable_tokens
                                         ),
                                         "liability_cost_usd": (
                                             estimate_cost_usd(
                                                 failure.provider,
                                                 failure.billable_tokens,
                                             )
                                         ),
                                     },),
                                     "usage_verified": failure.usage_verified,
                                 })
            if not reply.strip():
                failure = "empty_response: provider returned no content"
                diff = ""
            else:
                diff = extract_unified_diff(reply)
                failure = (
                    "extraction_failure: no unified diff found in provider response"
                    if not diff
                    else (
                        "no_op_diff: unified diff has no effective content change"
                        if not has_effective_change(diff)
                        else check_applies(
                        pinned_root, diff, runner, expected_path=evolve_file
                        )
                    )
                )
            if failure is None:
                try:
                    applied_source = _materialize_applied_source(
                        pinned_root, evolve_file, diff, runner
                    )
                except (OSError, ValueError) as exc:
                    failure = f"apply_failure: {type(exc).__name__}"
                    feedback = (
                        f"\nYOUR PREVIOUS DIFF FAILED TO APPLY: {failure}\n"
                        "Re-emit a corrected unified diff with accurate context lines."
                    )
                    continue
                return Candidate(
                    candidate_id=candidate_id(diff, "ok"), target_id=target_id,
                    diff=diff, origin_model=model.id, parent_id=parent_id,
                    metadata={"routed_model": resolved.get("model", "injected"),
                              "provider": resolved.get("provider", "injected"),
                              "proposal_status": "ok",
                              "budget_chargeable": True,
                              "provider_attempts": tuple(
                                  candidate_attempts
                              ),
                              "provider_route_provenance": dict(
                                  usage["provider_route_provenance"]
                              ),
                              "applied_source": applied_source,
                              "usage_verified": bool(pool and pool.usage_verified)},
                )
            feedback = (f"\nYOUR PREVIOUS DIFF FAILED TO APPLY: {failure}\n"
                        "Re-emit a corrected unified diff with accurate context lines.")
        # Both attempts failed: empty diff -> no_op_diff tripwire zeroes it.
        category = "apply_failure"
        if failure:
            prefix = failure.split(":", 1)[0]
            if prefix in {
                "empty_response", "extraction_failure", "malformed_diff",
                "unsafe_diff_path", "mismatched_diff_headers", "symlink_escape",
                "out_of_scope_diff",
                "no_op_diff",
            }:
                category = prefix
        return Candidate(candidate_id=candidate_id("", category), target_id=target_id,
                         diff="", origin_model=model.id, parent_id=parent_id,
                         metadata={"proposer_failed": "diff rejected after bounded retry",
                                   "proposal_status": category,
                                   "proposal_error": failure or category,
                                   "provider_attempts": tuple(candidate_attempts),
                                   "provider_route_provenance": dict(
                                       usage["provider_route_provenance"]
                                   ),
                                   "usage_verified": bool(pool and pool.usage_verified),
                                   "budget_chargeable": True})

    # Honest spend accounting: the campaign CLI reads these after the run and
    # prices tokens at the provider's upper-bound rate (same doctrine as the
    # heartbeat lane — real usage is never invisible to the budget).
    propose.usage = usage  # type: ignore[attr-defined]
    propose.resolved = resolved  # type: ignore[attr-defined]
    return propose
