"""Structural fitness tests for Titanium runtime hardening spines.

These tests intentionally parse source text instead of importing runtime modules so
Phase-0/Titanium guardrails remain runnable on clean hosts whose system Python may
not match the repo's runtime interpreter. They protect campaign invariants from
regressing while the runtime packet implementations proceed.
"""
from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR = REPO_ROOT / "dharma_swarm" / "orchestrator.py"
RUNTIME_PLAN = REPO_ROOT / "docs" / "plans" / "TITANIUM_RUNTIME_HARDENING_WPS_2026-07-17.md"
EXECUTOR_PROMPT = REPO_ROOT / "docs" / "prompts" / "TITANIUM_HARDENING_EXECUTOR_SPINES_2026-07-17.md"
AUTHORITY_PLAN = REPO_ROOT / "docs" / "plans" / "TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tree(path: Path) -> ast.Module:
    return ast.parse(_source(path), filename=str(path))


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _iter_string_constants(tree: ast.AST) -> list[str]:
    values: list[str] = []
    for node in ast.walk(tree):
        value = _constant_string(node)
        if value is not None:
            values.append(value)
    return values


def test_tit020_orchestrator_retry_cleanup_must_not_wipe_idempotency_key() -> None:
    """TIT-020 guard: retry identity cleanup must preserve the intent key.

    Earlier audit evidence found an attempt-cleanup list/helper deleting
    ``idempotency_key`` before retry. That made every retry mint a fresh key and
    defeated durable dedupe. On this branch the old helper/list has drifted away;
    this structural guard keeps it from returning under any name.
    """
    tree = _tree(ORCHESTRATOR)
    source = _source(ORCHESTRATOR)

    # The old regression anchor should not exist, and if a future attempt-cleanup
    # list/helper is reintroduced it must not contain the durable intent key.
    assert "_ATTEMPT_IDENTITY_METADATA_KEYS" not in source

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            target_names = [t.id for t in targets if isinstance(t, ast.Name)]
            if any("ATTEMPT" in name and "IDENTITY" in name for name in target_names):
                assert "idempotency_key" not in _iter_string_constants(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and "clear" in node.name.lower() and "identity" in node.name.lower():
            assert "idempotency_key" not in _iter_string_constants(node)

    # Direct mutation patterns that remove the key from metadata are forbidden.
    forbidden_fragments = (
        '.pop("idempotency_key"',
        ".pop('idempotency_key'",
        'del metadata["idempotency_key"]',
        "del metadata['idempotency_key']",
        'del td.metadata["idempotency_key"]',
        "del td.metadata['idempotency_key']",
    )
    for fragment in forbidden_fragments:
        assert fragment not in source


def test_frontier_capacity_doctrine_forbids_cost_based_model_downgrade() -> None:
    """The campaign must preserve frontier-capacity-first semantics.

    WP-A/Spine-A is an authorization/accountability rail, not a cost-minimizing
    router. This protects the user's explicit correction from being diluted by
    future docs or executor prompts.
    """
    runtime_plan = _source(RUNTIME_PLAN)
    executor_prompt = _source(EXECUTOR_PROMPT)
    authority_plan = _source(AUTHORITY_PLAN)

    assert "FrontierCapacityGate" in runtime_plan
    assert "WP-A is not a cost-minimization program" in runtime_plan
    assert "preserve maximum useful model quality and context" in runtime_plan
    assert "must not downgrade frontier model choice" in runtime_plan
    assert "must not automatically downgrade model quality" in executor_prompt
    assert "without downgrading authorized frontier lanes" in authority_plan

    prohibited = (
        "CostGate",
        "global LLM cost gate",
        "cost-minimizing router",
        "downgrade-to-cheaper-model policy",
    )
    combined = "\n".join((runtime_plan, executor_prompt, authority_plan))
    for phrase in prohibited:
        assert phrase not in combined
