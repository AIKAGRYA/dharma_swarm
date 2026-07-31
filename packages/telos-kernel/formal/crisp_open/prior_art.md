# Prior Art — Crisp-Open Conversion: Proof-Carrying Self-Modification

**Research cutoff:** 2026-07-31  
**Phase status:** complete before construction  
**Claim discipline:** this document reports what the cited work establishes, where it stops, and whether it subsumes either limb of the proposed target theorem. “Not found” means not found in the sources and indexes checked; it is not a universal nonexistence claim.

## 1. Result of the prior-art gate

The exact conjunction requested by the campaign was **not located as an already-published theorem**:

1. an immutable checker accepts only invariant-preserving self-modifications;
2. invariant closure holds by induction over arbitrarily many accepted rewrites; and
3. the reachable systems are unbounded under a defended, nontrivial semantic complexity measure.

However, the closure half is not novel in broad form. Proof-carrying code, typed assembly language, foundational proof-carrying code, certified compilation, and especially Cai–Shao–Vaynberg’s mechanized **Certified Self-Modifying Code** already establish powerful forms of fixed-checker safety and sound reasoning about runtime-generated or mutated code. The new burden, if any, lies in combining such closure with a mathematically explicit opening limb that is not merely program-size inflation.

The strongest direct predecessor is Cai, Shao, and Vaynberg (2007). It gives a mechanized Coq framework for modular reasoning about code that loads, generates, or mutates code at runtime. It therefore substantially subsumes the proposed closure idea, though not the proposed theorem’s unbounded-opening requirement.

No source checked establishes that an invariant-preserving rewrite relation also generates unbounded **qualitative** novelty. Open-ended-evolution literature instead repeatedly warns that a system can satisfy apparently unbounded size, diversity, compressibility, or activity criteria while remaining scientifically trivial. This is the central adversarial constraint on limb (B).

## 2. Correction to the motivating theorem claims

The campaign’s opening paragraph is directionally useful but mathematically too broad.

**Löb.** Löb’s theorem concerns provability predicates in sufficiently strong formal systems satisfying the derivability conditions. In one familiar form, if a theory proves `Prov(⌜P⌝) → P`, then it proves `P`. It constrains broad internal reflection and soundness claims; it does **not** say that every system is unable to verify every bounded or syntactically restricted successor. A fixed external proof checker shifts the trusted base rather than abolishing it.

**Rice.** Rice’s theorem rules out a total decision procedure for every nontrivial extensional property over arbitrary partial computable functions/programs. It does **not** forbid decidable checking in a restricted language, finite-state fragment, proof-carrying discipline, or syntactic class whose semantic property is decidable by construction.

Accordingly, the candidate escape is legitimate only under a precise claim: the checker’s soundness is trusted externally; the rewrite domain is restricted; and the invariant is decidable on that domain. This avoids asking the mutable object system to certify the global soundness of its own proof calculus. It does not remove the trusted computing base, prove the checker correct from nowhere, or solve unrestricted program verification.

## 3. Foundational barriers

### PA-01 — Löb, “Solution of a Problem of Leon Henkin” (1955)

**Verified record:** M. H. Löb, *The Journal of Symbolic Logic* 20(2), 115–118. DOI: https://doi.org/10.2307/2266895

**Establishes.** Under standard derivability conditions, sufficiently strong formal systems cannot freely internalize their own soundness; the theorem characterizes when a system can prove an implication from provability to truth.

**Stops.** It does not prohibit external proof checking, stratified systems, restricted object languages, or proving preservation lemmas about a relation without asserting the checker’s global soundness inside the mutable object system.

**Subsumes target.** It constrains the interpretation and trusted-base story, but subsumes neither limb (A) nor limb (B).

### PA-02 — Rice, “Classes of Recursively Enumerable Sets and Their Decision Problems” (1953)

**Verified record:** H. G. Rice, *Transactions of the American Mathematical Society* 74(2), 358–366. DOI: https://doi.org/10.2307/1990888

**Establishes.** No nontrivial extensional class of recursively enumerable sets is decidable in the unrestricted setting captured by the theorem.

**Stops.** It does not apply as a blanket ban on properties of a deliberately restricted, decidable language or on proof validation where the certificate carries the difficult reasoning.

**Subsumes target.** It forces a restricted modification domain or incomplete gate. It proves neither requested limb.

## 4. Proof-carrying code, typed low-level languages, and certified compilation

### PA-03 — Necula, “Proof-Carrying Code” (1997)

**Verified record:** George C. Necula, POPL 1997, pp. 106–119. DOI: https://doi.org/10.1145/263699.263712

**Establishes.** An untrusted producer can supply executable code plus a proof that the code satisfies a previously fixed safety policy; the host validates the proof before execution.

**Stops.** The paper is about admission of supplied code under a fixed policy, not an indefinitely rewriting lineage, induction over rewrite depth, or open-ended semantic growth.

**Subsumes target.** It subsumes the fixed-checker/proof-certificate pattern behind a single transition, but not the reachability theorem or opening limb.

### PA-04 — Morrisett, Walker, Crary, and Glew, “From System F to Typed Assembly Language” (1998)

**Verified record:** POPL 1998, pp. 85–97. DOI: https://doi.org/10.1145/268946.268954

**Establishes.** A type-preserving compilation path from System F to a typed RISC-like assembly language; well-typed low-level code preserves high-level abstractions and can serve as automatically produced proof-carrying code.

**Stops.** It proves type preservation across compilation transformations, not unbounded self-rewrite reachability or unbounded novelty.

**Subsumes target.** It is strong prior art for a decidable invariant and accepted nontrivial transformations, partially subsuming the mechanism of limb (A).

### PA-05 — Appel, “Foundational Proof-Carrying Code” (2001)

**Verified record:** Andrew W. Appel, LICS 2001, pp. 247–256. DOI: https://doi.org/10.1109/LICS.2001.932501

**Establishes.** Proof-carrying code can be reduced toward a small foundational trusted base rather than trusting a large verification-condition generator or type system implementation.

**Stops.** It minimizes and clarifies the checker’s foundation; it does not make the foundation mutable, prove open-ended reachability, or eliminate the need to trust a kernel.

**Subsumes target.** It directly informs `K` and the trusted-computing-base claim, but not limb (B).

### PA-06 — Cai, Shao, and Vaynberg, “Certified Self-Modifying Code” (2007)

**Verified record:** Hongxu Cai, Zhong Shao, Alexander Vaynberg, PLDI 2007, pp. 66–77. DOI: https://doi.org/10.1145/1250734.1250743

**Establishes.** A mechanized framework for modular verification of programs that load, generate, or mutate code at runtime, with the soundness result implemented in Coq. This is direct proof-oriented prior art for self-modifying machine code.

**Stops.** The contribution is sound reasoning about self-modifying behavior under its program logic and machine model. It does not prove that accepted rewrites generate an unbounded semantic-complexity hierarchy, nor does it offer a generally accepted open-endedness criterion.

**Subsumes target.** It substantially subsumes the broad novelty claim for limb (A). Any new construction must distinguish itself through the exact inductive reachability theorem, a particularly small checker/model, or limb (B)—not merely by saying “self-modifying code carries proofs.”

### PA-07 — Leroy and the CompCert development

**Verified records:** CompCert project documentation and theorem source: https://compcert.org/ ; semantic-preservation theorem documentation: https://compcert.org/man/manual001.html ; current proof source: https://compcert.org/doc/html/compcert.driver.Compiler.html

**Establishes.** A realistic optimizing compiler machine-checked in Coq/Rocq, with semantic-preservation theorems connecting source and generated assembly behavior.

**Stops.** Certified compilation preserves the semantics of a compilation input. It does not by itself define a mutable lineage, a proof-carrying rewrite gate, or unbounded opening.

**Subsumes target.** It supplies mature precedent for semantic preservation and a fixed proof kernel, partially subsuming closure engineering but not the target conjunction.

## 5. Reflective and self-improving agents

### PA-08 — Schmidhuber, “Gödel Machines” (2003; revised 2006)

**Verified record:** Jürgen Schmidhuber, arXiv:cs/0309048, https://arxiv.org/abs/cs/0309048 ; author-maintained version: https://people.idsia.ch/~juergen/goedelmachine.html

**Establishes.** A theoretical self-referential agent whose initial axioms describe its hardware, utility, environment assumptions, and software; it performs a rewrite after finding a proof that executing the rewrite is preferable to continuing proof search.

**Stops.** The usefulness proof is relative to supplied axioms and utility, and the practical search for strong usefulness proofs is the bottleneck. The construction is not a demonstration of sustained empirical open-ended improvement. The literature checked contains related implementation-oriented and approximate systems, so the categorical statement “nobody built one” is too strong; the defensible statement is that no source located a full, general implementation realizing the paper’s ideal guarantee at practical scale.

**Subsumes target.** It is broader than the proposed toy model in rewrite ambition, but it does not provide the requested fixed-kernel invariant-closure plus non-gameable unbounded-opening theorem.

### PA-09 — Yudkowsky and Herreshoff, “Tiling Agents for Self-Modifying AI, and the Löbian Obstacle” (2013)

**Verified record:** listed and linked by MIRI’s research guide: https://intelligence.org/research-guide/ ; bibliographic confirmation: https://intelligence.org/stanford-talk/

**Establishes.** Formal toy settings for agents attempting to trust successors that reason similarly, exposing Löbian obstacles and partial workarounds such as strength hierarchies or restricted trust.

**Stops.** The line does not yield unrestricted self-trust or a complete real-world design. MIRI’s own guide describes the relevant approaches as partial and sometimes unsatisfactory.

**Subsumes target.** It applies when the current agent must reason about a successor reasoner’s reliability. A fixed external kernel checking a restricted certificate avoids much of this exact setup, but only by making the kernel part of the immutable trusted base.

### PA-10 — Fallenstein and Soares, “Vingean Reflection: Reliable Reasoning for Self-Improving Agents” (2015)

**Verified record:** MIRI technical-report release and abstract: https://intelligence.org/2015/01/15/new-report-vingean-reflection-reliable-reasoning-self-improving-agents/

**Establishes.** A research framing for how a weaker current agent could reason abstractly and reliably about smarter successors it cannot predict in detail.

**Stops.** It surveys and frames formal proof-based approaches rather than delivering a general solved architecture for self-improvement.

**Subsumes target.** It identifies a harder successor-reasoning problem than the final toy theorem addresses. The toy theorem can deliberately avoid Vingean reflection by using a fixed relation and kernel.

### PA-11 — Fallenstein, Taylor, and Christiano, “Reflective Oracles” (2015)

**Verified record:** arXiv:1508.04145, https://arxiv.org/abs/1508.04145

**Establishes.** Reflective oracles can answer questions about oracle machines with access to the same oracle while avoiding diagonal contradiction through randomized answers on problematic queries; they support a foundation for classical game-theoretic agents.

**Stops.** Randomized reflective-oracle consistency is not a proof-carrying invariant gate and does not show safety closure across program mutation.

**Subsumes target.** Neither limb; it is an alternative response to self-reference in a different formal setting.

### PA-12 — Garrabrant et al., “Logical Induction” (2016)

**Verified record:** arXiv:1609.03543, https://arxiv.org/abs/1609.03543

**Establishes.** A computable process assigning and refining probabilities over logical sentences, satisfying broad coherence and self-reference desiderata despite bounded computation.

**Stops.** It produces calibrated beliefs rather than deductive certificates of invariant preservation, and it does not define an open-ended rewrite relation.

**Subsumes target.** Neither limb directly; it addresses uncertainty when proofs are unavailable or delayed.

### PA-13 — Taylor, “Quantilizers” (2016)

**Verified record:** AAAI author record and MIRI release: https://ocs.aaai.org/ocs/index.php/HCOMP/index/search/authors/view?affiliation=Machine+Intelligence+Research+Institute&country=US&firstName=Jessica&lastName=Taylor&middleName= ; https://intelligence.org/2015/11/29/new-paper-quantilizers/

**Establishes.** A bounded-optimization alternative that samples from a high-performing quantile under a reference distribution, intended to reduce extreme Goodharted strategies.

**Stops.** The guarantee depends strongly on the reference distribution and has known limitations in repeated settings. It is not an inductive self-modification proof.

**Subsumes target.** Neither limb; it is relevant to adversarial evaluation of any complexity or utility measure used for opening.

### PA-14 — Zhang et al., “Darwin Gödel Machine” (2025)

**Verified record:** arXiv:2505.22954, https://arxiv.org/abs/2505.22954

**Establishes.** An empirical system that edits its own coding-agent code, keeps an archive/tree of variants, and validates changes on coding benchmarks; the paper reports substantial benchmark improvements under sandboxing and human oversight.

**Stops.** The admission criterion is empirical benchmark performance, not a formal proof of an invariant over every reachable state. Its experiments are finite, and benchmark progress is not a proof of unbounded open-endedness.

**Subsumes target.** It operationalizes mutable search and lineage exploration, but neither machine-checks limb (A) nor proves limb (B).

### PA-15 — Wang et al., “Huxley-Gödel Machine” (2025; ICLR 2026)

**Verified records:** arXiv:2510.21614, https://arxiv.org/abs/2510.21614 ; ICLR 2026 record: https://iclr.cc/virtual/2026/poster/10009359

**Establishes.** The paper identifies a **Metaproductivity–Performance Mismatch**: a node’s present benchmark performance can be a poor proxy for its descendants’ improvement potential. It proposes a clade-level metric and search method.

**Stops.** The descendant metric remains empirical and benchmark-relative. It does not prove invariant closure or open-endedness, and its “true” clade quantity is not generally available during search.

**Subsumes target.** It directly strengthens the adversary’s measure-gaming/Goodhart objection to limb (B), but proves neither limb.

### PA-16 — Iacob et al., “The Red Queen Gödel Machine” (2026 preprint)

**Verified record:** arXiv:2606.26294, https://arxiv.org/abs/2606.26294

**Establishes.** A recent framework that co-evolves agents and evaluators under controlled utility changes, explicitly criticizing the stationary-evaluator assumption in self-improvement systems.

**Stops.** Guarantees are scoped per epoch/objective, and the work is an empirical preprint rather than a fixed-invariant closure theorem. Evolving the evaluator also abandons the proposed experiment’s immutable-`K` premise.

**Subsumes target.** It exposes the cost of a fixed checker/measure: an immutable evaluator may become the ceiling or target of optimization. It does not subsume the formal target.

## 6. Self-reproduction and open-ended evolution

### PA-17 — von Neumann, *Theory of Self-Reproducing Automata* (lectures 1948–49; edited 1966)

**Verified record:** John von Neumann, edited by Arthur W. Burks, University of Illinois Press, 1966. Stable catalog record: https://search.worldcat.org/title/theory-of-self-reproducing-automata/oclc/263608

**Establishes.** A universal-constructor architecture separating description, construction, copying, and control, demonstrating how an automaton can construct automata at least as complex as itself.

**Stops.** Universal construction and self-reproduction do not by themselves produce an evolutionary process with indefinitely increasing complexity. The unfinished theory did not deliver the sought detailed mechanism for evolutionary growth of complexity.

**Subsumes target.** It motivates the opening question but proves neither a proof-carrying safety gate nor unbounded evolutionary novelty.

### PA-18 — McMullin, “John von Neumann and the Evolutionary Growth of Complexity” (2000)

**Verified record:** Barry McMullin, *Artificial Life* 6(4), 347–361. DOI: https://doi.org/10.1162/106454600300103674

**Establishes.** A historical and conceptual reconstruction of von Neumann’s larger aim: not merely self-reproduction, but the possibility of descendants more complex than their ancestors.

**Stops.** It does not supply a completed formal criterion or a machine-checked construction satisfying that criterion.

**Subsumes target.** It supports the legitimacy of the opening-side research question, not the theorem.

### PA-19 — Bedau et al., “Open Problems in Artificial Life” (2000)

**Verified record:** *Artificial Life* 6(4), 363–376. DOI: https://doi.org/10.1162/106454600300103683

**Establishes.** A widely cited list of fourteen grand challenges in artificial life, including how life generates radical novelty and how evolutionary transitions increase complexity.

**Stops.** It is a challenge list, not a theorem or consensus definition. Its 2000 publication date alone cannot establish that every listed problem remains unsolved today.

**Subsumes target.** It establishes historical prominence. Later literature below is required to support continued uncertainty about definitions and measures.

### PA-20 — Taylor et al., “Open-Ended Evolution: Perspectives from the OEE Workshop in York” (2016)

**Verified record:** *Artificial Life* 22(3), 408–423. DOI: https://doi.org/10.1162/ARTL_A_00210

**Establishes.** The field distinguishes observable hallmarks from mechanisms, endorses pluralism about kinds of open-ended evolution, and reports little agreement on precise definitions and measures. It explicitly separates quantitatively new adaptations within a predetermined class from qualitatively new adaptations outside such a class.

**Stops.** It provides a research map and operational questions, not a single accepted mathematical criterion.

**Subsumes target.** It shows why proving one unbounded scalar does not automatically settle von-Neumann-style opening.

### PA-21 — Bedau, Snyder, and Packard, “A Classification of Long-Term Evolutionary Dynamics” (1998)

**Verified record:** *Artificial Life VI*, pp. 228–237. Author abstract: https://people.reed.edu/~mab/papers/alife6.ab.htm

**Establishes.** Empirical evolutionary-activity statistics distinguishing absent, bounded, and unbounded adaptive activity, with comparisons among artificial systems, neutral shadows, and the fossil record.

**Stops.** The classification depends on chosen components, statistics, and empirical extrapolation. It is not a proof that an arbitrary reachable set has unbounded qualitative complexity.

**Subsumes target.** It offers candidate diagnostics, not a theorem suitable for the requested exact limb (B).

### PA-22 — Standish, “Open-Ended Artificial Evolution” (2003)

**Verified record:** arXiv:nlin/0210027, https://arxiv.org/abs/nlin/0210027 ; journal DOI: https://doi.org/10.1142/S1469026803000914

**Establishes.** In a size-neutral Tierra run, organism size increased without measured organismal complexity increasing.

**Stops.** The result is system- and metric-specific, not a universal impossibility theorem.

**Subsumes target.** It kills raw AST length or code size as an adequate opening measure.

### PA-23 — Lehman and Stanley, “Abandoning Objectives: Evolution Through the Search for Novelty Alone” (2011)

**Verified record:** *Evolutionary Computation* 19(2), 189–223. DOI: https://doi.org/10.1162/EVCO_a_00025

**Establishes.** Novelty search can outperform direct objective optimization in deceptive domains by rewarding behavioral novelty rather than proximity to a fixed objective.

**Stops.** Novelty is relative to a behavior characterization and archive; finite experimental success is not proof of indefinite complexity growth or safety preservation.

**Subsumes target.** It informs candidate opening mechanisms but not either formal limb.

### PA-24 — Chaitin, metabiology / *Proving Darwin* (2012–2013)

**Verified records:** Gregory Chaitin, *Proving Darwin: Making Biology Mathematical*, Pantheon/Vintage, 2012/2013, publisher record: https://www.penguinrandomhouse.com/books/25805/proving-darwin-by-gregory-chaitin/ ; “Life as Evolving Software,” DOI: https://doi.org/10.1142/9789814374309_0015

**Establishes.** A mathematical toy metabiology in which mutating software evolves toward larger fitness values, connecting algorithmic information theory, mutation, and open-ended mathematical growth.

**Stops.** Its organisms, mutation operators, and fitness are highly idealized; the model does not provide a generally accepted biological or ALife criterion of qualitative open-endedness. Radosław Siedliński’s peer-reviewed critique argues that genocentric reductionism and biological oversimplification prevent it from serving as a proper model of Darwinian evolution (DOI: https://doi.org/10.1515/slgr-2016-0059).

**Subsumes target.** It supplies a formal unbounded-growth motif, but not invariant-preserving proof-carrying self-modification under a fixed kernel.

### PA-25 — Wang et al., “POET” (2019)

**Verified record:** arXiv:1901.01753, https://arxiv.org/abs/1901.01753

**Establishes.** Co-generation of environments and agents, with transfer of solutions among environments, can produce diverse stepping stones and solve challenges inaccessible to direct optimization controls.

**Stops.** The experiments run in bounded domains for finite time. “Endlessly” names an aspiration/potential, not a proof of mathematical unboundedness.

**Subsumes target.** It is empirical opening prior art and highlights environmental coevolution, but has no closure theorem.

### PA-26 — Dolson et al., “The MODES Toolbox” (2019)

**Verified record:** *Artificial Life* 25(1), 50–73. DOI: https://doi.org/10.1162/artl_a_00280

**Establishes.** Operational metrics for change, novelty, complexity, and ecological potential, intended for comparable empirical diagnosis across evolutionary systems.

**Stops.** The authors present a toolbox of hallmarks, not a universal definition; they note continuing debate over whether open-endedness is quantifiable and that systems may score as open-ended without matching the intended phenomenon.

**Subsumes target.** It provides adversarial checks and empirical diagnostics but no exact theorem for limb (B).

### PA-27 — Hintze, “Open-Endedness for the Sake of Open-Endedness” (2019)

**Verified record:** *Artificial Life* 25(2), 198–206. DOI: https://doi.org/10.1162/artl_a_00289

**Establishes.** A simple model can satisfy published open-endedness requirements and exhibit increasing compression-based complexity/diversity while remaining intuitively disappointing. The paper concludes that definitions of complexity and diversity are more decisive than mere indefinite continuation.

**Stops.** It is a counterexample to sufficiency of criteria, not a proof that no robust criterion can exist.

**Subsumes target.** It is the most direct prior-art warrant for the campaign’s measure-gaming attack. Any scalar limb (B) must be interpreted narrowly and cannot be equated with full qualitative novelty without more structure.

### PA-28 — Sayama and Nehaniv, “Self-Reproduction and Evolution in Cellular Automata: 25 Years After Evoloops” (2025 issue)

**Verified record:** *Artificial Life* 31(1), 81–95. DOI: https://doi.org/10.1162/artl_a_00451

**Establishes.** A current review of constructive self-reproduction and Darwinian evolution in cellular automata, including achievements, remaining challenges, and renewed interest in open-ended evolution.

**Stops.** The reviewed systems establish reproduction/evolutionary possibility, not a universally accepted formal criterion for indefinitely increasing qualitative complexity.

**Subsumes target.** It confirms that self-reproduction and evolutionary variation are distinct from resolving the opening criterion.

## 7. Synthesis against the target theorem

### Limb (A): closure

The broad mechanism is established prior art. A fixed kernel validating proofs or typing derivations can enforce a chosen safety policy over admitted code. Mechanized reasoning about runtime self-modification exists. What remains legitimate for a small Lean development is an exact, inspectable theorem for one deliberately restricted rewrite relation:

`∀ n s, Reach n s → I s`.

That theorem can be useful as a crisp model, but it must not be advertised as solving unrestricted safe self-modification, defeating Löb generally, or defeating Rice generally.

### Limb (B): opening

No generally accepted criterion was found. The literature distinguishes at least:

- syntactic size;
- support/cardinality or state-space occupancy;
- compressibility/algorithmic complexity approximations;
- behavioral novelty relative to an archive;
- adaptive evolutionary activity;
- ecological complexity;
- major transitions and emergence of new levels;
- quantitative novelty within a predefined ontology;
- qualitative novelty that changes the ontology or meta-model.

A Lean theorem can prove unboundedness only for a specifically defined measure. It cannot silently promote that measure into “genuine novelty.” The least gameable measure available for the proposed truth-table toy language is **semantic support cardinality**: the number of observable inputs on which the program returns `true`. It is invariant under false padding and changes only when the observable function’s support grows. Nevertheless, it remains quantitative novelty in a fixed coordinate ontology and does not capture emergent new predicates, new interaction levels, or new semantics.

### Joint target

The exact small-model conjunction appears machine-adjudicable and likely constructible:

1. `K` is fixed and checks a decidable admissibility proposition.
2. An accepted step preserves `I` and leaves the kernel identity unchanged.
3. `Reach n` is indexed by arbitrary `n`; induction proves closure.
4. An explicit accepted lineage has semantic-support complexity `n` at depth `n`.

This would prove an exact toy theorem. It would **not** settle the scientific open problem of evolutionary growth of qualitative complexity. The likely category error is that the closure invariant and the opening measure can be made nearly orthogonal: protecting one coordinate while activating endlessly many fresh coordinates proves coexistence by construction, not endogenous evolution of novelty.

## 8. Phase-0 ruling

**The exact target theorem was not found already proved. Construction may proceed.**

The construction must carry these prior-art constraints into its claim boundary:

- Cite Certified Self-Modifying Code as the nearest direct closure predecessor.
- State that the trusted kernel is shifted/fixed, not eliminated.
- State that Rice is avoided only by restriction of the object language/relation.
- Reject code length as an opening measure.
- Name semantic-support unboundedness as quantitative opening in a fixed ontology.
- Label any claim of qualitative novelty or von-Neumann-style evolutionary complexity as `CONJECTURE` or out of scope.

## 9. Citation validation register

Every entry below was resolved in a publisher page, scholarly index, official project page, or arXiv record during Phase 0. The URLs above are the stable identifiers used in the artifact.

| ID | Work | Verified identifier/index |
|---|---|---|
| PA-01 | Löb 1955 | DOI 10.2307/2266895; Cambridge Core |
| PA-02 | Rice 1953 | DOI 10.2307/1990888; Transactions AMS record/index |
| PA-03 | Necula 1997 | DOI 10.1145/263699.263712; ACM Digital Library |
| PA-04 | Morrisett et al. 1998 | DOI 10.1145/268946.268954; ACM Digital Library/Cornell |
| PA-05 | Appel 2001 | DOI 10.1109/LICS.2001.932501; DBLP/IEEE metadata |
| PA-06 | Cai et al. 2007 | DOI 10.1145/1250734.1250743; ACM Digital Library/DBLP |
| PA-07 | CompCert | Official CompCert manual and generated proof documentation |
| PA-08 | Gödel Machine | arXiv:cs/0309048; author-maintained IDSIA page |
| PA-09 | Tiling Agents | MIRI research guide and bibliography |
| PA-10 | Vingean Reflection | MIRI technical-report release |
| PA-11 | Reflective Oracles | arXiv:1508.04145 |
| PA-12 | Logical Induction | arXiv:1609.03543 |
| PA-13 | Quantilizers | AAAI author record; MIRI paper release |
| PA-14 | Darwin Gödel Machine | arXiv:2505.22954 |
| PA-15 | Huxley-Gödel Machine | arXiv:2510.21614; ICLR 2026 poster record |
| PA-16 | Red Queen Gödel Machine | arXiv:2606.26294 |
| PA-17 | von Neumann/Burks 1966 | WorldCat catalog record |
| PA-18 | McMullin 2000 | DOI 10.1162/106454600300103674; PubMed |
| PA-19 | Bedau et al. 2000 | DOI 10.1162/106454600300103683; PubMed/Caltech |
| PA-20 | Taylor et al. 2016 | DOI 10.1162/ARTL_A_00210; MIT Press |
| PA-21 | Bedau et al. 1998 | Author/research-institution abstract and proceedings metadata |
| PA-22 | Standish 2003 | arXiv:nlin/0210027; DOI 10.1142/S1469026803000914 |
| PA-23 | Lehman & Stanley 2011 | DOI 10.1162/EVCO_a_00025; MIT Press references |
| PA-24 | Chaitin 2012/2013 | Publisher record; DOI 10.1142/9789814374309_0015 |
| PA-25 | POET | arXiv:1901.01753 |
| PA-26 | MODES | DOI 10.1162/artl_a_00280; MIT Press |
| PA-27 | Hintze 2019 | DOI 10.1162/artl_a_00289; MIT Press |
| PA-28 | Sayama & Nehaniv 2025 | DOI 10.1162/artl_a_00451; MIT Press/PubMed |

## 10. Iterations 5–6 supersession addendum

This addendum supersedes the Phase-0 construction recommendation where it proposed a Boolean truth table and semantic-support cardinality as the cheapest adequate opening model. That recommendation was useful only as a falsifiable first construction. Iteration 4 showed that the truth-table model separated protected and free coordinates, while Iteration 5 replaced it with a total function language and a mutable AST-rewrite operator.

The Iteration 5 range-based anti-generator condition is also withdrawn. For any effectively checkable finite-path transition system, a fixed certificate-replay interpreter can enumerate every reachable state when its input may carry an arbitrary finite path. This is a negative result about a naive open-endedness criterion, not an impossibility theorem for open-ended evolution.

Iteration 6 isolates the descriptive-complexity consequence at the correct abstraction level. Relative to an explicit object language with a shortest-code function and a fixed composition interpreter, every closed deterministic lineage satisfies:

`K(sₙ) ≤ K(s₀) + K(step) + K(n) + O(1)`.

The mechanized natural-number description uses the self-delimiting length

`bitLength(n) + 2 · bitLength(bitLength(n)) + 1`,

which has the intended `log n + 2 log log n + O(1)` shape. A pure counter attains the same depth-description term while carrying no qualitative novelty. Descriptive complexity at the closed-system ceiling therefore does not distinguish novelty from counting.

Iteration 6 takes the open-system exit. When a lineage consumes an externally supplied input description, the corresponding checked bound is:

`K(s) ≤ K(seed) + K(step) + K(consumed input) + O(1)`.

A separate induction proves invariant preservation across the consumed inputs. The two obligations are independent: the fixed checker constrains what transformations are admitted and how information is processed; it does not determine whether information arrives. This formal separation aligns with the open-ended-evolution literature’s emphasis on environmental and ecological interaction without claiming that the present toy model captures biological evolution.

Surface 8 also lands on the Iteration 5 parity model. Although a successor growth operator increases the shared semantic coordinate, violates the invariant, and is rejected before installation, the constant-description rewrite `.wrapDouble` is reachable from the actual initial state and increases the chosen complexity forever while preserving parity. The formal no-product-decomposition theorem is sound, but the coupling is not load-bearing.

The structural alternative remains open: organizational levels, new observables outside the seed ontology, or growth in the minimum ontology required to describe behavior have not been formalized here. No claim is made that the development defines universal Kolmogorov complexity, proves a biological open-endedness theorem, or resolves von-Neumann-style qualitative novelty. The legitimate result is a crisp open/closed fork and a machine-checked warning against several naive scalar criteria.
