# Memory Kernel Production Bar

Status: post-merge rollout contract
Date: 2026-05-23

## Purpose

Memory Kernel is the canonical front door for agent memory. It is not a new
central database, and it is not allowed to become another competing memory
surface.

This document defines the bar for calling Memory Kernel production-integrated.
The read-only/shadow release has merged. The next rollout step is default
runtime read-path use. No agent, dashboard, PR, or audit may describe the
system as production memory unless these invariants hold.

## Production Meaning

Production-integrated means:

1. Agents ask Memory Kernel for memory context instead of manually choosing
   among MemoryLattice, MemoryPalace, Chetana, raw logs, vectors, Smriti, Codex
   memory, or conversation logs.
2. Memory Kernel returns bounded memory packs with provenance, authority,
   truth state, risk, freshness, source references, admitted atoms, omitted
   atoms, and omission reasons.
3. Memory Kernel governs the read path and the write policy. It does not own
   every storage engine.
4. KnowledgeOps and Chetana remain the canon metabolism path. Memory Kernel may
   route evidence and proposals; it must not silently promote memory to canon.

## Subordinate Engines

MemoryLattice and MemoryPalace are engines below Memory Kernel.

- MemoryLattice is a runtime/evidence/retrieval engine. Its facts remain
  observed or claimed evidence until promoted.
- MemoryPalace is a retrieval and projection engine. Its vector, LanceDB, and
  graph results are pointers or derived views, not truth.
- UnifiedIndex, VectorStore, LanceDB, GraphNexus, semantic graphs, and retrieval
  feedback are projection or evidence lanes unless a governed promotion path
  explicitly changes their status.

No subordinate engine may be treated as a competing canonical memory surface.

## External Parity Bar

The long-term target is to absorb the durable parts of the current agent-memory
field without inheriting its weak trust model:

- Anthropic-style stable agent interfaces, filesystem-backed portability,
  shared scoped stores, auditability, rollback, and redaction.
- Letta/MemGPT-style core memory, archival memory, stored messages, and
  agent-editable memory blocks.
- LangGraph-style short-term thread memory, long-term scoped memory, and
  semantic/episodic/procedural separation.
- Vector-store semantic retrieval as an index layer, never as memory authority.

Dharma's differentiator is not merely recall. The differentiator is governed
admission: the system must know what memory is allowed to become context.

## Read-Path Gate

Before Memory Kernel becomes the default context provider:

- required adapter readiness must pass;
- context parity and safety evals must report zero hard failures;
- memory packs must preserve existing agent behavior or improve it measurably;
- local paths and secret-like values must remain redacted;
- projections, high-risk atoms, rejected atoms, and superseded atoms must be
  omitted by default;
- omission reasons must be visible to the caller.

## Write-Path Gate

Before Memory Kernel becomes the default write governor:

- every memory writer must be registered or explicitly blocked;
- every accepted write must emit a receipt or use an approved writer spec;
- direct writes to unknown memory surfaces must fail governance checks;
- projection writes must remain projection writes;
- runtime facts must not become semantic canon without KnowledgeOps/Chetana
  promotion.

## Canon Gate

Canonical memory requires a governed promotion path.

- Chetana staging is backlog, not canon.
- Chetana quarantine is explicitly non-authoritative.
- Trusted wiki/KnowledgeOps artifacts are curated evidence unless a promotion
  receipt marks a stronger state.
- Vector, LanceDB, graph, retrieval feedback, routing memory, raw logs, and
  generated summaries cannot become canon by retrieval score alone.

## Runtime Default Boundary

The current Memory Kernel release is allowed to become the default context
read path when the readiness, writer sentinel, context eval, focused tests, and
operator smoke checks pass.

It must not be called full production memory until the write policy,
Lattice/Palace subordination, and promotion gates are all enforced in runtime
code.
