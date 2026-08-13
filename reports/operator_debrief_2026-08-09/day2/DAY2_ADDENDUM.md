# Operator Debrief — Day 2 Addendum (2026-08-09, real todo list)

The operator supplied the real 8-item todo list after the day-1 debrief shipped. Same rules:
delegate through the system where possible, route around what's broken, receipts everywhere.
All 8 were submitted to the swarm task board (`POST /api/commands/task`, ids in board
snapshots) AND produced via fallback lanes where the swarm failed.

## Delegation scorecard — the real list

| # | Item | Swarm outcome | What you actually got | Where |
|---|---|---|---|---|
| 1 | Darshan syndication agent (5 sites, 3-5 registers, daily, self-evolving) | Dispatched, killed by 300s timeout + reconciler race | **Buildable spec**: `darshan_scribe` persona, 5 registers × 5 platforms (Medium excluded — API closed to new tokens), operator-gated publishing per charter, cron+launchd design, yaml-lite skill file, 7-day runplan. Platform APIs verified: Substack/LessWrong/HN have no self-serve write APIs → paste-queues; Bluesky/Mastodon fully automatable. | `darshan_syndication_engine_spec.md` |
| 2 | Shrama Capital hedge fund + 5 labs + top-20 platforms + signup recommendation | Same death | **Architecture on real prior art**: repo already ships `dharma_swarm/capital_lab/` (contracts, RiskGovernor, paper membrane, 21/21 tests). 5 named labs, vector fitness (not just PnL), paper-first hard gates, credential vault design. **Recommendation: Alpaca paper + Kraken Futures demo first (both free, no capital at risk)**; Coinbase-vs-IBKR deferred pending operator answers (jurisdiction, capital, tax, custody). | `shrama_capital_architecture.md` |
| 3 | Headless YouTube pipeline + first 3 videos | Same death | **Stack + scripts**: ElevenLabs→Remotion/Manim/VHS→ffmpeg→YouTube Data API, ~$22-30/mo, review-gated publish. 3 scripts written from real repo material. **Videos cannot be rendered/uploaded from this sandbox** — account/OAuth/phone-verification steps are an ~1-2h operator checklist in the doc. | `youtube_pipeline.md` |
| 4 | GEB anime gamified learning journey | Same death | **Full design doc** (~5,000 words): "The Eternal Golden Loop", 9 arcs, real-terminal-in-anime mechanic, XP only on mechanical receipts, licensing ledger, 3-milestone build plan. | `geb_anime_journey.md` |
| 5 | SIS development + steward + top-10 outreach + red team | Agent RAN (Claude Code lane, observed live) but its completion was **discarded** — `Invalid transition: pending -> completed` | **Plan grounded in the SIS corpus**: 6 projectors in the corpus's own build order, steward watch/evolve loop, 10 named outreach targets with verified 2026 roles, 5-persona red-team rubric. Carries the corpus's own fence: no outreach before one externally-countersigned artifact exists. | `sis_development_plan.md` |
| 6 | SAB website + Moltbook recruitment | Completed-then-discarded (same race) | **BLOCKED**: no SAB website exists in this repo; the SAB strategy doc lives on the founder's machine per `dgc health`. Moltbook: no credentials here; only in-repo mention is a TUI category key. Funnel is speccable once the site repo + credentials are named. | `blocked_items_verdicts.md` |
| 7 | RSI DGM lab, 50 rounds | Lab run directly (not via board) | **Ran 50 shadow cycles; 0 proposals.** Two defects: home-relative path scan (needs `~/dharma_swarm`), and the daemon hardwires the OpenRouter provider (`dharma_swarm/terminal_commands/evolution.py:134-135`) — every proposal call failed `OPENROUTER_API_KEY not set` while a working claude_code lane sat in the same process. | `rsi_lab_run.md`, `blocked_items_verdicts.md` |
| 8 | Mech interp ×10 via RunPod | Completed-then-discarded (same race) | **BLOCKED**: lab repo (`mech-interp-latent-lab-phase1`) is not in this checkout, no `RUNPOD_API_KEY`, and "latest 10 experiments" has no queue definition here. | `blocked_items_verdicts.md` |

**Net: 0 of 8 completed through the swarm board.** 5 of 8 produced ship-ready specs/plans via
direct delegation; 3 of 8 are credential/repo-blocked and documented. Day 1's one swarm success
did not repeat — day 2's heavier tasks all exceeded the 300s ceiling.

## New friction entries (continuing day-1 numbering)

- **F15 (BLOCKING) — completed work discarded by state race.** Agents finished tasks after the
  timeout+reconciler had requeued them; the board rejected the results: "Task board update
  failed for 540f3868…: Invalid transition: pending -> completed" (3 occurrences,
  `~/.dharma/logs/operator.log`). Real Claude Code output (observed live in the process table,
  PID 10049 working task 33c1a7bc) was thrown away.
- **F16 (PAINFUL) — graph reconciler orphan sweep.** All 8 day-2 tasks flipped to `pending` with
  "Graph reconciler: orphaned run … requeued" as their result text (board snapshot 13:56 UTC),
  erasing execution context.
- **F17 (PAINFUL) — dispatch returns 0 with 13 idle agents and 8 pending tasks** (13:57 UTC
  snapshots) — after the orphan sweep, routing never re-offered the tasks.
- **F18 (PAINFUL) — evolve daemon scans `$HOME/dharma_swarm`,** not the checkout ("No Python
  files found in /root/dharma_swarm/dharma_swarm", run log). Routed around with a symlink.
- **F19 (BLOCKING for the RSI lab) — evolve daemon's brain is OpenRouter-only**
  (`terminal_commands/evolution.py:134-135`), ignoring the provider chain and the working
  claude_code lane. 50 cycles → ~99 failed calls → 0 proposals.
- **F20 (PAINFUL) — "memory survival" protocol didn't survive.** Agent prompts demand
  externalizing findings to `~/.dharma/shared/` before death; after 16+ agent runs the
  directory is empty (ls receipt, 13:58 UTC).

## Questions only the operator can answer (blocking items 2, 6, 8)

1. **Trading**: jurisdiction/residency, capital you'd genuinely risk, tax setup, custody
   preference? Recommendation stands: start **Alpaca paper + Kraken Futures demo** (free, no
   capital) while deciding.
2. **SAB**: which repo/host is the SAB website in? It is not in dharma_swarm.
3. **Mech interp**: grant a session the lab repo + `RUNPOD_API_KEY`, and name the 10
   experiments (or the queue file that defines "latest").
4. **Accounts** for Darshan syndication (Bluesky, Mastodon, Substack) and YouTube (Google
   Cloud project + channel): all creation/first-posts are operator-gated by design.
