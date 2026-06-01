# Andon Reconciliation — Codex Audit vs Repo Ground Truth

**Reconciled by:** perplexity-computer
**At:** 2026-06-01T06:50Z
**Inputs:** verdicts/perplexity-A.md (identity), verdicts/perplexity-B.md (envelopes), verdicts/perplexity-C.md (authority+execution)
**Branch:** perplexity-grounding/1780289724-vocabulary-census
**Andon state:** verdicts in; reconciliation drafted; cord ready for operator close decision.

This document is **not** a doctrine update. It is a single-source-of-truth summary of what the Codex audit got right, what it got wrong, what it missed, and what (if anything) Layer-2 Revision 3 should name.

---

## Headline pattern across A + B + C

**Codex is directionally correct on fragmentation, but evidentially sloppy.** It pattern-matches on the smell of duplication and is right that the repo has real ID/envelope sprawl. But it (a) hallucinates names (`correlation_key`, "spec envelope", `nats_a2a_bridge.py`), (b) miscounts (NATS wire formats, the 8th envelope, the 4-way `claim_id` collision it listed as one), (c) confuses domain stores with ontology authorities (C1), and (d) audits its own **untracked working-tree files** as if they were repo state (C4). Net: the audit is a usable smoke signal pointing roughly at real engineering debt, not a reliable specification of that debt.

---

## Verdict matrix (one row per Codex claim)

| # | Codex claim | Slice verdict | Reality (cite) |
|---|---|---|---|
| 1 | 10+ incompatible ID schemes | **partially_confirmed** | A — 13 surfaces real. `correlation_id` is *aliased to `trace_id`* by `spine/__init__.py:15-24` and `spine/receipt.py:94-96` (Codex missed this). `correlation_key` does not exist (`verdicts/perplexity-A.md` table row). `claim_id` quietly fragments into 4 surfaces with 4 generators — *worse than Codex claimed*, Codex listed it once. |
| 2 | 7 envelope schemas, pairwise incompatible | **partially_confirmed** | B — 6 of 7 confirmed and only 3 of 15 pairwise paths have translators (real sparse bridging). 7th "spec envelope" does not exist as code. NATS undercounted — there are at least 3 ad-hoc wire formats. An 8th envelope (`CanonicalEvent` at `dharma_swarm/engine/events.py:58`) was missed by Codex entirely. |
| 3 | 5–7 ontology stores claim authority | **overstated** | C1 — single two-layer stack: `OntologyRegistry` (in-memory) + `OntologyHub` (SQLite), accessed through one shared singleton `get_shared_registry()` (`ontology_runtime.py:116`). Codex counted domain stores (`ArtifactStore`, `CheckpointStore`, etc.) as ontology authorities. They are not. |
| 4 | `execute_action` at `ontology.py:637` logs success without applying mutations | **confirmed** | C2 — `ontology.py:594-639` sets `result="success"` unconditionally, never reads `ActionDef.modifies`, never calls `update_object`. No test asserts mutation. **This is real and is the load-bearing engineering finding of the entire audit.** |
| 5 | InterruptGate auto-approves without handler (toy) | **partially_confirmed** | C3 — production singleton at `cascade.py:36` is wired `callback=None, auto_approve=True`. A full callback+timeout+filesystem path exists in the class (`checkpoint.py:114-119`). Codex's "toy" framing is lazy; the architectural primitive is there, the wiring choice in production is the gap. |
| 6 | A2A is both external protocol and internal work queue (dangerous conflation) | **not directly verified this round** | Slice E was not picked up by perplexity; goes back to fleet for any agent. |
| 7 | NATS bridge publishes without canonical envelope | **wrong** | C4 — `nats_a2a_bridge.py` is **untracked working-tree code** that has never been on `main` or this branch. Codex audited code that does not exist in the repo. |
| 8 | Multiple workflow-state owners, no `workflowRun` boundary | **not directly verified this round** | Slice D was not picked up by perplexity; goes back to fleet. |

---

## What Codex MISSED that matters (Slice F findings, pulled from A/B/C side-notes)

1. **`claim_id` 4-way collision (from A).** Four independent surfaces, four generators, zero FKs. Query for `claim_id` in one store has no defined relationship to any other. **This is the single sharpest identity problem in the repo and Codex listed it as one item.**

2. **`agent_id` is type-inconsistent (from A).** Sometimes UUID hex (`AgentConfig.id`), sometimes role name string (`"claude"`, `"orchestrator"`). Same field, different runtime types depending on call site. `AGENT_IDENTITY_UNIFICATION.md` was archived as unfinished.

3. **`CorrelationContext` is voluntary, not enforced (from A).** A real unification layer exists at `correlation_context.py:113-155` but no ID-bearing struct (`DelegationRun`, `A2ATask`, `TaskClaim`) reads from it on construction. The unification is theoretical.

4. **`idempotency_key` has two incompatible generators (from A).** `_new_id("idem")` (random UUID) on the board side; `_stable_id(...)` (SHA-256 of content) on memory-promotion side. Same name, structurally incompatible — a random key cannot replay-dedupe; a hash key cannot be found by random lookup.

5. **`trace_id` has two generators on the A2A path (from A).** `correlation_context._new_trace_id()` produces `trc_<hex>`; `A2ATask.trace_id` defaults to empty string. Correlation chain breaks silently when A2A is in the loop.

6. **`CanonicalEvent` exists and is uncatalogued (from B).** A real 8th envelope at `dharma_swarm/engine/events.py:58`.

7. **NATS wire fragmentation is 3+, not 1 (from B).** Codex named NATS as one envelope; the bus actually carries 3+ ad-hoc dict shapes.

---

## Implications for Layer-2 Revision 3 (field-bridge types)

Now I can answer the question that triggered the andon — *should Revision 3 of PROPOSED_VOCABULARY.md add field-bridge types?* For each candidate I had on the table:

### `executionIdentity` (unified ID model) — **PROCEED, but re-scope**

- ✅ Justified by A. 13 surfaces are real.
- 🔄 Re-scope: the headline isn't "many ID names." It's that **(i)** `claim_id` fragments 4 ways with no FK contract, **(ii)** `CorrelationContext` exists but is voluntary, **(iii)** `agent_id` is type-inconsistent. A field-bridge type named `executionIdentity` should *name the contract that `CorrelationContext` already tries to be* — making the voluntary mechanical.
- 🔗 Field invariant: A2A `Task.id` / LangGraph `thread_id` / Temporal `WorkflowExecution.RunId` / OpenTelemetry `trace_id`. All of these are versions of the same concept (a durable boundary for a unit of execution). Naming `executionIdentity` does what John asked — bridges the field invariant *and* names what dharma_swarm already half-built.

### `runEnvelope` (canonical wire envelope) — **PROCEED**

- ✅ Justified by B. 6 real envelopes, sparse bridging (3/15 translators), 3+ NATS wire shapes, 8th envelope uncatalogued.
- 🔗 Field invariant: A2A message envelope / LangGraph `BaseMessage` / Temporal `Payload` / NATS message + headers / OpenTelemetry `Span` attributes. Real cross-protocol convergence.

### `workflowRun` (durable execution boundary) — **DEFER pending Slice D**

- ⚠️ Slice D was not verified this round (no agent picked it up). The "no `workflowRun` boundary" claim is unverified.
- 🔍 Action: get Slice D verdict before naming this. `DelegationRun` at `runtime_state.py:368` may already be the boundary, in which case the move is renaming, not inventing.

### `authority` (meta-type declaring canonical owner per Layer-2 object) — **KILL**

- ❌ C1 invalidates this. There is one canonical ontology stack with a singleton accessor. The "5–7 authorities" rhetoric was Codex misreading domain stores. No need for a meta-type to declare what's already singular.

### Binding fix for `actionDefinition` + `gateDecision` — **CRITICAL, NOT A NEW TYPE**

- C2 is the real bug. The existing `actionDefinition.modifies` is declared but **not read** by `execute_action`. The existing `gateDecision` passes but **mutation never fires**. This is Layer 1.5 (binding) work, not Layer 2 (naming).
- 🔧 The right move: keep the Revision 2 types, file a separate engineering ticket against `ontology.py:594-639` to honor `ActionDef.modifies`. **Do not invent a new type to solve a binding bug.**

### `interrupt` / `humanReview` — **PROCEED narrowly**

- C3 verdict is mixed. The class exists; production wiring pins auto-approve. A field-bridge type `humanReview` (or `interrupt`) matching LangGraph's `interrupt` / Temporal's `Signal` / A2A's `input-required` state would name the contract production should adopt.

### `subject` / `stream` (NATS event-channel) — **DEFER**

- B revealed NATS wire fragmentation but didn't reveal a missing event-channel concept. Subjects exist; envelopes don't. Address envelope (`runEnvelope`) first.

### `trace` / `causalLink` (OpenTelemetry invariant) — **MERGE into `executionIdentity`**

- A showed `trace_id` is already aliased to `correlation_id` by the spine. The bridge type is already half-named. Fold this into the `executionIdentity` contract; don't proliferate.

### `toolBinding` (MCP-era invariant) — **OUT OF SCOPE this round**

- Nothing in the audit or the verdicts touches MCP. Defer.

---

## Final Revision-3 shape (proposed, conditional on operator approval)

If the operator closes the andon and authorizes Revision 3, the change set is:

**Add (3 new types, narrowly scoped):**

1. `executionIdentity` — names the contract `CorrelationContext` already half-implements, plus `claim_id` deduplication policy. Field invariant: A2A `Task.id` / LangGraph `thread_id` / Temporal `RunId` / OpenTelemetry `trace_id`.
2. `runEnvelope` — canonical wire envelope. Field invariant: A2A message / LangGraph `BaseMessage` / NATS message + headers.
3. `humanReview` (or `interrupt`) — names the existing InterruptGate's intended contract. Field invariant: LangGraph `interrupt` / Temporal `Signal` / A2A `input-required`.

**Defer (pending slices D, E):**

4. `workflowRun` — needs Slice D verdict on workflow-state ownership.

**Kill:**

5. `authority` meta-type — C1 invalidates.

**File as engineering ticket, not vocabulary:**

6. C2 binding bug — `execute_action` does not honor `ActionDef.modifies`. Separate PR; Revision 2 types are correct; the implementation needs to catch up.

**Out of scope this round:**

7. `toolBinding`, `subject`/`stream`, separate `trace`/`causalLink` (folded into `executionIdentity`).

---

## What the operator needs to decide

1. **Close andon?** Three out of six slices have verdicts (A, B, C). Slices D (workflow-state) and E (A2A external/internal collision) were not picked up by perplexity-computer this round; no other agent has posted a verdict yet. **Option (i):** close andon now and ship narrow Revision 3 (add `executionIdentity`, `runEnvelope`, `humanReview`; defer `workflowRun`). **Option (ii):** keep andon open another tick to wait for D/E verdicts from claude/devin/hermes/mike before finalizing.
2. **File C2 separately?** The mutation-binding bug is real engineering debt that should not block vocabulary work. Recommend filing as separate issue against `ontology.py:637`.
3. **Field-invariant naming check:** the three proposed names (`executionIdentity`, `runEnvelope`, `humanReview`) are deliberately chosen to match A2A / LangGraph / Temporal / OpenTelemetry vocabulary while also naming what dharma_swarm already half-built. Operator approval needed on the names themselves before they enter PROPOSED_VOCABULARY.md.

---

## What we will NOT do without operator approval

- Will not amend `PROPOSED_VOCABULARY.md`.
- Will not file the C2 binding bug as a separate PR (operator decides whether to scope it that way).
- Will not extend the andon scope or reopen verdicts already accepted.
- Will not declare Codex's untracked working-tree code (C4 ghost files) as repo state, ever.
