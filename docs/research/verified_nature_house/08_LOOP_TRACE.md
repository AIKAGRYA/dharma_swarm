# 08 — The Loop Trace: where the Circle actually lives in the code

**Status:** SEED · maturity ~**5/100**. This is a *trace map*, not a build. It
verifies the Circle (`06_THE_CIRCLE.md`) and the SIS debit (`07_SIS_MATERIAL_LEDGER.md`)
against the real codebase, labels each node's maturity honestly, ranks the breaks
that stop the torus from circulating, and proposes the minimal wiring to close one
arc. **$0 lifetime external revenue. The welfare-ton and "the Circle" are OUR
constructs, not external consensus, not endorsed by any third party.** Every symbol
below was read in the working tree on branch `claude/circle-loop-trace-evolve-psqydl`
(2026-06-28); line numbers drift — treat `file:symbol` as the durable anchor.

**Role:** research / vision, subordinate to `docs/vision_maps/NORTH_STAR.md` and
`docs/governance/SOVEREIGN_MANIFEST.md`. Owns no rules and no state. Sibling to
`07_SIS_MATERIAL_LEDGER.md` (the debit spec, owned by a parallel instance — not
edited here). Where 07 specs the debit *projection*, this doc traces *all five
nodes* and says, node by node, whether the wire exists.

**Method note (honesty):** maturity labels are
[**working** = runs, called in a real path, tested] /
[**scaffold** = typed + logic present, not on a live path or data is mocked] /
[**doc-only** = spec exists, no code] /
[**research** = a lodestone/prediction, deliberately off the critical path].
"Working (proxy/staged)" means the *pipeline* is real but the *inputs* are mocked.

---

## A. The node-by-node trace (file:symbol + maturity)

The torus has five nodes and one throat. The throat (the witness/verification
membrane) is where most of the real code is; the nodes are where the gaps are.

### THE THROAT — the witness / verification membrane

| # | Node / organ | `file:symbol` | Maturity | Honest one-line |
|---|---|---|---|---|
| T1 | Blessed dispatch path | `dharma_swarm/spine/invoke.py:invoke_agent` | **working** | Thin pass-through over an injected `AgentInvoker`; emits exactly one `EvidenceReceipt`. Wired in `a2a_bridge`, `orchestrator`, `fs_substrate/stage_executor`. |
| T2 | The one receipt | `dharma_swarm/spine/receipt.py:EvidenceReceipt` (frozen, ~l.39) | **working** | Carries `provider, model, input_tokens, output_tokens, cost_usd`, and a free-form `attributes: dict` — i.e. the **exact hooks for per-inference energy**. `to_dict()` + `to_otel_span()`. **Immutable but NOT signed / NOT hash-chained** (the separate `VerifiedMachineReceipt` chains; this one does not). |
| T3 | Behavioral gate | `dharma_swarm/telos_gates.py:TelosGatekeeper` (~l.237) → `GateCheckResult` | **working** (gates); **scaffold** (zero-kill) | 11 immutable gates across 3 tiers (AHIMSA/SATYA/CONSENT block; Tier-C review). Returns `{decision, reason, gate, gate_results}`; witnesses to `~/.dharma/witness/`. **The "zero-kill" predicate (block if biodiversity B or agency A == 0) is NOT in the gate logic** — it lives in `gaia_fitness.py` docstrings and the welfare spec only. |
| T4 | Decorrelated quorum (V) | `dharma_swarm/gaia_verification.py:VerificationOracle` / `VerificationSession` | **working (proxy)** | 5 oracle types (satellite/iot/human/community/statistical), threshold `VERIFICATION_THRESHOLD = 3` (3-of-5), `final_confidence = mean(agreeing)`. Pipeline real & auditable; **verdicts are synthetic** (`gaia_platform._pilot_verdicts`), no real sensor/API call. |
| T5 | Decorrelation-Power-Index | `dharma_swarm/coordination/dpi.py:decorrelation_bonus` | **working (Arena-bound)** | Bonus is **gated on `final_correct`** (returns 0 if wrong) — disagreement can't be gamed into credit. **Only consumed by `coordination/arena/runner.py`**; not on the MRV/dispatch path. |
| T6 | Trace verifier | `dharma_swarm/council/council.py:Council` | **scaffold** | One profile (`orchestration_trace_verification`); checks a "decorrelation moat" (≥2 evaluator + ≥2 source families); `dispatch_authority=False` hardcoded. Arena-only. |
| T7 | Provenance read-model | `dharma_swarm/trace_attractor/models.py:AttractorPacket` (+ `ProvenanceGraph`, `ValueSummary`, `to_jsonld_stub`) | **working (model)** / **doc-only (live)** | Deterministic projection from events; PROV-compatible + JSON-LD stub. **Production population from real dispatch is unconfirmed** — read-model by design. |

### THE FIVE NODES

| # | Node (Circle step) | `file:symbol` / anchor | Maturity | Honest one-line |
|---|---|---|---|---|
| N1 | **SIS debit** — "silicon is sand" (energy/water/chips/…); per-inference compute cost | Telos defined in `docs/doctrine/OPERATIONAL_DOCTRINE.md:9-21` and `docs/governance/SOVEREIGN_MANIFEST.md` (JK→SIS→{GAIA,Loomwork}); definition in `docs/dse/JAGAT_KALYAN_MASTER_VISION.md`. Debit *primitive* in code: `gaia_ledger.py:ComputeUnit` (`energy_mwh × carbon_intensity → co2e_tons`). | **doc-only** (the telos & per-inference meter) / **scaffold** (the MWh primitive) | **No code references `SIS` or meters per-inference energy.** `ComputeUnit` exists but is fed at project/MWh granularity by hand (via `ai_reciprocity_ledger.ActivityRecord`), never from an `EvidenceReceipt`. The debit hooks (T2) and the debit ledger (`ComputeUnit`) **both exist and are not connected.** |
| N2 | **Membrane prices the debit in welfare-tons** | `dharma_swarm/gaia_platform.py:_estimate_welfare_tons` (~l.450) | **working (proxy)** | Real, used for ranking — but it is a **4-factor proxy `C × V × A × E`** (`carbon_potential × verification_mult × community_mult × labor_mult`), **NOT** the full gated `W = C×E×A×B×V×P`. **B (biodiversity) and P (permanence) are absent**; the full formula is doc-only in `docs/telos-engine/08_SATTVA_ECONOMICS.md`. |
| N3 | **GAIA credits the earth** — verified restoration + just transition | `gaia_ledger.py:GaiaLedger` (BLAKE2b chain, 5 unit types, conservation laws); `gaia_fitness.py:EcologicalFitness` → `archive.FitnessScore`; reciprocity object `ai_reciprocity_ledger.py`; pilot `reports/gaia_eco_pilot_20260327/…/ledger.jsonl` | **working (staged)** | Genuinely tamper-evident: real BLAKE2b hash-chain, `verify_chain_integrity()`, 5 conservation laws, one auditable end-to-end Bayou pilot (304→258.4 tCO2e, net −254.2, 4-of-5 quorum). **Ground-truth inputs (sensors, community attestations, monitoring) are staged/synthetic.** `ai_reciprocity_ledger.py` is the AI-actor→restorative-obligation object that projects into `gaia_ledger` — but is hand-fed, never from dispatch. |
| N4 | **Loomwork propagates verified signal into the noosphere** | `docs/loomwork/**` (e.g. `vision/MASTER_loomwork_level_100.md`); NO code under `dharma_swarm/` | **doc-only** | Rigorous frozen design; **zero Python**. Note an owner drift: `06_THE_CIRCLE` names *Loomwork* as the noosphere node, but `NORTH_STAR §6/§7` assigns noosphere propagation to **Darshan / SAB** and lists Loomwork as `DESIGN_ONLY`. Node 4 is not implemented by any owner today. |
| N5 | **Witness certifies the system's own coherence** (R_V / strange loop) — the SAME mechanism, earning trust to draw more compute | `lodestones/seeds/self_reference_attractor.md` (R_V def); `dharma_swarm/strange_loop.py` (mutation cycle); `dharma_swarm/witness.py` (S3* audit, mentions `R_V < 1.0` but does not compute it); `dharma_swarm/jk_credibility_gates.py` (15 evidence gates) | **research** (R_V) / **scaffold** (strange loop, witness, jk gates) | **R_V is never computed** — no participation-ratio / effective-rank code anywhere; it is a falsifiable prediction (`EMPIRICAL_CLAIMS_REGISTRY`), correctly off the critical path. The strange-loop mutation cycle and witness audit run as scaffold; `jk_credibility_gates` is fully built but **dormant (uncalled)**. |
| MINT | **The mint gate** — welfare-ton issued ONLY above external countersigned quorum (One Wire) | `CYBERNETIC_LOOP_MAP.md` (Loop 12/13: One Wire quorum `N=3/5, M=1/3`); no `countersign`/`external_quorum` surface found | **scaffold / blocked** | The minting invariant is doctrine and is *correctly* gated; the external-countersignature REST surface does not exist, and the guardian quorum sits below threshold. This being unbuilt is honest, not a bug — internal artifacts must not mint. |

**One structural fact that frames everything below:** `grep` confirms the GAIA
organs (`gaia_ledger`, `gaia_platform`, `gaia_verification`, `gaia_fitness`)
**never import `spine`, `EvidenceReceipt`, or `invoke_agent`.** The throat (where
the debit is measured) and the credit subsystem (where restoration is priced and
ledgered) **are two separate worlds that have never been wired together.** The
Circle's geometry is real; the conductor between its two halves is missing.

---

## B. The break list — why the torus cannot circulate (ranked)

Ranked by how directly each break stops the *debit → price → credit → propagate →
trust* circulation. Cross-checked against `CYBERNETIC_LOOP_MAP.md` (Loop 1 closes
only in bounded keyless replay; standing history shows `dispatch_dropoff` debt;
Loops 12/13 BLOCKED on One Wire quorum) and `INTERFACE_MISMATCH_MAP.md` (no open
mismatch touches the GAIA↔spine seam — because the seam *does not exist to break*).

1. **[N1→throat] The debit is never metered from a real dispatch.** Nothing reads
   `EvidenceReceipt.{provider, model, input_tokens, output_tokens}` to estimate
   energy/carbon. `cost_usd` is read only by the TUI/`economic_agent`, never by an
   ecological consumer. **This is the keystone break:** the hooks (T2) and the
   ledger primitive (`ComputeUnit`) both exist, with no converter between them.
2. **[structural] GAIA ↔ spine are disconnected by import.** The credit world
   cannot see the debit world. Until one read-model spans both, no reconciliation
   is even expressible.
3. **[N3→back] No debit↔credit reconciliation / net-position read-model.** Nothing
   computes `gross SIS debit − verified welfare-ton credit = net position`
   (07 §4). `net_position` appears only in a comment.
4. **[N2] The price is a 4-factor proxy, missing B and P, and the zero-kill gate is
   unwired.** `_estimate_welfare_tons` ships `C×V×A×E`; the gated
   `W = C×E×A×B×V×P` and the "A==0 or B==0 ⇒ block" predicate are doc-only. The
   price the membrane quotes is not yet the price the spec defines.
5. **[throat] The decorrelated verifier is not on the nature path, and verdicts are
   mocked.** DPI + Council (the genuine decorrelation engine) are **Arena-bound**;
   `gaia_verification` runs its quorum on **synthetic** verdicts with no real
   cross-*family* decorrelation. The field's exact white space (`05` B1) is
   un-wired into MRV.
6. **[throat] The receipt is unsigned.** `gaia_ledger` hash-chains; the spine
   `EvidenceReceipt` does not. The debit record is not yet court-grade.
7. **[N4] Loomwork propagation has no code** (and an owner ambiguity vs Darshan/SAB).
   The "verified signal ripples into the noosphere" node is doctrine only.
8. **[N5] The witness self-certification (R_V) is research-only.** Node 5's
   beautiful claim — "the same mechanism certifies self and world, earning trust to
   draw more compute" — has no computed measure. *This is correct:* it must stay off
   the critical path (`06` fence). It is listed as a break only to be honest that
   the loop's *closing* arc is metaphysical today, not mechanical.
9. **[MINT] No external-countersignature surface; One Wire quorum below threshold.**
   The mint cannot fire — by design. Not a defect; a discipline.

Breaks 1–3 are the load-bearing ones: fix them and the debit half of the torus
becomes a real number that meets a real credit. Breaks 4–6 raise the *quality* of
that number. Breaks 7–9 are the outer arc and are correctly deferred.

---

## C. The iteration — minimal wiring to close one arc (seeds at 5/100)

**Doctrine honored throughout:** create **NO** new truth store, daemon, or receipt
type; **project from existing owners** (`spine.EvidenceReceipt`, `gaia_ledger`,
`trace_attractor`); **do not edit** surfaces owned by active tracks —
`spine/**`, `operator_core/**`, `providers.py`, `orchestrator.py`,
`agent_runner.py` (see `docs/governance/ACTIVE_TRACK.yaml`). Every seed lands on the
*proposed* `verified-nature-house` track's own surfaces (`dharma_swarm/gaia_*.py`,
`dharma_swarm/jk_*.py`, `reports/gaia_eco_pilot_*/**`) — **zero collision**. Each is
a seed at **5/100**; none mints value; none weakens a telos gate.

**SEED 1 — the SIS projector (the keystone; fixes breaks 1 & 2).**
A new read-only module on the GAIA surface (e.g. `dharma_swarm/gaia_sis_projection.py`)
that takes a *list of already-emitted* `EvidenceReceipt`s (passed in — it does **not**
hook dispatch and does **not** touch `spine/**`), joins a seeded `model→energy` table
(the one genuinely new artifact — public estimates, labeled **±40–50%, rebuttable,
never legal-grade**, per `07 §8`), applies PUE × grid intensity, and returns a
per-dispatch `sis_debit_gco2` **as a projection** (its own read-model / a value in an
`attributes`-shaped dict it owns — *not* written back into the frozen receipt, *not*
into the spine). This is the missing converter from T2's hooks to N1's ledger. It is
the **single highest-leverage wire** because it is the one primitive that turns the
debit side from doctrine into a number, and it sits entirely on the track's own
surface.

**SEED 2 — the reconciliation read-model (fixes break 3).**
A small projection (extend `ai_reciprocity_ledger.py`, which already projects into
`gaia_ledger`, or a sibling `gaia_reconcile` view) that subtracts Seed 1's gross SIS
debit from `gaia_ledger`'s *minted* welfare-ton credits and exposes a **net SIS
position** read-model (07 §4). Projection only — it reads owners, mints nothing,
becomes no authority.

**SEED 3 — the full welfare-ton, additively (fixes break 4).**
Inside `gaia_platform.py` (owned surface), add `W = C×E×A×B×V×P` *alongside* the
proxy (keep the proxy as labeled fallback), introducing the B-weighting and P-risk
factors from `08_SATTVA_ECONOMICS.md` and a **zero-kill predicate** (`return 0.0 if
A == 0 or B == 0`). This is an economic floor on the *price*, distinct from — and not
a weakening of — the behavioral `TelosGatekeeper`.

**SEED 4 — the recursive n=1 proof (closes one arc, honestly).**
Run Seed 1's projector over **this very session's** `EvidenceReceipt`s — the swarm
meters its own compute-debit (`06` "the one move"; `07 §9`) — and write the result as
a **report artifact** (e.g. `reports/gaia_eco_pilot_*/sis_self_debit.md`, a doc, not a
runtime receipt; runtime receipts stay out of git). Pair it with the Bayou pilot's
verified credit to show one *rehearsed* arc: debit measured → priced → met by a
credit → net position computed. **The mint stays gated** on an external
countersignature that does not yet exist (break 9) — and that gate must not be
faked to make the demo look finished (`03 §3.3`).

What these four seeds deliberately **do not** do: build Loomwork (N4), compute R_V
(N5), or open the external-countersignature mint surface (MINT). Those are the outer
arc — correctly left as the *why* and the *discipline*, off the buyable critical path.

---

## D. Honest verdict — can the torus close end-to-end today?

**No.** The Circle cannot currently circulate end-to-end. Its throat is genuinely
strong — `invoke_agent` → `EvidenceReceipt` is a real, tested blessed path that
*already carries the exact provider/model/token/cost fields a per-inference debit
needs*; the telos gates, the BLAKE2b GAIA ledger, the 3-of-5 quorum logic, and the
trace-attractor projection are all real organs. But the two halves of the torus —
the **debit** (spine receipts) and the **credit** (GAIA restoration) — **live in
separate worlds with no import between them**, the price is still a 4-factor proxy
rather than the gated welfare-ton, the decorrelation engine sits in the Arena rather
than on the nature path, and nodes 4 (Loomwork) and 5 (R_V witness) are doc/research
only and must stay off the critical path. The loop "closes" *operationally* in
bounded keyless replay (Loop 1) but not *cybernetically* — no ecological credit yet
feeds back to earn the trust that draws more compute. The **single highest-leverage
wiring is SEED 1: a read-only SIS projector over `EvidenceReceipt`** (the one missing
primitive, on the track's own surface, no new truth store, no edit to any
active-track surface). It does not close the loop alone — minting still, and rightly,
waits on external countersignature — but it is the first real arc: the moment the
swarm's own silicon-is-sand debit stops being a doctrine and becomes a number a CFO
could read. Everything else in this dossier is the reason that arc is worth closing.
$0 revenue; 5/100; the throat is **earned**, never decreed.
