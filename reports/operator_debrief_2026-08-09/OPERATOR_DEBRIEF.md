# OPERATOR DEBRIEF — 2026-08-09

A full day-in-the-life as dharma_swarm's first real operator, in a fresh remote checkout
(`claude/dharma-swarm-operator-debrief-xh8jin` @ 726a544, Linux container, HOME=/root).
Per the mission's hard rules, nothing was repaired — everything broken was logged and routed
around. Placed under `reports/` (not root) because of the "No new root files" rule (CLAUDE.md).

**Caveat:** the operator's todo list arrived as placeholder text, so the four example tasks
were used as the real list: Darshan Issue One outline, world_radar weekly summary, PR backlog
review, Japanese learning app research.

---

## 1. The Path That Works

The minimal morning sequence that got from laptop-open to delegated-work-in-flight today:

```bash
make onboard                                   # 1.1s → READY (read-only status only)
pip install fastapi 'uvicorn[standard]' aiosqlite aiofiles   # because pip install -e . is broken (see F2)
DHARMA_API_ALLOW_LOCAL_NOAUTH=1 bash run_operator.sh --background   # API on :8420
# submit work:
curl -X POST localhost:8420/api/commands/task -H 'Content-Type: application/json' \
  -d '{"title":"...","description":"...","priority":"normal"}'
curl -X POST localhost:8420/api/commands/dispatch     # nothing executes until this fires
# watch:
curl localhost:8420/api/commands/tasks                # poll; no push view exists
```

That path is real — it produced one genuinely excellent completed delegation today. But it is
**not documented anywhere as a path**: every step except `make onboard` was discovered by
reading source or error logs. `make onboard` prints READY while zero of the execution steps
below it can run (its own output says READY "is not permission to edit" — but it also isn't
evidence you can *operate*). There is no persistent tick loop in this path: tasks only move
when you manually POST `/api/commands/dispatch` (the real daemon is `dgc orchestrate-live`,
`dharma_swarm/terminal_commands/lifecycle.py:83`, which needs the broken package install).

## 2. Friction Ledger

**BLOCKING** (stopped the loop until routed around)

- **F1 — `dgc` does not exist after onboard.** `which dgc` → not found. Entry point declared at
  `pyproject.toml:60` but `pip install -e .` fails: `Cannot uninstall cryptography 41.0.7,
  RECORD file not found` (pip output, 2026-08-09). Workaround: `python3 -m dharma_swarm.dgc_cli`.
- **F2 — API won't start on a fresh machine.** `bash run_operator.sh` → "Operator failed to stay
  up"; log shows `ModuleNotFoundError: No module named 'fastapi'`
  (`~/.dharma/logs/operator.log`). No requirements bootstrap ran or was suggested. Workaround:
  manual `pip install fastapi ...`.
- **F3 — All POST endpoints refuse loopback with no hint of the fix.** Startup log says "The
  keyless lane serves loopback clients only" but every POST returned
  `{"error":"unauthorized"}`. The actual contract: loopback is refused unless
  `DHARMA_API_ALLOW_LOCAL_NOAUTH=1` (`api/main.py:425`). The env var name appears in neither
  the error nor the startup message. Found by reading source.
- **F4 — Swarm agents' default brains are unreachable, and dispatch doesn't notice.** Provider
  chain is cheap-first Ollama→…→OpenRouter (`dharma_swarm/runtime_provider.py:122-137`). No
  Ollama server exists here; jikoku log recorded 14 "LLM calls" to OllamaProvider lasting
  3–11 ms (instant failures), including the incoherent
  `OllamaProvider (claude-sonnet-4-20250514)` (`~/.dharma/jikoku/JIKOKU_LOG.jsonl`). Tasks sat
  "running" while agents walked a dead chain; 6 of 8 dispatched tasks eventually died at the
  300 s timeout.
- **F5 — Headless agent died asking a human for permission.** The PR-backlog task executed via
  ClaudeCodeProvider and returned "I need your permission to use the WebFetch tool… There
  should be a permission prompt in the UI" — as its *result*, with `status=completed`,
  `success: true`, in the trace (`~/.dharma/traces/traces_2026-08-09.jsonl`, task
  bd2e40d5f350400b). Nothing can approve that prompt; the subprocess lane has no permission
  profile.

**PAINFUL**

- **F6 — 300 s task timeout + silent requeue + self-spawned work starves user work.** Timed-out
  tasks flip back to `pending` with result "Task execution timed out after 300.0s"; the next
  dispatch then picked two swarm-self-spawned "Develop latent insight" tasks over my four
  user-submitted ones (board snapshots 13:43–13:45 UTC). The one successful task took ~4 min —
  the ceiling kills anything longer, which is most real knowledge work.
- **F7 — Cost accounting is blind on the only working lane.** The claude_code dispatch traces
  record `prompt_tokens: 0, completion_tokens: 0, cost_usd: 0.0`; no
  `~/.dharma/traces/cost_ledger.jsonl` was created; `routing_decisions` in
  `~/.dharma/state/runtime.db` has 2 rows. The operator cannot answer "what did today cost".
- **F8 — `dgc health` is hardwired to the founder's laptop.** 77 of 79 checks are absolute paths
  like `~/mech-interp-latent-lab-phase1/` and `~/agni-workspace/` — "2 OK, 77 MISSING" on any
  other machine (command output, 2026-08-09). As a health check it carries no signal here.
- **F9 — Dashboard install fails out of the box.** `npm install` → ERESOLVE peer-dep conflict on
  `@visx/heatmap` (`/root/.npm/_logs/2026-08-09T13_34_39_945Z-debug-0.log`). Works with
  `--legacy-peer-deps` (23 s), then `npm run dev` serves (GET / → 307, compiled 4.7 s).
- **F10 — API startup logs real component failures every boot.** `GnaniLodestone: concept
  seeding failed: cannot import name 'ConceptGraph' from 'dharma_swarm.graph_nexus'` and
  `stigmergy seeding failed: … string_too_long` (`~/.dharma/logs/operator.log`).
- **F11 — world_radar live ingest crashes on this network.** `python3 -m
  dharma_swarm.world_radar.cli bronze-hn --query … ` → unhandled urllib traceback (raw
  `urlopen` in `dharma_swarm/world_radar/bronze.py` vs. sandbox egress proxy). No graceful
  error.
- **F12 — No built-in operator view of the board.** Queued/running/done was watched via a
  hand-rolled curl poll loop; results are only visible by re-fetching the full task list.
  (The TUI/dashboard may render this, but the TUI showed "bridge booting" and was not
  drivable headlessly; not disproven — just not reachable today.)

**COSMETIC**

- **F13 — TUI model line claims `claude:claude-opus-4.8 [unverified]`** before any bridge
  connection (launch render, `terminal/`).
- **F14 — `make onboard` "Next:" suggests `make agent-build-preflight PACKET=<path>`** for every
  session, though packets only bind on hot paths — mildly misleading for a non-editing operator.

## 3. Dead vs Alive

**Alive (participated in today's work, observed):**
`scripts/governance/agent_onboard.py` (onboard), `api/main.py` + routers (FastAPI on :8420),
`dharma_swarm/swarm.py` SwarmManager (task creation), `dharma_swarm/orchestrator.py`
(routing/dispatch/timeout), `dharma_swarm/agent_runner.py` + `dharma_swarm/providers.py`
ClaudeCodeProvider (the one working brain), `dharma_swarm/stigmergy.py` (2 marks written from
completed tasks — `dgc stigmergy` output), witness JSONL (`~/.dharma/witness/witness_20260809.jsonl`,
BLOCKED→reroute entries), jikoku span log, conversation_log, `dharma_swarm/observability.py`
(dispatch traces), `dharma_swarm/world_radar/cli.py` (ran; network-failed), the Bun/Ink TUI
(`terminal/`, launches), the Next.js dashboard (serves after F9 workaround), latent-gold task
spawner (self-spawned 4+ tasks).

**Dead / never fired today:**
`dharma_swarm/evolution.py` DarwinEngine (`dgc evolve trend` → "No fitness data yet"),
`dharma_swarm/dharma_kernel.py` (`dgc dharma status` → "Kernel not initialized"), the HUM
(`dgc hum` → "No dreams yet"), NATS substrate (onboard: "127.0.0.1:4222: not listening",
0/5 mirrors), all Ollama/keyed API providers (no keys, no server), Go ingestors
(`tools/world_signal_ingestor_go/`, `tools/world_scout_go/` — no bronze receipts under
`~/.dharma`), `graph_nexus.ConceptGraph` (import error, F10), the orchestrate-live daemon
(never started — blocked behind F1), cost ledger (file never created).

## 4. Delegation Scorecard

| Todo item | Swarm outcome | Manual fallback | Quality |
|---|---|---|---|
| World radar weekly summary | **SWARM DID IT.** Task 17bb01f5, builder agent via claude_code, ~4 min. Truthful "zero signals ingested" digest with evidence, citation spot-checks all passed (commit fbb4785, `world_signal_supply.md`, `bronze.py:33-37` all verified). | Mine reached the same conclusion with less depth. | **5/5** — would ship. The swarm's answer beat my manual one. |
| PR backlog review | **FAILED** — died on WebFetch permission prompt, reported as completed/success (F5). | Done via GitHub API: 33 open PRs triaged into close (8 stranded drafts), operator-decision, merge-priority, dep-bump lanes (`pr_backlog_review.md`). | Swarm 0/5 · manual **4/5** — actionable, would use. |
| Darshan Issue One outline | **TIMED OUT** twice at 300 s (task 6a9b5c04). | Done by delegated subagent from `docs/plans/DARSHAN_CHARTER_2026-07-12.md`: 8 pieces mapped to the seven desks (charter:27-39), editorial-law constraints honored (`darshan_issue_one_outline.md`). | Swarm 0/5 · manual **4/5** — real editorial review needed before use. |
| Japanese learning app research | **TIMED OUT** at 300 s (task 637f78b0). | Done by delegated subagent with web research: SRS landscape (FSRS vs SM-2 vs WaniKani fixed ladder), pitch-accent gap analysis, 7 differentiators, sources per claim (`japanese_app_research.md`; two sources proxy-blocked, flagged inline). | Swarm 0/5 · manual **4/5** — solid spec input. |

Net: **1 of 4 delegations succeeded through the system** (and that one was excellent). The other
three were completed by reaching around the system. All four outputs are in this directory.

## 5. Cost

Unanswerable from the system's own records: the claude_code lane logs zero tokens/zero dollars
(F7), the 14 Ollama attempts cost nothing because they never connected, and no
`cost_ledger.jsonl` exists. The honest ledger for today is: ~15 failed local-provider
connection attempts + 2 Claude Code subprocess runs (unmetered) + this session's own
Claude usage (outside the organism's books entirely).

## 6. The Harness Verdict

What actually worked today was: **a task board + one dispatch verb + one competent
subprocess brain, driven over HTTP.** Not the TUI (booted but bridge-dependent and not the
thing I reached for), not the dashboard (install friction, and it's a viewer, not a
delegation surface), not dgc (read-only status views, and not even installed).

The daily interface should be **the task board as a chat-adjacent surface**: submit tasks in
natural language, see queued/running/done/failed with live results, kick or schedule
dispatch, and approve permission escalations (F5 died precisely for want of an "approve"
button reachable by a human). The nearest existing embodiment is `POST /api/commands/task` +
`GET /api/commands/tasks` — thin, already works, needs a front end that shows result text and
failure states honestly. The TUI is the right *skin* for this if its bridge lands; the
dashboard is the right *evening review* surface. But the spine to invest in is
board-in/board-out, because that's the only loop that closed today — and when it closed
(world radar digest), the output was genuinely better than my manual attempt.

## 7. Top 10 Fixes (ranked by daily-loop unblock)

1. **One-command runnable bootstrap** — fix `pip install -e .` (cryptography conflict, F1) or
   ship `make run` that creates a venv, installs deps (incl. dashboard's peer-dep pin, F9),
   and starts the API. Today READY ≠ runnable.
2. **Provider reachability probe at dispatch** — skip providers that fail an instant
   healthcheck; never mark a task `running` when its whole chain is dead (F4). Also fixes the
   Ollama-serving-Claude-model routing incoherence.
3. **Permission profile for the ClaudeCodeProvider subprocess lane** — pass an allowed-tools
   config so headless agents never stall on interactive prompts (F5); it killed the only
   other task that had a working brain.
4. **Honest failure states on the board** — permission-stall and timeout are `failed`, not
   `completed/success=true` or silent `pending` (F5, F6). Everything downstream (stigmergy
   salience, retries, operator trust) inherits this lie today.
5. **User-task priority over self-spawned work** — dispatch picked "latent insight" tasks
   while my four submitted tasks sat timed-out in pending (F6). Operator work first, always.
6. **Raise/parameterize the 300 s execution timeout** and surface it at submit time. The one
   success took ~4 min; the ceiling is calibrated below real task length.
7. **Loopback auth developer path** — `run_operator.sh` (non-production) should either set
   `DHARMA_API_ALLOW_LOCAL_NOAUTH=1` itself or the 401 body should name the env var (F3).
8. **Meter the claude_code lane** — parse the CLI's usage output into the cost ledger so
   "what did today cost" has an answer (F7).
9. **Live board view** — surface `GET /api/commands/tasks` (with full results and failure
   reasons) in the TUI's first screen; today the view was a hand-rolled curl loop (F12).
10. **Make `dgc health` checkout-relative** (F8) and initialize the dharma kernel on first
    run — the flagship integrity check ("Kernel not initialized") and the health command both
    return noise on any machine but one.

---

*Receipts referenced throughout: command outputs from this session (2026-08-09, 13:32–13:46 UTC),
`~/.dharma/logs/operator.log`, `~/.dharma/jikoku/JIKOKU_LOG.jsonl`,
`~/.dharma/traces/traces_2026-08-09.jsonl`, `~/.dharma/witness/witness_20260809.jsonl`,
board snapshots via `GET /api/commands/tasks`, and file:line citations inline.*
