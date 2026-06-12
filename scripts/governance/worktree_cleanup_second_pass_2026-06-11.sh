#!/usr/bin/env bash
# worktree_cleanup_second_pass_2026-06-11.sh
# Executes the "Second pass 2026-06-11" plan in reports/worktree_triage_report_2026-06-10.md
# Idempotent. NEVER touches GOLD/UNSURE paths, the primary repo, dharma_swarm_live,
# ds_ws3, ds_ws4, or any ds_stitch_* path.
# BUNDLE: tar dirty+untracked files -> git bundle HEAD -> worktree remove --force.
set -u

MAIN_REPO="/Users/dhyana/dharma_swarm"
COMPOST="$HOME/.claude/cabinet/_compost/worktrees_2026-06-11"
LOG="$COMPOST/cleanup.log"

echo "============================================================"
echo "WARNING: the dharma_swarm daemon's cwd is /Users/dhyana/dharma_swarm."
echo "This script never touches $MAIN_REPO, /Users/dhyana/dharma_swarm_live,"
echo "ds_ws3, ds_ws4, or ds_stitch_* paths, but confirm no running process"
echo "(dgc daemon, marathon, codex lanes) has its cwd inside any path below"
echo "before proceeding. Check: lsof +D <path> / dgc status"
echo "============================================================"

mkdir -p "$COMPOST"
touch "$LOG"
log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"; }

# ---------------------------------------------------------------
# DENY-LIST: GOLD + UNSURE (both passes) + protected. The script
# refuses to act on these even if they appear in an action list
# by mistake. ds_stitch_* is prefix-matched in is_denied().
# ---------------------------------------------------------------
DENY=(
  # protected
  "/Users/dhyana/dharma_swarm"
  "/Users/dhyana/dharma_swarm_live"
  "/Users/dhyana/ds_ws3"
  "/Users/dhyana/ds_ws4"
  # GOLD — second pass 2026-06-11
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_identity"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_memory_kernel_preflight_20260516"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_proof_artifacts"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_recursive_evolution_20260516"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr323"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_route_witness"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_worker4_pr323_codeql"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_worker4_pr332_codeql"
  "/Users/dhyana/dharma_swarm_governed_memory_recursive_integration"
  "/Users/dhyana/dharma_swarm_opus_traverse"
  "/Users/dhyana/dharma_swarm_truth_spine"
  "/Users/dhyana/worktrees/chetana-wiki-verify"
  "/Users/dhyana/worktrees/dharma_swarm_kaizen_exec_loop_pr"
  "/Users/dhyana/worktrees/dharma_swarm_live_ops_cockpit_v2"
  # UNSURE — second pass 2026-06-11 (incl. world_radar_live: conflicting GOLD+BUNDLE verdicts)
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_pr_queue_probe_20260524"
  "/Users/dhyana/dharma_swarm_kaizen_review"
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_world_radar_live"
  # GOLD — carried over from first pass (2026-06-10)
  "/Users/dhyana/dharma_swarm_cashclaw"
  "/Users/dhyana/dharma_swarm_opus_identity"
  "/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v1"
  "/Users/dhyana/dharma_capital_lab"
  "/Users/dhyana/.qwen/worktrees/holon-agent"
  "/Users/dhyana/dharma_swarm_governed_recursive_proof"
  "/Users/dhyana/worktrees/dharma_swarm_honest_spine_v2"
  "/Users/dhyana/dharma_swarm_substrate_spec"
  # UNSURE — carried over from first pass (2026-06-10)
  "/Users/dhyana/worktrees/dharma_swarm_spine_slice_b"
  "/Users/dhyana/dharma_swarm_main_cutover"
  "/Users/dhyana/dharma_swarm_pr_review_control"
)

is_denied() {
  local p="$1"
  case "$p" in
    /Users/dhyana/ds_stitch_*) return 0 ;;
  esac
  for d in "${DENY[@]}"; do
    [ "$p" = "$d" ] && return 0
  done
  return 1
}

# ---------------------------------------------------------------
# BUNDLE (preserve uncommitted files + full bundle, then remove)
# format: "path|detached_head_on_remote(yes/no)"
# bundle is skipped only when detached AND head already on a remote
# ---------------------------------------------------------------
BUNDLE=(
  "/Users/dhyana/cleanup_worktrees/dharma_swarm_memory_kernel_default_context_20260523|no"
  "/Users/dhyana/dharma_swarm_action_authority_spec|no"
  "/Users/dhyana/dharma_swarm_cwt_v0|no"
  "/Users/dhyana/dharma_swarm_moltbook_research_wt|no"
  "/Users/dhyana/dharma_swarm_pr326|yes"
  "/Users/dhyana/dharma_swarm_pr_392|no"
  "/Users/dhyana/dharma_swarm_pr_398|no"
  "/Users/dhyana/dharma_swarm_pr_399|no"
  "/Users/dhyana/dharma_swarm_toolbelt_push|no"
  "/Users/dhyana/worktrees/dharma_swarm_live_ops_cockpit_v1|no"
  "/Users/dhyana/worktrees/dharma_swarm_live_ops_cockpit_v1_docops_fix|no"
  "/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2|yes"
)

bundled_count=0
skipped_count=0
failed_count=0

# ---------------------------------------------------------------
# BUNDLE pass: tar uncommitted, bundle HEAD, then force remove
# ---------------------------------------------------------------
log "=== SECOND PASS 2026-06-11: bundle-then-remove (${#BUNDLE[@]} candidates) ==="
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

  # 1. tar ONLY dirty + untracked files (if any)
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

  # 2. bundle full history at HEAD (skip only if detached + already on remote)
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

  # 3. remove (force OK — uncommitted content + history are preserved above)
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
echo "=========== SECOND PASS CLEANUP SUMMARY ==========="
echo "bundled+removed            : $bundled_count"
echo "skipped (already gone/done): $skipped_count"
echo "failed/refused (see log)   : $failed_count"
echo "compost dir                : $COMPOST"
echo "log                        : $LOG"
echo -n "worktrees remaining        : "
git -C "$MAIN_REPO" worktree list | wc -l
