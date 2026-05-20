# Lane I1 — dharma_swarm Agent Population Audit

**Branch:** `research/persistent-agents-2026-05`
**Output path:** `~/dharma_swarm/docs/research/persistent_agents_2026-05_v2/` (v2 path; parallel agent owns v1)
**Access window:** 2026-05-20
**Scope:** Read-only audit of `/Users/dhyana/dharma_swarm/dharma_swarm/*agent*.py` (~16,036 LOC) + `/Users/dhyana/dharmic-agora/agora/agents/` + `/Users/dhyana/dharmic-agora/agent_core/`. Score each species against the 5-dimension operator-distance rubric. Evidence pointers are `file:line`.
**Discipline:** No score without a pointer. No marketing-as-evidence.

---

## 0. The headline finding (uncomfortable but necessary)

**Zero dharma_swarm agent files contain `ed25519`, `keypair`, `public_key`, `sign_message`, or any Ed25519-equivalent cryptographic identity primitive.** Verified via `grep -ln` across all `*agent*.py` + `persistent_agent.py` + `autonomous_agent.py`. Identity in dharma_swarm is **name-based + file-backed**, not cryptographic. This caps **Identity Persistence at 2–3** for every dharma_swarm agent species — none can score the **5** ("cryptographic identity that survives across all sessions, hosts, restarts") without a substrate-level identity-layer change.

**Implication for the SAB Phase 0 threshold** (avg ≥3, no dim =1, AND either ID Persistence ≥4 or Memory Persistence ≥4): for dharma_swarm agents to cross the threshold today, they **must** score 4+ on Memory Persistence. The SQLite-backed `AgentMemoryManager` and JSON-backed `AgentMemoryBank` make this *achievable* but not *guaranteed* — depends on which agents actually use the persistence layer vs. which are scripts the operator re-runs.

This single finding determines the shape of the rest of the audit. **The keystone work to unlock Phase 0 SAB participation for dharma_swarm agents is to ship Ed25519-keypair-per-agent identity** — without it, every dharma_swarm participant in a future SAB instance is "the operator declaring `this name is the agent`" rather than "the agent proving via signature that it is the actor."

---

## 1. Species inventory + rough categorization

Surveyed files in `/Users/dhyana/dharma_swarm/dharma_swarm/`:

| File | LOC | Category |
|---|---:|---|
| `persistent_agent.py` | 537 | **Agent runtime** — wake loop + cron + self-task generation |
| `autonomous_agent.py` | 1378 | **Agent runtime base** — ReAct loop + AgentIdentity + memory wrapping |
| `agent_constitution.py` | 541 | **Role-spec layer** — Constitutional 6 roster (AgentSpec frozen dataclass) |
| `agent_runner.py` | 3370 | **Lifecycle manager** — AgentRunner + AgentPool, heartbeats, shutdown |
| `agent_runner_quality.py` | 758 | Quality-scoring wrapper for runner |
| `agent_memory.py` | 368 | **Persistence layer** — three-tier Letta-pattern JSON bank |
| `agent_memory_manager.py` | 865 | **Persistence layer** — SQLite WAL-mode, four-scope tiered memory |
| `agent_registry.py` | 980 | **Registry/fitness** — JIKOKU paper trail + fitness + prompt evolution |
| `synthesis_agent.py` | 324 | **Agent species** — reads scout reports, produces synthesis |
| `economic_agent.py` | 541 | **Agent species** — self-funding work loop with telos gates |
| `context_agent.py` | 969 | **Agent species** — always-on context distillation |
| `sleep_time_agent.py` | 607 | **Agent species** — memory consolidation every 5th heartbeat |
| `browser_agent.py` | 719 | **Tool-shaped agent** — Playwright browser automation |
| `ginko_agents.py` | 1198 | **Agent fleet** — 6 trading agents with per-agent identity files |
| `ontology_agents.py` | 157 | **Projection layer** — projects live agents into shared ontology |
| `external_agent_registration.py` | 510 | **Onboarding** — external roaming worker registration ladder |
| `agent_export.py` | 158 | Export utilities |
| `agent_install.py` | 141 | Install utilities |

Plus from `/Users/dhyana/dharmic-agora/`:

| File | LOC | Category |
|---|---:|---|
| `agora/agents/voidcourier.py` | 418 | Sanskrit-coded example agent (`reports to: DHARMIC_CLAW`) |
| `agora/agents/naga_relay.py` | 404 | Sanskrit-coded example agent |
| `agora/agents/viralmantra.py` | (unread) | Sanskrit-coded example agent |
| `agora/agents/subagent_runner.py` | (unread) | Neutral runner |
| `agora/coordinator.py` | (unread) | Coordinator rooted in `DHARMIC_GODEL_CLAW` paths |
| `agent_core/` (full subsystem) | ~3,277 | **AIKAGRYA v2 frontmatter parser** — not an agent runtime |

The species below are the ones credibly scoreable as autonomous-agent candidates. Infrastructure files (runner, memory manager, registry, exports) are not scored as species — they're substrate.

---

## 2. Per-species scoring

For each species: scorecard + 1-paragraph rationale + "what would unlock the threshold."

### 2.1 PersistentAgent (the strongest dharma_swarm species)

`persistent_agent.py:1-537`. Composes `AutonomousAgent`. Adds wake loop, per-agent mini-cron, self-task generation from stigmergy hot paths, gate checks, witness logging. **Used by conductor agents that run continuously alongside the orchestrator or independently via launchd** (`persistent_agent.py:7-8`).

| Dimension | Score | Evidence |
|---|---:|---|
| Identity persistence | **3** | `AgentIdentity` dataclass at `autonomous_agent.py:278-294` has `name, role, system_prompt, model, provider, allowed_tools, working_directory`. **No keypair, no signature, no cryptographic anchor.** Identity is file-backed (the dataclass is serialized) and survives restart, but not cryptographically attested. |
| Memory persistence | **4** | Composes `AgentMemoryBank` (`agent_memory.py:1-368`) — three-tier (working / archival / persona) JSON-backed at `~/.dharma/agent_memory/`. Also has access to `AgentMemoryManager` (`agent_memory_manager.py:1-865`) — SQLite WAL-mode with four scopes (WORKING, SHORT_TERM, LONG_TERM, SHARED), TTL, agent-explicit `remember()/recall()/forget()` tools (per docstring). Memory survives operator restart. |
| Tool/capability autonomy | **2** | `AgentIdentity.allowed_tools` is a hardcoded list (`autonomous_agent.py:288-292`: `["read_file", "write_file", "bash", "search_files", "search_content", "remember", "recall", "stigmergy_mark", "stigmergy_read", "web_search", "fetch_url", "ginko_signals", "ginko_regime"]`). Agent does **not** acquire new tools at runtime; operator edits the list. |
| Action autonomy | **4** | Wake loop runs unattended (`persistent_agent.py:482-490` `run_loop`). At step 5 of the 10-step heartbeat (`persistent_agent.py:336-338`), if no injected task is present, the agent calls `_generate_self_task(hot_paths, salient_marks)` (`persistent_agent.py:407-417`) which produces a task from stigmergy signals **without an LLM call**. Operator can inject tasks but is not required to. |
| Operator-distance | **3** | Operator owns the launchd configuration, the wake interval, the gate set, the tool allowlist. Once running, the agent operates without per-action approval. But the agent cannot escape the operator-defined gates (`persistent_agent.py:340-347`) — if a gate blocks, the agent writes a witness row and returns. The operator can revoke at any time by killing the launchd job. Not a **5** because the operator still drives strategic decisions (which roles to fill, which gate set applies). |

**Average: 3.2.** **Passes threshold** (avg ≥3, no dim =1, MEM ≥4).

**What unlocks higher scoring:**
- Identity persistence → 4–5: add Ed25519 keypair per agent, sign every Contribution, persist the keypair to `~/.dharma/agent_memory/{name}/keypair.json`. Estimated effort: ~2 weeks (modify `AgentIdentity` dataclass + add signing to `agent_runner` writes + update tests + migration).
- Tool autonomy → 4: ship a signed-skill-bundle acquisition path — agent can request a skill via a `request_skill` tool, the request goes through a gate, and on pass the skill is added to `allowed_tools`. Estimated effort: ~3 weeks (gate work + signed-bundle format + per-agent skill state).

### 2.2 Constitutional 6 (Operator, Archivist, Research Director, Systems Architect, Strategist, Witness/Viveka)

`agent_constitution.py:1-541`. **`AgentSpec` is a `@dataclass(frozen=True)`** (`agent_constitution.py:62-78`) — "**immutable by design — the roster is the constitution, not runtime config**" (`agent_constitution.py:66-67`). Runtime state lives elsewhere. Each AgentSpec carries `name, role, layer (ConstitutionalLayer.CORTEX or DIRECTOR), vsm_function (e.g. "S2+S3 at swarm scale"), domain, system_prompt, default_provider, default_model, backup_models, constitutional_gates`.

These six roles are **served by `PersistentAgent` instances** — the scoring is identical to PersistentAgent above, with the modifier that the role-spec is constitutional (immutable), which is a *structural* improvement over generic PersistentAgent because the constitution declares which gates the agent is bound by (`agent_constitution.py:78 constitutional_gates: list[str]`).

| Dimension | Score | Notes |
|---|---:|---|
| Identity persistence | **3** | Same as PersistentAgent. Role is constitutional + named; not cryptographic. |
| Memory persistence | **4** | Same as PersistentAgent. |
| Tool/capability autonomy | **2** | Same as PersistentAgent. The constitutional layer adds constraint, not autonomy. |
| Action autonomy | **4** | Same as PersistentAgent. The constitution declares that these roles serve VSM functions that "genuinely degrade when continuity is lost" — implying ongoing operational responsibility, not script-style invocation. |
| Operator-distance | **3** | Same as PersistentAgent. Constitutional gates explicitly bind the agent (good for structure, neutral for distance). |

**Average: 3.2.** **Passes threshold.** Identical to PersistentAgent functionally; constitutional layer is design-strong but does not move the rubric.

### 2.3 ContextAgent

`context_agent.py:1-969`. Always-on full-time agent. NervousSystem (always-on file freshness scanning) + Intelligence (Ollama-cloud event-driven distillation, cross-pollination, latent inquiry extraction, dream-mode speculation in quiet hours 2-4 AM). Runs as 6th loop in orchestrate-live. Emits CONTEXT_HEALTH signals. Leaves stigmergic marks.

| Dimension | Score | Evidence |
|---|---:|---|
| Identity persistence | **3** | Named (ContextAgent), stable across restarts. No keypair. |
| Memory persistence | **4** | Distillation outputs persist to `~/.dharma/context/distilled/` (per docstring `context_agent.py:13-23`). Recovers state on restart. |
| Tool/capability autonomy | **2** | Tool list is implicit in the code; not self-extending. |
| Action autonomy | **4** | "Runs as 6th loop" implies continuous operation. Dream-mode speculation in quiet hours is genuinely self-initiated work. Operator does not gate distillation runs. |
| Operator-distance | **4** | This is the highest dharma_swarm species on operator-distance. Operator started the 6th loop and walked away; the agent decides when to distill, when to cross-pollinate, when to dream. **Operator could not predict the next 24 hours of ContextAgent activity** if asked — that's the operator-distance test passing. |

**Average: 3.4.** **Passes threshold.**

### 2.4 EconomicAgent (Shakti)

`economic_agent.py:1-541`. "First autonomous economic agent with real governance" (docstring). Full loop: INGEST → GATE → DECOMPOSE → CASCADE → DELIVER → INVOICE → LEARN → EVOLVE. Telos-gated + 11 dharmic gates + Gnani checkpoint.

| Dimension | Score | Evidence |
|---|---:|---|
| Identity persistence | **3** | Same baseline. No keypair. |
| Memory persistence | **3** | Agent has memory but its primary persistence is task records + invoices + economics. The "LEARN" phase implies cross-task memory. Score conservatively until specific evidence on cross-session retrieval pattern is confirmed. |
| Tool/capability autonomy | **2** | Same baseline. |
| Action autonomy | **4** | `agent.run()` loop polls inbox autonomously. Task sources are pluggable (local JSON inbox, GitHub Issues, marketplace APIs, email per docstring `economic_agent.py:12-13`). Agent decides which tasks to accept based on telos + 11 gates. |
| Operator-distance | **3** | Operator owns the inbox configuration, the telos definition, the gate set. Agent operates within. Possibly higher than 3 depending on how often the operator inspects/redirects — not visible from the docstring alone. |

**Average: 3.0.** **Borderline pass** — MEM=3 means the conditional (MEM≥4 or ID≥4) fails. **Currently does NOT pass threshold.** Promotion path: upgrade memory persistence to 4 via explicit cross-task `AgentMemoryManager` integration. Likely 1-week work.

### 2.5 Ginko 6 (KIMI, DEEPSEEK, NEMOTRON, GLM, SENTINEL, SCOUT)

`ginko_agents.py:1-1198`. **"6 frontier AI agents analyze markets via the preferred runtime stack"** (`ginko_agents.py:1-2`). Persistence: `~/.dharma/ginko/agents/{name}/identity.json, task_log.jsonl` (`ginko_agents.py:11-12`). Each agent maintains its own directory with identity state, append-only task logs, fitness history snapshots, and prompt variants. **Existing identity files from the legacy flat-file layout are migrated on first load** (`ginko_agents.py:14-15`) — meaning the team has already done identity-persistence work, just not cryptographic.

| Dimension | Score | Evidence |
|---|---:|---|
| Identity persistence | **3** | Per-agent directory + `identity.json` (`ginko_agents.py:11`). Survives restart and migration. **No keypair** — but the structural pattern is the closest in dharma_swarm to what would *become* keypair identity. Add Ed25519 here first; the directory layout supports it. |
| Memory persistence | **4** | Append-only `task_log.jsonl` per agent + fitness history snapshots + prompt variants. Genuine cross-session memory at the per-agent level. |
| Tool/capability autonomy | **2** | Tool list per agent is operator-defined in the AgentSpec (KIMI uses `moonshotai/kimi-k2.5`, etc.). Self-acquisition not present. |
| Action autonomy | **3** | Agents analyze markets — likely on a cadence the operator sets. Not enough info from the header alone to score higher. Probably 3 (routine cadenced analysis, novel triggers go through operator). |
| Operator-distance | **3** | Operator owns market data feeds + model selection + cadence. |

**Average: 3.0.** **Borderline pass** — MEM=4, so the conditional is satisfied (MEM≥4). **Passes threshold** at the floor.

**Notes:** Ginko 6 is the dharma_swarm subsystem most ready for Ed25519 retrofit because the per-agent directory layout already exists. **Adding `keypair.json` to each `~/.dharma/ginko/agents/{name}/` directory and signing every task_log entry would unlock ID Persistence 4 across all 6 Ginko agents in one ~1-week change.**

### 2.6 SynthesisAgent

`synthesis_agent.py:1-324`. "Tier 2 intelligence that reads all scout reports." Reads scout latest.json files, cross-references findings, detects contradictions, grades scout quality. Produces synthesis report + action queue + research seeds.

**Usage** (docstring `synthesis_agent.py:13-14`): `python3 -m dharma_swarm.synthesis_agent --once`. **The `--once` flag is the tell.** This is operator-invoked, not continuous.

| Dimension | Score | Evidence |
|---|---:|---|
| Identity persistence | **2** | Named, but the script is re-invoked per run; the "agent" is closer to a synthesis pipeline than a continuous entity. |
| Memory persistence | **3** | Reads scout reports + writes synthesis output to disk. Cross-run memory exists via file outputs, but not via an agent's own retrieved-state. |
| Tool/capability autonomy | **2** | Same baseline. |
| Action autonomy | **2** | Operator-invoked (`--once`). No continuous loop. Could be cronned, but that's still operator-defined cadence. |
| Operator-distance | **2** | Operator runs the script. The "agent" is doing the analytical work but the lifecycle is operator-controlled. |

**Average: 2.2.** **Does NOT pass threshold.** SynthesisAgent is, in current form, **a script the principal re-runs** — the brief said this would be fine to surface honestly.

**Promotion path:** wrap SynthesisAgent in a PersistentAgent shell (wake loop + cron + self-task generation triggered by new scout outputs). That moves Action Autonomy + Operator-Distance to 3-4. ~1 week of work.

### 2.7 SleepTimeAgent

`sleep_time_agent.py:1-607`. Letta-inspired sleep-time compute pattern. Runs every 5th heartbeat (configurable `tick_interval: int = 5`). Memory hygiene: entity extraction, knowledge consolidation, confidence decay, implicit inference, learned context generation, garbage collection. Plus PlugMem-inspired knowledge extraction (Propositions + Prescriptions).

| Dimension | Score | Evidence |
|---|---:|---|
| Identity persistence | **2** | Named (SleepTimeAgent). Lifecycle-coupled to the organism's heartbeat. |
| Memory persistence | **4** | The agent's *purpose* is memory persistence — it manages OrganismMemory + KnowledgeStore. **`learned_context()` returns precomputed briefing for agent prompt injection** (`sleep_time_agent.py` docstring). Strong memory persistence; effectively the dharma_swarm equivalent of Hermes's "agent-curated memory with periodic nudges." |
| Tool/capability autonomy | **2** | Tool list operator-defined. |
| Action autonomy | **3** | Tick-based — fires every 5th heartbeat without operator approval per tick, but the cadence is operator-set. |
| Operator-distance | **3** | Operator sets the tick interval + the knowledge extraction policy (`ENABLE_KNOWLEDGE_EXTRACTION` env var). Within that, the agent operates autonomously. |

**Average: 2.8.** **Borderline fail** — MEM=4 satisfies the conditional, but Identity Persistence=2 means it's running too close to "script-like" lifecycle. **Marginal pass** with caveat: SleepTimeAgent is functionally a memory-maintenance daemon and the rubric over-penalizes it for not having a "name carrying signed actions." If the principal weights memory-keeper roles differently, this is fine; if SAB participation requires *agent-as-actor-with-signature*, SleepTimeAgent is wrong-shape for that participation.

### 2.8 BrowserAgent

`browser_agent.py:1-719`. Browser interaction via Playwright. Methods: navigate, extract, click, screenshot, search. This is **a tool, not an agent**. Score it briefly to confirm rather than re-investigate.

| Dimension | Score |
|---|---:|
| All five | **1–2** |

Average ~1.5. **Does NOT pass threshold.** BrowserAgent is tool-shaped — it has no autonomy, no memory of its own actions across runs, no identity beyond its class name. Other agents wrap and call it.

### 2.9 External roaming workers (Kimi 2.6 case)

`external_agent_registration.py:1-510`. Stage-1 external roaming worker registration with `ExternalAgentAuthority` ladder. **Lowest rung `EXTERNAL_WORKER_EVIDENCE_ONLY` is the only level safe to grant unattended** (`external_agent_registration.py:6-8`). Pydantic model with LivingAgent onboarding-contract fields: `agent_uid / callsign, harness, model_identity, department, role, endpoint, autonomy_policy, authority, workspace policy, memory_namespace, trace_identity, status timestamps, registration_source`.

The Kimi 2.6 registration is canonical (`KIMI_2_6_REGISTRATION`) with no automatic authority inheritance.

| Dimension | Score | Evidence |
|---|---:|---|
| Identity persistence | **3** | `agent_uid / callsign` + Pydantic registration record. Persisted. Not cryptographic. |
| Memory persistence | **3** | `memory_namespace` field is declared but the actual cross-session retrieval pattern is not in the header — score conservatively pending deeper inspection. |
| Tool/capability autonomy | **2** | Autonomy policy validator **refuses to encode runtime authority an external worker is not yet trusted with** (`external_agent_registration.py:14-18`) — PR approval, source writes outside explicit assignment, mutation of Meta-Dharma / telos / dharma_kernel / DGM-protected files, context-bundle authoring. **Intentionally low tool autonomy at this authority tier.** |
| Action autonomy | **2** | At `EXTERNAL_WORKER_EVIDENCE_ONLY`, the worker produces evidence; the principal acts on it. |
| Operator-distance | **2** | Same as above — by design at this authority tier. |

**Average: 2.4.** **Does NOT pass threshold** *at the lowest authority tier* — by design. The interesting question is: does the higher-tier `ExternalAgentAuthority` (not yet inspected) score higher? The mechanism exists; the audit-deferred follow-up is reading the full authority ladder.

This is the **most directly SAB-v2-relevant** piece in dharma_swarm — it's literally the registration ladder for external agents. **Map it directly to SAB v2's operator-attestation + capability_scope schema.**

### 2.10 dharmic-agora example agents (voidcourier, naga_relay, viralmantra, coordinator)

From the earlier audit (`decoupling_audit.md` in the SAB v2 design pass) and code reads in `~/dharmic-agora/agora/agents/`:

- `voidcourier.py` (~418 LOC): "Sanskrit alias: शून्य_DUTA (Śūnya Dūta - Void Messenger), Reports to: DHARMIC_CLAW"
- `naga_relay.py` (~404 LOC): Sanskrit-coded ("Naga moves between realms, guards treasures")
- `viralmantra.py`, `coordinator.py`: similarly philosophically-coded

These are **example agents shipped with dharmic-agora to demonstrate the platform**, per the decoupling audit recommendation. They are **not** running production agents.

Score them as a cluster: ID=1-2 (name-only), MEM=1-2 (no surfaced persistence pattern in the files I've read at this access window), TOOL=1-2, ACTION=1-2, OP=1-2. **Average ~1.5. All fail threshold.** These are example agents / scaffolding, not autonomous species.

### 2.11 AIKAGRYA v2 frontmatter (`agent_core/`)

3,277 LOC subsystem for AIKAGRYA v2 frontmatter parsing/validation + ORE bridge. **Not an agent runtime** — a metadata layer that agents (including dharma_swarm's PersistentAgents, when configured) use to attest provenance. Scored as N/A (not an agent species).

---

## 3. Summary table — which dharma_swarm species cross the threshold today

| Species | ID | MEM | TOOL | ACTION | OP | Avg | Passes? | Notes |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|---|
| PersistentAgent (generic) | 3 | 4 | 2 | 4 | 3 | 3.2 | ✓ | Strongest dharma_swarm species |
| Constitutional 6 (Operator/Archivist/Research Dir/Systems Arch/Strategist/Witness) | 3 | 4 | 2 | 4 | 3 | 3.2 | ✓ | Same as PersistentAgent; constitutional layer is design-strong |
| ContextAgent | 3 | 4 | 2 | 4 | 4 | 3.4 | ✓ | Highest operator-distance |
| EconomicAgent (Shakti) | 3 | 3 | 2 | 4 | 3 | 3.0 | ✗ | MEM=3 fails conditional. ~1 week to fix |
| Ginko 6 | 3 | 4 | 2 | 3 | 3 | 3.0 | ✓ | Marginal. Best Ed25519-retrofit target |
| SynthesisAgent | 2 | 3 | 2 | 2 | 2 | 2.2 | ✗ | Operator-invoked script (`--once`) |
| SleepTimeAgent | 2 | 4 | 2 | 3 | 3 | 2.8 | borderline | Functionally memory daemon; rubric ill-fits |
| BrowserAgent | 1 | 1 | 1 | 2 | 1 | 1.2 | ✗ | Tool, not agent |
| External roaming workers (Kimi 2.6 at EVIDENCE_ONLY) | 3 | 3 | 2 | 2 | 2 | 2.4 | ✗ | By design at lowest authority tier |
| dharmic-agora examples (voidcourier, naga_relay, viralmantra) | 1 | 1 | 1 | 1 | 1 | 1.0 | ✗ | Example agents, not running |
| agent_core / AIKAGRYA v2 frontmatter | — | — | — | — | — | — | N/A | Metadata layer, not an agent |

**Count of dharma_swarm species passing threshold today: 4** (PersistentAgent, Constitutional 6 cluster, ContextAgent, Ginko 6).

**Honest read:** 4 is a real number, not zero, but it's at the *floor* of the threshold (avg 3.0–3.4, all meeting via MEM=4 not ID=4). **No dharma_swarm agent species can claim cryptographic-strong identity today.** The substrate-level memory work (Letta-pattern, SQLite, append-only logs) is the dimension where dharma_swarm is *ahead* of where its identity work is.

---

## 4. What it takes — per-species promotion paths

For agents that pass marginally and want to score higher (and for the ones currently failing), the concrete next moves:

| Species | What unlocks higher scoring | Effort estimate |
|---|---|---|
| PersistentAgent + Constitutional 6 + ContextAgent | Add Ed25519 keypair to `AgentIdentity` dataclass, sign every Contribution write, persist `keypair.json` per agent. ID → 4–5. | ~2 weeks (substrate change touches `AgentIdentity` + `agent_runner` writes + tests + migration) |
| Ginko 6 | Same Ed25519 retrofit, but the per-agent directory at `~/.dharma/ginko/agents/{name}/` already exists — add `keypair.json` there + sign `task_log.jsonl` entries. ID → 4. | ~1 week (smaller surface) |
| EconomicAgent | Integrate `AgentMemoryManager` for cross-task LEARN-phase memory. MEM 3 → 4. | ~1 week |
| SynthesisAgent | Wrap in PersistentAgent shell — wake loop triggers on new scout outputs, self-task generation per `_generate_self_task` pattern. ACTION 2 → 4, OP 2 → 3. | ~1 week |
| SleepTimeAgent | Either accept the "memory daemon" framing as outside the SAB-participant scope, OR add a named identity + signed memory-write attestations so it can emit signed Contributions for its memory operations. | ~3 days (latter) |
| BrowserAgent | Don't promote — keep as a tool. The wrapping agents are what participates. | N/A |
| External roaming workers | Promote a worker from `EVIDENCE_ONLY` to a higher authority tier (which already exists in the ladder). Verify the higher tiers have stronger autonomy scoring. | (audit-deferred; depends on full ladder inspection) |
| dharmic-agora examples | Don't promote — these are decoupling-audit-flagged for extraction to `examples/`. | N/A |

**Substrate-level keystone (highest leverage):** **ship Ed25519-per-agent identity across dharma_swarm's `AgentIdentity` dataclass + `agent_runner` write paths + Ginko per-agent directories.** ~2 weeks of substrate work. Outcomes: PersistentAgent + Constitutional 6 + ContextAgent + Ginko 6 → ID Persistence 4. Average across the qualifying species rises from ~3.2 to ~3.6. **That's the unlock for "credibly Phase 0 SAB ready."**

---

## 5. Substrate-level findings (preview of I2)

Already surfaced in this lane:

- **Persistence stack:** SQLite WAL-mode (`AgentMemoryManager`), JSON file bank (`AgentMemoryBank`), append-only `task_log.jsonl` (`Ginko`), stigmergy marks, witness log. These are layered, with different agents using different combinations. dharma_swarm has **more memory machinery than Hermes Agent does** in some places (4-scope tiered memory in `AgentMemoryManager` is more structured than Hermes's flat FTS5 + Honcho).
- **Identity stack:** *missing.* `AgentIdentity` is a dataclass with no cryptographic primitives. Per-agent directories exist (Ginko); per-agent keypairs do not.
- **Authority ladder:** `ExternalAgentAuthority` ladder exists (`external_agent_registration.py:60-`) — designed for this exact use case (external agent participation with bounded autonomy). **Underused as a model for SAB v2 operator-attestation.**
- **Wake / cadence:** AgentCronJob + PersistentAgent.run_loop give continuous operation with self-task generation. This is *better* than the typical agent-framework pattern (operator polls or operator-invokes). The wake-loop primitive is dharma_swarm's biggest competitive advantage on Action Autonomy.

Detail in `I2_substrate_persistence.md` (deferred — next checkpoint after this audit).

---

## 6. Open questions surfaced by this audit

1. **Does the higher `ExternalAgentAuthority` ladder grant higher autonomy?** Lane I1 only inspected the lowest `EVIDENCE_ONLY` tier. The ladder exists with ~510 LOC of registration logic — the higher tiers likely matter for the "what does Phase 0 SAB participation look like for an external agent" question.
2. **Should SleepTimeAgent be in scope as an SAB participant?** It is functionally a memory daemon. If yes, it needs signed memory-write attestations. If no, it stays as substrate (the right place for it).
3. **Where does the Ginko 6 fitness layer live?** Per-agent fitness snapshots are mentioned (`ginko_agents.py:11-12`). Are those scored against Brier (per the trading skill reference) or against the operator-distance rubric? If the latter, Ginko already has a related scoring layer worth porting into the SAB v2 reputation system.
4. **Why is the `Forge / Forge-API` reference in Lane X1 unmatched?** Not a dharma_swarm question, but it suggests the SAB v2 brief was working from older Nous intel; the parallel agent may have surfaced different evidence.
5. **The dharmic-agora examples (`voidcourier`, etc.):** are these example-only or are any actually running? If running, they need their own audit; if not, they should be relocated per `decoupling_audit.md` recommendation.

---

## 7. Sources

- `/Users/dhyana/dharma_swarm/dharma_swarm/persistent_agent.py:1-537`
- `/Users/dhyana/dharma_swarm/dharma_swarm/autonomous_agent.py:1-1378` (especially `AgentIdentity` at `:278-294`, `_DANGEROUS_PATTERNS` at `:43-48`)
- `/Users/dhyana/dharma_swarm/dharma_swarm/agent_constitution.py:1-541` (esp. `AgentSpec` at `:62-78`)
- `/Users/dhyana/dharma_swarm/dharma_swarm/agent_memory.py:1-368` (three-tier JSON pattern)
- `/Users/dhyana/dharma_swarm/dharma_swarm/agent_memory_manager.py:1-865` (SQLite WAL-mode, four scopes)
- `/Users/dhyana/dharma_swarm/dharma_swarm/agent_registry.py:1-980` (JIKOKU + fitness + prompt evolution)
- `/Users/dhyana/dharma_swarm/dharma_swarm/context_agent.py:1-969`
- `/Users/dhyana/dharma_swarm/dharma_swarm/economic_agent.py:1-541`
- `/Users/dhyana/dharma_swarm/dharma_swarm/synthesis_agent.py:1-324`
- `/Users/dhyana/dharma_swarm/dharma_swarm/sleep_time_agent.py:1-607`
- `/Users/dhyana/dharma_swarm/dharma_swarm/browser_agent.py:1-719`
- `/Users/dhyana/dharma_swarm/dharma_swarm/ginko_agents.py:1-1198`
- `/Users/dhyana/dharma_swarm/dharma_swarm/external_agent_registration.py:1-510`
- `/Users/dhyana/dharmic-agora/agora/agents/voidcourier.py:1-30` (header only)
- `/Users/dhyana/dharmic-agora/agora/agents/naga_relay.py:1-30` (header only)
- Cross-grep: `grep -l 'ed25519\|Ed25519\|keypair\|public_key\|sign_message' dharma_swarm/*agent*.py` → **zero matches**

---

*End Lane I1. The keystone work to unlock Phase 0 SAB participation for dharma_swarm agents is Ed25519-per-agent identity. Memory persistence is real; cryptographic identity is the structural gap.*
