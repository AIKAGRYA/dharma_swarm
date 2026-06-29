"""Prove the coordinated coding swarm works on a REAL bug with 3 LIVE model families.

    PYTHONPATH=. <venv>/python -m dharma_swarm.forge_v1.coding_swarm_demo

Sets up a real local repo with a genuinely tricky bug + a hidden test, then runs
PLAN(Gemini) -> BUILD(DeepSeek) -> VERIFY(GLM-5.1), looping until the real test
passes. Prints the full coordination trace. This is the swarm-as-coding-agent the
Forge is meant to measure — real models, real file edits, real test grading."""
from __future__ import annotations

import tempfile
from pathlib import Path

from dharma_swarm.model_pool import FORGE_NVIDIA_LLAMA_VERIFIER_MODEL_ID

from .coding_swarm import CodingTask, Role, run_coding_swarm

# A genuinely tricky bug: a "merge overlapping intervals" function that's wrong in
# two ways (doesn't sort first; uses > instead of >= so touching intervals don't
# merge). A naive one-shot often fixes one and misses the other — coordination helps.
BUGGY = '''\
def merge_intervals(intervals):
    """Merge overlapping or touching intervals. [[1,3],[2,6],[8,10],[10,12]] -> [[1,6],[8,12]]."""
    merged = []
    for start, end in intervals:
        if merged and start > merged[-1][1]:
            merged.append([start, end])
        else:
            if merged:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
    return merged
'''

HIDDEN_TEST = '''\
import sys
from solution import merge_intervals
cases = [
    ([[1,3],[2,6],[8,10],[10,12]], [[1,6],[8,12]]),      # touching 10-10 must merge
    ([[8,10],[1,3],[2,6]], [[1,6],[8,10]]),              # unsorted input
    ([[1,4],[0,2],[3,5]], [[0,5]]),                       # unsorted + overlap chain
    ([], []),
    ([[5,7]], [[5,7]]),
]
for inp, want in cases:
    got = merge_intervals([list(x) for x in inp])
    if [list(g) for g in got] != [list(w) for w in want]:
        print(f"FAIL: {inp} -> {got}, want {want}"); sys.exit(1)
sys.exit(0)
'''


def main() -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="coding_swarm_"))
    (tmp / "solution.py").write_text(BUGGY)
    (tmp / "test_solution.py").write_text(HIDDEN_TEST)

    task = CodingTask(
        workdir=tmp,
        problem=(
            "merge_intervals must merge overlapping AND touching intervals and must work on "
            "UNSORTED input. Failing examples: [[1,3],[2,6],[8,10],[10,12]] should give "
            "[[1,6],[8,12]]; unsorted [[8,10],[1,3],[2,6]] should give [[1,6],[8,10]]."
        ),
        edit_file="solution.py",
        test_cmd=["test_solution.py"],
    )

    # Three DIFFERENT live families — genuine decorrelation (deepmind / chinese / nvidia).
    planner = Role("planner", "glm-5.1")
    builder = Role("builder", "gemini-2.5-flash")
    verifier = Role("verifier", FORGE_NVIDIA_LLAMA_VERIFIER_MODEL_ID)

    print("=" * 70)
    print("CODING SWARM — PLAN(glm) -> BUILD(gemini) -> VERIFY(llama-3.3), real bug")
    print("=" * 70)
    res = run_coding_swarm(task, planner, builder, verifier, max_rounds=3)

    print("-" * 70)
    print(f"RESOLVED: {res.resolved}  | rounds: {len(res.rounds)}  | "
          f"tokens: {res.total_tokens}  | {res.wall_seconds:.0f}s")
    for r in res.rounds:
        print(f"  round {r.n}: build={r.build_model} tests={'PASS' if r.passed else 'FAIL'}"
              + (f" -> verifier({r.verify_model}) diagnosed" if r.diagnosis else ""))
    print("=" * 70)
    print("This is a REAL coordinated multi-model coding agent fixing a real bug —"
          " the swarm arm the Forge measures. Swap the local bug for a SWE-bench"
          " instance (swebench_real.py) and the same loop attacks real GitHub bugs.")
    return {"resolved": res.resolved, "rounds": len(res.rounds), "tokens": res.total_tokens}


if __name__ == "__main__":
    main()
