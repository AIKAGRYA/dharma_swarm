# Canonical-substrate composition evidence

The semantic bundle and hashes below were observed at implementation head `2323d3a42f94` over base `9fd1bfc39e6d`. Persistence-layout and gate evidence were refreshed 2026-08-05T08:09:57Z against committed parent `0feebfacc450`; no fingerprinted semantic module or manifest byte changed between those heads.

The implementation is split by responsibility and imports the existing substrate directly:

- `autocatalytic_contracts.py`, `autocatalytic_adapters.py`, and `autocatalytic_portfolio.py` are compatibility facades that preserve the public import surface;
- contract primitives, source/manifest checks, adapter evidence, the ten project adapters, task handling, proof construction, and cycle execution are split into focused modules, each below 500 lines;
- `autocatalytic_verifier.py` and `autocatalytic_receipt_verifier.py` re-invoke the same adapter implementation to detect source drift or witness tampering, then separately evaluate structure and bounded local mutable-receipt consistency; this is not an independently implemented semantic oracle;
- the verifier fingerprints an explicit closed tuple of all 14 semantic implementation modules, using length-framed names and bytes captured once at import;
- `A2AServer`, task/artifact/message types, `AgentCard`, and `CardRegistry` remain the canonical A2A substrate;
- every task submission goes through `submit_task_via_spine_sync`, which owns runtime-truth and idempotency receipts before delegating to `A2AServer`;
- `RuntimeStateStore`, `RuntimeReceipt`, `correlation_scope_sync`, `CatalyticGraph`, and `dharma_state_dir` remain their existing canonical owners.

No second task-store implementation, graph implementation, card registry, correlation context, truth spine, or runtime database is introduced. A persisted run reuses the canonical `A2AServer`, `CardRegistry`, and `RuntimeStateStore` implementations and materializes `{cycle_id}.json`, the mutable `latest.json` alias, `{cycle_id}.tasks.jsonl`, ten card JSON files, and receipt rows in the existing `state/runtime.db`, all beneath the already declared Dharma state directory. Project adapters are read-only and record `side_effects_performed=false`; none of these local mutable artifacts authorizes an authority upgrade.

## Source identity and seams

| Source | SHA-256 | Seam used |
|---|---|---|
| `dharma_swarm/autocatalytic_adapter_evidence.py` | `8cf4d89339c9c77f8310231e00e639a533a4834d3b37e591dc1414600f4cf8c2` | evidence/source helpers (120 LOC) |
| `dharma_swarm/autocatalytic_adapters.py` | `a10ab7e60b8cc05227766e8674fe353b6cf56c6ecaed530ba8c721b991b37a7f` | stable adapter facade and registry (259 LOC) |
| `dharma_swarm/autocatalytic_adapters_research_promote.py` | `0ca82001cdd416d240ad182f6e48dc3f8e2f0e42ee84a8da5d3bce52656633e5` | research, assurance, delivery, and promotion adapters (406 LOC) |
| `dharma_swarm/autocatalytic_adapters_sense_execute.py` | `8dc0c9cae5fe6d44a3be052c964cd5ac5c0c673039ec60a51ec2882562ea3fe2` | sensing, planning, execution, supervision, and selection adapters (333 LOC) |
| `dharma_swarm/autocatalytic_contract_primitives.py` | `f6cac0c582b8d2540e2f5f6ee2e5d1a41ff9ee27eae12697696d371d9b83c50c` | frozen result types and contract primitives (178 LOC) |
| `dharma_swarm/autocatalytic_contracts.py` | `19824e95d7e8956d9fd5634c59eea52118f5843e3b8799165a8c36e065faab52` | stable contract facade (216 LOC) |
| `dharma_swarm/autocatalytic_cycle_runtime.py` | `689c21a9aad21d3b9a2d06ab9acdf4afced1a57613e8b758ca85f67bbade6aaa` | persisted two-turn cycle and shared state-root resolution (390 LOC) |
| `dharma_swarm/autocatalytic_manifest_contracts.py` | `3b6781f8c883d2a3be0e761caef6bc8883b8b3ae97852676e5be41aab07ff450` | topology, manifest, and promotion-predicate checks (306 LOC) |
| `dharma_swarm/autocatalytic_portfolio.py` | `67810f32da2a5185329e8ea561277b3d7c5625e3be85ba8cbf91e600a0153965` | public facade and CLI (156 LOC) |
| `dharma_swarm/autocatalytic_proof_builders.py` | `2c9f90b5188096e9ec133aaa88303f0e09b96bfd9fb8e9927ef6f162d9a109ac` | structural hop and cycle proof construction (318 LOC) |
| `dharma_swarm/autocatalytic_receipt_verifier.py` | `1aa4c7856b7a42006e798d668267ce3b18b963a8ced270ec8e28493565638f8a` | exact local receipt joins and attestation checks (241 LOC) |
| `dharma_swarm/autocatalytic_source_contracts.py` | `a85ed31a47d97edfeb4441467811b065e16f874336503afa6ef473cdaffbc096` | source kinds, strict parsing, and hashing (189 LOC) |
| `dharma_swarm/autocatalytic_task_runtime.py` | `f640326193967522b75938a09a8cc2e10263e3be1369c22bc529d81b62937481` | typed A2A task handling (151 LOC) |
| `dharma_swarm/autocatalytic_verifier.py` | `fcf1d3286b206f8f0b835ecaf5fe181ded8decd61208686b54cede180d37b16d` | structural checking and explicit bundle fingerprint (374 LOC) |
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

The independently recomputed byte-framed 14-module implementation bundle hash is `e22f39820f483f33c581323f27c845bddbb5669178fdc0047cd3c89d218d956e`, exactly matching the fresh witness.

## Authority boundary

The spine returned `status=ok` for each local hop and recorded 20 rows each of `side_effect_intent`, `side_effect_complete`, and `idempotency_consumed`. The semantic evaluator separately selects and exact-joins 20 `a2a_task`, 20 `autocatalytic_hop_proof`, and one `autocatalytic_cycle_proof` row. All rows are locally mutable, so neither set is authenticated provenance. The evaluator returns the immutable `LocalReceiptConsistencyCheck` modality `local_mutable_runtime_receipt_consistency` with `independently_authenticated=false`; authenticated execution remains a separate, unsatisfied type obligation.

Each of the 20 project-evidence rows also carries a `dharma.autocatalytic.promotion_gate.v1` evaluation. The manifest must exactly match the ordered code-owned predicate set for its node, missing or non-boolean evidence fails closed, and forged gate payloads fail adapter replay. All 20 gates in the fresh witness are unsatisfied, and zero authorize an authority upgrade. Even an all-true synthetic gate is definitionally `blocked`; promotion requires a separately reviewed authority-bearing evaluator and work packet. This prevents evidence readiness from becoming standing by truthiness or consensus.

Because adapter replay shares implementation with the producer, it is a drift/tamper check rather than diversity evidence. A common-mode adapter bug may survive both invocations. No authority above `local_rehearsal` may rely on this shared implementation without a separately owned evaluator or trust root.

Witnesses, canonical A2A task logs, card files, and runtime receipts resolve from one state-root function on every call. `DHARMA_STATE_DIR`, the manifest-declared override, takes precedence over legacy `DHARMA_HOME`; the resolved root owns `a2a/autocatalytic_portfolio` and `state/runtime.db`. An integration test runs a complete two-turn default cycle under an alternate root, reloads it without explicit paths, and checks the cycle archive, byte-identical mutable alias, 20-row cycle task log, exact ten-card set, and receipt database beneath that root.
