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
import tempfile
from pathlib import Path
from typing import Callable

from dharma_swarm.foundry.army import ArmyModel
from dharma_swarm.foundry.evaluator import Candidate
from dharma_swarm.foundry.live import call_chat, choose_model, list_models, pick_provider
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
    """``git apply --check`` against ``tree``. None on success, reason on failure."""
    if not diff.strip():
        return "no unified diff found in reply"
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as fh:
        fh.write(diff if diff.endswith("\n") else diff + "\n")
        patch = fh.name
    try:
        proc = runner(["git", "apply", "--check", "--unsafe-paths",
                       "--directory", str(tree), patch],
                      capture_output=True, text=True, timeout=30)
        if getattr(proc, "returncode", 1) != 0:
            return (getattr(proc, "stderr", "") or "apply --check failed").strip()[:300]
        return None
    except (subprocess.SubprocessError, OSError) as exc:
        return f"apply error: {type(exc).__name__}"
    finally:
        Path(patch).unlink(missing_ok=True)


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
    usage = {"tokens": 0, "calls": 0}

    def _default_caller(model_hint: str, prompt: str) -> str:
        if "model" not in resolved:
            picked = pick_provider(env)
            if picked is None:
                raise RuntimeError("no provider key present for real proposer")
            name, base, key, default_model = picked
            resolved["provider"] = name
            resolved["base"] = base
            resolved["key"] = key
            resolved["model"] = choose_model(list_models(base, key)) or default_model
        text, tokens = call_chat(resolved["base"], resolved["key"], resolved["model"],
                                 prompt, max_tokens=PROPOSAL_MAX_TOKENS,
                                 temperature=0.7, timeout=120.0)
        usage["tokens"] += tokens
        usage["calls"] += 1
        return text

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
            except Exception as exc:  # noqa: BLE001 — a dead lane is a zero, not a crash
                return Candidate(candidate_id=f"{model.id}-{seed}", target_id=target_id,
                                 diff="", origin_model=model.id, parent_id=parent_id,
                                 metadata={"proposer_error": type(exc).__name__})
            diff = extract_unified_diff(reply)
            failure = check_applies(pinned_root, diff, runner)
            if failure is None:
                return Candidate(
                    candidate_id=f"{model.id}-{seed}", target_id=target_id,
                    diff=diff, origin_model=model.id, parent_id=parent_id,
                    metadata={"routed_model": resolved.get("model", "injected"),
                              "provider": resolved.get("provider", "injected")},
                )
            feedback = (f"\nYOUR PREVIOUS DIFF FAILED TO APPLY: {failure}\n"
                        "Re-emit a corrected unified diff with accurate context lines.")
        # Both attempts failed: empty diff -> no_op_diff tripwire zeroes it.
        return Candidate(candidate_id=f"{model.id}-{seed}", target_id=target_id,
                         diff="", origin_model=model.id, parent_id=parent_id,
                         metadata={"proposer_failed": "diff did not apply after retry"})

    # Honest spend accounting: the campaign CLI reads these after the run and
    # prices tokens at the provider's upper-bound rate (same doctrine as the
    # heartbeat lane — real usage is never invisible to the budget).
    propose.usage = usage  # type: ignore[attr-defined]
    propose.resolved = resolved  # type: ignore[attr-defined]
    return propose
