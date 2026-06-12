# FRONTIER_PEERS — the competitive landscape for the sovereign holon

**Written:** 2026-06-09 · **Author:** opus_composer (web-grounded, primary sources where possible)
**Why this file exists:** the holon initiative should carry its competitive landscape next to its plan.
This maps the most powerful persistent/autonomous agents of mid-2026 against the five properties we
are building toward, names the one seat in the table that is still empty, and says who to copy for which
organ. Cross-checked against this folder's own 52-source dossiers (`00_RESEARCH_DOSSIER.md`,
`04_FRONTIER_DOSSIER.md`) — it does not contradict them; it sharpens them.

---

## The thesis (what "bleeding edge" actually means here, mid-2026)

Three things hardened across the field between Feb–June 2026, and all three point the same way:

1. **Harness engineering is the discipline, not prompt engineering.** The agent's power lives in the
   *harness* — memory, context compaction, tool/MCP wiring, permissions, persistence, self-improvement —
   not the base model. "From prompt engineering to harness engineering."
2. **The multi-agent debate collapsed into one answer.** Five vendors (Anthropic, OpenAI, AutoGen,
   Cognition, LangChain) converged on **orchestrator + context-isolated subagents**: one orchestrator owns
   the full context and spawns *ephemeral isolated* subagents that return a *compressed summary*. Cognition's
   "Don't Build Multi-Agents" evolved into "agents contribute *intelligence* (different signal), but
   **writes stay single-threaded**." → **Build one coherent sovereign holon first; the fleet is subagents
   it spawns, not peers it shares a brain with.**
3. **Self-evolution went from theory (Gödel machine) to shipping (runtime tool-synthesis).** The frontier is
   no longer "can an agent rewrite itself" but "an agent that synthesizes its own tools mid-run and keeps
   what verifies."

Our differentiator is **none of these three** — they're table stakes now. Ours is the fourth thing nobody
has shipped as a product: **identity-and-value governance that binds a sovereign agent without sitting in
its task hot-path.** "Sovereign within the banks." That is the empty seat (§4).

---

## 1. The peer table — 10 systems × our five properties

Properties: **Persist** (survives sessions, real memory) · **Auto** (wakes/self-tasks, no human in hot path)
· **Self-ctx** (loads its own identity/boot bundle) · **Self-evolve** (writes/refines own skills/tools over
time) · **Self-govern** (operates under its own declared authority/banks). 🟢 strong · 🟡 partial · 🔴 weak/absent.

| Tier | System | Persist | Auto | Self-ctx | Self-evolve | Self-govern | Why it matters to us |
|---|---|:--:|:--:|:--:|:--:|:--:|---|
| **0 — reference** | **Anthropic Managed Agents** (Apr 08 2026) | 🟢 | 🟢 | 🟢 | 🟡 | 🟡 | **The architecture to copy** (primary-verified, Anthropic eng blog). Three virtualized components: **session** (append-only event log) / **harness** (the loop that calls Claude + routes tool calls) / **sandbox** (execution env). Their metaphor: *brain* = Claude+harness, *hands* = sandbox+tools. Recovery: on failure, `wake(sessionId)` + `getSession(id)` → resume from last event. The API layer persists an Agent *config* (model, prompt, tools, MCP, skills) that Sessions reference. **This *is* the record→runtime bridge, productized.** |
| 1 | **Hermes Agent** (Nous Research, Feb 2026) | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | The direct ancestor — your `hermes-m5` runs on it. On-device persistent memory, writes/refines its own skills, gets better the longer it runs. NVIDIA-backed (DGX Spark, NemoClaw). Everything *except* governance. |
| 1 | **Live-SWE-agent** (arXiv 2511.13646) | 🟡 | 🟢 | 🟡 | 🟢 | 🔴 | **Self-evolution SOTA** (primary-verified): **77.4% SWE-bench Verified**, 45.8% SWE-bench Pro, *no test-time scaling*. Starts from "the most basic agent scaffold with only access to bash tools" and **autonomously evolves its own scaffold at runtime** while solving real problems. The live "evolving over time" reference. |
| 1 | **Devin 2.0** (Cognition) | 🟢 | 🟢 | 🟡 | 🔴 | 🔴 | Most mature autonomous SWE: sandboxed browser+terminal+editor, plans/codes/tests/iterates, persistent sessions. Also the *author* of the single-threaded doctrine (§thesis-2). |
| 1b | **Darwin/Huxley-Gödel Machine** (Sakana+UBC / HGM) | 🟡 | 🟡 | 🟡 | 🟢 | 🔴 | The self-rewriting-code lineage. DGM keeps an open-ended archive of agent variants; **HGM** (newer) approximates the optimal self-improver for human-level coding. The rigorous root of self-modification. (Your own DGM loop — currently unwired — is this lineage.) |
| 2 | **Manus** (Monica) | 🟢 | 🟢 | 🟡 | 🟡 | 🔴 | The *general-purpose* autonomy pole (not just code): cloud-to-local hybrid, long multi-step research+execution. |
| 2 | **OpenHands** (All Hands AI) | 🟡 | 🟢 | 🟡 | 🔴 | 🔴 | Leading *open-source* autonomous SWE agent; self-hostable, model-agnostic. The one you could fork for the Hands layer. |
| 2 | **Google Jules / Antigravity** | 🟢 | 🟢 | 🔴 | 🟡 | 🟡 | Async: clones your repo into a cloud VM, works while you're away. Antigravity productizes "holon-as-cell" with managed guardrails. |
| 2 | **OpenAI agent line** (Operator → ChatGPT Agent) | 🟡 | 🟢 | 🟡 | 🔴 | 🟡 | Broadest computer-use + tool-use; thin on long-term identity/self. |
| 2 | **OpenClaw / Claw + NVIDIA NemoClaw** | 🟢 | 🟡 | 🟢 | 🔴 | 🟡 | The other harness you named — persona-persistent + **hardened secure runtime**. Closest existing thing to a *governed* sandbox. |

*Deliberately downranked per your own research:* **Voyager-lineage / AIOS** and **MetaGPT / ChatDev** —
real and historically important, but they are *context-sharing multi-agent swarms*, the pattern the 2026
consensus moved away from. Their lesson (skill libraries, role decomposition) survives; their topology does not.

*Honest sourcing note:* popularity figures floating around (Hermes "47K stars in 42 days," OpenHands
"66K users," Devin price points) come from secondary/SEO blogs — treat as directional, not verified.
The *architectures* above are confirmed against primary sources (Anthropic engineering blog, Cognition,
arXiv). Capability numbers cited (77.4% SWE-bench etc.) are primary-verified against the papers/blogs (2026-06-09).

---

## 2. The 2026 harness taxonomy → which holon organs we have

The field now treats a harness as **nine composable, measurable, upgradeable layers**. Mapped to our build:

| Harness layer (2026 SOTA) | What leaders ship | Our holon status |
|---|---|---|
| Agent loop | ReAct, LangGraph (checkpointed state machines) | ✅ `AutonomousAgent` ReAct + `PersistentAgent` wake loop |
| Context delivery / compaction | Prompt Caching, **Compaction API** (84% token cut), LLMLingua | 🟡 MemoryKernel exists; no compaction-API-grade summarizer |
| Planning / decomposition | Plan-and-Execute, LATS (MCTS over trajectories) | 🟡 self-task generation only |
| Tool / MCP | MCP standard, Composio (250+ APIs), identity-propagating tools | 🟢 deep MCP stack already mounted |
| **Permissions / authorization** | **PEP + PDP "Authorization Fabric," Open Agent Passport (signed pre-action audit), SPIFFE identity** | 🔴 **`autonomy_policy` never read — no PDP, no PEP.** This is the gap. |
| Memory / persistence | **Session event-log replay** (Managed Agents), initializer→executor handoff | 🟡 identity on disk, but no record→runtime replay |
| Observability / tracing | 27-event hook pipelines, middleware interception points | 🟡 witness logs exist, not a trace fabric |
| Evals / verification | SkillTester, AutoHarness, deployment-blocking eval gates | 🔴 no per-agent verification loop |
| Self-improvement | **SkillOpt** (trajectory-driven, validation-gated), runtime tool-synthesis | 🟡 skills exist; evolution loop unwired |

**Read this column top to bottom:** we are strong on loop + MCP, partial on memory/context/planning, and
**red exactly where sovereignty lives** — permissions (PEP/PDP) and per-agent verification. That is not a
coincidence. It is the shape of the empty seat.

---

## 3. Self-evolution reference designs (the "evolving over time" pole)

Lineage, oldest → bleeding-edge: **SICA** (17%→53% SWE-bench, offline strategy improvement) →
**Darwin-Gödel Machine** (archive of self-rewritten variants) → **Huxley-Gödel Machine** (approximates the
optimal self-improver) → **SWE-RL** (Meta Superintelligence, RL on evolution) → **Live-SWE-agent** (autonomous
scaffold self-evolution from a bash-only start, **77.4%** — the current SOTA). Benchmarked by **SWE-EVO** (long-horizon
software-evolution scenarios). **Design directive:** copy Live-SWE-agent's *runtime scaffold/tool
self-synthesis* and DGM's *kept-archive-of-variants*; both must route through our telos/authority gate so
self-modification is **bounded**, not open-ended — which is precisely what none of them do.

---

## 4. The empty seat — what we'd be first to ship

Every system above is 🔴 or 🟡 on **self-govern**. The 2026 field solved *enforcement plumbing* for
**task safety** (PEP/PDP authorization fabric, signed pre-action passports) — but always as an *external
guardrail on a tool-using worker*, optimizing *coding-task reliability*. Two things are still unbuilt as a
shipped product:

1. **Identity/value governance, not just action governance.** Our gate optimizes a *different objective* —
   identity coherence and telos/value-alignment — not task-completion. (Category-error caution from our own
   dossier: don't gut governance because a *coding* benchmark says "governance hurts reliability." Different
   objective.)
2. **The record→runtime bridge that loads the agent's *own* banks.** Managed Agents proves the *mechanism*
   (config → session → replay). Nobody has wired it to a **PDP that reads the agent's own `autonomy_policy`
   at decision time** and a **telos gate off the task hot-path** that binds *who the agent is*, not just
   *what the tool may touch*.

**The seat:** a single-threaded sovereign holon whose harness (a) loads its real identity/model/banks at
runtime (Managed-Agents pattern), (b) self-evolves its tools with reflection (Live-SWE-agent pattern) but
**through a telos/authority PDP** (the unbuilt part), (c) spawns isolated subagents for *intelligence*, never
shares its brain (2026 consensus), and (d) carries per-agent verification (eval gate) so "done" means green.
Build organs 5 + 6 of `STATE_OF_TRUTH.md` and that seat is ours.

---

## 5. Design directives (who to copy for which organ)

- **Record→runtime bridge** → copy **Anthropic Managed Agents**: Agent-config + Session event-log + replay-on-crash.
- **Hands / sandbox** → **OpenHands** (forkable) or **NemoClaw** (hardened) for the execution container.
- **Self-evolution** → **Live-SWE-agent** (runtime tool-synthesis) + **DGM/HGM** (kept variant archive), gated.
- **Authorization** → **PEP/PDP Authorization Fabric** + **Open Agent Passport** — but extended from action-safety to *identity/value* binding.
- **Multi-agent** → orchestrator + **isolated** subagents returning compressed summaries; **single-threaded writes** (Cognition/Anthropic consensus). Our stigmergy/decorrelation is a *better* flavor of "intelligence not actions."
- **Persistence/context** → **Compaction API** pattern for the wake-loop's memory handoff.

---

## Addendum 2026-06-12 — Hermes Agent re-verified (the frontier moved in 3 days' worth of releases)

Fresh primary-source check (github.com/NousResearch/hermes-agent README + RELEASE_v0.15.0 + v2026.5.29/v2026.6.5 release notes, hermes-agent.nousresearch.com/docs):

- **Velocity:** ~190k stars, 390 contributors, 17 releases since 2025-07; v0.15.0 alone = 1,302 commits / 747 PRs. Conclusion unchanged but sharpened: **we cannot and should not out-velocity commodity harness plumbing.** Include it; don't rebuild it.
- **What Hermes now ships** (beyond the Feb-2026 row in the table): 20+ messaging platforms from one gateway; built-in cron + webhooks; profiles (isolated config/sessions/skills/memory per instance) + global `SOUL.md` personas; skills hub (19,932 catalog entries, agentskills.io standard); MCP client + `hermes mcp serve`; six terminal backends incl. serverless persistence (Daytona/Modal); git-worktree isolation; filesystem checkpoints/rollback; **kanban multi-agent platform** — orchestrator auto-decomposition, swarm topology (root → parallel workers → **gated verifier** → **gated synthesizer**, shared blackboard), per-task model overrides, worktree-per-task; promptware/Brainworm defense at three chokepoints; Atropos RL trajectory export.
- **Strategic read — convergent evolution toward the empty seat:** Hermes' kanban now has *gated verifiers* and *prompt-injection chokepoints* — action-safety and task-verification are commoditizing fast. What remains unshipped anywhere: **identity/value governance** (telos gates bound to who the agent *is*), **receipts as a truth spine** (EvidenceReceipt-grade, externally re-readable), and **bounded self-evolution through a policy door**. The seat is still empty, but the wall clock is running.
- **Include-directive (operator-ratifiable):** Hermes Agent is MIT and provider-agnostic — it can serve as a commodity **body** for a holon: one Hermes *profile* per holon, `SOUL.md` projected from `~/.dharma/agents/<name>/prompt_variants/active.txt`, free-model routing, cron pulse, Telegram reachability — while dharma_swarm stays the **governing organism** (identity seed, kill/budget, talk receipts, witness, evolution archive). Same pattern extends to OpenHands (coding hands) and Claude Code/Codex (dev seats): **one soul, many bodies** — the `agent.seed.yaml` contract from `04_FRONTIER_DOSSIER.md` is the projection surface.
- Peer-table delta: Hermes row Self-evolve stays 🟢, Self-govern stays 🔴 (sandboxing + command approval + promptware defense = action safety, not value governance). OpenClaw lineage note: Hermes ships `hermes claw migrate` — it is positioning as the claw-family successor.

## Sources
- Anthropic, *Scaling Managed Agents: Decoupling the brain from the hands* (engineering blog, 2026); anthropics/skills `managed-agents-overview.md`.
- Cognition, *Don't Build Multi-Agents* (Jun 2025) + *Multi-Agents: What's Actually Working* (2026).
- *Live-SWE-agent: Self-Evolving Software Agents* (arXiv 2511.13646); *A Self-Improving Coding Agent / SICA* (arXiv 2504.15228); *Darwin Gödel Machine* (arXiv 2505.22954); *Huxley-Gödel Machine*; *SWE-RL* (Meta, Dec 2025); *SWE-EVO* (arXiv 2512.18470).
- Nous Research Hermes Agent docs + NVIDIA NemoClaw blog; hermes-agent README + RELEASE_v0.15.0/v0.15.1 notes (re-verified 2026-06-12).
- `awesome-harness-engineering` (2026 taxonomy); A2A Protocol; Open Agent Passport / SPIFFE auth drafts.
- This folder's `00_RESEARCH_DOSSIER.md`, `04_FRONTIER_DOSSIER.md` (52-source landscape).

*Living doc — re-verify quarterly; the frontier moves monthly. Last re-verification: 2026-06-12 (Hermes Agent).*
