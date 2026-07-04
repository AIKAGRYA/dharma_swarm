# Shadow Language Seed

Status: bootstrap seed, not a full language implementation.

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
For `dharma_lab.fragment.v1`, the vector components are declared in
`dharma_lab/governance/trust_base.yaml`.

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
