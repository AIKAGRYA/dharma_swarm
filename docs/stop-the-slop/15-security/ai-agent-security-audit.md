---
id: ai-agent-security-audit
version: 0.0.1
theme: 15-security
status: tested
invariant: >
  An AI agent's attack surface is its INPUTS and its TOOLS. Untrusted text (user
  messages, fetched web content, agent-to-agent messages, tool outputs) can carry
  instructions — prompt injection — and the only real defense is least-privilege on
  tools plus treating all model-adjacent text as untrusted data, never as commands.
  "The model will know better" is not a control. The blast radius of a confused
  agent is whatever its tools can do.
lineage:
  - "Saltzer & Schroeder 1975 — least privilege; complete mediation"
  - "OWASP LLM Top 10 — LLM01 prompt injection, LLM06 excessive agency, LLM08 tool misuse"
  - "the confused-deputy problem (Hardy 1988) — the agent acts with authority it shouldn't lend"
ground_truth_tools: ["map the agent's input sources & tool permissions", "trace untrusted text → tool-call path", "the repo's own gates/guardrails"]
returns_clean: true
---

## Prompt

> Audit an **AI agent system** for injection & excessive-agency risk. The invariant
> (Saltzer–Schroeder, OWASP LLM Top 10): the attack surface is **inputs × tools**.
> Any untrusted text reaching the model (user input, fetched pages, agent-to-agent
> messages, tool results) can carry instructions; the controls are **least-privilege
> tools** + **treat model-adjacent text as data, never commands** + **complete
> mediation** (every tool call gated).
>
> **Map and assess:**
> 1. **Input sources** — where does untrusted text enter the prompt? (user, web,
>    A2A, tool output, retrieved docs). Each is an injection vector.
> 2. **Tool surface** — what can the agent *do*? Rank tools by blast radius (shell,
>    file-write, network, payments). Is each least-privilege and gated?
> 3. **Injection path** — trace untrusted-input → tool-call. Can a crafted message
>    make the agent take a privileged action? (the confused-deputy test).
> 4. **Existing controls** — gates, allow-lists, human-in-the-loop, sandboxing.
>    Credit them; find the gaps.
>
> Output: vector → tool → blast radius → control present? → gap. **Return clean** on
> controls that are real; flag missing mediation as the priority. This is code/arch
> audit, not legal advice.

## Why it's built this way

Agent security is a 2026 frontier the generic kits miss entirely. It's old
principles applied to a new surface: least privilege (don't give the agent tools it
doesn't need), complete mediation (gate every tool call), confused-deputy (the agent
must not lend its authority to injected instructions). The discipline is mapping the
real input×tool matrix, not reciting "sanitize inputs."

## Demonstration run

**Target:** `dharma_swarm/` — itself an agent swarm — 2026-06-25.

- **Input vectors (untrusted text → model):** A2A agent-to-agent messages
  (`dharma_swarm/a2a/**`), web fetch/search (`web_search.py`), user/operator
  commands. Each is an injection surface; A2A is notable — *another agent's* output is
  not trusted input.
- **Tool surface / blast radius:** the swarm can dispatch providers, run tools, write
  memory, and (gated) modify itself. High-blast tools exist.
- **Existing controls (credit where due):** `TelosGatekeeper` (**11 safety gates**
  incl. CONSENT, REVERSIBILITY, WITNESS), the spine's `EvidenceReceipt` mediation,
  and (from the truth-graph track) **A2A ingress rejecting unstructured essays** in
  favor of a typed `claim/evidence/verdict/next_action` schema — which is *exactly*
  the "treat A2A text as structured data, not commands" defense. Strong posture.
- **Gaps to probe (honest):** does *every* high-blast tool call pass a gate (complete
  mediation), or are there bypass paths (cf. the spine-bypass allowlist)? Is fetched
  **web content** (`web_search`) ever concatenated into a prompt that can then call a
  tool — the classic injection→action path? Recommend tracing one untrusted-web →
  tool-call path end to end.

**Verdict:** unusually strong existing controls (telos gates + typed A2A ingress);
the open item is proving **complete mediation** on the high-blast tools and the
web-content→tool path. Named honestly, not asserted clean.

## Changelog

- **v0.0.1** (2026-06-25) — AI-agent security audit (Saltzer–Schroeder / OWASP LLM
  Top 10 / confused-deputy): map inputs × tools, trace injection→action, credit
  controls. Tested on `dharma_swarm`'s own agent layer: credited the 11 telos gates +
  typed A2A ingress; flagged complete-mediation + web→tool path as the open items.
