# Active Track Evidence

Generated: 2026-05-20T12:16:15+00:00
Track: `cockpit-control-surface-2026-05`
Prerequisites: **OK**
Completion: **4/4**
Shippable: **YES**

## Criteria

- ✓ `control_surface_envelope_exists` (file_contains) — pattern 'class ControlSurfaceEnvelope' found in dharma_swarm/operator_core/control_surface_models.py
- ✓ `display_hints_exists` (file_contains) — pattern 'DisplayHints' found in dharma_swarm/operator_core/control_surface_models.py
- ✓ `cockpit_dashboard_page_exists` (file_exists) — dashboard/src/app/dashboard/control-surface/page.tsx present
- ✓ `world_radar_wired` (file_exists) — dharma_swarm/world_radar/__init__.py present
- ✓ `control_surface_router_registered` (file_contains) — pattern 'control_surface' found in api/main.py
- ✓ `contract_tests_present` (file_exists) — tests/test_control_surface.py present
- ✓ `pr_307_merged` (pr_merged) — PR #307: state=MERGED mergedAt=2026-05-18T14:04:59Z
- ✓ `pr_244_merged` (pr_merged) — PR #244: state=MERGED mergedAt=2026-05-13T14:16:33Z
- ✓ `control_surface_adr_published` (file_exists) — docs/architecture/CONTROL_SURFACE.md present
- ✓ `ledger_watcher_envelope_aware` (file_contains) — pattern 'ControlSurfaceEnvelope|envelope' found in dharma_swarm/operator_brief/watchdog.py
- ✓ `manifest_health_snapshot_archived` (file_exists) — reports/state/control_surface_manifest_health_snapshot.md present
- ✓ `next_seam_adr_drafted` (file_exists) — docs/architecture/adr/0001-next-seam-candidate.md present

## Findings

- **INFO** `track-shippable`: All 4 completion criteria pass. Track 'cockpit-control-surface-2026-05' is SHIPPABLE — close it and declare the next active track.
