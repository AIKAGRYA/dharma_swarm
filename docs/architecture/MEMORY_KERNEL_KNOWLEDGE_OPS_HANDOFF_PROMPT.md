# Handoff prompt — Dharma Memory Kernel + Knowledge Operations

Copy everything below into a fresh Codex instance if the current session reaches
its execution limit.

---

You are continuing an active, high-rigor architecture research goal in
`/Users/dhyana/dharma_swarm`. Work autonomously until the objective is genuinely
complete; do not restart the investigation or implement runtime code.

## Mission and required reads

The user's persistent goal is:

> Run the attached architecture prompt iteratively until a massive,
> implementation-shaping breakthrough; use as many subagents as useful.

Read these files in order and in full before acting:

1. Original prompt:
   `/Users/dhyana/.codex/attachments/c1f1d3e9-1314-42cc-8754-a4746cb7de60/pasted-text-1.txt`
2. Current master specification:
   `/Users/dhyana/dharma_swarm/docs/architecture/MEMORY_KERNEL_KNOWLEDGE_OPS_MASTER_SPEC_V0.md`
3. Dated evidence receipt:
   `/Users/dhyana/dharma_swarm/docs/architecture/evidence/MEMORY_KERNEL_KNOWLEDGE_OPS_EVIDENCE_20260710.md`
4. This handoff.

The original prompt requires repository reality, current primary-source
research, a first-principles model, target architecture, all 16 deliverables,
schemas, diagrams, ADRs, threat model, evaluation, roadmap, 3/5/10-year
scenarios, rejected ideas, operator decisions, and falsification experiments.
The report now contains all 16. The remaining work is adversarial closeout,
council rerun, final evidence binding, and verification—not another broad draft.

## Central answer and breakthrough

The user asked why provenance-first research memory should differ from Dharma's
whole memory/vector system. The answer is:

> It should not be separate infrastructure. Research, agent, operational,
> personal, and RSI memory are policy profiles over one shared typed substrate.
> Vector, graph, wiki, summary, cache, and context systems are rebuildable
> projections, never authorities.

The working substrate is **Dharma Epistemic Memory Intermediate Representation
(EMIR)**:

- Memory Kernel: storage-neutral facade, evaluator, policy boundary, and
  canonical front door.
- Knowledge Ops: transformation/write/maintenance compiler.
- One canonical semantic record log plus an encrypted, domain-scoped source
  vault.
- Six roots only: `SourceArtifact`, `Event`, `Assertion`, `Decision`,
  `Procedure`, and `Derivation`.
- Entities, episodes, syntheses, contexts, evaluations, contradiction
  assessments, and projection runs are subtypes/values/views until a distinct
  constructor/owner/lifecycle fixture proves another root necessary.

The language-level contribution is small and challengeable:

```text
Assertion<P, M, A>  // proposition, invariant modality, invariant asserter

assess(AssertionRef, EvidenceBundle, EvaluationPolicy, TransactionBasis)
  -> SupportAssessment<P, M>

invariant: assess() cannot change M or A
```

Support is not a mutable field or total monotonic state on an assertion. Later
assessments may strengthen, weaken, contest, refute, or disagree by policy.
`SourceAsserted<P> -> Observed<P>` and
`Decision<P, scope> -> EmpiricalFact<P>` are type errors. Ordinary agent writes
cannot self-assign modality or authority; capability-scoped constructors and the
evaluator enforce them.

Other load-bearing semantics already integrated:

- logical ID, version ID, protected integrity digest, domain-scoped storage key,
  semantic event ID, and retry identity are distinct;
- retained payloads are byte-stable, but authorized erasure is real;
- historical `knowledge_basis` never time-travels authorization: every read and
  execution uses the current `security_basis`;
- one serialized/fenced authority; offline nodes submit authenticated,
  expiring, idempotent `RecordProposal`s;
- canonical semantic events are authority; the outbox is mutable operational
  delivery state;
- projection definition, build, validation, and activation are separate
  append-only records;
- SQLite is the `v0-reference`; PostgreSQL 18 is one feature-rich benchmark
  candidate with **no preference** before experiment 13 decides the production
  store at the Phase 4 gate;
- a separately protected deletion/revocation/key-state watermark is restored
  before any node may serve, preventing pre-deletion backup resurrection;
- same-turn web material is a tainted ephemeral lane only; durable use is an
  asynchronous capture/extract/evaluate path;
- post-generation atomic answer verification repairs or abstains; context
  coverage alone is not grounding proof.

The master spec includes a syntax-checked minimal SQLite relational sketch,
constructor commit pseudocode, and a complete World Radar source-to-verified-
answer trace. Preserve these as falsifiable reference contracts.

## Repository truth already established

Repository basis when the receipt was made:

```text
HEAD db5da6d864006340d58f9dc389437825e5e3436f
branch agent/magpie-seed
```

Key findings, with exact citations in §2 and the evidence receipt:

- Census: 81 registered surfaces, 70 existing, 11 missing.
- Readiness says `ready` only for bounded adapter coverage: 7/7 required, but
  just seven factories are content-aware and generic metadata adapters cover
  most surfaces.
- Default Memory Kernel context receives but ignores the recall query and then
  admits deterministic surface enumeration.
- Two incompatible “hybrid” retrievers exist; one skips vector retrieval when
  FTS returns any result.
- Runtime context is assembled across wrong/duplicate physical databases:
  `runtime.db`, `memory_plane.db`, and `memory.db`.
- AgentRunner independently injects query recall, latent gold, and agent memory
  beyond ContextCompiler.
- Knowledge Ops produces staging/review/receipt artifacts but deliberately has
  no canonical mutation executor.
- `contracts.intelligence.MemoryPlane` / `SovereignMemoryPlaneAdapter` is another
  competing mutable runtime-fact writer, not the missing canonical writer.
- Live `vectors.db` was about 57 GiB with AUTOINCREMENT high-water 24,796,967;
  source code has no dedup column/index, live schema has drifted, `upsert()`
  always inserts, and only one current row had a populated `content_hash` in the
  dated snapshot.
- World Radar's Python bridge passes archive flags that the Go CLI does not
  implement; the live health artifact said archive disabled/count zero/bytes
  zero while raw HTTP bodies were discarded after parsing.

Do not repeat live mutable counts as current facts. Cite the dated receipt and
its WAL/high-watermark caveats.

## Verification already captured

The evidence receipt contains exact commands and outputs:

- focused kernel/retrieval suite: `56 passed, 14 warnings`;
- context/compiler group: `86 passed`;
- retrieval group: `22 passed, 18 warnings`;
- Knowledge Ops group: `22 passed`;
- event/index/hybrid/lattice group: `23 passed`;
- legacy/agent-memory group: `104 passed, 1 failed`.

The existing failure is real and must be disclosed, not fixed in this no-code
task:

```text
tests/test_memory_integration.py::TestBackwardCompatibility::
test_build_sections_accepts_knowledge_block

TypeError: ContextCompiler._build_sections() missing required keyword-only
argument: memory_kernel_section
```

The report's 260-line embedded SQLite DDL was also executed against an in-memory
SQLite database and parsed successfully. The current byte-pinned master-spec
SHA-256 is:

```text
00d30b6e700da89c883077562be579097ac2ca80f3978071581928cdb0adce76
```

## Review/council state

Three independent full-report reviewers initially returned `REVISE` and their
concrete objections were integrated: support-assessment separation, six-root
normalization, protected identity, current security basis, transaction/fencing,
vault crash protocol, deletion/restore closure, projection split, authority
issuance/revocation, async web intake, cycle guards, database neutrality,
source-maturity gaps, eval rigor, and exact repo corrections.

Preliminary six-provider council artifacts exist at:

```text
reports/agentops/decorrelated_review_council/
  20260710T151529Z-memory-kernel-knowledge-ops-v0_1-hold_blockers.{md,json}
  20260710T151943Z-memory-kernel-knowledge-ops-v0_1-network-retry-hold_blockers.{md,json}
```

The network-real retry had six critic scores 78/82/84/90/92/100, average 87.67,
with three approves and three revises; the persistent A2A witness was not fresh
then, so status correctly remained `HOLD_BLOCKERS`.

A complete v0.2 round then ran with all six requested lanes and a fresh
persistent witness:

```text
reports/agentops/decorrelated_review_council/
  20260711T001737Z-memory-kernel-knowledge-ops-v0_2-hold_blockers.{md,json}
scores: 68/78/82/89/93/95; average 84.17; HOLD_BLOCKERS
```

It found substantive finalization/contract gaps. Those are now remediated in the
byte-pinned v0.2 candidate: matching version/changelog; research-only fence and
Phase 0 owner/exit table; gateway-only DML; exhaustive constructor-emission
matrix; special sealed genesis; signed/fenced commits; security-event batches
and strict folds; outbox shadow-definition identity; contradiction comparator
and direction semantics; CRDT/root-pressure fixtures; separable-axis composition;
storage neutrality; retention/tamper defaults; and concrete golden fixture
specifications. Three independent reviewers rechecked the final repository,
frontier, and data/trust concerns and each returned `PASS`.

Do not call the report 100/100 or production-ready. The only remaining council
step is the remedial rerun over this exact pinned candidate with a fresh witness;
the result must be appended honestly even if it remains `HOLD_BLOCKERS`.

Required council defaults are documented by the local
`codex-composer-decorrelated-review-council` skill and currently are:

```text
ollama:glm-5.2:cloud
ollama:kimi-k2.7-code:cloud
ollama:qwen3-coder:480b-cloud
ollama:deepseek-v4-pro:cloud
ollama:minimax-m3:cloud
openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free
```

Use the council skill exactly and attach the master spec, evidence receipt,
`docs/architecture/MEMORY_KERNEL_PROD_BAR.md`, and
`docs/architecture/memory_kernel_current_intent.md`. Network access may require
scoped escalation. Verify witness freshness immediately before the run.

## Exact remaining closeout

1. Verify the Palantir witness is running/fresh, then rerun the six-lane
   decorrelated council against the exact pinned v0.2 master and current receipt.
2. If it identifies a genuine research-contract blocker, patch it, recompute the
   master hash, update the receipt, and rerun; reject demands to implement the
   explicitly out-of-scope Phase 0 runtime fixes as a condition for reviewing a
   no-code research artifact.
3. Append/link the remedial council receipt and its honest scores/witness state,
   then compute the final evidence-receipt and handoff hashes.
4. Reconfirm master hash, DDL parse, 103 local references, balanced fences,
   focused 56-test pass, census/readiness, known single failure, and
   `git diff --check` if any file changed.
5. Commit only task-owned architecture files if normal repository policy allows;
   preserve all unrelated dirty work. Mark the active goal complete
   only when all 16 deliverables, evidence binding, verification, and honest
   council closeout are finished.

## Preserve unrelated user work

Do not revert or modify these pre-existing paths:

```text
 M reports/governance/active_track_evidence.json
 M reports/governance/active_track_evidence.md
 M reports/governance/nats_live_production_matrix/latest.json
 M reports/governance/track_portfolio.json
?? docs/governance/REMOTE_HOLON_MESH_AND_SHARED_BOARD_V1.md
?? reports/governance/ONBOARD_META_NOTEBOOK.md
?? reports/governance/nats_live_production_matrix/nats-live-20260708T005030Z-23095df4/
?? reports/governance/nats_live_production_matrix/nats-live-20260709T144535Z-f434a78a/
?? scripts/runtime/sync_agent_keys_to_vps.sh
```

Task-owned new architecture paths are the master spec, this handoff, and the
dated evidence directory. Council artifacts may be gitignored.

## Completion standard

This is architecture research, not implementation authorization. Lead the final
handoff with the actual result, changed files, verification, current council
status, the existing test failure, and remaining operator decisions. The
strongest modest claim is:

> Dharma does not need another memory module. It needs a small typed epistemic
> kernel in which ordinary agents cannot forge modality or authority, while
> every expensive intelligence layer remains replaceable and every correction,
> revocation, and deletion remains historically honest and operationally
> enforceable.

---
