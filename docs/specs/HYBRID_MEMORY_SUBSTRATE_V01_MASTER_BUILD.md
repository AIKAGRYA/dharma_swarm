# Hybrid Memory Substrate — v0.1 Proving Seams Master Build Spec

**Status:** v0.1 scoped delivery (first proving seams of the integrated hybrid)  
**Vision context:** Full plan to completion is sketched in § Future Iterations. This packet delivers the minimal end-to-end that proves the hybrid works cleanly, powerfully, and receiptably.  
**Owner surface:** MemoryKernel (dharma_swarm/memory_kernel), world_radar / GO ingest (dharma_swarm/world_radar + tools/*_go), chetana promote/gates, wiki substrate + schema layer.  
**Primary model target:** gpt-5.5 high reasoning for planner/evaluator; strong builders for implementation.  
**Delivery model:** PR stack (not mega PR). Every PR produces receipts, tests, and a closeout receipt.  
**Parallel lane:** Explicitly declared under the active track `runtime-truth-spine-adoption-2026-06` per ACTIVE_TRACK.yaml parallel_lane_policy.

---

## 1. Mission (v0.1)

Prove that the three-layer hybrid can be wired end-to-end with seamless, efficient, receipted, future-proof communication:

- **MemoryKernel** remains the canonical governed memory bus (typed `MemoryAtom` surfaces, risk-aware queries, provenance, write governance, human-gated promotion).
- **Karpathy-style wiki** becomes the LLM-maintained synthesis/compounding/research projection layer (ingest-time compilation, cross-referenced pages, contradiction flagging, living model under explicit schema).
- **GO / world_radar / Idea Spark spine** remains the high-fidelity, cost-accounted external perception + triage ingest layer (receipt-first, strict boundary, promotion decisions flow into the hybrid).

v0.1 success = one real external signal can travel:
receipt → MemoryKernel typed surface/atom → gated promotion into wiki synthesis page (with provenance, review_status, cross-refs) → usable in agent context (via MK preview + wiki reader) — all under receipts, make-onboard visibility, and schema discipline.

This is the load-bearing seam. Everything else in the full vision is iteration on this foundation.

---

## 2. The Hybrid Architecture (Ground Truth for This Packet)

**Layer roles (non-negotiable for v0.1 and beyond):**

- **MemoryKernel (M1 read facade + M2 write governance + receipts)**  
  Central typed, risk-modeled, provenance-carrying memory substrate.  
  All structured, receipted, runtime, episodic, semantic, and projection data projects here as `MemoryAtom` (with `MemoryLane`, `TruthState`, authority/risk levels, source/payload digests, context_admissible, promotion_allowed, etc.).  
  Agents and orchestrator query it with rich `MemoryQuery`.  
  It already folds in vectors (as projections), graphs/bridges (derived), memory_lattice (control-plane), episodic logs (raw streaming), smriti/external (low-authority), and the knowledge_wiki adapter surface.  
  It owns the promotion gate machinery (human + automated reviews → reviewed canonical receipts).

- **Karpathy LLM Wiki (raw/ + wiki/ + schema)**  
  The premier LLM-maintained, human+agent-readable synthesis layer.  
  LLM (under schema) owns: ingest-time compilation, entity/concept pages, cross-linking, contradiction flagging, incremental enrichment, index/log maintenance.  
  Knowledge compounds. Queries that need global synthesized understanding hit this layer (or hybrid retrieval).  
  Raw sources stay immutable. The schema (CLAUDE.md + dedicated wiki protocol) is the living contract describing roles, promotion rules, lifecycle, and maintenance loops.

- **GO / world_radar / Idea Spark (receipt spine)**  
  High-fidelity external world signal perception + triage.  
  Go side: collection, normalization into deterministic typed receipts (receipt_id, correlation, hashes, payload), durable spool, optional gated NATS (never default authority).  
  Python side: projection, source learning/weights, deterministic Idea Spark triage tuple (novelty, telos_fit, tractability, source_confidence), ingest-cost events, promotion decisions.  
  Receipts are truth. They must project cleanly into MemoryKernel before any higher synthesis.

- **Shared promotion & quality machinery (chetana-style gates + MK promotion gate + telos)**  
  The single seam for "staged / reviewed / promoted into higher-authority surface" (MK atom or wiki page).  
  Carries provenance, review_status, cost, contradictions, rollback receipts.

**Query model (efficiency invariant):**  
- Fast, filtered, risk-capped, lane-aware, typed retrieval → MemoryKernel.  
- Rich, cross-referenced, synthesized, compounding understanding → wiki layer (or hybrid).  
- Hybrid retrieval is explicit and schema-described.

**No new authority.** Everything projects from owners + receipts. Read models project; they do not become the source of truth.

---

## 3. v0.1 Scope (The Proving Seams — Bounded & Shipable)

**Allowed surfaces (strict — do not touch outside these without new lane approval):**
- dharma_swarm/memory_kernel/** (new world_signal surface(s), atoms, adapters, writer specs, promotion path)
- dharma_swarm/world_radar/** + tools/*_go (receipt projection into MK, triage → promotion decision)
- dharma_swarm/chetana/promote.py + governance.py (reuse/extend for hybrid promotion)
- ~/.dharma/knowledge/wiki/ (new pages created only via promotion seam; no direct writes)
- Schema files: CLAUDE.md (top-level hybrid rules), docs/wiki/ or equivalent dedicated wiki protocol file (maintenance loops, promotion contract, query guidance)
- Tests, receipts, make-onboard render updates, and one narrative doc

**Explicit non-goals for this packet (do not implement):**
- Full wiki maintenance loops running autonomously (scaffolding + one manual+receipted cycle only).
- Performance/hybrid retrieval optimization or benchmarking.
- Moving existing chetana metabolic tools or all 20+ wiki readers.
- Broad MemoryKernel refactor or new M3 write surfaces beyond the promotion seam.
- NATS changes or new external ingestors.
- Changes to the active spine track surfaces (agent_runner, orchestrator, a2a_bridge) except for context consumption of the new hybrid.
- New god objects or authority stores.

**Three proving seams (PR stack order):**

**Seam A — GO/world_radar receipts become first-class MemoryKernel citizens**  
- New typed surface(s) (e.g. "external.world_signal", "external.idea_shard") with proper `MemorySurfaceRole`, category, risk levels, provenance_quality.  
- Receipt projection path (world_radar/go_bridge + receipt_bridge) emits `MemoryAtom`s (EPISODE / SOURCE_CHUNK / FACT as appropriate) with full source digest, correlation, cost metadata.  
- Writer discovery/sentinel/policy updated so these writes are classified and admissible.  
- One end-to-end receipted flow: world signal → receipt → MK atom visible in `iter_memory_atoms` + `preview_memory_pack`.

**Seam B — Gated promotion from MK into wiki synthesis layer**  
- Extend/reuse promotion gate (MK promotion_gate.py + chetana promote) to support "promote to wiki synthesis" as a target.  
- Promotion decision carries: source MK atom ids, review_status, provenance, cost, contradictions.  
- Wiki page is created/updated with frontmatter that records the promotion receipt id, source atoms, confidence, lifecycle.  
- Cross-references and index.md updated as part of the promotion (or immediately after as a logged step).  
- review_status and quality-ranking logic (already in wiki_mcp.py) respected.

**Seam C — Schema contract for the hybrid (the "idea file" discipline)**  
- Update CLAUDE.md (or a new top-level section) with explicit hybrid model, query guidance (when to use MK vs wiki vs both), promotion contract, and non-goals.  
- Create/maintain a dedicated wiki protocol file (e.g. `docs/wiki/MAINTENANCE_PROTOCOL.md` or `AGENTS.wiki.md`) that the LLM reads on every wiki session: ingest rules, page templates, contradiction handling, promotion seam description, lifecycle, lint expectations.  
- This file is the living Karpathy-style schema for this specific hybrid.

**End-to-end proof for v0.1:**  
One external signal (from an existing GO ingestor or a minimal test source) must:
1. Emit a canonical receipt.
2. Appear as a typed `MemoryAtom` in MemoryKernel with correct provenance/risk/lane.
3. Be promoted (human or deterministic gate + receipt) into a wiki synthesis page.
4. The wiki page is findable via the (fixed) wiki tools and carries promotion provenance.
5. Agent context (via MK preview) can surface the promoted knowledge.

All steps produce receipts or immutable logs. make onboard renders the new surfaces and promotion activity.

---

## 4. Plan to Completion (Full Vision Arc — For Context & Next Agents)

This v0.1 packet is the foundation. The full vision is staged as follows (next agents will expand these into subsequent packets):

**v0.2 — Rich promotion & synthesis loops**  
- Automated (schema-driven) suggestion of promotion candidates from MK + GO signals into wiki.  
- Full wiki maintenance loops (ingest → lint → contradiction → revival) running under the protocol file, with receipts.  
- Bidirectional flow: valuable wiki syntheses can emit typed facts/edges back into MemoryKernel as `KNOWLEDGE_CARD` or `FACT`.

**v0.3 — Hybrid retrieval & efficiency**  
- Production hybrid query surface (MK for fast filtered + wiki for depth, with RRF or learned fusion).  
- Performance characteristics documented (token budgets, latency, recall for different query classes).  
- Caching / projection strategies between layers.

**v0.4 — Idea Spark → MK → wiki as first-class path**  
- Complete GO/ world_radar triage tuple wired into MK promotion policy.  
- "Idea Spark" artifacts become first-class `MemoryAtomType` with their own risk/lane treatment.  
- End-to-end cost accounting across the entire hybrid.

**v0.5 — Full surface coverage & deprecation of rivals**  
- archaeology_ingestion, vault_bridge, and other shadow stores either folded as projections into MK or explicitly deprecated with migration receipts.  
- All major readers (context_compiler, chetana metabolic, CLI, MCPs) route through the hybrid contract or are documented as intentionally narrow.

**Ongoing invariants (never relax):**  
- Receipts + provenance everywhere.  
- No new authority stores.  
- MemoryKernel as the typed governance bus.  
- Wiki as the LLM-maintained compounding synthesis layer.  
- GO as receipt-first external perception.  
- Strong, co-evolving schemas as the discipline mechanism.  
- Parallel lane policy followed for every significant increment.

---

## 5. PR Stack (v0.1 — Ship in This Order)

**PR 1 — Foundation & Lane Declaration**  
- Create this spec file + lane declaration in ACTIVE_TRACK.yaml or a companion `docs/governance/parallel_lanes/hybrid-memory-v01.md`.  
- Add initial surface specs for world_signal in memory_kernel/surface_specs_core.py or extended.  
- Update writer_specs and discovery so the new surface is known.  
- Add minimal receipt projection scaffolding in world_radar (no behavior change yet).  
- Verification: make onboard shows new surface (even if empty), lane doc is present, CI green.

**PR 2 — Receipts into MemoryKernel (Seam A core)**  
- Implement projection from world_radar receipts → `MemoryAtom` in the new surface.  
- Full adapter + iter_memory_atoms support.  
- Unit tests + one integration test that a receipt appears in preview_memory_pack.  
- Receipt artifacts for the projection run.  
- Verification: `make onboard`, targeted pytest, receipt file present with correct fields.

**PR 3 — Promotion seam (Seam B)**  
- Wire MK promotion decision to target "wiki synthesis".  
- Create/update wiki page via the promotion path (respecting existing write_trusted + cross_update if possible, or thin wrapper).  
- Frontmatter includes promotion receipt id, source atom ids, review_status, provenance summary.  
- One end-to-end test: receipt → MK atom → promoted wiki page (with links back to receipt).  
- Receipts for the promotion decision and page creation.

**PR 4 — Schema contract (Seam C) + end-to-end proof**  
- Update CLAUDE.md with hybrid model section.  
- Create the dedicated wiki maintenance protocol file with the v0.1 rules.  
- Final end-to-end harness test (or ds-goal receipt) exercising the full path.  
- Update make onboard render to show hybrid activity (new surfaces + recent promotions).  
- Narrative handoff doc (this packet + what was learned).  
- All v0.1 completion criteria green.

Each PR: declare scope in description, run narrowest meaningful tests + make onboard + receipt generation, have separate evaluator pass before close, produce closeout receipt.

---

## 6. Verification Matrix (Hard Gates)

**Baseline (every PR + final):**
- `make onboard`
- `make governance-all` (or the relevant subset)
- `python3 scripts/governance/check_track_status.py` (must still pass for the active spine track)

**Seam-specific:**
- Receipt files present with stable ids, correlation, hashes, promotion links.
- `MemoryAtom` visible in `iter_memory_atoms` / `preview_memory_pack` with correct fields.
- Wiki page created via promotion path (not direct edit) and carries promotion provenance.
- Schema files loaded by the relevant agents/MCPs (documented).
- One full signal path exercised and receipted end-to-end.

**Anti-false-green:**
- If any step is "import and pretend" instead of real receipt/project/promote, mark the relevant criterion INCONCLUSIVE.
- All new surfaces must appear in make onboard output.

---

## 7. Agent Orchestration & Launch Commands

**Lane declaration (do this first in the worktree/branch/packet):**
Use the exact language required by ACTIVE_TRACK.yaml:
- Owner: [your identity or the packet name]
- Branch/worktree or ds-goal packet: [name]
- Allowed surfaces: listed in §3
- Verification command: the matrix above + receipt collection
- Receipt path: reports/hybrid_memory_v01/ + ds-goal ledger

**Recommended launch (bounded long-running build):**
```bash
make onboard
# Declare the lane (edit ACTIVE_TRACK companion or create the parallel lane doc + commit the declaration)

make autonomy-goal GOAL="Hybrid Memory Substrate v0.1 — GO receipts into MemoryKernel + gated promotion into Karpathy wiki synthesis + schema contract. Prove one real signal flows end-to-end with receipts."

# Then launch the harness (example — adjust to your current autonomy tooling)
make long-harness-init RUN_ID=hybrid-memory-v01 MODE=brownfield RISK=Q3 GOAL="..." 
# or the ds-goal / autonomy-run equivalent you use

# Inside the run, follow the PR stack order. Every PR produces its receipt before the next begins.
```

Use context quorum for architecture decisions. Use separate evaluator agents for each PR closeout.

---

## 8. Placeholders & Extension Points (for the next agent)

- [ ] Full text of the wiki maintenance protocol file (Seam C) — start from the Karpathy gist principles + the hybrid roles defined here.
- [ ] Exact `MemorySurfaceSpec` + atom type mapping for world_signal / idea shards.
- [ ] Performance / token budget numbers once the hybrid retrieval seam exists (v0.3).
- [ ] Detailed promotion policy rules (what scores/tuples auto-suggest promotion vs require human).
- [ ] Migration/deprecation plan for archaeology_ingestion and vault_bridge (v0.5).
- [ ] Any additional surfaces discovered during implementation that should be registered in MemoryKernel.
- [ ] Updated ACTIVE_TRACK.yaml block when this lane is ready to be recorded as completed or superseded by the next iteration.

---

## 9. Why This Packet, Why Now, Why Scoped

We have the conceptual model (75%+). We have the strongest memory engineering in the repo (MemoryKernel). We have a receipt-first external ingest system with a detailed spec. We have the wiki substrate with recent coverage/quality fixes. We have the Karpathy pattern deeply understood.

What we do not yet have is the *running, receipted, end-to-end proof* that these layers communicate seamlessly and powerfully.

This v0.1 packet delivers exactly that proof on the minimal seams that matter, while giving the full vision arc for context. It follows the repo's proven ship rhythm (PR stack, receipts, explicit lanes, make onboard, no new authority, active-track alignment).

Once this lands with clean receipts, the next agent(s) have a solid foundation to expand into the richer loops, hybrid retrieval, and full coverage without creating the classic failure modes.

---

**Handoff note to the next agent(s):**  
This file + the lane declaration commit is the starting artifact. Fill the placeholders, expand Future Iterations into the next packet when v0.1 ships, and keep every change receipted and lane-compliant. The goal is a hybrid that is end-to-end working, seamless, very efficient for its use cases, future-proof by construction, and bleeding-edge in the combination of typed governance (MemoryKernel) + compounding LLM synthesis (Karpathy) + receipted external perception (GO).

Ready when the first real signal completes the loop above and all v0.1 criteria are green in the evidence.

**Generated:** 2026-06-08 by Grok (from deep research session on Karpathy pattern, MemoryKernel internals, GO spine, and hybrid convergence). Extend freely.