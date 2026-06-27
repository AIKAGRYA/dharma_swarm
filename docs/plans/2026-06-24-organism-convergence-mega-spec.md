---
title: Organism Convergence — Synthesis & Integration Spec
status: working_plan
created: 2026-06-24
owner: operator (John) + opus_composer
kind: plan
supersedes: prior short convergence sketches (this is the binding sequence)
---

# Organism Convergence — Synthesis & Integration Spec

> **This is a plan, not a map.** It does NOT replace `docs/MEGAFILE_INDEX.md`, `docs/governance/SWARM_GENOME.md`, or `docs/governance/ACTIVE_TRACK.yaml`. It does NOT define a new organ taxonomy. Its only output is a short sequence of PRs that update **existing homes**. When this plan's work lands, this file is metabolized (archived), not promoted to canon.

## 0. Governing constraint — read first

**Do not add noise. So much of this already exists.** This program is ~80% synthesis / signal / integration, not building. The cockpit + UX space already has several recent in-flight builds (a busy, "dirty" space). This convergence must become the conceptual + reality layer that **feeds** that existing space — never a parallel artifact beside it.

Every workstream below begins by inventorying what already exists and prefers **wiring existing pieces together** over creating anything new. The repo's own rule is binding (`MEGAFILE_INDEX.md`): *"convergence, not invention — do NOT create another root truth-spine doc."* Codex already wrote a tenth map (`DHARMA_SWARM_MASTER_MAP.md`); it was archived 2026-05-07. We do not repeat that.

Only two new files are sanctioned, both explicitly non-noise:
1. **this working-plan** (a temporary `plan`, permitted by the recursion rules), and
2. **`docs/architecture/LIMBS_ATLAS.md`** — already a *reserved* Slot 4 stub graduating STUB→SEEDED, blessed by `MEGAFILE_INDEX.md` recursion rules.

Everything else is **edits to existing homes**: `ACTIVE_SURFACE_MANIFEST.yaml`, `docs/ontology/semantic_objects.yaml`, the operator-coherence cockpit read model, `docs/MEGAFILE_INDEX.md`.

## 1. Executive frame

The repo *feels* like it needs one clean organization map. The verified reality is the opposite:

- **Conceptual layer: over-supplied but governed.** Nine canonical org-maps already exist (§2). They don't truly conflict — they're zoomed to different levels. The pain is that no one declared *how they nest*, so every new pass invents another list.
- **Physical layer: genuinely disordered.** ≈400 loose modules at the package root, dozens of loose files at repo root, ~4 parallel terminal trees, duplicate archive dirs, and the word "spine" used 6 distinct ways across ~1,237 mentions.

The job: **declare the nesting, govern the vocabulary, weave the map into live observability, stage the physical cleanup** — without mutating code in step one.

**Tie-line (the shared language; keep verbatim):**
> Genome gives direction. Organs hold function. Active tracks harden organs. Receipts prove motion. Cockpit projects proof.

## 2. Authority stack (inventory — owns / does-not-own)

| Home | Owns | Does NOT own |
|---|---|---|
| `docs/MEGAFILE_INDEX.md` | the 10 reserved onboarding slots; "convergence not invention" rule | live state; organ taxonomy |
| `foundations/THE_ORGANISM.md` | identity + genome: Krishna(inward)/Arjuna(outward); 4-layer (Foundations, Mechanisms, Self-Organs, Arjuna-Organs) | live state; build intent |
| `docs/vision_maps/NORTH_STAR.md` | the *why* / telos / vision | rules; live state |
| `docs/governance/SWARM_GENOME.md` | first-token compressed organism map (8 organs) + custody labels | live truth (explicitly "not a source of live truth") |
| `docs/governance/SOVEREIGN_MANIFEST.md` | architectural ground truth + measured counts | behavioral rules (defers to `CLAUDE.md`) |
| `docs/governance/CANONICAL_DOC_STACK.md` | doc ownership: 3-layer SSoT (Intent/Surface/State) + owner map | the facts themselves (points to owners) |
| `foundations/INDEX.md` | the 11 intellectual pillars + syntheses + PSMV lattice | operational/runtime truth |
| `docs/ontology/SEMANTIC_COMMONS.md` (+ `semantic_objects.yaml`, `semantic_aliases.yaml`) | durable names, aliases, lifecycle states | architecture; live state |
| `docs/governance/ACTIVE_TRACK.yaml` | current build **intent** (the portfolio) — Intent layer | surfaces; runtime state |
| `ACTIVE_SURFACE_MANIFEST.yaml` | the **surface registry** (what exists in code) — Surface layer | intent; doctrine |

## 3. Taxonomy nesting model (declare levels, not a new list)

The organ-list churn has one root cause: there are already **four+ canonical organ taxonomies at different zoom levels**, and nobody declared which is which, so each pass invents a fifth. The fix is a nesting declaration, not a better blend.

| Level | Owner | Vocabulary |
|---|---|---|
| Genome (why/identity) | `foundations/THE_ORGANISM.md` | Krishna/Arjuna; Foundations/Mechanisms/Self-Organs/Arjuna-Organs |
| Governance organism map (first-token) | `docs/governance/SWARM_GENOME.md` | the 8 compressed organs |
| Outward organs (Arjuna) | `docs/governance/VENTURE_CELL_PORTFOLIO.yaml` | venture cells |
| Build lanes (current work) | `docs/governance/ACTIVE_TRACK.yaml` | active tracks |
| Physical limbs (code) | Slot 4 `docs/architecture/LIMBS_ATLAS.md` | modules/limbs |

**Rule (binding):** *No agent may introduce a new organ/limb list unless it names the level and the owning file above.* Codex's "blended 12-organ map" is rejected on this rule — and specifically its placement of **Holarchy as an organ** is wrong: per `docs/architecture/ADRs/ADR-009-holarchy-and-falsifiable-coherence.md`, Holarchy is the *coordination pattern*, not a body part.

## 4. Vocabulary policy

**Approved terms** (each resolves to one owner): Runtime Truth Spine, Agent Communications Fabric, Semantic Commons, Holarchy, Cybernetic Loop Ecology, Evolution Engine, Active Track, Venture Cell, Limb / Module.

**Discouraged / ambiguous** (require disambiguation): bare **"spine"** (means ≥6 things today; in code, reserve for the Runtime Truth Spine), "holarchy organ", "active track organ", "transport presence".

**Krishna/Arjuna vocabulary boundary (load-bearing).** Venture-cell statuses (§5) describe *outward-facing, external-market readiness* and must **never** be applied to internal code surfaces. Worked example of the violation to fix: `operator_core/world_radar/receipt_bridge.py` is an internal module yet is tagged `INCUBATING` (a venture-cell status) in `SOVEREIGN_MANIFEST.md`, while its sibling bridges use `ALIVE`/`STALE`. That contamination is the canonical illustration of why this boundary is governed.

**Enforcement:** route through Semantic Commons + the **existing** `scripts/governance/name_drift_preflight.py`. Gradual — no hard-fail on historical text in the first vocabulary PR.

## 5. Observability discipline — "one source, two faces" (first-class, integration-only)

The map must not be hand-written prose that rots (the fate of `docs/architecture/NAVIGATION.md`, now stale). It renders from the **same machine-readable source the cockpit already reads**.

- **The one source:** `ACTIVE_SURFACE_MANIFEST.yaml` — each entry already carries `id`, `route`, code location (`api_dependencies`/`module`), `status`, `health_check_ids`, `next_action`, `wired_to`.
- **Face A (still photo):** the human limbs map = Slot 4 `LIMBS_ATLAS.md`, rendered from the manifest.
- **Face B (live feed):** the cockpit = `dharma_swarm/operator_core/operator_coherence_cockpit.py` + `api/routers/operator_coherence.py`, which **already** read the manifest and probe git/process/loop state live.

They can never disagree because they read the same source. This is wiring two existing things together — not a new build.

**Status lattice — two existing axes, kept separate (no new vocabulary imported across the boundary):**

| Axis | Applies to | Vocabulary (already exists) | Owner |
|---|---|---|---|
| Liveness/wiring | internal limbs/surfaces | `live / degraded / stub / shadow / incubating / declared_not_started` (+ `next_action`) | `ACTIVE_SURFACE_MANIFEST.yaml` |
| Dormant-value | outward Arjuna organs only | `ACTIVE_SEASON_0 / ACTIVE_BUILD_TRACK / INCUBATING / DESIGN_ONLY / ENVISIONED / DORMANT / HELD / RETIRED` | `VENTURE_CELL_PORTFOLIO.yaml` |

**Anti-forgetting:** the internal liveness axis already carries the "built-but-unwired" signal (`stub`/`degraded` + a non-null `next_action`, or `wired_to: []`). The cockpit renders this so valuable-but-unwired work stays visible, not forgotten. *Add at most ONE* honest internal value (e.g. `built_unwired` / `parked`) **only if** the existing values prove insufficient in practice — decided during PR4, not assumed now.

**Discipline rule (binding):** every limb entry on the map must resolve to either a `health_check_id` (provably live) or an honest non-live status. *No box without one or the other.* This is what kills the "is this real or aspirational?" confusion at the source.

## 6. Physical-tree problem statement

Measured disorder (prior-session counts — **re-measure fresh before any move**, do not trust these):
- ~400 loose `.py` modules at the `dharma_swarm/` package root (should nest into existing subpackages: `operator_core/`, `memory_kernel/`, `a2a/`, `chetana/`, …).
- dozens of loose files at repo root (doctrine `.md` mixed with operational scripts/config).
- ~4 parallel terminal trees (`terminal/`, `terminal-v2/`, `terminal_engine/`+siblings) for one concern.
- duplicate `archive/` and `_archive/` trees.
- "spine" overloaded across ~1,237 mentions.

Fresh-measurement commands to run at implementation time:
```
ls -1 dharma_swarm/*.py | wc -l            # loose package-root modules
ls -1 *.md | wc -l                          # loose root docs
grep -rIl --include=*.py -e '\bspine\b' .   # spine usage surface
```

## 7. Program workstreams (integration-first; each starts "what already exists")

- **A — Slot 4 Limbs Atlas.** Create `docs/architecture/LIMBS_ATLAS.md` rendering **physical/code limbs only** from `ACTIVE_SURFACE_MANIFEST.yaml`; update `MEGAFILE_INDEX.md` Slot 4 STUB→SEEDED. Not a master map; it explains limbs and points back to the manifest as owner.
- **B — Vocabulary governance.** Add approved/forbidden architectural terms to `docs/ontology/semantic_objects.yaml` + aliases; add tests; wire `name_drift_preflight.py`. Fix the `receipt_bridge.py` contamination.
- **C — Observability projection.** Connect manifest ↔ cockpit ↔ `make onboard` so the two faces stay identical and built-but-unwired stays visible. Decide the single optional internal status value here, only if needed.
- **D — Physical-cleanup discovery track.** Open a **proposed** (not active) track scoping package-root nesting, terminal consolidation, archive consolidation.
- **E — Enforcement & receipts.** Add checks gradually; no hard-fail on historical text in the first PR.

## 8. Requirements

**Functional**
- An agent can determine which map level (§3) owns any given concept.
- Major terms resolve through Semantic Commons.
- Slot 4 explains physical limbs without becoming a master map.
- Every limb on the map cites a live probe or an honest status.
- Physical cleanup can be opened as a normal active track.

**Non-functional**
- No new first-read surface; no new root truth doc.
- No broad file moves in the first PR.
- No hard vocabulary gate until registry + tests prove stable.
- Every claim cites an owner.
- No second source for observability — render from the existing manifest only.

## 9. Alternatives considered

- **New `ORGANISM_OPERATING_MAP.md`** — reject: this is map #10, the exact noise the governing constraint forbids; the prior `DHARMA_SWARM_MASTER_MAP.md` was already archived for this.
- **Refresh only `SWARM_GENOME.md`** — partial: good for orientation, wrong home for the physical tree.
- **Physical cleanup first** — reject: cleanup without vocabulary governance repeats the same confusion.
- **Semantic Commons only** — partial: vocabulary improves but the physical tree and observability stay unaddressed.

## 10. Rollout

| PR | Scope | Mutates |
|---|---|---|
| **PR1** | this spec | one new plan file (this) |
| **PR2** | Slot 4 `LIMBS_ATLAS.md` seeded; Slot 4 status STUB→SEEDED | `docs/architecture/LIMBS_ATLAS.md` (new, sanctioned), `docs/MEGAFILE_INDEX.md` (edit) |
| **PR3** | vocab objects/aliases/tests; fix `receipt_bridge` contamination | `docs/ontology/*.yaml`, tests, `SOVEREIGN_MANIFEST.md` (one-line fix) |
| **PR4** | observability projection (manifest↔cockpit↔onboard); optional 1 internal status value | manifest, cockpit read model, onboard |
| **PR5** | proposed physical-cleanup track | `ACTIVE_TRACK.yaml` (proposed entry) |
| **PR6+** | cleanup slices, one surface family at a time | code moves, each with fresh dependency + import/test proof |

## 11. Verification matrix

| Area | Check |
|---|---|
| Docs ownership | no new root master map; `MEGAFILE_INDEX.md` remains the slot authority |
| Vocabulary | registry parses; forbidden aliases fail tests; approved aliases resolve; `receipt_bridge` contamination fixed |
| Active track | track checker still passes; optional fields don't break parsers |
| Onboard | `make onboard` still renders; no new first-read burden |
| Observability | every limb resolves to a `health_check_id` or an honest status; cockpit + Slot 4 render from the same manifest (no second source) |
| Physical cleanup | fresh inventory generated before any move; every move has import/test proof |

## 12. No-gos

- Do not create another master map.
- Do not rename the whole organism vocabulary in one pass.
- Do not move code before fresh dependency/import analysis.
- Do not hard-fail all historical uses of "spine" immediately.
- Do not collapse Krishna / Arjuna / Genome language into generic enterprise-architecture terms.
- Do not treat Holarchy as an organ.
- **Do not apply venture-cell statuses to internal code surfaces.**

## 13. Open sequencing questions (carried, not blocking)

1. Slot 4 STUB→SEEDED in PR2, or only after a fresh code inventory is embedded?
2. The single optional internal "built-but-unwired/parked" status — add it, or is `stub`/`degraded` + `next_action` already enough? (decide in PR4 from real usage)
3. Physical-cleanup first target: package-root modules, terminal trees, or archives?

## Acceptance

This spec is complete when another agent can implement **PR2** without deciding: where the synthesis belongs, which maps are canonical, which terms are approved/forbidden, which work is documentation-convergence vs physical cleanup, which PR comes first, or what tests prove the first slice safe.
