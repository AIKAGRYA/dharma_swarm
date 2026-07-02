# Audit 2026-07-01 Remediation

Date: 2026-07-01 JST

Source audit: `docs/governance/AUDIT_2026-07-01.md`

## Fixed Locally

- Vector-store fallback guard verified: `tests/test_vector_store.py` covers large fallback scan refusal and hybrid degradation.
- Runtime-spine track no longer renders `SHIPPABLE` at 70/100: `hardening_score_at_least_75` is now a completion criterion.
- `BR-007` reopened in `docs/state/BROKEN_REGISTER.md`; the historical closed entry remains as superseded history.
- Algedonic triage reactivated:
  - repo handler: `dharma_swarm.cron_runner` supports `handler: algedonic_triage`;
  - repo schedule: `cron_jobs.json` has enabled 15-minute triage;
  - live schedule: `~/.dharma/cron/jobs.json` has enabled 15-minute triage, with backup `~/.dharma/cron/jobs.json.bak-20260701-algedonic-triage`;
  - cursor drained manually: 481 pending signals, then 2 additional signals, triaged to `~/.dharma/triage/2026-06-30.md`;
  - `com.dharma.cron-daemon` was restarted after the handler patch so the live process imports the new dispatch table;
  - live scheduler status after the repaired run: `last_status=ok`, `last_error=null`, `last_run_at=2026-06-30T22:55:00Z`, next run `2026-06-30T23:10:00Z`.
- AgentRunner self-editing memory is wired through the production `SwarmManager.spawn_agent` path.
- Stale docs corrected:
  - test-suite count/runtime note added to `CLAUDE.md`;
  - `INTERFACE_MISMATCH_MAP.md` and `CLAUDE.md` now agree that NEW-14 remains an open BLOCKER;
  - `docs/ops/PR_REVIEW_CONTROL.md` now describes the current Merge Master Mike router and separates it from official `@claude` GitHub app credentials.
- Fitness property fixture updated for the full current `FitnessScore` dimensions, including `swabhaav_alignment` and `economic_value`.

## Still Blocked Or Intentionally Not Mutated

- `@claude` GitHub Actions routing remains credential-blocked. No Anthropic/Claude repository secret or GitHub app installation was created by this pass.
- `BR-007` data repair remains blocked on choosing the canonical `ontology.db` and a backup/merge plan. `store_sync` was not enabled in live cron state.
- SWE-bench Forge consolidation remains a separate multi-worktree initiative; no destructive worktree or branch cleanup was performed.
- Full test-suite runtime remains too long for this remediation pass; focused tests were run instead.

## Verification Run

- `pytest -q tests/test_vector_store.py`
- `pytest -q tests/properties/test_fitness_properties.py tests/test_track_portfolio.py::test_hardening_score_at_least_blocks_flat_score tests/test_track_portfolio.py::test_hardening_score_at_least_passes_when_threshold_met`
- `pytest -q tests/test_cron_runner.py::test_run_cron_job_dispatches_algedonic_triage tests/test_swarm.py::test_spawn_agent_preserves_constitutional_routing_metadata`
- `pytest -q tests/test_track_portfolio.py`
- `pytest -q tests/test_active_track_governance.py::test_check_track_status_runs`
- `python3 scripts/governance/render_active_track_includes.py --check`
- `python3 scripts/governance/check_track_status.py`
- `./.venv/bin/python -c 'from dharma_swarm.cron_runner import execute_cron_job; r=execute_cron_job({"handler":"algedonic_triage","timeout_sec":60}); print(r.status.value); print(r.output)'`
- `launchctl kickstart -k gui/501/com.dharma.cron-daemon`
- `./.venv/bin/python -c 'from dharma_swarm import cron_scheduler; from dharma_swarm.cron_runner import run_cron_job; jobs=cron_scheduler.load_jobs(); job=next(j for j in jobs if j.get("id")=="algedonic_triage"); success,out,err=run_cron_job(job); cron_scheduler.save_job_output(job["id"], out); cron_scheduler.mark_job_run(job["id"], success, err); print(success, out, err)'`
