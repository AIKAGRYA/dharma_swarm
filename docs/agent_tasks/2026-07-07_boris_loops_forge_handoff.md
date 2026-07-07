# FORGE HANDOFF — the 10 Boris-style loops dharma_swarm needs now

**Date:** 2026-07-07 · **Author:** Fable 5 session (gap-check + gates session)
**For:** any fresh executing session (Claude Code, codex, or swarm) with repo + shell access
**Prereqs on disk:** PR #819 (audit gap-check), PR #822 (hygiene gates) — read their descriptions
before building; the gates they land are load-bearing verifiers for several loops below.

---

## 0. Doctrine (read once, apply everywhere)

A **loop** here means the Boris Cherny / Anthropic agentic loop: *context → action →
VERIFIER → repeat until green*, with the verifier as the entire source of trust.
The 2026-07-06/07 audit trail proved this empirically in this repo: every entropy class
that permanently died, died by mechanism-verifier; every class that recurred had only
doctrine or campaigns. The merge lane (38 CI checks + Mike) is the best loop in the
estate; the thinkodynamic director (agent loop, zero verifier) is the worst.

**Admission rule (hard):** a loop may be built only if its verifier fits in one sentence
a machine can check. If you can't write that sentence, it is not loop work — it is
session work for a strong model with the operator present.

**Harness laws (every loop, no exceptions):**
1. **One door.** Loop output = small PRs into main through full CI, or receipts under
   `~/.dharma/`. Never long-lived branches, never direct pushes, never repo-committed
   runtime receipts.
2. **Net-zero exhaust.** Every loop iteration ends artifact-net-zero outside its one
   deliverable: ephemeral worktrees removed (`git worktree remove` in a `finally`),
   scratch in `/tmp` or `~/.dharma/`, no stray files. The worktree-budget checker
   (`scripts/governance/check_worktree_budget.py`, PR #822) will publicly shame you
   in `make onboard` otherwise.
3. **Ungameable verifiers.** A loop must not be able to satisfy its verifier by
   weakening it: no xfail-ing tests, no `|| true`, no editing the checker, no editing
   baselines/allowlists except to SHRINK them. Enforce by prompt AND by making the
   verifier read-only to the loop where possible (CI-side verifiers are best).
4. **Kill switch + budget.** Every loop reads an enable flag and a per-run cap from
   `~/.dharma/loops/config.json` (create it; e.g. `{"burn_down": {"enabled": true,
   "max_prs_per_night": 5}}`). No cap, no loop.
5. **Cheap models inside, frontier outside.** Inner-loop iteration runs on the free/cheap
   lanes via `runtime_provider` (THE ONE WAY — never hardcode a model). Frontier
   intelligence is spent designing/adjudicating verifiers only.
6. **Receipts.** Every run appends one JSON line to `~/.dharma/loops/<loop>/runs.jsonl`:
   `{ts, items_attempted, items_green, prs_opened, verifier_before, verifier_after}`.
   A loop with no receipts is presumed dead.
7. **Surface respect.** Check `docs/governance/ACTIVE_TRACK.yaml` owned_surfaces before
   editing; run `gh pr list --state open` for collisions; pre-commit hooks require
   Python ≥3.10 on PATH (`PATH="$REPO/.venv/bin:$PATH" git commit` — system python3
   is 3.9 and produces FAKE hook failures).
8. **Disposal stays operator-gated.** Loops prepare deletions and nag; a human clicks yes.

**Build order:** Loop 1 first (it is the template all others copy), then 2 and 10
(the outer-loop spine), then any order. Do NOT build all 10 in one session — one loop,
proven green for 2 runs, then the next. A loop factory that ships 10 unproven loops is
the exact slop pattern this doc exists to kill.

---

## Loop 1 — Debt burn-down loop (the template)

- **What:** picks ONE mechanical finding per iteration and fixes it: ruff full-ruleset
  findings (`ruff check dharma_swarm/ --select=E,F,W --ignore=E501,W291,W293` — 237 at
  time of writing), misleading xfails (7 organism/swarm pinning the dead instant-HOLD
  policy; 8 TUI xfails whose reason string is false — fix by stubbing
  `_can_route_to`/`_provider_ready`, see PR #819 §2.1), stale doc line-cites
  (`EVOLUTION_PROPOSAL_GATE_CONTRACT.md` ~L1543 → symbol anchors, same fix in
  `proposal_gate_probe.py` docstring).
- **Verifier (one sentence):** the targeted finding count strictly decreases AND
  `make test-smoke` + full CI stay green.
- **Inner loop:** pick item → fix → run focused tests + ruff → open small PR (≤ ~50
  lines diff) → next item.
- **Outer loop:** nightly cron/launchd, cap 5 PRs/night; morning: operator merges greens.
- **Guardrail:** deleting a test/assertion or adding an xfail/noqa/allowlist entry is
  FORBIDDEN as a "fix" — the verifier must improve by real repair only.
- **Done when:** ruff full ruleset = 0 (then widen the CI gate's `--select` in
  `tests.yml` — the comment there documents this exact promotion), xfail reasons true,
  cite drift gone.

## Loop 2 — Machine hygiene loop

- **What:** operationalize PR #822's bricks. Run `check_worktree_budget.py --strict
  --receipt`; diff worktree/branch inventory against the janitor + readiness receipts
  (`reports/governance/branch_janitor_2026-07-04.md`: 172 receipted-deletable branches;
  `reports/governance/worktree_readiness_2026-06-30/`); emit ONE consolidated
  "approve these deletions" list with exact commands.
- **Verifier:** budget receipt fresh (<24h) AND worktree count non-increasing
  week-over-week AND every proposed deletion cites a prior campaign receipt.
- **Inner loop:** sense → compare → prepare delete-list → nag (onboard renders it).
- **Outer loop:** launchd daily. **Act stays one-touch operator yes** (Harness law 8).
- **Done when:** count ≤ budget (8) and stays there for 30 days.

## Loop 3 — Test-desert coverage loop

- **What:** the repo's test-to-file ratio fell 25.6% → 18.3% (Mar→Jul). Target named
  deserts first: `model_defaults.py` (routing hot path, zero dedicated tests),
  the TUI submit→runner path (zero passing coverage), `terminal_commands/diagnostics.py`
  (`cmd_invariants` untested; its broad `except Exception → silent zeros` pattern needs
  characterization tests), then coverage-guided.
- **Verifier:** `pytest --cov` percentage on the target module strictly increases AND
  new tests fail when the covered behavior is mutated (spot-check with one deliberate
  local mutation, reverted before PR — mutation-check the test, not the code).
- **Guardrail:** no snapshot/tautology tests (asserting the placeholder — the C2 trap).
- **Done when:** every routing/dispatch hot-path module has a dedicated test file.

## Loop 4 — Mismatch-map truth loop

- **What:** make `INTERFACE_MISMATCH_MAP.md` structurally unable to lie (audit C3).
  Steps the loop grinds through: delete the false "Guardian Crew auto-updates" header;
  reconcile header vs table (NEW-12 is open — say so); add every open item to
  `docs/interface_mismatches.yaml` with a pinned test or `fixed_in` SHA so
  `mismatch_registry.py`'s guard stops being a permanent no-op; then invert (YAML
  canonical, .md generated).
- **Verifier:** a consistency checker exits 0 — header/table/YAML agree, and every
  `status: resolved` entry's `fixed_in` is an ancestor of HEAD
  (`git merge-base --is-ancestor`).
- **Note:** the checker itself is the first deliverable (frontier-session work);
  the grind afterwards is cheap-model loop work.
- **Done when:** the checker is in CI and green.

## Loop 5 — MI regression loop (paper-alive loop)

- **What:** nightly re-verification of the R_V paper's standing claims so the research
  stays alive unattended. Runs the canonical pipeline
  (`~/"ALL MECH INTERP"/mech-interp-latent-lab-phase1/scripts/p0_canonical_pipeline.py`)
  on pinned model+seed+data hashes; compares key metrics against pinned tolerances.
- **Verifier:** every pinned claim reproduces within tolerance; receipt (metrics + hashes
  + git SHA of lab repo) written to `~/.dharma/loops/mi_regression/`.
- **Boundary (hard):** experiments live in the LAB repo; only receipts cross into
  dharma_swarm awareness. No agent writes conclusions/wiki/paper text — measurement
  only (the C5 proxy-laundering lesson).
- **First session task:** operator + strong model pin the claim list + tolerances
  (this part is NOT loop work).
- **Done when:** 7 consecutive nightly green receipts; then extend to new-checkpoint
  sweeps (same harness, new model hashes).

## Loop 6 — Trading receipt loop (the revenue verifier)

- **What:** the one revenue lane with a Cherny-grade verifier (fills/P&L: external,
  numeric, fast, unarguable). Phase A is DISCOVERY, not trading: locate the existing
  trading-agency code (start: `cashclaw/revenue-hydra-v1` worktree/branch), audit what
  actually executes, and wire a **paper-trading** loop that writes signed daily P&L
  receipts to `~/.dharma/loops/trading/`.
- **Verifier (phase A):** a dated P&L receipt exists per market day, derived from
  broker/paper API records (not self-reported numbers — the C2 fabricated-scalar
  lesson applies with money).
- **Promotion gate (operator-only):** N≥20 consecutive paper receipts + explicit
  operator sign-off before ONE dollar of real capital; real-capital caps live in the
  kill-switch config. Never let an agent raise its own cap.
- **Honesty note:** trading P&L is external *verification*, not "external humans
  served" — it funds the mission; it doesn't satisfy the spine objective by itself.
  Charter as a track when phase A is green (a new project is a new track).

## Loop 7 — Doc-truth loop (claims-with-checkers)

- **What:** grind through doctrine claims that assert mechanisms ("enforced", "auto-
  updates", "canonical front door", dormant organs presented as live — audit C5/C6) and
  either (a) wire the claim to an existing checker, (b) reword it to truth, or
  (c) mark it `STALE-UNVERIFIED`. Known queue: CLAUDE.md worktree line → point at the
  new checker; Key Abstractions live/staged markers; "two meanings of R_V" note;
  DEVIN.md §9 → pointer, not restatement; QWEN.md → defers-to stub;
  `memory_kernel/writer_specs.py:560-577` stale entries.
- **Verifier:** the docops/canonical-guard suite exits 0 AND a claims-index file maps
  each mechanism-claim → checker-or-STALE-marker with zero unmapped claims.
- **Guardrail:** CLAUDE.md edits are PROPOSED as a PR the operator merges — never
  applied silently.

## Loop 8 — Excretion loop (dead-code subtraction)

- **What:** the next maturity stage is subtraction. Known-dead queue from the audit
  (verified 2026-07-06): `providers_extended.py`'s three orphaned provider classes
  (name-collision hazard with working same-name production classes — delete WITH their
  tests), the unmounted GraphQL stub package, `worktree_second_pass_list.py`,
  `verify_quality_membrane.py`, the 10 `a2a_block_*` incident scripts → `git mv` to
  `scripts/governance/incidents/`. Then feed from import-graph analysis.
- **Verifier:** repo-wide grep shows zero non-test references to the deleted symbol
  before the PR, and full CI green after — deletion PRs get NO other changes mixed in.
- **Cap:** one deletion target per PR; 3 PRs/night max. Subtraction earns trust slowly.
- **Done when:** never — this loop runs forever. That's the point.

## Loop 9 — PR shepherd loop (close the review side of Mike)

- **What:** Mike merges; nothing systematically reviews. For every open PR: run the
  repo's own review checklist (mismatch impact, Coherence Delta completeness, test
  coverage of behavior changes, surface ownership) and post ONE structured review
  comment; flag stalls (>72h) with a state recommendation (merge/rebase/close-with-
  reason) into the morning briefing.
- **Verifier:** every open PR has a review receipt newer than its last commit;
  open-PR median age stays <7 days (it is 2 days today — keep it there as the fleet
  scales).
- **Guardrail:** the shepherd never merges and never approves — it reviews. Mike +
  operator keep merge authority.

## Loop 10 — The overnight composer (outer loop of loops)

- **What:** the spine that runs loops 1/3/4/7/8 while the operator sleeps. Reads
  `~/.dharma/loops/queue.jsonl` (each line: `{loop, item, verifier_cmd}`), executes
  each item in an EPHEMERAL worktree (create → work → PR → remove), respects all caps,
  writes the morning briefing: greens to merge, reds with reasons, verifier trendlines
  (ruff count ↓, coverage ↑, worktree count ↓, dead files ↓).
- **Verifier (of the composer itself):** after every run — zero leftover worktrees vs
  pre-run baseline, every opened PR has completed CI, receipts written, caps respected.
  A composer run that leaves exhaust FAILS its own verifier and halts the schedule.
- **Build note:** do NOT resurrect the thinkodynamic director for this. Build small and
  boring: a ~200-line runner + launchd plist. The existing `codex_overnight.py` /
  holon wake machinery may be salvageable — evaluate, don't assume.
- **This is the compounding asset.** Everything above multiplies through it.

---

## NOT loops (do not let an eager session loop-ify these)

Architecture consolidation (DharmaGraph owns it), the two-ReAct-engine merge, paper
writing/interpretation, revenue product design, anything touching live capital beyond
Loop 6's receipted paper phase, CLAUDE.md rewrites, and disposal execution (always
operator-gated). Their verifiers are human judgment; keep them in sessions.

## Success metric for the whole program

One number per week in the morning briefing: **verifier-green loop-days / total
loop-days**, plus the four trendlines (ruff ↓, coverage ↑, worktrees ↓, open-PR age →).
If a loop is red or silent 3 consecutive days, disable it and file one issue — a dead
loop lying about being alive is worse than no loop (see: chetana metabolic clock,
docops reconcile's 102 silent failures — liveness-check the loops themselves).
