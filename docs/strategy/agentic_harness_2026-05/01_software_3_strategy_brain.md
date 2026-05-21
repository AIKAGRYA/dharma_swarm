# 01 Software 3.0 Strategy Brain

Expert lens: AI-native product strategist.
Local grounding: written after reading the 33-file local evidence base in `00_local_evidence_base.md`.
External grounding: user-supplied transcript, OpenAI Agents SDK, Cursor cloud agents, GitHub Copilot cloud agent, Anthropic multi-agent research, Codified Context.

## Core Claim

Dharma Swarm should stop judging itself as an app that happens to use agents. It should be judged as agent-first infrastructure: a repo, memory system, governance layer, and command plane designed so AI workers can discover context, act inside boundaries, produce evidence, and improve their behavior across runs.

The transcript's "menu-gen test" is the right anti-distraction filter. If a proposed feature can be replaced by one multimodal prompt plus one MCP call in the next model release, it is not a moat. The moat is the verified operating substrate: context manifests, task ownership, memory ledgers, ontology-native runtime objects, performance arenas, and operator judgment.

## What This Means For Dharma Swarm

The repo already contains a lot of high-concept architecture. The risk is not lack of ambition. The risk is that ambitious terms outrun operational proof. Software 3.0 rewards systems where the model is the computer, the prompt is code, and the context window is the immediate working memory. But durable product value lives outside a single context window: repo maps, trust rules, sandboxes, CI evidence, typed runtime state, and memory that survives session collapse.

Therefore the strategic priority is not "make a prettier frontend" or "add more agent types." The priority is making Dharma Swarm legible to agents and verifiable to humans. The winning surface is a system where a new agent can arrive, run `make onboard`, know the active track, know which files are protected, know what context tools are available, know where memory lives, and leave a handoff that another agent can trust.

## Product Wedge

The high-ROI wedge is "multi-agent engineering integrity for large messy repos." The world is producing many coding agents. Fewer systems can coordinate them without chaos. Dharma Swarm's comparative advantage should be:

- Context quorum before action.
- Evidence-backed handoffs.
- Protected-file policy.
- Runtime-spine ontology.
- Measurement gates.
- Memory curation.
- Operator cockpit.
- Agent cultivation, not anonymous task churn.

This is a Software 3.0 product because it does not merely automate a human workflow. It creates a new workflow: agents as persistent role-bearing contributors whose context, actions, memory, and quality are all observable.

## Kill Criteria

Do not build features that:

- Exist mainly as UI wrappers around a model capability.
- Duplicate an existing repo substrate.
- Add new nouns before promoting the runtime spine.
- Increase the number of places a new agent must check before working.
- Cannot produce a receipt, log, test result, or measurable change.
- Require a giant context-window provider to become useful.

## Build Criteria

Build features that:

- Shorten cold start for new agents from 30 minutes to under 5 minutes.
- Turn passive docs into executable checks or receipts.
- Preserve task ownership and trace identity across agents.
- Let the operator review agent work by evidence rather than conversation memory.
- Create a measured improvement loop around CI, Omega, HP, and task outcomes.

## Blunt Recommendation

Make Dharma Swarm the anti-sprawl agent harness. The product should be less "many agents doing things" and more "a governed organism that knows who is acting, what they checked, what changed, why it is safe, and whether it improved the system."
