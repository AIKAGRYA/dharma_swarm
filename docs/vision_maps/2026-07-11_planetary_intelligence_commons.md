# Planetary Intelligence Commons — the constitutional nervous system for agentic civilization

**Status:** VISION BRAID (the *why*). SEED-stage. $0 revenue, **no track claimed** — the
active portfolio is at WIP 10/10 (`docs/governance/ACTIVE_TRACK.yaml`), so building this
requires composting a track first (`docs/research/planetary_intelligence_commons/02_WEDGE_AND_ROADMAP.md`
§ "What it would cost to start"). This doc owns no rules, no state, and **no revenue claim.**
**Authority:** subordinate to `docs/vision_maps/NORTH_STAR.md` and
`docs/governance/SOVEREIGN_MANIFEST.md §Telos Hierarchy`. The Causal Action Receipt spec it
braids is subordinate to the binding `docs/research/RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md` ADR.
**Subordinates / braids (does not replace):** `docs/research/verified_nature_house/06_THE_CIRCLE.md`
(the torus at n=1 org), `07_SIS_MATERIAL_LEDGER.md` (the debit half), the PIC research series
`docs/research/planetary_intelligence_commons/00_FIELD_MAP.md` · `01_CAUSAL_ACTION_RECEIPT.md`
· `02_WEDGE_AND_ROADMAP.md`, and the vocabulary proposal
`docs/research/palantir-ontology/vocabulary-census/PROPOSED_PIC_VOCABULARY.md`.
**Anti-pattern guard (THE_ORGANISM needle):** if this ever reads as "a paper about our own
architecture" that no external human transacts through, it has failed. The braid earns its
keep only through Arc n=1 (below) closing on one real, externally-countersigned outcome.

---

## The question this answers

`06_THE_CIRCLE.md` closed one organism's loop into a torus: SIS debit → witness throat →
GAIA credit → Darshan/SAB propagation → back (`06_THE_CIRCLE.md:53-93`). This doc asks the
next question: **what is that torus, federated across every agent, lab, community, and
registry on the emerging agentic internet?** Not a bigger version of us — the missing layer
*above* the agentic internet that MCP, A2A, AP2, x402, and ERC-8004 are already building
(`docs/research/planetary_intelligence_commons/00_FIELD_MAP.md` §1). That stack answers *how*
agents talk, pay, and prove identity. It does not answer five constitutional questions.

## The five questions no existing protocol answers

For any action an agent takes in the world:

1. **Authority** — under whose authority does it act?
2. **Material burden** — what real burden (energy, water, minerals, downstream obligation)
   does it create?
3. **Telos** — what purpose does it serve, and was that purpose actually met?
4. **Evidence** — what independently proves the result?
5. **Challenge / reversal** — who can contest or undo it, on what grounds, with what effect?

The agentic-stack field map confirms each is only *partially* addressed and only *within a
silo*: authority is payment-scoped (AP2) or on-chain (ERC-8004); burden is expressed only for
payments; telos is self-asserted and unchecked; evidence is fragmented across C2PA / TEE /
Rekor / OTel; and reversal is network-specific and often final by design
(`00_FIELD_MAP.md` § "Gap analysis"; `research/agentic_stack.md:162-168`). The Planetary
Intelligence Commons (PIC) is the neutral layer that binds these five into one portable record
and lets communities hold the throat.

## Move 1 — The doctrine symmetry (the keystone)

This repo already has the constitutional shape of PIC, in miniature, as a **binding ADR**:
the **anti-double-write law** — read-models project truth from owners; you never mint a
parallel owner or a second receipt (`docs/research/RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md:145-151`).
SIS and GAIA obey it: they are projections over `EvidenceReceipt` and `gaia_ledger`, not new
stores (`07_SIS_MATERIAL_LEDGER.md:26-40`).

The external field map's gap analysis independently concludes with the *identical* rule for
the whole agentic internet: **"interoperate, don't duplicate"** — anchor authority on
OAuth/OIDC + DIDs, reuse AP2 mandate structure, register via ERC-8004, carry evidence via
C2PA/TEE/Rekor, emit telemetry via OTel, and add *only* the genuinely missing receipt +
challenge/reversal semantics (`research/agentic_stack.md:181`).

The internal law and the external strategy are the same law at two scales. Therefore:

> **PIC is constitutionally a projection layer at every scale.**

Internally, the **Causal Action Receipt (CAR)** is an IR / read-projection over
`EvidenceReceipt` / `RuntimeReceipt` / `VerifiedMachineReceipt` / `ClosureEvidenceReceipt` /
`Leaf` (`01_CAUSAL_ACTION_RECEIPT.md` § "Binding rules"). Externally, it is a
binding-projection over AP2 mandates, ERC-8004 registrations, C2PA manifests, TEE
attestations, MRV evidence records, and FPIC records. **PIC mints no parallel authority
anywhere.** That is *why* it can plausibly be neutral infrastructure big labs and registries
adopt: it never competes with the systems it binds. This is the ONE LAW (`NORTH_STAR.md:57-59`)
at planetary scale.

## Move 3 — Web 5, positioned honestly

The web read (Web 1) → wrote (Web 2) → owned (Web 3) → **acts** (Web 4: the agentic internet
— MCP/A2A/AP2/x402, already named in `NORTH_STAR.md §7`/§10 as "GAIA reciprocity, Web-4.0
trust"). We define **Web 5** as the web becoming capable not merely of reading, publishing,
owning, and acting, but of **coordinating and evolving under witnessed purpose, material
accountability, and reciprocal obligation.**

SAB / Dharmic Agora supplies the lawful epistemic process that makes "witnessed purpose" more
than a slogan: authority is earned, challenged, and corrected; correction ranks at least as
high as publication; volume is never sufficient for authority
(`SAB_DHARMIC_AGORA_REMOTE_HANDOFF_2026-06-11.md`, core invariants; referenced only — that
constitution lives in `shakti-saraswati/dharmic-agora`, not here).

**Honesty fence on the term:** "Web5" as a field term is contested — the best-known prior
claimant (Jack Dorsey's TBD project) is effectively dead. This is *our* definition, seed-labeled;
we do not claim field consensus. Say it once and move on.

## Move 4 — The organ braid: five questions, one per organ

Each constitutional question maps to an existing organ. **This is a braid over mostly-seed
organs, and the honest status is the point** (anti-theater). Statuses trace to
`NORTH_STAR.md §7` and `docs/governance/SOVEREIGN_MANIFEST.md §Telos Hierarchy`.

| Question | Organ | Status (cited) |
|---|---|---|
| **Authority** | SAB / Dharmic Agora (witnessed authority + challenge/correction) | **DORMANT**, lives in `shakti-saraswati/dharmic-agora` (`repo_canon_brief.md` (a); `NORTH_STAR.md:113-117`) |
| **Material burden** | SIS ("Silicon Is Sand") — full material cost of compute | **SEED 5/100**, spec only, $0 revenue (`07_SIS_MATERIAL_LEDGER.md:3-7`) |
| **Telos** | telos gates / Dharma Swarm substrate | **ACTIVE** substrate (`CLAUDE.md §Key Abstractions`; live battery in `dharma_swarm/telos_gates.py`) |
| **Evidence** | Runtime Truth Spine + witness membrane | **ACTIVE** (`EvidenceReceipt`, `06_THE_CIRCLE.md:47-51`) |
| **Capital / outcome** | GAIA — welfare-ton restoration loop | **ENVISIONED** (`06_THE_CIRCLE.md:70-78`; `07_SIS_MATERIAL_LEDGER.md:80-96`) |
| **Immune detection** (harms/gaps) | Loomwork — planetary immune system | **DESIGN_ONLY** (`NORTH_STAR.md §7`; `06_THE_CIRCLE.md:33-37`) |
| **Propagation** | Darshan (noosphere), with SAB as basin | **ACTIVE_SEASON_0** (`NORTH_STAR.md:110-120`) |

**The Circle (`06_THE_CIRCLE.md` torus) is PIC at n=1 org; PIC is the Circle federated.** The
throat — the witness / verification membrane — is the same in both: decorrelated multi-agent
aggregation + tamper-evident provenance + welfare-ton unit + telos gate
(`06_THE_CIRCLE.md:47-51`). Federation changes only *who holds the throat*: from one org's
membrane to a federated layer holding **only** identity, interoperability, constitutional
invariants, challenge rights, and receipt schemas — while local, bioregional communities
retain custody, define legitimate benefit, and can veto or revoke
(`02_WEDGE_AND_ROADMAP.md` § "Federated and bioregional").

## Move 5 — "Legitimacy + teeth" is the unoccupied quadrant

The footprint research maps the governance terrain into a quadrant nobody holds
(`footprint_and_visions.md:143-148`): Anthropic's Collective Constitutional AI and vTaiwan
have **legitimacy without teeth** (deliberation that doesn't bind — vTaiwan "stalled" precisely
because consultation wasn't binding, `footprint_and_visions.md:128`); the per-MW data-center
fee bills (UW-Milwaukee, Illinois POWER Act, Virginia) have **teeth without legitimacy**
(coercive, no deliberative process, `footprint_and_visions.md:48-52`); ReFi had **neither at
scale** (`footprint_and_visions.md:92-101`).

PIC's bid for the empty quadrant: SAB-grade witnessed deliberation (legitimacy) binding SIS
debits and GAIA outcome-gated release (teeth). The instrument sits deliberately **between
coercion and charity** — a voluntary-but-verifiable reciprocity instrument that restores
social license. The demand signal is already on the record: ~75 data-center projects (~$130bn)
blocked or delayed in Q1 2026 amid local opposition, with siting now an electoral issue
(`footprint_and_visions.md:18`, `:148`).

## The one move that turns the braid real (Arc n=1)

Following the ONE LAW (each doc names the real gated outcome its loop closes through), the
whole braid closes through **Arc n=1**, the recursive move already specced in
`07_SIS_MATERIAL_LEDGER.md:152-160`:

> The swarm meters its own compute — a SIS projector over *this repo's own* `EvidenceReceipt`s
> (zero new stores; one new projector + one seed-labeled model→energy table), prices the debit
> in welfare-tons, routes it to one verified restoration outcome, obtains an external
> countersignature, and emits the result as the **first full Causal Action Receipt** — all
> nine nodes populated once (`01_CAUSAL_ACTION_RECEIPT.md` § "Arc n=1 worked example").

That single closed arc is the torus proven at n=1, now expressed as a CAR rather than a bare
welfare-ton. Everything above is the reason that arc is worth closing. The commercial wedge
(verifiable compute offsets) and the world-scale domain (a nature-restoration outcome graph)
follow it, strictly ordered, in `02_WEDGE_AND_ROADMAP.md`.

## What this vision does NOT license (the fence)

- **The throat is earned, not decreed.** "Everything must pass through us" is a
  chokepoint-by-fiat fantasy. Throats (Visa, SWIFT, ICANN, Palantir) are earned over decades
  via adoption + standards capture + network effects (`06_THE_CIRCLE.md:141-144`). PIC becomes
  the throat only by being the most-trusted node — one verified CAR at a time — and lets the
  "must" emerge. Leading with the monopoly claim is the founder delusion the field's failures
  (`00_FIELD_MAP.md` § "Adjacent visions") should inoculate against.
- **The metaphysics are the why, not the product.** R_V, strange loops, the torus cosmology
  are load-bearing for coherence and the "safety = intelligence" claim, **inert** as a sales
  object (`06_THE_CIRCLE.md:145-148`). Sell the verified receipt; let the constitution be the
  reason it is trustworthy.
- **No parallel owner, ever.** CAR is an IR/projection. It creates no new receipt store, mints
  no parallel authority, and re-litigates none of the anti-double-write ADR
  (`RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md:145-151`). If a future build ever adds a "canonical
  PIC receipt store," it has violated the keystone (Move 1).
- **Welfare-tons stay non-fungible.** The material-burden debit is gross carbon (what was
  emitted); the credit is a welfare-ton (verified restoration with co-benefits,
  `W = C×E×A×B×V×P`, `07_SIS_MATERIAL_LEDGER.md:90-96`). The membrane reconciles them with a
  declared, rebuttable conversion — it never pretends a gross ton emitted equals a welfare-ton
  restored. Debit and credit are deliberately different units.
- **SEED 5/100 stands.** This is a braid, not a build. $0 revenue. No track claimed. The
  welfare-ton and the CAR are our constructs, not the field's consensus.
