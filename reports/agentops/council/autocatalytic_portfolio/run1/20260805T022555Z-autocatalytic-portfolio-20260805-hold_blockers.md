# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 75
score_avg: 87.83

## Blockers

- glm52: score=90 < 100
- glm52: disagreement=No disagreement with the premise. The ten nodes are defensibly load-bearing: each binds at least one active project, has a distinct typed transform, and has executable proof_refs. The selection is not an arbitrary relabeling of ten tracks b
- kimik3: verdict=revise
- kimik3: disagreement=The premise that the ten nodes are selected on executable producer/consumer substance rather than being the ten active governance tracks relabeled is only partially supported. The binding test enforces an exact bijection between node projec
- qwen3coder: verdict=revise
- minimaxm3: verdict=revise
- minimaxm3: disagreement=No disagreement with the implementation's claim ceiling or its honesty about unproven regions. The review requires the per-node dynamic page and the /api/manifest/autocatalytic endpoint code to be in the evidence bundle before issuing a pas
- nemotron3ultra: verdict=revise
- nemotron3ultra: disagreement=The prompt claims 'portfolio snapshot: 10 nodes, 13 edges, one SCC, one autocatalytic set, contract valid, zero validation errors' but this cannot be verified without the missing declaration files. The implementation code correctly enforces
- persistent-agent:palantir-pilot: persistent A2A worker is not currently running

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=True verdict=pass score=90 actual=glm-5.2
  summary: The ten-node autocatalytic portfolio makes a deliberately narrow claim (local_rehearsal) and backs it with executable evidence: a closed signal ring with matching input/output continuity, strict promotion rules that block transport-ACK/nonterminal/tampered/gapped/stale-verifier promotion, hash-linked two-turn witnesses reverified on read, and read-only dashboard projections that do not overclaim authority or external effects. Three ungrounded membranes are visibly gated with proof obligations. T
- `kimik3` `kimi_code:k3` ok=True verdict=revise score=84 actual=k3
  summary: Substantively honest, well-bounded implementation: the local_rehearsal ceiling is enforced in code (TransportAck has no promotion surface, CompletedHop/CycleProof have real verification, witnesses are reverified on read including verifier fingerprint), composition uses the canonical manifest/A2A server/runtime DB/CatalyticGraph rather than a rival store, and negative tests cover nonterminal tasks, ACK non-promotion, and artifact tampering. However, two truthfulness gaps prevent merge-as-stated:
  blocker: Binding-completeness is not part of the runtime contract: validate_portfolio only checks that bindings are known track ids (unfiltered by status via _active_track_ids), while test_every_active_project_is_bound_into_the_metabolism asserts bound == {status==ACTIVE}. An 11th activated track leaves validate_portfolio green, the API snapshot contract_valid=true, and the dashboard showing a healthy closed ring while one active project is unbound. The invariant the review was asked to guarantee is enfo
  blocker: Dashboard hides server-side contract failure: build_autocatalytic_snapshot returns topology.contract_valid and topology.validation_errors, but AutocatalyticPortfolioResponse in autocatalyticPortfolio.ts omits the topology field and neither organism page surfaces validation errors; hasClosedTenNodeRing/summarizePortfolio recompute closure client-side, so a drifted manifest that fails server validation renders without any fail-closed signal.
  blocker: Cross-feed edges are unvalidated free text: oracle_evidence, safety_contract, and operator_intent appear only as edge.signal values; no node declares them as output_signal and validate_portfolio checks only ring-pair presence, not cross-feed signal provenance or semantic type, leaving 3 of 13 declared 'typed feeds' untyped in the enforced contract.
- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=True verdict=revise score=90 actual=kimi-k2.6
  summary: The visible implementation demonstrates strong semantic safety, honest claim ceilings, and rigorous hash-linked witness verification. The deterministic in-process rehearsal harness correctly rejects transport-ack promotion, enforces exact terminal status, and recomputes all hashes on read. Dashboard presentation logic is read-only, authority-typed, and does not overclaim external effects. Blocked from pass by unattached integration surfaces: the backend API endpoint consumed by the dashboard, th
  blocker: Missing API route implementation: /api/manifest/autocatalytic is declared as a dashboard dependency in ACTIVE_SURFACE_MANIFEST.yaml and consumed in organism/page.tsx, but no backend handler implementation or contract test is attached; the frontend-to-backend integration is unverified.
  blocker: Missing dynamic page implementation: /dashboard/organism/[nodeId] is referenced by portfolioNodeHref, declared in every node manifest entry, and claimed as compiled, but its Next.js page implementation is not attached; per-node authority badges and proof-obligation presentation cannot be reviewed.
  blocker: Missing ACTIVE_TRACK.yaml: test_every_active_project_is_bound_into_the_metabolism reads docs/governance/ACTIVE_TRACK.yaml, which is not attached; the premise that the ten nodes bind every currently active project rather than an arbitrary subset is unverifiable.
  blocker: Unversioned verifier fingerprint: verify_cycle_witness binds witness validity to the exact SHA256 of autocatalytic_portfolio.py via _implementation_fingerprint; any patch to the verifier invalidates all stored witnesses without a compatibility window, migration path, or documented archival policy.
- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=True verdict=approve score=100 actual=deepseek-v4-pro
  summary: The implementation is honest, well-tested, and enforces strict claim ceilings. All active projects are bound, promotion rules are enforced, and the dashboard is read-only with clear authority badges. No overclaims. The local rehearsal harness is deterministic and verifiable. No blockers.
- `minimaxm3` `ollama:minimax-m3:cloud` ok=True verdict=revise score=88 actual=minimax-m3
  summary: Implementation is honest and well-defended: closed ten-node signal ring, autocatalytic set invariant enforced through CatalyticGraph, TransportAck has no promotion surface to CompletedHop, two-turn local rehearsal with hash/visitation/causation continuity, witnesses are reverified against the verifier-bytes fingerprint on read, and the dashboard surfaces label every node with a distinct authority badge and clearly mark external effects as not proven. Cannot reach 100 because the per-node dynamic
- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=revise score=75 actual=nvidia/nemotron-3-ultra-550b-a55b:free
  summary: The autocatalytic portfolio implementation is well-structured with strong anti-slop guarantees (explicit promotion barriers, hash-linked artifacts, reverification on read, honest claim ceilings). However, the evidence package is missing critical declaration files (ACTIVE_TRACK.yaml, node documentation pages, proof reference implementations) required to verify the core claims that (1) these are the ten load-bearing nodes bound to active projects, and (2) every active project is actually bound. Th
  blocker: ACTIVE_TRACK.yaml not provided — cannot verify test_every_active_project_is_bound_into_the_metabolism claim that bound projects == active tracks
  blocker: Node documentation pages (docs/architecture/autocatalytic_nodes/*.md) not provided — validate_portfolio require_files=True checks these exist
  blocker: Proof reference files (e.g., dharma_swarm/world_radar/go_bridge.py, tests/test_world_radar_go_bridge.py, etc.) not provided — validate_portfolio require_files=True checks these exist
  blocker: Core infrastructure implementations (A2AServer, CatalyticGraph, RuntimeStateStore, correlation_context, daemon_config) not provided — cannot verify they compose correctly without rival substrate
  blocker: Dashboard dependencies (@/lib/api, @/lib/theme, ./_components) and API route /api/manifest/autocatalytic not provided — cannot verify read-only projection works

## Persistent Agent

- `palantir-pilot` status=stopped fresh=False
  blocker: persistent A2A worker is not currently running
