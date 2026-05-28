# Onboarding Receipt Template

Use this before architecture, refactor, governance, runtime-spine, persistence, dashboard-truth, or hot-path work.

Fields to include in a PR body, planning doc, or agent handoff:

- ran_or_read_make_onboard
- date_utc
- branch
- head_sha
- active_track
- broken_register_top_items
- proposed_change_summary
- touched_hot_paths
- existing_owner_surface
- new_surface_needed
- why_existing_owner_is_insufficient
- anti_slop_rule_relevant
- active_surface_manifest_update_needed
- active_track_update_needed
- evidence_or_receipt_path
- proceed
- reason

Rule of thumb:

Name the existing owner before creating a new surface.

Check the existing guard runner before adding a new guard.

Declare RuntimeStateStore / EvidenceReceipt role before adding a new persistence path.

Produce this receipt before architecture or refactor proposals.
