"""Classify a pull request's changed paths into CI work classes.

Why this exists
---------------
Most workflows still trigger on `pull_request`. A workflow-level `paths:`
filter cannot be applied to a CONTRACTED check name: the workflow would not
run, the check would be MISSING, and CI truth would degrade every docs-only
PR. The multiplier, not the volume of work, is what starves the queue (a
measured 435-deep queue on 2026-08-07; one Dependabot bump spawned ~28 runs).

`tests.yml` mixes two REQUIRED pytest contexts with advisory jobs; a
workflow-level `paths:` filter there would skip the required contexts, they
would never report, and branch protection would wait forever. Required jobs
keep running unconditionally. Advisory jobs — including contracted CodeQL,
Semgrep, and the quality ratchet — become conditional, keyed on this
classifier, and report SKIPPED (which CI truth treats as PASS).

Failure posture
---------------
FAIL OPEN, always. Every error path reports every class as changed, so the only
possible failure is running too much. A classifier bug must never silently skip
a test -- that is the AI-N4 shape in `docs/governance/hygiene/patterns/`: a check
that never runs against the instance it exists to catch.

Diff flags
----------
`--no-renames --name-only -z` are not stylistic. PR #1200 proved both
alternatives are exploitable against a prefix match:

  * rename detection reports only the destination, hiding the source path;
  * the human-readable format C-quotes non-ASCII bytes, so
    `.github/workflows/é.yml` arrives as `"​.github/workflows/\303\251.yml"` and
    no longer matches a `.github/` prefix.

NUL-delimited output with rename detection off avoids both.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

# A class is "changed" when any changed path matches one of its rules. Suffix
# rules end with the extension; every other rule is a path prefix.
CLASS_RULES: dict[str, tuple[str, ...]] = {
    # Go sources plus the Python bridges that assert against them. Makefile is
    # in here because both Go lanes invoke `make go-ci` and nothing else in
    # tests.yml uses make -- a change to that target must run the lanes it
    # drives.
    "go": ("tools/", "*.go", "go.mod", "go.sum", "Makefile"),
    "dashboard": ("dashboard/",),
    "terminal": ("terminal/",),
    # Anything that can change Python behaviour, including the dependency
    # pins that decide which Python actually runs.
    "python": (
        "*.py",
        "pyproject.toml",
        "uv.lock",
        "requirements.txt",
        "requirements-dev.txt",
    ),
    # Heavy advisory scans. Lockfiles are intentionally absent: a Dependabot
    # uv bump must still run required pytest (python class) but should not
    # enqueue CodeQL/Semgrep/the ratchet. pyproject.toml is a CodeQL input
    # because it can add package paths the analyzer follows.
    "codeql": ("*.py", "pyproject.toml"),
    "semgrep": ("*.py", "*.go", "dashboard/", "terminal/", ".semgrep/"),
    "quality_ratchet": (
        "*.py",
        "docs/governance/hygiene/",
        "scripts/governance/hygiene/",
    ),
}

CLASSES: tuple[str, ...] = tuple(CLASS_RULES)

# Advisory jobs defined in tests.yml. Editing that workflow must run those
# jobs; it must not force CodeQL/Semgrep/the ratchet (those workflows have
# their own self-coverage below).
TESTS_WORKFLOW_CLASSES: tuple[str, ...] = (
    "go",
    "dashboard",
    "terminal",
    "python",
)

# Self-coverage. Editing this classifier must run every class -- otherwise a
# rule change cannot exercise the jobs it gates. Per-class paths force only
# the workflow that owns that class.
SELF_COVERAGE_PATHS: tuple[str, ...] = ("scripts/ci/classify_changed_paths.py",)
CLASS_SELF_COVERAGE: dict[str, tuple[str, ...]] = {
    "codeql": (".github/workflows/codeql.yml",),
    "semgrep": (
        ".github/workflows/semgrep.yml",
        "scripts/governance/run_semgrep_with_ca.sh",
    ),
    "quality_ratchet": (
        ".github/workflows/quality-ratchet.yml",
        "scripts/governance/hygiene/ratchet.py",
        "scripts/governance/hygiene/ratchet_counters.py",
        "docs/governance/hygiene/ratchet_baselines.json",
    ),
}
TESTS_WORKFLOW_PATH: str = ".github/workflows/tests.yml"


def _matches(path: str, rule: str) -> bool:
    if rule.startswith("*"):
        return path.endswith(rule[1:])
    return path == rule or path.startswith(rule)


def classify(paths: list[str]) -> dict[str, bool]:
    """Map changed paths to work classes. Pure; no I/O, no git.

    A change to any SELF_COVERAGE_PATHS entry marks every class changed: the
    rules deciding which jobs run are inputs to every job here.
    """
    if any(p in SELF_COVERAGE_PATHS for p in paths):
        return all_true()
    classes = {
        name: any(_matches(p, rule) for p in paths for rule in rules)
        for name, rules in CLASS_RULES.items()
    }
    if TESTS_WORKFLOW_PATH in paths:
        for name in TESTS_WORKFLOW_CLASSES:
            classes[name] = True
    for name, extra_paths in CLASS_SELF_COVERAGE.items():
        if any(p in extra_paths for p in paths):
            classes[name] = True
    return classes


def all_true() -> dict[str, bool]:
    """The fail-open answer: every class changed, so every job runs."""
    return dict.fromkeys(CLASSES, True)


def changed_paths(base: str, head: str) -> list[str] | None:
    """NUL-delimited changed paths, or None when the diff cannot be trusted.

    None is a distinct outcome from an empty list. An empty list means the diff
    was read and was genuinely empty; None means it could not be read, and the
    caller must fail open rather than treat "unreadable" as "nothing changed" --
    the AI-N1 shape (unreadable input reported as a definite value).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--no-renames", "--name-only", "-z", base, head],
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    # Bytes, not text: a path is not required to be UTF-8. surrogateescape
    # round-trips the undecodable bytes instead of raising mid-classification.
    raw = result.stdout.decode("utf-8", errors="surrogateescape")
    return [entry for entry in raw.split("\0") if entry]


def resolve(event: str, base: str, head: str) -> tuple[dict[str, bool], str]:
    """Return (classes, reason). Never raises."""
    if event != "pull_request":
        return all_true(), f"event={event or '<empty>'} is not a pull_request"
    if not base or not head:
        return all_true(), "pull request base or head sha missing"
    paths = changed_paths(base, head)
    if paths is None:
        return all_true(), f"could not read diff {base[:12]}..{head[:12]}"
    return classify(paths), f"classified {len(paths)} changed path(s)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", default=os.environ.get("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--base", default=os.environ.get("BASE_SHA", ""))
    parser.add_argument("--head", default=os.environ.get("HEAD_SHA", ""))
    parser.add_argument("--output", default=os.environ.get("GITHUB_OUTPUT", ""))
    args = parser.parse_args(argv)

    classes, reason = resolve(args.event, args.base, args.head)

    lines = [f"{name}={str(value).lower()}" for name, value in classes.items()]
    if args.output:
        with open(args.output, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    for line in lines:
        print(line)
    print(f"reason: {reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
