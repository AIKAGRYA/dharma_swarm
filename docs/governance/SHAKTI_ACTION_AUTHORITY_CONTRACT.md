# SHAKTI Action Authority Contract

Status: PR-S0 contract only. This document does not implement enforcement.

## Current Anchors

- `SHAKTI_QUESTIONS` is a `DharmaKernel.MetaPrinciple`, not a `TelosGatekeeper` core gate:
  `dharma_swarm/dharma_kernel.py:29`, `dharma_swarm/dharma_kernel.py:74`,
  `dharma_swarm/telos_gates.py:221`.
- The current formal Shakti constraint is
  `significant_action requires shakti_check >= 2_of_4` with severity `medium`:
  `dharma_swarm/dharma_kernel.py:345`, `dharma_swarm/dharma_kernel.py:346`.
- `PrincipleSpec.structured_predicate` exists for deterministic metadata checks:
  `dharma_swarm/dharma_kernel.py:80`, `dharma_swarm/dharma_kernel.py:83`.
- `PolicyCompiler` maps `critical` to `block`, `high` to `warn`, and `medium` to `log`:
  `dharma_swarm/policy_compiler.py:35`.
- `Policy.check_action()` blocks only rules whose enforcement level is `block`:
  `dharma_swarm/policy_compiler.py:85`, `dharma_swarm/policy_compiler.py:132`.
- Generic `StructuredPredicate` is one flat field comparison and treats missing fields
  as non-violating: `dharma_swarm/structured_predicate.py:32`,
  `dharma_swarm/structured_predicate.py:61`.
- `ActionExecution` currently carries execution metadata through fields including
  `input_params`, `gate_results`, and `executed_by`: `dharma_swarm/ontology.py:210`.
- The Shakti wiki upgrades the target from a count check to
  `significant_action requires valid_action_authority_case`:
  `/Users/dhyana/Desktop/dharma-wiki/concepts/shakti-action-authority-case.md:39`.
- The wiki says Shakti is an action-authority layer and its four powers are
  inseparable dimensions: `/Users/dhyana/Desktop/dharma-wiki/concepts/shakti-quadrature.md:48`.

## Predicate

Recommended signature:

```python
def shakti_action_authority_predicate(action: ActionExecution) -> bool:
    """Return True when the action has a risk-scaled authority case."""
```

Contract result:

- `True`: the significant action has enough authority evidence for its risk level.
- `False`: the action is significant but lacks the required authority case.
- Non-significant actions may return `True` without requiring a full case.

The predicate must be deterministic. It may inspect only action metadata, not call
models, clocks, networks, subprocesses, or mutable global state.

## Metadata Contract

The predicate reads this metadata from `ActionExecution.input_params` unless a
future typed field is added to `ActionExecution`:

```python
{
    "is_significant_action": bool,
    "risk_level": "low" | "medium" | "high" | "critical",
    "action_authority_case": {
        "maheshwari_scope": str,
        "mahakali_refusal_scan": list[str],
        "mahalakshmi_impact_scan": str,
        "mahasaraswati_execution_plan": str,
        "witness_reference": str | None,
    },
}
```

Minimum floors:

- `low`: `mahasaraswati_execution_plan`.
- `medium`: `mahasaraswati_execution_plan`, `mahalakshmi_impact_scan`.
- `high`: medium fields plus `maheshwari_scope` and `mahakali_refusal_scan`.
- `critical`: high fields plus `witness_reference`.

`shakti_check_count` is deprecated compatibility metadata. A count can be logged,
but it must not satisfy the predicate by itself.

## Enforcement Recommendation

Recommend a named Shakti evaluator bound by `PolicyCompiler`, not severity-only
promotion.

Reasoning:

- Promoting the axiom from `medium` to `high` only maps to `warn`, not `block`:
  `dharma_swarm/policy_compiler.py:35`.
- Promoting it to `critical` would block, but overloads severity with a predicate
  binding decision instead of saying why Shakti is special.
- The generic predicate format is too shallow for a risk-scaled nested authority
  case and fails open on missing fields: `dharma_swarm/structured_predicate.py:32`,
  `dharma_swarm/structured_predicate.py:61`.
- A named evaluator keeps Shakti separate from `TelosGatekeeper.CORE_GATES` while
  allowing `valid_action_authority_case` to block autonomous significant actions.

Follow-on implementation should add a failing-closed named evaluator and compiler
binding for `SHAKTI_QUESTIONS`. Human-in-the-loop runs may start at warn while the
operator calibrates; autonomous significant actions should fail closed after the
binding lands.

## PR-S0 Tests

Tests should assert:

- `shakti_action_authority_predicate` exists.
- A significant high-risk action without `mahakali_refusal_scan` is rejected.
- A significant critical action without `witness_reference` is rejected.
- `PolicyCompiler` changes `allowed` to `False` for autonomous significant-action
  predicate failure after the binding lands.
