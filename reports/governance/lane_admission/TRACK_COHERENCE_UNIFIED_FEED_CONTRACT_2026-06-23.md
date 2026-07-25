# Track Coherence Unified Feed Contract — 2026-06-23

## Why this exists

The grading/audit branch advanced after the earlier backplane spec. It now adds a single cockpit-ready projection:

```text
reports/governance/track_coherence.json
reports/governance/track_coherence.md
scripts/governance/track_coherence.py
make track-coherence
```

This unified feed should become the cockpit's preferred track-coherence input once the grading branch lands. Until then, it is **branch-candidate truth**, not canonical truth.

## Verified git state

- Canonical main: `origin/main` = `839fd25f43c76375f49e45012fe8f20a324aa74c`
- Grading branch: `origin/claude/tracks-consolidation-grading-nb67lq` = `bfaaae350ca784355ac1829898f23aa7dceb8813`
- Branch relation: `0 behind / 9 ahead` relative to `origin/main`
- Latest relevant commit: `governance: unified track coherence projection (one feed for the cockpit)`

Canonicality: `OPEN_PR_REMOTE` / candidate. Do not present as canonical until the branch lands.

## Real schema, verified from branch blob

Top-level keys:

```text
generated_at
doctrine
portfolio
umbrellas
tracks
```

`portfolio` keys:

```text
active
close_ready
overstated
objective_coverage
uncovered_objectives
```

`umbrellas[]` keys:

```text
id
name
members
keystone
blocked_on
close_ready
rollup_state
```

`tracks[]` keys:

```text
id
umbrella
serves
owner
coherence_state
presence
file_shippable
quality_grade
quality_score
attested_shippable
audit_opinion
claim_holds
holds_votes
opinion_spread
high_smells
verified_age_days
ttl_days
stale
open_blockers
depends_on
```

## Cockpit preference order

When available and canonical, the cockpit should prefer:

1. `track_coherence.json` — unified track row/umbrella projection for UI.
2. `track_health.json` — quality grade + attestation backing feed.
3. `track_audits/*.audit.json` — raw audit quorum backing feed.
4. `active_track_evidence.json` — canonical presence feed always available on main.

While `track_coherence.json` is branch-only, the cockpit may project it only with a visible `OPEN_PR_REMOTE` / candidate badge.

## Mapping to prior backplane fields

| Prior backplane signal | Unified feed field |
|---|---|
| presence_grade | `presence`, `file_shippable` |
| quorum_attestation | `attested_shippable`, `holds_votes`, `audit_opinion`, `opinion_spread` |
| claim_holds | `claim_holds` |
| coverage_contribution | `serves`, `portfolio.objective_coverage`, `portfolio.uncovered_objectives` |
| staleness_ttl | `verified_age_days`, `ttl_days`, `stale` |
| blockers | `open_blockers`, `depends_on`, umbrella `blocked_on` |
| OVERSTATED | `coherence_state == "OVERSTATED"` or track id in `portfolio.overstated` |
| close-ready | `coherence_state == "CLOSE_READY"` or track id in `portfolio.close_ready` |

## UI guidance

- Surface `portfolio.uncovered_objectives` at the top of the cockpit: the monothematic substrate-only gap remains the biggest coherence defect.
- Render `coherence_state` as the dominant track row state, not raw file shippability.
- Show `presence` and `claim_holds` as distinct columns; file-green + `claim_holds=false` is the loud OVERSTATED condition.
- Render umbrella rollups as the 3-row strategic view:
  - Runtime Truth Spine
  - Cybernetic Closure & Routing
  - Sovereign Holons

## Doctrine

The unified feed is explicitly a read model: `doctrine = "read model: projects from owners; owns no truth"`. The cockpit must keep this doctrine and not treat the feed as a new authority store.
