# 04 Memory Palace Strategy

Expert lens: memory systems architect.
Local grounding: written after reading the 33-file local evidence base in `00_local_evidence_base.md`.
External grounding: Letta, CrewAI memory, LangGraph persistence, AutoGen memory, STATE-Bench, PEPA.

## Core Claim

Memory should not be a scrapbook. It should be a governed operating layer that improves future task performance, preserves identity continuity, and can be evaluated.

The mistake to avoid is "more memory means more intelligence." Bad memory creates false confidence, stale maps, injected goals, and duplicate context. Good memory is scoped, sourced, compact, expirable, and measured.

## Memory Types Dharma Swarm Needs

Working memory:

- Current task state.
- Active assumptions.
- Context receipts.
- Open questions.
- Expires at handoff or task close.

Role memory:

- Stable patterns learned by a persistent agent.
- Subsystem ownership notes.
- Repeated failure modes.
- Preferred context tools.
- Curation required.

Project memory:

- Canonical decisions.
- ADR links.
- active track history.
- protected files.
- CI and measurement conventions.

Evidence memory:

- Source refs.
- run reports.
- test outputs.
- PR outcomes.
- external research citations.

Identity memory:

- Agent role contract.
- promotion tier.
- tool permissions.
- competence evidence.
- demotion/retirement history.

## Required Memory Discipline

Every durable memory write should have:

- Claim.
- Source path or URL.
- Timestamp.
- Scope.
- Confidence.
- Expiry or review date.
- Owner.
- Contradiction link if applicable.

Do not let agents write global memory from untrusted tool output. Tool output can propose memory; another gate should promote it.

## Recall Policy

Before acting, agents should recall:

- Their role memory.
- The active project memory for the touched subsystem.
- Recent failure memory for the same class of work.
- Protected-file rules.
- Known stale maps.

After acting, agents should write:

- What changed.
- What they learned.
- Which source was authoritative.
- What remains uncertain.
- What future agent should check first.

## Benchmark Stance

STATE-Bench is important because it asks whether memory improves production task outcomes, not whether facts can be retrieved. Dharma Swarm should use the same standard:

- Does memory reduce repeated onboarding time?
- Does it reduce broken handoffs?
- Does it improve test pass rate?
- Does it improve PR acceptance?
- Does it reduce context-tool calls without reducing correctness?
- Does it prevent repeated false L4 claims?

## PEPA Lesson

PEPA's value for Dharma Swarm is not robot personality theater. The architectural lesson is the three-layer loop: intrinsic orientation, deliberative planning, and grounded action, with episodic memory and reflection. Dharma Swarm can adapt this as:

- Sys3: role/mission/identity and strategic constraints.
- Sys2: task planning and context quorum.
- Sys1: tools, tests, file edits, command plane actions.

## Immediate Move

Do not build a grand memory graph first. Start with a per-agent filesystem plus a memory update rubric:

- `MEMORY.md` for compact curated memory.
- `DECISIONS.md` for durable decisions with source refs.
- `KNOWN_STALE.md` for maps or assumptions that failed.
- `HANDOFF.md` for current transfer.
- `receipts/` for machine-readable context manifests.
