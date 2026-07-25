# Open PR Disposition Receipt

Repository: `AmitabhainArunachala/dharma_swarm`
Receipt timestamp: `2026-06-29T16:04:43Z`
Scope: open PRs only.

## Summary

Open PRs inspected: 13

Disposition counts:

| Disposition | Count |
| --- | ---: |
| MERGE_READY | 0 |
| NEEDS_REBASE | 2 |
| NEEDS_FIX | 4 |
| SUPERSEDED_CLOSE | 7 |
| OPERATOR_DECISION | 0 |
| BLOCKED | 0 |

No pending or unknown checks were found in the spot-check query. All non-green CI states below are completed failures.

## PR Matrix

| PR | Branch | Draft | Merge state | CI state | Disposition | Next action |
| --- | --- | --- | --- | --- | --- | --- |
| [#704](https://github.com/AmitabhainArunachala/dharma_swarm/pull/704) | `codex/pudgala-autopoiesis-protostar-20260626` | yes | `DIRTY`, mergeable=`CONFLICTING` | 27 success, 0 failure | NEEDS_REBASE | Rebase/resolve conflicts first; CI was green on the captured head but cannot merge while conflicting and draft. |
| [#706](https://github.com/AmitabhainArunachala/dharma_swarm/pull/706) | `ops/report-2026-06-26T0000Z` | yes | `CLEAN` | 30 success, 0 failure | SUPERSEDED_CLOSE | Older automated ops report. Propose close as superseded; do not merge despite green CI. |
| [#708](https://github.com/AmitabhainArunachala/dharma_swarm/pull/708) | `oz/spine-metric-refresh-2026-06-26` | yes | `UNSTABLE` | 29 success, 2 failure | SUPERSEDED_CLOSE | Older duplicate/stale spine metric refresh. Propose close/supersede; if kept, repair pytest 3.11/3.12 failures. |
| [#710](https://github.com/AmitabhainArunachala/dharma_swarm/pull/710) | `chore/spine-adoption-metric-refresh` | yes | `UNSTABLE` | 27 success, 3 failure | NEEDS_FIX | Repair quality ratchet regression and matching pytest ratchet failures before considering undraft. |
| [#713](https://github.com/AmitabhainArunachala/dharma_swarm/pull/713) | `claude/anti-slop-enforcement-2026-06` | no | `DIRTY`, mergeable=`CONFLICTING` | 31 success, 1 failure | NEEDS_REBASE | Resolve merge conflict first; then fix the branch workflow missing `ruff` in quality-ratchet. |
| [#714](https://github.com/AmitabhainArunachala/dharma_swarm/pull/714) | `ops/report-2026-06-26T1800Z` | yes | `CLEAN` | 31 success, 0 failure | SUPERSEDED_CLOSE | Older automated ops report. Propose close as superseded; do not merge despite green CI. |
| [#715](https://github.com/AmitabhainArunachala/dharma_swarm/pull/715) | `ops/report-2026-06-27T0000Z` | yes | `BLOCKED` | 30 success, 1 failure | SUPERSEDED_CLOSE | Stale automated ops report blocked by DocOps. Propose close/supersede. |
| [#716](https://github.com/AmitabhainArunachala/dharma_swarm/pull/716) | `slice/roast-skill` | yes | `UNSTABLE` | 30 success, 1 failure | NEEDS_FIX | Fix pytest 3.11 timeout in `tests/test_sleep_cycle.py::test_graceful_degradation`. |
| [#717](https://github.com/AmitabhainArunachala/dharma_swarm/pull/717) | `ops/report-2026-06-27T1800Z` | yes | `BLOCKED` | 29 success, 3 failure | SUPERSEDED_CLOSE | Stale automated ops report blocked by DocOps plus manifest-health pytest failures. Propose close/supersede. |
| [#718](https://github.com/AmitabhainArunachala/dharma_swarm/pull/718) | `claude/monetization-strategy-team-rgn7g6` | no | `BLOCKED`, mergeable=`MERGEABLE` | 26 success, 4 failure | NEEDS_FIX | Repair DocOps, import provenance, and manifest-health failures. |
| [#719](https://github.com/AmitabhainArunachala/dharma_swarm/pull/719) | `claude/sis-seed1-carbon-attribution` | no | `BLOCKED`, mergeable=`MERGEABLE` | 31 success, 3 failure | NEEDS_FIX | Repair DocOps and manifest-health failures. |
| [#720](https://github.com/AmitabhainArunachala/dharma_swarm/pull/720) | `ops/report-2026-06-28T1800Z` | yes | `UNSTABLE` | 30 success, 3 failure | SUPERSEDED_CLOSE | Stale automated ops report blocked by quality ratchet. Propose close/supersede. |
| [#722](https://github.com/AmitabhainArunachala/dharma_swarm/pull/722) | `ops/ops-report-2026-06-29T0600Z` | yes | `UNSTABLE` | 30 success, 3 failure | SUPERSEDED_CLOSE | Latest captured automated ops report is still draft/unstable and stale for this campaign receipt. Propose close/supersede. |

## Commands Run

All commands were read-only except writing this receipt file.

| Timestamp UTC | Command |
| --- | --- |
| `2026-06-29T15:57:52Z` | `gh pr list --repo AmitabhainArunachala/dharma_swarm --state open --json number,title,headRefName,isDraft,mergeStateStatus,updatedAt,url --limit 100` |
| `2026-06-29T15:58Z` | `for n in 706 714 704 713 716 718 719 708 710 715 717 720 722; do gh pr view "$n" --repo AmitabhainArunachala/dharma_swarm --json number,mergeStateStatus,statusCheckRollup,isDraft,headRefName,title,updatedAt,url; done` |
| `2026-06-29T15:59Z` | `for n in 706 714 704 713 716 718 719 708 710 715 717 720 722; do gh pr view "$n" --repo AmitabhainArunachala/dharma_swarm --json number,statusCheckRollup; done` |
| `2026-06-29T16:00:50Z` | `for n in 706 714 704 713 716 718 719 708 710 715 717 720 722; do gh pr view "$n" --repo AmitabhainArunachala/dharma_swarm --json number,statusCheckRollup --jq 'pending/unknown selector'; done` |
| `2026-06-29T15:59Z-16:03Z` | Spot-check logs with `gh run view <run_id> --repo AmitabhainArunachala/dharma_swarm --job <job_id> --log` for failing quality-ratchet, DocOps, import-provenance, and pytest jobs. |
| `2026-06-29T16:04:43Z` | `date -u +%Y-%m-%dT%H:%M:%SZ` |
