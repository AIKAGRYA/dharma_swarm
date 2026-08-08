# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 88
score_avg: 98.0

## Blockers

- nemotron3ultra: verdict=revise

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=True verdict=pass score=100 actual=glm-5.2
  summary: Ten-node autocatalytic portfolio is honest, well-tested, and production-grade for its claimed local_rehearsal ceiling. Adapters do substantive read-only work; cross-feeds are causal and one-shot; structure-only and local-receipt-consistency are distinct non-authoritative types; no overstatement found in code, API, dashboard, or docs.
- `kimik3` `kimi_code:k3` ok=True verdict=pass score=100 actual=k3
  summary: Typed-gates revision resolves my prior blockers: promotion predicates are now code-owned, executable, strict-boolean, content-addressed, all-true-still-blocked; shared-implementation replay is documented as drift-check-only; heartbeat witness carries raw NATS consumer state. Ceiling stays honest at local_rehearsal; no overstatement found.
- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=True verdict=pass score=100 actual=deepseek-v4-pro
  summary: Ten-node autocatalytic portfolio is honest, well-tested, and production-grade for its claimed local_rehearsal ceiling. Adapters do substantive read-only work; cross-feeds are causal and one-shot; structure-only and local-receipt-consistency are distinct non-authoritative types; no overstatement found in code, API, dashboard, or docs.
- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=True verdict=pass score=100 actual=deepseek-v4-pro
  summary: Ten-node portfolio is honest, well-tested, fail-closed, and respects local_rehearsal ceiling. No overstatement; all claims backed by executable evidence.
- `minimaxm3` `ollama:minimax-m3:cloud` ok=True verdict=approve score=100 actual=minimax-m3
  summary: Honors local_rehearsal ceiling. validate enforces ring/edges/pages/active-track equality; 10 typed read-only adapters; StructuralHop/LocalReceiptConsistencyCheck are distinct immutable non-promoting modalities; cross-feeds ledger-bound one-shot; canonical substrate; 196 tests pass.
- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=revise score=88 actual=nvidia/nemotron-3-ultra-550b-a55b:free
  summary: Ten-node autocatalytic portfolio is internally consistent and honestly capped at local_rehearsal, but three verified blockers remain: (1) gate evidence is self-authored on feature branch, not trusted-CI re-run per repo doctrine; (2) palantir-pilot heartbeat is self-reported, not independently verifiable; (3) proof_obligations are prose strings, not executable checks as required. Qwen lane invalid due to Kimi substitution.
  blocker: Gate evidence (pytest 196/45/20, Next build, pre-commit suite) exists only as self-authored local_gate_receipt.json on feature branch; repo's safety-TCB doctrine requires trusted-CI re-run for authenticity
  blocker: persistent_agent_evidence.json heartbeat status/freshness is self-reported by producer; no independent verification included in packet
  blocker: Manifest proof_obligations for all 10 nodes are prose strings, not executable checks (receipt_valid/command_passes-style), contradicting packet's own requirement for executable proof obligations per promotion
  blocker: Required qwen3-coder:480b-cloud lane invalid: actual_model=kimi-k2.6 does not match requested decorrelated family

## Persistent Agent

- `palantir-pilot` status=running fresh=True
