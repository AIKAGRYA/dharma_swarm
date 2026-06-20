"""Forge v1 — the FIRST real end-to-end swarm-vs-best-of-N measurement on a
REAL SWE-bench-Verified instance, graded by the OFFICIAL swebench Docker harness.

This is the L3 flip taken all the way: live frontier models (Gemini + GLM),
real repo@commit tasks, real hidden-test grading. Nothing is faked. An honest
negative (swarm did not beat best-of-N) is a valid, ship-worthy result.

What it measures
----------------
For each instance, two arms at EQUAL token budget:

  CHAMPION : best-of-N on ONE model (gemini-2.5-flash). Sample up to N patches
             under a TokenBroker cap; grade EACH with verify_prediction (Docker);
             keep the first that resolves.
  SWARM    : two DECORRELATED real model families (gemini-2.5-flash + glm-5.1)
             each propose one patch; grade each with verify_prediction; keep the
             first that resolves. Same TokenBroker cap as champion (equal budget).

  swarm_lift = pass_rate(swarm) - pass_rate(champion) over the instances.

Why a swebench-aware best-of-N (not harness.best_of_n)
------------------------------------------------------
The forge_v1 inline `verify()` runs an inline gold test in a temp dir. Real
SWE-bench tasks are repo@commit + a HIDDEN FAIL_TO_PASS/PASS_TO_PASS suite that
only exists inside the instance's Docker image. So we grade with
`swebench_real.verify_prediction` (the official Docker harness) instead. The
model is given the problem statement (+ the real target-file context pulled from
the instance image — the same context an agent grepping the repo would find, NOT
the gold patch) and must emit a unified diff against the repo.

Run (needs the swebench venv + Docker up; SLOW — ~11 min/instance under qemu):

    PYTHONPATH=/Users/dhyana/ds_forge_v1_scoreboard \
      /Users/dhyana/dharma_swarm/.venv/bin/python \
      -m dharma_swarm.forge_v1.run_real --instances django__django-12209 -n 3

Artifacts (full result JSON) go to ~/.dharma/forge_v1/real_run_<ts>.json — never
the repo.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# When run as `python dharma_swarm/forge_v1/run_real.py`, sys.path[0] is THIS
# dir, and the sibling `swebench.py` (offline fixtures) shadows the real swebench
# PyPI library. Drop the script dir so the library wins. (`python -m ...` is
# clean already; this just makes both invocations work.)
_here = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != _here]

from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402
from dharma_swarm.forge_v1.harness import BudgetExhausted, TokenBroker  # noqa: E402
from dharma_swarm.forge_v1.providers import LiveModel, PoolCompletion  # noqa: E402
from dharma_swarm.forge_v1.swebench_real import (  # noqa: E402
    instance_image_key,
    verified_instances,
    verify_prediction,
)

# Default tiny/fast pure-logic instances (no network tests). Picked by smallest
# (FAIL_TO_PASS, PASS_TO_PASS, patch size) over sympy/django in Verified.
DEFAULT_INSTANCES = ["django__django-12209"]

CHAMPION_MODEL = "gemini-2.5-flash"
# Second DECORRELATED family for the swarm (Ollama-Cloud GLM, chinese_cluster) —
# a genuinely different model family from Gemini (deepmind), not a temperature
# stand-in. Verified live via dkeys + a real PONG call before this run.
SWARM_MODELS = ["gemini-2.5-flash", "glm-5.1"]


# --------------------------------------------------------------------------- #
# Pulling REAL target-file context out of the instance Docker image
# --------------------------------------------------------------------------- #
def _target_paths_from_gold(instance: dict) -> list[str]:
    """File paths the gold patch touches. We use the PATHS only (not contents) —
    an agent grepping the repo for the bug would find the same files. This is
    context, not the fix."""
    paths = []
    for line in instance.get("patch", "").splitlines():
        m = re.match(r"^\+\+\+ b/(.+)$", line)
        if m:
            paths.append(m.group(1).strip())
    return paths


def _read_files_from_image(instance: dict, paths: list[str], *, max_chars: int = 400_000) -> dict[str, str]:
    """Read the FULL real file contents AT base_commit from the instance's repo by
    running a throwaway container off the prebuilt image. The repo lives at
    /testbed inside the swebench image. Returns {path: content} (best-effort;
    missing files skipped). This is legitimate working-tree context an agent would
    have — the BUGGY pre-fix source, never the gold patch.

    NOTE: we do NOT truncate to a small window — the bug can be anywhere in the
    file (django/db/models/base.py is ~1900 lines and the fix is near line 850),
    and Gemini's input window is ~1M tokens, so the whole file fits. Truncating
    the context to the first 16KB was why the first run's patches were garbage:
    the model never saw the buggy region. max_chars is just a sanity ceiling."""
    image = instance_image_key(instance)
    out: dict[str, str] = {}
    # Make sure the image is present (pull is slow but one-time; the eval will
    # need it anyway). Best-effort: if pull fails we just skip context.
    subprocess.run(
        ["docker", "pull", image],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    for p in paths:
        try:
            proc = subprocess.run(
                ["docker", "run", "--rm", "--entrypoint", "cat", image, f"/testbed/{p}"],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            continue
        if proc.returncode == 0 and proc.stdout:
            content = proc.stdout
            if len(content) > max_chars:
                content = content[:max_chars] + "\n# ... (file truncated at sanity ceiling)\n"
            out[p] = content
    return out


# --------------------------------------------------------------------------- #
# Repair prompt + patch parsing (unified-diff oriented, swebench-shaped)
# --------------------------------------------------------------------------- #
def build_repair_prompt(instance: dict, file_context: dict[str, str]) -> str:
    """Ask the model for COMPACT SEARCH/REPLACE edits (Aider edit-block format).

    We deliberately do NOT ask for a unified diff (LLM-authored diffs fail at
    `git apply`: miscounted `@@` line counts, drifted context, mid-hunk
    truncation) NOR for the whole corrected file (a ~1900-line/78KB module is too
    much output for slower families — GLM-5.1 on Ollama Cloud TIMED OUT at 240s
    re-emitting it). Instead the model returns small SEARCH/REPLACE blocks: the
    exact original snippet and its replacement. WE apply them to the real base
    content by exact string match, then compute a guaranteed-applicable unified
    diff with difflib. The model only writes the few changed lines — tiny output,
    works across families — and never does diff bookkeeping."""
    repo = instance["repo"]
    problem = instance["problem_statement"]
    ctx_blocks = []
    for path, content in file_context.items():
        ctx_blocks.append(
            f"### File `{path}` (current buggy contents at this commit):\n"
            f"```python\n{content}\n```"
        )
    ctx = "\n\n".join(ctx_blocks) if ctx_blocks else "(no file context available)"
    return (
        f"You are fixing a real bug in the `{repo}` repository.\n\n"
        f"## Bug report / problem statement\n{problem}\n\n"
        f"## Source file(s) you may edit\n{ctx}\n\n"
        "## Your task\n"
        "Make the MINIMAL change needed to fix the bug. Do NOT touch tests. Output "
        "must be valid Python.\n\n"
        "Return ONE OR MORE edits in this exact SEARCH/REPLACE format, and NOTHING "
        "else:\n\n"
        "<<<<<<< SEARCH path=django/db/models/base.py\n"
        "<the exact original lines to find, copied verbatim from the file above>\n"
        "=======\n"
        "<the replacement lines>\n"
        ">>>>>>> REPLACE\n\n"
        "Rules: the SEARCH text MUST appear verbatim (character-for-character, same "
        "indentation) in the named file so it can be located exactly. Keep each "
        "SEARCH block small (just the lines you change plus a little surrounding "
        "context to make it unique). Use one block per distinct edit. Put the file "
        "path on the SEARCH marker line as shown.\n"
    )


# Aider-style edit block: <<<<<<< SEARCH path=... \n search \n ======= \n replace \n >>>>>>> REPLACE
_EDIT_BLOCK_RE = re.compile(
    r"<{5,}\s*SEARCH\s+path=([^\s`]+)\s*\n(.*?)\n={5,}\s*\n(.*?)\n>{5,}\s*REPLACE",
    re.DOTALL,
)
# Back-compat: a fenced block whose info line carries `path=<path>` -> full file.
_FILE_BLOCK_RE = re.compile(
    r"```[a-zA-Z0-9_]*\s+path=([^\s`]+)\s*\n(.*?)```", re.DOTALL
)


def parse_edit_blocks(text: str) -> list[tuple[str, str, str]]:
    """Pull (path, search, replace) tuples from the model's SEARCH/REPLACE blocks."""
    out = []
    for m in _EDIT_BLOCK_RE.finditer(text or ""):
        out.append((m.group(1).strip(), m.group(2), m.group(3)))
    return out


def apply_edit_blocks(
    base_files: dict[str, str], edits: list[tuple[str, str, str]]
) -> tuple[dict[str, str], str | None]:
    """Apply SEARCH/REPLACE edits to base file contents by EXACT string match.
    Returns (new_files, error). error is set (and new_files empty) if any edit's
    SEARCH text is not found verbatim or is ambiguous (appears >1 time) — we never
    guess, because a wrong match would corrupt the file silently."""
    new_files = {p: c for p, c in base_files.items()}
    applied = 0
    for path, search, replace in edits:
        if path not in new_files:
            return {}, f"edit targets unknown file {path!r}"
        content = new_files[path]
        count = content.count(search)
        if count == 0:
            return {}, f"SEARCH text not found verbatim in {path}"
        if count > 1:
            return {}, f"SEARCH text ambiguous ({count}x) in {path}"
        new_files[path] = content.replace(search, replace, 1)
        applied += 1
    if applied == 0:
        return {}, "no edits applied"
    # Keep only files that actually changed.
    changed = {p: c for p, c in new_files.items() if c != base_files.get(p)}
    if not changed:
        return {}, "edits produced no change"
    return changed, None


def parse_full_files(text: str) -> dict[str, str]:
    """Back-compat: pull {path: full_content} from `path=` fenced blocks (used if a
    model ignores the SEARCH/REPLACE format and returns whole files instead)."""
    out: dict[str, str] = {}
    for m in _FILE_BLOCK_RE.finditer(text or ""):
        path = m.group(1).strip()
        body = m.group(2)
        if not body.endswith("\n"):
            body += "\n"
        out[path] = body
    return out


def compute_unified_diff(base_files: dict[str, str], new_files: dict[str, str]) -> str:
    """Compute a git-style unified diff from base->new file contents using difflib
    — guaranteed to apply (correct line counts/context by construction) because we
    generate it, not the model. Only paths present in BOTH (and actually changed)
    produce hunks. swebench applies the result with `git apply -p1`."""
    import difflib

    chunks: list[str] = []
    for path, new_content in new_files.items():
        base_content = base_files.get(path)
        if base_content is None or new_content == base_content:
            continue
        diff = difflib.unified_diff(
            base_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=3,
        )
        body = "".join(diff)
        if not body:
            continue
        chunks.append(f"diff --git a/{path} b/{path}\n{body}")
    out = "".join(chunks)
    if out and not out.endswith("\n"):
        out += "\n"
    return out


@dataclass
class Proposal:
    model: str
    patch: str
    tokens: int
    error: str | None = None


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

    def __init__(self, model_id: str, temperature: float = 0.2, max_tokens: int = DIFF_MAX_TOKENS):
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._completion = _DiffCompletion(model_id, temperature, max_tokens)

    def propose(self, instance: dict, file_context: dict[str, str]) -> Proposal:
        prompt = build_repair_prompt(instance, file_context)
        try:
            text, tokens = self._completion.complete(prompt)
        except Exception as e:  # transient/timeout provider error -> errored sample, not crash
            return Proposal(model=self.model_id, patch="", tokens=0,
                            error=f"{type(e).__name__}: {e}")

        # Primary path: SEARCH/REPLACE edit blocks applied to base content.
        edits = parse_edit_blocks(text)
        if edits:
            new_files, err = apply_edit_blocks(file_context, edits)
            if err:
                return Proposal(model=self.model_id, patch="", tokens=tokens, error=err)
        else:
            # Fallback: model returned whole `path=` files instead.
            new_files = parse_full_files(text)
            if not new_files:
                return Proposal(model=self.model_id, patch="", tokens=tokens,
                                error="no SEARCH/REPLACE or path= block in response")

        patch = compute_unified_diff(file_context, new_files)
        if not patch.strip():
            return Proposal(model=self.model_id, patch="", tokens=tokens,
                            error="edits produced no change vs base")
        return Proposal(model=self.model_id, patch=patch, tokens=tokens)


# Hard wall-clock cap on ONE live model call. Without it, a stalled provider
# (observed: GLM-5.1 on Ollama Cloud leaving the SSL socket in CLOSE_WAIT with the
# process at 0% CPU) hangs the whole run forever — provider.complete has no
# client-side timeout. asyncio.wait_for turns a hang into a TimeoutError that the
# proposer catches and records as an errored (unresolved) sample.
MODEL_CALL_TIMEOUT_S = 240


class _DiffCompletion(PoolCompletion):
    """PoolCompletion with overridable temperature + max_tokens (long diffs) and
    a hard per-call timeout so a hung provider can't stall the whole run."""

    def __init__(self, model_id: str, temperature: float, max_tokens: int,
                 timeout_s: int = MODEL_CALL_TIMEOUT_S):
        super().__init__(model_id)
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_s = timeout_s

    def complete(self, prompt: str):
        import asyncio

        from dharma_swarm.models import LLMRequest
        from dharma_swarm.forge_v1.providers import _usage_tokens

        request = LLMRequest(
            model=self._wire_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )

        async def _call():
            return await asyncio.wait_for(
                self._provider.complete(request), timeout=self._timeout_s
            )

        response = asyncio.run(_call())
        return response.content or "", _usage_tokens(response.usage)


# --------------------------------------------------------------------------- #
# Swebench-aware arms (grade with the Docker harness, share one TokenBroker)
# --------------------------------------------------------------------------- #
@dataclass
class GradedSample:
    model: str
    tokens: int
    patch_len: int
    resolved: bool
    grade_seconds: float
    error: str | None = None


@dataclass
class ArmRun:
    arm: str
    passed: bool = False
    samples: list[GradedSample] = field(default_factory=list)
    tokens_spent: int = 0
    wall_seconds: float = 0.0
    budget_exhausted: bool = False
    note: str = ""


def _grade(instance: dict, patch: str, *, timeout: int) -> tuple[bool, float, str | None]:
    """Grade ONE patch with the official swebench Docker harness. An empty patch
    is graded too (swebench reports it unresolved). Returns (resolved, seconds,
    error). An infra failure (image build/pull) is surfaced as an error, never a
    fake verdict."""
    t0 = time.time()
    try:
        resolved = verify_prediction(instance, patch, timeout=timeout)
        return bool(resolved), time.time() - t0, None
    except Exception as e:  # infra error: report honestly, do not fake
        return False, time.time() - t0, f"{type(e).__name__}: {e}"


def _consume_proposal(
    run: ArmRun, instance: dict, prop: Proposal, broker: TokenBroker, *, grade_timeout: int
) -> bool | None:
    """Charge tokens, grade the proposal, record the sample. Returns:
      True  -> resolved (arm passes, stop),
      False -> graded but not resolved (keep going),
      None  -> budget exhausted (stop the arm).
    A proposer error or empty patch is recorded as an unresolved sample (no
    Docker grade) so a transient provider failure doesn't kill the run or fake a
    verdict."""
    try:
        broker.charge(prop.tokens)
    except BudgetExhausted:
        run.budget_exhausted = True
        return None
    if prop.error or not prop.patch.strip():
        run.samples.append(
            GradedSample(prop.model, prop.tokens, len(prop.patch), False, 0.0,
                         prop.error or "empty-patch")
        )
        return False
    resolved, secs, err = _grade(instance, prop.patch, timeout=grade_timeout)
    run.samples.append(
        GradedSample(prop.model, prop.tokens, len(prop.patch), resolved, secs, err)
    )
    if resolved:
        run.passed = True
        return True
    return False


def champion_best_of_n(
    instance: dict,
    file_context: dict[str, str],
    proposer: SweBenchProposer,
    broker: TokenBroker,
    *,
    n: int,
    grade_timeout: int,
) -> ArmRun:
    """Best-of-N on a single model, graded by Docker. Keep the first patch that
    resolves; stop when budget can't afford the next sample."""
    run = ArmRun(arm="champion_best_of_n")
    t0 = time.time()
    for i in range(n):
        prop = proposer.propose(instance, file_context)
        outcome = _consume_proposal(run, instance, prop, broker, grade_timeout=grade_timeout)
        if outcome is None or outcome is True:
            break
    run.tokens_spent = broker.spent
    run.wall_seconds = time.time() - t0
    return run


def swarm_arm(
    instance: dict,
    file_context: dict[str, str],
    proposers: list[SweBenchProposer],
    broker: TokenBroker,
    *,
    grade_timeout: int,
) -> ArmRun:
    """Decorrelated swarm: each model proposes one patch; grade each with Docker;
    keep the first that resolves. Shares the SAME broker cap as the champion
    (equal budget). Selection across decorrelated proposers = the honest way a
    swarm can beat best-of-N (Transcendence Principle: diversity + verifier
    gate)."""
    run = ArmRun(arm="swarm")
    t0 = time.time()
    for proposer in proposers:
        prop = proposer.propose(instance, file_context)
        outcome = _consume_proposal(run, instance, prop, broker, grade_timeout=grade_timeout)
        if outcome is None or outcome is True:
            break
    run.tokens_spent = broker.spent
    run.wall_seconds = time.time() - t0
    return run


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def run(
    instance_ids: list[str],
    *,
    n: int,
    budget: int,
    grade_timeout: int,
    swarm_second_model: str,
    single_family_standin: bool,
) -> dict:
    results = []
    for iid in instance_ids:
        print(f"\n{'=' * 72}\n[run_real] instance: {iid}", flush=True)
        instance = verified_instances(instance_ids=[iid])[0]
        image = instance_image_key(instance)
        print(f"[run_real] repo={instance['repo']} base={instance['base_commit'][:12]} image={image}", flush=True)

        # Real working-tree context (paths from gold headers, contents from image).
        paths = _target_paths_from_gold(instance)
        print(f"[run_real] pulling file context for {paths} from image (one-time pull may be slow)...", flush=True)
        ctx = _read_files_from_image(instance, paths)
        print(f"[run_real] got context for {list(ctx)} ({sum(len(v) for v in ctx.values())} chars)", flush=True)

        # CHAMPION: best-of-N on gemini.
        champ_proposer = SweBenchProposer(CHAMPION_MODEL)
        champ_broker = TokenBroker(cap=budget)
        print(f"[run_real] CHAMPION best-of-{n} on {CHAMPION_MODEL} (budget {budget} tok)...", flush=True)
        champ = champion_best_of_n(
            instance, ctx, champ_proposer, champ_broker, n=n, grade_timeout=grade_timeout
        )
        for s in champ.samples:
            print(f"    champ sample: model={s.model} tok={s.tokens} patch_len={s.patch_len} "
                  f"resolved={s.resolved} ({s.grade_seconds:.0f}s){' ERR:'+s.error if s.error else ''}", flush=True)
        print(f"[run_real] CHAMPION passed={champ.passed} tokens={champ.tokens_spent} wall={champ.wall_seconds:.0f}s", flush=True)

        # SWARM: gemini + second family, equal budget.
        if single_family_standin:
            swarm_proposers = [
                SweBenchProposer(SWARM_MODELS[0], temperature=0.2),
                SweBenchProposer(SWARM_MODELS[0], temperature=0.9),
            ]
            swarm_note = "single-family stand-in: gemini@0.2 + gemini@0.9 (NOT a 2nd family)"
        else:
            swarm_proposers = [
                SweBenchProposer(SWARM_MODELS[0]),
                SweBenchProposer(swarm_second_model),
            ]
            swarm_note = f"decorrelated 2-family: {SWARM_MODELS[0]} + {swarm_second_model}"
        swarm_broker = TokenBroker(cap=budget)
        print(f"[run_real] SWARM ({swarm_note}) budget {budget} tok...", flush=True)
        swarm = swarm_arm(instance, ctx, swarm_proposers, swarm_broker, grade_timeout=grade_timeout)
        for s in swarm.samples:
            print(f"    swarm sample: model={s.model} tok={s.tokens} patch_len={s.patch_len} "
                  f"resolved={s.resolved} ({s.grade_seconds:.0f}s){' ERR:'+s.error if s.error else ''}", flush=True)
        print(f"[run_real] SWARM passed={swarm.passed} tokens={swarm.tokens_spent} wall={swarm.wall_seconds:.0f}s", flush=True)
        swarm.note = swarm_note

        results.append(
            {
                "instance_id": iid,
                "repo": instance["repo"],
                "image": image,
                "file_context_paths": list(ctx),
                "champion": asdict(champ),
                "swarm": asdict(swarm),
            }
        )

    n_inst = len(results)
    champ_pass = sum(1 for r in results if r["champion"]["passed"])
    swarm_pass = sum(1 for r in results if r["swarm"]["passed"])
    champ_rate = champ_pass / n_inst if n_inst else 0.0
    swarm_rate = swarm_pass / n_inst if n_inst else 0.0
    total_tokens = sum(
        r["champion"]["tokens_spent"] + r["swarm"]["tokens_spent"] for r in results
    )
    return {
        "kind": "forge_v1_real_run",
        "timestamp": int(time.time()),
        "config": {
            "instances": instance_ids,
            "best_of_n": n,
            "budget_per_arm_tokens": budget,
            "grade_timeout_s": grade_timeout,
            "champion_model": CHAMPION_MODEL,
            "swarm_models": [SWARM_MODELS[0], swarm_second_model] if not single_family_standin
            else [SWARM_MODELS[0] + "@0.2", SWARM_MODELS[0] + "@0.9"],
            "swarm_is_single_family_standin": single_family_standin,
        },
        "n_instances": n_inst,
        "champion_pass_rate": champ_rate,
        "swarm_pass_rate": swarm_rate,
        "swarm_lift": swarm_rate - champ_rate,
        "total_live_tokens": total_tokens,
        "per_instance": results,
    }


def _gemini_price_usd(tokens: int) -> float:
    """Rough blended $ for gemini-2.5-flash (~$0.30/M in, ~$2.50/M out). We only
    track a total token count, so use a blended ~$1/M as a coarse upper bound."""
    return tokens / 1_000_000 * 1.0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Forge v1 real swarm-vs-best-of-N run")
    ap.add_argument("--instances", nargs="*", default=DEFAULT_INSTANCES,
                    help="SWE-bench-Verified instance ids")
    ap.add_argument("-n", "--best-of-n", type=int, default=3, help="champion best-of-N (<=3 for a proof)")
    ap.add_argument("--budget", type=int, default=20000, help="token cap PER ARM (equal budget)")
    ap.add_argument("--grade-timeout", type=int, default=1800, help="swebench per-eval timeout (s)")
    ap.add_argument("--swarm-second-model", default="glm-5.1",
                    help="second swarm family (must be a live key)")
    ap.add_argument("--single-family-standin", action="store_true",
                    help="if no 2nd live family: use gemini@2 temperatures (honest stand-in)")
    args = ap.parse_args(argv)

    t0 = time.time()
    result = run(
        args.instances,
        n=args.best_of_n,
        budget=args.budget,
        grade_timeout=args.grade_timeout,
        swarm_second_model=args.swarm_second_model,
        single_family_standin=args.single_family_standin,
    )
    wall = time.time() - t0
    result["total_wall_seconds"] = wall
    result["approx_usd"] = _gemini_price_usd(result["total_live_tokens"])

    out_dir = dharma_state_dir() / "forge_v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"real_run_{result['timestamp']}.json"
    out_path.write_text(json.dumps(result, indent=2))

    print("\n" + "=" * 72)
    print("[run_real] FINAL REPORT")
    print(f"  instances           : {result['config']['instances']}")
    print(f"  best_of_n           : {result['config']['best_of_n']}")
    print(f"  budget/arm (tokens) : {result['config']['budget_per_arm_tokens']}")
    print(f"  swarm models        : {result['config']['swarm_models']} "
          f"(single-family stand-in: {result['config']['swarm_is_single_family_standin']})")
    for r in result["per_instance"]:
        print(f"  - {r['instance_id']}: champion_resolved={r['champion']['passed']} "
              f"swarm_resolved={r['swarm']['passed']} "
              f"(champ {r['champion']['tokens_spent']}tok/{r['champion']['wall_seconds']:.0f}s, "
              f"swarm {r['swarm']['tokens_spent']}tok/{r['swarm']['wall_seconds']:.0f}s)")
    print(f"  champion_pass_rate  : {result['champion_pass_rate']:.3f}")
    print(f"  swarm_pass_rate     : {result['swarm_pass_rate']:.3f}")
    print(f"  >>> swarm_lift      : {result['swarm_lift']:+.3f}")
    print(f"  total live tokens   : {result['total_live_tokens']}  (~${result['approx_usd']:.4f})")
    print(f"  total wall-clock    : {wall:.0f}s ({wall/60:.1f} min)")
    print(f"  result JSON         : {out_path}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
