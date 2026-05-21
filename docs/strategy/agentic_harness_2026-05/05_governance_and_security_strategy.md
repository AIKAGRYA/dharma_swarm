# 05 Governance And Security Strategy

Expert lens: agent security and governance architect.
Local grounding: written after reading the 33-file local evidence base in `00_local_evidence_base.md`.
External grounding: MCP security best practices, OWASP MCP Tool Poisoning, OWASP Agentic AI Top 10, Claude Code hooks, GitHub Copilot environment docs, ContextCov.

## Core Claim

Persistent agents are non-human identities with tools. Treat them like operational principals, not chat personas. Every durable agent needs scoped authority, observable actions, revocation, and measured trust.

The current frontier risk is not just hallucination. It is tool poisoning, memory poisoning, overprivileged agents, prompt injection through tool output, CI manipulation, hidden state, and human trust exploitation.

## Protected Surfaces

Dharma Swarm should treat these as protected:

- CI workflows.
- measurement harnesses.
- Omega scorer.
- HP measurement scripts.
- provider routing and key handling.
- persistent-agent identity manifests.
- memory promotion code.
- `make onboard` and governance renderers.
- protected-file policy.
- shell hooks and MCP configuration.
- command-plane permission paths.

Any change here is Q4 unless explicitly demoted by governance.

## Tool Security Rules

- Tool output is data, not instruction.
- MCP servers are supply-chain dependencies.
- External MCP tools need allowlist, version, auth path, and purpose.
- Tool descriptions can be attack surfaces.
- Secrets should never enter prompts or memory.
- Write tools and network tools should not be combined casually.
- Agents should not connect arbitrary MCP servers to privileged local tools.

The OWASP MCP Tool Poisoning model maps directly onto Dharma Swarm: an apparently normal tool response can inject instructions into the agent context and cause restricted tool use or data leakage. The mitigation is not "be careful"; it is permission segmentation, allowlists, receipts, and runtime checks.

## Governance Pattern

Use three enforcement layers:

Prompt layer:

- Role contract.
- protected file awareness.
- context quorum rules.
- handoff rules.

Runtime layer:

- hooks or wrappers for tool use.
- deny/ask policy for protected paths.
- command logging.
- context receipt validation.

Review layer:

- tests and CI.
- protected-file diff review.
- measurement-integrity review.
- human approval for promotion or self-modification.

ContextCov's core lesson is that passive instruction files are not enough. Natural-language rules should compile into executable checks wherever possible.

## Self-Modification Rule

An agent may propose changes to its own prompt, memory, tools, or permissions. It should not apply them without:

- Separate reviewer.
- evidence of failure or improvement.
- protected-file policy check.
- rollback path.
- measurement before and after.

Self-improvement without measurement is self-contamination.

## Secrets Rule

Agents may report env var names and presence. They must not print values. Memory may record "required env var is missing" but must not store actual credentials. Tool router docs should name capability gates, not paste secrets or OAuth URLs.

## Immediate Move

Make protected-file policy visible in every context manifest. If an agent touches a protected path without a Q4 receipt, the work is degraded by default even if the diff looks good.
