# Language Womb Seed

Status: bootstrap seed, not a full language implementation.

Highest goal: grow a language where claims carry epistemic modality and
authority in their semantics, not merely in logs emitted after execution.
Runtime receipt emission is already available elsewhere in `dharma_swarm`; the
new language must eventually reject invalid epistemic dependencies at
typecheck/evaluation time.

Prior-art gate: before extending this seed, update `prior_art.md` and show why
the proposed construct is not already solved by LM orchestration frameworks,
proof assistants, type/effect systems, provenance systems, or probabilistic /
paraconsistent languages.

## Smallest Viable Grammar

There is one top-level syntactic form:

```text
receipt ::= "receipt" "{" claim modality predecessors trust_base "}"
```

The four required fields are:

```text
claim        ::= opaque-bytes | structured-claim
modality     ::= Proven_by | Tested_by | Attested_by | Assumed
predecessors ::= "[" receipt-hash* "]"
trust_base   ::= trust-base-id
```

At seed time, `claim` may be opaque bytes. A method can later attach a
structured claim schema. `trust_base` is a single fragment authority at seed
time, not yet a lattice element.

## Evaluation Rule

An emission is accepted by the seed evaluator iff:

```text
lyapunov(next_state) <= lyapunov(current_state)
or predecessors include a valid coercion receipt explaining the increase
```

The comparison is componentwise over the trust base's declared Lyapunov vector.
For `naga_ir_language_womb.fragment.v1`, the vector components are declared in
`naga_ir_language_womb/governance/trust_base.yaml`.

## Modality Floor

The bootstrap language cannot prove itself. The first program is therefore
`Attested_by`. Later typechecker/evaluator work may strengthen subsequent
programs, but not by silently rewriting the bootstrap modality.

## Extension Rule

Every extension proposal is itself a `receipt` program whose claim class is
`language_extension`. Adoption requires mesh-consensus receipts following the
policy in `specs/naga_ir/dharma_lane/COLLECTIVE_LANGUAGE_PROMPT.md`.

Confidence: 83/100. This seed is intentionally small and may be too permissive
around opaque `claim`; it is sufficient to host the bootstrap receipt without
pretending the full language exists.
