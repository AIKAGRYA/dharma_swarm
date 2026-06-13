#!/usr/bin/env bash
# worktree_cleanup_2026-06-10.sh
# Executes the triage plan in reports/worktree_triage_report_2026-06-10.md
# Idempotent. NEVER touches GOLD/UNSURE paths, the primary repo, or dharma_swarm_live.
# Provably-removable: plain `git worktree remove` (no --force; failures logged + skipped).
# BUNDLE: tar uncommitted files -> git bundle HEAD -> worktree remove --force.
set -u

MAIN_REPO="/Users/dhyana/dharma_swarm"
COMPOST="$HOME/.claude/cabinet/_compost/worktrees_2026-06-10"
LOG="$COMPOST/cleanup.log"

echo "============================================================"
echo "WARNING: the dharma_swarm daemon's cwd is /Users/dhyana/dharma_swarm."
echo "This script never touches $MAIN_REPO or /Users/dhyana/dharma_swarm_live,"
echo "but confirm no running process (dgc daemon, marathon, codex lanes) has its"
echo "cwd inside any path below before proceeding. Check: lsof +D <path> / dgc status"
echo "============================================================"

mkdir -p "$COMPOST"
touch "$LOG"
log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"; }

# ---------------------------------------------------------------
# DENY-LIST: GOLD + UNSURE + protected. The script refuses to act
# on these even if they appear in an action list by mistake.
# ---------------------------------------------------------------
DENY=(
  "/Users/dhyana/dharma_swarm"
  "/Users/dhyana/dharma_swarm_live"
  # GOLD
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_memory_kernel_preflight_20260516"
  "/Users/dhyana/dharma_swarm_cashclaw"
  "/Users/dhyana/dharma_swarm_opus_identity"
  "/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v1"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr323"
  "/Users/dhyana/dharma_capital_lab"
  "/Users/dhyana/.qwen/worktrees/holon-agent"
  "/Users/dhyana/dharma_swarm_governed_recursive_proof"
  "/Users/dhyana/worktrees/dharma_swarm_honest_spine_v2"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_recursive_evolution_20260516"
  "/Users/dhyana/dharma_swarm_substrate_spec"
  # UNSURE
  "/Users/dhyana/worktrees/dharma_swarm_spine_slice_b"
  "/Users/dhyana/dharma_swarm_main_cutover"
  "/Users/dhyana/dharma_swarm_pr_review_control"
)

is_denied() {
  local p="$1"
  for d in "${DENY[@]}"; do
    [ "$p" = "$d" ] && return 0
  done
  return 1
}

# ---------------------------------------------------------------
# PROVABLY REMOVABLE (dirty=0, untracked=0, head_on_github=true)
# ---------------------------------------------------------------
PROVABLE=(
  "/private/tmp/chetana-restoration"
  "/Users/dhyana/.dharma/codex_lanes/worktrees/cleanup-audit"
  "/Users/dhyana/.dharma/marathon/repo"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_memory_kernel_hardening_20260523"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_recursive_discovery"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr314"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr320"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr324"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr326"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr327"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr328"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr338"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr341"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_route_witness_main"
  "/Users/dhyana/dharma_swarm_brakes"
  "/Users/dhyana/dharma_swarm_budget_fix"
  "/Users/dhyana/dharma_swarm_codex_mention_main"
  "/Users/dhyana/dharma_swarm_core_scan"
  "/Users/dhyana/dharma_swarm_dgmd_smoke_20260514T045353Z"
  "/Users/dhyana/dharma_swarm_integrate_chetana"
  "/Users/dhyana/dharma_swarm_lak_e2e"
  "/Users/dhyana/dharma_swarm_main_verify"
  "/Users/dhyana/dharma_swarm_pr319"
  "/Users/dhyana/dharma_swarm_tcs_heartbeat"
  "/Users/dhyana/dharma_swarm_trace_attractor_causal_spine"
  # "/Users/dhyana/ds_ws4"  — EXCLUDED: PR #558 / WS4b follow-up work planned here (operator memory 2026-06-09)
  "/Users/dhyana/promotion_worktrees/dharma_swarm_go_g06_local_model_inventory"
  "/Users/dhyana/promotion_worktrees/dharma_swarm_runtime_projector"
  "/Users/dhyana/worktrees/dharma_swarm_spine_slice_a"
)

# ---------------------------------------------------------------
# BUNDLE (preserve uncommitted files + full bundle, then remove)
# format: "path|detached_head_on_remote(yes/no)"
# bundle is skipped only when detached AND head already on a remote
# ---------------------------------------------------------------
BUNDLE=(
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_codex_lane_runner|no"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_interop_fleet|no"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_memory_knowledge|no"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr325|no"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_root_governance_residue|no"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_viz_invariant|no"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_pr_queue_probe2_20260524|no"
  "/Users/dhyana/dharma_swarm-go-ingest-spine-clean|no"
  "/Users/dhyana/dharma_swarm_boardstore_spec|no"
  "/Users/dhyana/worktrees/dharma_swarm_spine_slice_c|no"
  "/Users/dhyana/promotion_worktrees/dharma_swarm_mask_prereg|no"
)

removed_count=0
bundled_count=0
skipped_count=0
failed_count=0

# ---------------------------------------------------------------
# Pass 1: provably removable — try plain remove, never --force
# ---------------------------------------------------------------
log "=== PASS 1: provably-removable (${#PROVABLE[@]} candidates, no --force) ==="
for wt in "${PROVABLE[@]}"; do
  if is_denied "$wt"; then
    log "DENY-LIST HIT (refusing): $wt"
    failed_count=$((failed_count+1))
    continue
  fi
  if [ ! -d "$wt" ]; then
    log "already gone, skipping: $wt"
    skipped_count=$((skipped_count+1))
    continue
  fi
  if git -C "$MAIN_REPO" worktree remove "$wt" >>"$LOG" 2>&1; then
    log "REMOVED: $wt"
    removed_count=$((removed_count+1))
  else
    log "FAILED (left in place, no --force in this pass): $wt"
    failed_count=$((failed_count+1))
  fi
done

# ---------------------------------------------------------------
# Pass 2: BUNDLE — tar uncommitted, bundle HEAD, then force remove
# ---------------------------------------------------------------
log "=== PASS 2: bundle-then-remove (${#BUNDLE[@]} candidates) ==="
for entry in "${BUNDLE[@]}"; do
  wt="${entry%%|*}"
  detached_on_remote="${entry##*|}"
  name="$(basename "$wt")"

  if is_denied "$wt"; then
    log "DENY-LIST HIT (refusing): $wt"
    failed_count=$((failed_count+1))
    continue
  fi
  if [ ! -d "$wt" ]; then
    log "already gone, skipping: $wt"
    skipped_count=$((skipped_count+1))
    continue
  fi

  # 2a. tar ONLY dirty + untracked files (if any)
  tarball="$COMPOST/${name}_uncommitted.tgz"
  if [ -f "$tarball" ]; then
    log "tar exists, skipping tar: $tarball"
  else
    # porcelain: strip 3-char status prefix; for renames keep the new path
    filelist="$(git -C "$wt" status --porcelain 2>>"$LOG" | sed -e 's/^...//' -e 's/^.* -> //')"
    if [ -n "$filelist" ]; then
      if printf '%s\n' "$filelist" | tar -czf "$tarball" -C "$wt" -T - >>"$LOG" 2>&1; then
        log "TARRED uncommitted -> $tarball"
      else
        log "TAR FAILED, skipping removal of: $wt"
        failed_count=$((failed_count+1))
        continue
      fi
    else
      log "no dirty/untracked files, no tar needed: $wt"
    fi
  fi

  # 2b. bundle full history at HEAD (skip only if detached + already on remote)
  bundlefile="$COMPOST/${name}.bundle"
  if [ "$detached_on_remote" = "yes" ]; then
    log "detached HEAD already on remote, skipping bundle: $wt"
  elif [ -f "$bundlefile" ]; then
    log "bundle exists, skipping bundle: $bundlefile"
  else
    if git -C "$wt" bundle create "$bundlefile" HEAD >>"$LOG" 2>&1; then
      log "BUNDLED -> $bundlefile"
    else
      log "BUNDLE FAILED, skipping removal of: $wt"
      failed_count=$((failed_count+1))
      continue
    fi
  fi

  # 2c. remove (force OK — uncommitted content + history are preserved above)
  if git -C "$MAIN_REPO" worktree remove --force "$wt" >>"$LOG" 2>&1; then
    log "REMOVED (after preservation): $wt"
    bundled_count=$((bundled_count+1))
  else
    log "REMOVE FAILED (preservation artifacts kept): $wt"
    failed_count=$((failed_count+1))
  fi
done

# tidy stale administrative entries for worktrees whose dirs are gone
git -C "$MAIN_REPO" worktree prune >>"$LOG" 2>&1 || true

echo ""
echo "================= CLEANUP SUMMARY ================="
echo "provably-removable removed : $removed_count"
echo "bundled+removed            : $bundled_count"
echo "skipped (already gone/done): $skipped_count"
echo "failed/refused (see log)   : $failed_count"
echo "compost dir                : $COMPOST"
echo "log                        : $LOG"
echo -n "worktrees remaining        : "
git -C "$MAIN_REPO" worktree list | wc -l
