"""Fake local code-repair fixtures for the offline harness. Each is a tiny,
deterministic bug plus a HIDDEN gold test (a plain-python script: exit 0 = pass,
so no pytest dependency is needed inside the sandbox). Real SWE-bench-Verified
instances replace these later behind the same RepairTask interface."""
from __future__ import annotations

from .harness import RepairTask

_ADD_TEST = (
    "import sys\n"
    "from solution import add\n"
    "try:\n"
    "    assert add(2, 3) == 5\n"
    "    assert add(0, 0) == 0\n"
    "    assert add(-1, 1) == 0\n"
    "except AssertionError:\n"
    "    sys.exit(1)\n"
)

ADD_TASK = RepairTask(
    name="add-minus-bug",
    files={"solution.py": "def add(a, b):\n    return a - b\n"},  # bug: '-' not '+'
    test_files={"test_solution.py": _ADD_TEST},
    gold_patch={"solution.py": "def add(a, b):\n    return a + b\n"},
    test_args=["test_solution.py"],
)

_MAX_TEST = (
    "import sys\n"
    "from solution import max_of\n"
    "try:\n"
    "    assert max_of([1, 5, 3]) == 5\n"
    "    assert max_of([-2, -9]) == -2\n"
    "    assert max_of([7]) == 7\n"
    "except AssertionError:\n"
    "    sys.exit(1)\n"
)

MAX_TASK = RepairTask(
    name="max-returns-first-bug",
    files={"solution.py": "def max_of(xs):\n    return xs[0]\n"},  # bug: first, not max
    test_files={"test_solution.py": _MAX_TEST},
    gold_patch={"solution.py": "def max_of(xs):\n    return max(xs)\n"},
    test_args=["test_solution.py"],
)

DEMO_TASKS = [ADD_TASK, MAX_TASK]
