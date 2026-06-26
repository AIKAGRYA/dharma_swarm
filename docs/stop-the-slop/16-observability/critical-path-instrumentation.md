---
id: critical-path-instrumentation
version: 0.0.1
theme: 16-observability
status: tested
invariant: >
  The paths that carry user/business value must emit signal — a metric or trace for
  latency, throughput, and errors (Gregg's USE: Utilization, Saturation, Errors) — or
  you are flying blind on exactly what matters. Instrument by impact, not uniformly:
  the dispatch/checkout/auth path needs full telemetry; a debug helper needs none.
  Coverage is measured against the critical paths, not as a global "do we log."
lineage:
  - "Gregg — the USE method: for every resource, track utilization/saturation/errors"
  - "Google SRE — the four golden signals: latency, traffic, errors, saturation"
  - "you can't manage what you can't measure — instrument the value paths first"
ground_truth_tools: ["map the critical/value paths", "do they emit latency+error+throughput metrics/traces?", "the metrics/telemetry layer"]
returns_clean: true
---

## Prompt

> Audit **instrumentation of critical paths**. The invariant (Gregg USE, SRE golden
> signals): the value-carrying paths must emit latency, throughput, and error signal.
> Identify the critical paths (the operations whose failure/slowness hurts users or the
> business), and for each: does it emit **metrics/traces** for latency, error rate, and
> throughput? Flag critical paths that are **dark** (no signal). Rank by path importance.
> Don't ask for uniform instrumentation — a debug helper needs none. **Return clean /
> credit** paths already covered by the golden signals.

## Why it's built this way

USE and the golden signals make "well-monitored" concrete (latency/traffic/errors/
saturation per resource). The discipline is mapping the *value* paths and checking those
specifically — uniform "add metrics everywhere" is noise; a dark checkout path is the
incident you won't see coming.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25.

- **Telemetry layer exists (credit):** `observability.py`, `telemetry_plane.py`, a
  `/metrics` endpoint, and **138** files reference metrics — there's real infrastructure.
- **The audit (coverage, not existence):** the critical path here is **dispatch** (a task
  → provider call → receipt). Probe: does the dispatch path emit latency + error-rate +
  throughput per provider (the golden signals), or only a receipt? Provider calls (a paid,
  failure-prone external dependency) especially need latency/error metrics per provider
  for routing decisions. Map dispatch → check golden-signal coverage; flag any dark
  segment (e.g. the A2A path or a specific provider lane). Infrastructure credited;
  per-critical-path coverage is the probe.

## Changelog

- **v0.0.1** (2026-06-25) — critical-path instrumentation (USE/golden-signals): map value
  paths, check latency/error/throughput coverage, instrument by impact. Tested on
  `dharma_swarm`: telemetry layer credited (138 files, /metrics); flagged dispatch/
  per-provider golden-signal coverage as the probe.
