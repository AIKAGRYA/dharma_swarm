# Blocked Items — Verdicts with Receipts (2026-08-09)

## Mech interp: "Run the latest 10 experiments via RunPod" — BLOCKED

- The mech-interp lab is not in this repository. The ecosystem map that `dgc health` checks
  places it at `~/mech-interp-latent-lab-phase1/` on the founder's machine ("R_V metric
  research — ACTIVE, 70-80% paper-ready", `dgc health` output 2026-08-09) — MISSING here.
- No RunPod credential exists in this environment (`env | grep -i key` shows no
  `RUNPOD_API_KEY`, 2026-08-09).
- The only RunPod material in-repo is `docs/RUNPOD_SWEBENCH_RUNBOOK.md`, which is the Forge
  SWE-bench harness, not mech-interp.
- **To unblock:** give a session access to the `mech-interp-latent-lab-phase1` repo + a
  `RUNPOD_API_KEY`, and define "the latest 10 experiments" (an experiment queue file does not
  exist in this repo).

## SAB website: "fully finish + agent onboarding + recruit 10 Moltbook agents" — BLOCKED (website), SPECCABLE (funnel)

- No SAB website exists in this repository (`grep -rli "SAB" docs/` returns only unrelated
  matches — semantic-codec and TUI docs). The SAB strategy doc lives on the founder's machine
  per the `dgc health` map (`~/agni-workspace/NORTH_STAR/SAB_500_YEAR_VISION.md` — MISSING here).
  "Fully finish" is unactionable from this checkout: the site's repo/host was never named.
- Moltbook: no Moltbook credentials or integration exist here (the only in-repo mention is a
  TUI command-category key, `terminal/src/commandRegistry.ts:35`). Recruiting external agents
  requires a Moltbook account and is outward-facing engagement — operator-gated by the same
  logic the Darshan charter applies to platform posting.
- **To unblock:** point a session at the SAB website repo; provide Moltbook credentials; then
  the recruitment funnel (an agent-onboarding page + an attributed recruitment post + a
  10-slot cohort tracker) is a one-session build.

## RSI / DGM lab: "run 50 rounds" — RAN, and the run itself is the finding

- A real lab exists: `dgc evolve daemon --cycles N --shadow` (DarwinEngine, shadow = propose
  without applying). It was run for 50 cycles in this session
  (`reports/operator_debrief_2026-08-09/day2/rsi_lab_run.md` has the full record).
- Two defects surfaced before the first proposal:
  1. The daemon scans `$HOME/dharma_swarm/dharma_swarm` — a hardcoded home-relative path —
     so in any checkout outside `~` it finds "No Python files" (log receipt; routed around
     with a symlink).
  2. Proposal generation is hardwired to the OpenRouter provider — `provider =
     swarm._router.get_provider(ProviderType.OPENROUTER)`
     (`dharma_swarm/terminal_commands/evolution.py:134-135`) — even with
     `--single-model --model claude-code`. Every cycle failed with "OPENROUTER_API_KEY not
     set" despite a working claude_code lane in the same process's swarm.
- **Result of 50 rounds:** 0 proposals, 0 fitness records; ~78+ failed LLM calls. The lab is
  runnable machinery with an unreachable brain in this environment.
- **To unblock:** either set `OPENROUTER_API_KEY`, or route evolve-daemon through the same
  provider chain the orchestrator uses (it already holds `swarm._router`).
