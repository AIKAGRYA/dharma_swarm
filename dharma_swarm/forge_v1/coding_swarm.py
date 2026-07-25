"""A REAL coordinated multi-model coding agent — the thing the Forge was always
meant to point at the benchmark, and which did not exist before this.

NOT "2 models each take one shot." This is a genuine coordination topology with
THREE DIFFERENT model families playing distinct roles and handing off FULL traces:

    PLAN  (model A) -> reads the bug + code, writes a concrete fix plan
    BUILD (model B) -> implements the plan, returns the corrected file(s)
    VERIFY(model C) -> runs the real tests; on fail, diagnoses and hands the
                       trace BACK to BUILD. Loop until tests pass or max_rounds.

Decorrelation is the point (Transcendence Principle): the builder's blind spots
are caught by a verifier from a different family, whose diagnosis steers the next
build. The verifier's pass/fail is the REAL test exit code — never self-report.

This is the swarm ARM for the Forge. Champion = best-of-N on one model. Here the
swarm earns its budget only if PLAN->BUILD->VERIFY coordination beats that.
Models are real (providers.PoolCompletion); the file edits and test runs are real.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .providers import PoolCompletion

_FILE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


@dataclass
class Role:
    name: str
    model: str  # model_id resolvable by PoolCompletion (e.g. "gemini-2.5-flash")


@dataclass
class CodingTask:
    workdir: Path            # real dir holding the buggy code (mutated in place)
    problem: str             # what to fix
    edit_file: str           # the single file the builder may rewrite (relative)
    test_cmd: list[str]      # how to run the hidden test, argv after workdir cwd


@dataclass
class Round:
    n: int
    plan: str = ""
    build_model: str = ""
    verify_model: str = ""
    passed: bool = False
    diagnosis: str = ""
    tokens: int = 0


@dataclass
class SwarmResult:
    resolved: bool
    rounds: list[Round] = field(default_factory=list)
    total_tokens: int = 0
    wall_seconds: float = 0.0


def _ask(model_id: str, prompt: str) -> tuple[str, int]:
    """One real completion via the live provider stack. Returns (text, tokens)."""
    backend = PoolCompletion(model_id)
    return backend.complete(prompt)


def _extract_code(text: str, fallback: str) -> str:
    m = _FILE_RE.search(text or "")
    return m.group(1) if m else fallback


def _run_tests(task: CodingTask) -> tuple[bool, str]:
    """Run the real test command in the workdir. pass = exit 0. Returns (passed, output)."""
    try:
        proc = subprocess.run(
            [sys.executable, *task.test_cmd],
            cwd=task.workdir,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    out = (proc.stdout + "\n" + proc.stderr).strip()
    return proc.returncode == 0, out[-2000:]  # tail of the failure for the verifier


def run_coding_swarm(
    task: CodingTask,
    planner: Role,
    builder: Role,
    verifier: Role,
    *,
    max_rounds: int = 3,
    log=print,
) -> SwarmResult:
    """Run the PLAN->BUILD->VERIFY coordination loop on a real bug. Returns whether
    the real tests passed and the full per-round trace."""
    t0 = time.time()
    result = SwarmResult(resolved=False)
    path = task.workdir / task.edit_file
    original = path.read_text()

    # PLAN — the planner (model A) sets direction from the bug + current code.
    plan_prompt = (
        f"You are the PLANNER in a coding team. A bug must be fixed in `{task.edit_file}`.\n\n"
        f"PROBLEM:\n{task.problem}\n\nCURRENT FILE `{task.edit_file}`:\n```python\n{original}```\n\n"
        "Write a SHORT, concrete plan (3-6 bullet points) for the exact change needed. "
        "Name the function/lines and the precise fix. Do NOT write the full file — just the plan."
    )
    plan, ptok = _ask(planner.model, plan_prompt)
    log(f"  [PLAN/{planner.model}] {ptok} tok")
    result.total_tokens += ptok

    diagnosis = ""  # carries the verifier's critique into the next build round
    for n in range(1, max_rounds + 1):
        rnd = Round(n=n, plan=plan if n == 1 else "", build_model=builder.model,
                    verify_model=verifier.model)
        current = path.read_text()

        # BUILD — the builder (model B) implements the plan (+ any verifier diagnosis).
        build_prompt = (
            f"You are the BUILDER. Fix the bug in `{task.edit_file}` and return the FULL corrected "
            f"file in one python code block (no prose).\n\nPROBLEM:\n{task.problem}\n\n"
            f"PLAN (from the planner):\n{plan}\n\n"
            + (f"PREVIOUS ATTEMPT FAILED. VERIFIER DIAGNOSIS:\n{diagnosis}\n\n" if diagnosis else "")
            + f"CURRENT FILE:\n```python\n{current}```\n"
        )
        build_text, btok = _ask(builder.model, build_prompt)
        result.total_tokens += btok
        rnd.tokens += btok
        new_code = _extract_code(build_text, current)
        path.write_text(new_code)

        # VERIFY — run the REAL tests (ground truth), then have the verifier model
        # (model C) diagnose a failure for the next round.
        passed, output = _run_tests(task)
        rnd.passed = passed
        log(f"  [BUILD/{builder.model} round {n}] {btok} tok -> tests {'PASS' if passed else 'FAIL'}")
        if passed:
            result.resolved = True
            result.rounds.append(rnd)
            break

        diag_prompt = (
            f"You are the VERIFIER. The builder's patch to `{task.edit_file}` FAILED its tests.\n\n"
            f"PROBLEM:\n{task.problem}\n\nTHE PATCHED FILE:\n```python\n{new_code}```\n\n"
            f"TEST OUTPUT (failure):\n{output}\n\n"
            "Diagnose WHY it failed and tell the builder exactly what to change next. Be specific and short."
        )
        diagnosis, vtok = _ask(verifier.model, diag_prompt)
        rnd.diagnosis = diagnosis
        rnd.tokens += vtok
        result.total_tokens += vtok
        log(f"  [VERIFY/{verifier.model} round {n}] {vtok} tok -> diagnosis handed back to builder")
        result.rounds.append(rnd)

    if not result.resolved:
        path.write_text(original)  # leave the bug untouched on failure (clean)
    result.wall_seconds = time.time() - t0
    return result
