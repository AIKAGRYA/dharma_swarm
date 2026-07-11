# PIC 01 — The Causal Action Receipt (CAR): an IR / read-projection, never a store

**Series:** PIC research — `00_FIELD_MAP.md` (external field) · `01_CAUSAL_ACTION_RECEIPT.md`
(this file) · `02_WEDGE_AND_ROADMAP.md` (arcs, partners, objections). The *why* lives in
`docs/vision_maps/2026-07-11_planetary_intelligence_commons.md`.
**Status:** SEED (5/100). **Spec of an intermediate representation, not a shipped
receipt type.** $0 revenue, no track claimed (portfolio WIP 10/10,
`docs/governance/ACTIVE_TRACK.yaml`).
**Authority — this is the load-bearing one:** the CAR is **subordinate to the binding
ADR** `docs/research/RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md` (PR #471). It inherits that
ADR's anti-double-write rule verbatim (`:145-151`) and may **never** be read as licence
to mint a new receipt store. Also subordinate to `docs/vision_maps/NORTH_STAR.md` and
`docs/governance/SOVEREIGN_MANIFEST.md §Telos Hierarchy`.
**Naming:** camelCase plain-English `api_name` per the naming floor
(`docs/architecture/ADRs/ADR-008-ontology-api-name-grammar.md`); proposed object names
are registered as *proposal-status* in
`docs/research/palantir-ontology/vocabulary-census/PROPOSED_PIC_VOCABULARY.md`, not in
the SSOT. Sanskrit stays in narrative only.
**Anti-pattern guard:** if a future build ever adds a "canonical PIC receipt store," the
CAR has been misread and Move 1 of the braid is violated. The CAR is a *view*.

---

## 0. The one sentence

> **A Causal Action Receipt is a read-projection that joins already-owned receipts —
> internal ones for our own actions, external protocol objects for the wider agentic
> internet — into one portable, challengeable answer to the five constitutional
> questions for a single action. It owns no truth. It mints nothing. It is an IR.**

Everything else in this file elaborates that sentence and fences it.

## 1. Why an IR and not a receipt

The repo already proved, as a binding ADR, that when an inner layer owns a receipt the
outer layer must **associate / project, never mint a second one**
(`RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md:145-151`). SIS obeys it: the material-burden
ledger is "a read-model projection over `EvidenceReceipt` … creates no new truth store,
no daemon, no second receipt" (`docs/research/verified_nature_house/07_SIS_MATERIAL_LEDGER.md:33-40`).
The external field map independently prescribes the identical rule for the whole agentic
internet — "interoperate, don't duplicate" (`research/agentic_stack.md:181`;
`00_FIELD_MAP.md` § "Gap analysis").

The CAR is that rule applied to the accountability question. It is the same architectural
move as SIS, one level up: **project over the owners, never become an owner.** An IR
(intermediate representation) is the right noun — like a compiler's IR, it is derived,
disposable, and re-derivable from source; it is not the source.

## 2. The nine nodes

Each node answers one constitutional question (or a necessary connective). The node set
is the *same nine* that the nature-finance pipe breaks at (`00_FIELD_MAP.md` §2;
`research/nature_finance_mrv.md:163`) — the CAR is domain-neutral, but nature is where
its nodes were independently rediscovered by another field.

| # | Node (`api_name`) | Question | Projects from (internal) | Binds to (external) |
|---|---|---|---|---|
| 1 | `delegationRecord` | **Authority** — under whose authority? | `RuntimeReceipt.principal` / identity fields (`runtime_state.py:714`) | AP2 Mandate; Authenticated Delegation token ([arXiv 2501.09674](https://arxiv.org/abs/2501.09674)); ERC-8004 principal binding; OAuth `act` chain |
| 2 | `intentionRecord` (telos) | **Telos** — what purpose, and was it met? | telos-gate decision + `Leaf` intention (`packages/telos-kernel/telos_kernel/receipt.py:74`) | AP2 Intent Mandate; A2A AgentSkill; CSA purpose declaration |
| 3 | `materialBurdenManifest` | **Material burden** — what real cost? | SIS projector over `EvidenceReceipt` (`spine/receipt.py:41`; `07_SIS_MATERIAL_LEDGER.md:33`) | AP2 budget constraints; SCI-for-AI; EcoLogits |
| 4 | `communityAuthorityGrant` | **Legitimacy** — whose consent, revocable? | *(external-only for now — no internal owner; SAB when it wakes)* | FPIC-as-revocable-record ([AFi FPIC](https://accountability-framework.org/fileadmin/uploads/afi/Documents/Operational_Guidance/OG_FPIC-2020-5.pdf)); Regen Community Staking DAO |
| 5 | `evidenceRecord` | **Evidence** — what independently proves it? | `EvidenceReceipt` + `VerifiedMachineReceipt` (`spine/receipt.py:219`) | C2PA 2.4; TEE attestation; Sigstore/Rekor; ERC-8004 Validation; ClimateTRACE |
| 6 | `actionRecord` (capital) | connective — what was actually done/paid? | `RuntimeReceipt` payload; `gaia_ledger` credit | AP2 Cart/Payment Mandate; x402 settlement; Isometric cert |
| 7 | `witnessedOutcome` | **Evidence of result** — decorrelated confirmation | `ClosureEvidenceReceipt` (`dharma_swarm/operator_core/closure_v0.py:69`) | independent VVB; Sylvera/BeZero rating; WRI outcome-payment |
| 8 | `challengeRecord` / `reversalEvent` | **Challenge / reversal** — who can undo, on what grounds? | *(new IR semantics — see §5; no internal owner yet)* | ERC-8004 feedback revocation; buffer-pool release; NVIDIA Earth-2 reversal-risk feed |
| 9 | `learningRecord` | connective — what propagates back? | signal-bus emission; diversity-archive update | (domain feedback loops) |

Node 4 and node 8 are the two the whole external field is *missing* (FPIC-as-record and a
portable reversal primitive, `00_FIELD_MAP.md` §1–2). They are exactly where the CAR
earns its keep — and exactly where it has **no internal owner yet**, so they are honestly
marked as IR-only semantics, not projections of anything shipped.

## 3. Field sketch (illustrative types — SEED, not frozen)

```python
# ILLUSTRATIVE. Not a Pydantic model to ship. A CAR is assembled at read time
# from join keys, never persisted as a new canonical row.
class CausalActionReceipt:            # api_name: causalActionReceipt
    car_id: str                        # deterministic hash of (trace_id, action_id) — derivable, not authoritative
    trace_id: str                      # JOIN KEY → EvidenceReceipt.trace_id
    causation_id: str | None           # JOIN KEY → upstream action that caused this one
    # --- the nine nodes, each a reference + projected view, never a copy-of-record ---
    delegation: DelegationRef          # → RuntimeReceipt.principal / AP2 mandate id / ERC-8004 addr
    intention: IntentionRef            # → telos-gate decision id / Leaf id
    material_burden: BurdenView        # → SIS projection (gross gCO2 + p05/p95 band), rebuttable
    community_authority: GrantRef | None   # → FPIC record id (external); None until node exists
    evidence: list[EvidenceRef]        # → EvidenceReceipt / VMR / C2PA manifest / Rekor entry ids
    action: ActionRef                  # → RuntimeReceipt payload / AP2 Cart id / x402 tx
    witnessed_outcome: OutcomeRef | None   # → ClosureEvidenceReceipt id; decorrelated quorum result
    challenge: list[ChallengeRef]      # → challengeRecord ids (may be empty)
    learning: LearningRef | None       # → signal-bus / archive update id
    # --- provenance of the projection itself ---
    projected_at: datetime
    source_owners: dict[str, str]      # node → owning system, so any node can be re-derived from source
```

The rule the sketch encodes: **every field is a reference or a projected *view* carrying
its `source_owner`, never a copied system-of-record.** A CAR can be thrown away and
rebuilt from `trace_id` alone. That is what makes it an IR.

## 4. Binding rules (inherited from the ADR, non-negotiable)

1. **No new persistence path.** The CAR is assembled at read time by joining on
   `trace_id` / `receipt_id` / `causation_id`. It does not get its own table, daemon, or
   append log. (`RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md:145-151`; the association/projection
   flow at `:153-163` is the exact pattern to follow.)
2. **Association, never minting.** Where an internal owner already writes the receipt
   (EvidenceReceipt on dispatch; the single RuntimeReceipt on the A2A path,
   `RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md:141`), the CAR *links* to it. It never writes a
   parallel RuntimeReceipt. Invariant to preserve: `count(runtime_receipts WHERE
   run_id=R) == 1` per dispatch (`:149`).
3. **External nodes bind, they don't re-issue.** `delegationRecord` references an AP2
   mandate or ERC-8004 registration by id; it does not mint a new authority. Same for
   C2PA manifests, TEE quotes, FPIC records. PIC mints no parallel authority anywhere
   (the doctrine-symmetry keystone, `2026-07-11_planetary_intelligence_commons.md`
   Move 1).
4. **Rebuttable, banded numbers only.** The `materialBurdenManifest` view carries the
   SIS p05/p95 band and the rebuttable label (`07_SIS_MATERIAL_LEDGER.md:64-77`); a CAR
   never surfaces a debit as a settled precise figure.
5. **Debit ≠ credit, non-fungible.** The burden node is gross carbon (what was emitted);
   the outcome node's welfare-ton is verified restoration (`W = C×E×A×B×V×P`). The CAR
   records the declared, rebuttable conversion between them — it never equates a gross
   ton emitted with a welfare-ton restored (`07_SIS_MATERIAL_LEDGER.md:90-96`).

## 5. Challenge / reversal — the state machine (node 8, the genuinely new part)

This is the one primitive the external field has nowhere (`00_FIELD_MAP.md` §1 row 5,
§2 challenge row; `research/agentic_stack.md:168`). It is IR-level state, projected from
challenge/reversal *events*, not a new authority:

```
        submit
   [ ISSUED ] ───────────────▶ a CAR exists for an action
       │
       │ challengeRecord filed (by an authorized party, on stated grounds, with evidence)
       ▼
 [ CHALLENGED ] ──── decorrelated quorum review (the throat: council/ + dpi.py) ────┐
       │                                                                            │
       │ upheld (challenge fails)                        reversed (challenge wins)  │
       ▼                                                                            ▼
   [ UPHELD ]                                                              [ REVERSED ]
       │                                                                            │
       │ (CAR stands; challenge appended, not erased)         reversalEvent emitted │
       │                                                                            ▼
       └────────────── learningRecord ◀───────────────────────────────── [ COMPOSTED ]
                       (both outcomes propagate as signal; nothing is deleted)
```

State fields (illustrative):
- `challengeRecord`: `{ challenger_authority_ref, grounds, evidence_refs[], filed_at }`
  — **who** can challenge is resolved through `communityAuthorityGrant` (node 4), so
  reversal rights are held by communities, not decreed by the layer.
- `reversalEvent`: `{ car_id, decorrelated_quorum_ref, effect, composted_at }` — the
  *effect* is explicit (credit clawback, welfare-ton retirement reversal, obligation
  re-opened), answering the field's "with what effect?" gap.
- **Nothing is destroyed.** Upheld or reversed, the original CAR and the challenge both
  persist; only the *projected state* changes and a `learningRecord` propagates. This is
  the anti-double-write law again: you append and re-project, you never overwrite truth.

Countersignature / decorrelation fields (the throat, `06_THE_CIRCLE.md:47-51`): the
`witnessedOutcome` and any `reversalEvent` carry a `decorrelated_quorum_ref` — the
outcome is minted/reversed only above an external, decorrelated quorum (the One Wire
posture), never on a single agent's say-so. This is the Transcendence Principle
(`CLAUDE.md §The Transcendence Principle`) expressed as receipt provenance.

## 6. Arc n=1 worked example (all nine nodes populated once)

The recursive first proof already specced in `07_SIS_MATERIAL_LEDGER.md:152-160` and
`06_THE_CIRCLE.md:152-160`, now expressed as a CAR — **the swarm meters its own
compute**:

| Node | Populated by, in Arc n=1 |
|---|---|
| 1 `delegationRecord` | this session's own principal / run identity (`RuntimeReceipt`, `runtime_state.py:714`) |
| 2 `intentionRecord` | the telos-gate decision that admitted the work |
| 3 `materialBurdenManifest` | SIS projector over *this repo's own* `EvidenceReceipt`s × a seed-labeled model→energy table → gross gCO₂, p05/p95 banded (`07_SIS_MATERIAL_LEDGER.md:44-52`) |
| 4 `communityAuthorityGrant` | **honestly empty / external** — no community node yet; marked `None`, not faked |
| 5 `evidenceRecord` | the `EvidenceReceipt`s themselves + their Rekor-style provenance |
| 6 `actionRecord` | the priced debit routed to one verified restoration outcome, welfare-tons |
| 7 `witnessedOutcome` | external countersignature on the restoration (decorrelated quorum) |
| 8 `challengeRecord` | empty at issue; the state machine (§5) stands ready if contested |
| 9 `learningRecord` | the result emitted back to the swarm's signal bus |

That single closed arc is the torus proven at n=1 (`06_THE_CIRCLE.md:95-99`), now the
**first full Causal Action Receipt** — nine nodes populated once, node 4 honestly `None`.
The honesty of the empty node is the point: a CAR that faked community authority would
violate the anti-theater fence.

## 7. Non-goals (explicit)

- **Not a new receipt type to persist.** If you find yourself writing a
  `car` table or a `CarReceipt` Pydantic model with its own writer, stop — that is the
  double-write trap (`RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md:165-169`).
- **Not an authority.** The CAR issues no mandates, no credentials, no credits. It
  references them.
- **Not a blockchain / token.** No native token; PIC explicitly rejects the ReFi
  speculative-token model (`00_FIELD_MAP.md` § "Adjacent visions";
  `research/footprint_and_visions.md:101`).
- **Not SAB.** Node 4's authority process lives in `shakti-saraswati/dharmic-agora`
  (DORMANT), referenced only — its constitution is not re-litigated here.
- **Not legal-grade.** Every projected number is decision-useful and rebuttable, never
  legal-grade (the OpenET posture, `07_SIS_MATERIAL_LEDGER.md:76`).

## 8. The fence (5/100)

- The CAR is a **spec of a view**, not a build. $0 revenue, no track claimed.
- Two of its nine nodes (community authority, challenge/reversal) have **no internal
  owner yet** — they are IR semantics awaiting real owners (SAB; a decorrelated
  challenge process). Naming them and not implementing them is the honest posture;
  faking them would be the lie.
- The model→energy table (node 3) is seeded from public estimates, ±~40–50%, never
  provider telemetry (`07_SIS_MATERIAL_LEDGER.md:142-149`).
- If this doc ever reads as licence to build a canonical PIC receipt store, it has failed
  its own keystone. The CAR is, and remains, an IR.
