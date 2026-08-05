# Decorrelated review: ten-node autocatalytic A2A portfolio, stabilized pass

RESPONSE PROTOCOL (mandatory): reason silently, then emit one minified JSON
object of at most 2,000 characters. Do not restate the task. Do not expose
analysis. Keep `summary` under 240 characters, `evidence_checked` to at most
eight short strings, and use `[]` for empty arrays. The first byte must be `{`
and the last byte must be `}`.
If `score` is below 100, every deduction must identify a concrete blocker or
required change that is supported by the attached evidence. Do not deduct for
an unstated preference or for production/external authority this local packet
explicitly does not claim.
If `blockers`, `required_changes`, and `explicit_disagreement` are all empty,
`score` must be 100; a lower score would violate this response protocol.

Review the attached implementation as a skeptical architecture, epistemics,
safety, integration, and operability critic. The user asked to connect the ten
most load-bearing mechanisms/projects into an A2A autocatalytic system and give
every node its own page.

The claim is deliberately narrower than “the production organism is live”:

- this is the metabolism of every currently ACTIVE governance track; the ten
  node boundaries are justified independently by distinct adapters, typed
  producer/consumer contracts, proof references, and authority ceilings;
- the manifest declares and validates a closed ten-node signal ring plus three
  typed cross-feeds; all three are exercised across a two-turn run;
- every node runs a project-specific read-only adapter and emits a typed signal
  envelope whose positive-named port is qualified by an evidence-backed state;
- the current states are intentionally non-promoting: historical fixture,
  planned-not-accepted, rehearsal-without-domain-execution, observed gaps,
  candidate-not-selected, blocked-no-proposal, not-verified,
  authorization-not-observed, external-gate-closed, and promotion-blocked;
- adapter evidence is content-addressed and source-kind aware; structured JSON
  rejects duplicate keys, wrong schemas/types, and invalid required digests,
  while JSONL and raw UTF-8 sources remain explicit distinct contracts;
- every cross-feed is consumed before the target adapter, resolves to exactly
  one prior evidence-ledger row, matches source/target/signal/hash/state/
  modality/turn, is removed one-shot, and perturbs the target evidence hash;
- the verifier re-invokes the same consume -> adapter -> emit implementation,
  which detects source drift and witness tampering but is not implementation
  diversity and cannot rule out common-mode semantic bugs;
- each node declares an exact ordered set of code-owned promotion predicates;
  missing, extra, reordered, unknown, or non-boolean predicates fail closed;
- predicate evaluations are content-addressed inside project evidence, yet an
  all-true evaluation remains `blocked`, carries
  `authority_upgrade_authorized=false`, and requires a new authority-bearing
  evaluator plus a separately reviewed work packet;
- `TransportAck` cannot inhabit `StructuralHop`;
- `StructuralHop` and `StructuralCycleProof` prove semantic/causal/hash shape
  only and explicitly carry no execution authority;
- structural checking returns `StructuralCycleCheck(modality="structure_only")`;
- every task enters through canonical `submit_task_via_spine_sync`; the spine
  records 20 intent, 20 completion, and 20 idempotency-consumed rows;
- the public semantic receipt evaluator separately checks exactly 20 A2A rows,
  20 semantic rows, and one cycle row and returns
  `LocalReceiptConsistencyCheck(modality="local_mutable_runtime_receipt_consistency",
  independently_authenticated=false)`;
- a locally writable SQLite store is explicitly forgeable by a local operator,
  so local receipt consistency is never described or rendered as authenticated
  execution provenance;
- the verifier fingerprint byte-frames and hashes all four implementation
  modules once at import, preventing a running old evaluator from stamping
  replacement on-disk bytes as its own;
- latest-witness alias loading preserves the attested cycle path and the
  returned API witness must reverify unchanged;
- the strongest result is `local_rehearsal`; independent peers, live provider
  semantics, JetStream domain completion, authenticated provenance,
  publication, revenue, production liveness, and external effects are not
  proven;
- `/dashboard/organism` and `/dashboard/organism/[nodeId]` fail closed on the
  backend topology contract and render adapter evidence only for a fully
  recomputed locally receipt-consistent witness.

Hardening evidence before this council:

- portfolio snapshot: 10 nodes, 13 edges, one SCC, one autocatalytic set,
  contract valid, zero validation errors;
- Python work-packet gate: 198 passed, one third-party deprecation warning;
- focused adversarial matrix: 20/20 passed; complete portfolio module: 45/45;
- dashboard contract assertions: 10 passed;
- focused Ruff and ESLint: clean;
- Next production build: overview and dynamic node routes compiled;
- mounted FastAPI TestClient response-contract test passes;
- the complete staged pre-commit suite passes: test hygiene, contract tests,
  uplift/forge/docops/hygiene/manifest guards, gitleaks, Semgrep, and syntax;
- adversarial review proved that raw SQL can forge local mutable receipt rows;
  the implementation now represents that as a bounded consistency modality
  instead of claiming independent authority;
- typed-gate adversarial cases cover manifest drift, non-boolean inputs, forged
  gate authority, and the all-true-still-non-authorizing invariant;
- alternate-root integration proves the manifest-declared `DHARMA_STATE_DIR`
  override wins over legacy `DHARMA_HOME`, and a default two-turn run plus
  reload keeps both witness files and `state/runtime.db` under one resolved root;
- fresh cycle `autocat_682808db6cbc4d50` reloads in a fresh process with structural
  and local-consistency checks valid; witness SHA-256 is
  `bc5b2e3752349fee00cb1077f6a9c5bb7a05fb060f0907148aa49768d6970de2`;
- its 20 project-evidence rows contain 20 unsatisfied promotion gates and zero
  authority upgrades; its four-module implementation fingerprint is
  `ef857d247921d142f27ceeccc1ae1f40fe91c35531be3b27e735b99fe200a5c3`;
- the persistent `palantir-pilot` witness must be running with a heartbeat
  younger than the council threshold;
- a requested model lane counts only when `actual_model` matches its required
  decorrelated family; a Kimi substitution does not satisfy the Qwen lane.

Prior blocker dispositions for this exact tree:

- trusted CI is a post-commit, exact-SHA authenticity gate and will run after
  this packet is committed and pushed; this local council is not asked to grant
  merge authority and must not treat absent pre-commit CI as an internal code
  defect;
- the persistent worker is a companion liveness witness, not a precondition for
  portfolio semantic correctness, and the council runner independently captures
  its raw heartbeat plus JetStream consumer state rather than trusting the
  checked-in summary;
- prose `proof_obligations` remain human-readable statements, while the exact
  executable layer is `PROMOTION_CHECKS_BY_NODE`, strict-boolean
  `evaluate_promotion_gate`, manifest equality validation, content-addressed
  adapter evidence, replay rejection, and dashboard rendering;
- shared adapter replay is explicitly documented as drift/tamper detection, not
  independent semantic implementation; a separate evaluator is required before
  any authority above `local_rehearsal` and is deliberately not fabricated in
  this non-authorizing packet.

Audit for concrete blockers, especially:

1. whether each node does substantive project-specific read-only work rather
   than relabeling a track or echoing a transform string;
2. whether active-track equality, ring ports, pages, cross-feed declarations,
   and edge topology are enforced at runtime rather than only in tests;
3. whether positive port names plus negative signal states remain impossible
   to promote through self-authored hashes, task completion, transport ACK, or
   model consensus;
4. whether structure-only and local mutable-receipt consistency are distinct
   result types with no public authority-erasing switch;
5. whether any code or UI still overstates mutable local receipts as execution
   provenance, live A2A peers, domain completion, or external effects;
6. whether stale verifier/source evidence, altered aliases, missing/extra
   receipts, duplicate JSON keys, wrong schemas/types/digests, forged or stale
   cross-feeds, duplicate/gapped hops, or broken turn chains fail closed;
7. whether the API, overview, dynamic node page, docs, and manifest tell the
   same authority story;
8. whether this composes the canonical A2A server, runtime-truth submission
   spine, RuntimeStateStore, correlation context, Agent Cards, and
   CatalyticGraph rather than creating a rival execution substrate;
9. missing tests, unsafe writes, operational failure modes, or unchallengeable
   evidence claims.

Treat shared-implementation adapter replay as a stated limitation, not as an
independently implemented oracle. Require a separate evaluator before authority
above `local_rehearsal`; do not require that scope-expanding evaluator inside
this explicitly non-authorizing P1 rehearsal packet.

Do not require unauthorized publication or external effects as a local code
review gate. Do require an honest ceiling and an executable proof obligation
for every future authority promotion.

Return exactly one JSON object with:

- `verdict`: `pass`, `approve`, `revise`, `reject`, `blocked`, `failed`, or
  `insufficient_context`;
- `score`: integer 0-100;
- `summary`: concise result;
- `blockers`: concrete blockers only;
- `required_changes`: changes needed for 100/100;
- `evidence_checked`: paths, commands, or claims checked;
- `explicit_disagreement`: use exactly `""` when there is no disagreement;
  otherwise state the concrete disagreement.

Score dimensions: integration quality, evidence quality, anti-slop,
safety/governance, and operability. A high score requires challengeable
evidence, not rhetorical completeness.

Your first output character must be `{` and your last must be `}`. Do not emit
analysis, planning, commentary, or a Markdown fence before or after the object.
