# Model Routing Semantic Commons Guard

This routing consolidation branch does not own the canonical
`docs/ontology/SEMANTIC_COMMONS.md`, `semantic_aliases.yaml`, or
`semantic_objects.yaml` files. Until those ontology files are reconciled into
this worktree, this document is the branch-local guard for model-routing naming
discipline.

## Required Concepts

The model-routing surface must preserve these Semantic Commons concepts:

- `ModelKeyRouting`
- `DKeysKeyStore`
- `RuntimeProvider`
- `ModelHierarchy`
- `ProviderPolicyRouter`
- `ModelRouter`
- `RoutingMemory`

## Forbidden Aliases

The branch must not introduce these deprecated or misleading names as live
architecture:

- `parallel model routing layer`
- `project .env keys`
- `direct provider factory`
- `scattered model order`

## Local Enforcement

`tests/test_model_key_routing_guard.py` enforces this branch-local guard when
the target worktree does not contain the canonical ontology files. It also
blocks new model literals outside approved registries and new raw provider-key
reads outside the key registry.
