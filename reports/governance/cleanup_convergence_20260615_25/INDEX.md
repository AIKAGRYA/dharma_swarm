# Dharma Swarm Cleanup Convergence Index

Generated: 2026-06-25 JST
Worktree: `/Users/dhyana/ds_cleanup_convergence_20260625`
Branch: `cleanup/convergence-20260615-25`
Initial baseline: `origin/main` at `a46522040cc6d4ec80cf9f1466a81c7dac33c616`
Deletion-recheck baseline: `origin/main` at `21ee18b365a7a0f4b22bb9b087a987973c6fdaa3`
Post-deletion baseline: `origin/main` at `240a92c6b12b390e429298dfb36661ed8af365a8`

## Purpose

This packet turns the June 15-25 local Dharma Swarm sprawl into one clinical
cleanup map. It does not merge dirty worktrees, prune branches, or claim source
packets are production-ready. Its job is to preserve the map, classify the work,
record the first operator-approved worktree deletion batch, and point each
keeper toward an active track, proposed track, operator surface, archive bucket,
or explicit decision bucket.

## Evidence Read

| Source | Current evidence |
|---|---|
| User task | `/Users/dhyana/.codex/attachments/27a5c7a8-1524-486a-8c5a-e86a8bc6bbac/pasted-text-1.txt` |
| Initial baseline | `git fetch origin main` completed; `origin/main` was `a46522040cc6d4ec80cf9f1466a81c7dac33c616` for the first packet pass |
| Deletion-recheck baseline | `origin/main` was refreshed to `21ee18b365a7a0f4b22bb9b087a987973c6fdaa3` before deletion readiness verdicts |
| Onboarding | `make onboard` ran in `/Users/dhyana/dharma_swarm` and in this convergence worktree |
| Worktree list | Initial packet inventory captured 19 registered worktrees; deletion recheck showed 20 registered worktrees including `/Users/dhyana/dharma_swarm_wt/render-on-demand`; post-deletion verification shows 15 registered worktrees |
| Preservation root | `/Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST` exists |
| Backup root | `/Users/dhyana/dharma_recover_backups` exists |
| Backup receipt | `receipts/BACKUP_RECEIPT.md` says bundles verified, 686 stable files checksum-verified, and archive copied to `agni` |
| Triangulation summary | `receipts/TRIANGULATION_SUMMARY.md` says preservation is no longer local-only and cleanup should classify before removal |
| Preservation table | `trees/tree_preservation_summary.tsv` covers 19 June 24 trees/clones |
| Read-only audit | `/private/tmp/dharma_swarm_readonly_audit_20260624_84785/CONSOLIDATED_REPORT.md` covers 19 trees and 1,098 unique at-risk file instances |
| Sprawl memory | `/Users/dhyana/.claude/projects/-Users-dhyana/memory/local-tree-sprawl-backup-2026-06-24.md` records corrected keeper/junk verdicts |
| PR truth checked | GitHub connector checked PR #648, #674, and #685 |
| Deletion readiness recheck | `DELETION_READINESS_RECHECK.md` refreshed current deletion candidates through four read-only passes, records the first approved worktree deletion batch, and prepares exact Tier C approval commands without running them |
| Publication status | PR #688 merged into `main` as `73113dbd0770c251ba5128ae16f496141c932fee`; this packet has a follow-up local receipt pending publication |

## Deliverables

- `worktree_inventory.tsv` - current and preserved status for each major worktree/clone.
- `keeper_matrix.md` - keeper packets, classes, evidence, and proposed landing route.
- `decision_log.md` - decisions made while building this convergence packet.
- `OPERATOR_MAP.md` - short operator-facing answer map.
- `PALANTIR_SEMANTIC_ONTOLOGY_META_SCRATCHPAD.md` - proposed-only ontology notes and typed object candidates.
- `DELETION_READINESS_RECHECK.md` - exact-path deletion readiness report, read-only addenda, executed first-batch deletion receipt, and next Tier C exact-path approval list.
- `CLOSEOUT.md` - final receipt for this convergence packet.

## Current High-Level Verdict

Preservation is verified enough to continue non-destructive cleanup planning.
The dirty work is not one coherent merge. It separates into a few real keeper
lanes and a lot of preserved-but-not-promoted output:

- A2A/NATS preflight is real active runtime substrate and needs its own rebase
  and PR lane.
- Reconciliation reports are real governance membrane material, but raw command
  dumps should stay archived.
- Helm closeout and terminal branch are real operator surface work, but need a
  live-use gate before landing.
- Cashclaw has a real revenue branch history, but the 714 preserved untracked
  June 24 files are generated run output and should not be promoted.
- The old independent clone is archive-only unless the operator explicitly
  revives the March autonomy line.
- Anti-slop promotion membrane has landed through PR #685 and is present on
  current `origin/main`.
- The clean cockpit extraction and PR #674 repair branches are already on main
  or superseded by merged PRs.

## Classification Taxonomy

Every worktree or packet in this convergence map is assigned exactly one class:

- `CANONICALIZE_NOW`
- `PORT_TO_TRACK`
- `DASHBOARD_OPERATOR_SURFACE`
- `GOVERNANCE_MEMBRANE`
- `ACTIVE_RUNTIME_SUBSTRATE`
- `REVENUE_OR_CAPITAL_EXPERIMENT`
- `ARCHIVE_ONLY`
- `GENERATED_REPORT_JUNK`
- `DUPLICATE_OR_SUPERSEDED`
- `NEEDS_OPERATOR_DECISION`

## Boundaries

- Only the five operator-approved `git worktree` cleanup commands were run.
- No Tier C `rm` command was run.
- No dirty worktree was merged wholesale.
- No source packet from another dirty worktree was copied into this convergence
  branch.
- Generated reports are treated as evidence or archive material, not as source
  code.
- "Done", "live", "shippable", and "closed" are used only where evidence
  supports that exact claim.
