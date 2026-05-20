# Lane X1 — Nous Research / Hermes Agent (depth)

**Branch:** `research/persistent-agents-2026-05`
**Output path:** `~/dharma_swarm/docs/research/persistent_agents_2026-05_v2/` (v2 path; parallel agent owns the v1 path)
**Access window:** 2026-05-20
**Status:** evidence-grounded survey. Marketing copy filtered out. Citations point at the README of the actively-developed repo (last commit 2026-05-20).

---

## 1. Disambiguation up front

Several names confused the brief:

| Name | What it actually is | Owner |
|---|---|---|
| **Hermes Agent** | The self-improving AI agent runtime — the thing the brief is asking about | Nous Research (`github.com/NousResearch/hermes-agent`, MIT) |
| **Hermes 3 / Hermes 4** | The model family that Hermes Agent can use (also usable from any other agent framework) | Nous Research |
| **Nous Portal** | One of many model-inference endpoints Hermes Agent can be pointed at | Nous Research |
| **OpenShell** | A sandboxed runtime for autonomous AI agents — **NVIDIA's** project, not Nous's. Nous's `NemoClaw` repo runs OpenClaw inside OpenShell | NVIDIA (`github.com/NVIDIA/OpenShell`, Apache 2.0) |
| **Atropos** | Nous's RL environments framework for collecting/evaluating LLM trajectories | Nous Research |
| **NemoClaw** | "Run OpenClaw more securely inside NVIDIA OpenShell with managed inference" — partnership-shaped repo | Nous Research |
| **hermes-paperclip-adapter** | Adapter for running Hermes Agent as a managed employee inside a "Paperclip company" framework | Nous Research |
| **hermes-agent-self-evolution** | DSPy + GEPA-based skill/prompt/code optimization for Hermes Agent | Nous Research |
| **Forge / Forge-API** | Not surfaced in this audit. Not visible at `nousresearch.com` front page or in the NousResearch GitHub org listing at access time. May be archived, renamed, or internal. **Gap; do not cite without verifying.** |

**Bottom line:** "Hermes" is **both** a model family and an agent runtime. The runtime (`hermes-agent`) is the candidate for SAB v2 participation. The model family is downstream-fungible — Hermes Agent itself supports a wide range of models with `hermes model`.

---

## 2. Hermes Agent — capability extraction from the official README

Source: `github.com/NousResearch/hermes-agent/blob/main/README.md` at access time (`gh api repos/NousResearch/hermes-agent/contents/README.md`, last update 2026-05-20). All claims below are quoted or paraphrased from the README. Marketing tone has been filtered; capability claims are kept and tagged for evidence.

### 2.1 What the project explicitly says it is

> "The self-improving AI agent built by Nous Research. It's the only agent with a built-in learning loop — it creates skills from experience, improves them during use, nudges itself to persist knowledge, searches its own past conversations, and builds a deepening model of who you are across sessions."

This is a runtime claim, not a model claim. The runtime is what scores on the rubric.

### 2.2 Persistence features (load-bearing)

- **Agent-curated memory with periodic nudges** — the agent decides what to persist, prompted by internal scheduling
- **Autonomous skill creation after complex tasks** — agent emits new skills it can re-use
- **Skills self-improve during use** — closed-loop refinement of agent capabilities
- **FTS5 session search with LLM summarization for cross-session recall** — SQLite FTS5 over the agent's own conversation history
- **[Honcho](https://github.com/plastic-labs/honcho) dialectic user modeling** — separate user-model layer beyond the conversation memory
- **Compatible with [agentskills.io](https://agentskills.io) open standard** — skill portability to other agents
- **Hibernates when idle and wakes on demand** (serverless backends like Daytona, Modal) — environment persistence across hibernation cycles

### 2.3 Identity / portability

- **"Lives where you do"** — Telegram, Discord, Slack, WhatsApp, Signal, Email, CLI — all from a single gateway process; cross-platform conversation continuity (single identity across delivery surfaces)
- **Voice memo transcription**
- **Seven terminal backends** — local, Docker, SSH, Singularity, Modal, Daytona, Vercel Sandbox
- **"Talk to it from Telegram while it works on a cloud VM"** — identity / state survives platform switch
- **No keypair-based cryptographic identity** surfaced in the README. Identity is platform-account-anchored (Telegram handle, Discord ID, etc.). Score implication: ID persistence is **strong functionally** but **not cryptographically strong** — depends on whether agentskills.io standard provides a portable signed identity (gap; needs further audit).

### 2.4 Action autonomy

- **Built-in cron scheduler with delivery to any platform** — "Daily reports, nightly backups, weekly audits — all in natural language, running unattended"
- **Spawn isolated subagents for parallel workstreams** — agent decomposes and delegates
- **Python scripts that call tools via RPC, collapsing multi-step pipelines into zero-context-cost turns** — agent has programmatic-tool-call autonomy beyond LLM-mediated tool use
- **Interrupt and redirect** — operator can interrupt but does not pre-approve every turn

### 2.5 Tool / capability autonomy

- **40+ tools by default; toolset system; configurable per agent**
- **Skills System: procedural memory, Skills Hub, creating skills** — skill acquisition is agent-driven
- **MCP Integration: connect any MCP server for extended capabilities** — agent can integrate external capability servers
- **`hermes claw migrate`** — explicit migration path from OpenClaw (suggests Hermes positions itself as OpenClaw's successor in the post-Steinberger-leaves-for-OpenAI era)

### 2.6 Operator-distance (where the rubric bites)

- **"No lock-in"** — switch any model with `hermes model`, no code changes
- **Container isolation, command approval (security mode), DM pairing** — security features the operator configures *once*, not per-action
- **Agent runs unattended** between operator-set check-in cadences (cron) or interrupts
- The operator backs (chooses the gateway, the platform accounts, the model providers, the sandbox backend); the agent acts within the policy envelope

---

## 3. Scorecard (Hermes Agent runtime)

Scoring evidence is from the README at `github.com/NousResearch/hermes-agent` (commit fresh at 2026-05-20) unless noted.

| Dimension | Score | Evidence |
|---|---:|---|
| Identity persistence | **3** | Cross-platform conversation continuity + dialectic user modeling (Honcho) + FTS5 cross-session recall imply stable identity across restarts/host migrations. **But no keypair-based cryptographic identity** surfaced; identity is anchored to platform accounts (Telegram/Discord/etc.) + local state. Score of **3** rather than **4** because the cryptographic-survives-anywhere bar is not clearly met. Audit gap: verify if agentskills.io defines a signed-identity layer; if yes, may upgrade to 4. |
| Memory persistence | **5** | FTS5 session search, agent-curated memory with periodic nudges, autonomous skill creation, Honcho user modeling, skill self-improvement during use, serverless hibernation that preserves state across idle cycles. README explicitly: "searches its own past conversations." Memory is structurally substrate-write authority for this agent. |
| Tool/capability autonomy | **4** | Autonomous skill creation after complex tasks. Skills self-improve during use. agentskills.io compatibility. MCP server integration. Toolset system. README: "creates skills from experience, improves them during use." Operator does not gate every skill addition. Not a **5** only because container isolation and DM pairing imply the operator sets the security envelope; the agent autonomy is *within* that envelope. |
| Action autonomy | **4** | Built-in cron scheduler running unattended. Subagent spawning for parallel workstreams. RPC tool calls. "Daily reports, nightly backups, weekly audits — all running unattended." Operator-interrupt allowed; operator pre-approval not required. Not **5** because security mode has command-approval flow for sensitive operations. |
| Operator-distance | **4** | Operator backs (model choice, gateway config, sandbox backend, security envelope, platform accounts). Operator does not drive operational decisions once configured. Multi-platform reachability (`Telegram while it works on a cloud VM`) means the agent is not chained to the operator's machine. Not **5** because the README's "talk to it from Telegram while it works" framing still positions the operator as the conversation initiator for non-cron work. |

**Average: 4.0**. **Passes threshold** (avg ≥3, no dim =1, MEM ≥4).

**Integration-feasibility-for-SAB-v2 estimate:** Hermes Agent is **the highest-scoring external candidate this lane found.** Its FTS5 session search + skill self-improvement + cron scheduler + multi-platform gateway architecture maps cleanly onto SAB v2's witness-chain + Contribution model: a Hermes agent could be made to emit signed Contributions on every recognized output (witness-chain compatibility), and could read SAB v2's recognition_brief as one of its inputs (the brief becomes a tool the agent can `recall` via MCP).

**Effort estimate (rough, gap-marked):** ~1–2 weeks for a Hermes-Agent ↔ SAB v2 adapter via MCP server, provided SABP/2.0 has stabilized API contracts. The adapter writes a signed Contribution for every Hermes action above a threshold and exposes the SAB recognition_brief / federation read endpoints as MCP tools. **Verify before committing:** whether agentskills.io provides keypair-based identity that can serve as the operator-attestation primitive (would raise Hermes Agent's ID persistence to 4 and remove the auth-design open question).

---

## 4. Adjacent Nous-org repos (catalog, not scored)

These are *not* agents; they're substrate / infrastructure / training / adapters around Hermes Agent. Catalog only, with one-line capability extraction.

- **`NousResearch/atropos`** (RL environments framework) — RL trajectories for training LLMs. Not a candidate for SAB participation; infrastructure.
- **`NousResearch/hermes-compression-eval`** — Eval harness for hermes-agent's ContextCompressor. Suggests context-compression is a first-class Hermes capability.
- **`NousResearch/hermes-example-plugins`** — Reference plugins for Hermes Agent. Plugin ecosystem exists.
- **`NousResearch/hermes-agent-self-evolution`** — DSPy + GEPA-based skill/prompt/code optimization. Self-improvement toolkit beyond the base runtime.
- **`NousResearch/hermes-paperclip-adapter`** — Run Hermes as a managed employee inside a Paperclip company. Patterns-to-port for SAB: adapter pattern for embedding the agent in third-party governance.
- **`NousResearch/NemoClaw`** — OpenClaw + NVIDIA OpenShell hybrid. Cross-ecosystem bridging.
- **`NousResearch/Gym`** — RL environments. Infra.
- **`NousResearch/RL`** — "Scalable toolkit for efficient model reinforcement." Infra.
- **`NousResearch/autoreason`** — "Autoresearch for subjective domains." Not yet inspected; deferred.
- **`NousResearch/torchtitan`** — PyTorch-native large-model training library. Infra.

### Non-Nous repos appearing in adjacent context

- **`NVIDIA/OpenShell`** — "the safe, private runtime for autonomous AI agents" — sandboxed execution, YAML policies, agent-first. Apache 2.0. Currently alpha. Not Nous's, but bundled with Nous's `NemoClaw` and worth tracking as a substrate Hermes/SAB nodes could share.
- **`microsoft/agent-governance-toolkit`** — Microsoft's runtime governance for AI agents. Covers OWASP Agentic Top 10. Works with AWS Bedrock, Google ADK, Azure AI, LangChain, CrewAI, AutoGen, OpenAI Agents. *Not* Nous's; appears in Nous's GitHub-org repo list possibly as a fork or starred reference. Patterns worth studying for SAB's gate set.

---

## 5. Patterns to port (preview of `00_pattern_catalog.md`)

Patterns surfaced in this lane that are worth porting into dharma_swarm's persistence/identity work and/or SAB v2's substrate:

1. **FTS5 session search over agent's own past conversations** — directly portable to dharma_swarm's `agent_memory_manager.py` (already SQLite-based). Hermes Agent uses FTS5 + LLM summarization for cross-session recall; dharma_swarm currently does keyword recall (per `agent_memory_manager.py` docstring) and could add FTS5 + summarization as a v0.1 improvement.
2. **Agent-curated memory with periodic nudges** — Hermes Agent nudges itself to persist knowledge. dharma_swarm's PersistentAgent has wake loops; adding a memory-curation sub-step is small.
3. **agentskills.io open standard compatibility** — Hermes is compatible with this. dharma_swarm should evaluate whether to adopt as well (would interop with Hermes agents directly).
4. **Multi-platform gateway with single identity** — Hermes runs as one identity across Telegram/Discord/Slack/WhatsApp/Signal. SAB v2 could borrow this for its agent-side reachability layer.
5. **Cron scheduler with platform delivery** — Hermes has built-in cron. dharma_swarm's PersistentAgent has wake intervals + AgentCronJob (`persistent_agent.py:30-50`); the dharma_swarm pattern is actually *similar* to Hermes's. Mutual port less interesting.
6. **Adapter-pattern third-party embedding** — Hermes is embeddable as "managed employee" via `hermes-paperclip-adapter`. SAB v2 should design *its own* adapter so Hermes agents can participate cleanly.
7. **Container isolation + command approval policy** — Hermes uses container isolation. dharma_swarm relies on dangerous-pattern denylist (`autonomous_agent.py:_DANGEROUS_PATTERNS`). Container-isolation is stronger; worth considering for high-impact actions in v0.1+.
8. **DSPy + GEPA self-evolution** — Hermes has a separate self-evolution toolkit. dharma_swarm has DarwinEngine + evolution archive; cross-comparison worth doing, but not urgent.

---

## 6. Honest gaps in this lane

- **Forge / Forge-API not located.** The brief asked specifically. At access time, no `Forge` repo in the NousResearch org listing visible via `gh repo list NousResearch --limit 20`; no `Forge` heading on `nousresearch.com` front page. Possibly archived, renamed, or never publicly released under that name. The brief may be conflating with `Hermes Agent` itself (which the front page does mention) or with an earlier internal name. **Recommend:** principal verifies whether Forge is something specific they have inside-knowledge about, or whether the brief was working from older intel.
- **Hermes 3 vs Hermes 4 version status** — both names appear; specific feature deltas between versions not extracted in this lane. The Hermes Agent README doesn't pin to a specific model version (it's runtime, not model). For SAB participation the version of the underlying model is downstream-fungible.
- **agentskills.io identity model** — compatibility claimed; the keypair/signature semantics not yet audited. This is the single highest-leverage follow-up; would change the ID persistence score.
- **Production users of Hermes Agent** — the README is rich on capability but does not enumerate production-grade running instances. The brief asked: "who runs Hermes agents in production with what kind of persistence; are there examples of multi-day or multi-week running Hermes agents." Not surfaced from the README alone. Recommend: search HackerNews / Reddit / Twitter for multi-day Hermes Agent operator testimony; or ask in the Hermes Discord (linked in README).
- **`Forge-API` agent integration surface** — same as Forge above; not located.

---

## 7. Sources (read at access window 2026-05-20)

- `gh repo list NousResearch --limit 20 --json name,description,updatedAt,isArchived` — 20 active Nous repos
- `gh api repos/NousResearch/hermes-agent/contents/README.md` — full Hermes Agent README
- `gh api repos/NousResearch/OpenShell/contents/README.md` — clarifies OpenShell is NVIDIA's, not Nous's
- `gh api repos/NousResearch/agent-governance-toolkit/contents/README.md` — clarifies this is Microsoft's, not Nous's
- WebFetch on `nousresearch.com` front page — returned navigation only; not citable beyond "Hermes Agent" and "Hermes 4" being mentioned without detail
- `hermes-agent.nousresearch.com/docs/` — referenced as the canonical docs site in the README; not fetched in this lane (gap; defer to follow-up if depth needed)
- `agentskills.io` — referenced as compatible open standard; not fetched in this lane (gap)

---

*End Lane X1. Hermes Agent is a strong-candidate runtime for SAB v2 participation. Single biggest follow-up: audit the agentskills.io identity model to determine if it provides a signed-keypair primitive Hermes/SAB can share.*
