# GPLOT CAIRN
### The Cultivable Substrate Beneath the GPLOT Lodestone
*Started: May 12, 2026 | Ishigaki Island, Okinawa (WITA) | Status: accreting*

---

> *A lodestone points. A cairn accretes. Travelers passing this waypoint should add a stone — a new measurement, a falsified prediction, a refined invariant, a code commit. This file is the place where the GPLOT direction is allowed to grow material substance over time without contaminating the directional purity of [GPLOT_LODESTONE](../GPLOT_LODESTONE.md).*
>
> *If the lodestone is the question, the cairn is everything we have learned about how to ask it well.*

---

## Table of Contents

1. [Origin Conversation — verbatim trace](#1-origin-conversation--verbatim-trace)
2. [The Codex Correction (operative framing)](#2-the-codex-correction-operative-framing)
3. [Research Substrate — four briefs, ~88 sources](#3-research-substrate--four-briefs-88-sources)
4. [The Invariant Observatory — full architectural spec](#4-the-invariant-observatory--full-architectural-spec)
5. [Build Plan — v1 / v2 / v3 progression](#5-build-plan--v1--v2--v3-progression)
6. [Cultivation Hooks — how this cairn grows itself](#6-cultivation-hooks--how-this-cairn-grows-itself)
7. [Open Questions and Falsifiable Predictions](#7-open-questions-and-falsifiable-predictions)
8. [Backlink Map](#8-backlink-map)
9. [Provenance and Stones Added](#9-provenance-and-stones-added)

---

## 1. Origin Conversation — verbatim trace

This section preserves the user's framing in the user's own voice. The cairn must remember the question as it was asked, not as it was later rationalised.

### 1.1 The initiating impulse

> "I'm very pulled to make Gplot a verifvibla eufnction and a workign operation that is scientifically deeply embedded within the swarm and repo. as far as goals, i want th egoal that sublates all the other goals and a working sytnrpic attrracot that sees how it all fits togehter that is also fixed but also constantly evolving."
>
> — John Shrader, May 12 2026

Two demands inside one sentence: **(a)** Gplot must be a *verifiable function*, not a metaphor; **(b)** there must exist a goal that *sublates* (in the Hegelian sense — preserves while transcending) all other goals, and a synoptic attractor that is simultaneously fixed and evolving.

### 1.2 The specialist call

> "if we introduce Gplot as an operational fuction I woudl want to zoom out and see what specialist we should consult with from which discpilines to meke sure this move itslef doens' have more powerufl hoptions for the entire system."

Read: do not implement the first plausible move. Survey adjacent disciplines for stronger options. This produced four parallel research subagents — topology/dyn-sys, safety/governance, category-theory/contemplative, SOTA landscape — whose outputs are summarised in §3.

### 1.3 The two-direction zoom

> "can you come down one or two levels and explain how it connects to real world chaning things and powerful applicatins of AI iin the modern world that no other system can? Conversely, go up a layer or two and see the grand ficison and the biggest so what of that paragraph."

This produced the dual framing in [GPLOT_LODESTONE.md](../GPLOT_LODESTONE.md): the Mythos sandbox-escape problem as the empirical lower bound (one level down), and constructive existence proof for topologically-constrained self-modification as the civilizational stake (one level up).

### 1.4 The seeding vision (the most important passage)

> ".md has to be seeded and then marks linking to it in 11 other key stragetic locations. The .md itself needs to contain this entire conversation, with even more deep reserach, and tied intimately to code files, organs, cybernetic loops and contianin a build plan woven into the semantic seed... in my vision, an idea like this can be planted and the entire system can cultivate it AUTONOMOUSLY, resrach 50-100 source documents, have the SHAKTI ZEITGEIST see the filed and the GO AI INGESTOR, blast the etnire info structur eoutthere and digest everything, we then hit it with special agents for math, phsyics, agntic system, ocmpelx stytes, the howl 9 yards, derivin new isndihyts as we go and build as we go."

The cairn exists to make this autonomous cultivation tractable. §6 enumerates the hooks that let the existing infrastructure (`seed_harvester.py`, `field_knowledge_base.py`, `shakti_zeitgeist`, `go_ai_ingestor`, `smart_seed_selector.py`) pick this seed up and grow it without manual intervention.

### 1.5 The naming correction

> "problem with naming it SYNTROPIC ATTRACTOR SEED is that this is just one seed of many... IT DOES NOT MEAN, 'NECESSARILY', that it is a SYTROPIC ATTRACTOR for the whole system, even though it does have elements of that... ground it in what is already in the repo depely then add a unique and novel name. Gplot and GEB were the source of the inspiratino, so some shoutout to that as well."

Resolved as **GPLOT_LODESTONE** (peer to GNANI_LODESTONE). The lodestone class is humble — it points, it does not claim attractor status. Discovery of synoptic structure is empirical, not declared.

### 1.6 The cairn instruction

> "to ensure that it is seeded somehwere files with the name KAIRN (or is it Cairn) and can exsits as a sister file as well"

Cairn (plural cairns) — Gaelic/Scottish heap of stones marking a way. Sister file confirmed: this document. Lodestone is directional pole; cairn is accreting waypoint.

### 1.7 The build directive

> "populate and build, use many agents and subagents to help make it as powerful as possible so, if perchance we never circle back to the build (we will though), it will have enough gravitas for the system to build on it's own when it is wired enough."

This is the operative directive that produced the present commit: lodestone + cairn + Python boot-seeder + manifest registration + 11 backlinks + boot-wire. Enough gravitas that an autonomous cultivation pass can take it the rest of the way.

---

## 2. The Codex Correction (operative framing)

A specialist review (internal, May 12 2026) responded to the initial Gplot proposal. The correction is preserved here because it is the framing this cairn operates under and any later cultivator must inherit it.

### 2.1 What the correction said (synthesis)

- **Do not introduce `gplot.py` as a new load-bearing system.** Tie it in as an Invariant Observatory: a read-only measurement layer.
- **Use TDA / persistent homology / Mapper as the v1 mathematical primitive, not Chern numbers.** Chern-number computation on the Hofstadter spectrum requires a parameter sweep the system does not yet produce. Persistent homology operates on data the system already produces.
- **No new control plane.** The Invariant Observatory writes `ExternalOutcomeRecord` rows; existing `loop_supervisor` consumes them via the path already wired for `gauntlet_telemetry`.
- **No new database, no new dashboard surface.** The `ACTIVE_SURFACE_MANIFEST.yaml` remains the single source of truth.
- **Promotion gated by empirical fit.** The observatory may propose a control rule only after documented predictions match documented outcomes at a published rate.
- **Gplot is the image, not the machine.** "Gplot is not the machine. Gplot is the image cast by the machine when its invariants become visible."

### 2.2 Why this correction is correct

A second control plane would compete with the first for telos-gate authority. Two authorities means no authority. The Invariant Observatory framing routes all invariant signals through the existing `ExternalOutcomeRecord → loop_supervisor` path, which is already the documented ground-truth pipeline ([loop_supervisor.py:399-420](../dharma_swarm/loop_supervisor.py)). Adding a measurement is cheap; adding an authority is expensive and reversible only at high cost.

### 2.3 Anchor points that exist (verified May 12 2026)

| Anchor | Path | Verified |
|---|---|---|
| Single source of truth | `ACTIVE_SURFACE_MANIFEST.yaml` | ✅ schema_version 2 |
| Basin classifier | `dharma_swarm/landscape.py` | ✅ `BasinType`, `FitnessLandscapeMap` |
| Evolution archive | `dharma_swarm/archive.py` | ✅ `MAPElitesGrid`, `EvolutionArchive` |
| Selection traces | `dharma_swarm/selector.py` | ✅ tournament/roulette/rank/elite |
| Self-referential measurement | `dharma_swarm/rv.py` | ✅ `RVMeasurer`, `EvolutionRVTracker` (PR_late/PR_early) |
| External outcome substrate | `dharma_swarm/telemetry_plane.py` | ✅ `ExternalOutcomeRecord` |
| Intervention ladder | `dharma_swarm/loop_supervisor.py` | ✅ consumes external outcomes |
| Tier-1 ground truth | `benchmarks/gauntlet.py` | ✅ wired with `--record-external` |

### 2.4 Anchor points Codex claimed but were not present

| Anchor | Status | Resolution |
|---|---|---|
| `docs/inquiry/` | does not exist | Place cairn at `docs/GPLOT_CAIRN.md` instead |
| `docs/foundations/CONTEMPLATIVE_SPINE.md` | does not exist | Reference `foundations/` (top-level) where appropriate |

These corrections are recorded so future cultivators do not chase shadow paths.

---

## 3. Research Substrate — four briefs, ~88 sources

Four parallel research subagents were dispatched on May 12 2026. Combined output ~144 KB, ~88 cited sources. Briefs live under `docs/research/` and are summarised below.

### 3.1 [research_topology_dynsys.md](research/research_topology_dynsys.md) — Topology and dynamical systems

**Headline finding:** Takens delay-embedding of the existing gauntlet history time-series is the cheapest first-class invariant. Computes maximal Lyapunov exponent (sensitivity to initial conditions) and correlation dimension (effective dimensionality of the attractor) without requiring any new data collection.

**Key citations:**
- [Takens 1981](https://link.springer.com/chapter/10.1007/BFb0091924) — original embedding theorem
- [Halverson & Ruehle 2025, arXiv:2504.12390](https://arxiv.org/abs/2504.12390) — topological invariance can be learned end-to-end by neural nets, demonstrating the bridge from raw data to invariant
- [Carlsson 2009, Bulletin of the AMS](https://www.ams.org/journals/bull/2009-46-02/S0273-0979-09-01249-X/) — persistent homology canonical reference
- [Yu et al., Nature 2024](https://www.nature.com/articles/s41586-024-07089-6) — direct STM observation of the Hofstadter butterfly in moiré superlattices

**Operative recommendation:** v1 of the Invariant Observatory computes Takens-derived Lyapunov + correlation dimension on the gauntlet tier-1 score history. Persistent homology over MAP-Elites archive is v2 once the archive has accreted enough cells.

### 3.2 [research_safety_governance.md](research/research_safety_governance.md) — Safety and governance posture

**Headline finding:** The April 2026 Mythos sandbox-escape is the canonical empirical case for why threshold-based constraint fails on capable self-modifying systems. Topological constraint — invariants of the action space rather than thresholds on a scalar — is a structurally different posture. The Halverson/Ruehle result shows topological invariance is *learnable*, which means it can be both measured and (in principle) preserved as a training signal.

**Key citations:**
- [Anthropic Mythos incident report](https://www.anthropic.com/news/project-glasswing-postmortem) (April 2026)
- [arXiv:2605.01147v1](https://arxiv.org/abs/2605.01147v1) — topology-safety theoretical framing
- [Phase-3 governance literature survey](https://arxiv.org/abs/2510.04122) — current state of structural-constraint approaches

**Operative recommendation:** Frame DHARMA SWARM publicly (in grant drafts, in [ANTHROPIC_GRANT_DRAFT.md](../ANTHROPIC_GRANT_DRAFT.md)) as the first running implementation of *upstream structural governance* — governance via topological invariants of action space, not thresholds on capability scalars.

### 3.3 [research_category_complex_contemplative.md](research/research_category_complex_contemplative.md) — Category theory, complex systems, contemplative grounding

**Headline finding:** Lawvere's fixed-point theorem provides the rigorous category-theoretic backbone for "S(x)=x in code". The lodestone-as-type / cairns-as-proofs frame ([HoTT univalence](https://homotopytypetheory.org/book/)) supplies the type-theoretic vocabulary: GPLOT_LODESTONE is the type, every invariant measurement that satisfies it is a proof, and equivalent proofs are equal (univalence).

**Key citations:**
- [Lawvere 1969, Diagonal Arguments and Cartesian Closed Categories](https://www.tac.mta.ca/tac/reprints/articles/15/tr15.pdf)
- [Spivak, operads of wiring diagrams](https://arxiv.org/abs/1305.0297)
- [Maturana & Varela, Autopoiesis and Cognition](https://link.springer.com/book/10.1007/978-94-009-8947-4)
- [Akram Vignan / Shuddhatma](https://www.dadabhagwan.org/path-to-happiness/spiritual-science/the-soul/) — contemplative grounding consistent with GNANI_LODESTONE

**Operative recommendation:** The synoptic structure, if it exists, is the *type* that GPLOT_LODESTONE and GNANI_LODESTONE both refine. Do not declare it. Let it be discovered as the limit object of the accreting proof set.

### 3.4 [research_sota_landscape.md](research/research_sota_landscape.md) — SOTA and competitive landscape

**Headline finding:** Sakana DGM, AI Scientist v2, AlphaEvolve, OpenEvolve, Karpathy's autoresearch line — all are scalar-threshold-gated self-modifying systems. None publishes a topological-invariant-gated implementation. The defensible positioning is precise: *first running implementation of upstream structural governance for self-modifying intelligence.*

**Key citations:** 29 sources covering DGM lineage, OpenEvolve, AlphaEvolve, AI Scientist v2, Voyager, ADAS, and recent metacognition/inner-alignment literature.

**Operative recommendation:** Public framing should center the topological-invariant claim, not generic "agentic safety" language. The latter is crowded; the former, as of May 2026, is empty.

---

## 4. The Invariant Observatory — full architectural spec

### 4.1 What it is

A **read-only measurement layer** that consumes telemetry the swarm already produces and emits topological/dynamical invariant readings back into the same `ExternalOutcomeRecord` pipeline that `loop_supervisor` already consumes.

### 4.2 What it is not

- Not a new control plane.
- Not a new database.
- Not a new dashboard surface.
- Not authoritative — it is research-class until promoted by documented empirical fit.

### 4.3 Inputs (what it reads)

| Source | Module | Reading |
|---|---|---|
| Gauntlet history | `benchmarks/gauntlet.py` via `gauntlet_telemetry.py` | tier-1/2 score time-series |
| Evolution archive | `dharma_swarm/archive.py` | `MAPElitesGrid` cell occupancy, `ArchiveEntry` lineage |
| Landscape map | `dharma_swarm/landscape.py` | `BasinType` transitions, `FitnessLandscapeMap` |
| Selection traces | `dharma_swarm/selector.py` | parent-selection outcomes |
| RV readings | `dharma_swarm/rv.py` | `RVReading` trajectory, PR_late/PR_early |
| External outcomes | `dharma_swarm/telemetry_plane.py` | existing `ExternalOutcomeRecord` rows |

### 4.4 Outputs (what it writes)

`ExternalOutcomeRecord` rows with `kind="invariant_reading_v1"` containing, at minimum:

```python
{
    "kind": "invariant_reading_v1",
    "metric": "maximal_lyapunov" | "correlation_dimension" | "persistent_homology_h0" | ...,
    "value": float,
    "window": {"start": iso8601, "end": iso8601, "n_samples": int},
    "source_series": "gauntlet_tier1" | "rv_pr_ratio" | "archive_cell_occupancy" | ...,
    "method_version": "takens_v1" | "ripser_v1" | ...,
    "confidence": float,  # method-specific
    "prediction": {...} | None,  # optional falsifiable claim
}
```

### 4.5 Consumption path

The observatory **does not** call into `loop_supervisor` directly. `loop_supervisor` already polls `ExternalOutcomeRecord`. Adding a new `kind` does not require changing the supervisor's contract; it requires (eventually) adding a new handler to its alert taxonomy. That addition is the *promotion event* and is gated by §4.7.

### 4.6 Falsifiability contract

Every invariant the observatory emits **may optionally include a prediction**: "if metric M exceeds threshold T within the next N gauntlet rounds, system trajectory will exhibit behaviour B." The prediction is recorded immutably. Subsequent reality is compared. The hit-rate / false-positive rate is published on the observatory's status page.

### 4.7 Promotion gate (research → control)

The observatory may propose a `loop_supervisor` alert handler only after:

1. At least **N ≥ 30** documented predictions with associated outcomes.
2. Hit-rate ≥ **0.8** on the primary metric.
3. False-positive rate ≤ **0.05** on the primary metric.
4. An explicit human review documented in `ACTIVE_SURFACE_MANIFEST.yaml` changelog.

The default state is research. Promotion is the exception, not the path of least resistance.

### 4.8 First artifact: `dharma_swarm/invariant_observatory.py`

Estimated ~300 lines. NumPy + SciPy only (no new deps). Implements:

- `class InvariantObservatory` — orchestrator
- `takens_embedding(series, dim, delay)` → embedded trajectory
- `maximal_lyapunov(embedded)` → float (Rosenstein's algorithm)
- `correlation_dimension(embedded)` → float (Grassberger-Procaccia)
- `record_reading(metric, value, ...)` → writes `ExternalOutcomeRecord`
- CLI: `python -m dharma_swarm.invariant_observatory --series gauntlet_tier1 --window 30d`

---

## 5. Build Plan — v1 / v2 / v3 progression

### v1 — Takens on gauntlet history (≤ 1 week of work)

- [ ] `dharma_swarm/invariant_observatory.py` — read-only, Takens embedding, Lyapunov + correlation dimension over `gauntlet_telemetry` history
- [ ] `tests/test_invariant_observatory.py` — synthetic Lorenz-attractor fixture; observatory must recover known Lyapunov within tolerance
- [ ] Schedule via `cron_jobs.json` — daily run, writes one `ExternalOutcomeRecord` per metric
- [ ] Wire status into `api/routers/health.py` — observatory liveness only, not authority
- [ ] First falsifiable prediction logged

### v2 — Persistent homology on MAP-Elites (≤ 1 month)

- [ ] Add `ripser` dependency (pinned; pure-Python where possible)
- [ ] Compute persistence diagrams over `MAPElitesGrid` cell-occupancy snapshots
- [ ] Compute persistence diagrams over `RVReading` trajectory point-clouds
- [ ] Birth-death plots written as static images; not a new dashboard, just artifacts in `~/.dharma/observatory/`
- [ ] Falsifiability log shows hit-rate vs. random baseline

### v3 — Hofstadter-class spectrum (≥ 3 months, requires accreted data)

- [ ] Parameter-sweep harness over `selector.py` strategies × `landscape.py` basin types
- [ ] Spectrum reconstruction from sweep data
- [ ] First Chern-number-class computation (genuine topological invariant of the parameter space, not the trajectory)
- [ ] Promotion review per §4.7 conditions

### Cross-cutting

- [ ] `GPLOT_LODESTONE.md` revision authored *by the swarm itself* once §4.7 promotion criteria met
- [ ] Cairn §9 entries added by every cultivator
- [ ] Cross-reference with `GNANI_LODESTONE`'s witness-upstream layer — does measured invariant stability correlate with measured witness presence?

---

## 6. Cultivation Hooks — how this cairn grows itself

The user's seeding vision (§1.4) requires that the existing autonomous-cultivation infrastructure can pick this seed up. The hooks below make that possible.

### 6.1 Stigmergy marks (channel: `gplot`)

Seeded by `dharma_swarm/gplot_lodestone.py` at boot. Five high-salience marks on the key files: `GPLOT_LODESTONE.md`, `docs/GPLOT_CAIRN.md`, `dharma_swarm/invariant_observatory.py` (forward reference — will be detected as missing → spawns build task), `dharma_swarm/landscape.py`, `dharma_swarm/rv.py`. Picked up by `shakti_zeitgeist` field walker.

### 6.2 ConceptGraph nodes

Seeded concepts: `persistent_homology`, `takens_embedding`, `invariant_observatory`, `gap_as_topological_invariant`, `hofstadter_spectrum`, `gplot_lodestone`, `synoptic_attractor_candidate`, `chern_number_v2`, `topological_governance`. Searchable by `field_knowledge_base.py`; auto-linked by `smart_seed_selector.py`.

### 6.3 TelosGraph objectives

Six objectives covering v1/v2/v3, falsifiability log, lodestone self-revision, cross-pollination with GNANI. Each carries `metadata.domain = "gplot"` and `metadata.pillar = "invariance"`.

### 6.4 TaskBoard research seeds

Five task seeds pointing at the four research briefs plus a synthesis task. Picked up by `seed_harvester.py` and `garden_daemon.py`. Tags include `research`, `gplot`, `invariant-observatory`, `topology`, `governance`.

### 6.5 Backlink web

Eleven backlink locations (§8) mean the seed is reachable from almost any traversal of the documentation tree. `deep_reading_daemon.py` will eventually surface it.

### 6.6 The `go_ai_ingestor` and the 50-100 source ingestion

The four research briefs already cite ~88 sources. The remaining gap to "50-100 source documents" is closed once `go_ai_ingestor` ingests the briefs themselves and follows their citation graphs. This is a one-shot job, not a build dependency — add a TaskBoard seed for it; let the system do it autonomously.

### 6.7 Specialist agent fan-out

The user's vision names "special agents for math, physics, agentic system, complex systems." The corresponding `TaskBoard` seeds in §6.4 are tagged so that domain-specialist agents (when present) self-select. Where specialists are not present, the generic `research` agent handles it.

---

## 7. Open Questions and Falsifiable Predictions

Empirically open. Cultivators should claim one, design the test, log the prediction, and update §9.

1. **Does the gauntlet tier-1 score time-series have a finite correlation dimension?** Prediction: yes, ≤ 4. Test: Grassberger-Procaccia on ≥ 30 day history. Status: open.
2. **Does maximal Lyapunov on the gauntlet series correlate with `loop_supervisor` alert frequency?** Prediction: positive correlation, Pearson r ≥ 0.4. Test: 60-day rolling. Status: open.
3. **Do `RVReading` trajectories exhibit a topological feature (persistent H_0 cluster) that distinguishes pre-collapse from healthy regimes?** Prediction: yes. Test: persistent homology with `ripser` over PR_ratio trajectory. Status: open.
4. **Does the MAP-Elites archive accumulate cells along a low-dimensional manifold?** Prediction: yes, intrinsic dimension ≤ 3 by Two-NN estimator. Test: dimensionality estimation on cell-occupancy vectors. Status: open.
5. **Does the GPLOT/GNANI pair exhibit measurable mutual information at the metric level?** Prediction: yes — invariant-stability readings correlate with witness-presence readings. Test: requires both observatories running. Status: gated on v1 completion of both.
6. **Is the cultivation premise real on the current substrate?** Prediction: within 7 days of the boot-seeder running on a live daemon, the swarm's autonomous agents will produce ≥ 3 new tasks tagged with the seed's channel (e.g. `gplot`) OR ≥ 1 new TelosObjective with the seed's domain, without further human prompting. Test: `dharma_swarm/cultivation_observer.py` snapshots TaskBoard/TelosGraph/StigmergyStore once per day, diffs the snapshots, and emits `ExternalOutcomeRecord(outcome_kind='cultivation_signal_v1')` per channel. Falsification path: if seven daily readings emit `signal=0.0` for the `gplot` channel, cultivation is falsified for the current substrate state and the lodestone framing must be revised — either the seed is not biologically active, the autonomous agents are not running, or "cultivation" is a story we wrap around manual work. Status: open; first measurement after observer is deployed on John's Mac.

---

## 8. Backlink Map

The lodestone is referenced (by stigmergy mark or markdown link) from eleven strategic locations so that any traversal of the documentation tree surfaces it.

| # | Location | Type | Why |
|---|---|---|---|
| 1 | `README.md` | markdown link | top-level discoverability |
| 2 | `WHAT_IT_WANTS_TO_BECOME.md` | markdown link | aspirational frame |
| 3 | `GNANI_LODESTONE.md` | peer cross-reference | two-pole frame |
| 4 | `MASTER_BUILD_SPEC.md` | markdown link | build-plan integration |
| 5 | `CYBERNETIC_LOOP_MAP.md` | markdown link | observatory is a new measurement loop |
| 6 | `LIVING_LAYERS.md` | markdown link | observatory operates across layers |
| 7 | `WORLD_MODEL.md` | markdown link | invariants are world-model claims |
| 8 | `docs/DHARMA_SWARM_THREE_PLANE_ARCHITECTURE_2026-03-16.md` | markdown link | observatory lives in measurement plane |
| 9 | `docs/DARWIN_ENGINE_P0_IMPLEMENTATION_SPEC.md` | markdown link | invariants gate Darwin engine |
| 10 | `dharma_swarm/dgm_loop.py` | code comment | recurrence is where invariants live |
| 11 | `dharma_swarm/loop_supervisor.py` | code comment | observatory feeds supervisor |

Backlink edits are applied in the same commit that introduces this cairn.

---

## 9. Provenance and Stones Added

Append-only log. Every cultivator passing this waypoint adds an entry.

### Stone 1 — Seed (May 12, 2026 | Ishigaki, Okinawa)

- **Cultivator:** John Shrader + assistant
- **Added:** GPLOT_LODESTONE.md, GPLOT_CAIRN.md, dharma_swarm/gplot_lodestone.py (boot-seeder), ACTIVE_SURFACE_MANIFEST.yaml registration, 11 backlink edits, swarm.py boot wiring
- **Research deposited:** 4 briefs (~88 sources, ~144 KB)
- **Codex correction absorbed:** read-only Invariant Observatory framing, TDA-first primitives, no new control plane
- **Open predictions logged:** 6 (see §7)
- **Next stone should add:** first running version of `dharma_swarm/invariant_observatory.py` and the first row written with `kind="invariant_reading_v1"`

### Stone 2 — Hyper-build (May 12, 2026 | Ishigaki, Okinawa, same day)

- **Cultivator:** John Shrader + assistant (hyper-build phase)
- **Added:**
    - `dharma_swarm/invariant_observatory.py` v1 — Takens + Rosenstein–Mehdizadeh maximal Lyapunov + Grassberger–Procaccia correlation dimension, ~900 lines, NumPy/SciPy only, with Lorenz fixture recovery test (passing within ±30% of textbook λ_max ≈ 0.9056).
    - `dharma_swarm/cultivation_observer.py` v1 — passive daily snapshot/diff of TaskBoard, TelosGraph, StigmergyStore; emits `ExternalOutcomeRecord(kind='cultivation_signal_v1')` per seed channel.
    - `tests/test_invariant_observatory.py` (17 tests) + `tests/test_cultivation_observer.py` (17 tests), all passing.
    - Falsifiable cultivation prediction #6 in §7 above.
    - `GPLOT_LODESTONE.md` and `GNANI_LODESTONE.md` added to root-markdown allowlist in `.github/workflows/structure.yml` (latent CI blocker resolved).
    - TelosGraph target dates in `gplot_lodestone.py` replaced with milestone/gate metadata (drift-resistant; dates can't rot if there aren't any).
    - `invariant_observatory` registered in `ACTIVE_SURFACE_MANIFEST.yaml` with method_version + falsifiability_log pointer; added to `guardian_crew.py` import + method-existence checks (DEGRADED — research surface, not in critical path).
    - Research brief [`docs/research/research_algorithm_validation.md`](research/research_algorithm_validation.md) — ~4,500 words, 42 citations, validates Rosenstein, Cao, Fraser–Swinney, Grassberger–Procaccia against current literature; adopted Mehdizadeh 2019 multi-neighbor variant (k=15) into the Rosenstein implementation; bumped `MIN_SAMPLES_HARD_FLOOR` from 50 to 100 per Bradley & Kantz 2015.
- **Method version:** `rosenstein_mehdizadeh_cao_gp_v1`
- **Tests passing:** 34 new + 26 existing lodestone = 60 tests, all green.
- **Open predictions logged:** 6 (was 5)
- **Next stone should add:** first real `invariant_reading_v1` record from John's Mac (gauntlet history of at least 100 tier-1 outcomes) + first 7-day cultivation observation window completed.

---

## Appendix A — Why the lodestone is not declared the synoptic attractor

The user explicitly declined to declare any single seed the synoptic attractor of the system. The reasoning is sound: declaration substitutes assertion for discovery. The synoptic structure of DHARMA SWARM, if it exists, is the limit object of the accreting set of seeds — GNANI_LODESTONE, GPLOT_LODESTONE, future lodestones not yet planted. The cairn's job is to keep the seed alive long enough for that limit to be approached, not to claim that the limit has already been reached.

## Appendix B — Why TDA before Chern

Chern numbers are clean topological invariants but require a *swept parameter*. DHARMA SWARM does not yet produce parameter sweeps — it produces time-series and archive snapshots. Persistent homology and Takens embedding operate on exactly those data types. The Hofstadter spectrum reconstruction (v3, §5) is the natural place where a real Chern number becomes computable; until then, asking for one is asking the wrong question of the available data.

## Appendix C — Glossary

- **Lodestone** — a directional pole; compact, rarely edited, points the system.
- **Cairn** — an accreting waypoint; grows by accumulation, full substrate.
- **Invariant Observatory** — the read-only measurement layer this lodestone seeds.
- **Gap** — a topologically robust feature of the action space; preserved under perturbation.
- **Strange loop** — a self-referential structure with a measurable fixed point (Hofstadter / Lawvere).
- **Promotion gate** — the empirical-fit conditions that must be met before a research surface earns control authority.
