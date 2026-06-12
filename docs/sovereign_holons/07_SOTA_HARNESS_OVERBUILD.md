# SOTA Overbuild — Runnable Shell + Verification + Context-Bridging Harness (June 2026 Frontier)

**Date:** 2026-06-09 · **Driver:** Operator directive to "overbuild whatever it takes" the under-built harness the frontier (and our own dossiers) say actually moves the needle.  
**Scope:** Model-agnostic (100% via runtime_provider + model_hierarchy + identity-declared model), bleeding-edge future-proof, project-only from existing owners (MemoryKernel as canonical context front door, no new authority stores/daemons/receipt systems per active-track axioms and A1–A8).  
**Philosophy:** Harness is the product. Durable external artifacts + separate Evaluator + sleep-time reorg + bi-temporal context + brain/hands decoupling + pass^k + prompt-injection defense + cost/observability/HITL. Anthropic Managed Agents (session/harness/sandbox), Letta sleep-time, Graphiti bi-temporal, τ-bench pass^k + GDS/meltdown, prompt caching / compaction lessons, all baked in as first-class.

**Non-negotiables (burned in):**
- Model-agnostic: Never hard-code a model string. Identity declares it; the shell resolves via `resolve_runtime_provider_config()` → `create_runtime_provider()`. Free-first for sovereigns, Max-plan for Anthropic, live fallback, decorrelated.
- Project only: All durable state is atoms/projections/writes through MemoryKernel surfaces, writers, promotion_gates, write_receipts, conversation_log (with interface), witness, runtime_state, spine receipts. No new top-level `holon_*` authority trees.
- Verification is load-bearing and external: Every outcome claim requires a re-readable artifact (separate process can open + assert). Same-model self-grading is forbidden. pass^k (every run succeeds) + GDS/meltdown instrumentation. Refuse unbacked "done".
- Context-bridging is first-class: Every cycle gets a budgeted, redacted, trust-tagged MemoryContextPack from MemoryKernel. Sleep-time reorg (raw episodic → learned facts/edges) runs on idle via AgentCron + MemoryKernel writers. Compaction, bi-temporal (validity windows via atom metadata + MemoryOrder/Lane), brain/hands/session decoupling (uniform runner interface, sandboxes as cattle, session state in MemoryKernel atoms).
- Prompt-injection defense: Trust-tagging on every atom (`<source:operator>`, `<source:tool:…>`, `<source:memory:surface_id>`). Tool whitelist for holons. No blind web fetch. Secrets redaction in context admission (already in MemoryKernel).
- Future-proof: Pluggable via MemoryKernel adapters, writer specs, promotion gates, context budgets/evals. Versioned schemas. Extensible without forking the shell.
- Hygiene + receipts: Update VC-N* patterns. Every significant step emits operator-visible receipts (projections over existing). Dual-audit / fresh-context / adversarial detonation before any "green".
- Active-track respect: This lane is off the declared runtime-truth-reconciliation track. We declare it explicitly (owner, surfaces, verifiers, receipt paths). Everything projects truth from owners; the harness does not become new authority.

**Frontier alignment (2026-06 sources ingested):**
- Anthropic Managed Agents: session (append-only event log via MemoryKernel + holon_events), harness (the governed loop), sandbox (injected runner). Brain/hands decoupling.
- Letta: sleep-time compute as async memory reorg (raw → learned context).
- τ-bench / Sierra: pass^k as the reliability metric (replaces empty fitness_history).
- arXiv long-horizon (2603.29231 etc.): GDS / meltdown instrumentation; naive memory hurts — therefore budgeted + promoted + bi-temporal only.
- Cognition / "don't build multi-agents": single coherent holon with decorrelated intelligence (different models/roles via the provider door) beats noisy ensembles.
- Prompt caching / NVIDIA Dynamo / compaction: stable prefixes first; variable preambles destroy KV; external compaction artifacts.
- Graphiti / bi-temporal: validity windows, point-in-time, incremental real-time via atom metadata + edges.
- Lethal-trifecta (moltbook): prompt-injection + tool-output poisoning defense is table stakes (trust tags + redaction + whitelists).

---

## Current State (verified 2026-06-09 post-session)

**Runnable shell (partial but real):**
- holon_bridge.py + /holon/{name}/chat: load registered agent from canonical ~/.dharma/agents/ → own model + byte-for-byte active.txt + identity. Streams via the one provider door. Never _agentic_stream. 17+ hardened tests + real-opus_composer smoke (outside CLAUDECODE).
- holon_runtime.py + thin organs (killswitch, budget_guard with real mid-loop spend_fn, compass non-binding, persistence append-only monotonic cycles, health): the loop composes kill → budget → injected work → compass → persist. 74+ tests post-detonation. Injected AgentRunner makes it model-agnostic today.
- PersistentAgent + AgentCronScheduler: skeleton for sleep-time (memory_consolidation every 2h, stigmergy_scan). No real MemoryKernel content yet.
- Gap: not yet wired to full MemoryKernel for durable context packs on every cycle; no brain/hands/session decoupling exposed as first-class; no external-artifact session log by default for the holon.

**Verification (doctrine + thin beginnings, under-built):**
- guard_outcome_claim exists (Step-3 tool boundary) + acceptance criteria in 02_FIRST_BRICK_SPEC demand verifier_artifact for outcome words.
- Witness.py (Viveka S3* sporadic auditor: telos + mimicry + gate, LLM-assisted, publishes to stigmergy + operator memory + signal bus).
- MemoryKernel has context_eval (safety findings, parity), promotion_gates (human + provenance + privacy + canon), write_receipts, burn-in receipts.
- Gap: not wired into the holon wake loop as a mandatory "refuse unbacked done"; no pass^k / GDS / meltdown instrumentation; no external-process re-readable artifact contract enforced on every cycle; most "verification" is still internal detonation.

**Context-bridging harness (strong substrate, missing content + integration):**
- MemoryKernel (the canonical front door): 30+ modules. Atoms (EPISODE, FACT, EDGE, WITNESS_EVENT, EXTERNAL_MEMORY, SOURCE_CHUNK, RETRIEVAL_FEEDBACK, METADATA). Surfaces classified by role/category/authority/risk/write_mode. Context admission (budgets, redaction of secrets/PII, trust tagging ready). preview_memory_pack + render. context_eval + parity + safety. promotion_gates + reviewed canonical receipts. writers with policy + discovery. census + readiness. Adapters over conversation_log, witness, runtime_state, smriti, wiki, codex, memory_plane, etc.
- Witness + conversation_log + runtime_state + spine receipts already live for projections.
- AgentCronScheduler skeleton in PersistentAgent.
- Gap: holon_runtime / bridge not consuming MemoryKernel packs on cycle; sleep-time cron has no real "raw episodic → learned facts/edges" reorg using writers/promotion; no compaction in the wake path; no bi-temporal (validity windows) exposed; no brain/hands/session decoupling contract; no durable external-artifact session for cross-window continuity beyond the thin holon_events.jsonl.

**Overall:** The 2026-06-09 session delivered the thin governed plumbing and the read-only bridge (materially better than cosmetic persona demos). The three frontier-moving areas (runnable shell integration, verification as organ, context-bridging content) remain the exact under-built pieces our own dossiers and the external review called out. The substrate (MemoryKernel + witness + provider door + thin loop) is unusually strong for June 2026 — we are not starting from zero.

---

## Overbuild Architecture (bleeding-edge, model-agnostic, project-only)

**Runnable Shell (model-agnostic holon runtime):**
- Identity (from ~/.dharma/agents/<name>/identity.json + active.txt + living_agent.json + optional registration) declares model + provider.
- Shell (holon_bridge + enhanced holon_runtime + PersistentAgent) resolves provider exclusively via the canonical door.
- Every wake cycle: (1) govern (kill/budget), (2) pull budgeted MemoryContextPack from MemoryKernel (trust-tagged, redacted, admission-checked), (3) inject into runner as `<source:memory:...>` atoms + the task, (4) runner executes (ReAct / tools / sandbox), (5) results written back as atoms (via writers), (6) compass + persist (projection), (7) optional sleep-time reorg on idle cycles.
- Brain/hands/session decoupling: Shell + MemoryKernel = session + harness brain. Injected runner (with sandbox) = hands. Uniform `AgentRunner(name) -> (task, reply)` + context pack contract. Sandboxes are cattle.
- Durable by default: Session state lives as MemoryKernel atoms (episodes, facts, edges, witness events). External artifacts (reviewed canonical receipts, write receipts, conversation_log entries with interface="holon") for crossing context windows and independent audit.

**Verification Harness (external, artifact-first, reliability instrumentation):**
- Mandatory artifact for any outcome claim ("done", "updated", "passed", "created", "fixed", "shipped", etc.). The artifact is a path a separate process can open and assert (diff, test output, receipt JSON, etc.).
- Refusal path: if claim without artifact, replace with logged refusal + violation entry (projection over existing witness / violations patterns).
- pass^k + GDS / meltdown: instrument the loop (or PersistentAgent profile). Track consecutive full successes on the same task. Record GDS (graceful degradation) and meltdown events. Replace empty fitness_history with this.
- Separate Evaluator: context_eval + promotion_gate style + witness sporadic auditor + (optional) decorrelated second model for artifact validation. Never same-model self-grade for fitness/reliability.
- External-process friendly: verifiers are shell commands or small Python entrypoints that take artifact path + expected outcome and exit 0 on pass. Baked into acceptance + CI.
- Dual-audit / fresh-context / detonation: every non-trivial change or phase must survive (a) fresh-context no-write evaluator, (b) adversarial detonation (multiple decorrelated lenses), (c) dual-audit (Claude + Codex independent review) before merge claim.

**Context-Bridging Harness (MemoryKernel-powered, SOTA 2026 patterns):**
- Every cycle gets a MemoryContextPack (budgeted, redacted, trust-tagged, admissible only).
- Compaction: use preview + render + context_parity/eval to produce compact external notes/artifacts before feeding LLM (Anthropic compaction lesson + 84% token cut patterns).
- Sleep-time compute (Letta): on idle cron cycles, run MemoryKernel writer reorg: demote stale raw episodes to archival, promote high-salience facts/edges, reorganize into learned context (raw → structured). Uses existing AgentCronScheduler + writers + promotion_gates (human review for high-authority).
- Bi-temporal (Graphiti): atoms carry validity windows, point-in-time queries via MemoryQuery + MemoryOrder + timestamps + edges. Incremental real-time via append-only writers.
- Brain/hands/session: session = MemoryKernel atoms + holon_events + conversation_log (interface). Harness = governed loop + context admission/eval. Hands = injected runner (sandboxed, uniform interface).
- Prompt-injection defense: every atom fed to the model is prefixed with source tag. Context admission already redacts secrets (extend to tool outputs). Tool calls for holons are whitelisted by default; write actions require explicit confirmation token (enforcement phase) or operator gate.
- External artifacts for durability: compaction notes, reorg receipts, reviewed canonical receipts (via MemoryKernel promotion), write receipts. All re-readable by separate processes.
- Future-proof pluggable: new surfaces/adapters/writers register in MemoryKernel; the shell consumes via the facade. Versioned atoms, budgets, evals, gates.

**Cross-cutting (cost, observability, HITL, hygiene, receipts):**
- Cost: holon_budget_guard already mid-loop; extend to full fleet (Opus + sub-agents) when heterogeneous dispatch lands. Surface via holon_health + dashboard.
- Observability: holon_health rows + MemoryKernel readiness + witness stats + signal bus events + runtime receipts.
- HITL: explicit confirmation for high-risk actions (scope in enforcement phase); operator can inject tasks, set kill, clear budget, review promotion decisions.
- Hygiene: extend VC-N01/N02/N03; add new patterns for "unbudgeted context injection", "verifier-less outcome in harness", "sleep-time without reorg receipt".
- Receipts: everything is a projection (conversation_log with interface, witness, runtime_state, spine EvidenceReceipt / RuntimeReceipt, MemoryKernel write/promotion/burn-in receipts). Never new authority.

---

## Phased Execution Plan (TDD + verifiers + receipts at every gate)

**Phase 0 (done in this turn):** Onboard + audit (MemoryKernel is the goldmine; gaps exactly as diagnosed). Lane declaration note (this overbuild is explicit operator-directed work on the holon harness; we project only and will update governance surfaces as needed).

**Phase 1 — Master Spec + Contracts (this turn, complete before heavy code):** This document + concrete contracts (MemoryContextPack injection into holon cycle, ArtifactRef + pass^k schema, SleepReorgReceipt, TrustTaggedAtom, RunnerContext interface). Verifier commands written first (shell/Python entrypoints that assert external artifacts).

**Phase 2 — Runnable Shell Overbuild (model-agnostic + context-bridging):**
- Wire holon_wake_cycle / run_holon_loop to accept optional MemoryKernel (or facade) and pull a budgeted pack for the cycle; inject as trust-tagged atoms into the runner task.
- Enhance the injected runner contract to receive + return context deltas (written back via MemoryKernel writers).
- Make PersistentAgent / holon bridge fully consume identity-declared model via the provider door (already close; harden the last seams).
- Add brain/hands/session decoupling contract (document + small adapter if needed).
- TDD: unit tests for pack injection, end-to-end with stub provider + MemoryKernel in-memory surface, live free-model smoke asserting context atoms were used.

**Phase 3 — Verification Harness Overbuild:**
- Mandatory artifact gate in the holon loop (before persist): if outcome words present and no artifact, refuse + log violation (projection).
- pass^k + GDS/meltdown instrumentation (simple counters + event emission in the loop; persist via existing holon_events or MemoryKernel).
- Wire separate evaluator path (reuse context_eval + witness + promotion_gate style; optional decorrelated second provider for artifact validation).
- External verifiers: ship the runnable commands + CI collection. "done" only when verifier green (fresh-context + detonation).
- TDD + dual-audit: every change survives the verifiers + independent review.

**Phase 4 — Context-Bridging Content + Sleep-Time (Letta + Graphiti + compaction):**
- Implement real sleep-time reorg cron (extend PersistentAgent's memory_consolidation): use MemoryKernel iter_episodes + writers to demote/promote, produce reviewed canonical receipts for high-authority moves.
- Compaction in the wake path: before LLM call, produce compact external note artifact via preview + render + parity; feed the compact + link to the full pack.
- Bi-temporal exposure: extend MemoryQuery usage in the shell for validity-window / point-in-time context packs.
- Durable external artifacts for session crossing (reviewed canonical receipts, compaction notes, reorg receipts) — all re-readable.
- TDD + live: idle cycle demo that actually reorganizes memory (measurable atom count / salience shift + receipt); compaction token reduction on real runs.

**Phase 5 — Cross-Cutting + Hygiene + Future-Proofing:**
- Prompt-injection: enforce trust-tagging on all atoms fed to holon LLMs; extend context admission redaction; tool whitelist defaults.
- Cost/observability/HITL: surface fleet budget, health rows, promotion decisions; simple HITL token for write actions in enforcement scope.
- Update hygiene (VC-N* + new patterns); update MAP/README/INDEX; add to make onboard output.
- Pluggability: ensure new MemoryKernel surfaces/adapters/writers just work for holons without shell changes.
- Full governance-all + test suite + docops integrity.

**Phase 6 — End-to-End Verification Closeout (external signals only):**
- Live runs: free models (Ollama Cloud / DeepSeek / etc.) + at least one frontier (Opus via Max or forced API) for the first holon (opus_composer).
- External-process artifact re-read verifiers pass (separate Python process opens receipts/artifacts and asserts).
- pass^k runs on a defined task (k consecutive full successes).
- Sleep-time reorg demo (idle cycle produces measurable learned context + receipt).
- Full adversarial detonation (multiple decorrelated lenses) + independent review (this document + receipts as the packet).
- Only then: update BUILD_LOG / STATE_OF_TRUTH / active-track evidence; operator ratifies "overbuilt to frontier standard".

**Anti-drift rules (burned in from the session that produced this request):**
- Verifier green (external, re-readable) + fresh-context no-write evaluator + adversarial detonation before any phase or merge claim.
- No self-certification. "done" = the external verifier returned green.
- Receipts at every material step (projections over existing).
- Model-agnostic enforced by construction (only the provider door is used).
- Respect axioms (no top-level new files in dharma_swarm/, no god objects, project from owners, update NAVIGATION/MAP when seams change).

---

## Immediate Next Actions (executing now)

1. This spec is the driver. Update sovereign_holons/MAP.md + README.md + INDEX.md to reference it (small edits).
2. Wire the first concrete overbuild increment: edit dharma_swarm/holon_runtime.py to accept optional memory_kernel and inject a context pack into the runner task (trust-tagged). Add corresponding tests + a live smoke verifier command.
3. Enhance the existing sleep-time cron path (PersistentAgent) to perform a real MemoryKernel-backed reorg on idle cycles and emit a reorg receipt.
4. Add the artifact-refusal gate + pass^k skeleton into the holon cycle (using MemoryKernel write_receipts + promotion patterns as the projection mechanism).
5. Run the full verification loop (tests + live free-model + external artifact check + detonation) before claiming any phase complete.
6. Operator decisions (as needed): confirm scope (read-only v1 vs enforcement), lane registration, funded frontier runs, merge approvals.

This is the overbuild the frontier evidence and our own audits said was the highest-leverage missing piece. We are not adding more beautiful organs for their own sake — we are making the runnable shell, the verification that actually proves work, and the context-bridging that survives long horizons first-class, durable, external-auditable, and model-agnostic.

Receipt for this document: written 2026-06-09 as the explicit response to the operator's "overbuild whatever it takes" directive on the three frontier-moving harness areas.

Next concrete code change follows immediately in this session.