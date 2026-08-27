---
title: Ten-Node Autocatalytic Portfolio
doc_type: architecture
status: active_reference
authority: declared_intent
owner: fleet-advancement-2026-08
---

# Ten-Node Autocatalytic Portfolio

This is the architecture page for the ten load-bearing metabolic mechanisms in `dharma_swarm`. The machine-readable authority is `ACTIVE_SURFACE_MANIFEST.yaml`; runtime witnesses are descriptive evidence under `~/.dharma/a2a/autocatalytic_portfolio/`. Neither this page nor the dashboard grants side-effect authority.

This portfolio is the metabolism of the currently active governance tracks, not a claim that ten was discovered independently of governance. The ten node boundaries are justified separately by distinct producer/consumer contracts, project adapters, proof references, and authority ceilings; several nodes bind more than one track. Seven nodes have `local_evidence` ceilings. Three missing membranes remain explicit and gated: operator experience, external value delivery, and learning promotion. Every currently `ACTIVE` track must be bound, and no inactive track may be smuggled into the active set; the manifest validator enforces that equality.

## Closed metabolism

| # | Node | Typed handoff | Authority | Bound projects |
|---:|---|---|---|---|
| 1 | [World-Signal Supply](autocatalytic_nodes/world_signal_supply.md) | `promoted_feedback -> grounded_signal` | `local_evidence` | RSI Lab / Meghadharma, Sublimation Forge |
| 2 | [Persistent Agent / Sarathi](autocatalytic_nodes/sarathi_runtime.md) | `grounded_signal -> prioritized_work` | `local_evidence` | Fleet advancement |
| 3 | [DharmaGraph Execution](autocatalytic_nodes/dharmagraph_execution.md) | `prioritized_work -> execution_receipt` | `local_evidence` | Fleet advancement |
| 4 | [Cybernetic Supervision](autocatalytic_nodes/cybernetic_supervision.md) | `execution_receipt -> closure_gap` | `local_evidence` | Fleet advancement |
| 5 | [Arena Selection](autocatalytic_nodes/arena_selection.md) | `closure_gap -> selected_experiment` | `local_evidence` | RSI Lab / Meghadharma, Sublimation Forge |
| 6 | [Chamber Research](autocatalytic_nodes/chamber_research.md) | `selected_experiment -> proposed_change` | `local_evidence` | RSI Lab / Meghadharma, Sublimation Forge |
| 7 | [Assurance & Merge](autocatalytic_nodes/assurance_merge.md) | `proposed_change -> verified_release` | `local_evidence` | Fleet advancement, SADHANA 10-day, RSI Lab / Meghadharma, Sublimation Forge |
| 8 | [Operator Experience](autocatalytic_nodes/operator_experience.md) | `verified_release -> authorized_action` | `projection_only` | Fleet advancement, SADHANA 10-day |
| 9 | [External Value Delivery](autocatalytic_nodes/external_value_delivery.md) | `authorized_action -> external_outcome` | `external_gated` | SADHANA 10-day |
| 10 | [Learning & Promotion](autocatalytic_nodes/learning_promotion.md) | `external_outcome -> promoted_feedback` | `projection_only` | SADHANA 10-day, RSI Lab / Meghadharma, Sublimation Forge |

The last output is the first input. Cross-edges additionally bind World Radar evidence to Chamber oracles, assurance contracts back to DharmaGraph, and operator intent back to Sarathi.

## Read-only project metabolism

The harness does not manufacture a positive result merely because a hop completed. Each node invokes a project-specific, read-only adapter, validates its source kind and contract, snapshots the bytes by SHA-256, and emits a typed signal envelope. Structured JSON rejects duplicate keys, wrong schemas or field types, and missing or invalid required digests; JSONL, Markdown, and text remain explicitly distinct source kinds. The verifier re-invokes the same adapter implementation against the current source bytes before it accepts the hop. That catches source drift and witness tampering, but it is not implementation diversity: a common-mode semantic bug can survive both invocations. Any authority above `local_rehearsal` therefore requires a separately owned evaluator or trust root, not this recomputation alone.

| Node | Adapter | Current emitted state |
|---|---|---|
| World-Signal Supply | `world_radar.historical_receipt_projection` | `historical_grounded_fixture` |
| Persistent Agent / Sarathi | `sarathi.pure_bootpack_plan` | `planned_not_accepted` |
| DharmaGraph Execution | `dharmagraph.pure_execution_identity` | `rehearsal_intent_no_domain_execution` |
| Cybernetic Supervision | `cybernetics_codex.committed_audit_projection` | `closure_gaps_observed` |
| Arena Selection | `arena.hermetic_truth_receipt` | `candidate_only_not_selected` |
| Chamber Research | `chamber.receipt_corpus_projection` | `blocked_no_proposal` |
| Assurance & Merge | `assurance.ci_contract_fail_closed` | `not_verified` |
| Operator Experience | `helm.read_only_authorization_projection` | `authorization_not_observed` |
| External Value Delivery | `darshan.effect_receipt_gate` | `external_gate_closed` |
| Learning & Promotion | `arena.zero_weight_learning_gate` | `promotion_blocked` |

The signal `type` remains the declared port type—for example `verified_release`—while `state` records the evidence-backed inhabitant, such as `not_verified`. `promotion_authorized` is always false in this local lane. This is an evaluator-level authority rule: a positive-named port cannot promote a negative or gated state into a stronger claim.

Three cross-feeds are exercised, not merely drawn. `oracle_evidence` reaches Chamber in the same turn; `safety_contract` reaches DharmaGraph on the next turn; and `operator_intent` reaches Sarathi on the next turn. Each `dharma.autocatalytic.cross_feed.v1` envelope must resolve to exactly one prior project-evidence ledger row and match its source, target, signal, evidence hash, state, modality, and expected turn. Consumption is one-shot: the feed is removed before the target emits anything new, and the target adapter binds the consumed value into its own evidence hash. Missing future-source feeds in turn zero remain explicit `not_available` values; a present malformed, forged, or stale feed fails the hop. None of these feeds can set `promotion_authorized`. Because the runtime bus is keyed by signal name, the validator also requires cross-feed signal names to be globally unique and rejects an ambiguous future declaration before execution.

## Executable promotion rule

`TransportAck` cannot inhabit `StructuralHop`.

`StructuralHop` deliberately carries no execution or promotion authority. It requires all of:

1. exact A2A status `completed`;
2. exactly one `dharma.a2a.semantic_hop.v1` data artifact;
3. the expected node, ordinal, input, output, trace, and correlation identity;
4. valid message causation and predecessor hash;
5. a recomputed artifact hash and project-evidence hash;
6. exact projected execution identity plus the expected A2A and semantic receipt IDs;
7. independently recomputed adapter evidence and cross-feed emissions.

`StructuralCycleProof` requires exactly ten ordered `StructuralHop` values and closure from node 10 back to node 1. Its result type is `StructuralCycleCheck(modality="structure_only")`; it cannot be mistaken for the receipt evaluator. The local harness proves two turns so the second turn consumes node 10's actual prior output, not only a bootstrap fixture.

A locally receipt-consistent two-turn witness must join to exactly 41 semantic-proof rows selected from the runtime database managed by `RuntimeStateStore`:

- 20 `a2a_task` receipts written by `A2AServer`;
- 20 `autocatalytic_hop_proof` receipts binding the semantic artifact and project evidence;
- one `autocatalytic_cycle_proof` attestation binding the proof root, implementation fingerprint, and runtime receipt set.

Submission also traverses the runtime-truth spine via `submit_task_via_spine_sync`, which records `side_effect_intent`, `side_effect_complete`, and `idempotency_consumed` rows for each hop. Those 60 substrate rows are operational evidence and are reported separately; they are not silently promoted into the verifier's 41-row semantic-consistency result.

The receipt evaluator opens the runtime database read-only and compares the exact run, task, idempotency key, message, trace, correlation, artifact, completion, and proof identities. It returns `LocalReceiptConsistencyCheck(modality="local_mutable_runtime_receipt_consistency", independently_authenticated=false)`. A self-consistent JSON witness without the rows fails this check.

This is not authenticated provenance. A local operator with write access can construct matching SQLite rows, so neither an unkeyed attestation nor the 41-row join proves that `A2AServer` executed the work against an adversary. The evaluator and dashboard therefore forbid promotion from local receipt consistency to authenticated execution. Stronger authority would require an independently controlled append-only issuer, signature/MAC, or equivalent trust root.

Run the contract and local rehearsal with:

```bash
python -m dharma_swarm.autocatalytic_portfolio check
python -m dharma_swarm.autocatalytic_portfolio run --turns 2
```

The strongest allowed result is `local_rehearsal`. It establishes ten logical A2A nodes in one process, project-specific read-only projections, typed cross-feed traffic, local mutable-receipt consistency, and semantic/causal continuity. It does not prove authenticated execution provenance, ten independent peers, live model semantics, JetStream domain completion, publication, revenue, a production daemon, or any external effect.

## Replay and evidence drift

The verifier fingerprint binds the exact portfolio declaration, verifier version, and byte-framed, explicitly enumerated implementation source bundle captured once when the verifier loads. The closed bundle includes the contracts, source/manifest helpers, adapters, task/proof/cycle runtime, receipt verifier, and compatibility facades. Capturing that bundle hash once prevents a running old evaluator from stamping newly replaced on-disk bytes as its own. Project evidence additionally binds each source artifact's bytes and validates any declared JSON digest. Declared governance-receipt digests replay their producer convention (`sort_keys`, compact separators, escaped Unicode); the portfolio witness uses its separately named sorted, compact, unescaped JSON serialization. A non-ASCII regression fixture prevents those two serializations from being silently conflated. A code, manifest, or source-evidence change intentionally makes an older “latest” witness fail current verification. The immutable artifact remains useful as an archive of what the older evaluator accepted, but a fresh witness must be minted before the dashboard may present the cycle as locally receipt-consistent under the new evaluator.

Default witness and runtime-receipt paths share one dynamically resolved state root. The manifest-declared `DHARMA_STATE_DIR` override wins over the legacy `DHARMA_HOME` alias. Each run materializes `a2a/autocatalytic_portfolio/{cycle_id}.json`, refreshes the mutable `latest.json` alias, writes the `A2AServer` task log `{cycle_id}.tasks.jsonl`, and registers ten card JSON files under `a2a/autocatalytic_portfolio/cards/`; semantic receipts use the existing `state/runtime.db`. Resolving all of them at call time prevents an import-order environment change from splitting a witness and its local receipt rows across different roots. These local mutable artifacts are replay evidence; they neither authenticate provenance nor permit promotion.

## Promotion boundary

Node authority is monotone. `local_evidence`, `projection_only`, and `external_gated` may not be upgraded by a cycle witness, model consensus, task status alone, social proof, or operator-interface presence. Each node page names the additional proof obligation required for a higher claim.

Each node also declares an exact list of code-owned `promotion_checks`. Manifest validation fails when a declaration is missing, reordered, added, or changed without a matching contract update. The adapter evaluates each check as a strict boolean against its own evidence details, includes the result inside the content-addressed project evidence, and reports the aggregate readiness state. Missing or non-boolean facts fail closed. These checks are challengeable evidence preconditions, not promotion authority: the gate remains `blocked` and `authority_upgrade_authorized=false` even when every predicate is true. A stronger claim requires a new authority-bearing evaluator and a separately reviewed work packet.

The dashboard renders adapter evidence only when the backend has accepted the portfolio contract and recomputed both structure and local receipt consistency. Failed topology validation or stale/untrusted evidence is shown as an error or non-verified state, never as authenticated execution or a healthy production cycle.

Operator pages:

- portfolio: `/dashboard/organism`
- node: `/dashboard/organism/<node_id>`
