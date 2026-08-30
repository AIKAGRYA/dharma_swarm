#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(
  unset CDPATH
  cd -- "$(dirname -- "$0")"
  pwd -P
)"
PACKAGE_DIR="$(
  unset CDPATH
  cd -- "$SCRIPT_DIR/.."
  pwd -P
)"
REPO_ROOT="$(
  unset CDPATH
  cd -- "$PACKAGE_DIR/../.."
  pwd -P
)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALLER="$PACKAGE_DIR/install.sh"
UNINSTALLER="$PACKAGE_DIR/uninstall.sh"
RECONCILER="$PACKAGE_DIR/scripts/reconcile-meghadharma-docker-limits.sh"

bash -n "$INSTALLER"
bash -n "$UNINSTALLER"
bash -n "$RECONCILER"
if command -v shellcheck >/dev/null; then
  shellcheck "$INSTALLER" "$UNINSTALLER" "$RECONCILER"
fi

for host in rushabdev agni meghadharma; do
  output="$(PYTHON_BIN="$PYTHON_BIN" "$PACKAGE_DIR/install.sh" --host "$host" --dry-run)"
  grep -Fq -- "--verify-host" <<<"$output"
  grep -Fq -- "restart and self-test guard" <<<"$output"
  "$PACKAGE_DIR/uninstall.sh" --host "$host" --dry-run >/dev/null
  "$PYTHON_BIN" "$REPO_ROOT/scripts/ops/vps_resource_guard.py" \
    --config "$PACKAGE_DIR/configs/$host.toml" --validate-config >/dev/null
done

rush_output="$(PYTHON_BIN="$PYTHON_BIN" "$PACKAGE_DIR/install.sh" --host rushabdev --dry-run)"
grep -Fq 'ollama.service MemoryHigh=640M MemoryMax=800M' <<<"$rush_output"
grep -Fq 'hermes-gateway.service MemoryHigh=800M MemoryMax=1200M' <<<"$rush_output"
grep -Fq 'openclaw-gateway.service MemoryHigh=512M MemoryMax=768M' <<<"$rush_output"

agni_output="$(PYTHON_BIN="$PYTHON_BIN" "$PACKAGE_DIR/install.sh" --host agni --dry-run)"
grep -Fq 'ollama.service MemoryHigh=4G MemoryMax=5G' <<<"$agni_output"
grep -Fq 'hermes-gateway.service MemoryHigh=1500M MemoryMax=2G' <<<"$agni_output"

megha_output="$(PYTHON_BIN="$PYTHON_BIN" "$PACKAGE_DIR/install.sh" --host meghadharma --dry-run)"
grep -Fq 'dharma-command-backend' <<<"$megha_output"
grep -Fq 'hermes' <<<"$megha_output"
grep -Fq 'dharma-swarm' <<<"$megha_output"
grep -Fq 'dharma-command-edge' <<<"$megha_output"
grep -Fq 'vps-resource-guard-docker-reconcile.timer' <<<"$megha_output"
grep -Fq 'scope InvocationID' <<<"$megha_output"
[[ "$(grep -Fc 'MemorySwapMax=' <<<"$megha_output")" == 4 ]]
grep -Fq 'dharma-command-backend' <<<"$megha_output"
grep -Fq 'MemorySwapMax=640M' <<<"$megha_output"

if rg -q 'docker (container )?update' \
  "$INSTALLER" "$UNINSTALLER" "$RECONCILER"; then
  echo "Unexpected non-invertible Docker HostConfig mutation" >&2
  exit 1
fi
grep -Fq 'OnUnitActiveSec=5s' \
  "$PACKAGE_DIR/systemd/vps-resource-guard-docker-reconcile.timer"
if find "$PACKAGE_DIR" -type f -name 'docker-compose.override.yml' | grep -q . || \
  rg -q 'mem_limit:|mem_reservation:|memswap_limit:|docker-compose\.override' \
    "$PACKAGE_DIR/install.sh" "$PACKAGE_DIR/uninstall.sh" \
    "$PACKAGE_DIR/README.md" \
    "$RECONCILER"; then
  echo "Unexpected non-invertible Compose/HostConfig memory policy" >&2
  exit 1
fi
grep -Fq 'StateDirectory=vps-resource-guard' \
  "$PACKAGE_DIR/systemd/vps-resource-guard-docker-reconcile.service"
grep -Fq 'InvocationID' \
  "$RECONCILER"
grep -Fq "sync -f \"\$temporary\"" \
  "$RECONCILER"
grep -Fq 'Legacy Compose-managing guard detected' "$PACKAGE_DIR/install.sh"
grep -Fq -- '--check-baselines' "$PACKAGE_DIR/uninstall.sh"
grep -Fq -- '--restore-current' "$PACKAGE_DIR/uninstall.sh"
if rg -q 'not applying stale|container ID is unchanged' "$PACKAGE_DIR/uninstall.sh"; then
  echo "Unexpected skip-on-stale-identity uninstall behavior" >&2
  exit 1
fi

# A restart is never part of ordinary reconciliation. The sole restart call is
# confined to ambiguous post-mutation recovery and must address the validated
# full Docker ID, never the mutable container name.
grep -Fq 'recover_ambiguous_mutation()' "$RECONCILER"
grep -Fq 'reason=identity-ambiguous-after-mutation' "$RECONCILER"
grep -Fq "docker restart --timeout 10 -- \"\$container_id\"" "$RECONCILER"
grep -Fq 'status=recovered-by-exact-id-restart' "$RECONCILER"
grep -Fq 'arm_mutation_quarantine()' "$RECONCILER"
grep -Fq 'recover_pending_quarantines' "$RECONCILER"
grep -Fq 'reason=pending-mutation-quarantine' "$RECONCILER"
grep -Fq 'reason=baseline-restore-readback-mismatch' "$RECONCILER"
grep -Fq 'reason=pending-quarantine-read-only-check' "$RECONCILER"
grep -Fq 'status=retired-non-live' "$RECONCILER"
grep -Fq 'status=skipped-pending-quarantine' "$RECONCILER"
grep -Fq 'RECOVERY_RETRY_SECONDS=300' "$RECONCILER"
grep -Fq 'recovery_cooldown_allows()' "$RECONCILER"
grep -Fq 'arm_automatic_recovery_cooldown()' "$RECONCILER"
grep -Fq 'attempt_epoch=' "$RECONCILER"
grep -Fq 'status=backoff' "$RECONCILER"
grep -Fq 'status=cooldown-armed' "$RECONCILER"
[[ "$(rg -c 'recovery_cooldown_allows "\$container" "\$container_id"' \
  "$RECONCILER")" == 1 ]]
cooldown_block="$(sed -n \
  '/^arm_automatic_recovery_cooldown() {/,/^audit_recovery_cooldowns() {/p' \
  "$RECONCILER")"
cooldown_temp_sync="$(grep -nF 'sync -f "$temporary"' <<<"$cooldown_block")"
cooldown_move="$(grep -nF 'mv -- "$temporary" "$path"' <<<"$cooldown_block")"
cooldown_dir_sync="$(grep -nF 'sync -f "$BASELINE_DIR"' <<<"$cooldown_block")"
cooldown_temp_sync="${cooldown_temp_sync%%:*}"
cooldown_move="${cooldown_move%%:*}"
cooldown_dir_sync="${cooldown_dir_sync%%:*}"
((cooldown_temp_sync < cooldown_move && cooldown_move < cooldown_dir_sync))
cooldown_gate_function="$(sed -n \
  '/^recovery_cooldown_allows() {/,/^}/p' "$RECONCILER")"
cooldown_test_dir="$(mktemp -d)"
trap 'rm -r -- "$cooldown_test_dir"' EXIT
(
  MODE=reconcile
  RECOVERY_RETRY_SECONDS=300
  BASELINE_DIR="$cooldown_test_dir"
  cooldown_record_id="$(printf 'a%.0s' {1..64})"
  cooldown_record_epoch="$(date +%s)"
  requested_same="$cooldown_record_id"
  requested_other="$(printf 'b%.0s' {1..64})"
  recovery_cooldown_path() { printf '%s/dharma-command-edge.recovery-cooldown\n' "$BASELINE_DIR"; }
  load_recovery_cooldown() {
    RECOVERY_COOLDOWN_CONTAINER=dharma-command-edge
    RECOVERY_COOLDOWN_CONTAINER_ID="$cooldown_record_id"
    RECOVERY_COOLDOWN_EPOCH="$cooldown_record_epoch"
  }
  sync() { :; }
  eval "$cooldown_gate_function"
  touch "$BASELINE_DIR/dharma-command-edge.recovery-cooldown"
  if recovery_cooldown_allows dharma-command-edge "$requested_same" test \
    >"$BASELINE_DIR/same.out" 2>&1; then
    echo "Fresh same-ID recovery cooldown must block a restart" >&2
    exit 1
  fi
  grep -Fq 'status=backoff' "$BASELINE_DIR/same.out"
  if recovery_cooldown_allows dharma-command-edge "$requested_other" test \
    >"$BASELINE_DIR/other.out" 2>&1; then
    echo "Per-name recovery cooldown must also block replacement-ID restart churn" >&2
    exit 1
  fi
  grep -Fq "prior_id=$cooldown_record_id" "$BASELINE_DIR/other.out"
  [[ -f "$BASELINE_DIR/dharma-command-edge.recovery-cooldown" ]]
  cooldown_record_epoch=0
  recovery_cooldown_allows dharma-command-edge "$requested_other" test \
    >"$BASELINE_DIR/expired.out" 2>&1
  grep -Fq 'status=cooldown-expired' "$BASELINE_DIR/expired.out"
  [[ ! -e "$BASELINE_DIR/dharma-command-edge.recovery-cooldown" ]]
)
rm -r -- "$cooldown_test_dir"
trap - EXIT
[[ "$(rg -c 'docker restart --timeout' "$RECONCILER")" == 1 ]]
if rg -q 'docker restart[^\n]*"\$container"' "$RECONCILER"; then
  echo "Ambiguity recovery must never restart by mutable container name" >&2
  exit 1
fi

# A captured baseline is retained for as long as that exact scope InvocationID
# remains active. Only a record whose incarnation is proven inactive is pruned.
if ! rg -Uq 'if record_scope_is_active "\$candidate_scope" "\$candidate_invocation"; then\n[[:space:]]+echo "event=docker-scope-baseline status=retained-active[^\n]*\n[[:space:]]+continue' "$RECONCILER"; then
  echo "Active Docker scope baselines must be retained" >&2
  exit 1
fi
grep -Fq 'status=pruned-inactive' "$RECONCILER"

# Interrupted durable-baseline writes cannot accumulate forever.
grep -Fq 'cleanup_orphan_temporaries()' "$RECONCILER"
grep -Fq 'status=orphan-temporaries-cleaned' "$RECONCILER"
[[ "$(grep -Fxc 'cleanup_orphan_temporaries' "$RECONCILER")" == 1 ]]

# Lifecycle safety must remain structural, not only an operator convention.
# An installer rollback stops both timer and oneshot so a process queued on the
# operation lock cannot run after files and baselines have been restored.
if ! rg -Uq 'if \[\[ "\$HOST_NAME" == meghadharma \]\]; then\n[[:space:]]+systemctl stop vps-resource-guard-docker-reconcile\.timer \\\n[[:space:]]+vps-resource-guard-docker-reconcile\.service' "$INSTALLER"; then
  echo "Installer rollback must stop the reconciler timer and service together" >&2
  exit 1
fi

# Scope inverses are physically inside the preinstall generation, so successful
# uninstall rotates both halves with one same-filesystem generation-root rename.
grep -Fq 'EVIDENCE_PREINSTALL_MOVED' "$UNINSTALLER"
grep -Fq "mv -- \"\$PREINSTALL_DIR\" \"\$EVIDENCE_DIR/preinstall\"" "$UNINSTALLER"
grep -Fq 'SCOPE_BASELINE_DIR="$STATE_DIR/preinstall/docker-scope-baselines"' "$INSTALLER"
grep -Fq 'SCOPE_BASELINE_DIR="$STATE_DIR/preinstall/docker-scope-baselines"' "$UNINSTALLER"
grep -Fq 'GENERATION_DIR="$STATE_DIR/preinstall"' "$RECONCILER"
grep -Fq 'BASELINE_DIR="$GENERATION_DIR/docker-scope-baselines"' "$RECONCILER"
if rg -q 'mv -- "\$SCOPE_BASELINE_DIR"' "$UNINSTALLER"; then
  echo "Scope baselines must rotate only within the atomic preinstall generation" >&2
  exit 1
fi

# Failed install rollback may reset baselines only after exact restoration
# succeeds; otherwise it retains the sole inverse for possible live caps.
if ! rg -Uq -- '--restore-current >/dev/null 2>&1; then\n[[:space:]]+rm -rf -- "\$SCOPE_BASELINE_DIR"' "$INSTALLER"; then
  echo "Install rollback must condition baseline reset on exact restore success" >&2
  exit 1
fi
grep -Fq 'preserving the active baseline generation' "$INSTALLER"

# Current managed bytes are never silently discarded by upgrade or uninstall;
# differing upgrade inputs and every uninstall-time current file are retained
# content-addressed inside the atomically rotated generation.
grep -Fq 'preserve_superseded_file()' "$INSTALLER"
grep -Fq 'preserve_uninstall_current_file()' "$UNINSTALLER"
grep -Fq 'evidence_root="$PREINSTALL_DIR/superseded-files"' "$INSTALLER"
grep -Fq 'evidence_root="$PREINSTALL_DIR/superseded-files"' "$UNINSTALLER"
grep -Fq 'ensure_private_evidence_directory()' "$INSTALLER"
grep -Fq 'ensure_private_evidence_directory()' "$UNINSTALLER"
grep -Fq 'Saved superseded-file evidence root is unsafe' "$UNINSTALLER"
grep -Fq 'sync -f "$PREINSTALL_DIR"' "$UNINSTALLER"

# Never unlink a coordination lock while FD 9 still owns its inode. Purge may
# clear corrupt state evidence, but the stable operation lock namespace stays.
if rg -q 'rm[^\n]*(operation\.lock|"?\$LOCK_FILE"?)' "$UNINSTALLER"; then
  echo "Purge must retain the stable operation lock inode" >&2
  exit 1
fi
grep -Fq 'Keep operation.lock and state.json.lock as stable inode namespaces' "$UNINSTALLER"
grep -Fq 'rm -f -- /var/lib/vps-resource-guard/state.json.corrupt' "$UNINSTALLER"

# Keep the operator-facing lifecycle contract aligned with these mechanisms.
grep -Fq 'Docker HostConfig memory fields remain untouched' "$PACKAGE_DIR/README.md"
grep -Fq 'Records for captured incarnations remain while' "$PACKAGE_DIR/README.md"
grep -Fq 'records are pruned only after the recorded scope' "$PACKAGE_DIR/README.md"
grep -Fq 'Interrupted-write temporary files are cleaned' "$PACKAGE_DIR/README.md"
grep -Fq 'Ordinary reconciliation does not restart containers' "$PACKAGE_DIR/README.md"
grep -Fq 'restart only the exact captured' "$PACKAGE_DIR/README.md"
grep -Fq 'every scope inverse together with one same-filesystem rename' "$PACKAGE_DIR/README.md"

grep -Fq -- '--self-test-targets' "$PACKAGE_DIR/systemd/vps-resource-guard-self-test.service"
if grep -Eq 'ExecReload=|ExecStartPre=' "$PACKAGE_DIR/systemd/vps-resource-guard.service"; then
  echo "Unexpected boot-time probe/reload in guard unit" >&2
  exit 1
fi
if rg -q 'user-0\.slice' "$PACKAGE_DIR/install.sh" "$PACKAGE_DIR/uninstall.sh"; then
  echo "Unexpected broad root-user slice control" >&2
  exit 1
fi

echo "installer contract checks passed"
