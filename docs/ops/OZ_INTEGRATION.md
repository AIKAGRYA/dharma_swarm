# Oz Integration — Workstream Index & Operator Runbook

Role: reference (Oz-integration index). Subordinate to the Warp plan "Operating Warp/Oz at Maximum Capacity for Dharma Swarm" and to `docs/governance/CANONICAL_DOC_STACK.md`. This file owns no authority; it indexes the Oz workstreams and holds the operator runbook for credentialed steps.

Anti-slop justification: one index doc for the Oz-integration track (branch `oz/integration-2026-06-25`), replacing scattered notes; it points to fact owners and does not duplicate them.

## What Oz is here (one line)
Oz is the swarm's replaceable peripheral nervous system — elastic hands, decorrelated eyes, an external heartbeat — strictly subordinate to APEX/Sarathi and the holarchy. The spine owns all receipts; Oz is overflow + external surface, never the nervous system or an authority.

## Five workstreams (archetype -> instance)
- W1 Decorrelated Verifier — `.warp/skills/oz-verify-claim/` + `.github/workflows/oz-verify-claim.yml` (runs on PRs).
- W2 Forge Automation — wraps `scripts/runtime/forge_swarm_evolution_arena_v0_*` + the overnight-autopilot harness; operator leases on spend/fitness (next).
- W3 AGNI Watchdog -> Dharma Capital strategy feed — read-only over `~/.dharma/remote_nodes/agni/*.json` (next).
- W4 Cleanup Janitor — `.warp/skills/oz-repo-hygiene/` + weekly schedule.
- W5 Drift Sentinel — Semantic Commons forbidden-alias / dangling-pointer / phantom scan (parked until operator GO).

## Existing Oz environments (reuse; do not recreate)
- dharma-spine-ops  `fGXBFftNfOkc2nKXSmyBNn`  (dev-full-agents; PR lifecycle) -> W1, W4
- dharma-swarm-dev  `dyvuDOOnmAwdIXk5fh3yL2`  (dev-full-agents) -> W2 Forge / heavy builds
- dharma-dashboard  `pW9OnuuXfuXPK9C0oOY9Qv`  (dev-web-agents) -> dashboard work

## Authority boundary (applies to every Oz workstream)
Inspect / run read-only checks / review / recommend / open PRs and issues — yes. Merge, approve, resolve threads, push to protected branches, expose secrets, move capital, place live orders, or mutate governance/kernel/telos/archive-fitness — only with explicit operator (and where irreversible, Sarathi) authorization. Every run emits a falsifiable receipt; no self-grading.

## Operator runbook (credentialed steps)
1. GitHub Actions secret for W1 (one time):
   `gh secret set WARP_API_KEY` (paste the Warp API key from `warp://settings/platform`).
   Optional: set repo variable `WARP_AGENT_PROFILE`.
2. W1 smoke test (verify a PR by hand before relying on the workflow):
   `oz agent run-cloud --environment fGXBFftNfOkc2nKXSmyBNn --skill "AmitabhainArunachala/dharma_swarm:oz-verify-claim" --prompt "Verify PR #<n>"`
3. W4 weekly hygiene schedule (after the skill is on the env's default branch):
   `oz schedule create --name "dharma repo hygiene" --cron "0 16 * * 1" --environment fGXBFftNfOkc2nKXSmyBNn --prompt "Read and run the oz-repo-hygiene skill; open ONE consolidated triage PR. Recommend only; never merge."`
4. Monitor: `oz run list` / `oz run get <id>`; `oz schedule list`.

## Warp Drive governance rule (register in-app: Warp Drive > Rules)
Paste as a rule so every Oz run inherits the contract:
"Run `make onboard` first and trust onboard/filesystem/git over prose. You are subordinate to APEX/Sarathi and the holarchy; never act as a second orchestrator. Recommend/verify/open-PRs only — never merge, approve, push to protected branches, expose secrets, move capital, place live orders, or mutate governance/kernel/telos/archive-fitness without explicit operator (Sarathi for irreversible) authorization. Every claim of 'done' must carry an independent, falsifiable receipt; never self-grade. Reuse existing surfaces; justify any net-new file in one sentence."

## Notes
- Phase 0 environments already exist (above); `warp_oz` is already partially admitted as an A2A contact (`~/.dharma/a2a/cards/warp-oz.json`).
- Skills become usable by scheduled/cloud runs once this branch is merged to the env's default branch (operator merges via PR — never auto-merge).
