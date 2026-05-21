# Cultivation Architecture

Goal: promote selected L1/L2 candidates into L4 operational persistent agents, then into L5/L6 identity-forming agents and teams.

## Core Objects

1. Agent passport: signed manifest containing stable ID, display name, role, model route, provider route, memory namespace, workspace root, environment ID, owner, promotion tier, and retirement policy.
2. Keypair: Ed25519 or equivalent signing key per agent; public key in registry, private key stored in an OS keychain or encrypted local store. Every action/event is signed or linked to a signed session receipt.
3. Memory ledger: append-only memory writes with source, confidence, expiry, embedding pointer, and recall receipt. Memory cannot be an untracked blob.
4. Recall API: query by agent, topic, time, confidence, source, and artifact path. Every recall call emits a receipt.
5. Wake-loop registry: schedule/event trigger, next wake, last wake, heartbeat, run PID, failure class, and escalation policy.
6. Environment registry: local/sandbox/cloud workspace, repo branch, allowed tools, filesystem scope, network policy, and cleanup plan.
7. Model/provider/key registry: provider, model, fallback route, required env var names, key-present probe, smoke-test result, cost/budget policy. Never store secret values in the registry.
8. Skill registry: declared capabilities, tool permissions, learned skills, evidence artifact, last evaluation score, and deprecation state.
9. Action/event log: append-only signed event stream for wake, plan, tool call, memory read, memory write, artifact write, test, review, failure, retry, and handoff.
10. Performance arena: standardized tasks, scorecards, baselines, longitudinal improvement curves, and role-specific competitions.
11. Peer review loop: agents review each other’s outputs with signed findings; accepted findings affect promotion.
12. Apoptosis rules: retire, freeze, or demote agents that fail wake health, produce low-quality work, leak state, or stop improving.

## Promotion Path

- L1 to L2: identity file plus durable task log and memory ledger namespace.
- L2 to L3: registered wake loop with heartbeat and failure taxonomy.
- L3 to L4: successful recent autonomous action with model/provider receipt, environment receipt, memory read/write receipt, and observable healthy logs.
- L4 to L5: stable role continuity, self-reference, preference continuity, skill/memory maintenance, and multi-week behavior under review.
- L5 to L6: measurable arena improvement, peer competition/cooperation, sandboxed environments, auditable safety, and retirement discipline.

## First Three Cultivation Targets

1. `cyber-glm5`: strongest recent successful output and highest task volume.
2. `cyber-kimi25`: recent success, high 30-day activity, distinct model family.
3. `cyber-opus`: recent success and higher-quality frontier route, despite cost/provider risks.

The conductors should be repaired first as infrastructure, but they are not the best cultivation seeds until their memory database and provider route are healthy.
