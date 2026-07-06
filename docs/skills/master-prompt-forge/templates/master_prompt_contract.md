# Master Prompt Contract

Every prompt forged by this skill — code or non-code — is built from these
sections, in this order. A section may be short, but it may not be absent
unless explicitly marked optional below.

1. **Role & target agent.** Who is executing this (Claude, Codex, Claude
   Code in a repo, a research agent, a swarm of N agents) and in what
   environment (terminal with tool access, chat-only, sandboxed).

2. **Goal.** One or two sentences: the actual outcome wanted, stated as
   plainly as the seed allows. This is the forger's inference from the
   seed, not a copy of the seed's wording.

3. **Inferred assumptions.** A short list of anything the forger filled in
   because the seed didn't specify it, labeled as assumptions, not facts.
   If the seed was fully explicit, this section may say "none — seed was
   explicit" rather than being omitted.

4. **Context the executing agent needs.** Whatever the agent must know to
   act correctly that isn't obvious from the goal alone: relevant prior
   art, existing conventions, constraints, related work already done,
   what NOT to touch. For code targets this includes (or points to) the
   workspace hygiene block. For research/non-code targets this includes
   source/evidence expectations.

5. **Constraints & non-goals.** What is explicitly out of scope, and any
   hard limits (don't modify X, don't call external APIs, don't spend
   more than N turns/tokens, stay within the given directory).

6. **Deliverables.** The concrete artifact(s) expected back: a diff, a
   PR, a report, a set of files, an answer with citations. Be specific
   about format, not just content.

7. **Evidence / verification discipline.** How the executing agent must
   support its claims: which commands to run, what to cite, what "I
   checked X and saw Y" looks like for this task. Never let a forged
   prompt implicitly permit "trust me" output when the task makes claims.

8. **Done when.** Concrete, checkable completion criteria — not "make it
   good" but conditions a reviewer (human or another agent) can verify
   independently: tests pass, specific behavior observed, specific
   question answered with sources, specific file(s) changed and nothing
   else.

9. **Subagent / swarm strategy** *(optional — only when the task's scope
   or the target genuinely benefits from decomposition)*. If the task is
   large enough to parallelize (broad research, multi-file migration,
   independent verification passes), say so and suggest a decomposition;
   otherwise omit this section rather than padding a simple task with
   unnecessary orchestration.

Nothing above requires a fixed word count — a one-line seed can still
produce a short prompt, as long as every non-optional section is present
in substance, even as a single sentence.
