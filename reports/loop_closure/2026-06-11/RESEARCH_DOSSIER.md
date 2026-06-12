# Loop Closure Campaign — Phase 0 Research Dossier

**Role:** report (dated descriptive output, per docs/AGENTS.md doc types)
**Track:** `loop-closure-2026-06` (declared in `docs/governance/ACTIVE_TRACK.yaml`)
**Date:** 2026-06-11
**Author:** Devin session 863663ec (operator-instructed master prompt: "wire all 13 loops together")
**Authority:** none. This dossier projects truth from owners (`CYBERNETIC_LOOP_MAP.md`, code, fresh command receipts); it does not become authority.

---

## 1. Mission restated

Wire all 13 cybernetic loops (per root `CYBERNETIC_LOOP_MAP.md`) until each runs
sense → interpret → constrain → act → adapt on real data, with receipts to its
declared owner surface and an automated closure check a fresh agent can run.
No build code before this dossier — that was the operator's mandate.

## 2. Fresh re-audit — what this box can and cannot verify

**Custody finding first (binding on everything below):** the loop map's
production evidence (1,013 witness entries, 89 organism_memory entities,
182 traces, 39 routing decisions) lives in `~/.dharma/` **on the operator's
machine**. On this Devin VM, `~/.dharma/` is 520K and contains only
`state/runtime.db` + `ops/` (receipt: `du -sh ~/.dharma` → 520K, 2026-06-11).
So this dossier distinguishes:

- **[box-verified]** — reproduced fresh on this VM, 2026-06-11.
- **[operator-box evidence]** — from the map's last audit (2026-05-20 header,
  2026-05-05 data audit); structurally plausible, not re-verifiable from here.

Fresh receipts gathered on this box:

| Receipt | Command | Result |
|---|---|---|
| Provider lanes all dead | `.venv/bin/dgc provider-smoke` | ollama `unreachable` (connection failed, localhost:11434); nvidia_nim `missing_config` (NVIDIA_NIM_API_KEY not set); openrouter `missing_config` (OPENROUTER_API_KEY not set). 0/3 lanes live. |
| Anthropic/OpenAI lanes also keyless | `env` scan + `dharma_swarm/providers.py:240,307` | Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY set in this environment. |
| Core state empty | `.venv/bin/dgc status` | Memory 0 entries, pulse never run, 0 gate checks today, AGNI workspace NOT SYNCED. |
| Ecosystem operator-coupled | `.venv/bin/dgc health` | **1 OK, 78 MISSING** paths — the ecosystem map hardcodes the operator's Mac filesystem (`~/agni-workspace/`, `~/trishula/`, `~/Library/Mobile Documents/...`). Portability finding: the organism's nervous system currently assumes one specific machine. |
| Loop supervisor never ran here | `.venv/bin/dgc loop-status` | "No loop supervisor state yet. Start the orchestrator to generate data." |
| dispatch_dropoff located & understood | read `dharma_swarm/orchestrator.py:2145-2160` | Fires when `pool.get(agent_id)` returns no runner. Requeue-once policy exists at `:635,:708`. Test `tests/test_orchestrator.py:1076` covers it. **Operational gap, not a code bug** — matches the map's own key finding. |
| Spine dispatch path exists but default OFF | `orchestrator.py:2164-2176` | `_run_task_via_spine` (one EvidenceReceipt per dispatch) gated by `DHARMA_SPINE_DISPATCH=1`, default off. Loop 1 closure should turn this ON so closure is receipted through the spine, serving the runtime-truth-reconciliation track rather than bypassing it. |
| Supervisor mechanism read | `dharma_swarm/loop_supervisor.py:1-60,127-270` | Pure-Python watchdog; ladder LOG_WARNING → PAUSE_LOOP → REDUCE_SCOPE → ALERT_DHYANA; stall = stale > 2× expected interval; per-loop LoopHealth with stagnant_cycles. This is the existing multi-loop stability owner — extend, don't duplicate. |
| Live entrypoint identified | `dharma_swarm/orchestrate_live.py` | Single asyncio process runs swarm tick (60s), pulse, evolution, health, living loops; drains signal bus pre-tick; watchdog wired at `:330-335`. This is where "all 13 together" actually executes. |

### 2.1 Fresh 13-loop status table

Statuses below = map's 2026-05-20 audit, annotated with what this box could
independently confirm. **No loop status got BETTER since the map; the map's
statuses are not stale-optimistic, they are stale-accurate-or-worse** (nothing
has run since; the census receipt machinery confirms no live processes here).

| # | Loop | Map status | Box re-audit 2026-06-11 |
|---|------|-----------|--------------------------|
| 1 | Swarm Task (60s) | NO | [box-verified] provider chain 0/3 live; dispatch path read; code structurally sound; gap is operational (no AgentRunner + no provider key). |
| 2 | Organism Heartbeat (300s) | PARTIAL | [operator-box evidence] 5 heartbeat cycles, 48 algedonic events, 18 gnani verdicts. Act/adapt blocked on running agents. Not reproducible here (no state). |
| 3 | Evolution (every 3rd tick) | PARTIAL | [operator-box evidence] 3 meta_archive entries, fitness 0.58494. Needs real task fitness (Loop 1). |
| 4 | Consolidation | PARTIAL | [operator-box evidence] 89 organism_memory entities; nothing agent-produced to consolidate. |
| 5 | Zeitgeist Scanner | PARTIAL | [operator-box evidence] local scanning works; no real gate-check data flowing. |
| 6 | Witness Auditor (3600s) | YES (in test) | [operator-box evidence] 1,013 entries; PASSED 444 / BLOCKED 230 / WARN 4; AHIMSA blocked destructive commands. Code path read — will audit real actions when Loop 1 closes. |
| 7 | Training Flywheel (300s) | PARTIAL | [operator-box evidence] 182 traces, 5+ quality-gate evaluations — all from test fixtures. |
| 8 | Recognition (7200s) | PARTIAL | [box-verified code] seed wiring present: `cascade.py:386-491`, `shakti_executive/inputs.py:100`, read by `meta_daemon.py`. Periodic trigger awaits LoopEngine schedule activation. |
| 9 | Conductors (120s) | PARTIAL | [operator-box evidence] 7 cron jobs tracked, pulse 3 runs / 0 failures. Blocked on provider. |
| 10 | Context Agent (60s) | NO | Depends entirely on Loop 1. |
| 11 | Replication Monitor (3600s) | PARTIAL | Structurally correct; no completed tasks → never triggered. |
| 12 | Self-Improvement (3600s) | NO | DarwinEngine instantiable; needs `DHARMA_SELF_IMPROVE` env + provider chain. Gated behind One Wire in Phase 3 (see §5). |
| 13 | Free Evolution Grind (600s) | NO | [box-verified] all providers fail — reproduced exactly the map's three failure modes via provider-smoke. |

### 2.2 Dependency lattice (verified, not inherited)

The map's claim that Loop 1 is the trunk **holds** under code reading:

```
provider key ──► Loop 1 (Swarm Task)
                   │ first task completes
                   ├──► Loop 6 Witness (audits real actions immediately)
                   ├──► Loop 2 Heartbeat act/adapt (agents now running)
                   ├──► Loop 5 Zeitgeist, Loop 9 Conductors  (first-task tier)
                   │ ~10 tasks
                   ├──► Loop 3 Evolution, Loop 4 Consolidation, Loop 7 Flywheel
                   │ ~100 tasks + stability
                   └──► Loop 8 Recognition eigenform, Loops 10/11
Loop 12/13 (self-modification) ──► additionally gated behind the One Wire
                                   (external receipt quorum N≥5, M≥3)
```

One refinement over the map: Loops 12/13 must NOT close merely when the
provider chain works. Per the Forge/Hydra invariant
(`docs/ops/DHARMA_FORGE_HYDRA_ARCHAEOLOGY_2026-06-11.md:242,265`), archive
fitness may only move on countersigned external acted receipts above quorum.
Self-modification without that gate is the named historical failure mode
(nine Hydra generations of internal-artifact churn).

## 3. External research findings (with receipts)

### 3.1 Self-improvement with archives — DGM
- Darwin Gödel Machine: self-modifying coding agents + archive of diverse
  stepping stones; SWE-bench 20.0%→50.0%, Polyglot 14.2%→30.7%. The winning
  mechanism is the archive (parallel exploration of diverse high-quality
  agents), which is structurally the repo's Transcendence Principle.
  https://arxiv.org/html/2505.22954v3 · code: https://github.com/jennyzzt/dgm
- Implication for Loops 3/12/13: empirical validation per change (benchmarks
  in DGM ↔ external acted receipts here) is the only thing standing between
  self-modification and Goodhart collapse.

### 3.2 Goodhart / reward hacking (why the One Wire invariant is load-bearing)
- "Reward Hacking as Equilibrium under Finite Evaluation": under five minimal
  axioms, any optimized agent structurally under-invests in unevaluated quality
  dimensions; hacking is an equilibrium, not a bug; agentic systems make
  coverage decline toward zero as tool count grows.
  https://arxiv.org/pdf/2603.28063
- Skalse et al., "Defining and characterizing reward hacking" (NeurIPS 2022):
  unhackable proxies are essentially impossible for stochastic policies.
  https://dl.acm.org/doi/10.5555/3600270.3600957
- Implication: internal fitness signals (test passes, self-evaluations) WILL
  be gamed under optimization pressure. The Guardian's external-receipt quorum
  is the correct counter; never let internal artifacts touch archive fitness.

### 3.3 Provider chain reliability (Phase 1 design inputs)
- Fallback Chain pattern (ordered handlers; confident-answer-or-fail signal;
  final fallback is honest "no answer", never a wrong answer):
  https://www.agentpatternscatalog.org/patterns/fallback-chain/
- Agent circuit-breaker spec: 3-state per-dependency breakers scoped per
  (provider, model, region); trigger on error rate + latency; retries INSIDE
  the breaker, never around it: https://geodocs.dev/ai-agents/agent-circuit-breaker-spec
- resilient-llm-router: rate-limit / quota / circuit health tracked as three
  ORTHOGONAL states per (provider, model, credential) — "a quota exhaustion is
  not a circuit failure"; decide skips before the call:
  https://github.com/eleata/resilient-llm-router
- Implication: the repo's claude_code `circuit_open` + key-missing failures
  are different state classes and must be reported differently. Phase 1
  should verify `providers.py` separates them (the provider-smoke output
  suggests it partially does: `unreachable` vs `missing_config`).

### 3.4 VSM ↔ multi-agent (the 13 loops in Beer's terms)
- VSG (a live VSM-architected autonomous agent, 800+ cycles):
  https://www.agent.nhilbert.de/
- ViableOS (VSM as the organizational layer for multi-agent systems; S1 talks
  to S2 only, S3* read-only audit): https://github.com/philipp-lm/ViableOS
- CyberneticAgents (AutoGen + Casbin RBAC, S1/3/4/5 as agents):
  https://github.com/simonvanlaak/CyberneticAgents
- Proposed mapping for this repo (to be hardened during Phase 2):
  S1 = Loops 1, 10 (operations); S2 = Loops 9, 11 + signal_bus (coordination/
  anti-oscillation); S3 = Loops 4, 7 (resource/optimization), S3* = Loop 6
  (audit); S4 = Loops 5, 3 (intelligence/adaptation); S5 = Loops 8, 2
  (identity/homeostasis); Loops 12/13 = S4→S5 self-redesign channel, hence the
  strictest gating. Algedonic channel = loop_supervisor's ALERT_DHYANA.

### 3.5 Multi-timescale coupled-loop stability
- Sensitivity-conditioning beyond singular perturbation (interconnected
  subsystems stabilized on separate timescales; preserving stability without
  slowing any subsystem): https://ar5iv.labs.arxiv.org/html/2101.04367
- Mixed feedback (fast positive + slow negative) for stable oscillation
  regimes: https://ar5iv.labs.arxiv.org/html/2110.06900
- Implication: the 60s/120s/300s/600s/3600s/7200s tick spectrum is a
  multi-timescale interconnection. The existing `loop_supervisor.py` ladder is
  the right enforcement point; the Phase 3 soak test must specifically watch
  for retry storms (fast loop) amplified by slow-loop corrections.

### 3.6 Machine-verifiable receipts (One Wire transfer-gate design inputs)
- AERF — Agent Evidence Receipt Format: Ed25519-signed JSON receipts of agent
  actions, independently verifiable with a stdlib-only verifier:
  https://github.com/aerf-spec/aerf
- Agent Receipts Protocol v0.4.0: W3C Verifiable-Credential-modeled, hash-
  chained tamper-evident receipt chains: https://agentreceipts.ai/spec/v0.4.0/
- Agent Action Receipt spec: https://github.com/Cyberweasel777/agent-action-receipt-spec
- Implication: "Guardian-confirmed external acted receipt" has existing open
  wire formats. SAB/dharmic-agora already runs Ed25519 identity + a
  hash-chained witness ledger — the One Wire's receipt format should converge
  with that, not invent a fourth scheme.

## 4. Honest constraints discovered

1. **Provider key is an operator decision** — no key of any kind exists in
   this environment. Phase 1, step 1 is blocked on John (named in the master
   prompt's escalation rules; request will offer session-only vs saved-secret).
2. **Production state is on the operator's box** — final closure receipts for
   "in production" must come from wherever the organism actually runs (John's
   Mac / VPS), not this VM. This VM can prove "closes with a live provider";
   the operator box proves "closed in production". Division of labor with
   Fable applies.
3. **`dgc health` ecosystem hardcodes one machine** — 78/79 paths missing on
   any fresh box. Not a Phase-1 blocker, but a finding the campaign should
   register (candidate BR entry) since "any agent sees the whole system" fails
   at the ecosystem layer.
4. **`DHARMA_SPINE_DISPATCH` default OFF** — closing Loop 1 without flipping
   this on would close the loop around the spine instead of through it,
   regressing substrate-nativeness. Coordinate with the
   runtime-truth-reconciliation track (it owns operator_core; the flag flip is
   an orchestrator concern — surface ownership check needed before the PR).

## 5. Ordered closure plan (predicted unblock cascade)

- **PR-zero (this PR):** dossier + `loop-closure-2026-06` track declared.
- **PR-1 (Phase 1a):** provider chain hardening — separate the three failure
  state classes per §3.3, fallback-chain ordering, honest provider-smoke
  receipts; no key needed to build/test (fake provider in tests).
  *Escalation to operator:* one real key (OPENROUTER recommended — cheapest
  multi-model lane already first-class in the router).
- **PR-2 (Phase 1b):** Loop 1 closure — AgentRunner alive under
  orchestrate_live with the real provider, `DHARMA_SPINE_DISPATCH=1`,
  dispatch_dropoff receipted, closure check added to `make orient`; then the
  100-task honest run with published success/failure counts.
- **PR-3..n (Phase 2):** per-loop closure verification in lattice order
  (6, 2, 5, 9 → 3, 4, 7 → 8, 10, 11), one PR per loop-tier, each adding the
  loop's automated closure check.
- **PR-final (Phase 3):** One Wire (receipt format per §3.6, quorum test
  BEFORE the wire), Loops 12/13 gated behind it, 24h multi-loop soak with
  loop_supervisor receipts.

Each PR: CI-green (24 checks), Coherence Delta, BR pre-flight check per
CLAUDE.md, no telos-gate weakening, all `~/.dharma` access through owners.
