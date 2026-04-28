# Dharma Control Loop v0.2 Spec

Date: 2026-04-28
Base: PR #48 / `feature/control-loop-hardening-chetana`
Status: implementation-ready spec

## 1. Thesis

Dharma Control Loop v0.1 made canonical action context-bearing:

runtime state -> context bundle -> AgentRunner prompt -> Guardian visibility

v0.2 should make that context path trustworthy enough to become stricter without
turning it into a new substrate. The next move is not "more memory". The next
move is authority separation, provenance checking, and graduated enforcement
around the existing `context_bundles`, `task_claims`, `delegation_runs`,
`artifact_records`, `SessionLedger`, and Guardian surfaces.

The practical rule:

Persisted context is evidence. It is not authority. Authority remains with the
system prompt, Telos/Dharma gates, operator intent, and current task contract.

## 2. External Security Grounding

OWASP describes the core prompt-injection failure as instructions and data
being processed together without clear separation, and recommends structured
prompt separation, input validation/sanitization, output monitoring, least
privilege, and comprehensive monitoring:
https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html

OWASP LLM01:2025 notes that prompt injection can affect models even when the
attack is not human-visible, and that RAG/fine-tuning do not fully mitigate the
class:
https://genai.owasp.org/llmrisk/llm01-prompt-injection/

OpenAI safety guidance recommends adversarial testing, human-in-the-loop review
for high-stakes actions, and constraining inputs/outputs to reduce misuse:
https://platform.openai.com/docs/guides/safety-best-practices/preventing-prompt-injection

OpenAI's prompt-injection explainer frames modern risk as third-party content
entering model context and misleading the model:
https://openai.com/safety/prompt-injections/

Applied to Dharma Swarm:

- `ContextCompiler` aggregates runtime state, memory, recall, artifacts, and
  workspace excerpts.
- `AgentRunner` injects the persisted bundle into the model prompt.
- Therefore `context_bundles.rendered_text` must be treated as untrusted
  evidence even when it was produced by the swarm.
- Guardian must watch the stored context path, not only the dispatch path.

## 3. Current Load-Bearing State

Already live after v0.1 and PR #48:

- `Orchestrator._assign_dispatch()` soft-compiles a `ContextCompiler` bundle
  during canonical dispatch.
- `task.metadata` and dispatch metadata carry `context_bundle_id`.
- `RuntimeLifecycle.runtime_metadata()` propagates context metadata into
  `task_claims` and `delegation_runs`.
- `RuntimeStateStore.get_context_bundle_sync()` lets synchronous prompt
  construction read persisted bundles.
- `AgentRunner._build_prompt()` injects persisted bundle text under
  `## Runtime Context Bundle`.
- PR #48 frames the bundle as continuity evidence, not authority, and fences it
  inside `<runtime_context_bundle>`.
- PR #48 scans persisted bundle text with the existing `injection_scanner`
  before prompt injection.
- `GuardianCrew.run_ledger_watcher()` warns when claims/runs lack context or
  when recent context bundles match injection signatures.
- `DGM_TARGET_FILES` excludes Telos/Dharma/evolution boundary files.
- `IdentityMonitor._measure_rm()` reads chetana atom health from the existing
  `.dharma/knowledge` tree.

This is enough spine to harden. No new database, no new ledger, and no new
memory substrate are required for v0.2.

## 4. Threat Model

### A. Context poisoning

An attacker or broken agent writes malicious content into a memory source,
artifact, session event, workspace excerpt, or chetana atom. `ContextCompiler`
later includes that text in `context_bundles.rendered_text`, and `AgentRunner`
injects it.

### B. Authority confusion

The model treats persisted context as a command channel rather than evidence.
This is especially dangerous because context bundles include old work and
retrieved recall that may look like instructions.

### C. Silent context bypass

Canonical dispatch writes claims/runs but no context bundle, or a context bundle
exists but is not readable by the prompt path.

### D. Evolution boundary corruption

Darwin/DGM mutates code that judges, gates, or records evolution itself.

### E. Measurement drift

TCS/RM remains blind to the knowledge substrate, so the organism cannot sense
whether its verified memory is fresh, stale, or growing.

## 5. v0.2 Invariants

1. Every canonical dispatch should have a `context_bundle_id` unless a soft-gate
   failure is explicitly recorded.
2. Every AgentRunner prompt that consumes a bundle must keep the bundle fenced
   and demoted to evidence.
3. Any context bundle with prompt-injection signatures must be blocked or
   replaced before prompt injection.
4. Guardian must detect:
   - recent claims/runs with no context bundle,
   - recent context bundles with injection signatures,
   - context bundle compile failures crossing a threshold.
5. Telos/Dharma/Governance boundary files must remain outside DGM mutation
   targets.
6. TCS/RM should include chetana health only as an additive signal, and must
   fail open when `.dharma/knowledge` is absent.

## 6. Implementation Slices

### Slice A - PR #48: context-boundary hardening

Implemented:

- Prompt-boundary evidence framing.
- Prompt-boundary injection scan.
- Guardian context-bundle injection warning.
- Chetana atom health signal in RM.

Remaining PR #48 acceptance:

- CI must be green, including `module-budget`.
- No direct import of sibling chetana code.
- No hard dispatch gate yet.

### Slice B - compile-time context scan metadata

Goal:

`ContextCompiler.compile_bundle()` should scan the rendered bundle before
persisting it and store scan metadata on the bundle:

```json
{
  "context_scan": {
    "status": "clean|blocked|scanner_unavailable",
    "findings": [],
    "scanner": "dharma_swarm.injection_scanner.scan_content"
  }
}
```

Rules:

- Store metadata only; do not add columns.
- Continue to persist the bundle in v0.2, but mark it.
- `AgentRunner` remains the prompt-boundary enforcement point.
- Guardian should prefer stored scan metadata when present, and fall back to
  scanning `rendered_text` for older bundles.

Tests:

- clean bundle gets `context_scan.status=clean`.
- injected bundle gets `context_scan.status=blocked`.
- Guardian reads metadata and does not need to rescan when metadata exists.
- AgentRunner still blocks even if metadata lies or is absent.

### Slice C - context compile failure threshold

Goal:

Guardian should warn when recent dispatches repeatedly record
`context_bundle_status=failed` or `missing_runtime_state`.

Data source:

- `task_claims.metadata_json`
- `delegation_runs.metadata_json`
- existing `context_bundle_failed` session events

No new table is needed.

Suggested rule:

- `>= 1` recent failure: WARNING.
- `>= 5` recent failures in 24h: DEGRADED.
- `>= 20` recent failures in 24h: BLOCKER.

Tests:

- one failed metadata row produces WARNING.
- five failed rows produce DEGRADED.
- attached bundles suppress the warning.

### Slice D - hard gate readiness metric, not hard gate

Do not hard-block dispatch yet. v0.2 should compute readiness for a future hard
gate:

```text
context_gate_readiness =
  recent_dispatches_with_context_bundle /
  recent_canonical_dispatches
```

Guardian should report if readiness falls below a threshold, but dispatch should
remain soft-gated in v0.2.

Why:

The v0.1/v0.2 path is still young. A hard gate would risk breaking live LF5
runtime behavior before the failure modes are sufficiently observed.

### Slice E - DGM boundary CI assertion

Goal:

Keep the protected-file list from regressing.

Add a small governance or DGM test that asserts:

- `telos_gates.py`
- `dharma_kernel.py`
- `evolution.py`
- `config.py`

are excluded from `DGM_TARGET_FILES`, and explicit mutation requests for those
files are rejected. The current tests cover this. CI should keep them in a
targeted suite.

## 7. Non-Goals

Do not include in v0.2:

- memory_fact promotion,
- artifact-to-memory distillation,
- Obsidian / LLM Wiki / QMD / Graphify,
- dashboard UX changes,
- provider routing changes,
- operator_actions enforcement,
- Darwin proposal lifecycle redesign,
- identity unification,
- new database tables,
- new ledger,
- vendoring sibling chetana code into main.

## 8. Why This Is the Highest-ROI Lane

Context bundles are now on the model's decision surface. That means their
trust boundary matters immediately. Hardening that boundary is more urgent than
expanding memory or UI, because every future memory/dashboard/evolution feature
will eventually flow through this same prompt path.

The core transformation is:

Before:

state existed, and some of it reached prompts.

After v0.2:

state reaches prompts through an explicit evidence boundary, is scanned at the
prompt edge, is watched by Guardian, and can become eligible for future hard
gating without relying on the human as the message bus.

## 9. Review Checklist

Before merging v0.2 slices:

- `python -m compileall dharma_swarm tests`
- `python -m pytest tests/test_bootstrap_loops.py tests/test_runtime_state.py tests/test_guardian_crew.py tests/test_dgm_loop.py tests/test_injection_scanner.py tests/test_identity.py tests/test_identity_v2.py tests/test_agent_runner.py::test_build_prompt_injects_persisted_context_bundle tests/test_agent_runner.py::test_build_prompt_blocks_injected_context_bundle -q --tb=short`
- `python3 scripts/governance/check_module_budget.py --base-ref <base> --head-ref HEAD`
- GitHub checks: tests, module-budget, structure, test-hygiene, commit-lint,
  gitleaks, semgrep, codeql.

## 10. Sentence Of Truth

Dharma Control Loop v0.2 should make inherited context useful without letting
inherited context become sovereign.

