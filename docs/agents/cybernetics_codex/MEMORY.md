# MEMORY - cybernetics_codex

Newest entries first.

## 2026-06-13 - Seed and registration packet

- Created the repo-native nest at `docs/agents/cybernetics_codex/`.
- Bound the steward to the existing Stage-1 external registration desk, not a new registry.
- Declared `A2AInboxRoute` / `agent-inbox` at `dharma.agent.cybernetics_codex.inbox`, with `runtime_status: declared_not_started`.
- Authority remains `external_worker_evidence_only`; no source writes, provider calls, spend, live external account action, PR approval, or autonomous dispatch.
- Primary verifier: `python3 scripts/governance/cybernetics_codex_audit.py --json`.

## Standing Context

The original campaign thread is the "13-Loop Wiring" prompt. Its backbone is:

- The 13 named loops.
- The closure definition: sense -> interpret -> constrain -> act -> adapt on real data, receipts at every transition, automated replay check.
- Loop 1 as the trunk hypothesis, to be verified rather than assumed.
- The One Wire invariant: internal artifacts never touch archive fitness; only countersigned external acted receipts above quorum do.
- Receipts before claims.
