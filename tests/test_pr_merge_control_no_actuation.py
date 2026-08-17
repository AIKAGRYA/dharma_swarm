"""Structural contract: the PR controller has no merge-actuation surface at all.

This replaces a family of tests that used to prove Merge Master Mike's merge
actuator *refused* to fire. Those tests were real, but they guarded a runtime
property of ~250 lines of code that could never succeed: `build_gate` emitted a
literal ``base_cas_enforced: False`` with no code path able to set it true, and
``validate_merge_authority_proof`` returned a constant blocker list. The
actuator was uninhabited by construction, and the merge queue -- which the
repository migrated to -- performs the merge itself.

Deleting a safety test is only defensible if the property it guarded becomes
*stronger*. So the guarantee moves from behavioural to structural: rather than
proving a merge path refuses, this proves no merge path exists. Code that is
absent cannot regress, cannot be re-enabled by a config flag, and cannot be
resurrected by a future edit without failing these tests.

If merge authority is ever genuinely wanted here, these tests must be deleted
deliberately and replaced with real authorization tests -- which is the point.
"""

from __future__ import annotations

import argparse
import ast
import inspect
import re
from pathlib import Path

import pytest

from scripts.runtime import pr_merge_control as prc

SOURCE_PATH = Path(prc.__file__)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)

# Symbols deleted with the actuator. Any of them reappearing means merge
# actuation is being rebuilt inside the evidence engine.
REMOVED_SYMBOLS = (
    "run_mike_merge_authority",
    "validate_merge_authority_proof",
    "gh_merge_command",
    "cmd_merge",
    "MERGE_MODES",
)


@pytest.mark.parametrize("symbol", REMOVED_SYMBOLS)
def test_merge_actuation_symbol_stays_deleted(symbol: str):
    assert not hasattr(prc, symbol), (
        f"{symbol} is back. The controller is an evidence engine; the merge "
        "queue performs merges. Re-adding actuation needs its own design and "
        "real authorization tests, not a restored constant."
    )


def test_no_subcommand_can_merge():
    parser = prc.build_parser()
    subparsers = [
        action
        for action in parser._actions  # noqa: SLF001 - argparse exposes no public API
        if hasattr(action, "choices") and isinstance(action.choices, dict)
    ]
    assert subparsers, "expected a subcommand parser"
    commands = set(subparsers[0].choices)
    assert "merge" not in commands, f"a merge subcommand exists again: {sorted(commands)}"
    # The surviving surface is exactly the evidence pipeline.
    assert commands == {
        "queue",
        "fanout",
        "packet",
        "gate",
        "comment",
        "reviewers",
        "run-agent",
    }, f"unexpected subcommand set: {sorted(commands)}"


def test_source_never_shells_out_to_a_merge():
    """No `gh pr merge`, as a shell string or as an argv pair.

    Covers the two forms the deleted actuator could have used: the composed
    command line, and a ["gh", "pr", "merge", ...] argument list. It does not
    claim to catch a merge assembled from runtime-computed fragments — that
    is what test_no_subcommand_can_merge covers, by proving no entry point
    reaches such code at all.
    """
    lowered = SOURCE.lower()
    assert "gh pr merge" not in lowered
    assert '"pr", "merge"' not in lowered
    assert "'pr', 'merge'" not in lowered


def test_gate_output_carries_no_actuation_permission_field():
    """base_cas_enforced was the actuator's permission bit. It should be gone."""
    assert "base_cas_enforced" not in SOURCE, (
        "base_cas_enforced is an actuation-permission field; the gate reports "
        "evidence and must not carry one"
    )


def test_fanout_authority_declares_no_merge_capability():
    """The fanout receipt must not advertise conditional merge authority."""
    assert "auto-when-clean" not in SOURCE
    assert "conditional_on_merge_gate_clean" not in SOURCE
    assert "evidence_only_no_actuation" in SOURCE


def test_render_github_comment_takes_no_merge_receipt():
    signature = inspect.signature(prc.render_github_comment)
    assert "merge_receipt" not in signature.parameters, (
        "the status comment must not render a merge receipt; nothing produces one"
    )


def test_no_function_writes_a_merge_receipt_artifact():
    assert "MIKE_MERGE_RECEIPT" not in SOURCE, (
        "a merge receipt artifact implies an actuator that produced it"
    )


def test_evidence_pipeline_survives():
    """The deletion must not have taken the useful half with it."""
    for kept in (
        "cmd_packet",
        "cmd_run_agent",
        "cmd_gate",
        "cmd_comment",
        "cmd_queue",
        "cmd_fanout",
        "build_gate",
        "classify_pr",
        "risk_from_files",
        "HOT_PATH_PATTERNS",
    ):
        assert hasattr(prc, kept), f"{kept} is part of the evidence engine and must stay"


def test_risk_tiering_still_blocks_hot_paths():
    """The genuinely novel guarantee is untouched by this deletion."""
    changed = [
        {
            "filename": "dharma_swarm/telos_gates.py",
            "status": "modified",
            "additions": 1,
            "deletions": 0,
        }
    ]
    risk = prc.risk_from_files(changed)
    assert risk["level"] == "CRITICAL"


def test_no_top_level_function_mentions_merge_execution():
    """Catch a re-introduced actuator under a different name."""
    offenders = []
    for node in TREE.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        segment = ast.get_source_segment(SOURCE, node) or ""
        if "gh pr merge" in segment or "--match-head-commit" in segment:
            offenders.append(node.name)
    assert not offenders, f"these functions look like merge actuators: {offenders}"


def _all_cli_options() -> set[str]:
    """Every option string the real CLI accepts, across all subcommands.

    Read from ``build_parser()`` rather than a hand list, so deleting a flag
    updates this automatically and cannot drift.
    """
    parser = prc.build_parser()
    options = {opt for a in parser._actions for opt in a.option_strings}
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                options |= {opt for a in sub._actions for opt in a.option_strings}
    return options


CONTROLLER = "pr_merge_control.py"


def _controller_arg_text(text: str) -> str:
    """Only the argument text actually handed to the controller.

    Workflows also call ``gh``, ``git`` and other scripts, so scanning a whole
    file attributes their flags to this CLI. Two invocation shapes are used
    here and both are extracted exactly:

    1. a direct call, continued across ``\\``-terminated lines;
    2. a ``args=(...)`` / ``args+=(...)`` array later expanded into the call.
    """
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    spans: list[str] = []

    for i, line in enumerate(lines):
        if CONTROLLER not in line:
            continue
        spans.append(line)
        j = i
        while lines[j].rstrip().endswith("\\") and j + 1 < len(lines):
            j += 1
            spans.append(lines[j])

    if f'{CONTROLLER} "${{args[@]}}"' in text:
        collecting = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("args=(") or stripped.startswith("args+=("):
                collecting = True
                spans.append(line)
                if stripped.endswith(")"):
                    collecting = False
                continue
            if collecting:
                spans.append(line)
                if stripped == ")":
                    collecting = False
    return "\n".join(spans)


def _flags_workflows_pass() -> dict[str, set[str]]:
    """Long flags each workflow hands to the controller."""
    root = Path(__file__).resolve().parents[1]
    passed: dict[str, set[str]] = {}
    for path in sorted((root / ".github" / "workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if CONTROLLER not in text:
            continue
        found = set(re.findall(r"(--[a-z][a-z0-9-]+)", _controller_arg_text(text)))
        if found:
            passed[path.name] = found
    return passed


def test_no_workflow_passes_a_flag_the_cli_rejects():
    """A deleted flag must not leave a live caller behind.

    This is the check that was missing when the merge actuator came out:
    ``merge-master-mike-backlog.yml`` kept passing ``--merge-mode`` and
    ``--merge-method`` to ``fanout`` after both were deleted. That workflow
    runs hourly under ``set -euo pipefail``, so it would have failed every
    hour with an argparse error while still looking merely "scheduled".

    Scope, stated honestly: this asserts each flag exists *somewhere* in the
    CLI, not that it is valid for the subcommand that call uses. Binding flag
    to subcommand would need to resolve shell arrays built at runtime, and a
    guard that guesses produces false alarms and gets deleted. Flag existence
    is the property that actually broke, and it is checkable exactly.
    """
    accepted = _all_cli_options()
    by_workflow = _flags_workflows_pass()
    assert by_workflow, "found no controller invocations to check — locator broke"
    offenders = {
        name: sorted(flags - accepted)
        for name, flags in by_workflow.items()
        if flags - accepted
    }
    assert not offenders, (
        "workflows pass flags the CLI does not accept: "
        + "; ".join(f"{n} -> {f}" for n, f in offenders.items())
    )
