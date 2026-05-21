# 02 Context Quorum Harness Strategy

Expert lens: agentic harness architect.
Local grounding: written after reading the 33-file local evidence base in `00_local_evidence_base.md`.
External grounding: Anthropic multi-agent research, OpenAI Agents SDK, Claude Code hooks/subagents, GitHub Copilot cloud agent, Augment, Qodo, Sourcegraph, Greptile.

## Core Claim

The next Dharma Swarm harness should make context gathering a protocol, not a personality trait. Agents should not be trusted because they sound confident. They should be trusted when they can show a context receipt from independent sources.

Context quorum means: before acting, an agent must gather enough independent evidence for the risk level of the task, record what was checked, state what disagreed, and attach artifacts that another agent can inspect.

## Quorum Levels

Q0: trivial text or formatting work.

- One local file read is enough.
- No code symbols, protected paths, or live state.

Q1: narrow docs or local code read.

- `make onboard` plus exact file reads.
- `rg` or Context+ when locating evidence.
- Handoff summary if another agent will continue.

Q2: normal code or architecture work.

- `make onboard`.
- One structural source: GitNexus, Context+, or repo map.
- One exact source: `rg`, file read, or test.
- One governance source: active track, broken register, protected policy, or relevant plan.
- Context manifest required.

Q3: protected or shared runtime work.

- All Q2 sources.
- Impact/blast-radius check.
- Tests or CI evidence.
- Protected-file policy check.
- Handoff with risk log and rollback path.

Q4: self-modification, measurement, CI, secrets, provider routing, or agent promotion.

- All Q3 sources.
- Human approval or explicit governance rule.
- Two independent context tools if available.
- CI/measurement evidence beats agent judgment.
- Memory update must cite source refs and expiry.

## Tool Disagreement Protocol

When tools disagree, do not average their answers. Classify the disagreement:

- Staleness: indexed tool conflicts with live file read. Live file wins, index gets marked stale.
- Scope: semantic tool found related concepts, exact search found the active implementation. Exact implementation wins for edits; semantic tool remains useful for blast radius.
- Authority: docs conflict with code. For current behavior, code and tests win; for intended governance, active track and canonical docs win.
- Measurement: agent reasoning conflicts with CI, tests, or scorer. Measurement wins unless the measurement harness is itself in scope and protected review is approved.

## Harness Shape

Use a small manifest object rather than a platform:

```json
{
  "risk": "Q2",
  "question": "what is being changed?",
  "sources_checked": [
    {"tool": "make_onboard", "artifact": "stdout", "status": "checked"},
    {"tool": "contextplus", "artifact": "tree", "status": "checked"},
    {"tool": "rg", "artifact": "exact_hits", "status": "checked"}
  ],
  "disagreements": [],
  "decision": "safe_to_edit_docs_only",
  "handoff_path": "~/.dharma/agents/<agent>/handoff/HANDOFF.md"
}
```

The manifest should live with the agent or run, not as root clutter. The repo should keep policy and schema; state roots should keep run receipts.

## What To Automate

Automate the checks that agents forget:

- Was `make onboard` run?
- Were protected files touched?
- Did the agent cite context tools it did not actually call?
- Did a Q2+ task produce a manifest?
- Did tests or CI run when code changed?
- Did the handoff contain absolute evidence paths?

## What Not To Automate Yet

Do not build a giant tool router dashboard before the protocol is used in real sessions. First make the receipt small, boring, and hard to fake. The harness should be easier than writing a persuasive apology after breaking the repo.
