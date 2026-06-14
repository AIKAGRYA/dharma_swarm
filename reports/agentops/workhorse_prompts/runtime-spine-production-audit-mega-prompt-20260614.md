# Runtime Spine Production Audit Mega-Prompt

Date: 2026-06-14 JST

Source skills used:
- `/Users/dhyana/m5-handoff/skills/mega-prompt/SKILL.md`
- `/Users/dhyana/m5-handoff/skills/prompt-lab/SKILL.md`

## Recommendation

Use the fused prompt below.

The earlier checklist prompt is better for coverage, repeatability, and receipts. The `mega-prompt` version is better for architectural judgment and avoiding shallow inventory work. For this audit, the fused version is strongest: it keeps the cognitive frame tight, then gives the agent enough concrete repo obligations to prevent poetic drift.

## Runnable Goal Draft

```text
/goal
Run the Runtime Spine Production Audit from:

reports/agentops/workhorse_prompts/runtime-spine-production-audit-mega-prompt-20260614.md

Continue until the audit is complete or blocked by a concrete external constraint. Do not make code changes. Use the repo's own governance systems, safe verification commands, recent git and PR evidence, memory/MCP/codebase tools, and live server checks where safe.

Definition of done:
- Every runtime-related official and unofficial lane has been found or intentionally ruled out.
- The runtime topology is mapped across governance, code, servers, dashboards, terminal/TUI surfaces, bridges, receipts, providers, and recent PRs/branches.
- NORTH STAR vision v2 and the nearest high-signal vision docs have been read and used to judge whether the runtime spine can serve the repo's full future shape.
- The 88/100 production-readiness claim has been accepted, corrected, or rejected with executable evidence.
- The report names the few runtime invariants that would make production readiness real, plus the blockers preventing them today.
- The final answer includes changed files, commands run, verification evidence, and any remaining blocker or risk.
```

## Fused Prompt

```text
You have inherited runtime platforms at three stages: one that looked clean because governance labels hid runtime drift, one that collapsed because every new surface got its own adapter, and one that became durable only after its runtime spine was reduced to a few observable invariants that every server, dashboard, agent, bridge, and receipt path had to obey.

Read this system as forces, not parts: governance pressure, live-process pressure, operator-surface pressure, evidence pressure, and future-vision pressure. A runtime spine is real only if those forces converge through it without special pleading.

Quality means three things: every readiness claim must reduce to executable evidence; every runtime-facing surface must have a canonical authority and a live path; and the runtime must be small enough to stay fast while strong enough to serve future organs not yet built. The audit must also audit its own evidentiary loop: if the runtime cannot generate evidence that could falsify its readiness score, it is not production-ready.

Do not accept words like shippable, adopted, truth, spine, bridge, or loop as evidence. Do not produce a loose inventory or propose more architecture because a gap is visible; find the few structural facts that explain the whole runtime field.

Below is the audit charge. Read it as a disputed production-readiness claim about whether /Users/dhyana/dharma_swarm has a coherent runtime spine.

---

Audit the runtime only in /Users/dhyana/dharma_swarm as of June 14 JST. The reported claim is that Runtime Truth Reconciliation is 88/100 production-ready, with adjacent lanes named Runtime Truth NATS, Runtime Truth Spine Adoption, Runtime Adoption, Composer Holon Spine Longrun, Cybernetic Loop Closure, A2A/NATS bridge work, dashboard runtime surfaces, terminal/TUI runtime surfaces, evidence receipts, provider/model runtime reporting, and bypass/adoption machinery. Treat that score as unproven.

Start from the repo's own truth systems: AGENTS instructions, `make onboard`, `make orient`, `make hygiene`, active-track governance, status scripts, recent git history from the last 14 days, branch/worktree/PR evidence, and code search. Use available MCPs, memory, GitHub tools, codebase tools, browser/server inspection, and parallel/decorrelated subaudits wherever they improve coverage.

Find every runtime-related file, script, service, server process, bridge, adapter, dashboard dependency, terminal dependency, governance declaration, PR, branch, report, receipt path, bypass list, and vision reference. Include official and unofficial lanes. Distinguish what is live, tested, declared, scaffolded, duplicated, stale, or broken.

Read NORTH STAR vision v2 and the few nearest high-signal vision/architecture documents needed to understand the repo's organs and future surfaces. Judge whether the runtime spine can serve all of them: governance, dashboards, terminal/TUI, agents, provider routing, evidence receipts, longruns, bridges, research-depth work, revenue/external-human-serving workflows, and future modular organs.

Do not edit code. Run safe verification commands. If a server/process should be live, verify whether it actually starts or is already running. If a check cannot run, name the exact constraint.

Produce one rigorous audit report with:
- Executive verdict and corrected production-readiness score.
- Runtime topology map across lanes, files, servers, bridges, receipts, dashboards, terminal/TUI, agents, and governance.
- Evidence table for each major runtime component: live/tested/declared/scaffolded/stale/broken, source files, governing track or PR, verification evidence, and risk.
- Vision alignment against NORTH STAR v2 and the closest architecture/vision docs.
- Server/process audit showing what is live, what starts, what fails, and what is only declared.
- Ranked blockers, especially bypass allowlists, non-live bridges, missing receipts, draft PR gates, duplicated runtime tracks, and dashboard/terminal/server drift.
- Consolidation path: what to close, merge, kill, promote into governance, and test before any production-ready claim.

---

What three runtime invariants, if enforced across governance, code, servers, receipts, and operator surfaces, would make the production-readiness score true rather than merely declared?
```

