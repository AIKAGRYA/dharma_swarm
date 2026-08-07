"""Classify a pull request's changed paths into CI work classes.

Why this exists
---------------
33 of this repository's 48 workflows trigger on `pull_request` and only 5 carry
a `paths:` filter, so a one-line dependency bump launches ~28 workflow runs. The
runner allowance is per-account, so those runs queue against every other PR: a
measured 435-deep queue on 2026-08-07, in which a single Dependabot PR
(`dependabot/uv/h2-4.4.1`) accounted for 28 runs by itself. The multiplier, not
the volume of work, is what starves the queue.

Workflow-level `paths:` cannot fix the worst offender. `tests.yml` mixes the two
REQUIRED pytest contexts with six advisory jobs; a `paths:` filter there would
skip the required contexts on a non-matching PR, they would never report, and
branch protection would wait forever. So the required jobs keep running
unconditionally and only the advisory ones become conditional, keyed on this
classifier.

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
    # Go sources plus the Python bridges that assert against them.
    "go": ("tools/", "*.go", "go.mod", "go.sum"),
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
}

CLASSES: tuple[str, ...] = tuple(CLASS_RULES)


def _matches(path: str, rule: str) -> bool:
    if rule.startswith("*"):
        return path.endswith(rule[1:])
    return path == rule or path.startswith(rule)


def classify(paths: list[str]) -> dict[str, bool]:
    """Map changed paths to work classes. Pure; no I/O, no git."""
    return {
        name: any(_matches(p, rule) for p in paths for rule in rules)
        for name, rules in CLASS_RULES.items()
    }


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
