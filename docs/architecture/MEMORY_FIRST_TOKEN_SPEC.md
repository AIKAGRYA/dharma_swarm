# Memory First-Token Spec — evidence-class position, routing-time memory, decorrelated seats

**Status:** SPEC-FIRST. No code changes. This document is organism-rewire-2026-07 item 5.
**Serves spine objective:** `substrate-nativeness`.
**Ratified doctrine:** `docs/plans/ORGANISM_REWIRE_DOCTRINE_2026-07-02.md` §3 (D2). NORTH_STAR §8.5's
"memory-kernel first-token orientation" is superseded by the refinement below — §3 there
subordinates to CLAUDE.md's Transcendence Principle, and identical first-token memory across
worker seats is homogenization, which the Principle names as a diversity cost.
**Sequencing:** spec (this doc) → shadow canary with quality metrics → C5 gate amendment lands →
only then flip `context_compiler.py` section order. No step here authorizes the flip.

---

## 1. Evidence classes — what may occupy first-token

The current ordering conflates *module* (`memory_kernel_section`, appended at
`dharma_swarm/context_compiler.py:533-534`, `priority=4` set in
`dharma_swarm/memory_kernel/default_context.py:77`) with *trust*. A `Memory Kernel` section can
carry a stale narrative claim at the same priority as a receipt-backed fact — the COLM
dead-calendar failure is exactly this: a stale claim at first-token propagates fleet-wide before
anything downstream gets a chance to contradict it. The fix is to key position off evidence
class, not off which store produced the text.

Two evidence classes, ordered:

- **`structural`** — receipt-backed AND TTL-carrying. May occupy first-token (new priority band
  0-1, ahead of `Governance`/`Operator Intent`). Two independently necessary properties, both
  required together:
  - **receipt-backed**: traceable to a `dharma_swarm.spine.receipt.EvidenceReceipt` (`receipt_id`,
    `trace_id`) or, pre-spine-adoption completion, to a `MemoryFact.source_event_id` /
    `source_artifact_id` (`dharma_swarm/runtime_state.py:577-579`) that itself resolves to a
    logged event — never a bare narrative claim.
  - **TTL-carrying**: has an expiry the compiler enforces at render time. `MemoryFact` already
    carries `valid_from`/`valid_to` (`dharma_swarm/runtime_state.py:575-576`); `MemoryContextPack`
    items from `memory_kernel/atoms.py` carry `truth_state` (`TruthState` — `atoms.py:164-172`)
    but no first-class TTL field today. A fact with `valid_to=None` (no expiry) is **not**
    structural — indefinite TTL is a narrative habit wearing a structural coat.
- **`narrative`** — everything else: prose claims, palace hits, semantic-graph hits, prior-session
  summaries, knowledge-store propositions without a source digest. Stays depth-on-demand
  (`Retrieved Recall`, `Memory Palace`, `Semantic Context`, `Durable Facts` bands — unchanged).

**Concrete data each kernel fact must carry to be first-token-eligible** (additive fields, no
schema break):

| field | type | source today | gap |
|---|---|---|---|
| `provenance_ref` | str | `MemoryFact.source_event_id` / `source_artifact_id`; `MemoryAtom.source_refs`+`source_digest`/`source_row_key` (required by the `require_source_digest`/`require_source_row_key` query flags already set in `default_context.py:43-44`) | already present; needs a single normalized accessor (`provenance_ref()` helper) so `context_compiler.py` doesn't special-case per-store shapes |
| `ttl` | datetime \| None | `MemoryFact.valid_to` | `MemoryAtom`/`MemoryContextPack` items have no TTL field — **new field required** on the atom or a derived one computed at pack-build time from surface policy |
| `evidence_class` | `Literal["structural","narrative"]` | none | **new field** — computed, not stored: `structural` iff `provenance_ref is not None and ttl is not None and ttl > now`. Compute once in `context_compiler_utils` and stamp it onto `ContextSection.metadata["evidence_class"]` so downstream code (fit, canary, C5 scorer) reads one flag instead of re-deriving it. |

`evidence_class` is a derived predicate, not operator-set metadata — this closes the obvious
gaming vector (a narrative fact cannot promote itself to first-token by claiming a TTL it doesn't
enforce).

---

## 2. `context_compiler.py` section-priority redesign

**What changes.** Replace the flat `priority: int` ordering
(`dharma_swarm/context_compiler.py:44-58` `_SECTION_WEIGHTS`, and the `priority=1..9` literals
scattered through `_build_sections`, `dharma_swarm/context_compiler.py:439-693`) with a two-level
key: `(evidence_class_rank, priority)`. `evidence_class_rank` is `0` for `structural`, `1` for
`narrative`. Sort key at `_fit_sections` (`context_compiler.py:695-733`, currently
`sorted(sections, key=lambda item: item.priority)` at line 701) becomes
`sorted(sections, key=lambda item: (item.evidence_class_rank, item.priority))`.

**What stays.** `_SECTION_WEIGHTS` (char-budget allocation per named section) is untouched — this
spec changes *order*, not *budget share*. `Governance` keeps priority=1 semantics but is
re-ranked relative to any `structural`-class fact section that out-trusts it. Section names,
`ContextSection` dataclass shape (`context_compiler_utils.py`), and the trim/truncate mechanics in
`_fit_sections` are unchanged. `Memory Kernel` (`default_context.py:77`, currently hard-coded
`priority=4`) stops being a privileged module-level priority; each `MemoryContextPack` item is
split at render time into a `structural` sub-section (admitted atoms whose `evidence_class ==
structural`) and a `narrative` sub-section (the remainder), each carrying the section's existing
priority number for ties within its class. `Always-On Memory` (`priority=4`,
`context_compiler.py:535-543`) and `Relevant Knowledge` (`priority=4`, line 550) are narrative by
default (no TTL enforcement in `memory_lattice.always_on_context` or `knowledge_store` today) and
sort after all `structural` content unless a future TTL is added to those stores.

**How `memory_kernel_shadow` becomes the canary for the new ordering.** The existing shadow path
(`dharma_swarm/memory_kernel/context_compiler_shadow.py`, `run_memory_kernel_context_canary`,
appended at `priority=99` in `context_compiler.py:368-375`) already runs a parallel MemoryKernel
render without touching `rendered_text` in `off`/`shadow` mode (M3E contract: "must not alter
`ContextBundleRecord.rendered_text`"). Extend this wrapper, don't build a second one: add a third
canary axis alongside the existing `mode` (`off`/`shadow`/`append`) — `ordering_mode`
(`legacy`/`evidence_class_shadow`) — that computes what the bundle **would** look like under
`(evidence_class_rank, priority)` ordering and stamps a diff into
`MemoryKernelContextCanaryResult.metadata` (new keys: `evidence_class_reorder_diff`,
`structural_sections_promoted`, `narrative_sections_demoted`) without changing `rendered_text`.
Reuses the fail-closed contract proven across M3E-M4B (disabled by default, additive metadata
only, existing env-var resolution in `resolve_memory_kernel_context_mode`) instead of inventing a
parallel canary mechanism.

**Metrics that decide promotion** (both required, measured over the shadow window before any
flip PR is opened):

1. **Completion quality delta.** Paired comparison of agent-run outcomes (existing telos-gate /
   arena scoring surfaces — reuse `dharma_swarm/coordination/` scorer conventions, not a new
   judge) between `legacy` ordering and `evidence_class_shadow` ordering on the same task set.
   Promotion bar: evidence-class ordering must not regress completion quality outside noise
   (bootstrap CI overlap check, same discipline as Arena v1 §3 of
   `LEARNED_AUDITABLE_ORCHESTRATOR_SPEC.md`), and must show measurable improvement on tasks where
   the legacy ordering placed a since-superseded/expired fact ahead of a valid receipt (the
   COLM-class failure the reorder targets).
2. **Token budget displacement.** `structural` sections must not crowd out `narrative` sections
   below a floor (`_fit_sections`'s existing pop/truncate loop, `context_compiler.py:719-732`,
   already measures this via `len(rendered) > char_budget`). Track `narrative_chars_dropped`
   per bundle in shadow mode; promotion bar: displacement stays within the same order of magnitude
   as today's trim rate (baseline captured from current `_fit_sections` truncation telemetry) —
   evidence-class ordering must not systematically starve narrative depth just because structural
   sections sort first.

Both metrics land as fields on the existing `bundle_metadata["memory_kernel_context"]` block
(`memory_kernel_context_metadata`, `context_compiler_shadow.py`) — no new metrics store.

---

## 3. Routing-time memory — the seam

Doctrine §3.2: "the kernel's highest-leverage seat is upstream: informing WHICH agent gets the
task and with which constraints (skill selection)." The exact seam is
`SwarmOrchestrator._select_idle_agent` (`dharma_swarm/orchestrator.py:1118-1168`), called from
`route_next` (`orchestrator.py:282`, call site at `orchestrator.py:302`) and from `fan_out`
(call site at `orchestrator.py:264`).

**Integration sketch (no code in this doc).** `_select_idle_agent` already runs a candidate
funnel — name-matched → role-matched → all idle (`orchestrator.py:1130-1148`) — then two
best-effort bias passes: `_efe_biased_pick` (active-inference EFE) and `_fitness_biased_pick`
(evolution fitness), falling through to FIFO. Routing-time memory becomes a **third bias pass**,
`_memory_biased_pick(candidates, task)`, inserted in that same chain (after `_fitness_biased_pick`,
before the FIFO fallback, or reordered relative to the other two — an implementation-time
decision, not a spec-time one). It queries `self.memory_kernel` (the kernel is not currently a
constructor field on `SwarmOrchestrator` — this is the one new wiring point: thread a
`memory_kernel: Any = None` reference into the orchestrator the same way `ContextCompiler`
already receives it at `context_compiler.py:69`) for **routing facts only** — a narrow query
shape distinct from the context-compiler's content query: "which candidate agents have
`structural`-class evidence of prior success/failure on this task's skill tags" — and returns a
re-ranked or filtered candidate list. It never rewrites `task.description` or injects prompt
content; it only narrows/orders **who**. This keeps memory's routing influence auditable
separately from its content influence, and keeps the blast radius of a bad routing fact bounded to
"wrong agent picked" (recoverable — retried) rather than "wrong fact believed" (silent,
fleet-wide).

**Constraint propagation.** If the kernel returns constraints (e.g. "agent X previously failed
this skill tag under provider Y"), they attach to `TaskDispatch.metadata` (already a free-form
dict, `td.metadata["dispatch_started_monotonic"]` sets precedent at `orchestrator.py:1986`) as
`td.metadata["routing_memory_constraints"]` — visible in the dispatch receipt without being
prompt content.

---

## 4. Diversity-preserving sampling for worker seats

Doctrine §3.3 and CLAUDE.md's Transcendence Principle both require this: broadcasting identical
first-token memory to every worker seat collapses the Krogh-Vedelsby diversity term
(`E_ensemble = E_mean - E_diversity`) exactly where the organism most needs decorrelated errors —
parallel `fan_out` dispatches (`orchestrator.py:250-267`) are the textbook case: N agents given the
*same* task should not all inherit the *same* first-token priors, or their errors correlate and
aggregation buys nothing.

**Mechanism.** `agent_uid` already exists as the stable per-agent identity concept
(`dharma_swarm/external_agent_registration.py:249`, `dharma_swarm/roaming_onboarding.py:95-103`,
memory namespace `f"agent:{agent_uid}"` at `roaming_onboarding.py:173`). Seat sampling keys off
it: `seed = stable_hash(agent_uid, task_id)` (deterministic — same agent, same task, same sample,
every run; reproducible for replay/audit, unlike a random seed) selects a **subset** of the
`structural`-class candidate atoms for that seat's first-token band, e.g. a k-of-n draw over
`MemoryContextPack.items` filtered to `evidence_class == structural`, rather than the full
admitted set. `k` is a budget-controlled parameter (existing `MemoryContextBudget.max_admitted_atoms`,
`default_context.py:48`, becomes the per-seat cap instead of a global cap).

**Coordinator/hub/composer exception.** Doctrine explicitly allows full first-token view for
seats that synthesize across workers (`fan_in`, `orchestrator.py:268-278`, and any `coordinator`/
`composer`-role agent per `AgentState.role`). These seats need the complete structural set to
reconcile worker outputs; decorrelation is a worker-seat property, not a system-wide one. Role
check: `agent.role` values already distinguish these (`_select_idle_agent`'s `preferred_roles`
matching at `orchestrator.py:1141-1145` shows the role vocabulary exists) — gate the sampling
subset vs. full-view choice off `agent.role in {coordinator, composer, hub}` at the same call site
that builds each seat's `ContextBundleRecord` (`compile_bundle`, `context_compiler.py:101`, new
`agent_uid` and `role` parameters threaded through from the dispatch call site).

---

## 5. C5 gate amendment

Current `score_c5` (`scripts/governance/trust_gate_status.py:316-343`) measures **module-first**
adoption: it statically scans `_build_sections` for `sections.append(memory_kernel_section)`
(`memory_kernel_position`, `trust_gate_status.py:295-313`) and scores 0.9 only when the
`Memory Kernel` section is literally the first `sections.append(...)` call. This directly rewards
the ordering this spec supersedes — under the new design, `Memory Kernel` is *split* across
`structural`/`narrative` sub-sections and is never a single monolithic first append, so unmodified
`score_c5` would regress to 0.0 (`wired=True, before>0` → the 0.2 branch, or worse if the static
scan can't find the literal append at all) the moment the reorder lands, even though the new
ordering is *more* first-token-correct than the old one.

**Proposed semantics.** Replace the static-scan measure with an evidence-class measure:
`score_c5` should confirm that (a) `context_compiler.py` sorts by
`(evidence_class_rank, priority)` (grep for the new sort key, replacing the
`memory_kernel_position` scan), and (b) at least one `structural`-class section is present ahead
of the first `narrative`-class section in a **live sampled bundle**, not just a source-scan — the
static-scan approach was already flagged in the current docstring ("a static source scan is the
honest measure available now; it flips the moment someone reorders", `trust_gate_status.py:296-300`)
as a stopgap. Concretely: `score_c5` gains a second evidence source, a fixture bundle build (small
`compile_bundle()` call against a seeded `RuntimeStateStore` with one receipt-backed TTL'd fact and
one narrative fact) and asserts the structural fact's section renders before the narrative
section's in `rendered_text`. Score bands:
- `0.0` — evidence-class sort key absent, or structural content never renders ahead of narrative.
- `0.5` — sort key present, fixture passes, but no live-traffic sample confirms it under real
  dispatch (source-scan-only confidence — same caveat as today).
- `0.9` — sort key present AND a live `reports/swarm_genome/` sample
  (existing cross-check at `trust_gate_status.py:337-341`) shows a structural section preceding
  a narrative one in an actual dispatched bundle.

This keeps `score_c5`'s existing shape (evidence list + score + owner-of-truth pointer to
`context_compiler.py` + `reports/swarm_genome/`) and its position in `build_scoreboard`
(`trust_gate_status.py:346-354`) unchanged — only the measurement predicate inside the function
changes.

---

## 6. Rollout: spec → canary → flip → rollback

1. **Spec** (this document). No code changes. Lands as documentation only.
2. **Canary.** Implement the `ordering_mode=evidence_class_shadow` extension to
   `context_compiler_shadow.py` (§2). Ships disabled by default, same fail-closed contract as
   every prior M3x/M4x memory-kernel shadow increment. Run against real dispatch traffic long
   enough to gather both promotion metrics (§2) — no fixed duration prescribed here; the
   promotion bar is metric-based, not calendar-based, consistent with this track's TTL-verification
   discipline elsewhere.
3. **C5 amendment PR.** Land §5's `score_c5` rewrite *before* the ordering flip, so the gate
   measures the target state correctly the moment it's reachable. This PR does not flip
   `context_compiler.py` itself — it only changes what "correct" means for the gate.
4. **Flip.** A single PR changes the `_fit_sections` sort key from `item.priority` to
   `(item.evidence_class_rank, item.priority)` and threads `evidence_class` onto `ContextSection`
   (§1-§2). Gated on: both promotion metrics clearing their bars, `score_c5` (amended) scoring
   ≥0.5 against the new code pre-merge via the fixture check, and routing-time memory (§3) +
   diversity-preserving sampling (§4) landing first or in the same change — flipping ordering
   without the sampling decorrelation would re-homogenize worker first-token content the moment
   structural sections start winning the sort, defeating §4 before it ships.
5. **Rollback.** The flip is a single sort-key change plus one new derived field
   (`evidence_class`) — no schema migration, no data deletion. Rollback is reverting the PR;
   `MemoryFact`/`MemoryAtom` records are unaffected since `evidence_class` is computed, never
   stored. The shadow canary path stays live post-flip (mode can be set back to `shadow`) so a
   regression can be diagnosed by re-diffing legacy vs. evidence-class ordering without a second
   deploy.

---

## Non-goals (inherited from the track; restated for this spec)

- Does not flip `context_compiler.py` ordering. That is a separate, gated PR (§6 step 4).
- Does not change `EvidenceReceipt` schema (`dharma_swarm/spine/receipt.py`).
- Does not add a TTL field to `MemoryAtom`/`MemoryContextPack` in this document — §1 names the
  gap; closing it is canary-phase work.
- Does not broadcast identical first-token memory to worker seats now or after the flip (§4 is a
  hard design constraint, not an optimization).
- Does not let market P&L, arena internals, or any internal-only signal decide the promotion
  metrics in §2 — completion quality is measured against the same receipted/telos-gated surfaces
  the rest of the organism already trusts.
