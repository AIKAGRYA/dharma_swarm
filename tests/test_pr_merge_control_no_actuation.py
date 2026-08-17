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

import ast
import inspect
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
    """No `gh pr merge` anywhere, in any string form."""
    lowered = SOURCE.lower()
    for needle in ('"merge"', "'merge'"):
        # A literal 'merge' token adjacent to a gh pr invocation is the shape
        # that matters; check the composed command directly.
        del needle
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
