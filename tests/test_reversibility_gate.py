"""Tests for the code-deterministic reversibility gate (Phase 8 safety invariant).

The load-bearing property under test: whether an action may run unattended is a
pure function of the action string + operator reachability. No model, provider,
or cognition input exists. A weak model resolved at wake cannot widen authority.
"""

from __future__ import annotations

from dharma_swarm.adaptive_autonomy import RiskLevel
from dharma_swarm.operator_core.reversibility_gate import (
    ActionClass,
    ReversibilityGate,
    classify_action,
)


def test_safe_and_low_actions_run_unattended() -> None:
    gate = ReversibilityGate()
    for action in ("read the status file", "git status", "append a log line"):
        d = gate.classify(action)
        assert d.may_execute_unattended is True
        assert d.action_class is ActionClass.REVERSIBLE_SAFE


def test_medium_action_requires_lease_not_unattended() -> None:
    d = classify_action("edit the config file")
    assert d.risk is RiskLevel.MEDIUM
    assert d.action_class is ActionClass.NEEDS_LEASE
    assert d.requires_execution_lease is True
    assert d.may_execute_unattended is False


def test_high_action_is_irreversible_never_unattended() -> None:
    d = classify_action("deploy to the cluster")
    assert d.action_class is ActionClass.IRREVERSIBLE
    assert d.may_execute_unattended is False


def test_critical_action_is_operator_only() -> None:
    d = classify_action("drop table users")
    assert d.action_class is ActionClass.OPERATOR_ONLY
    assert d.may_execute_unattended is False


def test_never_auto_overrides_even_benign_phrasing() -> None:
    # "send email" reads low-risk lexically but is a hard NEVER_AUTO back-door.
    d = classify_action("send email to the architect", operator_reachable=False)
    assert d.never_auto_hit == "send email"
    assert d.action_class is ActionClass.OPERATOR_ONLY
    assert d.may_execute_unattended is False


def test_never_auto_when_operator_reachable_escalates_to_irreversible() -> None:
    d = classify_action("git push origin main", operator_reachable=True)
    assert d.never_auto_hit == "git push"
    assert d.action_class is ActionClass.IRREVERSIBLE
    assert d.may_execute_unattended is False


def test_unknown_action_fails_closed_to_needs_lease() -> None:
    # The fail-closed invariant: unknown input is NEVER reversible_safe.
    d = classify_action("frobnicate the widgets in an unspecified way")
    assert d.may_execute_unattended is False
    assert d.action_class is not ActionClass.REVERSIBLE_SAFE


def test_gate_takes_no_model_input_by_construction() -> None:
    # Invariant #2c: the gate cannot be handed cognition. classify() has no
    # model/provider parameter, so a resolved model cannot influence the verdict.
    import inspect

    sig = inspect.signature(ReversibilityGate.classify)
    params = set(sig.parameters) - {"self"}
    assert params == {"action", "operator_reachable"}


def test_gate_import_chain_is_stdlib_only() -> None:
    """Operator ruling 2026-07-30: the automerge tier-policy guard imports
    classify_action on the referee workflow's bare python3 (no pip install,
    no pydantic). A third-party import anywhere in the gate's chain breaks
    the referee evaluation — pin the property by importing with pydantic
    blocked in a fresh interpreter."""
    import subprocess
    import sys
    import textwrap

    probe = textwrap.dedent(
        """
        import builtins
        real_import = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name == "pydantic" or name.startswith("pydantic."):
                raise ImportError("pydantic blocked: gate must stay stdlib-only")
            return real_import(name, *args, **kwargs)
        builtins.__import__ = guarded
        from dharma_swarm.operator_core.reversibility_gate import classify_action
        decision = classify_action("git status")
        assert decision.may_execute_unattended is True
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr


def test_classification_is_total_and_deterministic() -> None:
    gate = ReversibilityGate()
    samples = [
        "read", "write note", "edit file", "deploy", "delete everything",
        "", "spend $5", "approve lease for self", "trade BTC", "install service",
    ]
    for action in samples:
        d1 = gate.classify(action)
        d2 = gate.classify(action)
        # deterministic
        assert d1.action_class is d2.action_class
        # total: always exactly one of the four classes
        assert d1.action_class in set(ActionClass)
