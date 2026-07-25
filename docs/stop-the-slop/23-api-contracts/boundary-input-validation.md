---
id: boundary-input-validation
version: 0.0.1
theme: 23-api-contracts
status: tested
invariant: >
  All external input is hostile until validated, and validation happens ONCE at the
  trust boundary — parse into a typed, constrained value, then trust it inward. Scattered
  re-validation (or none) lets malformed/oversized/malicious input reach the core. "Parse,
  don't validate": convert untyped input into a type that makes invalid states
  unrepresentable, at the edge.
lineage:
  - "Saltzer & Schroeder — complete mediation: check every access at the boundary"
  - "Postel's law, carefully — be liberal in what you accept, but normalize it immediately"
  - "'Parse, don't validate' (Alexis King) — encode validity in the type at the edge"
ground_truth_tools: ["map trust boundaries (HTTP handlers, queue consumers, file/CLI input)", "is input parsed into a constrained type there?", "size/range/format limits"]
returns_clean: true
---

## Prompt

> Audit **input validation at boundaries**. The invariant (Saltzer–Schroeder, "parse
> don't validate"): external input is hostile until parsed into a typed, constrained
> value **at the trust boundary** — then trusted inward. For each boundary (HTTP handler,
> queue consumer, webhook, file/CLI input): is input **parsed into a validated type**
> (schema with size/range/format limits), or passed in raw / re-checked ad hoc deeper in?
> Flag: missing limits (unbounded string/list = DoS), validation done *after* use, and
> "stringly-typed" inputs that should be enums/constrained types. **Credit** boundaries
> that parse-at-the-edge. **Return clean** for a well-typed boundary.

## Why it's built this way

The bug is validation that's missing, late, or scattered; the cure is one parse at the
edge into a type that makes invalid states unrepresentable (King). Complete mediation
(Saltzer–Schroeder) is why it must be *every* boundary, once.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25.

- **Strong posture (credit):** the stack is **Pydantic 2 + FastAPI**, which *parse at
  the boundary by construction* — request bodies become validated models, and the
  truth-graph track explicitly makes **A2A ingress reject unstructured essays** in favor
  of a typed `claim/evidence/verdict/next_action` schema. That's textbook parse-don't-
  validate at the two main boundaries (HTTP + agent-to-agent). 🟢
- **The open probes:** (1) do the Pydantic models set **size/range limits** (max_length,
  ge/le) or just types? An unbounded `str`/`list` field is a DoS vector even when typed.
  (2) CLI/file/env inputs (`dgc` CLI, config loaders) — are these parsed as strictly as
  the HTTP boundary? Named as the gaps; the framework-level parsing credited.

## Changelog

- **v0.0.1** (2026-06-25) — boundary input validation (Saltzer–Schroeder/parse-don't-
  validate). Tested on `dharma_swarm`: credited Pydantic/FastAPI + typed A2A ingress
  (parse-at-edge); flagged missing size/range limits + CLI/file-input strictness as the
  probes.
