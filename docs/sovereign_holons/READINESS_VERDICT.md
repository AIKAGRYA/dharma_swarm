# BUILD-READINESS VERDICT — sovereign holon first brick

**Date:** 2026-06-09 · **Method:** 5-lens adversarial gauntlet (spec-executability, verifier-coverage, substrate/step-zero, governance-lane, copy-source-reality) + integrator. 6 agents, ~318k tokens.
**Verdict:** **GO_AFTER_GAPS · 38% ready.** Not safe to start a multi-hour *autonomous* build. The design is strong and research-grade; it is not build-ready.

> The single sentence: **the build would fail at import time** — `living_agent_kernel.py` (the bridge's governance organ) is not in the main repo, and **0 of 6 acceptance criteria have a runnable verifier**, so a long unsupervised build would grade its own homework and declare victory on vibes — the exact failure mode you've been burned by.

## The 6 verified blockers

1. **No buildable home.** `living_agent_kernel.py` (24 classes) is absent from `/Users/dhyana/dharma_swarm`; lives only in two drifted side-copies (`dharma_capital_lab`, `dharma_swarm_lak_e2e`). `external_agent_registration.py` is forked 510 vs 527 lines (identity_invariant logic missing from main). No worktree declared canonical. → bridge fails on first import.
2. **No verifiers.** 0/6 acceptance criteria have a runnable green-condition. Criterion 3 is a negative assertion with no instrumentation; criterion 6 checks file-existence, not test-pass. → autonomous build self-judges "done."
3. **Spec contradiction on the first agent.** `02_FIRST_BRICK_SPEC` recommends opus_composer; `05_RECONCILED_PLAN` mandates merge_master_mike. An autonomous agent cannot pick. (merge_master_mike is the stronger default-deny choice.)
4. **Governance non-goal collision.** Active track forbids "a new daemon, database, event log, truth store, or receipt system" and broad refactor of `agent_runner.py`. The plan's per-turn receipts + `holon_witness/` tree may violate this — unresolved whether they're new owners (forbidden) or projections over existing `spine.EvidenceReceipt` / `runtime_state.RuntimeReceipt` (allowed).
5. **No declared lane.** Holon work has zero lane registration in `ACTIVE_TRACK.yaml`; current branch is `qwen/spine-adoption` (a different lane). Committing here violates lane isolation.
6. **~15 unspecified contracts.** Confirmation-token flow (criterion 5 is unimplementable without it), artifact schema + refusal format, `PersistentAgent` constructor arg-sourcing, model resolution + Haiku fallback, `AgentSeedResolver` signature, `dgc agent talk` CLI contract. Not codeable-by-guessing.
7. **(scope) Gate fails open.** For a *sovereign* holon, v1 must fail-closed (wire the bridge's own pre-exec gate, or patch `_check_gate` to raise). "Gated" is false until fixed — scope it explicitly in or out.

## Ordered gap-closing checklist (smallest-first)

| # | Step | Effort | Owner |
|---|------|--------|-------|
| 1 | **Declare canonical runtime repo** (write it into `BUILD_STEP_ZERO.md`) | 5 min | **operator** |
| 2 | **Resolve agent-choice contradiction** (pick one; add superseding note to spec) | 5 min | **operator** |
| 3 | **Merge substrate deps** into canonical repo: cherry-pick `living_agent_kernel*.py` + the 17-line `identity_invariant` additions; prove `import dharma_swarm.operator_core.living_agent_kernel` closes | 2–4h forensics + 1–2h merge | claude/codex |
| 4 | **Declare holon lane** in `ACTIVE_TRACK.yaml` (id, owner, dedicated branch/worktree, allowed_surfaces, verification_command, receipt_path); create the worktree | 30 min | operator + claude |
| 5 | **Resolve receipt/daemon non-goal** with the active-track owner (new owner vs projection? session-harness not daemon?) | 1 async review cycle | operator |
| 6 | **Write the 6 verifier commands** into the spec — one runnable, exit-0-on-pass per criterion | 2–3h | claude |
| 7 | **Fill the ~15 unspecified contracts** (token flow, artifact schema, constructor args, model routing, resolver signature, CLI contract) | 3–5h | claude + operator decisions |
| 8 | **Gate-hardening decision** (fail-closed in v1, or explicit out-of-scope note + criterion) | 1–2h or a note | operator |

## Scope (honest — "copy" was really "reimplement")

Of the 6 organs: 1 works as-shipped (model routing), 2 exist but don't enforce (gate, autonomy_policy), 2 need full reimplementation (Managed-Agents-style bridge, Live-SWE-agent self-evolution), 1 is missing (living_agent_kernel).
- **First brick** (bridge alone, v1 read-only): **8–16 hours** once gaps 1–7 are closed.
- **"Sovereign within the banks"** (bridge + real enforcement / PDP): **3–4 weeks** sequential.
- No blocking *code* dependencies — the work is integration + gate hardening, not invention.

## Recommended first action
Operator makes the two zero-cost decisions in one sitting — (1) canonical repo, (2) first agent (recommend **merge_master_mike**) — written into `BUILD_STEP_ZERO.md`. Those unblock the substrate merge + spec-hardening that everything else depends on. **Do not start the autonomous build until step 3 (import chain closes) and step 6 (verifiers written) are green.**
