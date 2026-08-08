# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 98
score_avg: 99.67

## Blockers

- kimik3: verdict=revise

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=True verdict=approve score=100 actual=glm-5.2
  summary: Ten-node autocatalytic A2A portfolio with honest local_rehearsal ceiling, fail-closed promotion gates, distinct structure-only vs local-receipt-consistency types, content-addressed adapters, causal cross-feeds, and no authority overstatement. No concrete blocker found.
- `kimik3` `kimi_code:k3` ok=True verdict=revise score=98 actual=k3
  summary: Claim honestly capped at local_rehearsal; topology, gates, cross-feeds, fail-closed replay, distinct result types, and UI/API/doc authority story all verified against attached code and receipts. One concrete UI truthfulness nit blocks 100.
- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=True verdict=pass score=100 actual=kimi-k2.6
  summary: Ten-node autocatalytic portfolio satisfies all declared local-rehearsal claims: runtime topology enforcement, substantive adapters, honest authority ceiling, distinct structure/receipt types, comprehensive adversarial tests, aligned API/dashboard/docs. No blockers.
- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=True verdict=pass score=100 actual=deepseek-v4-pro
  summary: No concrete blockers remain. The ten-node portfolio is rigorously validated with fail-closed promotion, distinct structural/receipt checks, and honest authority ceilings. All evidence is challengeable and consistent.
- `minimaxm3` `ollama:minimax-m3:cloud` ok=True verdict=pass score=100 actual=minimax-m3
  summary: Bounded to local_rehearsal; structural vs local-consistency types distinct; adapter replay = drift/tamper only; verifier bundles 14 modules; all-true gates stay blocked; cross-feeds causal one-shot; 10 nodes project-specific read-only.
- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=approve score=100 actual=nvidia/nemotron-3-ultra-550b-a55b:free
  summary: Ten-node autocatalytic A2A portfolio passes all integration, evidence, anti-slop, governance, and operability criteria. Every node runs a project-specific read-only adapter over content-addressed sources, emits typed signal envelopes with negative states, and enforces promotion gates that remain blocked even when all predicates are true. Structural and local-receipt consistency are distinct modalities with no authority-erasing switch. The dashboard, API, and docs render the same local_rehearsal

## Persistent Agent

- `palantir-pilot` status=running fresh=True
