# Canonical-substrate composition evidence

Observed 2026-08-05T05:26:13Z from base `9fd1bfc39e6d` plus the packet-scoped diff.

The implementation is split by responsibility and imports the existing substrate directly:

- `autocatalytic_contracts.py` owns typed result values, exact code-owned promotion predicates, source-contract validation, topology checks, and canonical hashing;
- `autocatalytic_adapters.py` owns ten read-only project adapters plus ledger-bound, one-shot cross-feed consume/adapt/emit semantics;
- `autocatalytic_verifier.py` re-invokes the same adapter implementation to detect source drift or witness tampering, then separately evaluates structure and the bounded local mutable-receipt consistency result; this is not an independently implemented semantic oracle;
- `autocatalytic_portfolio.py` is the public facade and local rehearsal runner;
- `A2AServer`, task/artifact/message types, `AgentCard`, and `CardRegistry` remain the canonical A2A substrate;
- every task submission goes through `submit_task_via_spine_sync`, which owns runtime-truth and idempotency receipts before delegating to `A2AServer`;
- `RuntimeStateStore`, `RuntimeReceipt`, `correlation_scope_sync`, `CatalyticGraph`, and `dharma_state_dir` remain their existing canonical owners.

No second task store, graph implementation, card registry, correlation context, truth spine, or runtime database is introduced. The only new persisted artifact is a read-model witness under the already declared Dharma state directory. Project adapters are read-only and record `side_effects_performed=false`.

## Source identity and seams

| Source | SHA-256 | Seam used |
|---|---|---|
| `dharma_swarm/autocatalytic_contracts.py` | `94b85af9657e4812492364a4fe27b28f3ed6e9b46e7dc8844f0372062c4f1741` | typed authority/result, exact non-authorizing promotion gates, and fail-closed source contracts |
| `dharma_swarm/autocatalytic_adapters.py` | `860a2a17bae5734be0096c3b6b2efee2c9dbe67f470b372d5ec9c5635b74015c` | ten adapters; causal cross-feed ledger binding; content-addressed gate evaluation |
| `dharma_swarm/autocatalytic_verifier.py` | `a7f6809a8f9e545ffb584e7811e968dc1107481c3f6e047575a8908dc143fae6` | structural and local-consistency evaluation plus same-implementation adapter replay |
| `dharma_swarm/autocatalytic_portfolio.py` | `14ebeeb3fb44a0e86b9a0c100d5f25a252737434638b01c5fdf3ab971c6c86d3` | facade, handler composition, two-turn runner, shared state-root resolution |
| `dharma_swarm/a2a/a2a_server.py` | `08450fc3ca20e7b007bd43640e728474551682299e3349c49f639cfc11653ab9` | `A2AServer` line 315; local submit seam line 400 |
| `dharma_swarm/a2a/spine_adapter.py` | `fb1e6fcd5f2a1ffa78400fe8500dc4714267b9203640f6990a53faf507262b2a` | canonical `submit_task_via_spine_sync` line 178 |
| `dharma_swarm/a2a/agent_card.py` | `a48d76cef7cc9f929857f058e544441a22423484429e962ef9974ab2a289788f` | `CardRegistry` line 471 |
| `dharma_swarm/runtime_state.py` | `22af785d727c4302b13c1e0e153e1122bc81edc1472bcb3f95a072148c0bc7c2` | `RuntimeStateStore` line 1209; receipt write line 3216 |
| `dharma_swarm/correlation_context.py` | `f1e0b5e6b5863a23c9a21742e6dc37f68bee40a7b40f5a2f3b2da3c16a270440` | `correlation_scope_sync` line 145 |
| `dharma_swarm/catalytic_graph.py` | `ce7a4859431411714588e9b0144f1a90293095d220db48c73b8f5b2bc179f65c` | `CatalyticGraph` line 25; set detection line 164 |
| `dharma_swarm/daemon_config.py` | `cf5e27fbd2ce3bd6362a6d24b2ede5bd986805f37ef07d2da45783206ce86b6e` | `dharma_state_dir` line 20 |
| `api/main.py` | `840a86a703134d8e014fb7e68c5a544f2bcccf6cb00d195baa78a2f48d451f2b` | mounted FastAPI composition root |
| `dashboard/src/lib/api.ts` | `f54ca89728c3f9dcaeeba52ce10e3f909dc9f78061f8fe249450efebca8d3a5d` | existing dashboard API client |
| `dashboard/src/lib/theme.ts` | `4536dfad70e16ee443f9d40ea52804043ff3fdf9ade289edbd7d5cf24e2962b1` | existing dashboard theme vocabulary |

The independently recomputed byte-framed four-module bundle hash is `ef857d247921d142f27ceeccc1ae1f40fe91c35531be3b27e735b99fe200a5c3`, exactly matching the fresh witness.

## Authority boundary

The spine returned `status=ok` for each local hop and recorded 20 rows each of `side_effect_intent`, `side_effect_complete`, and `idempotency_consumed`. The semantic evaluator separately selects and exact-joins 20 `a2a_task`, 20 `autocatalytic_hop_proof`, and one `autocatalytic_cycle_proof` row. All rows are locally mutable, so neither set is authenticated provenance. The evaluator returns the immutable `LocalReceiptConsistencyCheck` modality `local_mutable_runtime_receipt_consistency` with `independently_authenticated=false`; authenticated execution remains a separate, unsatisfied type obligation.

Each of the 20 project-evidence rows also carries a `dharma.autocatalytic.promotion_gate.v1` evaluation. The manifest must exactly match the ordered code-owned predicate set for its node, missing or non-boolean evidence fails closed, and forged gate payloads fail adapter replay. All 20 gates in the fresh witness are unsatisfied, and zero authorize an authority upgrade. Even an all-true synthetic gate is definitionally `blocked`; promotion requires a separately reviewed authority-bearing evaluator and work packet. This prevents evidence readiness from becoming standing by truthiness or consensus.

Because adapter replay shares implementation with the producer, it is a drift/tamper check rather than diversity evidence. A common-mode adapter bug may survive both invocations. No authority above `local_rehearsal` may rely on this shared implementation without a separately owned evaluator or trust root.

Witness aliases and runtime receipts resolve from one state-root function on every call. `DHARMA_STATE_DIR`, the manifest-declared override, takes precedence over legacy `DHARMA_HOME`; the resolved root owns `a2a/autocatalytic_portfolio` and `state/runtime.db`. An integration test runs a complete two-turn default cycle under an alternate root, reloads it without explicit paths, and confirms both witness and receipt database stayed beneath that root.
