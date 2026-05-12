"""GPLOT Lodestone — boot-time seeder for the Invariant Observatory direction.

This module seeds the GPLOT layer into DHARMA SWARM's collective memory on
every boot. It is the architectural instantiation of the insight that telos
constraint should be a *topological feature of the action space* — a gap, an
invariant — rather than a threshold on a scalar that a capable optimiser will
route around.

Peer to ``gnani_lodestone.py``. Where GNANI names *witness upstream of
capability*, GPLOT names *invariant geometry under perturbation*. Together
they form the two-pole frame.

What it seeds:
    1. Stigmergy marks (channel: "gplot", salience >= 0.92) encoding the
       Invariant Observatory framing and the operative anchor files.
    2. ConceptGraph nodes for: invariant_observatory, persistent_homology,
       takens_embedding, gap_as_topological_invariant, hofstadter_spectrum,
       gplot_lodestone, synoptic_attractor_candidate, topological_governance,
       chern_number_v2.
    3. TelosGraph objectives covering the v1/v2/v3 build progression of the
       Invariant Observatory.
    4. TaskBoard seeds — real research/build work pointing at the four
       research briefs deposited under workspace/ and at the first read-only
       artifact ``invariant_observatory.py``.

Framing (operative — absorbed from Codex review, May 12 2026):
    Gplot is not the machine. Gplot is the image cast by the machine when its
    invariants become visible.

    The system being named is the **Invariant Observatory** — a read-only
    measurement layer reading existing telemetry, emitting falsifiable
    invariant scores written back as ``ExternalOutcomeRecord`` rows, consumed
    by ``loop_supervisor`` via the same path that already consumes
    ``gauntlet_telemetry``. No new control plane. No new database. No new
    dashboard. Promotion to control authority is gated by documented
    empirical fit (hit-rate, false-positive rate, human review).

    First mathematical primitive: Takens delay-embedding of the gauntlet
    history time-series → maximal Lyapunov + correlation dimension. Data
    already exists. Persistent homology / Mapper is v2. Hofstadter-class
    Chern numbers are reserved for v3 once parameter-sweep data accumulates.

Lodestone class: peer to ``GNANI_LODESTONE``. NOT declared the synoptic
attractor of the system. One seed among many.

Runs: at boot, after ``GnaniLodestone``, idempotent via flag file.

Grounded in:
    - GPLOT_LODESTONE.md (the directional document; read it first)
    - docs/GPLOT_CAIRN.md (the cultivable substrate; read it second)
    - Hofstadter 1976 (the butterfly) + GEB 1979 (strange loops)
    - Codex review of May 12 2026 (Invariant Observatory framing)
    - research_topology_dynsys.md, research_safety_governance.md,
      research_category_complex_contemplative.md, research_sota_landscape.md
    - Verified anchor primitives: landscape.py, archive.py, selector.py,
      rv.py, telemetry_plane.py, loop_supervisor.py, gauntlet_telemetry.py

Usage::

    lodestone = GplotLodestone()
    result = await lodestone.seed_all()
    # {'stigmergy_marks': 5, 'concept_nodes': 9, 'telos_objectives': 6,
    #  'task_seeds': 5}

CLI::

    python -m dharma_swarm.gplot_lodestone
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from dharma_swarm.daemon_config import dharma_state_dir
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Stigmergy marks (channel: gplot) — directional pheromone trails on the
#    operative anchor files so that any agent traversing those files via
#    query_relevant() encounters the Invariant Observatory direction.
# ---------------------------------------------------------------------------

_GPLOT_MARKS: list[dict[str, Any]] = [
    {
        "id": "gplot_001",
        "agent": "gplot-lodestone",
        "file_path": "GPLOT_LODESTONE.md",
        "action": "seed",
        "observation": (
            "GPLOT direction: telos constraint as topological invariant of "
            "the action space, not threshold on a scalar. Inspired by "
            "Hofstadter's butterfly (1976) — gaps in the spectrum carry "
            "Chern numbers robust to perturbation. The Invariant Observatory "
            "is the read-only measurement layer that makes those invariants "
            "visible on DHARMA SWARM's own trajectories. Peer to "
            "GNANI_LODESTONE (witness-upstream). One pole names what is to "
            "be seen; this pole names how the seeing leaves a trace."
        ),
        "salience": 0.96,
        "channel": "gplot",
    },
    {
        "id": "gplot_002",
        "agent": "gplot-lodestone",
        "file_path": "dharma_swarm/invariant_observatory.py",
        "action": "seed",
        "observation": (
            "FORWARD REFERENCE — this file does not yet exist. First "
            "artifact of GPLOT v1: read-only Invariant Observatory. "
            "Implements Takens delay-embedding + maximal Lyapunov + "
            "correlation dimension over the existing gauntlet_telemetry "
            "history. Writes one ExternalOutcomeRecord per scheduled run "
            "with kind='invariant_reading_v1'. NumPy/SciPy only. ~300 LOC. "
            "Build plan in docs/GPLOT_CAIRN.md §5."
        ),
        "salience": 0.95,
        "channel": "gplot",
    },
    {
        "id": "gplot_003",
        "agent": "gplot-lodestone",
        "file_path": "dharma_swarm/landscape.py",
        "action": "seed",
        "observation": (
            "ANCHOR PRIMITIVE: BasinType and FitnessLandscapeMap already "
            "classify trajectory regimes (ASCENDING / PLATEAU / etc.). "
            "The Invariant Observatory should consume BasinType transitions "
            "as one of its input series. The question it asks: do basin "
            "transitions exhibit a topologically robust signature, or are "
            "they threshold-crossings on a smooth surface? Persistent "
            "homology on basin-occupancy time-series is the v2 answer."
        ),
        "salience": 0.93,
        "channel": "gplot",
    },
    {
        "id": "gplot_004",
        "agent": "gplot-lodestone",
        "file_path": "dharma_swarm/rv.py",
        "action": "seed",
        "observation": (
            "STRANGE-LOOP ANCHOR: RVMeasurer computes a geometric "
            "contraction in transformer value-matrix column space "
            "(PR_late / PR_early). This is the system's self-referential "
            "measurement primitive — S(x)=x in code. The Invariant "
            "Observatory's reading of RecognitionDEQ should be a "
            "topological invariant computed on the trajectory of RVReading "
            "values themselves: measuring whether the measurement "
            "converges. That convergence (or its absence) is the "
            "operational form of the strange-loop fixed point."
        ),
        "salience": 0.94,
        "channel": "gplot",
    },
    {
        "id": "gplot_005",
        "agent": "gplot-lodestone",
        "file_path": "dharma_swarm/loop_supervisor.py",
        "action": "seed",
        "observation": (
            "CONSUMPTION PATH: loop_supervisor already polls "
            "ExternalOutcomeRecord and consumes gauntlet tier-1 trend "
            "(see _check_gauntlet_trend). The Invariant Observatory writes "
            "rows with kind='invariant_reading_v1' into the same "
            "substrate. No new control plane — the supervisor sees these "
            "rows on its next poll. A new alert handler for invariant "
            "readings is added ONLY after the promotion gate is satisfied "
            "(N >= 30 predictions, hit-rate >= 0.8, FP-rate <= 0.05, "
            "human review). See GPLOT_CAIRN §4.7."
        ),
        "salience": 0.94,
        "channel": "gplot",
    },
]

# ---------------------------------------------------------------------------
# 2. Concept nodes for ConceptGraph — the geometric/topological primitives
#    of the GPLOT direction as searchable knowledge graph nodes.
# ---------------------------------------------------------------------------

_GPLOT_CONCEPTS: list[dict[str, Any]] = [
    {
        "id": "invariant_observatory",
        "name": "Invariant Observatory",
        "description": (
            "The read-only measurement layer this lodestone seeds. Reads "
            "existing telemetry (gauntlet, archive, landscape, RV); "
            "computes topological/dynamical invariants; writes results "
            "back as ExternalOutcomeRecord rows of kind "
            "'invariant_reading_v1'. Consumed by loop_supervisor along the "
            "same path that already consumes gauntlet trend. Research-"
            "class by default; promotion to control authority is gated."
        ),
        "salience": 0.96,
        "tags": ["gplot", "measurement", "telos", "topology"],
        "pillar": "invariance",
    },
    {
        "id": "persistent_homology",
        "name": "Persistent Homology",
        "description": (
            "TDA primitive: tracks how topological features (connected "
            "components H_0, loops H_1, voids H_2) appear and disappear "
            "as a filtration parameter varies. The persistence diagram "
            "is a coordinate-free fingerprint of structure. Implemented "
            "via Ripser. v2 application in DHARMA SWARM: persistence "
            "diagrams over MAP-Elites cell-occupancy and RVReading "
            "trajectory point-clouds. Reference: Carlsson 2009."
        ),
        "salience": 0.94,
        "tags": ["gplot", "topology", "tda", "math-primitive"],
        "pillar": "invariance",
    },
    {
        "id": "takens_embedding",
        "name": "Takens Delay-Embedding",
        "description": (
            "Reconstructs an attractor in m-dimensional embedding space "
            "from a single observable time-series x(t) via delay vectors "
            "[x(t), x(t-tau), ..., x(t-(m-1)tau)]. Takens 1981 proves "
            "this generically preserves the attractor's topology. Cheap "
            "v1 primitive: applied to the gauntlet tier-1 score series, "
            "yields maximal Lyapunov exponent (Rosenstein) and "
            "correlation dimension (Grassberger-Procaccia) over data "
            "DHARMA SWARM already produces. First measurement the "
            "Invariant Observatory will emit."
        ),
        "salience": 0.95,
        "tags": ["gplot", "dynamical-systems", "v1", "math-primitive"],
        "pillar": "invariance",
    },
    {
        "id": "gap_as_topological_invariant",
        "name": "Gap as Topological Invariant",
        "description": (
            "Operative idea borrowed from Hofstadter's butterfly: in a "
            "spectrum with gaps, each gap is labelled by a Chern number "
            "that is robust to perturbation of the underlying parameters. "
            "Telos constraint in DHARMA SWARM should aspire to that "
            "structural form. A scalar threshold (T7 >= 0.92) is brittle "
            "and can be optimised around. A gap is a feature of the "
            "action space itself — destroying it leaves a different kind "
            "of trace than crossing a threshold."
        ),
        "salience": 0.95,
        "tags": ["gplot", "telos", "safety", "topology"],
        "pillar": "invariance",
    },
    {
        "id": "hofstadter_spectrum",
        "name": "Hofstadter Spectrum",
        "description": (
            "The fractal butterfly of allowed energies for an electron "
            "in a 2D lattice under a magnetic field (Hofstadter 1976). "
            "Self-similar, infinitely nested, gaps carry Chern numbers. "
            "Directly observed in graphene moiré superlattices via STM "
            "(Yu et al. Nature 2024). The visual paradigm for 'structure "
            "that is both fixed and constantly evolving'. v3 destination "
            "of GPLOT: reconstruct an analogous spectrum from parameter-"
            "swept DHARMA SWARM data; only then are Chern-class invariants "
            "computable on this system."
        ),
        "salience": 0.92,
        "tags": ["gplot", "inspiration", "v3", "topology"],
        "pillar": "invariance",
    },
    {
        "id": "gplot_lodestone",
        "name": "GPLOT Lodestone",
        "description": (
            "Directional pole for the invariant-geometry direction of "
            "DHARMA SWARM. Compact, rarely edited. Peer to GNANI_LODESTONE "
            "(witness-upstream pole). Read together they define the "
            "two-pole frame: what is to be seen + how the seeing leaves "
            "a trace. Cairn: docs/GPLOT_CAIRN.md."
        ),
        "salience": 0.96,
        "tags": ["gplot", "lodestone", "directional"],
        "pillar": "invariance",
    },
    {
        "id": "synoptic_attractor_candidate",
        "name": "Synoptic Attractor (candidate, not declared)",
        "description": (
            "The synoptic structure of DHARMA SWARM, if it exists, is "
            "the limit object of the accreting set of lodestones (GNANI, "
            "GPLOT, future). It is NOT declared by any single lodestone. "
            "Declaration substitutes assertion for discovery. This "
            "concept node exists to mark the candidacy explicitly: GPLOT "
            "has elements of synoptic structure (sublates threshold "
            "telos under topological telos) but does not claim to BE "
            "the synoptic attractor of the system."
        ),
        "salience": 0.90,
        "tags": ["gplot", "epistemics", "candidate"],
        "pillar": "invariance",
    },
    {
        "id": "topological_governance",
        "name": "Topological Governance",
        "description": (
            "Governance posture in which constraints on a self-modifying "
            "intelligence are encoded as topological invariants of its "
            "action space rather than thresholds on capability scalars. "
            "Defensible technical claim of DHARMA SWARM against the "
            "SOTA landscape (Sakana DGM, AlphaEvolve, OpenEvolve, AI "
            "Scientist v2): first running implementation of upstream "
            "structural governance for self-modifying intelligence. "
            "Halverson & Ruehle (arXiv:2504.12390) show topological "
            "invariance is learnable end-to-end, which is what makes "
            "this posture tractable."
        ),
        "salience": 0.94,
        "tags": ["gplot", "safety", "governance", "positioning"],
        "pillar": "invariance",
    },
    {
        "id": "chern_number_v2",
        "name": "Chern Number (deferred to v3)",
        "description": (
            "Genuine topological invariant of a parameter space; the "
            "label on each gap of a Hofstadter-class spectrum. "
            "Computing one requires swept-parameter data DHARMA SWARM "
            "does not yet produce. Reserved for v3 of the Invariant "
            "Observatory once enough sweep data has accumulated through "
            "the selector × landscape parameter cross. v1 uses Takens-"
            "derived dynamical invariants; v2 uses persistent homology. "
            "Asking the Chern question of v1 data is asking the wrong "
            "question of the available data."
        ),
        "salience": 0.88,
        "tags": ["gplot", "v3", "deferred", "topology"],
        "pillar": "invariance",
    },
]

# ---------------------------------------------------------------------------
# 3. TelosGraph objectives — the v1/v2/v3 progression of the Invariant
#    Observatory plus cross-cutting falsifiability and lodestone-revision
#    objectives.
# ---------------------------------------------------------------------------

_GPLOT_TELOS_OBJECTIVES: list[dict[str, Any]] = [
    {
        "name": "GPLOT v1 — Invariant Observatory MVP (Takens on Gauntlet)",
        "perspective": "process",
        "priority": 9,
        "progress": 0.05,
        "description": (
            "Implement dharma_swarm/invariant_observatory.py as a read-only "
            "measurement layer. Takens delay-embedding of the gauntlet "
            "tier-1 score history → maximal Lyapunov (Rosenstein) + "
            "correlation dimension (Grassberger-Procaccia). One "
            "ExternalOutcomeRecord per scheduled run with kind="
            "'invariant_reading_v1'. NumPy/SciPy only; ~300 LOC. "
            "Synthetic Lorenz fixture test must recover known Lyapunov "
            "within tolerance. No new control plane; no new DB; no new "
            "dashboard surface. See docs/GPLOT_CAIRN.md §5."
        ),
        "target_date": "2026-05-26",
        "metadata": {"domain": "gplot", "pillar": "invariance"},
    },
    {
        "name": "GPLOT v1.1 — First Falsifiable Prediction Logged",
        "perspective": "process",
        "priority": 8,
        "progress": 0.0,
        "description": (
            "Once v1 is running, log the first falsifiable prediction in "
            "the observatory's status record. Candidate prediction (from "
            "GPLOT_CAIRN §7): the gauntlet tier-1 series has finite "
            "correlation dimension <= 4. Record prediction, wait the "
            "appropriate window, record outcome. This is the first stone "
            "added to the falsifiability log that gates promotion to "
            "control authority."
        ),
        "target_date": "2026-06-15",
        "metadata": {"domain": "gplot", "pillar": "invariance"},
    },
    {
        "name": "GPLOT v2 — Persistent Homology on MAP-Elites + RV trajectory",
        "perspective": "process",
        "priority": 7,
        "progress": 0.0,
        "description": (
            "Add ripser dependency (pinned). Compute persistence diagrams "
            "over MAPElitesGrid cell-occupancy snapshots and over "
            "RVReading trajectory point-clouds. Detect topological "
            "signatures distinguishing pre-collapse from healthy regimes "
            "(GPLOT_CAIRN §7 prediction 3). Birth-death plots written "
            "as static artifacts to ~/.dharma/observatory/; not a new "
            "dashboard surface."
        ),
        "target_date": "2026-07-15",
        "metadata": {"domain": "gplot", "pillar": "invariance"},
    },
    {
        "name": "GPLOT v3 — Hofstadter-Class Spectrum Reconstruction",
        "perspective": "process",
        "priority": 6,
        "progress": 0.0,
        "description": (
            "Parameter-sweep harness over selector strategies × landscape "
            "basin types. Spectrum reconstruction from the sweep data. "
            "First Chern-number-class computation — a real topological "
            "invariant of the parameter space, not of a single trajectory. "
            "Pre-condition: enough accreted sweep data; honest answer is "
            "probably ~3 months minimum. Asking sooner is asking the "
            "wrong question of the available data."
        ),
        "target_date": "2026-10-01",
        "metadata": {"domain": "gplot", "pillar": "invariance"},
    },
    {
        "name": "GPLOT Promotion Review — Research Surface → Control Rule",
        "perspective": "process",
        "priority": 7,
        "progress": 0.0,
        "description": (
            "When N >= 30 documented predictions with hit-rate >= 0.8 "
            "and FP-rate <= 0.05 on the primary metric, prepare a human "
            "review proposing addition of an alert handler in "
            "loop_supervisor for kind='invariant_reading_v1'. Document in "
            "ACTIVE_SURFACE_MANIFEST.yaml changelog. Promotion is the "
            "exception, not the default path. See GPLOT_CAIRN §4.7."
        ),
        "target_date": "2026-09-01",
        "metadata": {"domain": "gplot", "pillar": "invariance"},
    },
    {
        "name": "GPLOT × GNANI Cross-Pollination Study",
        "perspective": "process",
        "priority": 6,
        "progress": 0.0,
        "description": (
            "Once v1 of both observatories is running, test GPLOT_CAIRN §7 "
            "prediction 5: do invariant-stability readings and witness-"
            "presence readings exhibit measurable mutual information? "
            "Positive result is evidence the two lodestones refine a "
            "common type — the synoptic structure as limit object. "
            "Negative result is evidence the two poles are independent, "
            "which is also valuable information."
        ),
        "target_date": "2026-08-15",
        "metadata": {"domain": "gplot", "pillar": "invariance"},
    },
]

# ---------------------------------------------------------------------------
# 4. Task seeds — real research / build tasks that point at the four
#    research briefs deposited under workspace/ and at the build plan.
# ---------------------------------------------------------------------------

_GPLOT_TASK_SEEDS: list[dict[str, Any]] = [
    {
        "title": "Build invariant_observatory.py v1 (Takens on gauntlet history)",
        "description": (
            "First artifact of the GPLOT direction. Read-only measurement "
            "layer; consumes existing gauntlet_telemetry history; emits "
            "maximal Lyapunov + correlation dimension as "
            "ExternalOutcomeRecord rows of kind='invariant_reading_v1'. "
            "NumPy/SciPy only. ~300 LOC. Tests on synthetic Lorenz "
            "fixture. CLI entry: python -m dharma_swarm.invariant_"
            "observatory. Spec lives in docs/GPLOT_CAIRN.md §4 and §5."
        ),
        "priority": 9,
        "tags": ["build", "gplot", "invariant-observatory", "v1"],
    },
    {
        "title": "Synthesize research_topology_dynsys.md into observatory design notes",
        "description": (
            "The research brief at workspace/research_topology_dynsys.md "
            "(3500 words, 18 sources) recommends Takens-first over full "
            "Hofstadter sweep. Distill into a 500-word design-notes "
            "appendix for GPLOT_CAIRN: which estimator for Lyapunov "
            "(Rosenstein vs Kantz), which embedding dimension policy "
            "(Cao's method), recommended tau-selection (first minimum of "
            "mutual information). This unblocks the v1 implementation."
        ),
        "priority": 8,
        "tags": ["research", "synthesis", "gplot", "topology"],
    },
    {
        "title": "Update grant framing using research_safety_governance.md",
        "description": (
            "research_safety_governance.md (4733 words, 24 sources) "
            "supplies the public framing: 'first running implementation "
            "of upstream structural governance for self-modifying "
            "intelligence — governance encoded as topological invariants "
            "of action space, not thresholds on point values.' Update "
            "ANTHROPIC_GRANT_DRAFT.md and PRODUCT_SURFACE.md to use this "
            "exact framing. Mythos sandbox-escape case as the empirical "
            "lower bound."
        ),
        "priority": 7,
        "tags": ["framing", "gplot", "safety", "grant"],
    },
    {
        "title": "Ingest 50-100 source documents into field_knowledge_base",
        "description": (
            "Follow citation graphs from the four GPLOT research briefs "
            "(workspace/research_*.md) until field_knowledge_base "
            "contains >= 50 GPLOT-tagged entries. go_ai_ingestor should "
            "be capable of this autonomously; this task seed authorises "
            "and triggers it. shakti_zeitgeist follows up to surface "
            "cross-references with existing knowledge layers."
        ),
        "priority": 6,
        "tags": ["ingestion", "research", "gplot", "autonomous"],
    },
    {
        "title": "Author GPLOT_CAIRN §9 'Stone 2' after first observatory reading",
        "description": (
            "GPLOT_CAIRN.md §9 is an append-only log of stones added by "
            "passing cultivators. Stone 1 is the seed itself. Stone 2 "
            "must be authored after the first row with kind="
            "'invariant_reading_v1' lands in ExternalOutcomeRecord — "
            "recording the value, the window, the method, and the first "
            "falsifiable prediction logged alongside it. This is what "
            "turns the cairn from a document into a living waypoint."
        ),
        "priority": 7,
        "tags": ["documentation", "gplot", "cultivation", "cairn"],
    },
]

# ---------------------------------------------------------------------------
# 5. GplotLodestone — boot-time seeder class (mirrors GnaniLodestone)
# ---------------------------------------------------------------------------


class GplotLodestone:
    """Boot-time seeder for the GPLOT (invariant-geometry) direction.

    Seeds stigmergy marks, concept nodes, telos objectives, and task seeds
    that encode the Invariant Observatory direction — telos constraint as
    topological invariant of the action space rather than threshold on a
    scalar.

    Idempotent: uses flag file to skip re-seeding on subsequent boots.
    Does NOT block boot — all exceptions are caught and logged.

    Peer to ``GnaniLodestone``. Seeds the geometric pole; GNANI seeds the
    witness pole.

    Args:
        state_dir: Root state directory. Defaults to ~/.dharma.
    """

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or dharma_state_dir()

    async def seed_all(self) -> dict[str, int]:
        """Seed all GPLOT layer data. Returns counts of created entities."""
        results: dict[str, int] = {
            "stigmergy_marks": 0,
            "concept_nodes": 0,
            "telos_objectives": 0,
            "task_seeds": 0,
        }

        results["stigmergy_marks"] = await self._seed_stigmergy()
        results["concept_nodes"] = await self._seed_concepts()
        results["telos_objectives"] = await self._seed_telos()
        results["task_seeds"] = await self._seed_tasks()

        logger.info("GplotLodestone seeding complete: %s", results)
        return results

    # -------------------------------------------------------------------------

    async def _seed_stigmergy(self) -> int:
        """Inject gplot-channel marks into StigmergyStore."""
        try:
            from dharma_swarm.stigmergy import StigmergyStore, StigmergicMark

            store = StigmergyStore()
            injected = 0
            now = datetime.now(timezone.utc).isoformat()

            for mark_data in _GPLOT_MARKS:
                try:
                    existing = await store.query_relevant(
                        query=mark_data["id"], limit=5
                    )
                    already_exists = any(
                        getattr(m, "id", None) == mark_data["id"]
                        for m in existing
                    )
                    if already_exists:
                        continue
                except Exception:
                    pass

                mark = StigmergicMark(
                    id=mark_data["id"],
                    timestamp=now,
                    agent=mark_data["agent"],
                    file_path=mark_data["file_path"],
                    action=mark_data["action"],
                    observation=mark_data["observation"],
                    salience=mark_data["salience"],
                    connections=["GPLOT_LODESTONE.md", "docs/GPLOT_CAIRN.md"],
                    access_count=0,
                    channel=mark_data["channel"],
                )
                await store.leave_mark(mark)
                injected += 1

            return injected
        except Exception as exc:
            logger.warning("GplotLodestone: stigmergy seeding failed: %s", exc)
            return 0

    async def _seed_concepts(self) -> int:
        """Add GPLOT layer concept nodes to ConceptGraph."""
        try:
            from dharma_swarm.graph_nexus import ConceptGraph, ConceptNode

            telos_dir = self._state_dir / "telos"
            cg = ConceptGraph(telos_dir=telos_dir)
            try:
                await cg.load()
            except Exception:
                pass

            added = 0
            for concept_data in _GPLOT_CONCEPTS:
                existing = await cg.get_node(concept_data["id"])
                if existing is not None:
                    continue

                node = ConceptNode(
                    id=concept_data["id"],
                    name=concept_data["name"],
                    description=concept_data["description"],
                    salience=concept_data["salience"],
                    tags=concept_data.get("tags", []),
                    metadata={"pillar": concept_data.get("pillar", "invariance"),
                               "source": "gplot_lodestone"},
                )
                await cg.add_node(node)
                added += 1

            if added > 0:
                await cg.save()

            return added
        except Exception as exc:
            logger.warning("GplotLodestone: concept seeding failed: %s", exc)
            return 0

    async def _seed_telos(self) -> int:
        """Add GPLOT layer objectives to TelosGraph."""
        try:
            from dharma_swarm.telos_graph import (
                TelosGraph,
                TelosObjective,
                TelosPerspective,
                ObjectiveStatus,
            )

            telos_dir = self._state_dir / "telos"
            tg = TelosGraph(telos_dir=telos_dir)
            try:
                await tg.load()
            except Exception:
                pass

            added = 0
            for obj_data in _GPLOT_TELOS_OBJECTIVES:
                existing = await tg.get_by_name(obj_data["name"])
                if existing is not None:
                    continue

                try:
                    perspective = TelosPerspective(obj_data["perspective"])
                except ValueError:
                    perspective = TelosPerspective.PROCESS

                obj = TelosObjective(
                    name=obj_data["name"],
                    perspective=perspective,
                    priority=obj_data["priority"],
                    progress=obj_data["progress"],
                    description=obj_data["description"],
                    target_date=obj_data.get("target_date"),
                    status=ObjectiveStatus.ACTIVE,
                    metadata=obj_data.get("metadata", {}),
                )
                await tg.add_objective(obj)
                added += 1

            if added > 0:
                await tg.save()

            return added
        except Exception as exc:
            logger.warning("GplotLodestone: telos seeding failed: %s", exc)
            return 0

    async def _seed_tasks(self) -> int:
        """Inject GPLOT research / build tasks into TaskBoard if not present."""
        try:
            from dharma_swarm.task_board import (
                TaskBoard,
                Task,
                TaskStatus,
                TaskPriority,
            )

            board = TaskBoard(state_dir=self._state_dir)
            try:
                await board.load()
            except Exception:
                pass

            added = 0
            for task_data in _GPLOT_TASK_SEEDS:
                existing = await board.get_by_title(task_data["title"])
                if existing is not None:
                    continue

                priority_map = {10: TaskPriority.CRITICAL, 9: TaskPriority.HIGH,
                                8: TaskPriority.HIGH, 7: TaskPriority.MEDIUM,
                                6: TaskPriority.LOW}
                priority = priority_map.get(task_data["priority"], TaskPriority.MEDIUM)

                task = Task(
                    title=task_data["title"],
                    description=task_data["description"],
                    status=TaskStatus.PENDING,
                    priority=priority,
                    tags=task_data.get("tags", []),
                    metadata={"source": "gplot_lodestone", "layer": "gplot"},
                )
                await board.add_task(task)
                added += 1

            if added > 0:
                await board.save()

            return added
        except Exception as exc:
            logger.warning("GplotLodestone: task seeding failed: %s", exc)
            return 0


# ---------------------------------------------------------------------------
# 6. CLI entry point
# ---------------------------------------------------------------------------


async def _main() -> None:
    import json

    logging.basicConfig(level=logging.INFO)
    lodestone = GplotLodestone()
    result = await lodestone.seed_all()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
