# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 84
score_avg: 96.5

## Blockers

- glm52: score=95 < 100
- kimik3: verdict=revise

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=True verdict=pass score=95 actual=glm-5.2
  summary: Ten-node autocatalytic portfolio is honest, well-tested, and production-grade for its claimed local_rehearsal ceiling. Adapters do substantive read-only work; cross-feeds are causal and one-shot; structure-only and local-receipt-consistency are distinct non-authoritative types; no overstatement found in code, API, dashboard, or docs.
- `kimik3` `kimi_code:k3` ok=True verdict=revise score=84 actual=k3
  summary: Narrow local_rehearsal claim is internally consistent, honestly capped, fail-closed by design; but merge-relevant gates are self-reported, promotion obligations are prose not executable, and heartbeat evidence is unverifiable from the packet.
  blocker: Gate evidence (pytest 196/45/20, Next build, pre-commit suite) exists only as self-authored local_gate_receipt.json on a feature branch; the repo's own doctrine (safety-TCB claim_boundary: integrity != authenticity, only trusted-CI re-run counts) is not satisfied for this packet's merge signal.
  blocker: persistent_agent_evidence.json is self-reported (status/fresh asserted by the producer); the required fresh palantir-pilot heartbeat cannot be independently verified from the packet.
  blocker: Manifest proof_obligations for every future authority promotion are prose strings, not executable checks, contrary to the packet's own requirement of an executable proof obligation per promotion.
- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=True verdict=pass score=100 actual=kimi-k2.6
  summary: Ten-node portfolio validates topology at runtime, enforces read-only adapters with negative signal states, binds cross-feeds to ledger rows, separates structure-only from local-receipt consistency, and fails closed on forged evidence. No blockers.
- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=True verdict=pass score=100 actual=deepseek-v4-pro
  summary: All checks passed; no blockers remain.
- `minimaxm3` `ollama:minimax-m3:cloud` ok=True verdict=approve score=100 actual=minimax-m3
  summary: Local-rehearsal ceiling honored. Ten distinct adapters with project-specific source contracts; topology, ring, pages, and cross-feed closure enforced by validate_portfolio. Non-promoting states consistent across API and dashboard.
- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=pass score=100 actual=nvidia/nemotron-3-ultra-550b-a55b:free
  summary: Ten-node autocatalytic portfolio meets all declared claims: substantive read-only project adapters, closed signal ring with three typed cross-feeds exercised across two turns, structure-only and local mutable-receipt consistency as distinct non-promotable modalities, honest local_rehearsal ceiling, canonical substrate composition, and comprehensive adversarial test coverage with fail-closed semantics.

## Persistent Agent

- `palantir-pilot` status=running fresh=True
