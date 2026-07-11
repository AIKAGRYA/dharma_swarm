# PROPOSED PIC VOCABULARY — object names for the Causal Action Receipt

**Status:** PROPOSAL, seed-labeled (5/100). **Not the SSOT.** This file proposes names;
it does **not** edit `PROPOSED_VOCABULARY.md` (the Layer-2 census) or any object/alias
manifest. Names here are candidates for a future census pass, resolved against the
existing grammar, not minted as canon.
**Authority:** naming floor is
`docs/architecture/ADRs/ADR-008-ontology-api-name-grammar.md` (camelCase plain-English
`api_name`, legible to any OSDK/A2A client; Sanskrit stays in narrative). Concept lineage
is subordinate to the CAR spec `docs/research/planetary_intelligence_commons/01_CAUSAL_ACTION_RECEIPT.md`
and its binding parent `docs/research/RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md`.
**Naming-SSOT rule (`CLAUDE.md`):** do not create a parallel naming scheme. If a branch
carries Semantic Commons manifests, these names must be reconciled against them before
adoption; until then they use the ADR-008 grammar as the floor.
**Anti-pattern guard:** if any name here is read as a new *record type to persist*, it has
been misread — every name below is a node/edge in an IR (a read-projection), never a store
(`01_CAUSAL_ACTION_RECEIPT.md` §1, §7).

---

## Why these names, and why only as a proposal

The CAR (`01_CAUSAL_ACTION_RECEIPT.md`) needs stable handles for its nine nodes and the
edges between them. The census posture (`PROPOSED_VOCABULARY.md:22`) is explicit: the
`api_name` must be legible to an agent that has never read a dharma doc, and the meaning
lives in the narrative, not the name. These names follow that posture. They are proposed,
not adopted, because (a) the portfolio is at WIP 10/10 with no PIC track, and (b) two of
the nodes have no internal owner yet (`01_CAUSAL_ACTION_RECEIPT.md` §8) — naming an object
before it has a producing owner is a proposal, not a canon entry.

Each entry: **one-line definition · CAR node served · what it is NOT · binds to.**

---

## The receipt itself

### `causalActionReceipt`
- **Definition.** A read-projection joining already-owned receipts into one portable,
  challengeable answer to the five constitutional questions for a single action.
- **CAR node.** The whole IR (the container over nodes 1–9).
- **Not.** Not a persisted record type; not an authority; not a token
  (`01_CAUSAL_ACTION_RECEIPT.md` §7). Not a second receipt store — that is the
  double-write trap (`RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md:165-169`).
- **Binds to.** `EvidenceReceipt` (`spine/receipt.py:41`) via `trace_id`; assembled at
  read time, re-derivable from source owners.

## The nine nodes

### `delegationRecord`
- **Definition.** The authority under which an action was taken, as a reference to an
  existing mandate/credential, not a new grant.
- **CAR node.** 1 — Authority.
- **Not.** Not a newly-minted credential; PIC mints no parallel authority.
- **Binds to.** `RuntimeReceipt.principal` (`runtime_state.py:714`); AP2 Mandate;
  Authenticated Delegation token ([arXiv 2501.09674](https://arxiv.org/abs/2501.09674));
  ERC-8004 principal binding.

### `intentionRecord`
- **Definition.** The declared purpose of an action plus whether it was met — telos, made
  checkable.
- **CAR node.** 2 — Telos.
- **Not.** Not a self-asserted, unchecked purpose string (the gap at
  `research/agentic_stack.md:166`); it must bind to an outcome.
- **Binds to.** telos-gate decision; `Leaf` intention
  (`packages/telos-kernel/telos_kernel/receipt.py:74`); AP2 Intent Mandate; A2A AgentSkill.

### `materialBurdenManifest`
- **Definition.** The real material cost an action creates — energy/water/minerals/
  downstream obligation — as a rebuttable, banded view.
- **CAR node.** 3 — Material burden.
- **Not.** Not a settled precise figure; ships with a p05/p95 band, never legal-grade
  (`07_SIS_MATERIAL_LEDGER.md:64-77`). Not a credit — it is the gross-carbon debit,
  non-fungible with the welfare-ton.
- **Binds to.** SIS projector over `EvidenceReceipt` (`spine/receipt.py:41`); SCI-for-AI;
  EcoLogits.

### `communityAuthorityGrant`
- **Definition.** A community's consent for an action, held as a **verifiable, portable,
  revocable** record with a local-veto primitive.
- **CAR node.** 4 — Legitimacy (the FPIC gap, `research/nature_finance_mrv.md:129`).
- **Not.** Not a static document/attestation; not decreed by the layer. **No internal
  owner yet** — external-only until SAB wakes (DORMANT, referenced only).
- **Binds to.** FPIC-as-revocable-record ([AFi FPIC](https://accountability-framework.org/fileadmin/uploads/afi/Documents/Operational_Guidance/OG_FPIC-2020-5.pdf));
  Regen Community Staking DAO.

### `evidenceRecord`
- **Definition.** What independently proves an action's result, as references to existing
  provenance artifacts.
- **CAR node.** 5 — Evidence.
- **Not.** Not a new evidence store; it unifies fragments others already own
  (`research/agentic_stack.md:167`).
- **Binds to.** `EvidenceReceipt` + `VerifiedMachineReceipt` (`spine/receipt.py:219`);
  C2PA 2.4; TEE attestation; Sigstore/Rekor; ClimateTRACE.

### `actionRecord`
- **Definition.** What was actually done or paid — the connective node tying authority and
  telos to a concrete act.
- **CAR node.** 6 — Capital / action (connective).
- **Not.** Not a payment rail; it references one.
- **Binds to.** `RuntimeReceipt` payload; `gaia_ledger` credit; AP2 Cart/Payment Mandate;
  x402 settlement.

### `witnessedOutcome`
- **Definition.** A decorrelated, externally-countersigned confirmation that the stated
  outcome actually occurred.
- **CAR node.** 7 — Evidence of result.
- **Not.** Not a single agent's say-so; minted only above an external decorrelated quorum
  (the One Wire posture; the Transcendence Principle as provenance).
- **Binds to.** `ClosureEvidenceReceipt` (`dharma_swarm/operator_core/closure_v0.py:69`);
  independent VVB; WRI outcome-payment.

### `challengeRecord`
- **Definition.** A filed contest of an action — who challenges, on what grounds, with what
  evidence.
- **CAR node.** 8 — Challenge (state: `CHALLENGED`).
- **Not.** Not a deletion; the original CAR persists, the challenge is appended
  (`01_CAUSAL_ACTION_RECEIPT.md` §5). **No internal owner yet** — new IR semantics.
- **Binds to.** ERC-8004 feedback revocation; `communityAuthorityGrant` (resolves *who*
  may challenge).

### `reversalEvent`
- **Definition.** The recorded effect of a successful challenge — clawback, retirement
  reversal, or re-opened obligation — with the quorum that decided it.
- **CAR node.** 8 — Reversal (state: `REVERSED → COMPOSTED`).
- **Not.** Not final-by-design settlement (the x402 gap, `research/agentic_stack.md:168`);
  not an erasure — it composts and propagates a `learningRecord`.
- **Binds to.** buffer-pool release; NVIDIA Earth-2 reversal-risk feed
  ([NVIDIA cBottle](https://blogs.nvidia.com/blog/earth2-generative-ai-foundation-model-global-climate-kilometer-scale-resolution/)).

### `learningRecord`
- **Definition.** What propagates back to the system from an action or its reversal, so
  failures and successes both become signal.
- **CAR node.** 9 — Learning (connective).
- **Not.** Not per-program siloed learning (the gap at `research/nature_finance_mrv.md:175`).
- **Binds to.** signal-bus emission; diversity-archive update (`archive.py`).

## Edges

### `outcomeGraphEdge`
- **Definition.** A typed causal link between two CARs — e.g. `causation_id` joining an
  upstream action to a downstream one — turning individual receipts into an outcome graph.
- **CAR node.** cross-node (the graph over CARs).
- **Not.** Not a new graph store; it is the join key made explicit
  (`01_CAUSAL_ACTION_RECEIPT.md` §3, `causation_id`).
- **Binds to.** `EvidenceReceipt.trace_id` / `causation_id`; DharmaGraph runtime (as a
  consumer, not an owner).

---

## The fence (proposal-status)

- **These are proposed names, not canon.** Adoption requires a census pass and
  reconciliation against the Semantic Commons manifests / ADR-008 grammar. This file edits
  no SSOT.
- **Every name is an IR node/edge, never a store.** If a build persists any of these as a
  canonical row with its own writer, it has violated the anti-double-write keystone.
- **Two nodes name things with no owner yet** (`communityAuthorityGrant`, `challengeRecord`/
  `reversalEvent`). The names exist so the gap is legible; the honesty of the missing owner
  is the point.
- **SEED 5/100.** $0 revenue, no track claimed.
