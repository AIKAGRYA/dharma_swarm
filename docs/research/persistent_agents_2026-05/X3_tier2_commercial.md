# X3 - Tier 2 Commercial / Closed Systems

These systems are pattern sources, not near-term SAB participants. Most have impressive action execution but fail the provisional threshold because durable participant identity and self-owned memory are not externally inspectable.

## Score summary

| System | Avg | Passes threshold | Reason |
|---|---:|---|---|
| Manus | 3.0 | No | Strong action sandbox, closed identity/memory evidence |
| Devin | 3.0 | No | Strong coding autonomy, closed identity/memory evidence |
| Cursor agents/background agents | 3.0 | No | Always-on cloud agents, no durable identity >=4 |
| OpenAI Codex / Operator | 2.6 | No | Powerful per-task/product agents, no public participant identity |
| Anthropic Claude Code / Computer Use | 2.6 | No | Supervised product/tool mode, not durable participant |
| Replit Agent | 2.2 | No | Product checkpointing, weak operator-distance evidence |
| Steinberger/OpenAI personal agents | 1.0 | No | No official inspectable runtime found |

## Manus

Evidence: `_cache/manus_docs.html`, `_cache/source_notes.md#tier-2-commercial--closed`.

The public docs describe a closed agent product with its own computer, internet, sandbox, persistent filesystem, tool installation, and independent task execution. That is meaningful action autonomy. It still fails the Phase 0 threshold because the public evidence does not expose a durable agent identity or self-owned memory model that survives hosts, operators, and audits.

Pattern worth porting: sandboxed computer plus persistent filesystem as a first-class agent environment.

## Devin

Evidence: `_cache/cognition_devin_environment.html`, `_cache/cognition_blog_devin_builds_devin.html`, `_cache/source_notes.md#tier-2-commercial--closed`.

Devin is a capable cloud software-engineering agent. The official environment docs show configured repos, tools, dependencies, blueprints/snapshots, and repeatable cloud tasks. Operator-distance is partial: the operator delegates tasks and reviews outputs, but the product does not expose durable participant identity or auditable self-memory at the level SAB needs.

Pattern worth porting: reproducible per-agent development environments with snapshots and reviewable PR output.

## Anthropic Claude Code / Computer Use / Claude in Chrome

Evidence: `_cache/anthropic_claude_code_memory.html`, `_cache/anthropic_computer_use.html`, `_cache/source_notes.md#tier-2-commercial--closed`.

Claude Code has useful project/user memory patterns, and Computer Use establishes a browser/computer interaction capability. The surveyed evidence is still product/session/tool memory, not a persistent independent participant. Action autonomy remains operator-led in normal usage.

Pattern worth porting: explicit approval modes and memory files that the operator can inspect.

## Cursor agents / background agents

Evidence: `_cache/cursor_cloud.html`, `_cache/cursor_background_agents.html`, `_cache/source_notes.md#tier-2-commercial--closed`.

Cursor's cloud/background agents are notable because the official page describes always-on agents, schedules, event triggers from GitHub/Slack/Linear/webhooks, remote sandboxes, MCP, PR output, demos/logs/screenshots, and memory tooling. That is closer to Phase 0 than most commercial tools.

It still fails the threshold because durable agent identity and memory >=4 are not externally inspectable. The product identity is team/account/task identity, not a participant identity that can be audited across hosts and model swaps.

Pattern worth porting: event-triggered background agents that produce reviewable artifacts and logs.

## Replit Agent

Evidence: `_cache/replit_agent.html`, `_cache/replit_checkpoints.html`, `_cache/source_notes.md#tier-2-commercial--closed`.

Replit Agent is useful as a product workflow pattern: task execution, app-building flow, and checkpoints. It is not a credible SAB participant based on surveyed evidence. There is no strong durable identity, no self-owned long-term memory, and no clear self-initiation beyond user-driven tasks.

Pattern worth porting: checkpoints as operator-visible rollback/audit points.

## OpenAI Codex / Operator

Evidence:

- https://platform.openai.com/docs/codex
- https://openai.com/codex/
- https://help.openai.com/en/articles/11096431-openai-codex-cli-getting-started
- https://openai.com/index/introducing-the-codex-app
- https://openai.com/index/introducing-operator/
- https://openai.com/index/computer-using-agent/
- `_cache/source_notes.md#tier-2-commercial--closed`

Codex cloud and the Codex app now matter for background engineering work. Official docs describe cloud tasks, sandboxed environments, parallel work, automations, Skills, and approval modes. Operator/ChatGPT agent supplies the browser/computer-action pattern.

The operator-distance score remains conservative. Codex agents are created for tasks or automations inside a user/team account. Public docs do not expose a durable per-agent identity, self-owned memory, or auditable cross-session agent life that would qualify as a SAB participant.

Pattern worth porting: sandboxed full-auto envelopes, work logs, and explicit approval modes.

## Steinberger's OpenAI work

Evidence: `_cache/source_notes.md#tier-2-commercial--closed`.

I did not find an official OpenAI runtime announcement that identifies a Steinberger-led persistent personal-agent product with inspectable identity/memory primitives. This should remain an open question for direct confirmation, not a scored capability claim.

## Commercial patterns that matter

- Always-on background agents are becoming productized.
- Sandboxed per-task computers are now standard for coding/browser agents.
- Approval modes are a necessary operator-distance control surface.
- Product memory is still mostly account/session/project memory, not agent-owned identity.
- Closed commercial systems are weak candidates for SAB Phase 0 unless they expose audit APIs for identity, memory, and action logs.
