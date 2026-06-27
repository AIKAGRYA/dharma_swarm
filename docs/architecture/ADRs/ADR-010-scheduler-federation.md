# ADR-010 — Scheduler Federation: the Wake-Loop / Cron SSOT for the Holarchy

**Status:** PROPOSED (drafted 2026-06-24; awaiting operator ratification)
**Owner:** @AmitabhainArunachala (operator doctrine) · drafted by Claude Code (opus)
**Relates to:** ADR-009 (holarchy — standing wake loops are REQUIRED) · ADR-008 (naming grammar) · `agent-admission-semantic-commons-2026-06` (admission + Semantic Commons) · `cybernetics-codex-stewardship-2026-06` (loop ecology) · `runtime-truth-reconciliation-2026-06` (read-models-project-truth doctrine) · `~/.hermes/config/global_pulse_map.json` · `~/.dharma/a2a_bus/` · CLAUDE.md worktree↔track rule
**Supersedes:** the implicit "each agent mints crons wherever it lives" model, and the one-shot 2026-05-27 `_unify` import (replaced by a continuous reconciler).

## Context

ADR-009 established the holarchy: **no single orchestrator**, N standing lane-holons (`opus_composer`, `codex_composer`, `hermes-m5`, holons per durable domain), each riding shared SSOTs (A2A, Semantic Commons, spine/receipts, ACTIVE_TRACK). It named — but did not specify — a load-bearing consequence: *standing wake loops are REQUIRED, and because `claude -p`/`codex exec` cannot nest, they must be external launchd/cron.* **That unspecified "how" is now a live failure.**

Ground truth (2026-06-24 scan):
- **Three scheduler planes that disagree:** repo `cron_jobs.json` (26 jobs, many dead `~/dgc-core`/`~/agni-workspace`/`~/jagat_kalyan` paths), live `~/.dharma/cron/jobs.json` (33 jobs, ~4 enabled+fresh), Hermes `~/.hermes/cron/jobs.json` (56+ jobs, last fired ~4 days ago). Each has a **different schema** and **no shared identity field**.
- **All three planes are currently dark** — no launchd entry, no scheduler process, freshest plane last wrote 8.7h ago. Every loop receipt is stale *because nothing is firing.*
- **No reconciler exists** — nothing reads all planes and reports canonical/duplicate/orphan/dark.
- **Stale-active lie:** `~/.dharma/a2a_bus/heartbeats.json` marks agents `status:"active"` with `process_running:false`, `last_seen` 24 days old.

Forward problem (the operator's question): as the fleet expands (hermes, codex_composer, opus_composer, persistent agents, holons, Claude Code routines, codex-CLI), **N holons × M mechanisms × different file locations** turns a 3-plane split-brain into combinatorial chaos. The holarchy is missing one shared SSOT: **the scheduling / wake-loop registry.** This ADR adds it.

## Decision 1 — Federate execution; centralize visibility + identity

There is **one scheduler control plane, and it is a *registry + reconciler + cockpit view* — NOT one cron store everyone writes to, nor one daemon that runs everything.**

Forcing a single executor fails here three ways: concurrent writers corrupt a shared file; holons have genuinely different execution surfaces (Hermes runs its own Python/toolsets/keys; Claude Code routines run in Anthropic cloud on a fresh clone; VPS agents are **NAT-unreachable from the Mac**); and one daemon couples every holon's lifecycle (a dead runner takes the whole fleet down — exactly today's failure). This is the scheduling expression of ADR-009's doctrine: *read models project truth from owners; owners stay owners.*

## Decision 2 — The CronEnvelope (the shared identity contract)

Every scheduled job, in every plane, MUST carry a small identity header. This is the differentiator that makes federation legible:

```yaml
# CronEnvelope — required header on every job, every plane
owner:          hermes-m5 | codex-composer | opus-composer | dharma-daemon | claude-code | codex-cli | holon-<id>
host:           m5-mac | vps-<name> | anthropic-cloud      # WHERE it must execute
scope:          repo | local-machine | agent-private | fleet
plane:          dharma-cron | hermes-cron | launchd | claude-routine | codex-cron
canonical_name: refresh-live-ops-census                    # idempotency key — Semantic-Commons-resolved
cadence:        "every 6h" | "0 4 * * *"
target:         <script path | prompt ref>
receipt_path:   ~/.dharma/ops/live_process_census.json     # where it writes proof of firing
```

`canonical_name` is the load-bearing field: it is the **idempotency key** the reconciler uses to detect that two holons scheduled the same work. Names MUST be resolved against the Semantic Commons (`docs/ontology/semantic_objects.yaml`) — the same anti-drift machinery already used for objects/agents. Worked example:

```
job A: {owner: hermes-m5,     canonical_name: refresh-live-ops-census, host: m5-mac}
job B: {owner: dharma-daemon, canonical_name: refresh-live-ops-census, host: m5-mac}
→ reconciler verdict: DUPLICATE (same canonical_name + host, two owners) → operator picks one owner
```

Today this collision is undetectable because the three planes share no namespace. The envelope fixes that without merging the stores.

## Decision 3 — Four-layer placement rule

What belongs where is decided by **what the job needs to touch:**

| Layer | Lives in | Executes on | Belongs here | Durability |
|-------|----------|-------------|--------------|------------|
| **Intent** (declarative) | repo `cron_jobs.json` (PR-reviewed) | nothing — a *spec* | reproducible system loops every checkout should have | git |
| **Local machine** | `~/.dharma/cron/jobs.json` + launchd | the M5 hub | organism maintenance needing local fs/procs/MCP (census, PR-control, kaizenops, de_bug) | launchd (reboot-proof) |
| **Agent-private** | the holon's own store (`~/.hermes/cron`, codex, holon) | that holon's runtime | the holon's *cognitive rhythm* needing its identity/keys/memory/toolsets (NIKKI, GEPA, Darwin) | holon lifecycle |
| **Cloud / remote** | Claude Code routines; the VPS's own cron | Anthropic cloud / the VPS | fresh-clone work; VPS-resident loops | self-hosted |

**Canonical local authority = `~/.dharma/cron/jobs.json`** (the freshest, cockpit-bound plane; the proven-live `de_bug_corral_scan` already rides it). **Intent is materialized into a runner, never executed from the repo** — finishing the stalled 2026-05-27 `_unify` (repo → `.dharma/cron`) is exactly this. Hermes cron stays a **separate peer plane** (a holon's private rhythm), surfaced by the registry, not merged into the machine plane.

## Decision 4 — Remote is publish/pull, never push

The constraint *"VPSes cannot reach Mac (NAT in Bali) — Mac must be hub"* decides remote scheduling:

- The hub **cannot trigger** a remote cron. Each remote holon runs its **own local scheduler** and **publishes its CronEnvelope manifest + heartbeat** to the shared bus (`~/.dharma/a2a_bus/bridge_heartbeats/<agent>.json`, already in use by codex_composer, opus_composer, fable_composer, qwen, devin, perplexity).
- The hub reconciler **reads and displays** remote crons and flags them stale; it **never executes** them.
- **Liveness honesty (mandatory):** a cron/holon is "active" only with a **fresh heartbeat AND a recent receipt**. Stale claims are downgraded — the same rule that makes the cockpit loop cards show `needs_attention` instead of fabricated green.

## Decision 5 — Registry + reconciler shape (reuse, don't rebuild)

The two hard primitives already exist; the reconciler is the only net-new piece.

- **Registry index:** promote `~/.hermes/config/global_pulse_map.json` from a Hermes-private map to the **fleet scheduler registry**. It already carries `workspaces` (the different locations), `source_hierarchy` (authority order), `sensor_jobs` (an embryonic cron list), and `expected_organs` (declared-vs-actual). Add a `cron_planes` section pointing at each plane's job file with its `owner`/`host`.
- **Reconciler (new):** read `global_pulse_map.workspaces` → each declares its cron file → normalize every job through the CronEnvelope → emit buckets and a receipt:
  - `canonical` — one owner, envelope-complete, firing within SLA
  - `duplicate` — same `canonical_name`+`host`, ≥2 owners
  - `orphan` — owner/host dead or path missing (e.g. the `host: agni` dead-wood jobs)
  - `dark` — registered + enabled but not firing (no fresh receipt) ← the current state of *all* planes
- **Cockpit view:** generalize `_probe_operating_loops` (already shipped, read-only) → `_probe_scheduler_registry`: one screen showing every cron by owner / host / plane / last-fired / collisions / dark-planes. This is the operator's *window onto the wake-loop holarchy* (ADR-009 Decision: the dashboard is a window, not a control panel).

## Decision 6 — Cron admission (the anti-sprawl guardrail)

A cron is **real** only if it (1) carries a complete CronEnvelope, (2) is registered in the scheduler registry, and (3) writes a receipt the reconciler can read. Anything else is an orphan and is composted. **This rides the existing `AgentAdmission` path** — admitting a holon admits its crons. No envelope + no registry entry = invisible = swept. This is what prevents "each agent quietly minting crons from a different location" from ever becoming chaos: the banks are defined before the river floods.

## Consequences

- **Sequencing (load-bearing):** do NOT build the federation while the runner is dark. Order: (1) restore one runner + prove it fires (the open L0 precondition); (2) ratify this envelope + ADR; (3) build the reconciler + scheduler-registry probe; (4) onboard holons onto it. Building the control plane over a dead runner repeats the "improve the wrong body" trap.
- **New Semantic Commons objects to admit** (via the AgentAdmission path, lifecycle = `seed`; do NOT mint canon outside that path): `CronEnvelope` (`dharma.scheduler.CronEnvelope`), `SchedulerRegistry` (`dharma.scheduler.SchedulerRegistry`), `CronPlane` (`dharma.scheduler.CronPlane`), `Reconciler verdict` enum. Run `name_drift_preflight.py` on adoption.
- **No new truth store / daemon / receipt system** — registry projects from owners; reconciler writes one receipt; cockpit renders read-only. Consistent with `runtime-truth-reconciliation` non-goals.
- **Non-goals:** a single global cron executor; pushing schedules to NAT'd remotes; executing crons from the repo; counting a declared cron or a transport ACK as a firing.
- **Verification:** the reconciler receipt + a green scheduler-registry card; collisions and dark-planes visibly flagged; no "active" label without fresh heartbeat + recent receipt.
- **Track home:** this design's stewardship fits `cybernetics-codex-stewardship-2026-06` (loop ecology); implementation of the reconciler/probe is a build packet to be opened as its own track or folded into the loop-closure lane on operator instruction.

## Open questions for ratification

1. Registry home: extend `global_pulse_map.json`, or mint a dedicated `docs/ops/SCHEDULER_REGISTRY.yaml` as the canonical index?
2. Reconciler cadence + owner holon (cybernetics-codex steward is the natural seat).
3. Transport for remote manifests: a2a_bus file-bus vs NATS vs git-sync — all three exist; pick one canonical.
