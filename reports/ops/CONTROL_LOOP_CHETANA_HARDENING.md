# Control Loop Chetana Hardening

Date: 2026-04-28
Branch: feature/control-loop-hardening-chetana
Base: origin/main@1e5f35d

## Summary

This slice hardens Dharma Control Loop v0.1 in two narrow ways:

1. Persisted runtime context bundles are still injected into AgentRunner prompts,
   but are now explicitly framed as continuity evidence rather than authority and
   fenced inside a runtime-context tag.
2. IdentityMonitor Research Momentum now includes chetana atom health from the
   existing `.dharma/knowledge` markdown tree: trusted/staged atom volume,
   atom recency, and trusted-atom `stale_after` freshness.
3. Persisted context bundles are scanned with the existing injection scanner
   before prompt injection, and Guardian warns when recent `context_bundles`
   contain prompt-injection signatures.

## Why

The v0.1 control loop made action inherit persisted runtime context. The first
hardening gap was prompt authority: persisted context should inform an agent
without becoming an instruction channel. The second gap was the fusion-plan
finding that TCS/RM did not see chetana, even though chetana is the substrate
where witness-memory leaves durable atoms.

## Files Changed

- `dharma_swarm/agent_runner.py`
  - Wraps persisted context bundle text with an explicit evidence-not-authority
    instruction and `<runtime_context_bundle>` fence.
  - Sanitizes suspicious persisted bundle content with the existing
    `injection_scanner` before prompt construction.
- `dharma_swarm/identity.py`
  - Adds a filesystem-based chetana RM signal.
  - Does not import `dharma_swarm.chetana`, because chetana currently lives in a
    sibling checkout and the canonical signal is the `.dharma/knowledge` tree.
- `dharma_swarm/guardian_crew.py`
  - Adds a LEDGER_WATCHER warning for recent `context_bundles` whose rendered
    text matches prompt-injection scanner rules.
- `tests/test_agent_runner.py`
  - Asserts the context-bundle prompt boundary is present.
  - Asserts injected persisted bundle content is blocked before reaching the
    prompt.
- `tests/test_guardian_crew.py`
  - Asserts Guardian detects injected persisted context bundles.
- `tests/test_identity_v2.py`
  - Asserts recent chetana atoms raise RM signal.
  - Asserts stale old chetana atoms produce a low RM signal.

## Out Of Scope

- No memory_fact promotion.
- No chetana package import or vendoring.
- No dashboard, provider routing, operator_actions, Darwin redesign, or ontology
  expansion.
- No hard gate beyond the existing v0.1 soft context gate.

## Verification

Passed:

```bash
git diff --check
python -m pytest tests/test_agent_runner.py::test_build_prompt_injects_persisted_context_bundle tests/test_identity_v2.py::TestRMFiltered -q --tb=short
python -m pytest tests/test_identity.py tests/test_identity_v2.py -q --tb=short
python -m pytest tests/test_agent_runner.py::test_build_prompt_injects_persisted_context_bundle -q --tb=short
python -m compileall dharma_swarm tests
python -m pytest tests/test_bootstrap_loops.py tests/test_runtime_state.py tests/test_guardian_crew.py tests/test_dgm_loop.py tests/test_identity.py tests/test_identity_v2.py tests/test_agent_runner.py::test_build_prompt_injects_persisted_context_bundle -q --tb=short
python -m pytest tests/test_agent_runner.py::test_build_prompt_injects_persisted_context_bundle tests/test_agent_runner.py::test_build_prompt_blocks_injected_context_bundle tests/test_guardian_crew.py tests/test_identity.py tests/test_identity_v2.py -q --tb=short
```
