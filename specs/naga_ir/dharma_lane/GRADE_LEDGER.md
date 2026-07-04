# Grade Ledger

Every claim in `DHARMA_GATING.md` must appear here with all three columns filled. Rows with any empty column are drift and must be either upgraded or removed.

Format: `| Section | Claim | Math structure | Predicate | Consequence | Citation |`

| Section | Claim | Math structure | Predicate | Consequence | Citation |
|---|---|---|---|---|---|
| §0 | System evolves toward a fixed point of coherent receipts | Vector-valued Lyapunov function \(V: \Sigma \to \mathbb{R}_{\geq 0}^4\) with componentwise product order | `telos_lyapunov(state) -> (V_coh, V_unres, V_drift, V_auth)` | Increase in \(V\) without supersession receipt blocks commit; emits `dharma.divergence.v1` | Khalil 2002; Goebel-Sanfelice-Teel 2012 |
| §1 | A receipt has no independent existence (dependent origination) | Free category \(\mathcal{R}\) with content-addressed objects and typed prev_hash morphisms | `receipt_identity(r) == sha256_uri(jcs(r.content ‖ sort(r.prev_hashes) ‖ r.trust_base_id))` | Cross-agent belief propagation always explicit and graph-visible; no receipt copying | Mac Lane 1998; Merkle 1987; Priest 2018 |
| §2 T4 | Trust is a conserved quantity under re-parenting symmetry | Non-functoriality of \(\mathrm{Auth}: \mathcal{R} \to T\) under re-parenting; coercion receipt required as connecting morphism | `is_authority_preserving(r_before, r_after)` | Ingest rejects mis-parented receipts regardless of producer intent | Noether 1918 |
| §2 T8 | Modality strengthening requires paying entropy cost | Total order on modality set \(M\); transition legal iff coercion receipt of matching or greater strength exists in predecessor set | `is_modality_legal(chain)` | Verifier rejects modality upgrade without coercion receipt | Lieb-Yngvason 1999 |
| §2 T5a/T5b | Hash is gauge-invariant under representation, symmetry-breaking under content | JCS equivalence class \([r]_{\text{JCS}}\); hash defined on class | `hash(jcs(r)) == hash(jcs(permute(r)))` and `!= hash(jcs(mutate(r)))` | Producer cannot gain advantage from representation choice | RFC 8785 |
| §3 | Canonicalization is four-valued (tetralemma) | Belnap four-valued lattice with (evidence-for, evidence-against) pairs | `canonicalize_belnap(r, budget) -> Belnap4` | `both`-valued receipts routed to contradiction reconciler with witnesses recorded | Belnap 1977; Priest 2008 |
| §4 | Mesh is a decoherence process; merges do not commute in general | Density-matrix-analog belief operators \(\rho_n\); projection postulate; non-commuting projectors | `belief_state(node, seq)`, `commutator_norm(P_A, P_B)` | Reconciler emits `dharma.noncommuting_merge.v1` recording both branches and commutator norm | von Neumann 1932; Nielsen-Chuang 2010; Aerts 2009 (analogy only) |
| §5 AB-01 | Substance identity requires time-translation symmetry | Noether symmetry of record class fields under time evolution | `has_time_translation_symmetry(cls) := all(f.frozen for f in fields(cls))` | Records declared as substances must be 100% frozen; otherwise must be re-declared as processes | Noether 1918 |
| §5 AB-02 | Exception swallow is destruction of causal information | Non-unitarity of silent exception handlers in the causal graph | `has_receipt_trail(handler)` | 0 undocumented absorptions; documented absorptions carry justification receipts | — (structural, no external citation) |
| §5 AB-03 | Cross-boundary interactions must be mediated | Locality principle on module import graph | Every cross-boundary edge carries `mediator_receipt` | Verifier rejects direct cross-boundary edges without mediator | — (structural) |
| §5 AB-04/05 | Certain violations have zero amplitude, not small amplitude | Boolean gates with no gradient — selection rules | AST match for `eval`, `exec`, dynamic imports in TCB scope | Zero-tolerance; any occurrence fails the run | — (structural; Vinaya pārājika is analogical, not load-bearing) |
| §6 | PR arc is forced by dependency graph of invariants | Topological sort of invariant-dependency DAG | Static check that each PR's invariants reference only prior-PR quantities | Reordering PRs produces undefined-reference errors in the invariant chain | — (internal derivation) |
| §7 | Document must survive adversarial reader who is both physicist and Madhyamaka scholar | Grade-check function over document sections | Mechanical audit of this ledger for missing columns | Any row with empty column blocks doc-lane commit until upgraded | — (self-referential meta-check) |

## Audit rules

R1. Adding a section to `DHARMA_GATING.md` requires adding a row here in the same commit.

R2. A row with fewer than three of {math, predicate, consequence} filled is a violation. The section it references must be either upgraded or removed.

R3. Citations in the last column are optional for structural / internal claims. They are mandatory for any claim invoking a named result from physics or philosophy.

R4. The audit itself is a receipt-emitting process. A future PR will implement `grade_audit.py` that reads both files, checks the correspondence, and emits `dharma.grade_audit.v1` receipts. Until then, the audit is manual and this file is the ledger.

R5. This file has L1..L8 from `DHARMA_GATING.md` §8 as its own binding constraints. It is a companion to that document, not an alternative surface.
