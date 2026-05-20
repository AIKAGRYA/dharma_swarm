# Active Track Evidence

Generated: 2026-05-20T08:05:58+00:00
Track: `cockpit-control-surface-2026-05`
Prerequisites: **OK**
Completion: **0/4**
Shippable: **no**

## Criteria

- ✓ `control_surface_envelope_exists` (file_contains) — pattern 'class ControlSurfaceEnvelope' found in dharma_swarm/operator_core/control_surface_models.py
- ✓ `display_hints_exists` (file_contains) — pattern 'DisplayHints' found in dharma_swarm/operator_core/control_surface_models.py
- ✓ `cockpit_dashboard_page_exists` (file_exists) — dashboard/src/app/dashboard/control-surface/page.tsx present
- ✓ `world_radar_wired` (file_exists) — dharma_swarm/world_radar/__init__.py present
- ✓ `control_surface_router_registered` (file_contains) — pattern 'control_surface' found in api/main.py
- ✓ `contract_tests_present` (file_exists) — tests/test_control_surface.py present
- ✓ `pr_307_merged` (pr_merged) — PR #307: gh query failed, skipped
- ✓ `pr_244_merged` (pr_merged) — PR #244: gh query failed, skipped
- ✗ `control_surface_adr_published` (file_exists) — docs/architecture/CONTROL_SURFACE.md MISSING
- ✗ `ledger_watcher_envelope_aware` (file_contains) — pattern 'ControlSurfaceEnvelope|envelope' NOT FOUND in dharma_swarm/operator_brief/watchdog.py
- ✗ `manifest_health_snapshot_archived` (file_exists) — reports/state/control_surface_manifest_health_snapshot.md MISSING
- ✗ `next_seam_adr_drafted` (file_exists) — docs/architecture/adr/0001-next-seam-candidate.md MISSING

## Findings

- **INFO** `track-in-progress`: 0/4 completion criteria pass. Track 'cockpit-control-surface-2026-05' is in progress.
