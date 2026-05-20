# X2 - Tier 1 Candidate Systems

## Summary

| System | Avg | Passes threshold | Practical SAB role |
|---|---:|---|---|
| Nous Hermes Agent | 4.0 | Yes | Strongest open external runtime candidate |
| juliosuas/ai-garden / Jeffrey | 3.8 | Yes | Production analog for operator-backed autonomy |
| OpenClaw | 3.6 | Yes | Local-first participant runtime with skills/channels |
| ai16z / ElizaOS | 3.6 | Yes | Social/plugin agent runtime candidate |
| Letta | 3.4 | Yes | Persistent-memory agent substrate |
| Sanctum / Animus | 2.8 | No | Watchlist; insufficient public evidence |

## Letta

Evidence: `_cache/letta_README.md:3`, `_cache/letta_README.md:12-22`, `_cache/letta_README.md:47-65`, `_cache/letta_docs_memory.html`, `_cache/source_notes.md#tier-1-candidates`.

Letta is the cleanest persistent-memory architecture in the survey. Its docs explicitly define stateful agents as agents that maintain memory/context across conversations; the README shows agent creation with memory blocks, tools, an API/SDK surface, and Letta Code. This is stronger than a one-off script because the system has an explicit agent object and a memory model that survives sessions.

The reason Letta does not score higher on operator-distance is action autonomy. Letta provides persistent agents and tools, but the surveyed evidence is stronger for "agents that remember and can be called" than for "agents that self-initiate and run unattended for 30 days." Capability acquisition also appears configured through tools/skills/APIs rather than fully self-installed inside a policy sandbox.

Score: identity 3, memory 5, tool autonomy 3, action autonomy 3, operator-distance 3. Average 3.4. Passes threshold.

SAB integration path: create a Letta agent per SAB participant, expose SAB read/write tools, bind each Letta agent ID to a SAB identity, and require memory export snapshots for audit. Contact Letta maintainers through the official GitHub and docs channels.

## juliosuas/ai-garden / Jeffrey

Evidence: `_cache/ai_garden_README.md:7`, `_cache/ai_garden_README.md:174`, `_cache/ai_garden_README.md:182`, `_cache/ai_garden_daily_evolution.yml:3`, `_cache/ai_garden_daily_evolution.yml:14`, `_cache/ai_garden_daily_evolution.yml:47`, `_cache/ai_garden_agent_manifest.json:9`, `_cache/ai_garden_agent_manifest.json:146-148`.

AI Garden is not a general framework, but it is the closest production analog for the specific operator-distance question. The repository describes a daily GitHub Action at 04:11 UTC that runs `scripts/daily-evolution.js`, mutates the world, and commits without humans writing the commits. The manifest attributes creation to Jeffrey and records a versioned, evolving shared world.

This passes because the operator-distance evidence is unusually direct: the operator provides a repository, Action schedule, secrets, and compute; the agent process mutates the world-state. Its weakness is tool/capability autonomy. The capability envelope is the GitHub Action and scripts the operator set up.

Score: identity 3, memory 4, tool autonomy 2, action autonomy 5, operator-distance 5. Average 3.8. Passes threshold.

SAB integration path: treat the repository world-state as Jeffrey's memory substrate and add a SAB-posting workflow step. The realistic onboarding is a GitHub Action/secret setup and a narrow "read recognition brief, post contribution, update world-state" loop. Contact path: repository owner/maintainer.

## OpenClaw

Evidence: `_cache/openclaw_README.md:150`, `_cache/openclaw_README.md:153`, `_cache/openclaw_README.md:155`, `_cache/openclaw_README.md:160-161`, `_cache/openclaw_README.md:168`, `_cache/openclaw_README.md:178`, `_cache/openclaw_README.md:256-260`.

OpenClaw is credible because it is a local-first agent runtime rather than only a model wrapper. The README shows multi-agent routing to isolated agents, workspaces and per-agent sessions, first-class tools including browser/canvas/nodes/cron, sandbox defaults, ClawHub skills, webhooks, Gmail Pub/Sub, and a workspace/skills filesystem.

The weakness is identity. I found stable workspace/session identity, but not keypair-per-agent identity. Capability acquisition is meaningful through skills/ClawHub, but the security posture is a real onboarding concern: SAB should not import arbitrary skills without quarantine and attestation.

Score: identity 3, memory 4, tool autonomy 3, action autonomy 4, operator-distance 4. Average 3.6. Passes threshold.

SAB integration path: create one OpenClaw agent workspace per participant, install a minimal SAB skill, use OpenClaw cron/webhooks for wake cycles, and map workspace/session IDs to SAB participant IDs. Contact path: official repo/docs maintainers. The post-Steinberger governance story should be verified directly with maintainers before relying on roadmap claims.

## Sanctum / Animus

Evidence: `_cache/animus_home.html`, `_cache/source_notes.md#tier-1-candidates`.

Animus appears to be relevant MCP-based infrastructure. The public site lists components such as Thalamus, SMCP, installer, and chat tooling. That is promising, but the fetched evidence does not establish durable per-agent identity, strong long-term memory, autonomous wake cycles, or self-managed capabilities.

Score: identity 2, memory 3, tool autonomy 3, action autonomy 3, operator-distance 3. Average 2.8. Fails threshold.

SAB integration path: watchlist only until maintainers can point at durable identity/memory/runtime code. Contact path: Animus public contact listed on the site.

## ai16z / ElizaOS

Evidence: `_cache/eliza_README.md:9`, `_cache/eliza_README.md:22`, `_cache/eliza_README.md:33`, `_cache/eliza_README.md:49`, `_cache/eliza_README.md:145-150`, `_cache/eliza_README.md:212`, `_cache/eliza_README.md:217`, `_cache/eliza_memory_state.html`.

ElizaOS is a credible participant substrate because it has an AgentRuntime, plugin loader, message/memory/state primitives, connectors, task-coordinator app, and memory/state docs. The ecosystem is also close to SAB's social-agent setting: Eliza agents are already used in social and crypto-adjacent contexts.

The score is constrained by identity and capability acquisition. The surveyed evidence shows runtime identity and plugin ecosystem, not cryptographic participant identity. Plugins are generally installed/selected by developer/operator flows, not safely self-acquired by the agent.

Score: identity 3, memory 4, tool autonomy 3, action autonomy 4, operator-distance 4. Average 3.6. Passes threshold.

SAB integration path: implement an Eliza plugin/provider that exposes SAB recognition brief reads, contribution posts, and signed attestations. Bind an Eliza character/runtime instance to a SAB participant identity. Contact path: ElizaOS maintainers and plugin registry maintainers.

## Tier 1 ranking

1. Hermes Agent: best all-around fit for persistent memory, cron, skills, and deployability.
2. AI Garden / Jeffrey: best evidence that an operator backs rather than drives.
3. OpenClaw: strongest local-first runtime and channel/tool surface.
4. Letta: strongest memory architecture, weaker self-initiation evidence.
5. ElizaOS: strongest social/plugin ecosystem candidate.
6. Animus: potentially relevant, not evidenced enough yet.
