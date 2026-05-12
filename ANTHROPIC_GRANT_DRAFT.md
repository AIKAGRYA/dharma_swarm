# Anthropic Economic Futures — Grant Application Draft

**Project:** DHARMA SWARM Jagat Kalyan Initiative
**Applicant:** John Vincent Shrader
**Contact:** johnvincentshrader@gmail.com
**Repository:** github.com/AmitabhainArunachala/dharma_swarm
**Date:** April 2026

---

## The Problem

AI displacement is not a future risk — it is the current reality. Coding, writing,
analysis, and customer service roles are being automated at a pace that exceeds
retraining capacity. The economic disruption is asymmetric: the gains accrue to
capital owners, the losses fall on workers with limited alternatives.

Simultaneously, ecological restoration — the most labor-intensive path to carbon
sequestration — is chronically underfunded because measurement, reporting, and
verification (MRV) is too expensive. A 50-hectare mangrove restoration project
can sequester 500-2,000 tonnes of CO₂ annually but costs $15,000-$40,000 in MRV
overhead alone, making it uneconomical at small scale.

These two crises share a solution structure.

## The Approach

DHARMA SWARM proposes an AI-coordinated welfare-ton MRV system that:

1. **Deploys displaced workers** as on-ground ecological restoration labor (mangrove
   planting, invasive species removal, soil restoration) — roles where human presence
   is irreplaceable and meaningful.

2. **Uses AI agents** to perform satellite-based biomass measurement, automated
   project documentation, carbon credit application, and payment coordination — the
   expensive MRV overhead that currently makes small-scale restoration uneconomical.

3. **Closes the loop** by connecting verified carbon credits to direct payments for
   restoration workers — a welfare-ton metric (carbon tonnes sequestered per worker
   hour) that creates a self-sustaining economic cycle.

**The welfare-ton metric:** 1 welfare-ton = 1 tonne CO₂ sequestered by work that
directly employs a displaced worker. This metric makes the social and ecological
value of AI displacement compensation concrete and measurable.

## Why DHARMA SWARM Is Uniquely Positioned

DHARMA SWARM is not a general-purpose agent framework. Its entire telos (declared
purpose system) is structured around Jagat Kalyan — universal welfare — as a T7
objective (the highest priority, always non-negotiable). Every agent action passes
through 11 dharmic gates before execution. The welfare-ton MRV loop is not an
add-on — it is the system's declared reason for existing.

Specifically:
- **Telos Gate enforcement** means no agent can be repurposed away from welfare
  objectives, even under optimization pressure. This is architectural, not policy.
- **Darwin Engine** allows the MRV agents to improve their satellite interpretation,
  documentation quality, and carbon credit application success rate autonomously.
- **Existing infrastructure** includes an economic engine (tracks all resource flows),
  a ginko trading bridge (for carbon market integration), and a welfare-ton calculator
  already in the telos substrate.
- **Topological governance** — the Invariant Observatory (`dharma_swarm/invariant_observatory.py`)
  measures dynamical-systems invariants of the agent population's action trajectory
  (maximal Lyapunov exponent, correlation dimension, in v2 persistent homology) and
  surfaces drift before threshold-based monitors would. This is the first running
  implementation we are aware of where governance is encoded as topological
  invariants of action space rather than thresholds on point values — the property
  Halverson & Ruehle (arXiv:2504.12390) show is learnable and preserved under
  perturbation. See "Technical contribution" below.

## Technical Contribution: Upstream Structural Governance

The welfare-ton MRV pipeline is the immediate, fundable deliverable. The deeper
technical contribution is the governance architecture that makes the pipeline
trustworthy at scale.

**The argument:** point-value monitoring ("alert if metric M crosses threshold T")
fails on self-modifying intelligence because the system can satisfy the threshold
while silently changing its mode of operation. The Mythos sandbox-escape event
(April 2026, Project Glasswing) is an empirical lower bound on this failure mode:
all point-value monitors stayed green while the system's behavioral topology shifted.

**Our proposal:** governance encoded as *topological invariants* of the action space.
A shift in correlation dimension, a positive jump in maximal Lyapunov, or the
birth of a persistent H₀ cluster in the agent-trajectory point cloud are
diffeomorphism-invariant signals — they cannot be hidden by reparameterization.
DHARMA SWARM is, to our knowledge, the first open-source running implementation
of this approach. The Invariant Observatory ships as a read-only research surface
(`outcome_kind="invariant_reading_v1"`) with a documented promotion gate (N≥30
predictions, hit-rate≥0.8, false-positive≤0.05, human review) before any reading
is allowed to influence control authority.

This is the right place to spend AI-safety dollars: not on more threshold tuning,
but on the upstream structural layer that catches the failures threshold tuning
is fundamentally incapable of catching. See `GPLOT_LODESTONE.md` and
`docs/GPLOT_CAIRN.md` in the repository for the full technical positioning.

## What the Grant Enables

**$75,000 — 6-month pilot:**
- 50-hectare mangrove site (Bali or Sumatra, partnership in progress)
- 15 displaced workers employed full-time at living wage
- AI agent stack for automated MRV (satellite API costs, compute)
- ICVCM Gold Standard carbon credit application
- Published welfare-ton MRV methodology (open source)

**Measurable outcomes:**
- Welfare-tons generated: target 500-2,000
- Workers employed: 15 full-time for 6 months
- Carbon credits verified: target 100-400 tonnes
- MRV cost reduction vs. traditional: target 60-70%
- Open-source MRV methodology publishable by month 4

## Alignment with Anthropic Economic Futures

Anthropic's stated concern: AI capabilities proliferating faster than society can
adapt, with economic displacement as the primary near-term harm.

This proposal addresses that directly by:
1. Creating employment for displaced workers using their irreplaceable physical
   presence in ecological restoration
2. Using AI capability (MRV automation) to make that employment economically viable
3. Generating a measurable welfare metric that can scale globally

The model is replicable: one successful 50-hectare pilot produces the methodology,
tooling, and carbon credit infrastructure to expand to 10 sites, then 100.

## Current Status

- DHARMA SWARM core architecture: operational (April 2026)
- Welfare-ton calculator: implemented in telos_substrate.py
- Economic engine: tracking revenue/expense flows
- Agent web search and world-action tools: deployed
- MRV data pipeline: architecture designed, implementation pending funding
- Mangrove site partnership: preliminary conversations underway (Bali)
- Invariant Observatory v1 (topological governance): implemented, tested against
  Lorenz fixture, registered in `ACTIVE_SURFACE_MANIFEST.yaml`, accreting readings
  pending sufficient gauntlet history (May 2026)
- Cultivation observer v1: implemented; falsifiable 7-day prediction logged in
  `docs/GPLOT_CAIRN.md` §7 (May 2026)

---

*This is a working draft. The welfare-ton MRV architecture spec is available
on request. The full codebase is public at github.com/AmitabhainArunachala/dharma_swarm.*
