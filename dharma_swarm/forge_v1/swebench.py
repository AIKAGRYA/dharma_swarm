"""L3-adjacent — the benchmark task source.

OFFLINE: a set of harder local code-repair fixtures, shaped like SWE-bench
(buggy module + a HIDDEN multi-assertion gold test) and tuned so a single weak
proposer often fails within budget but a decorrelated, verify-gated swarm
succeeds more often — i.e. there is genuine room for coordination lift to be
measured honestly.

LIVE (the flip): replace `bench_tasks()` with real SWE-bench-Verified-lite
instances. Each becomes a RepairTask whose `files` is the repo@commit working
tree, `test_files` is the hidden FAIL_TO_PASS/PASS_TO_PASS suite, and `verify`
runs inside the official SWE-bench Docker harness (or the hardened-local runner).
That swap needs: `pip install swebench`, the Docker-vs-hardened-local decision,
and the M5/amd64 emulation note. Nothing else in the pipeline changes."""
from __future__ import annotations

from .harness import RepairTask


def _task(name: str, buggy: str, gold: str, checks: list[str], fn: str) -> RepairTask:
    asserts = "\n".join(f"    {c}" for c in checks)
    test = (
        "import sys\n"
        f"from solution import {fn}\n"
        "try:\n"
        f"{asserts}\n"
        "except AssertionError:\n"
        "    sys.exit(1)\n"
    )
    return RepairTask(
        name=name,
        files={"solution.py": buggy},
        test_files={"test_solution.py": test},
        gold_patch={"solution.py": gold},
        test_args=["test_solution.py"],
    )


def bench_tasks() -> list[RepairTask]:
    return [
        _task(
            "median-off-by-one",
            buggy="def median(xs):\n    s = sorted(xs)\n    return s[len(s) // 2 - 1]\n",
            gold=(
                "def median(xs):\n"
                "    s = sorted(xs)\n"
                "    m = len(s) // 2\n"
                "    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2\n"
            ),
            checks=[
                "assert median([3, 1, 2]) == 2",
                "assert median([1, 2, 3, 4]) == 2.5",
                "assert median([5]) == 5",
            ],
            fn="median",
        ),
        _task(
            "fizzbuzz-order-bug",
            buggy=(
                "def fb(n):\n"
                "    if n % 3 == 0:\n        return 'Fizz'\n"
                "    if n % 5 == 0:\n        return 'Buzz'\n"
                "    if n % 15 == 0:\n        return 'FizzBuzz'\n"
                "    return str(n)\n"
            ),
            gold=(
                "def fb(n):\n"
                "    if n % 15 == 0:\n        return 'FizzBuzz'\n"
                "    if n % 3 == 0:\n        return 'Fizz'\n"
                "    if n % 5 == 0:\n        return 'Buzz'\n"
                "    return str(n)\n"
            ),
            checks=[
                "assert fb(15) == 'FizzBuzz'",
                "assert fb(3) == 'Fizz'",
                "assert fb(7) == '7'",
            ],
            fn="fb",
        ),
        _task(
            "dedup-loses-order",
            buggy="def dedup(xs):\n    return list(set(xs))\n",
            gold=(
                "def dedup(xs):\n"
                "    seen = set()\n"
                "    out = []\n"
                "    for x in xs:\n"
                "        if x not in seen:\n"
                "            seen.add(x)\n"
                "            out.append(x)\n"
                "    return out\n"
            ),
            checks=[
                "assert dedup([3, 1, 3, 2, 1]) == [3, 1, 2]",
                "assert dedup([]) == []",
            ],
            fn="dedup",
        ),
        _task(
            "binsearch-bound-bug",
            buggy=(
                "def bsearch(xs, t):\n"
                "    lo, hi = 0, len(xs)\n"
                "    while lo < hi:\n"
                "        mid = (lo + hi) // 2\n"
                "        if xs[mid] == t:\n            return mid\n"
                "        if xs[mid] < t:\n            hi = mid\n"
                "        else:\n            lo = mid + 1\n"
                "    return -1\n"
            ),
            gold=(
                "def bsearch(xs, t):\n"
                "    lo, hi = 0, len(xs)\n"
                "    while lo < hi:\n"
                "        mid = (lo + hi) // 2\n"
                "        if xs[mid] == t:\n            return mid\n"
                "        if xs[mid] < t:\n            lo = mid + 1\n"
                "        else:\n            hi = mid\n"
                "    return -1\n"
            ),
            checks=[
                "assert bsearch([1, 3, 5, 7], 5) == 2",
                "assert bsearch([1, 3, 5, 7], 1) == 0",
                "assert bsearch([1, 3, 5, 7], 4) == -1",
            ],
            fn="bsearch",
        ),
    ]


def synthetic_tasks(n: int = 24) -> list[RepairTask]:
    """A larger, well-powered set of synthetic repair tasks (distinct names so
    each model's competence varies). Purely for validating the MACHINERY at
    adequate statistical power (v0's n=3 was the bug); the real claim comes from
    swapping in SWE-bench-Verified. Each task: a function returns an off-by-one
    constant; the fix returns the right one."""
    tasks = []
    for i in range(n):
        right = i * 7 + 3
        test = (
            "import sys\n"
            "from solution import f\n"
            f"sys.exit(0 if f() == {right} else 1)\n"
        )
        tasks.append(
            RepairTask(
                name=f"const-{i}",
                files={"solution.py": f"def f():\n    return {right - 1}\n"},
                test_files={"test_solution.py": test},
                gold_patch={"solution.py": f"def f():\n    return {right}\n"},
                test_args=["test_solution.py"],
            )
        )
    return tasks
