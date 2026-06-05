# PR: Layer 2 Vocabulary Census — Proposed Vocabulary

**Branch:** `perplexity-grounding/vocabulary-census`  
**Entry point:** [`PROPOSED_VOCABULARY.md`](./PROPOSED_VOCABULARY.md)  
**Status:** Stage-1, evidence-only. Awaits John's voice.

---

## The Journey

This PR is the output of a four-pass inhabitation swarm. Four agents worked in parallel before a single name was proposed. Pass 1a read 33 vision and doctrine documents and built a concept map of what this system claims to be. Pass 1b walked 85 Python files, catalogued 300+ class definitions, and documented what the system actually implements. Pass 1c read 90 days of git log, PRs, operational logs, and NATS bus traffic to establish what is alive versus dormant. Pass 1d adversarially critiqued Devin's 21 types, finding 13 load-bearing, 5 aspirational-but-grounded, and 3 cargo-cult. Pass 2 ran the four maps against each other in a written debate — eight tensions, each argued from both sides, each resolved to a position. Pass 3 produced the narrative vocabulary you are reading now.

The hardest disagreement in the swarm was the NATS contradiction: Pass 1b found no NATS client in the Python codebase; Pass 1c found NATS live in operational logs from the May 31 surge. Both were correct. They were looking at two different buses — the in-process `SignalBus` and the inter-process NATS fleet fabric — and the resolution informed the whole naming posture: vocabulary-layer types for the typed A2A coordination layer, substrate for the internal heartbeat.

## What Changed from Devin's 21

**Removed (3):** `Paper` (no producer, semantically polluted by paper trading), `RevenueOffer` (orphan type, name mismatch with native `Offer` class), `Experiment` (three parallel definitions, no adapter — returns as `EXPERIMENTAL` when one is declared canonical).

**Renamed (key):** `ActionProposal → proposal`, `GateDecisionRecord → gateDecision`, `EvolutionEntry → evolutionProposal`, `StigmergicMark → stigmergyMark`.

**Added (7):** `stigmergyMark` (the most glaring omission — 8 core modules, API router, adapter already in `ontology_adapters.py`), `agentCard`, `agentSkill` (A2A 1.0 spec live), `routingDecision` (spine track canonical type), `opportunityCandidate` (ShaktiExecutive output), `identitySnapshot`, `zeitgeistSignal`, `corpusClaim` (the last three as EXPERIMENTAL with explicit wiring paths).

## Total: 22 types proposed (18 active, 4 experimental)

Read [`PROPOSED_VOCABULARY.md`](./PROPOSED_VOCABULARY.md) — specifically the Letter to John (Section 1) — before reviewing the individual type entries. The letter tells the story of what the swarm found, what surprised us, and what we argued about. The vocabulary makes sense inside that frame.
