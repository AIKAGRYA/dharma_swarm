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
  summary: All 10 criteria are supported by the attached bytes. The implementation confines MiroFish and stochastic engines to untrusted scenario generation (spec IV.2, research ledger engine table). V0 executes committed graph/types.py bytes via AST-validated isolated loading without importing graph/__init__.py (replay.py::_run_checkpoint_type, replay_worker.py inert package shells). WorldV1/ReplayBundleV1 enforce registered-data-only contracts with strict direct-object type checks, exact-key validation,
- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=True verdict=approve score=100 actual=kimi-k2.5
  summary: All PM0-1 through PM0-9 criteria satisfied with executable evidence. Round 2 blockers addressed: tests now explicitly construct copied FreshProcessVerification, copied Claim, serialized authority-shaped dict, and private _OperationalAuthorization dataclass; all fail closed without live witnesses or evaluator registry state. 100-process receipt shows unique PIDs, consistent semantic digests, and exact source byte digests matching the committed manifest. MiroFish correctly confined to untrusted sc
- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=True verdict=pass score=100 actual=qwen3-coder:480b-cloud
  summary: All PM0 criteria satisfied with concrete evidence. No blockers remain for HARNESS_PROVEN status on exact replay manifest.
- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=True verdict=pass score=100 actual=deepseek-v4-pro
  summary: All PM0-1 through PM0-9 criteria are supported by executable evidence, strict data contracts, isolated worker execution, fresh-process verification, and fail-closed promotion gates. The implementation boundaries are respected, non-claims are explicit, and no blocker remains. PM0-10 is pending council completion and is not a reason to reject.
- `minimaxm3` `ollama:minimax-m3:cloud` ok=True verdict=approve score=100 actual=minimax-m3
  summary: V0 implements a narrow, fail-closed proof membrane around the current RunCheckpoint.fork defect. All ten PM0 criteria are satisfied by executable evidence: MiroFish and other stochastic engines are explicitly quarantined to Generated scenario candidates with no path to promotion authority; the worker executes only the six declared source files (with recorded byte digests) and bypasses the broad graph/__init__.py; the data contract rejects tampering, unknown properties, widened imports, declared
- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=pass score=100 actual=nvidia/nemotron-3-ultra-550b-a55b:free
  summary: All PM0-1 through PM0-9 criteria satisfied with executable evidence. The fork-alias defect reproduces in 100/100 fresh processes with identical semantic digests. The corrected deep-copy control discriminates (parent isolation satisfied). All attack vectors (bundle/manifest drift, fixture drift, path substitution, direct object bypass, undeclared source execution, unknown properties, and declared nondeterminism fail closed. Refutes cannot promote. ParityScore(52) cannot discharge ProductionReady.

## Persistent Agent

- `palantir-pilot` status=running fresh=True
