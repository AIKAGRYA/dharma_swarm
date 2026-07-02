# Live Research Digest — Signal Synthesis Pipeline Trial Run

**Date:** 2026-07-01
**Nature of this artifact:** this IS the output type the "Signal Synthesis" pipeline
(proposed alongside this digest) is meant to produce continuously — a single
research/build-recommendation cycle run once, by hand, at conversational speed
instead of hundreds of times a day, automated. It exists to show the shape of
the output and to honestly record what a real run surfaces, good and bad.

**Companion artifacts:**
- `dharma_swarm/coordination/panel_diversity.py` — the one piece of code this
  run's findings justified building immediately (tested, see below).
- `docs/governance/proposed_tracks/signal-synthesis-desk-2026-07.yaml` — the
  corrected DRAFT track proposal for the rest of the system.

---

## What this run actually did

1. Live web search + fetch for current (2026) research on multi-agent
   orchestration, decorrelation, and consensus — the swarm's own core niche.
2. Attempted to clone/read a real GitHub implementation for grounding —
   **blocked** by this sandbox's outbound proxy (same restriction hit earlier
   ingesting arxiv/HN sources; see Finding 1).
3. Ran a 4-lens adjudication panel (Skeptic, Builder, Strategist, Diversity
   Auditor) against a candidate proposal ("build a Signal Council"), each
   grounded in the live research + the actual current repo code.
4. Triangulated every panel finding against real repo state (file:line
   citations, not assertions).
5. Built and tested the single highest-leverage code artifact the panel
   converged on.

---

## Finding 1 (the most important one): a live hallucination, caught

While researching, one lead — **"Mixture-of-Models: Unifying Heterogeneous
Agents via N-Way Self-Evaluating Deliberation"** (claimed: a "dynamic expertise
broker" + "quadratic voting consensus" letting small model ensembles match
frontier performance) — looked like the single most relevant find of the
session: a research validation of this repo's own Transcendence Principle.

A dedicated verification pass caught it as **fabricated or unverifiable**:
- The claimed companion GitHub repo (`peeramid-labs/nsed`) returns a clean
  **404** on direct fetch.
- The org's one *real* repo (`quorum-rs`, 0 stars) exists but never mentions
  quadratic voting or an expertise broker anywhere in its README.
- WebSearch's summarization layer produced confident, detailed, internally
  consistent technical claims (VRAM specs, a "knapsack problem" broker
  formulation, an 84% benchmark score) *identically worded* across many
  independent query phrasings — a strong confabulation signature, confirmed by
  attempting a direct fetch of the same claim against a known-real control
  paper ("More Agents Is All You Need," arXiv:2402.05120), which also returned
  proxy 403s, meaning **no claim in this environment can be verified by direct
  primary-source fetch at all** — only by cross-referencing independent
  secondary aggregators and checking claimed *artifacts* (repos, not prose)
  for existence.

**Why this is the most important finding, not a footnote:** this is a live,
concrete instance of exactly the risk a high-velocity ingestion pipeline must
defend against — a plausible, well-formatted, emotionally satisfying "find"
that is false. The technique that caught it — *attempt to verify a claimed
concrete artifact's existence, not just re-read more prose about it* — is a
load-bearing design requirement for the real system, not an optional nice-to-have.

## Finding 2: the adjudication panel itself reproduced the failure it judged

Independently, two of the four lenses (Skeptic and Diversity Auditor)
concluded — unprompted, without being told to look for this — that **the
panel's own construction** (4 role-prompted calls, all dispatched to one
underlying model) was itself an instance of the exact failure mode named in
the (separately, and this time genuinely verified) Ringelmann-effect and
memetic-drift research: same-model multi-persona debate produces no more
answer diversity than a single call.

This is not a minor caveat. It means: **the honest first output of this
research pipeline was a demonstration of its own necessary safeguard failing**,
caught only because the panel was told to be adversarial about itself. A
production version of this system needs that check running *automatically and
mechanically*, not dependent on a lens remembering to be self-critical. That
check is exactly what `panel_diversity.py` (built this session, tests below)
now provides.

## Finding 3: real, verified research (cross-referenced across independent sources)

| Finding | Verified? | Relevance |
|---|---|---|
| Ringelmann Effect in Multi-Agent LLM Systems (arxiv 2606.02646) | Cross-verified, multiple independent sources | 30 same-model agents ≈ 1 agent's diversity on MMLU-Hard; optimal team size often 3-5; non-monotonic (3 can beat 5) |
| Memetic Drift / QSG (Tanaka, Harvard/NTT, arxiv 2603.24676) | Cross-verified | Sampling-driven consensus is a "lottery," not reasoning, absent architectural diversity |
| Faramesh (arxiv 2601.17744) | Cross-verified | Deterministic PERMIT/DEFER/DENY execution-authorization control plane; fails safe to DENY on crash/timeout |
| PatchIsland (arxiv 2601.17471) | Cross-verified, strong convergence | Ensemble of diverse LLM agents + two-phase (crash-side, patch-side) dedup for continuous vulnerability repair; real AIxCC competition result: 31/43 (72.1%) fully autonomous |
| "Debate or Vote?" (arxiv 2508.17536) | Cross-verified | Voting drives most of multi-agent gain; debate alone doesn't provably improve expected correctness |
| "Nine Judges, Two Effective Votes" (arxiv 2605.29800) | Cross-verified | A 9-model, 7-family judge panel yields only ~2 independent votes' worth of signal; best single judge can match the full panel |
| "The Consensus Trap" (arxiv 2604.17139) | Cross-verified | Majority voting collapses once correlated/adversarial agents form a local majority; token-level interleaving more robust |
| X-MAS (arxiv 2505.16997) | Cross-verified | Heterogeneous-LLM multi-agent systems beat homogeneous ones by up to 47% on hard reasoning tasks |
| `lkaesberg/decision-protocols` (GitHub, 7 stars) | Directly fetched, real | Empirical voting-vs-consensus study for multi-agent LLM debate |
| "Mixture-of-Models: N-Way Self-Evaluating Deliberation" | **Unverifiable / likely fabricated** | See Finding 1 |

## Finding 4: environment constraint that changes the real design

Direct HTTP fetch (`WebFetch`, raw `git clone`, `curl`) to **arxiv.org and
github.com git-clone endpoints is blocked by this sandbox's outbound proxy** —
confirmed by testing even a known-real control paper and a plain Wikipedia URL.
`WebSearch`'s underlying fetch path is not blocked the same way. **This means a
production ingestion organ cannot assume raw HTTP egress works in every
execution environment it might run in** — it must treat a search-API-mediated
fetch path as a first-class transport, not a fallback, with raw fetch as an
enhancement only where available. This is new, concrete signal that should
change the Go scout's retry/fallback design, not a one-off inconvenience.

## Finding 5: the panel's verdicts, triangulated against real repo code

| Lens | Verdict | Load-bearing reason |
|---|---|---|
| Skeptic | DO NOT ELEVATE as originally specified | DPI's `decorrelation_bonus()` (`coordination/dpi.py:49`) is gated on `final_correct` — inapplicable to pre-verification thematic significance judgments, where no ground truth exists yet. Also: this panel is itself the counterexample (see Finding 2). |
| Builder | BUILDABLE NOW, with one *decision*, not a technical blocker | Theme clustering already mostly exists (`world_radar/analysis.py` `_movement_key`/`_movement_from_rows`) — title-key based, not semantic. `group_chat.py`'s `GroupChat` is a real, reusable debate scaffold. No Faramesh-style control plane exists — `telos_gates.py`/`DarwinEngine.gate_check` is the repo's existing fail-closed pattern; build one more small gate, don't invent new infra. ~1100-1400 LOC total for the full system. The one hard part: quadratic voting is statistically thin at N=3-5 and easy to fake-satisfy — and its only cited grounding (Finding 1) turned out to be unverifiable. |
| Strategist | TOO EARLY AS SCOPED | Real naming collision with the existing `council/council.py` `Council` (arena trace-verification, different job) — must rename. Should serve `research-depth` or `revenue-external-humans-served` (both at **zero** active tracks), not a 5th `substrate-nativeness` track (already at the WIP warn=5 threshold). Must integrate with, not duplicate, existing `signal_bus.py`/`signal_map.py`/`ginko_signals.py`/`world_signal_ingestor_go`. Complementary (not redundant) with the already-DRAFT `agentic-design-patterns-cognition-2026-07` track. |
| Diversity Auditor | DIVERSITY IS THEATER UNLESS FIXED | `provider_policy.py`'s `ProviderPolicyRouter` + `model_hierarchy.py`'s `CANONICAL_SEED_ORDER` already provide 18 genuinely heterogeneous providers across different labs (Ollama/GLM+DeepSeek+Kimi, Cerebras/Qwen, Google/Gemini, Mistral, Anthropic/Claude, OpenAI/GPT, ...). Nothing currently wires "lens role → distinct provider." `council/invariants.py`'s `meets_decorrelation()` (`MIN_EVALUATOR_FAMILIES=2`) is the right PATTERN to borrow (not the code — Council's own vocabulary excludes correctness/significance verdicts by design). |

## What was built this run (real, tested, not proposed)

`dharma_swarm/coordination/panel_diversity.py` + `tests/test_panel_diversity.py`
(8/8 passing) — a provenance gate that:
- assigns each panel "lens" role a genuinely distinct provider from
  `CANONICAL_SEED_ORDER` (`assign_diverse_lenses`)
- fails closed to `single_model_multi_persona` when fewer than 2 distinct
  provider families were actually dispatched, regardless of how the lenses'
  transcripts read (`check_panel_diversity`)
- additionally flags suspiciously convergent phrasing across lenses
  (dependency-free trigram-shingle Jaccard overlap) as a second, independent
  memetic-drift signal
- includes a regression test (`test_same_provider_every_lens_fails_closed`)
  that reproduces this exact session's own panel construction and proves the
  gate would have caught it

This is deliberately the *only* code shipped this run. The full pipeline
(theme clustering, debate scaffold wiring, vote aggregation, draft-YAML
writer, Faramesh-style write gate) is scoped as a DRAFT track — see the
companion proposal — pending the operator decisions the panel surfaced
(real vs. simulated model dispatch; correct spine objective; name that
doesn't collide with the existing Council).
