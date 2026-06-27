# KAIZENOPS

Purpose: primary continuous-improvement owner for Dharma Swarm operating loops.
This file is an umbrella governance map. It does not own live state, runtime
truth, doctrine, active-track intent, or ontology mutation.

## One-Line Role

KaizenOps owns the improvement metabolism: observe reality, find waste, route
one bounded corrective action, verify the result, and prevent the same failure
from reappearing as more diagnosis.

## Why This Exists

The system already has many observation surfaces: AgentOps, live ops, drift
triage, daily briefs, hygiene scans, reality-debt ledgers, name-drift scans,
Semantic Commons, result verifiers, and Hermes pulses. Without a single
improvement owner, those surfaces can produce beautiful reports while the same
failures persist.

KaizenOps is the owner of the conversion from observation to verified
improvement. It is the Andon/Kaizen layer above AgentOps and below active-track
ownership.

## Authority Boundary

KaizenOps may:

- read and summarize evidence from operational surfaces;
- classify waste, drift, blocked loops, repeated failures, stale maps, and
  claim inflation;
- recommend exactly one next corrective work packet per review;
- require a receipt before an improvement is counted;
- mark repeated diagnosis-without-action as a failure mode;
- ask the relevant owner to open, amend, or close an active track.

KaizenOps may not:

- replace `docs/governance/ACTIVE_TRACK.yaml` as intent owner;
- replace `ACTIVE_SURFACE_MANIFEST.yaml` as surface owner;
- replace runtime receipts or `RuntimeStateStore` as live-state owner;
- mutate Semantic Commons or ontology objects directly;
- assign final Human YDS ratings;
- claim an organ is live without owner evidence and a verifier.

## Primary Umbrella Surfaces

These surfaces are KaizenOps-adjacent. KaizenOps owns their improvement
interpretation, not their raw facts.

| Surface | Current owner | KaizenOps relation |
|---|---|---|
| AgentOps | `docs/governance/AGENTOPS.md`, reports/agentops | raw run evidence and work-packet receipts |
| KaizenReview bridge | `scripts/governance/kaizen_review_from_agentops.py`, `dharma_swarm/fractal/kaizen_review.py` | converts AgentOps reports into improvement reviews |
| Daily Operating Brief | `docs/governance/DAILY_OPERATING_BRIEF.md`, `dharma_swarm/daily_operating_brief.py` | daily operating projection; KaizenOps extracts durable corrective actions |
| Metabolic Clock | `docs/governance/METABOLIC_CLOCK.md` | cadence discipline; KaizenOps checks whether cadence produces value |
| Human YDS Ledger | `docs/governance/HUMAN_YDS_LEDGER.md`, `dharma_swarm/human_yds_ledger.py` | human value rating boundary; KaizenOps cannot forge final YDS |
| Drift triage | `dharma_swarm/dhyana/drift_triage.py` | ranked drift inputs; KaizenOps routes one repair at a time |
| Broken Register | `docs/state/BROKEN_REGISTER.md` | persistent known breakage; KaizenOps prevents orphaned breakage |
| Reality Debt Ledger | `docs/governance/REALITY_DEBT_LEDGER.md` | claim inflation debt; KaizenOps downgrades overclaims until receipts exist |
| Coherence Delta | `docs/governance/COHERENCE_DELTA.md` | PR/change coherence; KaizenOps treats incoherence as waste |
| Vibe-code hygiene | `docs/governance/VIBE_CODE_HYGIENE.md`, `docs/governance/hygiene/` | repeated AI-agent antipattern signals |
| Name Drift Preflight | `scripts/governance/name_drift_preflight.py` | naming waste and alias ambiguity inputs |
| Semantic Commons | `docs/ontology/SEMANTIC_COMMONS.md`, `dharma_swarm/semantic_commons.py` | identity-resolution substrate; KaizenOps routes drift into it, not around it |
| Live Ops Cockpit | `docs/ops/LIVE_OPS_COCKPIT.md`, live dashboards | runtime projection; KaizenOps checks live/projection mismatch |
| Manifest Health | `ACTIVE_SURFACE_MANIFEST.yaml`, `dharma_swarm/manifest_health.py` | declared-surface drift input |
| Greptile automated PR review | GitHub Greptile app comments + `reports/governance/greptile_review_intake_*.md/json` | advisory review signal; P1/P2 triage input for Mike packets |
| Hermes global pulse | `/Users/dhyana/.hermes/config/global_pulse_map.json` | cross-repo observer; KaizenOps is the improvement owner for repeated pulse findings |
| Hermes proactive effector | `/Users/dhyana/.hermes/scripts/proactive_effector.py` | effectors must act on real owner paths and write receipts |
| Hermes self dispatch | `/Users/dhyana/.hermes/scripts/self_dispatch.py` | anomaly-to-action path; KaizenOps rejects false-hand fixes |

## KaizenOps Improvement Contract

Every KaizenOps item must carry:

1. Observation: what was seen, with path or command evidence.
2. Owner: which file, track, script, service, or human owns the fact.
3. Waste class: diagnosis loop, false hand, name drift, claim inflation,
   stale map, broken receipt, dead provider, duplicate surface, missing owner,
   or external-proof gap.
4. One next action: the smallest bounded change that can reduce the waste.
5. Verifier: command, file, receipt, metric, test, or external proof.
6. Stop condition: when to stop observing and either ship, escalate, or close.

If an item lacks a verifier, it remains advisory and must not become a green
status claim.

## Canonical Failure Modes KaizenOps Must Catch

- Observation without consequence.
- Report generation after the same diagnosis has already converged.
- Handler ACK treated as semantic agreement.
- Delivery success treated as work completion.
- Generated receipts treated as external value.
- Map proliferation without one owner path.
- Path drift: detecting one path and fixing another.
- Active-track pressure used to close work without operator authorization.
- First-token orientation losing the organism map.
- Runtime projection claiming authority over live state.

## Current Organism Separation

KaizenOps is not another organ beside the rest. It is the improvement membrane
around all organs.

- Runtime/Substrate: makes execution possible.
- Governance: defines owners, tracks, and rules.
- Memory/Knowledge: preserves and routes context.
- Semantic Commons/Ontology: resolves names and object identity.
- Research: produces falsifiable knowledge.
- Revenue/Capital: metabolizes external value into compute and capability.
- Media/Noosphere: transmits output to the world.
- KaizenOps: watches all of the above for waste and converts one finding into
  one verified improvement.

## Lead Map Relationship

The live first door remains `make onboard`.
The first-token conceptual map remains `docs/governance/SWARM_GENOME.md`.
The whole-system why remains North Star v2: `docs/vision_maps/NORTH_STAR.md`.
The identity/body plan remains `foundations/THE_ORGANISM.md`.
The organ/status owner remains `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`.
The improvement owner is this file: `docs/governance/KAIZENOPS.md`.

## Visual Map

The current visual projection is:

`docs/vision_maps/ALIVE_ORGAN_MAP_2026-06-18.svg`

It is a projection, not authority. If it disagrees with owner files, update the
visual or mark it stale.

## Verifier Commands

```bash
make onboard
make docops-integrity
make semantic-commons-check
make bug-corral-scan
python3 scripts/governance/name_drift_preflight.py --json-output /tmp/name_drift_preflight.json --markdown-output /tmp/name_drift_preflight.md
```

## Upgrade Rule

A KaizenOps review is successful only if one of these changes happens:

- a broken path is fixed;
- a repeated alert is silenced because the underlying condition changed;
- a stale map is pointed to its owner or demoted;
- a verifier becomes stricter;
- a claim is downgraded to match evidence;
- a work packet lands with a receipt;
- the operator receives a clearer next decision with fewer moving parts.

No proof of one of those changes means the review produced value 0.
