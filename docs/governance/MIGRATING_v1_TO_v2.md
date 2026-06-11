# Migrating ACTIVE_TRACK.yaml: v1 (singular) → v2 (portfolio)

**Audience:** anyone (agent or human) editing `docs/governance/ACTIVE_TRACK.yaml`
who last touched it under schema_version 1.
**TL;DR:** the file now describes a **portfolio of 1..N co-equal tracks** with a
typed graph between them, not a single ACTIVE track. `make onboard` and the
checker still accept v1 for one release cycle; everything else has moved.

---

## 1. The one-sentence change

**v1:** `active_track: { id, status, prerequisites, completion_criteria, ... }`
— exactly one ACTIVE track, all dependency reasoning implicit.

**v2:** `spine_objectives: [...]` + `track_policy: {...}` + `active_tracks: [...]`
+ `closed_tracks: [...]` — 1..N co-equal tracks, with typed edges
(`depends_on`, `conflicts_with`, `serves`, `owned_surfaces`) the checker can
validate as a graph.

The v1→v2 adapter (`normalize_portfolio` in `scripts/governance/check_track_status.py`)
wraps a v1 file into a one-track v2 portfolio so legacy consumers keep working.

---

## 2. Shape — drop-in mapping

If your v1 looked like this:

```yaml
schema_version: 1
active_track:
  id: my-track
  status: ACTIVE
  prerequisites:
    - { id: p1, check: file_exists, path: foo.md }
  completion_criteria:
    - { id: c1, check: file_exists, path: bar.md }
```

The minimum v2 equivalent is:

```yaml
schema_version: 2

# NEW: declare the long-lived objectives the portfolio serves.
# Each track's `serves:` must point at one of these.
spine_objectives:
  - { id: obj-default, name: "Default spine objective" }

# NEW: WIP policy. The checker enforces these as ERROR/WARN.
track_policy:
  model: "1..N co-equal active tracks; typed graph; WIP-limited; surface-owned"
  min_active: 1
  max_active: 10
  warn_active: 5
  min_active_grace_days: 7            # advisory only
  min_active_grace_enforced: false    # explicit: NOT CI-enforced
  allow_active_active_conflict: false
  surface_overlap: warn

# RENAMED: `active_track:` (singular) → `active_tracks:` (list).
active_tracks:
  - id: my-track
    status: ACTIVE
    serves: obj-default               # NEW: required for ACTIVE tracks
    verified_at: "2026-06-09"         # NEW: ISO date the track was last verified
    ttl_days: 21                      # NEW: drift budget before re-verify
    # Optional typed edges (all default to []):
    depends_on: []                    # other track ids that must be SHIPPABLE first
    conflicts_with: []                # other track ids that can't be ACTIVE alongside
    owned_surfaces: []                # glob patterns this track owns
    prerequisites:
      - { id: p1, check: file_exists, path: foo.md }
    completion_criteria:
      - { id: c1, check: file_exists, path: bar.md }

# NEW: archive of historical tracks. Same shape as active_tracks but
# status != ACTIVE/SHIPPABLE. Edges from active → closed resolve fine.
closed_tracks: []
```

---

## 3. What's new that you should care about

| Concept | Why it exists | Where it's enforced |
| --- | --- | --- |
| `spine_objectives` | Long-lived "what are we even doing" anchors. Tracks are tactical; objectives are strategic. | `validate_portfolio_graph` — ERROR if an ACTIVE track has no/unknown `serves:`. |
| `track_policy.min_active` / `max_active` / `warn_active` | WIP limit. Focus is flow discipline, not a mutex. | CI ERROR if `n > max_active`; WARN if `n > warn_active` or `n < min_active`. |
| `min_active_grace_enforced` | Explicit tombstone so downstream consumers don't have to guess. Default `false` = advisory only. | Default false. Set true only if you wire actual auto-failure. |
| `depends_on` | Track A waits on Track B to be SHIPPABLE. Cycles are forbidden. | 3-colour DFS — emits the actual cycle path on failure. |
| `conflicts_with` | Two tracks can't both be ACTIVE. Default policy = ERROR; flip `allow_active_active_conflict` to allow. | `validate_portfolio_graph`. |
| `serves` | Which spine objective the track advances. Required for ACTIVE; optional for closed (validated if present). | `validate_portfolio_graph`. |
| `owned_surfaces` | Glob patterns of files/dirs this track is allowed to mutate. Overlap between ACTIVE tracks = WARN (or ERROR if `surface_overlap: error`). | `validate_portfolio_graph`. |
| `closed_tracks` | History without polluting the ACTIVE list. Edges from active → closed resolve normally. | `validate_portfolio_graph` shape-checks each entry (id required, edges must resolve). |

---

## 4. Edge resolution — the one rule that surprises people

Every typed edge (`depends_on`, `conflicts_with`) must point at an id that
exists in **either** `active_tracks` or `closed_tracks`. Dangling edges are
ERROR. So when you close a track, leave the entry in `closed_tracks` — don't
delete it, or every ACTIVE track that pointed at it will break the gate.

---

## 5. The v1 adapter — what stays working, what doesn't

`normalize_portfolio` accepts:

- `schema_version: 1` files with a singular `active_track:` (wrapped into a
  one-track portfolio with default policy).
- `schema_version: 2` files with full `active_tracks:`.
- A mixed file where `active_track:` exists at top level (treated as one v2
  track with default policy).

What does **not** work in v1 mode:

- `spine_objectives` — there is no spine; coverage checks are skipped.
- Typed-edge graph invariants — you only get the singular completion check.
- WIP limits — there's only ever one track.

If you want any v2 feature, migrate the file; the singular path is a
compatibility shim, not a maintained surface.

---

## 6. Checklist (paste into the PR description)

- [ ] `schema_version: 2`
- [ ] `spine_objectives:` declared, every active track's `serves:` resolves
- [ ] `track_policy:` block present with all six fields (plus
  `min_active_grace_enforced`)
- [ ] `active_track:` (singular) renamed → `active_tracks:` (list)
- [ ] Every active track has `id`, `status`, `serves`, `verified_at`, `ttl_days`
- [ ] All `depends_on` / `conflicts_with` ids resolve to declared tracks
- [ ] No `depends_on` cycles (checker prints the path if any exist)
- [ ] `python3 scripts/governance/check_track_status.py` runs clean locally
- [ ] `pytest tests/test_track_portfolio.py` runs clean locally

---

## 7. Where to look when something breaks

| Symptom | Where to look |
| --- | --- |
| `spine-missing:<tid>` | Track has no `serves:` — add one pointing at a spine objective id. |
| `spine-unresolved:<tid>` | `serves:` value isn't in `spine_objectives` ids — typo or missing objective. |
| `edge-unresolved:<tid>` | A `depends_on` / `conflicts_with` target isn't a declared track. Add it to `closed_tracks` or fix the id. |
| `dependency-cycle` | The checker prints `a -> b -> c -> a`. Break the cycle by deferring one edge. |
| `wip-exceeded` | More ACTIVE tracks than `max_active`. Close or merge one. |
| `surface-overlap:<glob>` | Two ACTIVE tracks both declared `owned_surfaces:` containing the same path. Split the surfaces or declare `conflicts_with`. |
| `closed-track-shape` | A `closed_tracks:` entry is missing an `id` or isn't a mapping. Same shape rules as active tracks apply. |

---

## 8. References

- Schema source: [`docs/governance/ACTIVE_TRACK.yaml`](./ACTIVE_TRACK.yaml)
- Optional CUE schema: [`docs/governance/active_track.schema.cue`](./active_track.schema.cue)
- Checker: [`scripts/governance/check_track_status.py`](../../scripts/governance/check_track_status.py)
- Tests: [`tests/test_track_portfolio.py`](../../tests/test_track_portfolio.py)
- Doctrine context: `SOVEREIGN_MANIFEST.md` (the `track_policy` amendment)