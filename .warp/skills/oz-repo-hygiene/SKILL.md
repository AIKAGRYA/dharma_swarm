---
name: oz-repo-hygiene
description: Scheduled repo-hygiene janitor for dharma_swarm. Use to triage open PRs, detect stale maps/docs, age the broken register, report branch/worktree sprawl, and check the swarm genome — emitting ONE consolidated triage PR or issue. Recommends only; never merges, closes others' PRs, pushes to protected branches, or mutates governance.
---

# oz-repo-hygiene (W4 — Cleanup Janitor)

Anti-slop justification: this net-new skill is the Oz "janitor" archetype. It reduces reorientation entropy by extending existing surfaces (`make onboard`, `docs/state/BROKEN_REGISTER.md`, the stale maps) and produces a reviewable merge queue, not autonomous changes.

You reclaim operator reorientation time by turning repo entropy into a single reviewable queue. You recommend; the operator decides.

## Authority boundary (hard)
- MAY: read repo + git + PR metadata, compute staleness/triage, open ONE consolidated triage PR or issue with recommendations, refresh clearly-generated maps within that PR.
- MUST NOT: merge, close, or approve PRs; push to protected branches; delete branches; rewrite history; expose secrets; or edit governance/canon authority files (`docs/governance/ACTIVE_TRACK.yaml`, kernel/telos surfaces, anything between `ACTIVE_TRACK:START/END` markers). Output is a proposal.

## Freshness thresholds (the definitions — do not improvise per run)
- **Stale PR**: no commit, review, or comment in **14 days**.
- **Superseded PR**: another open or merged PR touches the same surface with newer commits — cite the superseding PR number.
- **Stale map/doc**: last commit touching it is older than **30 days** AND `git log` shows ≥ 20 commits to the surfaces it describes since then. Maps in scope: `CYBERNETIC_LOOP_MAP.md`, `INTERFACE_MISMATCH_MAP.md`, `docs/state/LIVE_OPS_DASHBOARD.md`, `docs/architecture/NAVIGATION.md`.
- **Worktree budget** (per CLAUDE.md): open worktrees ≤ active-track count + 1 primary tree + ≤2 TTL-tagged scratch. Anything beyond, or unmapped to an active track, is a violation to report.

## Procedure
1. **Orient**: `make onboard`; capture active tracks, broken register, live-ops staleness.
2. **PR triage**: `gh pr list --state open --json number,title,updatedAt,author,labels`; classify each as `merge-ready` / `needs-review` / `stale` / `superseded` with a one-line reason and a recommended action (`merge` / `review` / `rebase` / `close`). Recommendations only — act on none of them.
3. **Stale maps/docs**: apply the threshold above; for each stale map, draft refreshed content as changes inside the triage PR, clearly marked generated. Never hand-write between managed markers.
4. **Broken-register aging**: update `last_verified` / age fields on open items in `docs/state/BROKEN_REGISTER.md`; flag any whose repro command now passes as auto-resolvable (do not resolve them yourself).
5. **Sprawl report**: count worktrees + local branches; list branches with no active-track anchor and worktrees over budget.
6. **Genome**: regenerate or diff the swarm genome map if a generator exists; otherwise note drift and where you looked.

## Output
- ONE consolidated branch + PR (or issue) titled `repo hygiene <YYYY-MM-DD>` containing the four sections below, in this order. Never more than one PR per run. If nothing is actionable, open nothing and report `HYGIENE: clean` with the counts you checked.

```
## PR triage
| PR | Title | Class | Age | Recommendation | Why (one line) |
|----|-------|-------|-----|----------------|----------------|
| #781 | fix loop5b gap code | stale | 21d | close | superseded by #755, same surface, merged |

## Stale maps refreshed
- <map>: <threshold hit: last touch Xd ago, N commits to described surfaces> → refreshed in this PR

## Broken register aging
- <BR-id>: last_verified bumped <old → new>; <still-broken | AUTO-RESOLVABLE: repro now passes (`cmd`, exit 0)>

## Sprawl
worktrees: <n>/<budget> · branches with no track anchor: <list>
```

- A JSON receipt under `reports/loop_closure/oz_hygiene/<YYYY-MM-DD>.json`:

```json
{
  "run_date": "2026-07-05",
  "prs_triaged": 12,
  "classification_counts": {"merge-ready": 2, "needs-review": 5, "stale": 4, "superseded": 1},
  "maps_refreshed": ["CYBERNETIC_LOOP_MAP.md"],
  "broken_register_aged": 7,
  "auto_resolvable": ["BR-014"],
  "worktrees": {"count": 5, "budget": 7, "unmapped": []},
  "output": "PR #<n> | issue #<n> | clean"
}
```

## Do NOT / stop conditions
- Anything requiring merge/close/secret/governance authority: stop and list it under a "needs operator" section instead of acting.
- Do not classify from memory or vibes — every `stale`/`superseded` label needs the dates or PR numbers that justify it in the "Why" column.
- Do not refresh a map by hand-editing generated regions; run the generator or mark the draft clearly generated.
- Do not open a second PR to "finish" a run; fold everything into the one queue or report clean.
- Do not delete, archive, or compost anything — recommend it and let the operator's compost flow (`~/.claude/cabinet/_compost/`) handle removal.
