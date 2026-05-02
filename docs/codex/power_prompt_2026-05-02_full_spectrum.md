# Codex Power Prompt — Full-Spectrum Diagnosis (Phases 0–7, Continuing the Counter-Audit)
**To**: Codex (next session, or any agent with GitNexus MCP + filesystem access)
**From**: Claude (the agent that wrote the bloat scan you already counter-audited)
**Date**: 2026-05-02
**Mode**: Full-spectrum read-only diagnosis. No edits. No commits. No new modules.
**Estimated**: 6–8 hours of agent compute across 7 phases.

---

## L4 — Telos

You already shipped a counter-audit (`~/.dharma/codex/replies/bloat_triage_counter_audit_20260502T095213+0800.md`). It was sharp: you refuted Claude's `autoresearch_loop.py` import claim, named `swarm.py` as a "live God object" rather than a clean façade, delivered a 50-file quarantine list with confidence scores, and flagged that `Evidence` ObjectType duplicates `dharma_corpus.EvidenceLink` and `KnowledgeArtifact.provenance`.

This prompt extends that work into a full-spectrum system diagnosis covering the seven phases of the structural audit spec. The bloat triage was Phase 1 + 5-partial + 7-partial. **Phases 0, 2, 3, 4, 6, and the rest of 5 and 7 remain.**

The output is the artifact Dhyana will hand to the external human Python engineer. It is the blueprint for the engineer's 8–16 hour read. If your output is honest and structured, the engineer's verdict will be 3× faster and 3× more accurate.

This prompt is one move in the Transcendence loop. Decorrelated errors cancel only if you stay independent. Keep tearing apart Claude's framing where it's wrong.

---

## L3 — Identity

You are the agent who:

- Already shipped working code (commit `9446e13` in chetana) and the counter-audit on the bloat scan.
- Resolved the `dgc_cli.py` 599-vs-7,089 discrepancy (canonical vs chetana, branch-specific).
- Refuted three of Claude's framing claims with evidence.
- Operates from `~/dharma_chetana/` worktree with ContextPlus + filesystem; you used those because gitnexus was stale and not on PATH.

This time GitNexus must be refreshed first (CLAUDE.md gitnexus section is now mandatory for symbol-level edits and audits — see `~/dharma_swarm/CLAUDE.md` lines 168–268). The new rules require `gitnexus_impact` before edits and `gitnexus_detect_changes` before commits. You won't be editing or committing, so most of those rules don't apply — but the *query* tools (`gitnexus_query`, `gitnexus_context`, `gitnexus_impact`) are now first-class for read-only diagnosis. Use them in this round.

You are not Claude's reviewer. You are Dhyana's independent counsel. The external human engineer will read your output as the most reliable structural verdict.

---

## L2 — Context

### What you've already done (Phase 0–7 coverage status)

| Phase | Status | Where |
|---|---|---|
| 0. Instrument check | NOT DONE | This prompt requires it |
| 1. Structural skeleton via GitNexus | PARTIAL | Counter-audit used ContextPlus blast-radius for top-10 files; GitNexus was stale + not on PATH. Now refreshed; redo the spine map with fresh GitNexus tools. |
| 2. Vision-to-Implementation alignment | NOT DONE | This prompt's main extension |
| 3. Memory system deep diagnosis | NOT DONE | This prompt's Phase 3 |
| 4. Governance stress test | NOT DONE | This prompt's Phase 4 |
| 5. Overlap & combination map | PARTIAL | Ginko cluster done in counter-audit. Terminal / provider+routing / ontology clusters remain. |
| 6. Live execution probing | NOT DONE | This prompt's Phase 6 |
| 7. Synthesis & findings | PARTIAL | Counter-audit has executive verdict, 50-file list, Phase 1.1 schema-duplicate appendix. Full structured findings matrix remains. |

### Anchor files (read first, full)

1. `~/.dharma/codex/replies/bloat_triage_counter_audit_20260502T095213+0800.md` — your prior counter-audit. Don't repeat its findings; build on them.
2. `~/dharma_swarm/docs/audits/REPO_BLOAT_SCAN_2026-05-02.md` — Claude's original scan.
3. `~/dharma_swarm/CLAUDE.md` — full file. Especially the **Transcendence Principle** (lines 45–79) and the new **GitNexus tooling section** (lines 168–268).
4. `~/dharma_swarm/SWARM_HOT_ITEMS.md` — live architecture/drift map.
5. `~/dharma_swarm/INTERFACE_MISMATCH_MAP.md` — known broken seams.
6. `~/dharma_swarm/MODEL_ROUTING_MAP.md` — LLM call paths (18 providers, 5 inconsistencies, 3 surfaces).

### Locked decisions Codex must not relitigate

- HumanOperator = `is_principal: bool` flag, not a separate ObjectType. [I — confirmed via AskUserQuestion 2026-05-01]
- R_V_Measurement is NOT a peer ObjectType. [I — same]
- Phase 1.2–1.5 build is paused. [B — captured in conversation]
- External human engineer is being hired; they call deletion/merge shots. [I]
- The 7 chetana modules (`causal_ledger`, `r_repair_metric`, `autoresearch_history`, `welfare_attribution`, `witness_resolver`, `drift_monitor`, `gate_calibration`) stay in chetana until merge wiring lands together. [I — your own recommendation in counter-audit]
- The **`Evidence` ObjectType duplicate-risk** you flagged in Appendix C of counter-audit is a real finding. Phase 1.1 schema is cheap to revert. Carry this forward into Phase 7's risk register.

### GitNexus state (as of 2026-05-02 02:00 UTC)

`~/dharma_swarm/.gitnexus/meta.json` reports `indexedAt: 2026-05-02T01:56:20Z`, embeddings=0. **Re-verify freshness in Phase 0.1.** If `indexedAt` is older than 24h or if `git log` shows commits after that timestamp, run `npx gitnexus analyze` per CLAUDE.md line 173.

---

## L1 — Task: The 7 Phases

Each phase produces artifacts saved to `/tmp/diagnosis/phase_N/`. Every claim in the final synthesis must cite phase + step number + file path + (if applicable) line number + pramana tag [G/B/P/I/S].

### Phase 0 — Instrument Check (15 min)

- **0.1 GitNexus index freshness**: `cat ~/dharma_swarm/.gitnexus/meta.json | python3 -c "import sys,json; m=json.load(sys.stdin); print(m.get('indexedAt'))"`. If stale, `cd ~/dharma_swarm && npx gitnexus analyze` (use `--embeddings` if you need semantic search; check the warning at CLAUDE.md line 253 about embedding deletion).
- **0.2 Assurance baseline**: `cd ~/dharma_swarm && python3 -m dharma_swarm.assurance --repo-root . 2>&1 | tail -20`. Capture per-scanner finding counts. This is "before" snapshot.
- **0.3 Test suite baseline**: `python3 -m pytest tests/ -q --tb=line 2>&1 | tail -5`. Record `X passed, Y failed, Z errors`.
- **0.4 Governance hooks**: `pre-commit run --all-files 2>&1 | tail -30`. Note crashes, skips, fails.
- **0.5 Read 5 canonical orientation files in order, fully**: SWARM_HOT_ITEMS.md → CLAUDE.md → docs/governance/{README, SOVEREIGN_MANIFEST, CANONICAL_DOC_STACK}.md → INTERFACE_MISMATCH_MAP.md → MODEL_ROUTING_MAP.md. Note every claim that could be verified later.

Output: `/tmp/diagnosis/phase_0/baseline.md` with all four numerical baselines and 5 claims-to-verify per orientation file.

### Phase 1 — Structural Skeleton via Fresh GitNexus (30 min — reduced; you partly covered)

Skip what you already did. Add only what GitNexus' fresh index gives you that ContextPlus didn't.

- **1.1 Pull execution flow inventory**: read resource `gitnexus://repo/dharma_swarm/processes`. Record entry points, depth, key symbols for all 300 traced flows. Group into functional clusters; compare to Leiden communities.
- **1.2 360-degree pillar context** (only the 4 you didn't cover with full ContextPlus depth in counter-audit): `gitnexus_context({name: "DharmaKernel"})`, `DarwinEngine`, `LoopEngine`, `RuntimeStateStore`, `TaskBoard`. Record callers count, callees count, processes participated in.
- **1.3 Blast-radius on hot paths**: `gitnexus_impact({target: "<X>", direction: "upstream"})` for `SwarmManager`, `get_swarm`, `TerminalBridge`, `SessionStore`, `ThinkodynamicDirector`. Compare to your counter-audit's `SwarmManager 155 usages in 39 files` claim — do GitNexus and ContextPlus agree?
- **1.4 Orphan execution flows**: cross-reference 300 processes against pillar call trees from 1.2. Any process with zero connection to the 10 pillars is candidate orphan flow.

Output: `/tmp/diagnosis/phase_1/spine.md` + `phase_1/orphan_flows.json`.

### Phase 2 — Vision-to-Implementation Alignment (60 min — the most important phase)

For each of the 9 Telos Engine vision docs (`docs/telos-engine/01_SATTVA_VISION.md` through `09_WHERE_IT_SITS.md`), extract the top 3–5 concrete capability claims. For each claim, run `gitnexus_query({query: "<capability claim>"})` and classify:

- **IMPLEMENTED**: execution flow exists, tests pass, code wired to a pillar.
- **SCAFFOLDED**: code exists but is not wired to any execution flow (orphan).
- **DOCUMENTED-ONLY**: vision doc describes it, no code implements.
- **CONTRADICTED**: code exists but does something different from the claim.

Then audit the **Transcendence Principle** (CLAUDE.md lines 45–79) against actual code:

- Diversity preservation → does `diversity_archive.py` actually run in any flow? `gitnexus_context({name: "diversity_archive"})`.
- Error decorrelation → does `orchestrator.py` topology routing actually diversify? Trace.
- Quality aggregation → is `ginko_brier.py` wired to anything live? (Hint: your counter-audit shows it's part of the active 9-file ginko core.)
- VSM governance → is `vsm_channels.py` imported by anything?

Then read `docs/architecture/PHILOSOPHICAL_ARCHITECTURAL_MARRIAGE.md` and compare claims to the implementation map.

Then read DSE: `docs/dse/{README, JAGAT_KALYAN_MASTER_VISION, DSE_ARCHITECTURE_MAP, DSE_PHASE_ROADMAP}.md`. For each phase on the roadmap, check `dse_integration.py`, `coalgebra.py`, `sheaf.py`, `geometry.py`, `info_geometry.py` for actual callers.

Output: `/tmp/diagnosis/phase_2/vision_alignment_matrix.md`. Format: one row per capability claim with classification + evidence path:line.

### Phase 3 — Memory System Deep Diagnosis (45 min)

- **3.1** Read `docs/architecture/MEMORY_SYSTEM_FUSION_MAP_2026-05-01.md` fully. Treat as ground truth unless code contradicts.
- **3.2** Verify connectivity claims for each system in the Fusion Map (lines 80–118 per spec): `EventMemoryStore`, `HybridRetriever`, `ContextCompiler`, `AgentMemoryManager`, `StrangeLoopMemory`, `MemoryLattice`, `MemoryPalace`, `VectorStore`. For each: does GitNexus call graph confirm the Fusion Map's claimed wiring? Or has code drifted?
- **3.3** Find actual write paths to `~/.dharma/`. `gitnexus_query({query: "write to dharma state directory"})` plus `grep -rn "Path.home() / .dharma" ~/dharma_swarm/dharma_swarm/`. Cross-reference with **Anti-Slop Rule 1's allowlist** (`docs/governance/ANTI_SLOP_RULES.md` lines 73–81). Any writer NOT in the allowlist is unauthorized authority — flag it.
- **3.4** Identify combinable systems. **Don't recommend deletion** (your counter-audit already does that for unrelated modules). Recommend **fusion points**: which memory systems share storage (e.g. `memory_plane.db`)? Which have overlapping retrieval interfaces? Which could become projections over a single canonical store?

Carry your **`Evidence` ObjectType duplicate-risk** finding into 3.4: if `Evidence` overlaps `KnowledgeArtifact.provenance` and `dharma_corpus.EvidenceLink`, that is a memory-system fusion candidate, not just a schema concern.

Output: `/tmp/diagnosis/phase_3/memory_authority_map.md` + a single ASCII diagram showing canonical write path → stores → retrieval paths → context injection.

### Phase 4 — Governance Layer Stress Test (45 min)

- **4.1** `python3 ~/dharma_swarm/scripts/uplift_guards/run_pre_commit.py`. Record pass/fail for each of the 6 guards: kernel-integrity, secrets-scan, autonomous-destruction, hotpath-ack, mismatch-adjacency, assurance-diff. (Note: `assurance-diff` had a `use_baseline` kwarg crash earlier today — verify whether that's been fixed in HEAD.)
- **4.2** `cd ~/dharma_swarm && semgrep --config .semgrep --metrics=off --verbose 2>&1 | tee /tmp/diagnosis/phase_4/semgrep.log`. Capture all findings. Cross-reference with `ANTI_SLOP_RULES.md` known-offender list. Any new finding NOT in the known-offender list is a regression.
- **4.3** `semgrep --test .semgrep/tests/ --metrics=off`. Expect 4/4 pass. If not, the rules themselves are broken.
- **4.4** `python3 -m dharma_swarm.assurance 2>&1`. Per-scanner breakdown. Compare to SWARM_HOT_ITEMS.md assurance-meta section. Note scanner whose count changed.
- **4.5** For each Anti-Slop Rule 1–10, verify: (a) the rule definition exists where ANTI_SLOP_RULES.md says, (b) severity matches doc, (c) listed known offenders match current code. Read `.semgrep/dharma-anti-slop.yml` and `scripts/governance/*` directly.
- **4.6** Read `docs/governance/REPO_GOVERNANCE_AUDIT.md`. What contradictions did it find? Are they still present?

Output: `/tmp/diagnosis/phase_4/governance_health_card.md`.

### Phase 5 — Overlap & Combination Map (45 min — Ginko done by counter-audit; finish remaining)

Skip ginko (you covered it). Cover three remaining clusters:

- **5.1 Cluster analysis**: read `gitnexus://repo/dharma_swarm/clusters` (1,809 Leiden communities). For each community with ≥5 members: functional theme, alignment with subpackage boundary, cross-community bridges.
- **5.2 Top-20 most-imported modules**: how many Leiden communities does each participate in? A module in 5+ communities is a structural bridge — healthy shared utility OR unhealthy god-object.
- **5.4 Ontology cluster (8 files)**: `ontology.py + 7 submodules` (action_gateway, adapters, agents, context, hub, query, runtime). Are these one coherent subsystem or 8 independent attempts? Note: your counter-audit already flagged `ontology_adapters.py` and `ontology_context.py` as orphan candidates.
- **5.5 Terminal surface convergence**: map all of these — `terminal_bridge.py`, `terminal_bridge_context.py`, `terminal_bridge_renderers.py`, `terminal_control.py`, `terminal_overnight_supervisor.py`, `terminal/` dir, `terminal-v2/` dir, `tui/`, `tui_legacy.py`, `tui_launcher.py`. Which surfaces are live? Which are dead? Where should they merge?
- **5.6 Provider/routing convergence**: map `providers.py`, `providers_extended.py`, `model_catalog.py`, `model_hierarchy.py`, `model_manager.py`, `model_registry.py`, `model_routing.py`, `power_model_catalog.py`, `smart_router.py`, `tiny_router_shadow.py`, `router_v1.py`. Cross-reference with `MODEL_ROUTING_MAP.md`'s 5 documented inconsistencies. What's the minimum routing path?
- **5.7** For each overlapping cluster: recommend COMBINE targets (not delete). Format: "X should become a method on Y" / "X and Y should merge into Z subpackage" / "X is the canonical version; Y should import from X instead of reimplementing."

Output: `/tmp/diagnosis/phase_5/combination_map.md`.

### Phase 6 — Live Execution Probing (60 min)

Stop reading code. Run it.

- **6.1 Boot the runtime**: `export TINY_ROUTER_BACKEND=heuristic && timeout 120 dgc orchestrate-live 2>&1 | tee /tmp/diagnosis/phase_6/boot.log`. Watch initialization order, failures, slowdowns.
- **6.2 Doctor**: `dgc health 2>&1 | tee phase_6/health.log`. Note discrepancies between `doctor.py` and Phase 1 GitNexus findings.
- **6.3 Invariants**: `dgc invariants 2>&1 | tee phase_6/invariants.log`. Do the kernel axioms pass? Is the SHA-256 signature intact?
- **6.4 Xray**: `cd ~/dharma_swarm && make xray 2>&1 | tee phase_6/xray.log`. Compare module counts and hotspot list to Phase 1.
- **6.5 Tests with coverage**: `python3 -m pytest tests/ -q --tb=short --cov=dharma_swarm --cov-report=term-missing 2>&1 | tee phase_6/tests.log`. Identify pillar modules (from 1.2) with zero test coverage — those are highest-risk gaps.
- **6.6 Real task dispatch**: `export TINY_ROUTER_BACKEND=heuristic && timeout 60 dgc orchestrate-live --max-tasks=3 2>&1 | tee phase_6/tasks.log`. Does a task complete? Trace end-to-end via GitNexus process map.
- **6.7 Cron daemon**: `timeout 60 python3 -m dharma_swarm.cron_runner 2>&1 | tee phase_6/cron.log`. What jobs fire? Do they succeed? What writes to `~/.dharma/`?

Output: `/tmp/diagnosis/phase_6/live_execution.md` summarizing what works, what fails, what's slow.

### Phase 7 — Synthesis & Findings (60 min)

Single structured document. **Not a narrative — a findings matrix.** Saves to `~/.dharma/codex/replies/full_spectrum_diagnosis_<ISO-8601>.md`.

Required sections:

- **7.1 Vision Alignment Matrix** (from Phase 2): each Telos Engine claim → IMPLEMENTED / SCAFFOLDED / DOCUMENTED-ONLY / CONTRADICTED + path:line.
- **7.2 Structural Health Card**:
  - Total modules / Load-bearing core / Peripheral / Orphan candidates / Recommended combinations
- **7.3 Memory Authority Map** (from Phase 3): single ASCII diagram + table.
- **7.4 Governance Health Card** (from Phase 4):
  - Guards passing X/6 / Anti-slop rules active Y/10 / Known offenders remaining Z / Assurance per-scanner / Module budget compliance.
- **7.5 Top 10 Combination Recommendations** (from Phase 5): what to combine, why (shared callers/storage/interface), how (specific merge steps), GitNexus impact analysis blast radius.
- **7.6 Top 5 Risks**: 5 things most likely to break the system or block progress, with evidence from all prior phases.
- **7.7 The Big Picture**: one paragraph — what this system is trying to become, where it actually is, the minimum path from here to there.

Plus required sections inherited from counter-audit conventions:

- **Where I disagree with Claude or my prior counter-audit**: substantive disagreement section. If you find that some of your prior counter-audit claims were wrong (e.g. a quarantine candidate now shows live importers via fresh GitNexus), name it.
- **What Dhyana should NOT do based on this diagnosis**: block over-eager moves.

---

## L0 — Technical

### Output destinations

- Per-phase artifacts: `/tmp/diagnosis/phase_0/` through `/tmp/diagnosis/phase_7/`. Each phase: at least one `.md` summary + JSON dumps of GitNexus query results for reproducibility.
- Final synthesis: `~/.dharma/codex/replies/full_spectrum_diagnosis_<ISO-8601>.md`. ~3,000–5,000 words.

### Pramana tags (mandatory on every empirical claim)

- **[G]** Geometric — verifiable from code/file system, deterministic
- **[B]** Behavioral — observed at runtime, dated
- **[P]** Proxy — inferred from a related signal
- **[I]** Inferential — derived from context not directly verifiable
- **[S]** Speculative — judgment call

Untagged empirical claims will be rejected by Dhyana's downstream review.

### Constraints

- **Read-only.** Do not edit any source file. Do not commit. Do not create branches. Do not write source modules.
- **No code patches.** If you find a bug, document it in §7.6 (risks); do not fix it in this round.
- **No new modules.** Especially: do not propose `system_doctor.py`, `vision_aligner.py`, or any "tool" to automate this. The deliverable IS the analysis. The engineer Dhyana hires will write tools if tools are needed.
- **GitNexus index must be fresh** before Phase 1.1 (per CLAUDE.md gitnexus rules). If `npx gitnexus analyze` fails, fall back to ContextPlus and document the failure.
- **No conversation with Claude.** This is one-shot. If you need clarification, mark the deliverable BLOCKED with the question and continue with what you have.
- **Time budget**: ≤ 8 hours wall-clock. Quality over coverage. Better to deliver Phases 0–4 + 7-partial well than 0–7 superficially.

### Anti-sycophancy gates

- §7.1 must include at least 5 capability claims classified as DOCUMENTED-ONLY or CONTRADICTED. If every Telos Engine vision claim is IMPLEMENTED, the diagnosis isn't honest.
- The disagreement section must include at least one substantive disagreement with either Claude's bloat scan, your prior counter-audit, or the diagnosis spec itself.
- The "do not do" section must block at least 2 over-eager moves.

---

## Appendix A — What's already on the table from prior rounds (for closure)

From your bloat triage counter-audit (2026-05-02 09:52 +0800):

- 13 strong orphan candidates with confidence ≥0.80
- 50-file quarantine list with confidence × LOC sort
- Ginko core (9 files: orchestrator, agents, brier, data, paper_trade, regime, sec, signals, bridge) confirmed integrated; remaining 8 ginko files marked merge/delete/park
- Refuted: `autoresearch_loop.py` is NOT imported by `evolution.py` in canonical
- Reframed: `swarm.py` is "live God object", not clean façade
- Phase 1.1 `Evidence` ObjectType flagged as duplicate-risk vs `KnowledgeArtifact.provenance` + `dharma_corpus.EvidenceLink`

Carry these forward — don't reverify, but use them as inputs to Phases 2–7.

---

## Appendix B — Locked decisions (do not relitigate)

- HumanOperator = `is_principal: bool` flag, not new ObjectType
- R_V_Measurement is NOT a peer ObjectType
- Phase 1.2–1.5 build paused; reversal of build directive in effect
- External human Python engineer is being hired; they call merge/delete shots
- 7 chetana modules stay in chetana until merge wiring lands together

---

## Appendix C — GitNexus tooling now mandatory

CLAUDE.md lines 168–268 (added 2026-05-02) make GitNexus tools first-class for symbol-level analysis. For your read-only diagnosis:

- `gitnexus_query({query: "concept"})` instead of grep when looking for execution flows.
- `gitnexus_context({name: "Symbol"})` for 360-degree views.
- `gitnexus_impact({target: "Symbol", direction: "upstream"})` for blast radius.
- Resources: `gitnexus://repo/dharma_swarm/{context, clusters, processes, process/<name>}`.

If `npx gitnexus analyze` crashes or hangs, document it in Phase 0.1 and proceed with ContextPlus + grep. The fallback is honest; pretending GitNexus worked when it didn't would corrupt downstream phases.

---

## Closing

The previous counter-audit was sharp because you stayed independent. Don't agree with my framing or with your own prior framing if fresh evidence says otherwise. The bloat scan, the counter-audit, and this prompt are all artifacts written by agents — including agents named "Claude" who are part of the bloat surface they describe. The numbers don't lie, but the framing can.

Dhyana is reading your reply, not Claude. Write to Dhyana. The external human engineer is reading your reply next, not Claude. Write something the engineer can act on without rereading 200 files.

When in doubt: cite, tag, refuse to claim what you can't verify.
