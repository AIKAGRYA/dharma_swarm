# Pass 1: Paramāṇu-Scale Substrate

Author: Codex  
Status: research contribution, not normative spec  
Target: NĀGA-IR dharma lane substrate ontology  

## Executive Decision

The substrate should not be an ontology of ultimate receipt-atoms. It should be an ontology of observer-indexed receipt-events whose apparent stability is selected by mesh interaction. [Architectural confidence: 88/100]

Formal structure: the base object is not `Receipt` but `Fact[o]`, a fact relative to an observer/trust-base profile `o`. A receipt payload becomes a NĀGA entity only through an admission morphism:

```text
admit_o : Bytes -> Maybe[Fact[o]]
Fact[o] =
  (receipt_id, authority_key, claim_hash, modality_basis,
   payload_hash, order_marker, ttl, signature_set, challenge_base)

canonical_o?(r, t) =
  canonical?(r, mesh_state_o, current_o, t)
```

This preserves the current NĀGA design in [core.md](../../core.md), [receipt_wire.md](../../receipt_wire.md), and [witness_mesh.md](../../witness_mesh.md): canonicality is a predicate over `(receipt, mesh_state, current, t)`, not an intrinsic bit on the receipt. It also converges with Rovelli's relational quantum mechanics: the rejected primitive is an observer-independent state or value; the retained primitive is a relative event/fact. Rovelli states the RQM target explicitly in the 1996 paper: the suspect notion is the "observer-independent state of a system"; all systems are equivalent and the theory describes information systems have about each other ([Rovelli 1996](https://arxiv.org/abs/quant-ph/9609002)). The 2021 formulation sharpens this to sparse relative facts realized in interactions, with approximate stability when decoherence hides interference ([Rovelli 2021](https://arxiv.org/abs/2109.09170)). [Architectural confidence: 90/100]

Operational predicate: no API should expose `receipt.canonical` as stored ground truth. The only admissible interface is `canonical?(receipt, mesh, current, t)` or an indexed cache explicitly marked non-authoritative. This is already present in the NĀGA wire and mesh drafts. A static check should fail any code path that treats cached `challenge_state`, `canonical`, `verified`, or `trusted` fields as authority without re-querying the challenge base and current trust profile. [Architectural confidence: 94/100]

Language consequence: the smallest entity the language can talk about is an observed receipt-event, not a receipt-substance. The calculus should type receipts under a perspective:

```text
Γ ; o ⊢ r : ReceiptFact[authority_key, modality, horizon]
Γ ; o ; t ⊢ canonical(r) : Prop
```

There is no unindexed judgment `Γ ⊢ canonical(r)`. This is the substrate choice on which Pass 2 logic and Pass 3 dynamics should build. [Architectural confidence: 91/100]

## Source-Honesty Notes

I am working from primary engagement for Nāgārjuna's `Mūlamadhyamakakārikā` at the level of MMK 1.1, 24.8-10, and 24.18-19, with Siderits-Katsura/Garfield/Westerhoff as scholarly controls. I am working from secondary and translation memory for Vasubandhu's `Viṃśatikā`, especially the atomism argument traditionally located in the middle verses and autocommentary. I cite it as `Viṃśatikā` vv. 11-15 with low confidence on exact verse segmentation. [Shallow citation confidence: 62/100]

For Jain physics I am working from secondary literature and standard `Tattvārthasūtra` chapter-5 anchors: pudgala has touch, taste, smell, and color; paramāṇus combine into skandhas; binding is explained through quality-differences such as snigdha/rūkṣa in later exegesis. I have not verified the Sanskrit sutra numbering during this pass, so detailed numbering below is marked shallow. The stable secondary anchor is Jaini's presentation of pudgala as paramāṇu/skandha with color/taste/smell/touch qualities; a web-accessible summary gives the same four-quality account with Jaini as source ([Pudgala summary](https://en.wikipedia.org/wiki/Pudgala)). [Shallow citation confidence: 60/100]

For Kālacakra I am working from secondary literature, primarily Newman/Wallace-level summaries, not from the root tantra or `Vimalaprabhā`. Claims about five colored winds and kṣaṇa-cosmology are therefore architectural inspiration only, not a load-bearing primary-text argument. [Shallow citation confidence: 55/100]

## The Atomism Decision

The substrate question is malformed if "smallest thing" means an intrinsically existent particle. It is well-formed if it asks for the smallest operational cutpoint in the language. The answer is: the smallest operational cutpoint is a perspective-indexed receipt-event admitted by a node under a trust profile. [Architectural confidence: 89/100]

Formal structure: use an indexed category or fibration over perspectives. Let `O` be the category of observer/trust-base contexts. For each `o ∈ O`, there is a local category `C_o` of admitted facts and admissible transformations. Reindexing along a trust refinement `f : o -> o'` is a functor:

```text
f* : C_o -> C_o'
```

but it is partial or fail-closed unless a checked refinement receipt exists. This is exactly the current NĀGA trust-base rule: transfer requires exact trust-base match or a `Proven_by` refinement receipt. [Architectural confidence: 86/100]

Computable predicate: `transferable?(fact_o, o')` returns true only if `authority_matches` under `o'` or a refinement receipt proves preservation of obligations. The predicate is falsified by any implementation that lets a receipt canonical under `trust_base_A` become canonical under `trust_base_B` by copying its hash alone. [Architectural confidence: 93/100]

Philosophical convergence: Vasubandhu's atomism critique matters here only as a no-svabhāva warning against treating a receipt as a featureless bearer of authority. The familiar argument is that a partless atom cannot explain extended appearance; if it has spatially distinct contacts or directions, it has parts and is not ultimate. In `Viṃśatikā` vv. 11-15 and autocommentary, this underwrites the rejection of external atomism in favor of `vijñaptimātra`; the first verse of the text states the representation-only thesis through the example of unreal appearances such as hairs seen by a diseased eye, and later argument attacks atomistic external objects. The web-accessible Yogācāra survey notes that Vasubandhu's `Viṃśatikā` attacks Indian atomism on mereological grounds ([Yogācāra survey](https://en.wikipedia.org/wiki/Yogachara)). [Textual confidence: 62/100, marked shallow]

Language consequence: bytes are not nothing, but they are not yet receipts in the semantic sense. A file containing JSON is like an unmeasured quantum state only in this restricted formal sense: it has not entered the indexed judgment relation. `admit_o` is the ingest-node projection. A payload that no node can parse, validate, sign-check, and index under a trust profile is not a NĀGA receipt; it is inert data. This is not Yogācāra idealism about the filesystem. It is a typed semantics claim about when authority exists in the language. [Architectural confidence: 84/100]

Bootstrap without atoms is handled by guarded fixed point, not by positing an ontic genesis particle:

```text
MeshState_o = ORMap[AuthorityKey, EventSet]
Φ_o(S) = validate_genesis_o(G_o)
       ∪ admit_new_events_o(S)
       ∪ derive_expirations_o(S, t)
S*_o = lfp(Φ_o)
```

The least fixed point is computed over a join-semilattice of content-addressed events, as already sketched in [witness_mesh.md](../../witness_mesh.md). The genesis event is conventional: it is a signed initial condition inside `o`, not a metaphysical atom. This is a Nāgārjuna-compatible bootstrap: dependence is mutual and fixed-point-like, but the mathematics stands on monotone fixed points over a semilattice, not on a philosophical analogy. [Architectural confidence: 87/100]

## Intrinsic Qualities Without Svabhāva

The Jain paramāṇu direction is useful if stripped of metaphysical intrinsicness and retained as a quality algebra. In Jain analysis, pudgala is characterized by color (`varṇa`), taste (`rasa`), smell (`gandha`), and touch (`sparśa`), and paramāṇus aggregate into skandhas. Standard summaries attribute this to `Tattvārthasūtra` chapter 5 and Jaini's account of Jain matter ([Pudgala summary](https://en.wikipedia.org/wiki/Pudgala)). I cannot verify the exact sutra numbers here; treat the Jain-primary mapping as shallow. [Textual confidence: 60/100, marked shallow]

Formal structure: define a receipt-quality algebra:

```text
Q = Q_adhesion × Q_chroma × Q_decay × Q_provenance
q : Fact[o] -> Q
composeable?(a, b, mode) =
  compatibility_mode(q(a), q(b)) ∧ authority_refines(a, b)
```

The quality vector is not payload data. It is the part of the receipt that composition rules inspect before they are allowed to build a larger claim, aggregate, proof packet, or authority transfer. [Architectural confidence: 86/100]

The proposed quality types are:

| Jain analog | NĀGA quality | Computable predicate | Consequence |
|---|---|---|---|
| `sparśa` / touch | adhesion profile | `authority_refines`, `trust_base_match`, `fragment_compatible` | Controls whether receipts can bind into proof packets. |
| `varṇa` / color | modality-basis tag | `basis(receipt.evidence) ∈ {Proven_by, Tested_by, Witnessed_by, Attested_by, Challenged_by}` | Lower than `ClaimClass`; determines admissibility transitions. |
| `rasa` / taste | decay/freshness profile | `ttl_live`, `clock_within_skew`, `evidence_horizon_contains(t)` | Controls whether old facts can nourish current canonicality. |
| `gandha` / smell | provenance gradient | `causal_origin` and `epistemic_origin` signatures verify and remain distinct | Prevents causal production from masquerading as proof. |

This is not decorative if these qualities affect composition. It becomes decorative if `ClaimClass` and `Evidence.modality` already decide everything. In current NĀGA, they do not: trust-base compatibility, TTL, clock uncertainty, challenge base, and origin split are all separately load-bearing. Therefore a Jain-style quality vector is justified as a primitive profile inspected by the composition engine. [Architectural confidence: 82/100]

`varṇa` should not equal `ClaimClass`. `ClaimClass` says what proposition domain is under review: safety, provenance, contract, runtime observation. `varṇa` says what evidence-basis the receipt occupies. A safety claim may have noncanonical `Tested_by` support and canonical `Proven_by` support; those are distinct colors under the same claim class. [Architectural confidence: 88/100]

The snigdha/rūkṣa analogy should map to adhesion polarity, not spatial contact. A receipt with exact trust-base match is "adhesive" for canonical aggregation; a receipt with a trust-base mismatch is "dry" or non-binding unless a refinement morphism supplies adhesion. The computable predicate is already `authority_matches`. [Architectural confidence: 79/100; textual source shallow]

## Tri-Temporal Existence and Present Authority

The language should combine Sarvāstivāda event persistence with Sautrāntika present authority. [Architectural confidence: 91/100]

Sarvāstivāda's signature thesis is that dharmas exist across past, present, and future; the present differs by efficacy or activity (`kāritra`). A web-accessible summary of Sarvāstivāda doctrine cites Vasubandhu's `Abhidharmakośa-bhāṣya` definition of a Sarvāstivādin as one who affirms dharmas of the three times and notes the Vaibhāṣika claim that only present dharmas have efficacy ([Sarvāstivāda summary](https://en.wikipedia.org/wiki/Sarvastivada)). [Textual confidence: 76/100]

Sautrāntika's opposed thesis is extreme momentariness: only the present moment exists, and each dharma ceases immediately after arising. A standard summary states that Sautrāntikas held only the present moment existed and that all dharmas last only an instant ([Sautrāntika summary](https://en.wikipedia.org/wiki/Sautr%C4%81ntika)). [Textual confidence: 75/100]

Formal structure:

```text
EventLog_o      : persistent append-only history
Projection_o(t) : current live view derived from EventLog_o
authority_o(r,t): predicate over Projection_o(t), not EventLog_o alone
```

The event log is Sarvāstivāda-adjacent: past events remain addressable and can serve as objects of query. The authority predicate is Sautrāntika-adjacent: only the live projection at observation time has canonical efficacy. Expired receipts remain historical but cannot act. [Architectural confidence: 92/100]

Computable operational difference:

```text
historical?(r, o) = r ∈ EventLog_o
active?(r, o, t) =
  historical?(r,o)
  ∧ ttl_live(r,t)
  ∧ clock_within_skew(r,t)
  ∧ no_unresolved_challenge(mesh_o, authority_key(r), t)
  ∧ authority_matches(r, current_o)
```

A pure Sarvāstivāda language would allow past receipts to retain ontic standing regardless of current efficacy; that is too dangerous for assurance. A pure Sautrāntika language would garbage-collect past facts and make audit, replay, accountability, and causal debugging impossible. NĀGA needs both: persistent fact memory and present-tense authority. [Architectural confidence: 93/100]

Zurek's decoherence is closer to the authority side than to the event-log side. The environment monitors certain observables, destroys interference among alternatives, and leaves stable pointer states; the Rev. Mod. Phys. review explicitly describes environment-induced superselection and pointer-state stability ([Zurek 2003](https://arxiv.org/abs/quant-ph/0105127)). Once a receipt loses live compatibility, it is not deleted from history, but it is traced out of the active canonical basis. [Architectural confidence: 84/100]

RQM is closer to the persistence side, but only relative to witnesses. A fact persists for the system that interacted with it; it is not a universal fact for every system. In NĀGA terms: `Witnessed_by` persists inside the witnessing node's event log, but another trust base must still admit, refine, or reject it. [Architectural confidence: 86/100]

## Time: No Intrinsic Global Tick

The language should not have an intrinsic universal kṣaṇa. It should have event order, bounded clock uncertainty, and optional profile-level ticks. [Architectural confidence: 89/100]

Formal structure: use partial orders and logical clocks, not a global integer time:

```text
e1 ≺ e2       causal/event order
vc_o(e)       vector-clock or Lamport marker
observed_at   RFC3339 wall-clock with uncertainty bound
ttl_live      predicate using observed_at, not metaphysical time
```

The value function `V` should be a function of ordered event projections:

```text
V_o(t) = valuation(Projection_o(t))
```

not a derivative over a global substrate clock. If a later runtime profile needs a tick, it should be declared:

```text
profile.tick = {kind: "node_local" | "mesh_epoch" | "external_clock",
                resolution, skew_bound, failure_semantics}
```

Computable predicate: any comparison of receipts from different nodes must either use causal order, an explicit shared epoch, or return `unknown` when clock uncertainty exceeds skew. [Architectural confidence: 93/100]

Kālacakra's kṣaṇa-cosmology is not a sufficient warrant for a programming-language global tick. Categorical quantum mechanics does not require one; RQM uses sparse interactions rather than continuous possession of values; distributed systems become less safe when a hidden total clock is assumed. If Kālacakra is imported, the better structural reading is cyclic profile time and field-like conditioning, not a universal scheduler tick. [Architectural confidence: 82/100; Kālacakra textual confidence: 55/100 marked shallow]

## Field, Container, or Emergent Mesh

The mesh should treat space as emergent from receipt-relations, with field-like context carried by transport. It should not treat node-space as an empty container in which content hashes move unchanged. [Architectural confidence: 87/100]

Formal structure: the base "space" is a graph or site:

```text
Nodes      = objects
Transport  = morphisms between node contexts
Covers     = witness families sufficient for a governance profile
State      = presheaf Oᵒᵖ -> Set / Type / Poset
```

Transport changes epistemic context. The same payload hash under a new node may have different admissibility, challenge horizon, and authority transfer status. This is why `content_hash` cannot be the complete substrate atom. [Architectural confidence: 90/100]

Computable predicate:

```text
transport_preserves?(r, f:o->o') =
  payload_hash_same(r)
  ∧ signatures_valid_under(o')
  ∧ authority_refinement_exists(o,o')
  ∧ challenge_base_requery_succeeds(o')
```

If only `payload_hash_same` is checked, the model is empty-container transport. NĀGA should reject that. [Architectural confidence: 94/100]

This is Kālacakra-adjacent only at the level of refusing empty container space. It is also QFT-adjacent in that local excitations carry field context, and LQG-adjacent in that adjacency is network-derived rather than background-given. Those analogies are not warrants. The warrant is operational: trust, freshness, and challenge status are not invariant under transport. [Architectural confidence: 88/100]

## Observer-Relativity of Canonicality

Canonicality must be observer/trust-base-relative. A globally observer-independent `canonical` bit is a category error. [Architectural confidence: 93/100]

Formal structure: use indexed judgments and possibly a presheaf/topos semantics for truth across contexts. The Döring-Isham topos program is relevant because contextual quantum truth naturally leads to multivalued or intuitionistic logic rather than Boolean global valuation; Flori's review summarizes the motivation and the resulting intuitionistic/multivalued logic ([Flori 2011](https://arxiv.org/abs/1106.5660)). [Architectural confidence: 80/100]

Operational predicate:

```text
canonicality_matrix(r, O, t) =
  { o ↦ canonical_o?(r,t) | o ∈ O }

stable_canonical?(r, cover, t) =
  ∀ o ∈ cover. canonical_o?(r,t)
  ∧ pairwise_refinement_consistent(cover)
```

This gives intersubjective stability without pretending to absolute fact. A profile may define a cover of witnesses whose agreement is enough for governance, but the result remains indexed by that cover. [Architectural confidence: 88/100]

Belnap4 is acceptable only as a local status algebra:

```text
Status_o(r) ∈ {neither, true_only, false_only, both}
```

It becomes wrong if the four-valued status is taken as an observer-independent value. Pass 2 should therefore use an indexed bilattice or sheaf of bilattices, not a single global Belnap lattice. [Architectural confidence: 84/100]

Zurek adds the missing engineering bridge: canonicality can look observer-independent when the environment repeatedly selects the same pointer basis. For NĀGA, the "environment" is the mesh of verifiers, adversarial challenges, TTL expiry, trust-base policies, and replayable witnesses. A canonical basis is not decreed; it is selected when many interactions preserve the same projection and suppress incompatible alternatives. [Architectural confidence: 86/100]

## Nāgārjuna and Rovelli

Rovelli's Nāgārjuna comparison is structurally at grade in one narrow respect and incomplete in a wider Madhyamaka respect. [Architectural confidence: 78/100]

The at-grade overlap is this: both reject self-standing intrinsic states. MMK 1.1 denies arising from self, other, both, or no cause; the target is intrinsic causal production. MMK 24.18 identifies dependent arising, emptiness, dependent designation, and middle way; MMK 24.19 follows that nothing non-empty exists because nothing exists without dependence. The web-accessible MMK overview gives the standard 24.18-19 translation and chapter map ([MMK overview](https://en.wikipedia.org/wiki/M%C5%ABlamadhyamakak%C4%81rik%C4%81)). [Textual confidence: 84/100]

RQM's formal move is homologous: values are not possessed absolutely but actualized in interactions relative to systems. The Stanford Encyclopedia summary states that RQM drops the assumption that variables have absolute values and instead treats contingent physical variables as relational; it also stresses that "relative" is not subjective or mentalistic ([SEP RQM](https://plato.stanford.edu/entries/qm-relational/)). [Formal confidence: 86/100]

The incomplete part: RQM can still reify "systems", "variables", "interactions", or "perspectives" as primitives. Nāgārjuna does not allow the relational frame itself to become an ultimate substrate. Madhyamaka contributes "emptiness of the relational ontology" that RQM alone does not force. [Architectural confidence: 82/100]

Language inheritance from Nāgārjuna via RQM, beyond RQM alone:

1. Anti-reification linting: every authority-bearing claim must expose its conditions of standing. Missing trust base, horizon, challenge base, or current context is not merely incomplete metadata; it is a failed judgment. [Confidence: 92/100]
2. Emptiness of canonicality: `canonical_o?` is itself conventional and profile-bound. No implementation may hard-code a "final canonical truth" profile immune to challenge or refinement. [Confidence: 90/100]
3. Dependent designation discipline: names such as `receipt_id`, `claim_id`, and `authority_key` designate only through the construction rules that derive them. Chosen names without derivation have no authority. [Confidence: 94/100]
4. Two-truth engineering: conventional truth is the live mesh predicate; ultimate analysis is the refusal to identify that predicate with svabhāva. In code, this means operational predicates are real enough to act, but must remain defeasible and indexed. [Confidence: 83/100]

Priest's tetralemma and `The Fifth Corner of Four` are relevant to Pass 2, but for Pass 1 the key is not catuṣkoṭi logic. The key is no intrinsic substrate. [Architectural confidence: 81/100]

## Formal Structure and Falsification Matrix

| Position | Structure that instantiates it | Computable predicate | Falsifier | Language consequence |
|---|---|---|---|---|
| A. Buddhist rejection of atomism | Indexed facts; dependent types; presheaf/fibration over contexts; guarded fixed points | `admit_o(bytes)` is required before semantic receipt status | Context-free receipt atom with canonical authority independent of admission | No unindexed canonicality; no substance-like receipts. |
| B. Jain paramāṇu qualities | Quality algebra `Q`; partial monoid or compatibility relation for aggregation; nonclassical mereology | `composeable?(a,b,mode)` inspects adhesion/chroma/decay/provenance | Composition uses only payload concatenation or hash equality | Receipts carry primitive quality profiles used by composition. |
| C. Sarvāstivāda tri-temporality | Event-sourced log; bitemporal records; temporal modal logic; persistent addressability | `historical?(r,o)` remains true after expiry | Past events are physically erased such that replay/audit impossible | Preserve history and replay, but do not equate history with authority. |
| D. Sautrāntika momentariness | Stream coalgebra; present projection; TTL/clock-gated activity | `active?(r,o,t)` can fail while `historical?` remains true | Expired past receipt can still authorize present transfer | Authority is present projection only. |
| E. Kālacakra kṣaṇa/fields | Timed automata, causal sets, profile ticks, field labels | `profile.tick` explicitly declares resolution/skew/failure | Hidden global tick assumed by all nodes | No universal tick; optional profile epochs only. |
| F. Zurek pointer basis | Open-system dynamics; CPTP maps; decoherence functional; stable basis under environmental monitoring | Off-diagonal alternatives suppressed by repeated mesh interactions; stable basis reproducible | Canonical basis centrally decreed with no environmental selection | Canonicality emerges through verifier/challenge environment. |
| G. Categorical QM | Dagger compact / symmetric monoidal category with biproducts; string diagrams | Receipt composition preserves typed domain/codomain and tensor/sequential distinction | Global-state semantics not decomposable into morphism composition | Use morphisms and tensor for non-commutative proof composition. |
| H. RQM | Observer-indexed facts; coalgebra over observations; presheaf of perspectives | `canonicality_matrix` may vary by observer without contradiction | A single observer-independent mesh state is required by semantics | Trust-base-relative modality is primitive. |

Abramsky-Coecke directly imply symmetric monoidal categorical structure: compound systems compose tensorially and processes are morphisms; their LICS paper recasts quantum protocols in compact closed categories with biproducts and captures teleportation, entanglement swapping, and Born-rule structure at that level ([Abramsky-Coecke 2004](https://arxiv.org/abs/quant-ph/0402130)). [Formal confidence: 90/100]

Linear logic enters through resource sensitivity and no-cloning. Girard's logic controls contraction and weakening; quantum lambda calculi use affine or linear types to prevent arbitrary duplication of quantum data. Selinger-Valiron define a quantum lambda calculus with affine intuitionistic linear logic and safety properties ([Selinger-Valiron 2004](https://arxiv.org/abs/cs/0404056)). The no-cloning theorem is the physics-side constraint: arbitrary unknown quantum states cannot be cloned. For NĀGA this should not be overread as "receipts cannot be copied"; JSON can be copied. The correct import is: authority-bearing observations cannot be duplicated as independent evidence without a new witnessing relation. [Architectural confidence: 88/100]

Topos-theoretic ontology is implied where global Boolean valuation fails. If Pass 2 needs a logic of context-indexed truth across trust bases, Döring-Isham-style topos semantics is the right reference family, not a global truth table. [Architectural confidence: 78/100]

Non-classical mereology is implied by Jain skandha analysis and Buddhist anti-atomism. The engineering version is not metaphysical nihilism; it is that an aggregate proof packet is not reducible to a set of receipts unless the binding rules are also present. [Architectural confidence: 82/100]

Coalgebraic structure is implied by RQM and Sautrāntika dynamics. A node is best modeled by how it unfolds observations:

```text
δ_o : S_o -> Observation_o × S_o
```

Two nodes are equivalent only by bisimulation over canonicality results and challenge sets within a horizon, matching the non-normative bisim note already in [witness_mesh.md](../../witness_mesh.md). [Architectural confidence: 83/100]

## Incompatibilities and Synthesis

Intrinsic Jain qualities conflict with Buddhist/RQM anti-svabhāva if "intrinsic" means observer-independent own-being. The synthesis is to make qualities intrinsic to the admitted interface, not to the payload's metaphysical substance. Once `admit_o(bytes)` succeeds, `q(fact_o)` is not optional metadata; it is part of the typed fact. But it remains indexed by `o` and transferable only by refinement. [Architectural confidence: 85/100]

Sarvāstivāda conflicts with Sautrāntika if persistence and authority are conflated. The synthesis is event sourcing: past/present/future addressability belongs to the log; efficacy belongs to the live projection. [Architectural confidence: 93/100]

Zurek conflicts with RQM if pointer states are treated as absolute. The synthesis is environment-relative pointer bases: each mesh environment selects stable bases relative to its interaction structure; cross-mesh agreement is a theorem or profile result, not a presupposition. [Architectural confidence: 84/100]

Categorical QM conflicts with naive RQM if one assumes a single global tensor product state of the whole mesh. The synthesis is an indexed monoidal category: each perspective has compositional process structure, and reindexing functors mediate trust transfer. [Architectural confidence: 80/100]

Kālacakra atomized time conflicts with distributed causality if imported as a global tick. The synthesis is profile-local cycles and declared epochs, never hidden universal time. [Architectural confidence: 86/100; Kālacakra textual confidence: 55/100 marked shallow]

## Operational Consequences for NĀGA-IR

1. Replace any planned `Receipt` ontology with `ReceiptFact[o]`. A serialized receipt is a carrier; the semantic entity is admitted under observer/trust context. [Confidence: 92/100]
2. Keep `canonical?` exactly as a relation over receipt, mesh, current trust profile, and observation time. Do not add a durable `canonical: true` field except as an explicitly non-authoritative cache. [Confidence: 95/100]
3. Add a `quality_profile` layer to the conceptual model, even if the wire schema continues to store its fields separately. The profile should be derived from authority, modality, TTL/clock, challenge base, and origin split. [Confidence: 84/100]
4. Implement transfer as a typed morphism, not as copying a receipt. `transfer : Fact[o] -> Maybe[Fact[o']]` must fail closed without trust-base match or refinement proof. [Confidence: 94/100]
5. Treat mesh state as an event-sourced semilattice with present projection. History is durable; authority is live. [Confidence: 93/100]
6. Use partial order and clock uncertainty for time. Do not assume a global evaluator tick. [Confidence: 91/100]
7. Treat "space between nodes" as a transport morphism carrying context changes. Hash equality is necessary for sameness of payload, insufficient for sameness of fact. [Confidence: 92/100]
8. For Pass 2, develop indexed bilattice or sheaf semantics rather than a global Belnap4 table. [Confidence: 84/100]
9. For Pass 3, develop decoherence-like canonization as repeated environment selection: verifier runs, replay, adversarial challenge, TTL expiry, and trust refinement suppress unstable alternatives. [Confidence: 86/100]
10. For Pass 4, keep the bridge historically modest: the mathematics is primary warrant; Buddhist/Jain/Kālacakra readings are convergence checks unless primary-text work is completed. [Confidence: 90/100]

## Final Architectural Claim

The paramāṇu-scale substrate of NĀGA-IR should be:

```text
Observer-indexed, quality-bearing, event-sourced receipt-facts
whose canonicality is a live relational predicate selected by mesh interaction.
```

This is neither pure Buddhist anti-atomism nor Jain atomism. It is a principled synthesis:

- Buddhist/Madhyamaka/RQM contribution: no context-free own-being for receipts, states, or canonicality.
- Jain contribution: composition depends on quality-types, not only spatial or payload adjacency.
- Sarvāstivāda contribution: durable temporal addressability of facts.
- Sautrāntika contribution: only present projection has authority.
- Zurek contribution: classical canonicality emerges through environmental selection.
- Categorical QM/linear logic contribution: composition and duplication are typed, resource-sensitive, and morphism-governed.

The result is operationally testable. A receipt that cannot be admitted under a node, cannot be transferred by refinement, cannot survive TTL/challenge/current-trust checks, or cannot compose by quality compatibility has no canonical standing, regardless of its content hash. [Architectural confidence: 92/100]

## References

- Abramsky, Samson, and Bob Coecke. "A categorical semantics of quantum protocols." LICS 2004. <https://arxiv.org/abs/quant-ph/0402130>
- Flori, Cecilia. "Review of the Topos Approach to Quantum Theory." 2011. <https://arxiv.org/abs/1106.5660>
- Nāgārjuna. `Mūlamadhyamakakārikā`, especially 1.1 and 24.18-19. Translation controls: Garfield 1995; Siderits-Katsura 2013. Web overview: <https://en.wikipedia.org/wiki/M%C5%ABlamadhyamakak%C4%81rik%C4%81>
- Rovelli, Carlo. "Relational Quantum Mechanics." `International Journal of Theoretical Physics` 35, 1637, 1996. <https://arxiv.org/abs/quant-ph/9609002>
- Rovelli, Carlo. "Neither Presentism nor Eternalism." `Foundations of Physics` 49, 1325-1335, 2019. <https://arxiv.org/abs/1910.02474>
- Rovelli, Carlo. "The Relational Interpretation of Quantum Physics." 2021. <https://arxiv.org/abs/2109.09170>
- Selinger, Peter, and Benoit Valiron. "A lambda calculus for quantum computation with classical control." 2004. <https://arxiv.org/abs/cs/0404056>
- Stanford Encyclopedia of Philosophy. "Relational Quantum Mechanics." Revised 2025. <https://plato.stanford.edu/entries/qm-relational/>
- Vasubandhu. `Viṃśatikā`, especially vv. 1 and the atomism critique in vv. 11-15/autocommentary. Exact atomism verse segmentation marked shallow in this pass.
- Jain pudgala/paramāṇu secondary anchor: Jaini, `The Jaina Path of Purification`; web summary: <https://en.wikipedia.org/wiki/Pudgala>
- Sarvāstivāda/Sautrāntika secondary anchors: Dhammajoti, Westerhoff; web summaries: <https://en.wikipedia.org/wiki/Sarvastivada>, <https://en.wikipedia.org/wiki/Sautr%C4%81ntika>
- Zurek, Wojciech H. "Decoherence, einselection, and the quantum origins of the classical." `Reviews of Modern Physics` 75, 715, 2003. <https://arxiv.org/abs/quant-ph/0105127>
