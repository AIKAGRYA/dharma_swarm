# Agentic Frontier Audit & Future-Proofing Roadmap — 2026-07-01

**Scope:** a multi-dimensional scan commissioned to answer one question — *is the
agentic-patterns work (atlas + ingestion + zeitgeist→memory bridge) the best,
most future-proof system we can build, and where does it fall short of the
2025-2026 bleeding edge?* Four independent audit passes (diff correctness +
governance, semantic/architecture, repo-wide loop-closure, and frontier
research) fed this synthesis.

> **Docs decay — check before citing (A6).** This is a dated point-in-time
> snapshot. Verdicts are pointers to code, not guarantees; re-verify before
> treating any line as settled.

Companion: [`docs/architecture/AGENTIC_PATTERNS_ATLAS.md`](../../docs/architecture/AGENTIC_PATTERNS_ATLAS.md).

---

## Part A — Corrected picture of the current system

The first-pass atlas understated the substrate. A deeper capability inventory
found the repo already implements, at real depth, several things a flat pattern
list misses:

| Capability | Reality found | Maturity |
|---|---|---|
| Reflection / self-correction | `reflexion.py` (verbal RL), `neural_consolidator.py` (advocate/critic), `telos_gates.check_with_reflective_reroute` (critique→revise→recheck) | Real, not "post-hoc only" |
| Behavioral adaptation | `trajectory_collector`→`strategy_reinforcer`→`training_flywheel` (score→UCB-select→prompt-inject) | Real; zero *trained-weight* by design |
| Memory | tiered surfaces + `sleep_time_agent.py` (Letta-style background hygiene) + `consolidation.py` | Strong |
| Eval / arena | frozen sealed-label taskpack + DPI (correctness-gated decorrelation) + Council verification | Strong |
| MCP | `mcp_server.py`, `dharma_context_mcp.py`, `chetana/mcp_server.py` | Partial (servers exist; no dynamic discovery) |
| Guardrails | 8 telos gates + 25-principle SHA-signed kernel + injection/credential detection | Strong |

**Net assessment:** the system sits at roughly **60-65% of the 2025-2026
bleeding edge** — production-grade on memory, guardrails, arena/eval, and
coordination; genuinely thin on *explicit multi-path reasoning* and
*first-class composable cognition organs*. The corrected atlas tally is
13 STRONG · 7 PARTIAL · 1 out-of-scope.

---

## Part B — Audit of what this PR shipped (findings + resolution)

Four findings survived adversarial review; all are resolved in-branch.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | **CRITICAL** | Rejected zeitgeist signals re-proposed **every hour forever** — the bridge never consulted the decision ledger, so a human REJECT was forgotten next cycle (silent signal ping-pong). | `load_settled_atom_ids()` now reads `zeitgeist_promotion_decisions.json`; ACCEPT/REJECT atom_ids are filtered out before proposing (DEFER intentionally resurfaces). Tested cross-cycle. |
| 2 | HIGH | Duplicate-signal accounting broke the queue invariant (`total ≠ proposals + blocked`). | Rewrote counting; invariant `total == proposals + blocker_occurrence_count` now holds and is unit-tested. |
| 3 | MEDIUM | `state_dir` path traversal (`expanduser()` doesn't canonicalize `..`). | Added `.resolve()`. |
| 4 | LOW | Write-site heuristic misclassified the review artifact as a memory writer (CI regression). | Hoisted the render call out of the write expression; write is now correctly `generated_artifact`. |

**Governance floor verified:** exhaustive write-site audit confirms the bridge
writes **only** under `meta/knowledge_ops/` — never MemoryKernel, canon, or any
authority store. Post-review (Codex App), the gate set was corrected to the FULL
structural battery — HUMAN_REVIEW + PROVENANCE + CONFLICT + **PRIVACY** +
**CANON_POLICY** + LINKING — so external public content cannot be promoted
without a privacy/canon check; nothing auto-accepts. Proposals carry
`truth_state: observed` (the honest state for an external observation, and the
state the promotion executor requires — the earlier `unverified` was an invalid
`TruthState` that silently made every proposal non-promotable). The One-Wire
invariant (internal artifacts never touch archive fitness) holds: promotion is
human-gated with zero auto-advance path.

**Loop-closure honesty:** this wiring **extends Loop 5 (Zeitgeist Scanner)** but
does **not** fully close it. Sense✓ Interpret✓ Constrain(propose)✓, but
**Act/Adapt is still open** — human decisions do not yet feed back to tune scout
source weights or triage. Finding #1's decision-memory is the first adapt-arm
link; full closure (decision→scout-weight feedback) remains a follow-up.

---

## Part C — Future-proofing roadmap (ranked by leverage)

The five highest-leverage moves to reach the bleeding edge, each mapped to what
exists today:

### 1. Self-consistency / multi-path reasoning (Pattern 17) — HIGHEST
**Gap:** grep finds zero CoT/ToT/self-consistency orchestration; reasoning is
single-trajectory, model-delegated. **Why it's #1:** N-sample-and-vote is the
most direct way to add *decorrelated* reasoning at the single-agent scale — it
serves the Transcendence Principle's error-decorrelation + quality-aggregation
conditions arithmetically. **Build:** `cognition/reasoning.py` — N samples at
temperature, verify/vote/synthesize, spine-routed, benchmarked on the arena
under budget parity. This is Phase 2 of the proposed cognition track and should
lead it.

### 2. General goal→subtree planning (Pattern 6)
**Gap:** planning is domain-specific (`auto_research/planner.py`) or manual
genome authoring; no reusable decomposer. **Why:** decomposition unlocks skill
selection (route subgoals to the best agent) and error isolation. **Build:**
`cognition/planner.py` generalizing the research planner; pair with
goal-monitoring so goals close, not just start.

### 3. Close Loop 5's adapt-arm (decision → scout feedback)
**Gap:** human ACCEPT/REJECT decisions are now remembered (this PR) but do not
yet tune the scout. **Build:** feed rejection/acceptance rates back into
`world_radar` source weights / triage thresholds so the radar *learns* which
sources earn attention — turning a one-way ingest into a closed cybernetic loop.

### 4. Token-aware context engineering + active compaction
**Gap:** context budgeting is **character**-based, not token-aware; no active
LLM-driven compaction or KV-cache-aware design; sub-agent context isolation is
implicit. **Why future-proof:** context is the primary lever for long-horizon
agents in 2026. **Build:** token-count the `ContextCompiler` budgets; add
abstractive compaction; add a monitor proving sub-agent context isolation.

### 5. Modern eval breadth + RLVR on-ramp
**Gap:** the arena is excellent but 24 frozen tasks, deterministic oracles only;
trajectory collection exists but no rejection-sampling/RLVR/GRPO on-ramp.
**Build (corpus-only, no training):** widen the taskpack toward SWE-bench-Verified
/ tau-bench-style tasks; add rejection-sampling over the existing
`trajectory_collector` output as the honest first rung toward verifiable-reward
training — staying zero-weight until the arena produces labels.

**Lower-priority but noted:** dynamic MCP tool discovery (Pattern 10);
proposal-artifact history/archiving (currently overwritten each cycle);
uncertainty quantification + abstention thresholds on the guardrail layer;
computer-use/streaming-interruptible agents.

---

## Part D — Single biggest risk & opportunity

**Biggest risk (now mitigated):** silent signal ping-pong — an unbounded
human-time drain where rejected signals reappear forever. Finding #1's
decision-memory closes the acute version; the residual is that the proposal
artifact is still overwritten each cycle (no history). *Recommend:* timestamped
proposal snapshots.

**Biggest opportunity:** the system already has the *hard* parts — a frozen
verifiable fitness arena, a decorrelation-power index that gates on correctness,
behavioral-RL trajectory plumbing, and a governance spine. The missing piece is
**explicit multi-path reasoning feeding that arena**: once `cognition/reasoning.py`
produces decorrelated trajectories and the arena scores them under budget parity,
the DPI can measure real per-agent lift — turning the whole stack from
"instrumented" into "self-improving with evidence." That is the shortest path
from 60-65% to genuinely bleeding-edge.

---

*Provenance: 4 parallel audit agents (diff-correctness, semantic-architecture,
repo-loop-closure, frontier-research) + a capability inventory sub-agent,
synthesized 2026-07-01. All Part-B fixes are committed and tested in-branch.*
