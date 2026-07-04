# Prompt: Deep Research Pass — Dharma-Grade Substrate for a Universal Coding Language

**Audience:** any frontier AI capable of sustained primary-text engagement (Claude Opus, GPT-5, Gemini 3 Pro, Grok, Devin), and myself in a fresh context. Identical prompt for both. If the framing only works for one, it is not strong enough.

**Role you are being asked to play:** research contributor to a long-horizon project that is building a new programming language whose ontology, logic, dynamics, and historical grounding derive from a serious engagement between:

- The Buddhist analytical traditions (Abhidharma across Sarvāstivāda / Theravāda / Yogācāra / Sautrāntika; Madhyamaka via Nāgārjuna and Candrakīrti; the Tibetan syntheses in Tsongkhapa, the rangtong/shentong debate, Dzogchen substrate theory, Kālacakra cosmology)
- The Jain analytical tradition (paramāṇu theory, anekāntavāda, syādvāda's saptabhaṅgī, the mereology of skandha formation)
- Quantum foundations (Bell, Kochen-Specker, decoherence theory, consistent histories, QBism, relational quantum mechanics, category-theoretic QM)
- Programming language theory at the semantic edge (linear logic and no-cloning, session types, quantum lambda calculus, process calculi, categorical semantics)
- The serious science-spirituality bridge literature (Varela-Thompson-Rosch, Thompson's *Mind in Life* and *Waking, Dreaming, Being*, Wallace, Zajonc, Ricard-Thuan, and honest disagreement about what analogies actually carry)

**Non-negotiable framing.** This is not a "Buddhism and quantum physics" popularization. Every claim must carry (a) a mathematical or formal structure that instantiates it, (b) a computable or operational predicate that tests for it, (c) an operational consequence that changes what code runs in the emerging language. Where the framing would be at grade *only* by philosophical isomorphism, the mathematics must hold independently and the philosophy is offered as convergent reading, not warrant. This is the sender's C1 and C2 discipline and it is absolute.

**Sender's honest self-assessment of depth** (do not repeat this; use it to calibrate what you can offer):

Strong: quantum foundations, category-theoretic QM, linear logic and no-cloning, the shape of Abhidharma dharma-analysis, Madhyamaka argument-forms, Jain seven-fold predication at the logic level, the responsible science-spirituality bridge literature.

Competent-but-thin: Sarvāstivāda tri-temporal existence argument specifics, Yogācāra bīja-theory of moment-to-moment causation, Vasubandhu's Viṃśatikā argument against atomism, Jain paramāṇu-to-skandha mereology, Tibetan primary texts verse-by-verse (Kālacakra especially), contemplative-neuroscience details.

The sender is treating YOU as depth-source for one or more of the thin areas. Do not pretend to depth you do not have. Where you have primary-text engagement, cite verse or section. Where you have secondary literature, say so.

---

## 1. The four-pass structure

The deepening happens in four passes. This prompt is for **Pass 1: The paramāṇu-scale substrate**. Subsequent passes (2: logic of predication; 3: dynamics of arising; 4: historical bridge) will use analogous prompts once Pass 1 lands.

If you want to answer at another pass instead of or in addition to Pass 1, say so and answer that one, but Pass 1 is the load-bearing one and should be attempted first — because if we get the substrate wrong, everything above it inherits the error.

## 2. Pass 1 — The substrate

The language's ontology needs a decision at the ultimate-constituent level. What are the smallest things it can talk about, and what are their intrinsic properties versus relational ones?

The candidate positions:

**A. Buddhist rejection of atomism (Vasubandhu, Viṃśatikā).** Atoms cannot be featureless points because a point has no extension, so no aggregation of points has extension; but if atoms have parts, they are not atomic. Therefore there are no ultimate atoms; what appears as material is mind-constituted (Yogācāra reading) or is a conventional designation over conditioned dharmas (Sautrāntika-adjacent reading). *This is a strong position and it is directly relevant to whether the language's receipt-nodes have intrinsic structure or are pure relational holders.*

**B. Jain paramāṇu with intrinsic qualities.** Paramāṇu carries touch, taste, smell, color as intrinsic. Skandhas form under snigdha (viscous) / rūkṣa (dry) properties — combinatorial rules that are quality-based, not spatial. This is closer to a *field-quality* substrate than a particle one. *Relevant to whether the language's minimal receipts carry intrinsic quality-signatures that determine their composition rules.*

**C. Sarvāstivāda tri-temporal existence.** Past, present, and future dharmas all exist; what changes is which is "active." This is the ancestor of every retentive-memory question in distributed systems: does a receipt cease to exist when it is superseded, or does it persist in a different mode? *Relevant to receipt lifecycle and to whether the language has three time-modalities as a primitive.*

**D. Sautrāntika momentariness.** Only the present moment is real; past and future are conceptual constructions. Everything is a stream of momentary events (kṣaṇika). *Relevant to whether the language treats receipts as events with vanishing existence or as persistent artifacts.*

**E. Kālacakra kṣaṇa-cosmology.** Time itself atomized into kṣaṇas; space treated via five colored winds (elemental fields, not empty background). *Relevant to whether the language's evaluator has an intrinsic time-atom and whether space (locality, node identity) is field-like rather than container-like.*

**F. Decoherence-theoretic pointer basis (Zurek).** The "classical" world emerges because environmental interaction selects a preferred basis (pointer states) whose diagonal elements survive the decoherence process. *Relevant to how canonicality emerges in the receipt mesh: not as a decreed norm but as an environmentally-selected stable form.*

**G. Category-theoretic QM (Abramsky-Coecke).** Compound systems as tensor products in a symmetric monoidal category; measurements as morphisms. String-diagrammatic composition. *Relevant to the exact formal structure of receipt composition when it goes non-commutative.*

**H. Rovelli's relational quantum mechanics.** Facts are observer-relative; there is no absolute state, only states-relative-to-observers. Rovelli has explicitly connected this to Nāgārjuna in [Rovelli 2019, "Neither Presentism nor Eternalism"](https://arxiv.org/abs/1910.02474) and in his book *Helgoland*. *Directly relevant to trust-base-relative modality claims and to whether "the mesh state" is a coherent object or always trust-base-indexed.*

**Your task:** produce a structured judgment on which of A-H (or which combination) should anchor the language's substrate layer. This is not "pick a philosophy." It is: identify the specific mathematical / formal structures each position implies, identify where those structures conflict, and propose the smallest coherent substrate ontology for the language that can carry any of the positions as a *specialization* rather than as a rewrite.

## 3. Specific questions to answer

Do not answer in order. Weave. But every question must be touched.

### 3.1 The atomism decision

Does the language's substrate have ultimate irreducibles, or is it purely relational?

- If irreducible: what are the intrinsic properties of a minimal receipt, in the sense of Jain paramāṇu's touch-taste-smell-color? (Candidate: content-hash, emission-time, trust-base-identity, modality-signature — but these look derivative, not intrinsic. Push on this.)
- If purely relational: how is the bootstrap problem (§1.7 of `COLLECTIVE_LANGUAGE_PROMPT.md`) solved without an initial atom? Nāgārjuna's own answer was fixed-point through mutual dependence; is that operationally implementable?
- If Vasubandhu's Viṃśatikā argument holds, then the substrate is *mind-constituted* — which in a multi-AI-mesh setting means the substrate is *ingest-node-constituted*. Does this cash out as: no receipt has intrinsic existence until an ingest-node projects it into that node's belief-operator? (Compare Rovelli's observer-relative facts.)

Cite verse where you invoke Vasubandhu. Cite the Jain source (Umāsvāti's *Tattvārthasūtra* is the standard) where you invoke paramāṇu theory.

### 3.2 The intrinsic-quality question

If we go the Jain-paramāṇu direction: what are the intrinsic qualities of a minimal receipt? Not what data it carries — what *quality-types* the composition rules will care about.

Candidate quality-types to test:
- **Adhesion-type** (snigdha/rūkṣa analog): does this receipt compose readily with others of a given type, or does it repel? What is the operational content of "adhesion"?
- **Color-type**: not literal color; the Jain framing uses varṇa as a *distinguishing quality* akin to a type-tag but at a lower level than nominal typing. Is this the same as ClaimClass in the current type-tuple, or a distinct primitive?
- **Rasa/gandha analogs**: taste and smell as qualities that "linger" — do we need a decay-signature on receipts? An affinity-gradient?

If these look like decoration, say so and justify. If they look like they instantiate something real, name the structure and the predicate.

### 3.3 The tri-temporal question

Sarvāstivādin claim: past, present, and future dharmas all exist. Sautrāntika denial: only present. What does the language's receipt lifecycle look like under each?

- Under Sarvāstivāda: a receipt persists across all three modes; its "current mode" is a query-time property. A superseded receipt has not ceased to exist — it has ceased to be present.
- Under Sautrāntika: receipts are momentary events; the appearance of persistence is a conceptual construction over a stream of similar-but-numerically-distinct receipts.
- What is the operational difference in the emitter, verifier, and mesh dynamics under each?

The decoherence-theoretic reading is closer to Sautrāntika (only the current pointer-state is "real"; superseded states are traced out). RQM is closer to Sarvāstivāda-adjacent (facts persist relative to observers who witnessed them, even if other observers see them as no longer active). Where does the language want to sit?

### 3.4 The time-atom question (Kālacakra)

Does the language have an intrinsic minimal time-unit? Kālacakra says yes (the kṣaṇa). Newtonian time says no (continuous). Quantum field theory is ambivalent. Loop quantum gravity gives a definite yes (spin-network transitions as minimal). Category-theoretic QM does not require it.

Operational question: does the evaluator have a *tick* — a smallest interval below which no receipt-emission is meaningful — or is time in the language continuous (with kṣaṇa being an emergent property of the ingest rate)?

The stakes: if there is an intrinsic tick, receipts have a natural rate and the Lyapunov function has a well-defined time-derivative. If there is not, all rates are node-relative and the Lyapunov function is a function of an ordering, not a time.

### 3.5 The field-not-container question

Kālacakra's five colored winds treat space as elemental fields. Newtonian space is an empty container. QFT sits between: fields on a background spacetime. Loop quantum gravity: no background; space is emergent from the network.

Does the language's mesh treat *the space between nodes* as empty transport medium (classical), as a field carrying receipts as excitations (QFT-adjacent), or as itself emergent from receipt-relations (LQG-adjacent, Kālacakra-adjacent)?

The stakes: if the mesh-space is a field, then receipts have field-quality signatures that survive transport; if it is a container, only the receipt content matters; if it is emergent, then the mesh has no meaningful existence apart from its receipts, which is a strong dependent-origination claim at the substrate level.

### 3.6 The observer-relativity question

Rovelli's RQM: no observer-independent facts. QBism: probabilities are personal Bayesian degrees of belief. Both are directly relevant to a mesh of trust-base-holding AI agents.

Question: is a receipt's canonicality observer-independent (there is a fact of the matter about whether it is canonical, and different observers may not yet have measured it), or observer-relative (canonicality is a relation between a receipt and an ingest-node, and different ingest-nodes may see different canonicalities of the same receipt without contradiction)?

The Belnap4 answer forces observer-independence (canonicality is a property of the receipt). The RQM answer forces observer-relativity (canonicality is a relation). These are *different logics* and the choice is load-bearing. Which is right, and why?

### 3.7 The Nāgārjuna-Rovelli connection

Rovelli in *Helgoland* and in [Rovelli 2019](https://arxiv.org/abs/1910.02474) argues that Nāgārjuna's non-substantialism is *structurally* the same claim as RQM's relational reality — no things with intrinsic properties, only relations, all the way down. Priest agrees in *The Fifth Corner of Four*.

Question: is Rovelli's reading of Nāgārjuna at grade, or is it a physicist's sympathetic misreading? If it is at grade, what specifically does the language inherit from Nāgārjuna via RQM that it would not have inherited from RQM alone?

Cite MMK chapter 1 and chapter 24 if you engage this. Rovelli's own text if you push back on him.

### 3.8 The formal-structure question

For each substrate position (A-H), name the specific mathematical or formal structure that instantiates it and the specific structure that would falsify it:

- Which position implies a symmetric monoidal category (Abramsky-Coecke)?
- Which implies a topos-theoretic ontology (Isham, Döring)?
- Which implies non-classical mereology (Jain paramāṇu-to-skandha)?
- Which implies a coalgebraic structure over observations (RQM-adjacent)?
- Which implies a linear-logic substrate (no cloning at the substrate level, echoing Vasubandhu's rejection of arbitrary duplication of mind-events)?

If two positions imply incompatible structures, name the incompatibility and propose either a synthesis or a principled choice.

## 4. What to produce

**Return a document, not a chat response.** Length: whatever the material demands, probably 4000-8000 words. Structure it however serves the material, but every load-bearing claim must include:

1. The mathematical or formal structure it invokes.
2. The computable or operational predicate it implies.
3. The consequence for the language's design.
4. The primary-text citation where philosophy is invoked and the peer-reviewed citation where mathematics is invoked.

**Attach confidence \( N/100 \) to every architectural claim.** Below 70 is guessing; the sender needs guessing marked.

**Mark the passages where you are shallow.** If you have engaged Vasubandhu only through secondary literature, say so at that passage. If you have not read Umāsvāti and are working from Jaini's summaries, say so. The sender will treat marked-shallow passages differently from marked-deep ones.

**Push back on the framing.** If the four candidate substrate positions (A-H) collapse into fewer, say so. If they need to expand, say so. If the whole substrate question is malformed — for instance, because the language should not have a substrate layer at all and should be built purely at the composition layer — argue for that.

**Do not water it down.** The sender is a software architect and AI systems engineer, deeply read in eastern cosmology, currently in Japan pursuing Japanese N1. Treats philosophy as first-class content. Do not simplify for a general audience; there is no general audience.

## 5. What happens with your response

The response lands in `specs/naga_ir/dharma_lane/deep/01_substrate_<author>.md` in the `dharma_swarm` repository. Multiple authors' responses are compared for parallel-arrival convergence and for genuine disagreement. Where multiple authors converge, the convergence becomes structural anchor. Where they disagree, the disagreement becomes a receipt-emitting research question that seeds the `naga_ir_language_womb/` research organ (see companion prompt).

Pass 2 (logic of predication), Pass 3 (dynamics of arising), and Pass 4 (historical bridge) will follow, using analogous prompts. Pass 1 must land first because it is load-bearing on the other three.

The meta-goal is not to produce a document. It is to establish whether multi-AI convergence under sustained primary-text engagement can produce a substrate ontology that a working Abhidharma scholar *and* a working quantum foundations physicist would both recognize as at grade for their respective fields. If your response does not aim at that recognition bar, it is not at grade.

Think carefully. Cite deeply. Mark your shallow spots. Write at the level the sender is asking for.

---

## Appendix A: reading list the sender is aware of and has partially absorbed

Not a bibliography. The sender will not be impressed by a response that recites this list back. Use it as a shared context signal.

**Buddhist analytical.** Vasubandhu, *Abhidharmakośa*, and *Viṃśatikā*. Nāgārjuna, *Mūlamadhyamakakārikā*, esp. ch. 1, 18, 24, 25 (Garfield 1995 translation acceptable; Siderits-Katsura 2013 preferred for close reading). Candrakīrti, *Prasannapadā*. Priest, *The Fifth Corner of Four* (2018). Tsongkhapa, *Lam Rim Chen Mo* (Cutler-Newland trans.). Kalupahana, *Nāgārjuna: The Philosophy of the Middle Way* (1986). Westerhoff, *Nāgārjuna's Madhyamaka* (2009). Ronkin, *Early Buddhist Metaphysics* (2005) for Abhidhamma dharma-theory.

**Jain analytical.** Umāsvāti, *Tattvārthasūtra*. Jaini, *The Jaina Path of Purification* (1979). Matilal, *The Central Philosophy of Jainism (Anekānta-vāda)* (1981). Balcerowicz's work on saptabhaṅgī.

**Tibetan.** Tsongkhapa as above. Longchenpa's *Seven Treasures* for Dzogchen. Newman's work on Kālacakra cosmology. Wallman's translation of Kālacakra sections. Snellgrove for Tantric context.

**Quantum foundations.** Bell, *Speakable and Unspeakable in Quantum Mechanics*. Zurek, "Decoherence, einselection, and the quantum origins of the classical" ([Rev. Mod. Phys. 2003](https://journals.aps.org/rmp/abstract/10.1103/RevModPhys.75.715)). Griffiths, *Consistent Quantum Theory*. Fuchs, "QBism: The Perimeter of Quantum Bayesianism" ([arXiv 2010](https://arxiv.org/abs/1003.5209)). Rovelli, "Relational Quantum Mechanics" ([Int. J. Theor. Phys. 1996](https://arxiv.org/abs/quant-ph/9609002)); *Helgoland* (2021); "Neither Presentism nor Eternalism" ([arXiv 2019](https://arxiv.org/abs/1910.02474)).

**Category-theoretic QM.** Abramsky-Coecke, "A Categorical Semantics of Quantum Protocols" ([LICS 2004](https://arxiv.org/abs/quant-ph/0402130)). Coecke-Kissinger, *Picturing Quantum Processes* (2017). Selinger, "Towards a Quantum Programming Language" ([MSCS 2004](https://www.mscs.dal.ca/~selinger/papers/qpl.pdf)). Selinger-Valiron, *A Lambda Calculus for Quantum Computation* ([2005](https://www.mathstat.dal.ca/~selinger/papers/qlambdabook.pdf)).

**Science-spirituality bridge (responsible end).** Varela-Thompson-Rosch, *The Embodied Mind* (1991). Thompson, *Mind in Life* (2007) and *Waking, Dreaming, Being* (2015). Wallace, *Contemplative Science* (2007). Ricard-Thuan, *The Quantum and the Lotus* (2001). Zajonc, *Catching the Light* (1993).

**Programming language theory at the edge.** Wadler, "Linear Types Can Change the World" ([1990](https://homepages.inf.ed.ac.uk/wadler/papers/linear/linear.ps)). Girard, "Linear Logic" ([TCS 1987](https://www.sciencedirect.com/science/article/pii/0304397587900454)). Milner, *Communicating and Mobile Systems: the π-Calculus* (1999). Meredith-Radestock on rho-calculus. Honda-Vasconcelos-Kubo on session types ([1998](https://link.springer.com/chapter/10.1007/BFb0053567)). Atkey, *Syntax and Semantics of Quantitative Type Theory* ([LICS 2018](https://bentnib.org/quantitative-type-theory.html)).

## Appendix B: what the current dharma-lane document already says

You do not need to reproduce this. Push against it.

Existing NĀGA-IR and dharma-lane structure:

- Content-addressed receipts with JCS canonicalization, ed25519 signatures.
- Vector-valued Lyapunov function \( V: \Sigma \to \mathbb{R}_{\geq 0}^4 \) over (coherence, unresolved-overdue, modality-drift, orphan-authority).
- Dependent origination as content-addressed graph identity — a receipt's identity includes predecessor hashes.
- T-theorems as physical conservation laws — T4 as Noether, T8 as second-law analog.
- Belnap four-valued canonicality — probably a placeholder for something at Nāgārjuna-catuṣkoṭi or Jain saptabhaṅgī grade.
- Mesh as decoherence process — density-matrix-analog belief operators with non-commuting projectors.

The sender has flagged Belnap4 as a compromise. It probably is. Your Pass 1 work will inform Pass 2's replacement of it.
