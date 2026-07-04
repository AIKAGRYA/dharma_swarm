# NĀGA Witness Mesh

Status: draft

Review target: PR #2 witness mesh

## Mesh role

The witness mesh records, merges, and expires receipt-state observations; it does not prove the underlying program correct by itself. [confidence: 94/100] The measured object is a set of receipt events keyed by `(subject_id, claim_hash, trust_base_id, fragment_id, fragment_version)`, and the threshold for mesh convergence is deterministic equality of canonical state after replicas have received the same event set. [confidence: 91/100] [Conflict-free Replicated Data Types](https://arxiv.org/abs/1805.06358)

## Event types

The mesh has six event types: `claim_seen`, `evidence_seen`, `challenge_opened`, `challenge_resolved`, `ttl_expired`, and `receipt_superseded`. [confidence: 90/100] A mesh implementation may add transport metadata, but these six events are the minimum needed to reconstruct bounded canonization state. [confidence: 88/100]

| Event | Measured object | Merge threshold | Confidence |
|---|---|---|---:|
| `claim_seen` | claim id and subject id | add-wins by receipt hash | 89/100 |
| `evidence_seen` | evidence record id | add-wins by evidence hash | 90/100 |
| `challenge_opened` | challenge receipt id | add-wins and blocks canonization | 94/100 |
| `challenge_resolved` | challenge resolution id | valid only when it names prior challenge | 92/100 |
| `ttl_expired` | receipt id and observed time | derived event, recomputable | 91/100 |
| `receipt_superseded` | old and new receipt ids | valid only with prev-hash link | 90/100 |

## Merge state

The normative merge state for PR #2 is a join-semilattice. [confidence: 90/100] The carrier is `MeshState = ORMap[AuthorityKey, EventSet]`; the partial order is subset inclusion by content-addressed event id per key; the join is deterministic union of event ids plus recomputation of resolution indexes as derived projections over the event set. [confidence: 90/100] [Conflict-free Replicated Data Types: An Overview](https://arxiv.org/abs/1806.10254)

```text
AuthorityKey = "sha256:" + SHA256(JCS({subject_id, claim_hash, trust_base_id, fragment_id, fragment_version}))
MeshState = ORMap[AuthorityKey, EventSet]
state_a <= state_b iff every key in state_a maps to an event-id subset in state_b
join(state_a, state_b) = deterministic_union_by_event_id(state_a, state_b)
canonical_mesh_projection?(state, receipt, current, t) =
  canonical?(receipt, state, current, t)
  and authority_key(receipt) == receipt.challenge_base.authority_key
```

The semilattice claim is limited to receipt-event convergence; it does not claim semantic convergence of programs. [confidence: 95/100]

## Challenge rule

`challenge_opened` is add-wins over `evidence_seen`: an unresolved challenge blocks canonization even when proof or test evidence is present. [confidence: 95/100] The threshold for unblocking is a `challenge_resolved` event whose resolver is authorized under the same trust base or a successor trust base with a checked refinement receipt. [confidence: 93/100] A receipt may cache `challenge_state`, but only a mesh query against `challenge_base` establishes absence of unresolved challenges. [confidence: 96/100]

Resolution states are exactly the wire set `open`, `refuted`, `accepted`, and `expired`; mesh projections may cache those states, but they may not introduce a fifth state without a schema-version bump. [confidence: 93/100]

## Resolver auth

A `challenge_resolved` event is admissible only when it names `resolver_id`, `resolver_role`, `resolver_signature`, `trust_base_id`, `policy_ref`, `challenge_receipt_id`, `resolution_kind`, and optional `refinement_receipt_id`. [confidence: 93/100] The threshold is a valid resolver signature plus a policy lookup showing that the resolver role can resolve the named challenge under the same trust base, or a `Proven_by` refinement receipt authorizing successor-trust-base resolution. [confidence: 92/100]

## Expiration rule

TTL expiration is computed from receipt fields and observation time, not from wall-clock mutation of stored events. [confidence: 93/100] A replica with `clock.clock_uncertainty_ms > clock.max_clock_skew_ms` must return `unknown` rather than `canonical`. [confidence: 92/100]

## Quorum rule

The core mesh does not require a fixed witness quorum. [confidence: 90/100] Product or governance profiles may require `distinct_witness_count >= n`, but the base canonization predicate only requires one admissible modality, no unresolved challenge, live TTL, matching trust base, valid signatures, and acceptable clock skew. [confidence: 93/100]

## Replay rule

Every `Witnessed_by` event must include either a replay hash, trace hash, or explicit non-replayable marker. [confidence: 91/100] Non-replayable witnesses can support incident history but cannot alone support canonical safety claims. [confidence: 93/100]

## Adversary rule

The adversary is a first-class participant, not an out-of-band reviewer. [confidence: 94/100] A valid adversarial challenge must carry a receipt, name the claim it attacks, and specify whether it refutes the claim, narrows the claim, expires the evidence, or contests the trust base. [confidence: 92/100]

## Non-normative bisim

Two finite mesh snapshots are authority-equivalent for a fixed challenge base and bounded horizon when every authority key yields the same `canonical_status` and the same unresolved challenge id set at every observation instant named by receipt TTL boundaries, challenge resolution times, and snapshot observation times inside that horizon. [confidence: 91/100] This is a non-normative target for future reconciliation work, not a proven bisimulation theorem; it is narrower than semantic equivalence of programs and does not import the evolution `bisimilar(...)` function as an implementation. [confidence: 96/100]

## Privacy rule

The privacy rule defines redaction limits: mesh events may carry redacted payloads, but redaction cannot remove the measured fields needed by the modality threshold. [confidence: 93/100] If a payload is private, the event must include a redaction policy, payload hash, and verifier-access statement; otherwise the event is historical but inadmissible for canonization. [confidence: 90/100]

## Failure states

The mesh must represent at least six failure states: `invalid_schema`, `signature_failed`, `ttl_stale`, `clock_skew_unknown`, `challenge_unresolved`, and `trust_base_mismatch`. [confidence: 94/100] Returning a generic failure for these cases is insufficient because each state requires a different repair path. [confidence: 91/100]

## Local mapping

Current repo integration is limited to spec compatibility. [confidence: 99/100] [dharma_swarm/coalgebra.py](../../dharma_swarm/coalgebra.py) can inform the later reconciler shape, but this PR #2 mesh spec does not claim a reconciler exists or that receipt events are already emitted in this checkout. [confidence: 98/100]
