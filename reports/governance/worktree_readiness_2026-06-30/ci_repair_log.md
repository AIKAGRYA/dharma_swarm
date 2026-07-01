# CI Repair Log

Repository: `AmitabhainArunachala/dharma_swarm`
Receipt timestamp: `2026-06-29T16:04:43Z`
Scope: open PRs only.

No pending or unknown checks were returned by the `statusCheckRollup` spot check. The items below are completed failures or explicit non-CI blockers.

## Repair Matrix

| PR | Failed/pending/unknown checks | Narrowest next repair or blocker |
| --- | --- | --- |
| [#704](https://github.com/AmitabhainArunachala/dharma_swarm/pull/704) | None. CI was 27/27 success. | Non-CI blocker: merge conflict (`mergeable=CONFLICTING`) plus draft. Rebase/resolve conflicts; rerun checks after conflict resolution. |
| [#706](https://github.com/AmitabhainArunachala/dharma_swarm/pull/706) | None. CI was 30/30 success. | No repair recommended. Superseded automated ops report; propose close/supersede. |
| [#708](https://github.com/AmitabhainArunachala/dharma_swarm/pull/708) | `pytest (3.11)`, `pytest (3.12)` | Supersede/close preferred. If kept: fix `tests/test_sleep_cycle.py::test_graceful_degradation` timeout on 3.11 and `tests/test_bootstrap_loops.py::test_full_loop_closure` on 3.12 (`Expected COMPLETED, got TaskStatus.RUNNING`). |
| [#710](https://github.com/AmitabhainArunachala/dharma_swarm/pull/710) | `Quality ratchet - repo-wide fitness function`, `pytest (3.11)`, `pytest (3.12)` | Quality ratchet reports `modules_over_500_lines` regression from 207 to 208. Split/refactor the newly over-budget module or remove the regression, then rerun `python3 scripts/governance/hygiene/ratchet.py --json` and pytest. Do not merely raise the baseline unless the operator accepts the regression. |
| [#713](https://github.com/AmitabhainArunachala/dharma_swarm/pull/713) | `Quality ratchet - whole-tree regression + baseline freshness` | First blocker: merge conflict. CI root cause from log: `ratchet: BROKEN - ruff binary not found (.venv/bin/ruff or PATH)`. After rebase, install/provision `ruff` in that workflow before invoking `scripts/governance/hygiene/ratchet.py`. |
| [#714](https://github.com/AmitabhainArunachala/dharma_swarm/pull/714) | None. CI was 31/31 success. | No repair recommended. Superseded automated ops report; propose close/supersede. |
| [#715](https://github.com/AmitabhainArunachala/dharma_swarm/pull/715) | `DocOps integrity gate` | Supersede/close preferred. If kept: refresh DocOps assertions expired on 2026-06-26 (`verified_at=2026-06-12`, `ttl_days=14`) and regenerate stale `docs/docops/AUTO_INVENTORY.md`. |
| [#716](https://github.com/AmitabhainArunachala/dharma_swarm/pull/716) | `pytest (3.11)` | Fix timeout in `tests/test_sleep_cycle.py::test_graceful_degradation` (`Timeout >30s`). Log shows path through `SleepCycle.run_full_cycle()` -> `bridge_coordinator.discover_all()` -> `_discover_concept_files`; narrow repair is to mock/limit expensive discovery in the degradation path or make the test deterministic under timeout. |
| [#717](https://github.com/AmitabhainArunachala/dharma_swarm/pull/717) | `DocOps integrity gate`, `pytest (3.11)`, `pytest (3.12)` | Supersede/close preferred. If kept: refresh DocOps assertions/inventory, then register or remove stale manifest endpoint `/api/operator-coherence/report` so `tests/test_manifest_health.py::TestHealthChecks::test_api_endpoint_registered_for_real_route` passes. |
| [#718](https://github.com/AmitabhainArunachala/dharma_swarm/pull/718) | `DocOps integrity gate`, `Import-provenance - third-party declaration ratchet`, `pytest (3.11)`, `pytest (3.12)` | DocOps: refresh expired assertions and stale inventory. Import provenance: undeclared `markdown` import at `docs/research/verified_nature_house/hub/site/build.py:64`; declare a real dependency and update baseline or remove the import. Pytest: register or remove `/api/operator-coherence/report` manifest entry. |
| [#719](https://github.com/AmitabhainArunachala/dharma_swarm/pull/719) | `DocOps integrity gate`, `pytest (3.11)`, `pytest (3.12)` | Refresh DocOps assertions/inventory. Pytest root cause is the same manifest-health failure: `/api/operator-coherence/report` has no matching mounted app route. Register the route or remove/update the manifest entry. |
| [#720](https://github.com/AmitabhainArunachala/dharma_swarm/pull/720) | `Quality ratchet - repo-wide fitness function`, `pytest (3.11)`, `pytest (3.12)` | Supersede/close preferred. If kept: repair the same `modules_over_500_lines` 207 -> 208 regression driving quality-ratchet and pytest ratchet failures. |
| [#722](https://github.com/AmitabhainArunachala/dharma_swarm/pull/722) | `Quality ratchet - repo-wide fitness function`, `pytest (3.11)`, `pytest (3.12)` | Supersede/close preferred. If kept: repair the same `modules_over_500_lines` 207 -> 208 regression driving quality-ratchet and pytest ratchet failures. |

## Gate Notes

Repeated failing gates:

| Gate | Affected PRs | First-pass root cause |
| --- | --- | --- |
| DocOps integrity | #715, #717, #718, #719 | Assertions expired on 2026-06-26 from `verified_at=2026-06-12`; manifest counts and `docs/docops/AUTO_INVENTORY.md` are stale on affected branches. |
| Import provenance | #718 | Undeclared `markdown` import in VNH hub site build script. |
| Quality ratchet regression | #710, #720, #722 | `modules_over_500_lines` moved 207 -> 208. |
| Quality ratchet workflow provisioning | #713 | Branch workflow invokes ratchet without `ruff` available. |
| Manifest health pytest | #717, #718, #719 | `/api/operator-coherence/report` listed as an API endpoint without a mounted route. |
| Sleep-cycle timeout pytest | #708, #716 | `tests/test_sleep_cycle.py::test_graceful_degradation` exceeds 30 seconds. |
| Bootstrap loop closure pytest | #708 | `tests/test_bootstrap_loops.py::test_full_loop_closure` leaves task `RUNNING` instead of `COMPLETED` on Python 3.12. |

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
