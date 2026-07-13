# Decorrelated Review Council

conviction_gate: **pass_fullness**
target_score: 100
critics: 6 required=6
score_min: 100
score_avg: 100.0

## Blockers

- none

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=True verdict=approve score=100 actual=glm-5.2
  summary: All eight required conditions verified against attached evidence. Attempt1 is present and typed failed. Final closeout is passed with six green gates and green negative control. Dependency-light and full plugin-aware suites remain distinct. Proof.py rejects fabrication, semantic mismatch, and unissued authority via named fail-closed codes. No council/model import path exists into PromotionEvaluator. MiroFish is classified as untrusted candidate source. Seven-source manifest pins df435af863e65128
- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=True verdict=approve score=100 actual=kimi-k2.7-code
  summary: Attempt 1 is preserved as failed; the final closeout passes with six green gates and a green negative control. Dependency-light and full plugin-aware suites remain distinct. proof.py and the test suite reject fabrication, semantic mismatch, and unissued authority. The seven-source manifest pins df435af863e651287de3f637509a45d59b133ad3, and the claim ceiling is HARNESS_PROVEN. All eight approval conditions are concretely satisfied.
- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=True verdict=approve score=100 actual=qwen3-coder:480b-cloud
  summary: All seven required verification criteria are met: attempt 1 preserved as failed, distinct full vs governed tests, HARNESS_PROVEN ceiling, model consensus is review-only, final governed result passes with six gates green, exact seven-source replay manifest pins df435af863e651287de3f637509a45d59b133ad3, and claim ceiling is exact-scope HARNESS_PROVEN.
- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=True verdict=approve score=100 actual=deepseek-v4-pro
  summary: All eight conditions verified: attempt1 failed, final closeout passed with six gates and control green, dependency-light and full tests distinct, proof semantics reject fabrication and mismatches, council output cannot mint authority, MiroFish untrusted, manifest pins df435af..., claim ceiling HARNESS_PROVEN. No blockers.
- `minimaxm3` `ollama:minimax-m3:cloud` ok=True verdict=approve score=100 actual=minimax-m3
  summary: All eight approval conditions verified against concrete evidence. Attempt 1 preserved as failed with two broad-suite gate failures plus sandbox denial; final closeout is typed passed with 6 gates green (33+84+22+12 tests plus diff/Ruff) and negative control green. Dependency-light (84/12) and full plugin-aware (102/22) suites remain distinct per RESEARCH_AND_VERIFICATION.md:104-113,181-188. proof.py rejects fabrication, modality/proposition/scope mismatch, and unissued capabilities via named cod
- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=approve score=100 actual=nvidia/nemotron-3-ultra-550b-a55b:free
  summary: All eight approval criteria verified: attempt 1 failed and preserved; final closeout passed with six green gates and clean scope; dependency-light and full plugin-aware tests remain distinct; proof semantics reject fabrication, semantic mismatch, and unissued authority; council/model output cannot mint evaluator permission; MiroFish/external simulators are untrusted candidate sources only; replay manifest pins df435af863e651287de3f637509a45d59b133ad3 across seven sources; claim ceiling is exact-

## Persistent Agent

- `palantir-pilot` status=running fresh=True
