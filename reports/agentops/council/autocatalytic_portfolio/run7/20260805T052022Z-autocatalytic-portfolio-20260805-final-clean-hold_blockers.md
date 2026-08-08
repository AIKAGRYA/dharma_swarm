# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 93
score_avg: 98.0

## Blockers

- kimik3: score=93 < 100
- minimaxm3: score=95 < 100

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=True verdict=approve score=100 actual=glm-5.2
  summary: Ten-node autocatalytic portfolio is honest, well-tested, and consistently capped at local_rehearsal across manifest, code, API, dashboard, and docs. No concrete blocker found.
- `kimik3` `kimi_code:k3` ok=True verdict=approve score=93 actual=k3
  summary: Internally consistent, fail-closed local_rehearsal packet: typed contracts, strict-boolean non-authorizing gates, one-shot ledger-bound cross-feeds, distinct structure_only vs local-mutable-receipt modalities, and honest ceilings in code, UI, and docs all align. Self-reported gate counts and one config naming detail remain unverified.
- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=True verdict=pass score=100 actual=kimi-k2.6
  summary: Ten-node autocatalytic portfolio passes executable contracts. Topology, adapters, cross-feeds, structural/receipt verification, and promotion gates are enforced and tested. No overstatement of local receipts. Honest local_rehearsal ceiling.
- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=True verdict=pass score=100 actual=deepseek-v4-pro
  summary: Ten-node autocatalytic portfolio meets all production-grade integration, governance, and safety criteria. No blockers remain; local_rehearsal ceiling is consistently enforced.
- `minimaxm3` `ollama:minimax-m3:cloud` ok=True verdict=pass score=95 actual=minimax-m3
  summary: Bounded local-rehearsal claim is consistent across manifest, contracts, adapters, verifier, docs, and UI. Ten distinct project adapters with content-addressing; structural and local-consistency modalities are distinct and fail closed on tamper/forge. No blocker remains inside the declared scope.
- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=pass score=100 actual=nvidia/nemotron-3-ultra-550b-a55b:free
  summary: Ten-node autocatalytic portfolio meets all stated claims: 10 distinct project-specific read-only adapters, closed signal ring with 3 typed cross-feeds exercised across 2 turns, structure-only and local mutable-receipt consistency as distinct non-authoritative result types, promotion gates fail-closed with all-true-still-blocked invariant, verifier fingerprints implementation at import, dashboard fails closed on topology contract, all claims honestly capped at local_rehearsal with no overstatemen

## Persistent Agent

- `palantir-pilot` status=running fresh=True
