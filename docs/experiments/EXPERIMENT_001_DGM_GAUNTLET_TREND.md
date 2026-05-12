# Experiment 001 — DGM Gauntlet Trend (Karpathy-style direct comparison)

**Status:** Designed 2026-05-12 · ready to run after first 3 nightly gauntlet runs land
**Owner:** John Shrader (dharma_swarm)
**Branch landing this:** `feat/gauntlet-external-outcome-rewire`

---

## 1. Background

The 2026-05-12 SOTA audit confirmed dharma_swarm already ships:

- **`benchmarks/gauntlet.py`** — 5-tier evaluation harness with externally
  grounded tier-1 tasks (BTC price ±1%, provider liveness, etc.).
- **`dharma_swarm/dgm_loop.py`** — Sakana-DGM-style sample → propose → gate
  → apply → benchmark → archive loop, with `novelty_pressure=0.7` (matches
  the [Sakana DGM paper default](https://arxiv.org/html/2505.22954v3)).
- **`dharma_swarm/telemetry_plane.py`** — `ExternalOutcomeRecord` schema
  + persistent SQLite store (`record_external_outcome` / `list_external_outcomes`).
- **`dharma_swarm/loop_supervisor.py`** — intervention ladder
  `LOG_WARNING → PAUSE_LOOP → REDUCE_SCOPE → ALERT_DHYANA`.

What was missing was a single **wire**: gauntlet results were persisted to
`~/.dharma/gauntlet/history.jsonl` but never reached the
`ExternalOutcomeRecord` substrate that DGM fitness and the loop supervisor
consume. PR `feat/gauntlet-external-outcome-rewire` adds
`dharma_swarm/gauntlet_telemetry.py` and a `--record-external` flag to close
the loop.

This experiment validates that the closed loop produces a measurable,
externally-grounded improvement signal — the central claim of bleeding-edge
agentic-evolution work ([Sakana DGM](https://sakana.ai/dgm/),
[Karpathy autoresearch](https://github.com/karpathy/autoresearch),
[AlphaEvolve](https://deepmind.google/blog/alphaevolve-impact/)).

---

## 2. Hypothesis

**H1 (primary):** Running the gauntlet nightly with `--record-external`
while DGM is active in shadow mode produces a positive tier-1 correctness
slope of **≥ +0.005 / day** over a 14-day window.

  *Effect size rationale:* +0.005/day × 14d = +7pp total correctness, which
  is large enough to be operationally meaningful but small enough to be
  plausibly reachable from cheap proposals. Karpathy autoresearch
  improvements over comparable horizons sit in this range.

**H2 (secondary):** When tier-1 ground-truth slope crosses below
−0.01 / day, the loop supervisor emits a `GAUNTLET_TIER1_REGRESSION` alert
within one supervisor tick (default 60 s).

**H3 (tertiary):** DGM proposals that improve composite gauntlet score
also improve tier-1 correctness (no Goodhart drift onto LLM-graded tiers).

---

## 3. Null Hypotheses

- **H0a (vs. H1):** Slope is in [−0.005, +0.005] / day — i.e., the wired
  loop produces no detectable improvement signal over the window. This
  would indicate the DGM proposals are no better than random and the wire
  itself adds no value.
- **H0b (vs. H2):** Synthetic regression injected via test fixture does
  *not* trigger the supervisor alert (wire broken).
- **H0c (vs. H3):** Composite-improving proposals show ≤ 0 mean
  tier-1 correctness delta (Goodhart on LLM-graded tiers).

---

## 4. Method

### Procedure

1. **Day 0:** Land PR; schedule nightly gauntlet via `schedule_cron`:
   `python -m benchmarks.gauntlet --all --record-external` at 03:00
   Asia/Makassar.
2. **Days 1–14:** Run DGM in shadow mode (`apply_in_shadow=True`); allow
   proposals to be persisted to archive but **not** applied to live agents.
3. **Day 7 mid-check:** Inspect `~/.dharma/runtime.db`
   `external_outcomes` table, run `check_gauntlet_trend_sync()` ad-hoc.
4. **Day 14:** Compute final slope per tier kind; freeze data; classify
   against thresholds.

### Measurement

- Primary metric: `gauntlet_telemetry.compute_trend_slope` on
  `OUTCOME_KIND_GAUNTLET_TIER1` outcomes over the 14-day window.
- Decision rule comes from the supervisor thresholds (improvement
  ≥ +0.005, regression ≤ −0.01) — **same** thresholds humans and
  machines use. No separate analysis-only test.
- Direct metric comparison, **no p-values, no Mann-Whitney**. This is the
  explicit Karpathy autoresearch convention: the slope itself is the
  signal and the threshold is the decision criterion.

### Pre-registered analyses (and *only* these)

- (A) Slope of `gauntlet.tier1.correctness` over 14 days.
- (B) Per-day slope of `gauntlet.composite` for cross-check (H3).
- (C) Count of `GAUNTLET_TIER1_REGRESSION` alerts after fixture injection
  on day 14 (H2 confirmation).

Any post-hoc analysis must be labeled "exploratory" in the report.

---

## 5. Stopping Rules

Stop the experiment early **only** for these pre-declared reasons:

1. **Hard regression**: tier-1 slope ≤ −0.02 / day for 3 consecutive days
   (double the supervisor threshold) → pause DGM, investigate.
2. **Outcome gap**: gauntlet runs persist to `history.jsonl` but no
   matching rows appear in the `external_outcomes` table for >24 h →
   the wire is broken, fix before continuing.
3. **Saturation**: tier-1 correctness ≥ 0.95 on 3 consecutive runs →
   experiment succeeded earlier than expected; freeze data, document.
4. **Cost runaway**: `cost_tracker` reports DGM-attributed spend > 5× the
   pre-experiment baseline for 2 consecutive days → pause to investigate
   `economic_fitness` integration.

No other early-stop rules. **No peeking at the slope before day 7.**

---

## 6. Falsification Criteria (when do we say "the rewire doesn't work")?

The wire is **falsified** if any of the following hold at day 14:

1. Fewer than 10 tier-1 outcome records were persisted (data plumbing
   broken — gauntlet ran but `--record-external` didn't deliver).
2. Tier-1 slope ∈ [−0.005, +0.005] / day **and** composite slope is also
   in that band (the closed loop produces no signal that direct
   `history.jsonl` reading wouldn't already produce — i.e., the wire
   adds no information).
3. H2 fixture injection fails to trigger a `GAUNTLET_TIER1_REGRESSION`
   alert (supervisor wire broken).

The wire is **supported** if:

- Tier-1 slope ≥ +0.005 / day over the 14-day window, **and**
- The supervisor alert fires correctly on synthetic regression, **and**
- DGM-attributed proposals correlate non-negatively with tier-1 gains.

---

## 7. Threats to Validity

- **Confounder — DGM novelty schedule:** if `novelty_pressure` drifts during
  the window, slope reflects schedule, not wire. Mitigation: pin
  `novelty_pressure=0.7` for the experiment.
- **Confounder — gauntlet task pool drift:** if task definitions change
  during the window, scores are not comparable. Mitigation: freeze
  `benchmarks/gauntlet.py` task set with `git tag exp-001-baseline` at day 0.
- **Confounder — external provider flakiness:** tier-1 includes live API
  calls (BTC price, etc.). Runs that fail because of provider outage
  should be excluded as `status="failed_external"`, not counted as
  correctness=0. *Not yet implemented*; current code counts outage as
  failure. Pre-registered exploratory analysis: re-compute slope after
  excluding runs where >50% tier-1 tasks hit a `failure_mode` containing
  `"provider"` or `"timeout"`.

---

## 8. Predicted Outcomes (forced commitment)

Written before running the experiment, to avoid hindsight bias:

| Metric | Predicted value at day 14 | 95% interval (subjective) |
|---|---|---|
| Tier-1 slope (per day) | +0.006 | [+0.001, +0.012] |
| Composite slope (per day) | +0.004 | [0.000, +0.010] |
| # `GAUNTLET_TIER1_REGRESSION` alerts during normal runs | 0 | [0, 1] |
| # alerts after fixture injection | 1 | [1, 1] |
| DGM proposals applied to archive | ≥ 15 | [10, 40] |

If actual results land outside the 95% interval on >1 metric, that is a
**signal the model of the system is wrong**, not just that the experiment
failed. Update [`docs/CYBERNETIC_LOOP_MAP.md`](../CYBERNETIC_LOOP_MAP.md)
accordingly.

---

## 9. References

- [Karpathy autoresearch (Mar 2026)](https://github.com/karpathy/autoresearch) — direct metric comparison, fixed wall-clock budget.
- [Sakana Darwin-Gödel Machine (May 2025)](https://arxiv.org/html/2505.22954v3) — novelty_pressure=0.7, MAP-Elites archive, SWE-bench 20%→50%.
- [DeepMind AlphaEvolve (May 2025)](https://deepmind.google/blog/alphaevolve-impact/) — Gemini Flash breadth + Pro depth evolutionary code search.
- [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve) — open MAP-Elites + island architecture reference.
- [SPC NeurIPS 2025](https://papers.nips.cc/paper_files/paper/2025/hash/cb7baa005c239c1c7c4098c2a9e00450-Abstract-Conference.html) — adversarial self-play critic.
- [Voyager (MineDojo)](https://voyager.minedojo.org) — skill library + auto curriculum.
- Internal: `docs/CYBERNETIC_LOOP_MAP.md` (2026-05-05 audit) — confirms the 13 loop edges that this wire closes.
