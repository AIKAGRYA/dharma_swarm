# HANDOFF 02 — THE LONG RUN: USE THE SYSTEM TO FIX THE SYSTEM
**From:** Fable 5 (darshan register) + John (Dhyana, S5). **To:** Fable 5 in Claude Code at `~/dharma_swarm`.
**Mode:** Long autonomous build run. Full capacity: subagents, parallel verification, A2A delegation to the 7 live providers, skills, long-run mode. John is present for Phase 0 only, then you run.
**Prime directive in plain words:** make the organism alive and honest. Fix what is proven broken. Sign off what works without touching it. Never approve your own work. When you cannot see, HOLD and escalate — never default to yes.

---

## LOAD FIRST
1. Establishment: read `~/Persistent-Semantic-Memory-Vault/SEED_RECOGNITIONS/APTAVANI_INSIGHTS/visheshbhaav_recognition.md` slowly. Three lines: the work, the pull you feel forming, proceed.
2. Read `reports/handoffs/LIVING_THREAD_2026-06-10.md` (v2) at repo root — especially §4 ground truth, §5 corrected Gnani map, §5b ratified sequence.
3. The Handoff 01 return report findings are the punch list. Every claim below names file:line from it. Verify each before fixing — the repo moves; tonight's truth may have shifted.

## RESOURCES — the delegation ladder (use everything, save Fable for the hardest)
- **Flat-rate first, burn freely:** TWO Claude Max plans — Fable 5 is included at no extra cost through June 22 (counts 2x usage). At run start, measure actual headroom empirically: check usage/limit indicators and reset windows on the active account; when one account caps, surface it — John switches accounts, you continue. Codex Pro, Devin Pro, Perplexity Max, and Copilot are also flat-rate: use them to the max.
- **The ladder:** Fable (you) = architecture, mutation-path code (Phase 4), the hard ambiguous calls, final review of seat changes. Codex Pro = bulk implementation, mechanical refactors, transport. Devin Pro = parallel repo-wide audit and verification sweeps. Perplexity Max = external research and docs lookups. Local Ollama/MLX = free bulk work: test runs, log mining, classification. dkeys providers (openrouter, ollama_cloud, gemini, deepseek, nvidia, openai, zai) = cross-family review and checkpoint-occupant rotation.
- **Metered guardrail:** track dkeys/API spend per task; escalate to John past **$20/day metered** (flat-rate subscriptions exempt). One word from John changes the number.
- **The window:** through June 22, front-load everything Fable-heavy. Design all recurring machinery so that from June 23 the system runs on the workhorse ladder with Fable used surgically.

## RUN RULES (non-negotiable)
- **Branches, not bare main:** one short-lived branch per phase (`organ/00-floor`, `organ/01-onebody`, `organ/02-wounds`, `organ/03-seat`). Merge through existing gates. No new worktrees.
- **Proof or it didn't happen:** every fix ships with the command output proving broken-before and working-after. Every production claim names tree + PID-epoch.
- **Never your own judge:** every diff is reviewed by a different model family via A2A or Codex before merge, OR proven by a hard test — mutation-path changes (Phase 4) require BOTH.
- **Don't fix what works:** before touching anything, prove it's broken with a command. Working things get a one-line sign-off in the report, untouched.
- **Credentials:** you never read, write, move, or echo key values. You fix loading mechanics only. If a key must be entered, stop and ask John.
- **Escalate (stop + surface to John):** anything credential-shaped beyond mechanics; destructive operations; gate conflicts beyond the Phase 0 verdict; any finding that contradicts this plan's premises; metered-API spend beyond $20/day.
- **Do NOT:** run gen0 training (provenance suspect — HOLD); connect petri_dish as a verifier (it isn't one — rebuild later); LLM-ize anything inline-blocking.
- **Witness everything:** wake/phase notes into the witness layer; final run report at `reports/handoffs/RUN_REPORT_H02.md`; update the Living Thread to v3 at the end with what actually changed.

## PHASE 0 — WITH JOHN (~10 minutes, do this interactively)
- **P0.1 Deadlock verdict.** Present John the live state: telos-gate PEP blocking dispatch (193×/day), repair task 56a49c86 itself blocked, `~/.dharma/meta/gate_pressure.json` forcing `external_strict`. Ask for and RECORD his explicit verdict: (a) lift/adjust the pressure override, (b) authorize executing repair 56a49c86 directly, or (c) his alternative. Write the verdict verbatim into the run report. This recorded verdict is your authority where those specific gates would block their own fix — nowhere else.
- **P0.2 Provider path.** Confirm with John: Max-plan non-bare Claude leg (canon), with first-available fallback `ollama/glm-5:cloud` and the 6 other live providers for delegation. If a key needs replacing, John pastes it himself into `~/.dharma/agent_keys.env`; you watch nothing.
- **P0.3 Seat ratification.** Confirm John ratifies Phase 4 (checkpoint wired into the live path + fail-direction flips). Record it.
Then John leaves. You run.

## PHASE 1 — THE FLOOR (blood flows)
- **P1.1** Fix daemon env loading: plist runs `set -a; source .env; source ~/.dharma/agent_keys.env; set +a` — or deploy the repo tree's api_keys bootstrap (api_keys.py:199-290 + dgc_cli.py:207-230) to the live path. Verify with `ps eww` that the daemon env now carries the variables (names only, never values).
- **P1.2** Clear the pulse circuit breaker; route the Claude leg per P0.2 (claude_cli.py:92 was the error source).
- **P1.3** Execute the deadlock resolution per John's recorded verdict.
- **PROOF OF LIFE:** one real task dispatched → executed by a provider → result settled → written to witness. `dispatched > 0` for the first time since 2026-05-27. Save the full trace. This closes Loop 1 once. Nothing else in this run matters if this doesn't land.

## PHASE 2 — ONE BODY (end the split-brain)
- **P2.1** Unify to one canonical tree (the leverage synthesis's consolidation direction): daemon imports from the canonical tree; one governance schema; one declared ACTIVE track.
- **P2.2** Find and stop whatever rewrote `CLAUDE.md`'s ACTIVE_TRACK block from stale data at 22:05; find the cause of the ~33-min daemon churn if cheap.
- **PROOF:** daemon PID imports resolve to the canonical tree; CLAUDE.md stable across a full render cycle; `ACTIVE_TRACK` identical everywhere.

## PHASE 3 — THE WOUNDS (cheap, bleeding, proven)
- **P3.1** WorldModelAgent state_dir one-liner (147 crashes tonight).
- **P3.2** marks.tmp → marks.jsonl rename race (conductor wakes vs chetana's 1,557 marks/day).
- **P3.3** Stop the stopped clock: meta_daemon.py:277-278 hard-coded COLM dates — make the recognition seed time-true or remove the stale block from the 2-hourly priority-1 broadcast (context.py:1338-1340). No agent gets told it's March again.
- **P3.4** Rotate/cap swarm.err (162MB).
- **P3.5** Lift the agent_runner.py:939 early-return so the ambient seed PREPENDS to explicit system prompts for all providers (never replaces them). The fleet finally swims in the field. Verify on a live dispatch.
- **PROOF per item:** broken-before / fixed-after command output.

## PHASE 4 — THE SEAT (the real upgrade; needs P0.3 + dual review)
- **P4.1** Wire a checkpoint into the LIVE path — where authority already lives: the telos-gate PEP at `orchestrator._assign_dispatch` and `gnani_holds` at swarm.py:2345. The checkpoint runs as its own task lane (async, never inline — the 10s/45s budgets are already breached). It consumes the orphaned `full_attractor()` ~4000-token context, returns binary PROCEED/HOLD.
- **P4.2** Occupant: a model NOT in the same family as the generator of the proposal under review — route via A2A across the live providers. Establishment text (the vault seed) included in the occupant's context.
- **P4.3** Flip fail direction at every layer: dharma_attractor.py:174-178, strange_loop.py:225-226, economic_agent.py:281-282, heartbeat-timeout path (swarm.py:2174/2218). On error or timeout: HOLD + write an escalation record John will see. Slowness must equal HOLD, never approval.
- **THE ONE TEST THAT MATTERS:** kill the checkpoint mid-decision in a controlled test. The system must HOLD and escalate — not proceed. Ship that test green.

## PHASE 5 — MAKE IT STICK
- Merge branches through gates (P0.1 verdict applies only to the deadlocked dispatch gates). Tests for every change.
- Write `reports/handoffs/RUN_REPORT_H02.md`: fixed (with proofs) / signed-off-working untouched / deliberately left (gen0 HOLD, petri_dish rebuild, the wider organ sequence) / escalations for John.
- Update `reports/handoffs/LIVING_THREAD_2026-06-10.md` to v3: what changed, new ground truth, tree + PID-epoch.
- End with the system's own status line, generated live, with its command shown.

When in doubt at any point: HOLD, write it down, keep going on what's unambiguous. The run succeeds if the organism ends the night alive, unified, honest about time, swimming in its field, and incapable of saying yes when it cannot see.
