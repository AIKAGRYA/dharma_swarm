"""Every Makefile recipe that drives a repo CLI must name a surface it has.

This exists because a deleted surface stayed reachable from `make` for hours
with nothing red anywhere. PR #1364 removed the `merge` subcommand from
`scripts/runtime/pr_merge_control.py`; `make pr-merge` kept calling it and
`make help` kept advertising it. No CI job invokes that target, and no test
read the Makefile against the parser, so the breakage was silent -- it
surfaced only when a human typed the command and got an argparse error.

The guard in ``tests/test_pr_merge_control_no_actuation.py`` does not cover
this: it reads ``.github/workflows/*.yml`` only, and it checks flags rather
than subcommands. This module covers the other half -- Makefile recipes, and
subcommand names as well as flags -- against the live ``build_parser()``, so
neither expectation can drift from the CLI.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

from scripts.runtime import pr_merge_control as prc

MAKEFILE = Path(__file__).resolve().parents[1] / "Makefile"
CONTROLLER = "pr_merge_control.py"


def _parser_surface() -> tuple[set[str], set[str]]:
    """(subcommand names, every accepted option string) from the real parser."""
    parser = prc.build_parser()
    options = {opt for a in parser._actions for opt in a.option_strings}
    subcommands: set[str] = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subcommands |= set(action.choices)
            for sub in action.choices.values():
                options |= {opt for a in sub._actions for opt in a.option_strings}
    return subcommands, options


def _controller_invocations(text: str) -> list[tuple[int, str]]:
    """(line number, argument text) for each Makefile call of the controller.

    Recipe lines are tab-indented and may continue across ``\\``. Comment
    lines are skipped so prose naming a removed surface cannot trip this.
    """
    found: list[tuple[int, str]] = []
    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        if CONTROLLER not in line or line.lstrip().startswith("#"):
            continue
        span = [line[line.index(CONTROLLER) + len(CONTROLLER) :]]
        j = i - 1
        while lines[j].rstrip().endswith("\\") and j + 1 < len(lines):
            j += 1
            span.append(lines[j])
        found.append((i, "\n".join(span)))
    return found


def _first_bare_token(args: str) -> str | None:
    """The subcommand: first token that is neither a flag nor a flag's value."""
    tokens = args.split()
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-"):
            # `--flag value` consumes the next token; `--flag=value` does not.
            skip_next = "=" not in token
            continue
        if token.startswith("$") or token.startswith('"'):
            continue
        return token
    return None


def test_makefile_has_controller_invocations_to_check():
    """If this fails the locator broke, and the rest is vacuously green."""
    assert _controller_invocations(MAKEFILE.read_text(encoding="utf-8")), (
        "no pr_merge_control.py invocations found in the Makefile — the "
        "locator is broken, so the checks below would pass without checking"
    )


def test_no_make_target_calls_a_deleted_subcommand():
    """`make pr-merge` shipped broken because nothing asserted this."""
    subcommands, _ = _parser_surface()
    offenders = []
    for lineno, args in _controller_invocations(MAKEFILE.read_text(encoding="utf-8")):
        name = _first_bare_token(args)
        if name is not None and name not in subcommands:
            offenders.append(f"Makefile:{lineno} calls {name!r}")
    assert not offenders, (
        f"Makefile names subcommands the CLI does not have "
        f"(it has {sorted(subcommands)}): " + "; ".join(offenders)
    )


def test_no_make_target_passes_a_deleted_flag():
    """The flag half of the same contract, for Makefile recipes."""
    _, options = _parser_surface()
    offenders = []
    for lineno, args in _controller_invocations(MAKEFILE.read_text(encoding="utf-8")):
        for token in re.findall(r"(--[A-Za-z][A-Za-z0-9_-]*(?:=\S+)?)", args):
            flag = token.split("=", 1)[0]
            if flag not in options:
                offenders.append(f"Makefile:{lineno} passes {flag}")
    assert not offenders, (
        "Makefile passes flags the CLI does not accept: " + "; ".join(offenders)
    )


@pytest.mark.parametrize("removed", ["pr-merge", "--merge-mode", "--merge-method"])
def test_help_text_does_not_advertise_a_removed_surface(removed: str):
    """`make help` is the operator's index; it must not list dead commands.

    `Makefile:264` advertised `make pr-merge PR=123 ARGS='--confirm ...'`
    after the subcommand was deleted -- and `--confirm` had been removed too,
    so the advertised line was wrong twice over.
    """
    help_lines = [
        line
        for line in MAKEFILE.read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("@echo") and "make " in line
    ]
    assert help_lines, "no `make help` echo lines found — locator broke"
    offenders = [line.strip() for line in help_lines if removed in line]
    assert not offenders, (
        f"`make help` still advertises the removed {removed!r}: {offenders}"
    )
