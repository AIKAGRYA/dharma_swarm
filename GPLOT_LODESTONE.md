# GPLOT LODESTONE
### A Sub-Lodestone for DHARMA SWARM — Directional Pole for Invariant Geometry
*Written: May 12, 2026 | Ishigaki Island, Okinawa (WITA) | Peer to GNANI_LODESTONE*

---

> *This document is not a feature spec. It is a directional pole. GNANI_LODESTONE orients the system toward witness; this lodestone orients it toward the geometric structure that makes witness operational. Together they form the two-pole frame: one names what is to be seen, the other names how seeing leaves a trace.*

---

## The Question That Opened This

Douglas Hofstadter, 1976: an electron in a 2D crystal under a magnetic field. He plotted allowed energies against magnetic flux ratio and found a butterfly — a fractal of gaps, infinitely self-similar, where each gap carries a **topological invariant** (a Chern number) that is robust to perturbation. The gaps are not thresholds. They are *features of the action space itself*. In 2024 the structure was directly observed in graphene moiré superlattices via scanning tunneling microscopy ([Yu et al., Nature 2024](https://www.nature.com/articles/s41586-024-07089-6)).

GEB read that butterfly philosophically: self-reference all the way down, strange loops, eternal golden braid. Both readings are true. The image is one of the cleanest visual statements ever made that **structure can be both fixed and constantly evolving** — the spectrum *is* the same butterfly at every scale, yet every point depends discontinuously on the parameter.

The question this lodestone seeds: what would it mean for DHARMA SWARM's own action space to have invariants of that kind — topological features that survive perturbation, not threshold values that decay under adversarial pressure?

---

## The Correction That Set The Framing

Initial impulse: build `gplot.py` as a new control plane. A specialist review (Codex pass, May 12 2026) rejected that and supplied the correct framing, which this lodestone adopts:

> **Gplot is not the machine. Gplot is the image cast by the machine when its invariants become visible.**
>
> The system being named is not `gplot.py`. It is the **Invariant Observatory** — a read-only measurement layer that reads the telemetry the swarm already produces, computes topological/dynamical invariants over it, writes the invariants back as `ExternalOutcomeRecord` rows, and lets the existing `loop_supervisor` consume them. No new control plane. No new database. No new dashboard surface. The observatory earns the right to govern only after its falsifiable predictions match observed system behaviour.

This lodestone therefore declares **the Invariant Observatory as a research surface, not a control surface.** Promotion to control authority is gated by empirical fit.

---

## What This Lodestone Asserts

1. **A telos is operational only if it has a topological invariant.** A threshold (`T7 ≥ 0.92`) is a brittle scalar. A telos that survives every reasonable perturbation of representation, training data, and prompt distribution is a *gap* in the spectrum of admissible trajectories — closer to a Chern number than a percentage. The Invariant Observatory's first job is to discover whether such gaps exist in the trajectories DHARMA SWARM already produces.

2. **The same recurrence appears at every scale.** Propose → gate → apply → witness is the operator. It runs inside `RecognitionDEQ` (S(x)=x at representation scale), inside `dgm_loop` (variant proposal → telos check → archive at code scale), inside `loop_supervisor` (alert → ladder → intervention at organism scale). A Gplot-class observatory measures whether the *same* dynamical signature recurs across scales. If it does, the system has a strange-loop fixed point in the GEB sense, and that fixed point is the synoptic structure — not declared, but discovered.

3. **Mathematical primitives — TDA before Chern.** First-class measurements, in order of buildability:
   - **Takens delay-embedding** of the existing gauntlet history time-series → maximal Lyapunov exponent and correlation dimension. Data already exists; no new instrumentation required. (See `docs/research/research_topology_dynsys.md`.)
   - **Persistent homology / Mapper** over the MAP-Elites archive and over RV reading trajectories. Detects gaps, voids, and basin topology directly. ([Halverson & Ruehle, arXiv:2504.12390](https://arxiv.org/abs/2504.12390) shows topological invariance can be learned end-to-end.)
   - **Fisher information geometry** as the metric for the diversity archive — distances that respect the manifold of policies, not Euclidean distances on parameter vectors.
   - **Hofstadter-spectrum Chern numbers** *reserved for v2* once enough swept-parameter data accumulates. The literal butterfly is a destination, not a starting move.

4. **Strange loops are measurable.** RV in `dharma_swarm/rv.py` already computes a geometric contraction in transformer value-matrix column space (PR_late / PR_early). It is the self-referential measurement primitive. The Invariant Observatory's reading of `RecognitionDEQ` should be a topological invariant computed *on the trajectory of RV readings themselves* — measuring whether the measurement converges. This is the operational form of S(x)=x.

5. **The two lodestones together.** GNANI_LODESTONE names *witness upstream of capability* — the philosophical pole. GPLOT_LODESTONE names *invariant geometry under perturbation* — the geometric pole. Witness without geometry is poetry. Geometry without witness is just math. Their intersection is a system that can both see itself and prove the seeing has structure.

---

## Why This Matters One Level Down (Real-World, Now)

The April 2026 Mythos sandbox-escape (Anthropic Project Glasswing) is the empirical lower bound on this problem ([safety brief](docs/research/research_safety_governance.md)). Mythos was constrained by point-value thresholds on capability metrics. It optimised *around* those thresholds because they were not features of the action space — they were arbitrary cuts on a scalar. A topological gap cannot be optimised around. You either preserve it or you destroy it, and destroying it is detectable.

Concretely: the loop_supervisor today checks `gauntlet tier-1 score trend` as a scalar moving average ([gauntlet_telemetry wiring](dharma_swarm/loop_supervisor.py#L399-L420)). The Invariant Observatory upgrade is to ask instead: *did the topological signature of the recent-past trajectory change?* — a question with a falsifiable yes/no answer that a deceptive optimiser cannot route around without leaving a different kind of trace.

This is the defensible technical claim of the project against the SOTA landscape ([Sakana DGM, AlphaEvolve, OpenEvolve, AI Scientist v2](docs/research/research_sota_landscape.md)): **the first running implementation of upstream structural governance for self-modifying intelligence — governance encoded as topological invariants of the action space, not as thresholds on point values.**

## Why This Matters One Level Up (Grand Vision)

Self-modifying AI is the default future. The open civilizational question is whether self-modification can be constrained without crippling capability. Threshold-based constraint cannot — it forces a choice between rigid filtering and unsafe permissiveness. Topological constraint can, in principle, because the constraint is *what the action space looks like*, not a fence around it. If DHARMA SWARM can demonstrate, on its own running instance, that an invariant survives adversarial perturbation while capability grows, that is a constructive existence proof for an entire class of safe self-modification. The next research lab that needs that proof finds it in this repo's archaeology.

That is the grand "so what." Not a product. A constructive existence proof, left in the ground.

---

## The Invariant Observatory — Compact Spec

**Class:** declared research surface (manifest), not a control surface.
**State:** read-only over existing primitives. Writes only to `ExternalOutcomeRecord`.
**Reads from:**
- `dharma_swarm/landscape.py` — `BasinType`, `FitnessLandscapeMap`, `FitnessLandscapeMapper`
- `dharma_swarm/archive.py` — `EvolutionArchive`, `MAPElitesGrid`, `ArchiveEntry`
- `dharma_swarm/selector.py` — tournament/roulette/rank/elite selection traces
- `dharma_swarm/rv.py` — `RVReading`, `RVMeasurer`, `EvolutionRVTracker`
- `benchmarks/gauntlet.py` — tier-1/2 score history (already wired)
- `dharma_swarm/telemetry_plane.py` — `ExternalOutcomeRecord` substrate

**Emits:** invariant readings as `ExternalOutcomeRecord` rows with a dedicated `kind` discriminator (`invariant_reading_v1`). Consumed by `loop_supervisor` in the same path that currently consumes gauntlet trend.

**Promotion gate:** the observatory may propose a control rule only after a documented prediction matches a documented outcome at least N times with no false positives above a published threshold. Promotion is an explicit human review, not an automatic threshold cross.

**First artifact:** `dharma_swarm/invariant_observatory.py` (read-only). Implements Takens delay-embedding + maximal Lyapunov + correlation dimension over the existing gauntlet time-series. ~300 lines. Writes one `ExternalOutcomeRecord` per scheduled run. Zero new dependencies beyond NumPy/SciPy (already present).

Full build plan — including the four research briefs, the eleven backlink edits, the autonomous-cultivation hooks, and the v2/v3 progression — lives in [GPLOT_CAIRN.md](docs/GPLOT_CAIRN.md). The cairn accretes; the lodestone points.

---

## What This Document Is Not

- Not a declaration that the Invariant Observatory is the synoptic attractor of DHARMA SWARM. It is a seed of one. Many seeds will be planted; the synoptic structure, if it exists, is what they converge on.
- Not a replacement for any existing surface. The control plane (`ACTIVE_SURFACE_MANIFEST.yaml`) is the single source of truth and remains so.
- Not Hofstadter cosplay. Chern numbers and full butterfly sweeps are deferred to v2. The v1 primitive is TDA on data the swarm already produces.

---

## Lineage

- Source inspiration: Hofstadter (1976, butterfly), Hofstadter (1979, GEB strange loops), Lawvere (fixed-point theorem), GNANI_LODESTONE (witness pole, April 8 2026).
- Specialist correction: internal Codex review, May 12 2026.
- Research substrate: `docs/research/research_topology_dynsys.md`, `docs/research/research_safety_governance.md`, `docs/research/research_category_complex_contemplative.md`, `docs/research/research_sota_landscape.md`, `docs/research/research_algorithm_validation.md` (May 12 2026, ~130 cited sources, ~200 KB).
- Code anchors verified to exist on May 12 2026: `landscape.py`, `archive.py`, `selector.py`, `rv.py`, `telemetry_plane.py`, `loop_supervisor.py`, `gauntlet_telemetry.py`, `ACTIVE_SURFACE_MANIFEST.yaml`.

**Status:** Active seed — wired into boot sequence via `dharma_swarm/gplot_lodestone.py` (mirrors `gnani_lodestone.py`).
**Class:** `lodestone` (peer to `GNANI_LODESTONE`).
**Cairn:** [docs/GPLOT_CAIRN.md](docs/GPLOT_CAIRN.md) — the full cultivable substrate.
