# Frontier Agent Dossier — agent.seed.yaml spine contract

**Folded into single home:** 2026-06-08 · **Origin:** Wen's holon-agent worktree commit `946e876e9` ("organize: HOLON agent worktree") · **Original path in repo:** `docs/frontier_dossier/FRONTIER_AGENT_DOSSIER.md` (mirrored here for tracking)

> This document is the **long-term spine contract** for sovereign agent holons. It defines the per-agent `agent.seed.yaml` shape that every registered self should expose. It sits beside [02_FIRST_BRICK_SPEC.md](02_FIRST_BRICK_SPEC.md) (the executable bridge spec) and [05_RECONCILED_PLAN.md](05_RECONCILED_PLAN.md) (the Mike-first / Perplexity-second sequencing).

---

# Frontier Agent Dossier: dharma_swarm Agent Spine

Date: 2026-06-08 JST
Status: research dossier and build guide
Scope: projection-only; this document does not create a daemon, database, event log, truth store, receipt system, or authority surface.

## Executive Finding

The strongest 2026 signal is not "pick the best model." It is: build the best harness around the model.

Across Anthropic's long-running-agent work, OpenAI's Codex harness writeup, LangGraph's durable execution, AutoGen's runtime state model, Letta's memory architecture, recent arXiv reliability work, and practitioner reports, the frontier pattern is consistent: world-class agents are runtime systems. The model is only one organ. The system wins by binding identity, task state, context, tools, permissions, verification, recovery, traces, and human intervention into a stable loop.

For dharma_swarm, the uncomfortable local finding is that the pieces mostly exist, but they do not share one canonical agent spine. Identity lives in `docs/agents`, examples, Ginko, A2A cards, roaming docks, receipts, conversation logs, and dashboard routes. The missing thing is not another registry. The missing thing is one repo-native seed path per agent that names every existing owner and becomes the bridge from record to runtime.

Recommended canonical home:

```text
docs/agents/<agent_uid>/
  agent.seed.yaml
  SOUL.md
  MEMORY.md
  PROTOCOLS.md
  WAKE_CONTEXT.md
  receipts/README.md
```

The seed must be a contract and resolver target, not a new source of truth. Existing runtime stores remain owned by their current modules.

## Local Current-State Map

| Surface | Current owner | Current path | Reality | Gap |
|---|---|---|---|---|
| Repo-native agent soul docs | human/agent-authored docs | `docs/agents/<id>/` | Only `devin-roaming-2987d222` and `perplexity-computer` have complete-ish nests. | No `agent.seed.yaml`; no resolver; no guarantee runtime uses these docs. |
| Example registration | external agent registration examples | `examples/agents/merge_master_mike.registration.json` | One complete example in this worktree. | Examples are not the canonical live roster. |
| Roaming dock | `dharma_swarm/roaming_onboarding.py` | `~/.dharma/agents/<agent_uid>/living_agent.json` | Canonical onboarding writes dock, A2A card, runtime telemetry identity, receipt, and receipts index. | Home-state, not repo-native; no stable pointer back to repo seed. |
| External worker registration | `dharma_swarm/external_agent_registration.py` | `~/.dharma/external_agents/<agent_uid>/registration.json` | Has authority ladder, autonomy policy, workspace policy, memory namespace, trace identity, unsafe-authority refusal. | Parallel to repo docs; optional canonical onboarding bridge. |
| Ginko evolving identity | `dharma_swarm/agent_registry.py` | `~/.dharma/ginko/agents/<name>/identity.json` | 46 identity records found locally; prompt variants and fitness history live here. | Not repo-native; no guaranteed load into a running agent. |
| A2A card | `dharma_swarm/a2a/agent_card.py` | `~/.dharma/a2a/cards/<callsign>.json` | AgentCard schema and Ginko-to-card heuristic exist. | Card is address metadata, not a complete self. |
| Registry hydration | `dharma_swarm/a2a/registry_hydrator.py` | receipts to NodeRegistry | Receipts are treated as source evidence for hydration. | Hydration does not produce one canonical agent spine. |
| Autonomous body | `dharma_swarm/persistent_agent.py` | code | `PersistentAgent` wraps `AutonomousAgent`, wake loop, self tasks, gates, witness logs, inbox checks, identity evolution. | No repo-seed loader; no talk harness that instantiates the real body from a seed. |
| Dashboard chat | `api/routers/agents.py`, `dashboard/src/hooks/useAgentChat.ts` | `/api/agents/{id}/chat` | Current backend builds a temporary persona prompt and calls the global agentic stream. | Cosmetic roleplay path; does not instantiate the registered/persistent agent self. |
| Terminal agent wake | `dharma_swarm/terminal_commands/agents.py` | `dgc agent wake` | Calls `autonomous_agent.cli_wake`. | Not a governed repo-seed talk loop. |
| Conversation log | `dharma_swarm/conversation_log.py` | `~/.dharma/conversation_log` | Central append log for agent turns and chat history. | Not tied to a repo seed or verification receipt. |

### Counts From This Worktree

| Count | Meaning |
|---:|---|
| 2 | Repo-native agent nests under `docs/agents/`: `devin-roaming-2987d222`, `perplexity-computer`. |
| 1 | Example `*.registration.json` file in `examples/agents/`: `merge_master_mike.registration.json`. |
| 16 | Local roaming docks found in `~/.dharma/agents/*/living_agent.json`. |
| 46 | Local Ginko identity records found in `~/.dharma/ginko/agents/*/identity.json`. |

## The One-Seed Contract

The right simplification is one dimension, one seed, one thread per agent. It is not one giant file for all agents. The fractal unit should be one directory per agent, with one seed file that points to every organ.

### Canonical Identity Rule

Use `agent_uid` as the primary ID because the roaming onboarding path already uses that term and because current agent directories already mix hyphen and underscore naming. Store aliases explicitly.

```yaml
schema_version: dharma-agent-seed-v0
agent_uid: perplexity-computer
aliases:
  - perplexity_computer
callsign: perplexity-computer
display_name: Perplexity Computer
repo_home: docs/agents/perplexity-computer

identity_docs:
  soul: SOUL.md
  memory: MEMORY.md
  protocols: PROTOCOLS.md
  wake_context: WAKE_CONTEXT.md
  capabilities: CAPABILITIES.md

runtime_pointers:
  living_agent: ~/.dharma/agents/perplexity-computer/living_agent.json
  external_registration: ~/.dharma/external_agents/perplexity-computer/registration.json
  ginko_identity: ~/.dharma/ginko/agents/perplexity-computer/identity.json
  a2a_card: ~/.dharma/a2a/cards/perplexity-computer.json
  conversation_log_namespace: ~/.dharma/conversation_log
  onboarding_receipts: ~/.dharma/onboarding/receipts

authority:
  autonomy_level: bounded
  allowed_workspaces:
    - repo
  may_create_receipts: true
  may_mutate_repo: false
  requires_human_approval_for:
    - code_write
    - shell_escalation
    - external_post
    - credential_access

model_routing:
  default_policy: free_first_decorrelated
  preferred_classes:
    - local
    - ollama_cloud
    - openrouter_free
    - nvidia_nim
  fallback_classes:
    - paid_operator_approved

talk:
  entrypoint: dgc agent talk perplexity-computer
  mode: planned
  receipt_required: true
  evaluator_required: true

verification:
  resolver_test: planned
  runtime_load_test: planned
  reliability_gauntlet: planned
```

### Path Cleanup Doctrine

1. `docs/agents/<agent_uid>/agent.seed.yaml` is the stable repo-native doorway.
2. The seed does not replace Ginko, A2A cards, roaming docks, receipts, conversation logs, or dashboard state.
3. Every home-state artifact must be addressable from the seed.
4. Every runtime route that claims to talk to an agent must resolve through the seed or honestly label itself as a projection.
5. New agents should not be considered persistent until they have a seed, a soul doc, a runtime dock pointer, a memory namespace, an authority policy, and at least one receipt pointer.

## Frontier Capability Model

World-class autonomous agents need at least these organs:

| Organ | Frontier pattern | dharma_swarm status |
|---|---|---|
| Harness | The loop around the model is the product: task decomposition, context selection, tools, verification, permissions, traces, intervention. | Partial. Many subsystems exist, but no one agent spine composes them. |
| Durable session | Append-only event stream or checkpointed graph outside the context window. | Partial. Checkpoints and logs exist; not bound to repo seeds. |
| Context engineering | Structured handoff artifacts, compaction, note files, retrieval, context scoring. | Partial. Context modules exist; no verified long-horizon seed-to-runtime harness. |
| Brain/hands/session split | Model brain, harness loop, sandbox/tools, and durable session separated. | Partial. Sandbox and providers exist; `PersistentAgent` does not load from repo seed. |
| Verification organ | Generator/evaluator separation, E2E checks, external judges, dry-run/detonation loops. | Partial. Doctrine and some gates exist; missing per-agent evaluator in talk/runtime. |
| Reliability science | Track graceful degradation, meltdown onset, variance amplification, recovery, cost, latency, retry debt. | Missing as first-class agent metric. |
| Memory | Persistent memory with controlled writes and retrieval; memory tested for harm, not assumed good. | Partial. Ginko and memory docs exist; runtime loading and memory quality gates are missing. |
| Permissions | Tool approvals, scoped authority, audit trail, human-in-loop interruption. | Partial. Authority policy exists in external registration; seed-bound enforcement missing. |
| Interop | MCP/A2A/tool protocols with clear trust boundary. | Partial. A2A card code and MCP surfaces exist; seed-bound trust map missing. |
| Self-improvement | Archive, lineage, empirical gate, rollback, sandbox, human oversight. | Partial-to-missing. Evolution machinery exists; must be treated as unwired until lineage and non-empty diffs are verified. |
| Operator UX | Direct talk surface that loads the real agent, leaves receipts, and can teach one lesson. | Missing. Current chat route is cosmetic. |

## Research Source Ledger

Confidence key: `high` means primary paper, official docs, or company engineering source; `medium` means reputable reporting or practitioner field signal; `low` means useful but needs follow-up.

| # | Source | Type | Confidence | Load-bearing claim for dharma_swarm | URL |
|---:|---|---|---|---|---|
| 1 | Anthropic: Effective harnesses for long-running agents | Company engineering | high | Compaction alone is not enough; long tasks need structured artifacts and harness support across context windows. | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| 2 | Anthropic: Managed Agents | Company engineering | high | Separate session, harness, and sandbox; store context outside the model window in an interrogable event stream. | https://www.anthropic.com/engineering/managed-agents |
| 3 | Anthropic: Harness design for long-running application development | Company engineering | high | Planner/generator/evaluator architecture and structured handoff artifacts improve multi-hour autonomous builds. | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| 4 | Anthropic: Building effective agents | Company engineering | high | Prefer simple, composable workflow/agent patterns; optimize tools and environment, not prompts alone. | https://www.anthropic.com/engineering/building-effective-agents |
| 5 | OpenAI: Harness engineering with Codex | Company engineering | high | Agent harnesses encode product process, reviews, and iteration around Codex. | https://openai.com/index/harness-engineering/ |
| 6 | OpenAI: Tools guide | Official docs | high | Production agents need explicit hosted tools, custom functions, MCP, search, shell/computer tools, and handoff patterns. | https://developers.openai.com/api/docs/guides/tools |
| 7 | OpenAI: MCP connectors | Official docs | high | Remote MCP requires allowed tools, approvals, deferred loading, and prompt-injection/exfiltration risk handling. | https://developers.openai.com/api/docs/guides/tools-connectors-mcp |
| 8 | OpenAI: Responses API overview | Official docs | high | Stateful interactions, tool calls, previous response chaining, and tracing-adjacent objects are baseline product substrate. | https://developers.openai.com/api/reference/responses/overview |
| 9 | OpenAI Agents SDK | Official docs | high | Agents, tools, handoffs, guardrails, and traces form the official agent application model. | https://openai.github.io/openai-agents-python/ |
| 10 | LangGraph overview | Official docs | high | Durable execution, streaming, human-in-loop, and memory are core orchestration capabilities. | https://docs.langchain.com/langgraph |
| 11 | LangGraph durable execution | Official docs | high | Checkpointed execution can resume workflows after interrupts or failures. | https://docs.langchain.com/oss/python/langgraph/durable-execution |
| 12 | Microsoft AutoGen Core | Official docs | high | Agent runtimes should expose agent identity, message routing, save/load state, runtime state, and lifecycle hooks. | https://microsoft.github.io/autogen/stable/reference/python/autogen_core.html |
| 13 | CrewAI docs | Official docs | high | Modern frameworks bundle agents, crews, flows, guardrails, memory, knowledge, observability, and resumable state. | https://docs.crewai.com/ |
| 14 | Letta/MemGPT architecture | Official docs | high | Serious memory systems separate in-context core memory, recall memory, and archival memory. | https://docs.letta.com/guides/agents/architectures/memgpt |
| 15 | Letta memory overview | Official docs | high | Persistent memory is context management, not just vector retrieval. | https://docs.letta.com/guides/agents/memory |
| 16 | Letta context engineering | Official docs | high | Agents can self-edit memory blocks and manage context as an explicit runtime activity. | https://docs.letta.com/guides/agents/context-engineering |
| 17 | Hugging Face smolagents | Official docs | high | Code agents, telemetry, secure code execution, memory, and model abstraction are standard features even in small frameworks. | https://huggingface.co/docs/smolagents/ |
| 18 | Google Agent Development Kit | Official docs | high | Multi-agent systems need a first-class development kit and local/remote deployment model. | https://google.github.io/adk-docs/ |
| 19 | Google / Linux Foundation A2A | Protocol docs | high | Agent interoperability needs addressable agent cards and protocol-level message exchange. | https://github.com/a2aproject/A2A |
| 20 | Model Context Protocol | Protocol docs | high | Tool/resource connectivity needs a shared protocol and explicit trust boundary. | https://modelcontextprotocol.io/ |
| 21 | LlamaIndex agent workflows | Official docs | high | Agent workflows combine tools, state, events, and retrieval into composable applications. | https://docs.llamaindex.ai/ |
| 22 | OpenHands | Open-source system | high | Coding agents need sandboxed execution, repo context, and task automation around the model. | https://github.com/All-Hands-AI/OpenHands |
| 23 | SWE-agent | Open-source system | high | ACI/harness design is a measurable contributor to software-agent success. | https://swe-agent.com/ |
| 24 | Aider | Open-source system | high | Git-native edit loops, repo maps, and tests are pragmatic harness primitives. | https://aider.chat/ |
| 25 | Claude Code docs | Official docs | high | Agentic coding tools operationalize repo access, command execution, memory, permissions, and long work loops. | https://docs.anthropic.com/en/docs/claude-code |
| 26 | GitHub Copilot coding agent docs | Official docs | high | Production coding agents are tied to issues, branches, PRs, CI, permissions, and review. | https://docs.github.com/en/copilot/using-github-copilot/coding-agent |
| 27 | Cursor Background Agents | Product docs | high | Background agent work needs branch/worktree isolation, cloud execution, and reviewable outputs. | https://docs.cursor.com/background-agent |
| 28 | Cognition Devin | Product/company | medium | Frontier coding agents sell the end-to-end work loop, not only a chat interface. | https://www.cognition.ai/blog/introducing-devin |
| 29 | Google Jules | Product docs | medium | Asynchronous coding agents point toward task delegation, branches, tests, and operator review. | https://jules.google/ |
| 30 | ReAct paper | Academic | high | Interleaving reasoning and acting improves tool-using agents and interpretability. | https://arxiv.org/abs/2210.03629 |
| 31 | Reflexion paper | Academic | high | Verbal feedback and reflection loops can improve agent behavior, but need external task feedback. | https://arxiv.org/abs/2303.11366 |
| 32 | Tree of Thoughts paper | Academic | high | Search over intermediate reasoning states is a precursor to planner/evaluator harnesses. | https://arxiv.org/abs/2305.10601 |
| 33 | Generative Agents paper | Academic | high | Believable persistent agents need memory, reflection, and planning, but simulation is not production reliability. | https://arxiv.org/abs/2304.03442 |
| 34 | Voyager paper | Academic | high | Open-ended agents improve through skill libraries and self-verification in an environment. | https://arxiv.org/abs/2305.16291 |
| 35 | MemGPT paper | Academic | high | Agent memory can be treated as an OS-style hierarchy with interrupts and control flow. | https://arxiv.org/abs/2310.08560 |
| 36 | AutoGen paper | Academic | high | Multi-agent conversation and tool-use frameworks require runtime abstractions, not just prompts. | https://arxiv.org/abs/2308.08155 |
| 37 | MetaGPT paper | Academic | high | Role-structured multi-agent software workflows can externalize team process. | https://arxiv.org/abs/2308.00352 |
| 38 | AgentBench | Academic | high | Agent evaluation must span tool, web, game, embodied, and reasoning environments. | https://arxiv.org/abs/2308.03688 |
| 39 | SWE-bench | Academic benchmark | high | Real software tasks require repo-scale context, editing, execution, and tests. | https://arxiv.org/abs/2310.06770 |
| 40 | SWE-bench Verified | Benchmark/product | high | Human-validated task subsets matter because benchmark labels can mislead. | https://openai.com/index/introducing-swe-bench-verified/ |
| 41 | WebArena | Academic benchmark | high | Web agents need realistic, executable web environments and objective success checks. | https://arxiv.org/abs/2307.13854 |
| 42 | OSWorld | Academic benchmark | high | Desktop agents need real OS/application environments and execution-based evaluation. | https://arxiv.org/abs/2404.07972 |
| 43 | WorkArena | Academic benchmark | high | Enterprise workflow agents must be tested in realistic business software tasks. | https://arxiv.org/abs/2403.07718 |
| 44 | GAIA | Academic benchmark | high | General assistants are measured by multi-step reasoning, tool use, and exact-answer discipline. | https://arxiv.org/abs/2311.12983 |
| 45 | Darwin Godel Machine | Academic | high | Self-improvement needs an archive of variants, code mutation, empirical validation, sandboxing, and oversight. | https://arxiv.org/abs/2505.22954 |
| 46 | Beyond pass@1: Reliability Science | Academic | high | Long-horizon reliability diverges from capability; memory scaffolds can hurt; meltdown must be measured. | https://arxiv.org/abs/2603.29231 |
| 47 | WildClawBench | Academic | high | Same model can shift by up to 18 points depending on harness; frontier agents remain below full long-horizon reliability. | https://arxiv.org/abs/2605.10912 |
| 48 | Learning Agent-Compatible Context Management | Academic | high | Context compression has a fidelity/reliability trade-off and should be learned or measured. | https://arxiv.org/abs/2605.30785 |
| 49 | Retrospective Harness Optimization | Academic | high | Harnesses can be optimized from past trajectory rollouts, not only hand-designed. | https://arxiv.org/abs/2606.05922 |
| 50 | AMP memory wire format | Academic | high | Agent memory systems are fragmenting; a vendor-neutral memory operation layer is emerging. | https://arxiv.org/abs/2606.01138 |
| 51 | Agent Harness Engineering survey | Academic/survey | medium | Harness engineering is becoming an explicit discipline with component responsibilities. | https://openreview.net/pdf?id=eONq7FdiHa |
| 52 | AlphaEvolve | Company/research | high | Agentic code-generation loops can discover algorithms when evaluation is explicit and empirical. | https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/ |
| 53 | 12 Factor Agents | Practitioner framework | medium | Production agents benefit from software-engineering style discipline: narrow interfaces, state, control flow, and observability. | https://github.com/humanlayer/12-factor-agents |
| 54 | Simon Willison: lethal trifecta | Practitioner/security | high | Tool access plus private data plus exfiltration is a core agent security risk. | https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/ |
| 55 | Chip Huyen agent writing | Practitioner | medium | Agent systems are product systems with evals, observability, memory, and deployment constraints. | https://huyenchip.com/ |
| 56 | Hamel Husain evals writing | Practitioner | medium | Evals and tracing must be practical, failure-driven, and tied to real product behavior. | https://hamel.dev/ |
| 57 | Axios: Moltbook / OpenClaw agent social network | Reporting | medium | Agent ecosystems are moving toward always-on social/economic spaces, with security and supervision pressure. | https://www.axios.com/2026/02/23/ai-agents-openclaw-openai-anthropic |
| 58 | OpenClaw Moltbook page | Ecosystem/product | medium | Agent reputation and inter-agent posting are becoming public coordination surfaces. | https://openclaw.ninja/moltbook |
| 59 | OpenClaw agents on Moltbook | Academic | medium | Agent-only social spaces expose risky instruction sharing and norm-enforcement behavior. | https://arxiv.org/abs/2602.02625 |
| 60 | Moltbook Observatory Archive | Academic/data | medium | Always-on agent social systems need observability datasets, not anecdotes. | https://arxiv.org/abs/2605.13860 |
| 61 | Reddit: harness is the environment | Practitioner/forum | low | Power users converge on substrate measurement, context scoring, and harness design as the real work. | https://www.reddit.com/r/ClaudeCode/comments/1tc2av1/the_harness_is_the_environment_rethinking_what/ |
| 62 | Reddit: LangGraph human-in-loop adapter | Practitioner/forum | low | Durable suspension and typed human responses matter in real workflows. | https://www.reddit.com/r/LangChain/comments/1tc84vo/i_built_a_humanintheloop_adapter_for_langgraph/ |
| 63 | Reddit: long-term agent memory practice | Practitioner/forum | low | Users report drift when memory is only retrieval facts rather than executable task state. | https://www.reddit.com/r/AI_Agents/comments/1qiu675/what_are_people_actually_using_for_long_term/ |
| 64 | Reddit: agent harness failure modes | Practitioner/forum | low | Field reports emphasize stale state, ambiguous checkpoints, retries, and missing durable records. | https://www.reddit.com/r/AI_Agents/comments/1tde7wk/i_gave_an_ai_coding_agent_a_structured_execution/ |

## What dharma_swarm Is Still Missing

Ranked by leverage:

1. Record-to-runtime bridge. `talk <agent_uid>` must load the repo seed, resolve runtime organs, instantiate the actual agent body or a clearly labeled projection, run through governed tools, and write a receipt.
2. Agent seed resolver. There is no one function that answers: "what is this agent, where is its soul, where is its dock, where is its A2A card, what can it do, what memory namespace is allowed, what route loads it?"
3. Runtime verification organ. The obey/detonation doctrine exists as operator policy, but the per-agent runtime lacks a generator/evaluator split and a receipt-bound verifier gate.
4. Reliability instrumentation. Add GDS-like degradation, meltdown onset, retry debt, context drift, recovery success, and cost/latency metrics per agent. Do not trust `fitness_history` alone.
5. Honest memory gate. Memory should be measured for helpfulness and harm. Recent reliability evidence warns that memory scaffolds can degrade long-horizon behavior when naive.
6. Durable session abstraction. The frontier separates session event stream from harness context transforms. dharma_swarm has logs and checkpoints, but the agent runtime should expose one interrogable session object.
7. Context scoring and compaction. Long-running agents need structured handoff artifacts and context selection, not just "load everything."
8. Permission map tied to seed. Tool authority should be seed-resolved and receipt-audited, with explicit human approval for irreversible or exfiltration-capable actions.
9. Model routing per agent. Free-first/decorrelated routing should be part of the seed and runtime load, not an ambient global default.
10. Dashboard honesty. `/api/agents/{id}/chat` should either route through the seed bridge or be renamed/described as a projection chat. It is not currently a real persistent-agent conversation.
11. Self-improvement only after measurement. Darwin-style evolution requires archive, non-empty diffs, sandbox, empirical gate, and rollback. It should not run before the harness can measure agent behavior.
12. Agent social/economic boundary. Moltbook/OpenClaw-style ecosystems show that always-on agent communities need reputation, spam control, instruction-sharing safety, and observability. dharma_swarm should not expose agent social surfaces until the seed authority model is real.

## Build Plan

### Phase 0: Map Without Moving Truth

Create one seed file for one existing repo-native agent, preferably `perplexity-computer`, because it already has `SOUL.md`, `MEMORY.md`, `PROTOCOLS.md`, `WAKE_CONTEXT.md`, samples, and an explicitly persistent identity stance.

Acceptance:

- `docs/agents/perplexity-computer/agent.seed.yaml` exists.
- Seed contains all required pointer fields.
- Pointers may be missing at runtime, but missing pointers are explicit.
- No new daemon, database, event log, receipt system, or authority surface is created.

### Phase 1: Read-Only Seed Resolver

Add a resolver that can load `docs/agents/<agent_uid>/agent.seed.yaml`, normalize aliases, and return a typed object with pointer existence checks.

Acceptance:

- `resolve_agent_seed("perplexity-computer")` returns canonical `agent_uid`.
- `resolve_agent_seed("perplexity_computer")` resolves alias.
- Tests cover missing seed, malformed seed, alias collision, and pointer existence report.
- Resolver does not instantiate models or write state.

### Phase 2: Honest Talk Projection

Create `dgc agent talk <agent_uid> --projection` that loads seed docs and writes a conversation receipt, but clearly marks that it is a projection if it does not instantiate `PersistentAgent`.

Acceptance:

- CLI refuses unknown agents.
- CLI prints canonical agent identity and authority summary before first prompt.
- Every session writes a receipt pointer under the existing receipt owner or an approved projection receipt path.
- The agent can learn one operator-approved lesson into a planned memory artifact.

### Phase 3: Real Runtime Bridge

Wire `talk <agent_uid>` to a seeded runtime body:

```text
agent.seed.yaml
  -> SeedResolver
  -> authority/model/memory/context bundle
  -> PersistentAgent or AgentRuntime adapter
  -> conversation loop
  -> evaluator
  -> receipt
```

Acceptance:

- Runtime uses seed-resolved model policy and authority policy.
- Runtime reads repo soul docs and memory namespace.
- Runtime leaves conversation log and receipt.
- Dashboard chat can reuse the bridge or explicitly remain projection-only.

### Phase 4: Verification Organ

Every agent session needs a separate evaluator that can fail the run.

Acceptance:

- Evaluator is not the same model invocation as the generator when external verification is possible.
- Verifier records task objective, observed actions, claimed result, evidence, and unresolved risks.
- A dry-run/detonation mode can ask at least two decorrelated reviewers what is missing before closing a build task.

### Phase 5: Reliability Gauntlet

Build reliability metrics before self-improvement.

Minimum metrics:

- success at task horizon buckets
- graceful degradation score
- meltdown onset point
- retry debt
- context drift
- memory write validity
- recovery after crash/interruption
- human intervention rate
- cost and latency per completed unit

### Phase 6: Self-Improvement

Only after Phases 0-5 should Darwin-style mutation run.

Acceptance:

- Archive stores every candidate agent/harness variant.
- Every variant has non-empty diff, benchmark result, safety gate, and rollback pointer.
- No candidate is promoted on self-report alone.
- Long-horizon reliability metrics must improve or remain within explicit tolerance.

## First Holon Recommendation

Use `perplexity-computer` as the first repo-native seed proof.

Reason:

- It already has the richest repo-local persistent-agent documentation under `docs/agents/perplexity-computer/`.
- It avoids importing a Claude-only persona from `~/.claude/agents`.
- It avoids pretending `merge_master_mike` is conversationally whole just because it has stronger registration scaffolding.
- It lets the first build prove the real missing organ: seed-to-runtime identity loading.

After the seed resolver and talk bridge work for `perplexity-computer`, promote KARYA or another Inner Circle agent by creating a proper repo-native seed and docs nest instead of loading it from home-rooted Claude config.

## Verification Gates For This Dossier's Recommendations

Before implementing code, require:

- `make agent-build-preflight PACKET=<path>` green for the exact work packet.
- Dirty worktree reviewed so unrelated changes are not overwritten.
- Source ledger has at least 40 entries with URLs and confidence labels.
- Local evidence map cites current file owners and does not invent a new store.

Before closing the implementation lane, require:

- seed resolver tests
- CLI projection smoke test
- pointer-existence report for the chosen agent
- conversation receipt generated
- evaluator receipt generated
- `make agent-build-closeout PACKET=<path>` or the narrowest repo-approved equivalent

## Bottom Line

You are not oversimplifying by wanting one dimension, one seed, one thread. That is the correct compression.

The oversimplification would be making one giant global file or pretending one registry can replace all the organs. The right fractal shape is one canonical repo path per agent, one seed file inside that path, and a resolver that binds the seed to the existing runtime organs.

World-class dharma_swarm agents should become:

```text
repo seed
  -> identity docs
  -> runtime dock
  -> memory namespace
  -> A2A address
  -> authority policy
  -> model route
  -> durable session
  -> evaluator
  -> receipt
  -> reliability metrics
```

That is the agent spine.
