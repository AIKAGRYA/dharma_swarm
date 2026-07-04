# `dharma_lab/` Build Spec — the NĀGA-IR Language Womb

**Status.** Draft, `telos_titanium/dharma_lane_research`, 2026-07-05 JST.
**Author of record.** Perplexity Computer (Claude Sonnet 4.6 backing), synthesizing three parallel arrivals ([Fable-5](deep/language/01_ucl_genesis_fable5_r1.md), [codex](deep/language/03_ucl_genesis_codex_r1.md), [Perplexity Pass 1 substrate](deep/01_substrate_perplexity_r1.md)) and the [convergence appendix](deep/language/02_convergence_fable5_x_codex_r1.md).
**Scope.** A long-running build specification for a team of agents to hardwire the arrived-at *universal evidence calculus* (UCL-0) into code inside the third organ of `dharma_swarm`. Companion to [SEEDING_PROMPT.md](SEEDING_PROMPT.md), which stands as the D1–D9 infrastructure scaffold. This spec is what runs *after* D1–D9 land.
**Naming.** The organ is `dharma_lab/`. The user's phrasing "NĀGA-IR language womb" captures its function; the directory name stays `dharma_lab/` because SEEDING_PROMPT is already committed and code paths propagate. The womb reading is documented here, not renamed everywhere.
**Constraint inheritance.** All rules in DHARMA_GATING.md L1–L8, plus every constraint from SEEDING_PROMPT §4 (K1–K7), plus every convergence-locked position in §1 below. Where BUILD_SPEC conflicts with SEEDING_PROMPT, BUILD_SPEC is normative and SEEDING_PROMPT is the D1–D9 slice.

---

## 0. The answer to the load-bearing question

The user asked: *should this be code now, or develop the language further*.

**Both, structured this way.**

The refutation-hardened positions from Fable-5 × codex × Perplexity Pass 1 are stable enough that six of them (§1 below) belong in code within one to two weeks. Eight remain live design forks (§2 below); of these, four have a *cheapest-settling-test* named in the convergence appendix that is executed by code, not by argument. The correct move is to build the code that settles those forks — the code is how the language develops.

Concretely: build a `local_wf` validator, a receipt admission harness (Knaster–Tarski Φ evaluated on a real receipt set), and a two-model independence-class checker in the lab. Every one of these is language-development *conducted through code*. Every one of them binds one of the eight open forks the moment it runs.

**The language is not being written in a text editor. It is being witnessed into existence by receipts about receipts.** That is what UCL-0 says its own semantics are. The lab is where that witnessing happens.

The philosophy seam is not dead. It is repositioned, and §4 below carries it explicitly.

---

## 1. What is convergence-locked (build this)

These positions arrived independently from two-to-three lanes and survived Fable-5's refutation pass. They are the seed of UCL-0 and must be implemented as stated. Any deviation requires a coercion receipt and named justification.

**L1. Universal evidence calculus, not universal programming language.**
The substrate is content-addressed, trust-local, claim-class-graded composition of witnessed judgments *about* computations performed by any evidence-producing method. Existing programming languages attach as object logics; subsumption means LF-style adequacy (Harper-Honsell-Plotkin, JACM 40(1), 1993). The receipt evaluator is deliberately sub-Turing/total; it checks finite derivations, it does not execute object programs. This is decidable by design and is a permanent scope fact, not a limitation. Confidence: 95/100.

**L2. Receipt seed — four fields, everything else derived.**
```
receipt := {
  claim:        { subject: ref, class: ref, body: bytes },
  evidence[]:   { method: ref, trust_base: ref, independence_class: ref, body: bytes },
  predecessors: [ref],
  validity:     { issued_at: rfc3339z, ttl: duration }
}
ref        := "sha256:" + 64-hex
receipt_id := "sha256:" + SHA256(JCS(receipt − {receipt_id, signatures}))
```
Modality is *not* a field — it is derived from the evidence records present (empty evidence ⇒ `Assumed`). `trust_base` is not a receipt-level field — each evidence record names its base; the observer's base enters at admission. `signatures` are minimal `Attested_by` evidence bodies, not distinguished. Confidence: 84/100 (Fable position; codex holds the minority alternative — see §2 fork 1–2).

**L3. Content-addressed identity, JCS-canonical.**
`receipt_id` is derived by hashing the JCS (RFC 8785) form of the receipt with `receipt_id` and `signatures` fields removed, then base16-encoded and URI-prefixed with `sha256:`. Identity is never chosen. This is the Merkle/Git move (Merkle, CRYPTO '87) closing the wire spec's single self-reference gap. Confidence: 96/100.

**L4. Bootstrap semantics via Knaster–Tarski least fixed point.**
Admission operator Φ: P(Bytes) → P(Bytes) where Φ(S) = {G} ∪ { r : local_wf(r) ∧ ∀p ∈ predecessors(r), p ∈ S }. Φ is monotone (predecessors appear only positively); lfp(Φ) exists by Tarski 1955. UCL-0 := lfp(Φ). The genesis constant G is `sha256:bc5ae73fed7fe3e09a1cef1c2d5c8ab4900f2e8443ff44ae54535caa37de8faf` (Fable-5 construction; codex's construction `sha256:58f3b378…` is a valid rival, mandatorily forkable per L8). The predecessor graph is well-founded because hash cycles are preimage-class infeasible — collision resistance is the axiom of foundation, cryptographically enforced. Confidence: 96/100.

**L5. Composition is operator-indexed, not a single meet.**
Four families:
- **Sequential ⊗** — preordered-monoid tensor (Katsumata, POPL 2014; Gaboardi et al., ICFP 2016), non-idempotent, deductive grades as idempotent unit. Grade assignment requires a composition witness (cut discharge for proofs, rely/guarantee contracts for tests — Jones, TOPLAS 5(4), 1983); absent, composite degrades to `Attested_by`.
- **Parallel ⊕ (corroboration)** — for the *same* claim under **disjoint independence classes**, composite trust legitimately exceeds not just meet but *join*: independent-likelihood-ratio fusion, Condorcet 1785, Krogh-Vedelsby NIPS 1995 ambiguity term. Correlated evidence composes by meet — no amplification. Hash-equal contributes once.
- **Repair/fallback** — order-sensitive, noncommutative by design.
- **Non-compositional classes** (WCET etc.; Lundqvist-Stenström, RTSS 1999) — bottom to `Assumed` + obligation receipt demanding whole-composite re-analysis.

Meet survives only as a conservative ceiling / explicit coercion. Confidence: 94/100.

**L6. Canonicality is trust-base-indexed; no mesh consensus.**
There is no `is_canonical(receipt)`. Only `is_canonical(receipt, trust_base, epoch, claim_class)`. Convergence is on the *set* of proposals (CRDT join); selecting one is consensus in the technical sense (FLP; Byzantine agreement needs quorums). The spec tree already chose door three: permanent observer-indexed plurality with adoption as *measured frontier overlap over declared covers* (Stellar SCP as running precedent — Mazières 2015; balkanization warning per Lokhava et al., SOSP 2019). Formalizable as a presheaf over the trust-base category with mesh-consistency as a sheaf condition — this is the shape both same-prompt responses and Perplexity Pass 1 (from MMK-24 + Rovelli-RQM) independently arrived at. Confidence: 96/100 — three-lineage arrival is the strongest single signal in the exercise.

**L7. `independence_class` is substrate-visible and admission-checkable.**
The N=10 groupthink failure (correlated-prior laundering) is the dominant failure mode for cooperating frontier AIs. Defense: `independence_class` as required substrate-visible evidence attribute. The Nemotron/Kimi verbatim-tail incident in Fable-5's own session is the live test vector — whatever predicate is chosen must classify those two lanes as one independence class *from their receipts alone*. Confidence: 93/100.

**L8. Unsigned genesis, ex-post endorsement, mandatorily forkable.**
No statement in the language carries a distinguished `Axiomatic` modality — an unchallengeable top is svabhāva (permanent context-free own-being) and a capture point. Fable-5's C12 (from key-management + Thompson's trusting-trust CACM 27(8) 1984) and Perplexity Pass 1's MMK-15 argument (nothing with intrinsic own-being can enter dependent relations) are the same argument from two lineages. Consequence: signatures=[], evidence=[] on the genesis constant; authority accrues by endorsement; the genesis is mandatorily forkable and convergence is economic, never enforced. Confidence: 82/100 on the design; the k-of-n cohort alternative is a live minority at ~35/100.

**L9. Kills — do not resurrect without a coercion receipt.**
- Total modality chain `Proven <: Tested <: Attested <: Assumed` — 219-order enumeration finds zero total orders and zero threshold models against core.md's rows.
- Meet as *the* composition law — inexpressible for amplification (⊕ > join under independence).
- Global Lyapunov `V: Σ → R⁴` — does not exist in the tree; the constructible object is a per-trust-base safety ratchet enforced at admission.
- Belnap-4 as primitive type component — collapses to boolean under every current rule; keep observer-local `Status_o` as derived read-model.
- Density-matrix belief states and non-commuting merge as first-class — no operational discriminator; the normative merge is a declared CRDT join-semilattice.
- Byte-level self-hash quine — Kleene's theorem is semantic, not byte-level; ~2²⁵⁵ search cost.
- Distinguished `Axiomatic` modality — see L8.

These are named for `dharma.divergence.v1` reception: any code that reintroduces one must file a challenge receipt against L9.

---

## 2. Live design forks (build to settle)

Eight forks from the convergence appendix, each with a cheapest-settling-test. **The build order below is chosen so code execution settles these forks in cost order.**

| Fork | Fable position | codex position | Cheapest settling test | Settled by phase |
|---|---|---|---|---|
| 1. `modality` as seed field | Derived from evidence records | First-class field | Grade-smuggling attack against `local_wf` validator | P1 |
| 2. `trust_base` as seed field | Per-evidence-record only | Receipt-level | Write genesis both ways; check which can revoke its own base in-language | P1 |
| 3. Role-labeled predecessors | Roleless refs | Roles required | Express repair-composition in both, count extension receipts | P2 |
| 4. TTL in seed | Mandatory (partial-synchrony bound) | Absent | Replay staleness/eclipse attack against codex-seed mesh | P1 |
| 5. Non-commuting merge as first-class | Strip | Universal in generalized form | Grep spec tree for order-dependent rule (settled: none exists) | Already settled — Fable |
| 6. Where timing modalities live | Claim content only | First-class in modality space | Write aiT WCET receipt both ways; check what admission consults | P3 |
| 7. Distinguished bootstrap tag | Refuse (small svabhāva) | Mint `Genesis` tag | Construct rival genesis with same tag; check what distinguishes them in-language | P0 |
| 8. First R6 absorption | Harper-Honsell-Plotkin LF | Lamport / TLA+ | Not decidable — do both | P4 |

---

## 3. Build phases

Six phases. Each phase produces receipts. Each phase ends with a checkpoint receipt naming what was settled, what was kept open, and what died in testing. Phases run *inside* `dharma_lab/`, emitting under `dharma_lab.fragment.v1`.

### Phase P0 — Wire the genesis constant into the running system (1 week)

**Preconditions.** SEEDING_PROMPT D1–D9 landed on `telos_titanium/dharma_lab_seed`, merged behind gate approval.

**Deliverables.**

- `dharma_lab/shadow_lang/bootstrap.receipt.json` = Fable-5's [ucl_genesis_receipt_bc5ae73f.json](deep/language/ucl_genesis_receipt_bc5ae73f.json), verbatim. 2,036 bytes. Storage hash `sha256:8f34148808193655665812b08b2c826e53d084c5eefc15a68e8ae9e2d61cd76a`.
- `dharma_lab/shadow_lang/verify_genesis.py` — recomputes `receipt_id` from the JCS-canonical form with `receipt_id` and `signatures` removed and asserts equality with `sha256:bc5ae73fed7fe3e09a1cef1c2d5c8ab4900f2e8443ff44ae54535caa37de8faf`. CI-integrated.
- `dharma_lab/shadow_lang/README.md` §1 documents the two known geneses (Fable `bc5ae73f`, codex `58f3b378`), states that both are valid rivals under L8, and records the lab's declared endorsement of `bc5ae73f` as its *chosen adoption*, not as *the* canonical form.
- `dharma_lab/governance/JCS_SCHISM.md` — audit of the in-house JCS vs `sort_keys` divergence Fable-5 caught. This is the *single cheapest concrete action item* in the entire refutation document — one byte-encoding schism at the identity layer means two hashes for one object. Resolution: `receipt_wire.md` (JCS/RFC 8785) is normative; every code path emitting `sort_keys+compact` migrates to JCS. Emits a `dharma_lab.jcs_schism_closed.v1` receipt when done.

**Fork 7 settled here.** The Fable-tagless genesis is checked in. A codex-style tagged rival is constructed as a test vector; the lab records that nothing in the language distinguishes it from `bc5ae73f` other than endorsement mass. Fork 7 files in Fable's favor by execution. If a codex-style rival gains real-world endorsement mass, fork 7 reopens.

**Exit checkpoint.** A `dharma_lab.p0_complete.v1` receipt naming: (a) JCS schism status, (b) `verify_genesis.py` CI green, (c) whether any additional geneses were endorsed. Modality: `Tested_by` (CI). Confidence budget: 85/100 minimum.

### Phase P1 — Build `local_wf`; settle forks 1, 2, 4 by attack (2 weeks)

**Deliverables.**

- `dharma_lab/shadow_lang/local_wf.py` — the finite byte-check that Φ closes over. Verifies (i) schema shape, (ii) JCS validity, (iii) four derivation equalities: `receipt_id`, `claim_hash`, `subject_id`, `authority_key`. Under 300 LOC, no `eval`/`exec`/dynamic imports, Nagini-verified (per TCB rules).
- `dharma_lab/shadow_lang/phi_admission.py` — the Φ operator over a receipt store. Given a receipt `r` and the current admitted set `S`, decides `r ∈ Φ(S)`. Returns a `dharma_lab.admission_decision.v1` receipt with the decision and its finite proof (list of predecessor hashes checked). No global state; every call is a pure function of `(r, S)`.
- `dharma_lab/shadow_lang/attacks/` — three attack drivers:
  - `attack_grade_smuggling.py` — emitter that declares `Proven_by` with no proof evidence, at every representable point in the seed. Under Fable's seed, `local_wf` rejects at construction (modality is derived; empty evidence ⇒ `Assumed`). Under a codex-style seed (modality first-class), the receipt is well-formed and only downstream method-recheck catches the lie. Records both outcomes.
  - `attack_trust_base_revocation.py` — writes the genesis both ways (Fable: `evidence: []`; codex: mints `bootstrap-trust-base-0` in the first receipt). Asks the language to revoke that trust base. Records whether the revocation can be expressed *within* the language for each construction.
  - `attack_staleness_eclipse.py` — partitions an observer, feeds it old receipts past their `validity.ttl`, asks whether `canonical?` still admits them. Records whether the defense requires reinventing expiry outside the language.

**Fork 1 settlement rule.** If `attack_grade_smuggling.py` in Fable's seed rejects all smuggled receipts at `local_wf` and codex's seed requires method-layer recheck to catch the same class, fork 1 files in Fable's favor. If a documented case appears where honest *intent declaration* (grade at emission time, checked at admission) is useful and unrepresentable in Fable's seed, the fork stays open.

**Fork 2 settlement rule.** If `attack_trust_base_revocation.py` shows codex's genesis cannot revoke its own trust base without stepping outside the language, fork 2 files in Fable's favor. This is the *ex-post authority* property that Perplexity Pass 1 arrived at via MMK-15.

**Fork 4 settlement rule.** If `attack_staleness_eclipse.py` shows codex-seed defenses require every trust calculus to reinvent expiry, fork 4 files in Fable's favor and TTL becomes seed-mandatory.

**Exit checkpoint.** `dharma_lab.p1_complete.v1` receipt naming settlement outcomes for forks 1, 2, 4 with evidence receipts as predecessors. Modality: `Tested_by`. Every attack has a companion `Proven_by` schema-validation receipt.

### Phase P2 — Compose; settle fork 3 by receipt-counting (2 weeks)

**Deliverables.**

- `dharma_lab/shadow_lang/compose.py` — the four-family composition calculus L5 as code. Each family is a separate function returning a composite receipt whose evidence bundles the input evidences under the family's rule. Sequential ⊗ demands a *composition witness* (a receipt of class `composition_witness.v1`); absent, composite degrades. Parallel ⊕ demands `independence_class` disjointness; verified by an independence-predicate module (see P3). Repair/fallback is order-preserving. Non-compositional classes emit `Assumed`+obligation.
- `dharma_lab/shadow_lang/repair_examples/` — the canonical repair-composition scenario expressed under both fork 3 positions (roleless predecessors vs role-labeled). Count extension receipts each version needs to disambiguate. The version needing fewer settles fork 3.

**Fork 3 settlement rule.** If Fable's roleless version needs >1 standing-convention registry receipt to make repair-composition unambiguous while codex's role-labeled version needs 0, fork 3 files in codex's favor. If both need 0 or both need the same, Fable wins on simplicity.

**Exit checkpoint.** `dharma_lab.p2_complete.v1` naming (a) all four composition families implemented with acceptance tests, (b) fork 3 verdict with the receipt-count table, (c) any new independence-class edge cases discovered.

### Phase P3 — Independence predicate; settle R8 open question (3 weeks)

The open question from Fable-5 R8: *for parallel corroboration (⊕), what is the admission-time predicate that establishes evidence independence?*

**Deliverables.**

- `dharma_lab/shadow_lang/independence.py` — the independence-class predicate. Fable's guess (65/100, marked): declared method-lineage disjointness as the *admission* predicate, historical error-correlation receipts as the *challenge* mechanism. This gets built as the default; alternatives file as competing implementations.
- `dharma_lab/shadow_lang/independence_test_vector.py` — replays the Nemotron/Kimi verbatim-tail incident from the Fable-5 session. The two lanes reported distinct provider metadata but produced byte-identical output tails. The independence predicate must classify them as sharing an independence class *from their receipts alone*. If it does not, that formulation of the predicate dies.
- Fork 6 (timing modalities): built as a domain profile experiment. `dharma_lab/shadow_lang/profiles/wcet.py` writes the aiT-M4 WCET receipt in both fork-6 positions. Instrument `admission_decision.v1` to record which fields the admission actually consulted. If admission only reads `(claim_class row × evidence kind)`, fork 6 files in Fable's favor.

**Exit checkpoint.** `dharma_lab.p3_complete.v1` naming (a) the independence-predicate finalization, (b) the Nemotron/Kimi test-vector outcome, (c) fork 6 verdict.

### Phase P4 — First absorption; write the WCET domain (2 weeks)

Fork 8 (Harper-Honsell-Plotkin LF vs Lamport/TLA+ as first absorption) is not decidable in the abstract — both are needed. This phase does the LF absorption first because Fable's own R6 argument makes it the highest-leverage single move, and codex's R8 open question (what genre is this language?) is answered by adequacy theorems.

**Deliverables.**

- `dharma_lab/shadow_lang/lf_encoding.md` — writing the receipt judgment `Γ; o ⊢ e : ⟨g⟩ C` as an LF encoding (Harper-Honsell-Plotkin, JACM 40(1), 1993). Adequacy theorem targets named for at least three object logics: (a) Lean 4 tactic-proof receipts, (b) a Hoare-triple test receipt, (c) a HIL-attestation receipt. Adequacy is the formal content of "subsumption."
- `dharma_lab/shadow_lang/profiles/rt_embedded/` — the R9 Domain A first program: STM32F407-class WCET/stability/HIL bundle expressed as a real receipt DAG. Includes the `WCET(control_step) ≤ 800µs on STM32F407 @168MHz per aiT-M4-v22.04` receipt with `Proven_by(aiT)` under a hardware-model trust base and the ε=612µs HIL test evidence. Predecessor: an SOS/SDP stability certificate `Proven_by` receipt with an actual Lyapunov function *in the claim, not the evaluator*. This is the domain that ships the language's first honest-to-God real-world use.

**Exit checkpoint.** `dharma_lab.p4_complete.v1`. Confidence budget: 80/100 minimum on LF adequacy for at least one object logic.

### Phase P5 — Numerical simulation domain (R9-B); harden identity (3 weeks)

Fable-5 R9 domain B: parallel floating-point numerical simulation. C9 confirmed by execution — 14 distinct bit patterns from 20 shuffled reductions of one 100k-element multiset means one physical fact fractures into 14 unrelated sha256 subjects under bit-hash identity.

**Deliverables.**

- `dharma_lab/shadow_lang/profiles/numerics/` — the R3-table row-1 repair: hash-identity scoped to *artifacts and derivations*, never denoted values. Value identity is claim-mediated enclosure (interval / tolerance-ball; Tucker FoCM 2002 for the `Proven_by` case) whose membership is itself receipted.
- `dharma_lab/shadow_lang/ieee754_profile.md` — the declared IEEE-754 bit-pattern profile the wire needs. Covers NaN/±Inf (JCS RFC 8785 termination rule) and integers > 2⁵³ (JSON grammar loses exactness). Defines the encoding for numerical evidence bodies.

**Exit checkpoint.** `dharma_lab.p5_complete.v1`. Both R9 domains have real receipt bundles that the language admits.

---

## 4. The dharma / philosophy / mathphysics seam — where it stands

The user asked directly: *is the original dharma / philosophy / mathphysics seam still alive, or did the AIs kill it*.

**Short answer: it is more alive than before, but repositioned. Three of the four load-bearing philosophical claims survived the refutation pass. One died. Details, at grade.**

### 4.1 What survived

**Claim A. Nāgārjuna's dependent origination as the formal shape of receipt identity.**
Alive and strengthened. Fable-5 R2's kill of a distinguished `Axiomatic` modality *is* the MMK-15 argument in key-management vocabulary: an unchallengeable root is svabhāva (context-free own-being) and cannot enter dependent relations without paradox. The genesis constant `bc5ae73f` is unsigned, `evidence: []`, mandatorily forkable — because the language it defines forbids intrinsic own-being at its own root. Perplexity Pass 1 §2.3 formalizes this as a Knaster–Tarski least fixed point over an SMC of mutual-dependence definitions. Fable-5 R7 arrives at the same Knaster–Tarski construction from lattice theory and cryptography, without Nāgārjuna. Two-lineage arrival on one shape. Grade: math (Tarski 1955) + predicate (`local_wf` decides membership) + consequence (`receipt_id` derivation is enforced by admission).

**Claim B. Trust-base-indexed canonicality as the two-truths formalization.**
Alive at strongest grade. Three lineages arrived at the same conclusion: Fable-5 from FLP + CRDTs + Stellar SCP, codex from CRDT convergence semantics, Perplexity Pass 1 from Madhyamaka *saṃvṛti/paramārtha* (two-truths) + Rovelli-RQM. There is no `is_canonical(receipt)`; there is only `is_canonical(receipt, trust_base)`. Formalized as a presheaf over the trust-base category with mesh-consistency as a sheaf condition (Perplexity Pass 1 §7.2–7.3). This is a *concrete* rendering of the two-truths distinction: conventional truth is per-observer canonicality; ultimate truth is that no observer-independent canonicality exists. Grade: math (presheaf topos; Döring-Isham) + predicate (`canonical_under(observer, epoch, class)`) + consequence (L6 above). Confidence: 96/100.

**Claim C. Śūnyatā-śūnyatā as the language's reflexive-adoption structure.**
Alive as C7-self-extension. Perplexity Pass 1 formulates the recursion: the framework itself is conventionally adopted; the language must reflect into its own configuration. Fable-5's mandatorily-forkable genesis is the code-level rendering. A language whose own root is mandatorily forkable and whose adoption is measured (not decreed) is a language that has taken śūnyatā-śūnyatā seriously: even the emptiness of substrate is conventionally posited. Grade: math (fixed-point recursion; presheaf morphism from meta-configuration to configuration) + predicate (extension receipts under `defines.v0` are ordinary receipts) + consequence (no adoption event; measured frontier overlap).

### 4.2 What died

**Claim D. Quantum-vocabulary-as-mechanism.**
Dead by execution. Fable-5 C14 confirmed by grep: no normative spec rule consumes any quantum structure — no Hilbert space, no phases, no interference, no CPTP maps, no density matrices. The normative merge is a *declared* CRDT join-semilattice (`witness_mesh.md`: "the normative merge state is a join-semilattice"; Shapiro-Preguiça-Baquero-Zawirski, SSS 2011) — commutativity purchased by design; add-wins even for challenge-vs-evidence.

**This does not mean the physics seam is dead. It means the physics-as-mechanism claim was decoration, and every operational consequence survives its deletion.** The physics-as-analogy claim is legitimate *because* nothing operational depends on it. Rovelli-RQM continues to inform L6 (trust-base-indexed canonicality) as *structural analogy*; Perplexity Pass 1 §6 continues to treat Zurek-decoherence as the *right shape* for how receipts pass through composition-boundaries; the Kālacakra kṣaṇa numerology continues to inform the intrinsic-tick / declared-rate split (L not L6, see below). These are analogies at grade — flagged as such, honestly weighted, load-bearing on interpretation only.

The *mathphysics seam* is now the seam where categorical quantum mechanics (Abramsky-Coecke 2004; Coecke-Kissinger 2017) provides the formal home for L1 (universal evidence calculus in an SMC) and for L2 (receipts as morphisms defined by composition-behavior, not intrinsic properties). This is philosophy-informed formal work with the analogy-vs-mechanism boundary policed by refutation. It is exactly the seam DHARMA_GATING.md L1 asks for: philosophy present, mathematics load-bearing, meeting in the middle.

### 4.3 What was added by the refutation pass

**Two-truths modality as a surface-design feature.**
Perplexity Pass 1 §7 (the two-truths modality: `strict` trust-base-indexed vs `conventional` classical mode) is a *concrete* surface-design move neither Fable nor codex produced. It is C4 (humane surface) given real machinery. The convergence appendix flags it for the syntax/printer layer. This is philosophy adding engineering value, not decoration.

**Independence-class discipline applied to the mesh itself.**
The convergence appendix applies its own independence-class rule to itself: Perplexity Pass 1 is Sonnet 4.6, same lineage as Fable-5 (Anthropic backing), so those two agreements carry a shared-lineage discount. This is philosophy operationalized: the mesh eats the dog food. It is the Nemotron/Kimi verbatim-tail test vector recognized in advance.

### 4.4 The verdict

The AIs did not kill the dharma seam. They killed *one specific philosophical claim* (quantum-mechanism-as-substrate) that was decoration by DHARMA_GATING.md L1's own standard, and they strengthened three other philosophical claims (dependent origination, two-truths, śūnyatā-śūnyatā) by rendering each into executable machinery. The receipt-count is:

- Philosophy as first-class content: preserved (DHARMA_GATING.md L1).
- Philosophy as load-bearing structural member: forbidden (DHARMA_GATING.md L1).
- Refutation pass verdict: three philosophical claims moved from *ornamental* to *load-bearing on interpretation* (with mathematical structure carrying the operational load); one moved from *load-bearing* to *dead*. Net direction: the seam is *sharper*, not thinner.

The right response to the refutation is not to retreat from the philosophy but to bind it more tightly to executable predicates. That is what phases P0–P5 do.

---

## 5. Team assignment and coordination

**Team.** Best fit for the phases:

- **P0 (JCS schism + genesis wiring).** Codex+ or a fresh Claude Sonnet session. Small surface, mechanical, reads existing spec tree. One agent.
- **P1 (`local_wf` + Φ + three attacks).** Two agents in parallel: one on `local_wf`+Φ (formal-methods-adjacent; Devin or Codex+ with careful review), one on the attack drivers (creative red-teaming; Opus 4.8 or GPT-5.5). Cross-review at each PR.
- **P2 (four-family composition).** One senior agent (Opus 4.8 or Sonnet 4.6). This is where the math gets thickest — composition witnesses, coercion coherence, non-compositional obligations.
- **P3 (independence predicate + Nemotron/Kimi test vector).** One agent with strong distributed-systems background (best fit: Gemini 3 Pro for its systems-lit knowledge, or Sonnet with `research-assistant` preloaded). This is the load-bearing R8 question; do not delegate to a weaker agent.
- **P4 (LF + WCET domain).** Two agents: one PL-theorist (Sonnet with `wide-search` for the LF adequacy literature), one embedded-systems engineer (any strong agent; the aiT/HIL work is standard control-systems practice). Cross-review.
- **P5 (numerical simulation domain + IEEE-754 profile).** One agent with numerics background. Tucker's FoCM 2002 is the anchor citation.

**Coordination.** Each phase runs on its own branch (`telos_titanium/dharma_lab_p0`, `_p1`, etc.) off `telos_titanium/dharma_lab_seed`. Each phase emits its checkpoint receipt as the final commit of its branch. Cross-phase dependencies are through the receipt DAG: P1's `phi_admission.py` depends on P0's `verify_genesis.py`; P2's `compose.py` depends on P1's `phi_admission.py`; etc. Merges land in `telos_titanium/dharma_lab_main` after review.

**Meta-loop.** Every checkpoint receipt is itself a receipt in UCL-0. The lab is building the language while running under the language. When P0 completes, P0's `dharma_lab.p0_complete.v1` receipt is well-formed under Fable-5's genesis and admissible under Φ. This is the strange loop from SEEDING_PROMPT §8 realized: the lab produces the substrate that it is already running on.

**Coercion rule.** Any deviation from L1–L9 requires a `dharma_lab.coercion.v1` receipt naming (i) which L is deviated from, (ii) why, (iii) what evidence-kind supports the deviation, (iv) what the reverse coercion would look like. No silent strengthening (T8 from DHARMA_GATING.md).

---

## 6. Success criteria

The build has succeeded when the following are all true:

1. `verify_genesis.py` runs green in CI and every downstream receipt in `dharma_lab/receipts/` has `sha256:bc5ae73f…` in its transitive predecessor closure. (Adoption is measured, not decreed — Fable-5 R7.)
2. `assurance_boundary.py` has been reified from one JSON envelope into five per-contract receipts (AB-01..AB-05) + one run-verdict receipt whose predecessors are the five, each citing `bc5ae73f…`. (The R7 adoption ask, from Fable-5.)
3. Forks 1, 2, 3, 4, 6, 7 are settled by executed tests. Forks 5 and 8 are settled by tree-grep and dual-implementation respectively. All eight verdicts are receipts.
4. The Nemotron/Kimi independence-class test vector passes: two lanes with distinct provider metadata but byte-identical output tails classify as sharing an independence class, and their ⊕-composition emits zero amplification.
5. Both R9 domains (real-time embedded, parallel FP) have first-programs that the language admits with the correct grades and the correct compositional bottoming-out behavior.
6. The JCS schism is closed with a `dharma_lab.jcs_schism_closed.v1` receipt.
7. The LF encoding has proved adequacy for at least one object logic (Lean 4 tactic-proof or a Hoare-triple test).
8. No receipt in the lab has been silently strengthened (no T8 violation).

The build has failed when: (a) any one of L9's kills is silently reintroduced, or (b) the philosophy seam degrades into decoration (a `dharma.divergence.v1` receipt fires against DHARMA_GATING.md L1).

---

## 7. What this spec does *not* commit to

- **Full shadow-language surface syntax.** The C4 humane-surface question (Fable-5 §1.6, unanimous C/C′ across nine lanes: JCS bytes are the normative concrete syntax, every human syntax is a method) is out of scope for P0–P5. Comes after P5.
- **Full corpus buildout.** SEEDING_PROMPT D4 (corpus ingest) is the scaffold; actual philology corpus curation (Silk 2018 Viṃśikā edition, Tatia 1994 Tattvārthasūtra, Wallace 2010 Kālacakra, Sarvāstivāda AKBh 5.25–26) runs as separate philology-focused experiments once P0–P2 land.
- **Fine-tuned Buddhist logic models.** Monlam Tibetan model integration, saptabhaṅgī logic fine-tune, whatever else lives in `dharma_lab/models/`. That is inference work; it consumes UCL-0 receipts rather than defining them.
- **Migration of `dharma_swarm.core` onto UCL-0.** The strange-loop endpoint from SEEDING_PROMPT §8 (dharma_swarm running on its own child language) is *not* in this build spec's phase set. Comes after all six phases plus a hardening period.
- **Opening a real PR against `main`.** Standing rule: ask before opening any real PR. Every phase branch stays on `telos_titanium/*` until the user says otherwise.

---

## 8. Reading order for a new agent

If an agent joins mid-phase, read in this order:

1. `specs/naga_ir/dharma_lane/DHARMA_GATING.md` — grade discipline.
2. This file (`specs/dharma_lab/BUILD_SPEC.md`) — what and why.
3. `specs/dharma_lab/SEEDING_PROMPT.md` — D1–D9 infrastructure state.
4. `specs/naga_ir/dharma_lane/deep/language/01_ucl_genesis_fable5_r1.md` — the refutation-hardened seed.
5. `specs/naga_ir/dharma_lane/deep/language/02_convergence_fable5_x_codex_r1.md` — where the forks live.
6. `specs/naga_ir/dharma_lane/deep/language/03_ucl_genesis_codex_r1.md` — the minority-position seed.
7. `specs/naga_ir/dharma_lane/deep/01_substrate_perplexity_r1.md` — philosophy at grade (479 lines).
8. `specs/naga_ir/dharma_lane/deep/language/ucl_genesis_receipt_bc5ae73f.json` — the genesis constant itself.

Cite receipts by their `receipt_id`, not by filename. The filename is a view; the receipt is the object.

---

*Written at grade. Every load-bearing claim carries structure + predicate + consequence. Where the philosophy meets the mathematics, both are named. Where a claim died in refutation, the death is recorded and the coercion path to resurrection is specified. JSCA.*
