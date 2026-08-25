#!/usr/bin/env bash
set -euo pipefail

EXPECTED_HOSTNAME=meghadharma-cloud
STATE_DIR=/var/lib/vps-resource-guard
GENERATION_DIR="$STATE_DIR/preinstall"
BASELINE_DIR="$GENERATION_DIR/docker-scope-baselines"
LOCK_FILE="$STATE_DIR/operation.lock"
HEADROOM_BYTES=134217728
CONTAINERS=(dharma-command-backend hermes dharma-swarm dharma-command-edge)
MEMORY_HIGH_BYTES=(2147483648 1572864000 805306368 402653184)
MEMORY_MAX_BYTES=(2684354560 2147483648 1073741824 536870912)
MEMORY_SWAP_MAX_BYTES=(671088640 805306368 268435456 201326592)
RECOVERY_RETRY_SECONDS=300

MODE=reconcile
case "${1:-}" in
  "") ;;
  --check-baselines) MODE=check ;;
  --restore-current) MODE=restore ;;
  *) echo "Usage: $0 [--check-baselines|--restore-current]" >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { echo "Too many arguments." >&2; exit 2; }

for command_name in chmod date docker flock hostname install mktemp mv readlink rm stat sync systemctl; do
  command -v "$command_name" >/dev/null || {
    echo "event=docker-scope-reconcile status=refused reason=missing-command command=$command_name" >&2
    exit 2
  }
done

actual_hostname="$(hostname)"
if [[ "$actual_hostname" != "$EXPECTED_HOSTNAME" ]]; then
  echo "event=docker-scope-reconcile status=refused reason=hostname-mismatch expected=$EXPECTED_HOSTNAME actual=$actual_hostname" >&2
  exit 2
fi

[[ ! -L "$STATE_DIR" ]] || {
  echo "event=docker-scope-reconcile status=refused reason=state-directory-symlink" >&2
  exit 2
}
if [[ "$MODE" == check ]]; then
  [[ -d "$STATE_DIR" ]] || {
    echo "event=docker-scope-reconcile status=refused reason=missing-state-directory-read-only-check" >&2
    exit 2
  }
else
  install -d -o root -g root -m 0700 "$STATE_DIR"
fi

if [[ "${VPS_RESOURCE_GUARD_LOCK_HELD:-0}" == 1 ]]; then
  lock_target="$(readlink "/proc/$$/fd/9" 2>/dev/null || true)"
  [[ "$lock_target" == "$LOCK_FILE" ]] || {
    echo "event=docker-scope-reconcile status=refused reason=invalid-inherited-lock" >&2
    exit 2
  }
else
  [[ ! -L "$LOCK_FILE" && ( ! -e "$LOCK_FILE" || -f "$LOCK_FILE" ) ]] || {
    echo "event=docker-scope-reconcile status=refused reason=invalid-lock-file" >&2
    exit 2
  }
  if [[ "$MODE" == check ]]; then
    [[ -f "$LOCK_FILE" ]] || {
      echo "event=docker-scope-reconcile status=refused reason=missing-lock-file-read-only-check" >&2
      exit 2
    }
    exec 9<>"$LOCK_FILE"
  else
    exec 9>"$LOCK_FILE"
  fi
fi
if [[ "$MODE" != check ]]; then chmod 0600 "$LOCK_FILE"; fi
lock_metadata="$(stat -c '%u:%g:%a' "$LOCK_FILE")"
[[ "$lock_metadata" == 0:0:600 ]] || {
  echo "event=docker-scope-reconcile status=refused reason=untrusted-lock-file metadata=$lock_metadata" >&2
  exit 2
}
flock -w 60 9 || {
  echo "event=docker-scope-reconcile status=refused reason=lock-timeout" >&2
  exit 1
}

[[ -d "$GENERATION_DIR" && ! -L "$GENERATION_DIR" ]] || {
  echo "event=docker-scope-reconcile status=refused reason=missing-or-invalid-generation" >&2
  exit 2
}
generation_metadata="$(stat -c '%u:%g:%a' "$GENERATION_DIR")"
[[ "$generation_metadata" == 0:0:700 ]] || {
  echo "event=docker-scope-reconcile status=refused reason=untrusted-generation metadata=$generation_metadata" >&2
  exit 2
}
[[ -f "$GENERATION_DIR/host" && ! -L "$GENERATION_DIR/host" ]] || {
  echo "event=docker-scope-reconcile status=refused reason=missing-generation-host" >&2
  exit 2
}
generation_host_metadata="$(stat -c '%u:%g:%a' "$GENERATION_DIR/host")"
[[ "$generation_host_metadata" == 0:0:600 && "$(<"$GENERATION_DIR/host")" == meghadharma ]] || {
  echo "event=docker-scope-reconcile status=refused reason=untrusted-generation-host" >&2
  exit 2
}

if [[ -e "$BASELINE_DIR" ]]; then
  [[ -d "$BASELINE_DIR" && ! -L "$BASELINE_DIR" ]] || {
    echo "event=docker-scope-reconcile status=refused reason=invalid-baseline-directory" >&2
    exit 2
  }
  baseline_directory_metadata="$(stat -c '%u:%g:%a' "$BASELINE_DIR")"
  [[ "$baseline_directory_metadata" == 0:0:700 ]] || {
    echo "event=docker-scope-reconcile status=refused reason=untrusted-baseline-directory metadata=$baseline_directory_metadata" >&2
    exit 2
  }
elif [[ "$MODE" == reconcile ]]; then
  install -d -o root -g root -m 0700 "$BASELINE_DIR"
  sync -f "$BASELINE_DIR"
else
  echo "event=docker-scope-reconcile status=refused reason=missing-baseline-directory" >&2
  exit 2
fi

CURRENT_BASELINE_TEMP=""
cleanup_current_temp() {
  local exit_status=$?
  if [[ -n "$CURRENT_BASELINE_TEMP" &&
        "$CURRENT_BASELINE_TEMP" == "$BASELINE_DIR"/.* &&
        -f "$CURRENT_BASELINE_TEMP" &&
        ! -L "$CURRENT_BASELINE_TEMP" ]]; then
    rm -f -- "$CURRENT_BASELINE_TEMP" || true
    sync -f "$BASELINE_DIR" 2>/dev/null || true
  fi
  exit "$exit_status"
}
trap cleanup_current_temp EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

valid_size() {
  [[ "$1" =~ ^(0|[1-9][0-9]*|infinity)$ ]]
}

is_allowlisted_container() {
  local expected
  for expected in "${CONTAINERS[@]}"; do
    [[ "$1" == "$expected" ]] && return 0
  done
  return 1
}

baseline_path() {
  printf '%s/%s.%s.%s.baseline\n' "$BASELINE_DIR" "$1" "$2" "$3"
}

quarantine_path() {
  printf '%s/%s.%s.%s.mutation-quarantine\n' "$BASELINE_DIR" "$1" "$2" "$3"
}

recovery_cooldown_path() {
  printf '%s/%s.recovery-cooldown\n' "$BASELINE_DIR" "$1"
}

load_record() {
  local path="$1" metadata expected_path
  local -a record_lines=()

  [[ -f "$path" && ! -L "$path" ]] || return 1
  metadata="$(stat -c '%u:%g:%a' "$path")"
  [[ "$metadata" == 0:0:600 ]] || return 1
  mapfile -t record_lines <"$path"
  [[ ${#record_lines[@]} -eq 8 ]] || return 1
  [[ "${record_lines[0]}" == version=1 ]] || return 1
  [[ "${record_lines[1]}" == container=* ]] || return 1
  [[ "${record_lines[2]}" == container_id=* ]] || return 1
  [[ "${record_lines[3]}" == invocation_id=* ]] || return 1
  [[ "${record_lines[4]}" == scope=* ]] || return 1
  [[ "${record_lines[5]}" == memory_high=* ]] || return 1
  [[ "${record_lines[6]}" == memory_max=* ]] || return 1
  [[ "${record_lines[7]}" == memory_swap_max=* ]] || return 1

  RECORD_CONTAINER="${record_lines[1]#container=}"
  RECORD_CONTAINER_ID="${record_lines[2]#container_id=}"
  RECORD_INVOCATION_ID="${record_lines[3]#invocation_id=}"
  RECORD_SCOPE="${record_lines[4]#scope=}"
  RECORD_HIGH="${record_lines[5]#memory_high=}"
  RECORD_MAX="${record_lines[6]#memory_max=}"
  RECORD_SWAP_MAX="${record_lines[7]#memory_swap_max=}"

  is_allowlisted_container "$RECORD_CONTAINER" || return 1
  [[ "$RECORD_CONTAINER_ID" =~ ^[0-9a-f]{64}$ ]] || return 1
  [[ "$RECORD_INVOCATION_ID" =~ ^[0-9a-f]{32}$ ]] || return 1
  [[ "$RECORD_SCOPE" == "docker-${RECORD_CONTAINER_ID}.scope" ]] || return 1
  valid_size "$RECORD_HIGH" || return 1
  valid_size "$RECORD_MAX" || return 1
  valid_size "$RECORD_SWAP_MAX" || return 1
  expected_path="$(baseline_path "$RECORD_CONTAINER" "$RECORD_CONTAINER_ID" "$RECORD_INVOCATION_ID")"
  [[ "$path" == "$expected_path" ]]
}

load_baseline() {
  local container="$1" container_id="$2" invocation_id="$3" scope="$4" path
  path="$(baseline_path "$container" "$container_id" "$invocation_id")"
  load_record "$path" || return 1
  [[ "$RECORD_CONTAINER" == "$container" &&
     "$RECORD_CONTAINER_ID" == "$container_id" &&
     "$RECORD_INVOCATION_ID" == "$invocation_id" &&
     "$RECORD_SCOPE" == "$scope" ]] || return 1
  BASELINE_HIGH="$RECORD_HIGH"
  BASELINE_MAX="$RECORD_MAX"
  BASELINE_SWAP_MAX="$RECORD_SWAP_MAX"
}

load_mutation_quarantine() {
  local path="$1" metadata expected_path
  local -a record_lines=()

  [[ -f "$path" && ! -L "$path" ]] || return 1
  metadata="$(stat -c '%u:%g:%a' "$path")"
  [[ "$metadata" == 0:0:600 ]] || return 1
  mapfile -t record_lines <"$path"
  [[ ${#record_lines[@]} -eq 8 ]] || return 1
  [[ "${record_lines[0]}" == version=1 ]] || return 1
  [[ "${record_lines[1]}" == container=* ]] || return 1
  [[ "${record_lines[2]}" == container_id=* ]] || return 1
  [[ "${record_lines[3]}" == invocation_id=* ]] || return 1
  [[ "${record_lines[4]}" == scope=* ]] || return 1
  [[ "${record_lines[5]}" == memory_high=* ]] || return 1
  [[ "${record_lines[6]}" == memory_max=* ]] || return 1
  [[ "${record_lines[7]}" == memory_swap_max=* ]] || return 1

  QUARANTINE_CONTAINER="${record_lines[1]#container=}"
  QUARANTINE_CONTAINER_ID="${record_lines[2]#container_id=}"
  QUARANTINE_INVOCATION_ID="${record_lines[3]#invocation_id=}"
  QUARANTINE_SCOPE="${record_lines[4]#scope=}"
  QUARANTINE_HIGH="${record_lines[5]#memory_high=}"
  QUARANTINE_MAX="${record_lines[6]#memory_max=}"
  QUARANTINE_SWAP_MAX="${record_lines[7]#memory_swap_max=}"

  is_allowlisted_container "$QUARANTINE_CONTAINER" || return 1
  [[ "$QUARANTINE_CONTAINER_ID" =~ ^[0-9a-f]{64}$ ]] || return 1
  [[ "$QUARANTINE_INVOCATION_ID" =~ ^[0-9a-f]{32}$ ]] || return 1
  [[ "$QUARANTINE_SCOPE" == "docker-${QUARANTINE_CONTAINER_ID}.scope" ]] || return 1
  valid_size "$QUARANTINE_HIGH" || return 1
  valid_size "$QUARANTINE_MAX" || return 1
  valid_size "$QUARANTINE_SWAP_MAX" || return 1
  expected_path="$(quarantine_path "$QUARANTINE_CONTAINER" "$QUARANTINE_CONTAINER_ID" "$QUARANTINE_INVOCATION_ID")"
  [[ "$path" == "$expected_path" ]]
}

load_recovery_cooldown() {
  local path="$1" metadata expected_path
  local -a record_lines=()

  [[ -f "$path" && ! -L "$path" ]] || return 1
  metadata="$(stat -c '%u:%g:%a' "$path")"
  [[ "$metadata" == 0:0:600 ]] || return 1
  mapfile -t record_lines <"$path"
  [[ ${#record_lines[@]} -eq 4 ]] || return 1
  [[ "${record_lines[0]}" == version=1 ]] || return 1
  [[ "${record_lines[1]}" == container=* ]] || return 1
  [[ "${record_lines[2]}" == container_id=* ]] || return 1
  [[ "${record_lines[3]}" == attempt_epoch=* ]] || return 1

  RECOVERY_COOLDOWN_CONTAINER="${record_lines[1]#container=}"
  RECOVERY_COOLDOWN_CONTAINER_ID="${record_lines[2]#container_id=}"
  RECOVERY_COOLDOWN_EPOCH="${record_lines[3]#attempt_epoch=}"
  is_allowlisted_container "$RECOVERY_COOLDOWN_CONTAINER" || return 1
  [[ "$RECOVERY_COOLDOWN_CONTAINER_ID" =~ ^[0-9a-f]{64}$ ]] || return 1
  [[ "$RECOVERY_COOLDOWN_EPOCH" =~ ^(0|[1-9][0-9]*)$ ]] || return 1
  expected_path="$(recovery_cooldown_path "$RECOVERY_COOLDOWN_CONTAINER")"
  [[ "$path" == "$expected_path" ]]
}

recovery_cooldown_allows() {
  local container="$1" container_id="$2" context="$3"
  local path now_epoch elapsed remaining

  [[ "$MODE" == reconcile ]] || return 0
  path="$(recovery_cooldown_path "$container")"
  [[ -e "$path" || -L "$path" ]] || return 0
  load_recovery_cooldown "$path" || {
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id context=$context reason=malformed-recovery-cooldown" >&2
    return 1
  }
  now_epoch="$(date +%s)" || {
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id context=$context reason=recovery-clock-unavailable" >&2
    return 1
  }
  [[ "$now_epoch" =~ ^(0|[1-9][0-9]*)$ ]] || {
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id context=$context reason=recovery-clock-invalid" >&2
    return 1
  }
  ((now_epoch >= RECOVERY_COOLDOWN_EPOCH)) || {
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id prior_id=$RECOVERY_COOLDOWN_CONTAINER_ID context=$context reason=recovery-clock-before-cooldown" >&2
    return 1
  }
  elapsed=$((now_epoch - RECOVERY_COOLDOWN_EPOCH))
  if ((elapsed < RECOVERY_RETRY_SECONDS)); then
    remaining=$((RECOVERY_RETRY_SECONDS - elapsed))
    echo "event=docker-scope-mutation-recovery status=backoff container=$container id=$container_id prior_id=$RECOVERY_COOLDOWN_CONTAINER_ID context=$context remaining_seconds=$remaining" >&2
    return 1
  fi
  rm -f -- "$path"
  sync -f "$BASELINE_DIR" || return 1
  echo "event=docker-scope-mutation-recovery status=cooldown-expired container=$container id=$container_id prior_id=$RECOVERY_COOLDOWN_CONTAINER_ID context=$context"
}

arm_automatic_recovery_cooldown() {
  local container="$1" container_id="$2" invocation_id="$3"
  local path temporary now_epoch

  [[ "$MODE" == reconcile ]] || return 0
  recovery_cooldown_allows "$container" "$container_id" recovery-restart || return 1
  path="$(recovery_cooldown_path "$container")"
  now_epoch="$(date +%s)" || return 1
  [[ "$now_epoch" =~ ^(0|[1-9][0-9]*)$ ]] || return 1
  umask 077
  temporary="$(mktemp "$BASELINE_DIR/.${container}.recovery-cooldown.tmp.XXXXXX")"
  CURRENT_BASELINE_TEMP="$temporary"
  {
    printf 'version=1\n'
    printf 'container=%s\n' "$container"
    printf 'container_id=%s\n' "$container_id"
    printf 'attempt_epoch=%s\n' "$now_epoch"
  } >"$temporary"
  chmod 0600 "$temporary"
  sync -f "$temporary" || return 1
  [[ ! -e "$path" && ! -L "$path" ]] || return 1
  mv -- "$temporary" "$path"
  CURRENT_BASELINE_TEMP=""
  sync -f "$BASELINE_DIR" || return 1
  load_recovery_cooldown "$path" || return 1
  [[ "$RECOVERY_COOLDOWN_CONTAINER" == "$container" &&
     "$RECOVERY_COOLDOWN_CONTAINER_ID" == "$container_id" &&
     "$RECOVERY_COOLDOWN_EPOCH" == "$now_epoch" ]] || return 1
  echo "event=docker-scope-mutation-recovery status=cooldown-armed container=$container id=$container_id invocation=$invocation_id retry_seconds=$RECOVERY_RETRY_SECONDS"
}

audit_recovery_cooldowns() {
  local candidate
  local -a candidates=("$BASELINE_DIR/"*.recovery-cooldown)
  for candidate in "${candidates[@]}"; do
    [[ -e "$candidate" || -L "$candidate" ]] || continue
    load_recovery_cooldown "$candidate" || {
      echo "event=docker-scope-mutation-recovery status=refused reason=malformed-recovery-cooldown path=$candidate" >&2
      return 1
    }
    echo "event=docker-scope-mutation-recovery status=cooldown-verified container=$RECOVERY_COOLDOWN_CONTAINER id=$RECOVERY_COOLDOWN_CONTAINER_ID attempt_epoch=$RECOVERY_COOLDOWN_EPOCH"
  done
}

read_scope_snapshot() {
  local scope="$1" raw key value
  SNAP_LOAD=""
  SNAP_ACTIVE=""
  SNAP_INVOCATION=""
  SNAP_HIGH=""
  SNAP_MAX=""
  SNAP_SWAP_MAX=""
  SNAP_CURRENT=""
  SNAP_PEAK=""
  SNAP_SWAP_CURRENT=""
  SNAP_SWAP_PEAK=""
  raw="$(systemctl show "$scope" \
    --property=LoadState --property=ActiveState --property=InvocationID \
    --property=MemoryHigh --property=MemoryMax --property=MemorySwapMax \
    --property=MemoryCurrent --property=MemoryPeak \
    --property=MemorySwapCurrent --property=MemorySwapPeak)" || return 2
  while IFS='=' read -r key value; do
    case "$key" in
      LoadState) SNAP_LOAD="$value" ;;
      ActiveState) SNAP_ACTIVE="$value" ;;
      InvocationID) SNAP_INVOCATION="$value" ;;
      MemoryHigh) SNAP_HIGH="$value" ;;
      MemoryMax) SNAP_MAX="$value" ;;
      MemorySwapMax) SNAP_SWAP_MAX="$value" ;;
      MemoryCurrent) SNAP_CURRENT="$value" ;;
      MemoryPeak) SNAP_PEAK="$value" ;;
      MemorySwapCurrent) SNAP_SWAP_CURRENT="$value" ;;
      MemorySwapPeak) SNAP_SWAP_PEAK="$value" ;;
    esac
  done <<<"$raw"
  # Inactive or collected transient scopes legitimately expose an empty
  # InvocationID. Callers distinguish that state from a failed snapshot.
  [[ -n "$SNAP_LOAD" && -n "$SNAP_ACTIVE" ]] || return 2
}

record_scope_is_active() {
  local scope="$1" invocation_id="$2"
  read_scope_snapshot "$scope" || return 2
  if [[ "$SNAP_LOAD" == loaded &&
        "$SNAP_ACTIVE" == active &&
        "$SNAP_INVOCATION" == "$invocation_id" ]]; then
    return 0
  fi
  return 1
}

same_incarnation() {
  local container_id="$1" scope="$2" invocation_id="$3" inspect_line inspected_id running
  inspect_line="$(docker inspect --format '{{.Id}} {{.State.Running}}' -- "$container_id" 2>/dev/null)" || return 1
  read -r inspected_id running <<<"$inspect_line"
  [[ "$inspected_id" == "$container_id" && "$running" == true ]] || return 1
  record_scope_is_active "$scope" "$invocation_id"
}

cleanup_orphan_temporaries() {
  local container candidate removed=0
  local -a candidates=()
  for container in "${CONTAINERS[@]}"; do
    candidates=("$BASELINE_DIR/.${container}."*.tmp.*)
    for candidate in "${candidates[@]}"; do
      [[ -e "$candidate" || -L "$candidate" ]] || continue
      [[ -f "$candidate" && ! -L "$candidate" ]] || {
        echo "event=docker-scope-reconcile status=refused container=$container reason=malformed-baseline-temporary path=$candidate" >&2
        return 1
      }
      if [[ "$MODE" == check ]]; then
        echo "event=docker-scope-reconcile status=refused container=$container reason=orphan-baseline-temporary path=$candidate" >&2
        return 1
      fi
      rm -f -- "$candidate"
      removed=$((removed + 1))
    done
  done
  if ((removed)); then
    sync -f "$BASELINE_DIR"
    echo "event=docker-scope-baseline status=orphan-temporaries-cleaned count=$removed"
  fi
}

arm_mutation_quarantine() {
  local container="$1" container_id="$2" invocation_id="$3" scope="$4"
  local baseline_high="$5" baseline_max="$6" baseline_swap_max="$7"
  local path temporary
  path="$(quarantine_path "$container" "$container_id" "$invocation_id")"
  if [[ -e "$path" ]]; then
    load_mutation_quarantine "$path" || return 1
    [[ "$QUARANTINE_CONTAINER" == "$container" &&
       "$QUARANTINE_CONTAINER_ID" == "$container_id" &&
       "$QUARANTINE_INVOCATION_ID" == "$invocation_id" &&
       "$QUARANTINE_SCOPE" == "$scope" &&
       "$QUARANTINE_HIGH" == "$baseline_high" &&
       "$QUARANTINE_MAX" == "$baseline_max" &&
       "$QUARANTINE_SWAP_MAX" == "$baseline_swap_max" ]]
    return
  fi

  umask 077
  temporary="$(mktemp "$BASELINE_DIR/.${container}.${container_id}.${invocation_id}.mutation.tmp.XXXXXX")"
  CURRENT_BASELINE_TEMP="$temporary"
  {
    printf 'version=1\n'
    printf 'container=%s\n' "$container"
    printf 'container_id=%s\n' "$container_id"
    printf 'invocation_id=%s\n' "$invocation_id"
    printf 'scope=%s\n' "$scope"
    printf 'memory_high=%s\n' "$baseline_high"
    printf 'memory_max=%s\n' "$baseline_max"
    printf 'memory_swap_max=%s\n' "$baseline_swap_max"
  } >"$temporary"
  chmod 0600 "$temporary"
  sync -f "$temporary" || return 1
  [[ ! -e "$path" ]] || return 1
  mv -- "$temporary" "$path"
  CURRENT_BASELINE_TEMP=""
  sync -f "$BASELINE_DIR" || return 1
  load_mutation_quarantine "$path" || return 1
  echo "event=docker-scope-mutation-quarantine status=armed container=$container id=$container_id invocation=$invocation_id"
}

disarm_mutation_quarantine() {
  local container="$1" container_id="$2" invocation_id="$3" path
  path="$(quarantine_path "$container" "$container_id" "$invocation_id")"
  load_mutation_quarantine "$path" || return 1
  [[ "$QUARANTINE_CONTAINER" == "$container" &&
     "$QUARANTINE_CONTAINER_ID" == "$container_id" &&
     "$QUARANTINE_INVOCATION_ID" == "$invocation_id" ]] || return 1
  rm -f -- "$path"
  sync -f "$BASELINE_DIR"
  echo "event=docker-scope-mutation-quarantine status=cleared container=$container id=$container_id invocation=$invocation_id"
}

retire_mutation_quarantine() {
  local container="$1" container_id="$2" invocation_id="$3" path retired_path
  path="$(quarantine_path "$container" "$container_id" "$invocation_id")"
  retired_path="${path}.retired"
  load_mutation_quarantine "$path" || return 1
  [[ "$QUARANTINE_CONTAINER" == "$container" &&
     "$QUARANTINE_CONTAINER_ID" == "$container_id" &&
     "$QUARANTINE_INVOCATION_ID" == "$invocation_id" &&
     ! -e "$retired_path" ]] || return 1
  mv -- "$path" "$retired_path"
  sync -f "$BASELINE_DIR"
  echo "event=docker-scope-mutation-quarantine status=retired-non-live container=$container id=$container_id invocation=$invocation_id evidence=$retired_path"
}

has_pending_quarantine() {
  local container="$1" container_id="$2" candidate
  local -a candidates=("$BASELINE_DIR/$container.$container_id."*.mutation-quarantine)
  for candidate in "${candidates[@]}"; do
    [[ -e "$candidate" || -L "$candidate" ]] && return 0
  done
  return 1
}

prune_stale_baselines() {
  local container="$1" current_path="${2:-}" candidate result
  local candidate_scope candidate_invocation
  local -a candidates=("$BASELINE_DIR/$container."*.baseline)
  for candidate in "${candidates[@]}"; do
    [[ -e "$candidate" || -L "$candidate" ]] || continue
    [[ -n "$current_path" && "$candidate" == "$current_path" ]] && continue
    if ! load_record "$candidate"; then
      echo "event=docker-scope-reconcile status=refused container=$container reason=malformed-stale-baseline path=$candidate" >&2
      return 1
    fi
    candidate_scope="$RECORD_SCOPE"
    candidate_invocation="$RECORD_INVOCATION_ID"
    if record_scope_is_active "$candidate_scope" "$candidate_invocation"; then
      echo "event=docker-scope-baseline status=retained-active container=$container id=$RECORD_CONTAINER_ID invocation=$candidate_invocation"
      continue
    else
      result=$?
      if ((result == 2)); then
        echo "event=docker-scope-reconcile status=refused container=$container reason=stale-baseline-state-unknown path=$candidate" >&2
        return 1
      fi
    fi
    rm -f -- "$candidate"
    sync -f "$BASELINE_DIR"
    echo "event=docker-scope-baseline status=pruned-inactive container=$container invocation=$candidate_invocation"
  done
}

capture_baseline() {
  local container="$1" container_id="$2" invocation_id="$3" scope="$4"
  local path temporary created=0 quarantine_candidate
  local -a quarantine_candidates=("$BASELINE_DIR/$container.$container_id."*.mutation-quarantine)
  for quarantine_candidate in "${quarantine_candidates[@]}"; do
    [[ -e "$quarantine_candidate" || -L "$quarantine_candidate" ]] || continue
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id reason=pending-mutation-quarantine path=$quarantine_candidate" >&2
    return 1
  done
  path="$(baseline_path "$container" "$container_id" "$invocation_id")"

  same_incarnation "$container_id" "$scope" "$invocation_id" || {
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=identity-changed-before-baseline" >&2
    return 1
  }

  if [[ -e "$path" ]]; then
    load_baseline "$container" "$container_id" "$invocation_id" "$scope" || return 1
    if ! sync -f "$path" || ! sync -f "$BASELINE_DIR"; then
      echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=baseline-sync" >&2
      return 1
    fi
    same_incarnation "$container_id" "$scope" "$invocation_id" || {
      echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=identity-changed-during-baseline-read" >&2
      return 1
    }
    prune_stale_baselines "$container" "$path" || return 1
    load_baseline "$container" "$container_id" "$invocation_id" "$scope"
    return
  fi

  read_scope_snapshot "$scope" || return 1
  if [[ "$SNAP_LOAD" != loaded ||
        "$SNAP_ACTIVE" != active ||
        "$SNAP_INVOCATION" != "$invocation_id" ||
        ! "$SNAP_HIGH" =~ ^(0|[1-9][0-9]*|infinity)$ ||
        ! "$SNAP_MAX" =~ ^(0|[1-9][0-9]*|infinity)$ ||
        ! "$SNAP_SWAP_MAX" =~ ^(0|[1-9][0-9]*|infinity)$ ]]; then
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=invalid-pre-cap-properties" >&2
    return 1
  fi

  umask 077
  temporary="$(mktemp "$BASELINE_DIR/.${container}.${container_id}.${invocation_id}.tmp.XXXXXX")"
  CURRENT_BASELINE_TEMP="$temporary"
  {
    printf 'version=1\n'
    printf 'container=%s\n' "$container"
    printf 'container_id=%s\n' "$container_id"
    printf 'invocation_id=%s\n' "$invocation_id"
    printf 'scope=%s\n' "$scope"
    printf 'memory_high=%s\n' "$SNAP_HIGH"
    printf 'memory_max=%s\n' "$SNAP_MAX"
    printf 'memory_swap_max=%s\n' "$SNAP_SWAP_MAX"
  } >"$temporary"
  chmod 0600 "$temporary"
  sync -f "$temporary" || {
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=baseline-file-sync" >&2
    return 1
  }
  if [[ -e "$path" ]]; then
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=baseline-collision" >&2
    return 1
  fi
  mv -- "$temporary" "$path"
  CURRENT_BASELINE_TEMP=""
  created=1
  sync -f "$BASELINE_DIR" || {
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=baseline-directory-sync" >&2
    return 1
  }
  load_baseline "$container" "$container_id" "$invocation_id" "$scope" || {
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=baseline-postcondition" >&2
    return 1
  }
  if ! same_incarnation "$container_id" "$scope" "$invocation_id"; then
    if ((created)); then
      rm -f -- "$path"
      sync -f "$BASELINE_DIR"
    fi
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=identity-changed-after-baseline" >&2
    return 1
  fi
  prune_stale_baselines "$container" "$path" || return 1
  load_baseline "$container" "$container_id" "$invocation_id" "$scope" || return 1
  echo "event=docker-scope-baseline status=captured container=$container id=$container_id invocation=$invocation_id memory_high=$BASELINE_HIGH memory_max=$BASELINE_MAX memory_swap_max=$BASELINE_SWAP_MAX"
}

bounded_limit() {
  local baseline="$1" policy="$2"
  if [[ "$baseline" == infinity ]] || ((baseline > policy)); then
    printf '%s\n' "$policy"
  else
    printf '%s\n' "$baseline"
  fi
}

recover_ambiguous_mutation() {
  local container="$1" container_id="$2" scope="$3" invocation_id="$4"
  local baseline_high="$5" baseline_max="$6" baseline_swap_max="$7" phase="$8"
  local inspect_line inspected_id running recovered_invocation

  # The durable quarantine remains armed until the exact Docker object has
  # restarted and the resulting exact scope incarnation has been restored to
  # the pre-mutation properties with a successful identity-bound readback.
  load_mutation_quarantine \
    "$(quarantine_path "$container" "$container_id" "$invocation_id")" || {
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=missing-or-malformed-quarantine" >&2
    return 1
  }
  [[ "$QUARANTINE_SCOPE" == "$scope" &&
     "$QUARANTINE_HIGH" == "$baseline_high" &&
     "$QUARANTINE_MAX" == "$baseline_max" &&
     "$QUARANTINE_SWAP_MAX" == "$baseline_swap_max" ]] || {
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=quarantine-contract-mismatch" >&2
    return 1
  }
  if ! inspect_line="$(docker inspect --format '{{.Id}} {{.State.Running}}' -- "$container_id" 2>/dev/null)"; then
    if ! docker info --format '{{.ServerVersion}}' >/dev/null 2>&1; then
      echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=docker-daemon-unavailable" >&2
      return 1
    fi
    if ! read_scope_snapshot "$scope"; then
      echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=old-id-and-scope-state-unknown" >&2
      return 1
    fi
    if [[ "$SNAP_LOAD" == loaded && "$SNAP_ACTIVE" == active ]]; then
      echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id current_invocation=$SNAP_INVOCATION phase=$phase reason=old-id-absent-but-scope-path-active" >&2
      return 1
    fi
    retire_mutation_quarantine "$container" "$container_id" "$invocation_id" || {
      echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=non-live-quarantine-retire-failed" >&2
      return 1
    }
    return 0
  fi
  read -r inspected_id running <<<"$inspect_line"
  [[ "$inspected_id" == "$container_id" ]] || {
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=pre-restart-identity-mismatch" >&2
    return 1
  }
  [[ "$running" == true ]] || {
    echo "event=docker-scope-mutation-recovery status=pending container=$container id=$container_id invocation=$invocation_id phase=$phase reason=exact-id-stopped" >&2
    return 1
  }
  if [[ "$MODE" == reconcile ]] &&
     ! arm_automatic_recovery_cooldown "$container" "$container_id" \
       "$invocation_id"; then
    return 1
  fi
  if ! docker restart --timeout 10 -- "$container_id" >/dev/null; then
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=exact-id-restart-failed" >&2
    return 1
  fi

  inspect_line="$(docker inspect --format '{{.Id}} {{.State.Running}}' -- "$container_id" 2>/dev/null)" || {
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=post-restart-container-unavailable" >&2
    return 1
  }
  read -r inspected_id running <<<"$inspect_line"
  [[ "$inspected_id" == "$container_id" && "$running" == true ]] || {
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=post-restart-identity-mismatch" >&2
    return 1
  }
  read_scope_snapshot "$scope" || {
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=post-restart-scope-unavailable" >&2
    return 1
  }
  recovered_invocation="$SNAP_INVOCATION"
  [[ "$SNAP_LOAD" == loaded &&
     "$SNAP_ACTIVE" == active &&
     "$recovered_invocation" =~ ^[0-9a-f]{32}$ ]] || {
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=post-restart-incarnation-invalid" >&2
    return 1
  }

  if ! systemctl set-property --runtime "$scope" \
    "MemoryHigh=$baseline_high" "MemoryMax=$baseline_max" \
    "MemorySwapMax=$baseline_swap_max"; then
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=baseline-restore-failed" >&2
    return 1
  fi
  if ! same_incarnation "$container_id" "$scope" "$recovered_invocation" ||
     ! read_scope_snapshot "$scope"; then
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=baseline-restore-identity-ambiguous" >&2
    return 1
  fi
  if [[ "$SNAP_LOAD" != loaded ||
        "$SNAP_ACTIVE" != active ||
        "$SNAP_INVOCATION" != "$recovered_invocation" ||
        "$SNAP_HIGH" != "$baseline_high" ||
        "$SNAP_MAX" != "$baseline_max" ||
        "$SNAP_SWAP_MAX" != "$baseline_swap_max" ]]; then
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=baseline-restore-readback-mismatch" >&2
    return 1
  fi

  disarm_mutation_quarantine "$container" "$container_id" "$invocation_id" || {
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id phase=$phase reason=quarantine-clear-failed" >&2
    return 1
  }
  if ! capture_baseline "$container" "$container_id" "$recovered_invocation" "$scope"; then
    echo "event=docker-scope-mutation-recovery status=error container=$container id=$container_id invocation=$invocation_id recovered_invocation=$recovered_invocation phase=$phase reason=recovered-baseline-capture-failed" >&2
    return 1
  fi
  echo "event=docker-scope-mutation-recovery status=recovered-by-exact-id-restart container=$container id=$container_id invocation=$invocation_id recovered_invocation=$recovered_invocation phase=$phase memory_high=$baseline_high memory_max=$baseline_max memory_swap_max=$baseline_swap_max"
}

set_exact_properties() {
  local container="$1" container_id="$2" scope="$3" invocation_id="$4"
  local desired_high="$5" desired_max="$6" desired_swap_max="$7"
  local baseline_high="$8" baseline_max="$9" baseline_swap_max="${10}"
  local recovery_status
  same_incarnation "$container_id" "$scope" "$invocation_id" || {
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=identity-changed-before-mutation" >&2
    return 1
  }
  arm_mutation_quarantine "$container" "$container_id" "$invocation_id" "$scope" \
    "$baseline_high" "$baseline_max" "$baseline_swap_max" || {
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=mutation-quarantine-arm-failed" >&2
    return 1
  }
  if ! same_incarnation "$container_id" "$scope" "$invocation_id"; then
    disarm_mutation_quarantine "$container" "$container_id" "$invocation_id" || true
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=identity-changed-before-set-command" >&2
    return 1
  fi
  if ! systemctl set-property --runtime "$scope" \
    "MemoryHigh=$desired_high" "MemoryMax=$desired_max" \
    "MemorySwapMax=$desired_swap_max"; then
    if recover_ambiguous_mutation "$container" "$container_id" "$scope" "$invocation_id" \
      "$baseline_high" "$baseline_max" "$baseline_swap_max" set-command-failed; then
      recovery_status=completed
    else
      recovery_status=pending-quarantine
    fi
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=set-property-failed recovery=$recovery_status" >&2
    return 1
  fi
  if ! same_incarnation "$container_id" "$scope" "$invocation_id"; then
    if recover_ambiguous_mutation "$container" "$container_id" "$scope" "$invocation_id" \
      "$baseline_high" "$baseline_max" "$baseline_swap_max" post-set-identity; then
      recovery_status=completed
    else
      recovery_status=pending-quarantine
    fi
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=identity-ambiguous-after-mutation recovery=$recovery_status" >&2
    return 1
  fi
  if ! read_scope_snapshot "$scope"; then
    if recover_ambiguous_mutation "$container" "$container_id" "$scope" "$invocation_id" \
      "$baseline_high" "$baseline_max" "$baseline_swap_max" post-set-readback; then
      recovery_status=completed
    else
      recovery_status=pending-quarantine
    fi
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=post-mutation-readback-failed recovery=$recovery_status" >&2
    return 1
  fi
  if [[ "$SNAP_LOAD" != loaded ||
        "$SNAP_ACTIVE" != active ||
        "$SNAP_INVOCATION" != "$invocation_id" ]]; then
    if recover_ambiguous_mutation "$container" "$container_id" "$scope" "$invocation_id" \
      "$baseline_high" "$baseline_max" "$baseline_swap_max" post-set-snapshot; then
      recovery_status=completed
    else
      recovery_status=pending-quarantine
    fi
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=identity-ambiguous-at-readback recovery=$recovery_status" >&2
    return 1
  fi
  if [[ "$SNAP_HIGH" != "$desired_high" ||
        "$SNAP_MAX" != "$desired_max" ||
        "$SNAP_SWAP_MAX" != "$desired_swap_max" ]]; then
    if recover_ambiguous_mutation "$container" "$container_id" "$scope" "$invocation_id" \
      "$baseline_high" "$baseline_max" "$baseline_swap_max" property-readback-mismatch; then
      recovery_status=completed
    else
      recovery_status=pending-quarantine
    fi
    echo "event=docker-scope-reconcile status=error container=$container id=$container_id invocation=$invocation_id reason=property-readback-mismatch recovery=$recovery_status actual_high=$SNAP_HIGH actual_max=$SNAP_MAX actual_swap_max=$SNAP_SWAP_MAX expected_high=$desired_high expected_max=$desired_max expected_swap_max=$desired_swap_max" >&2
    return 1
  fi
  disarm_mutation_quarantine "$container" "$container_id" "$invocation_id" || {
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=mutation-quarantine-clear-failed" >&2
    return 1
  }
}

recover_pending_quarantines() {
  local candidate
  local container container_id invocation_id scope high max swap_max
  local failures=0
  local -a candidates=("$BASELINE_DIR/"*.mutation-quarantine)
  for candidate in "${candidates[@]}"; do
    [[ -e "$candidate" || -L "$candidate" ]] || continue
    if ! load_mutation_quarantine "$candidate"; then
      echo "event=docker-scope-mutation-recovery status=refused reason=malformed-quarantine path=$candidate" >&2
      QUARANTINE_NAMESPACE_UNTRUSTED=1
      failures=$((failures + 1))
      continue
    fi
    container="$QUARANTINE_CONTAINER"
    container_id="$QUARANTINE_CONTAINER_ID"
    invocation_id="$QUARANTINE_INVOCATION_ID"
    scope="$QUARANTINE_SCOPE"
    high="$QUARANTINE_HIGH"
    max="$QUARANTINE_MAX"
    swap_max="$QUARANTINE_SWAP_MAX"
    if [[ "$MODE" == check ]]; then
      echo "event=docker-scope-mutation-recovery status=refused container=$container id=$container_id invocation=$invocation_id reason=pending-quarantine-read-only-check" >&2
      failures=$((failures + 1))
    elif ! recover_ambiguous_mutation "$container" "$container_id" "$scope" \
      "$invocation_id" "$high" "$max" "$swap_max" pending-cycle; then
      failures=$((failures + 1))
    fi
  done
  PENDING_QUARANTINE_FAILURES="$failures"
  ((failures == 0))
}

audit_recorded_baselines() {
  local candidate result container container_id invocation_id scope high max swap_max
  local -a candidates=("$BASELINE_DIR/"*.baseline)
  for candidate in "${candidates[@]}"; do
    [[ -e "$candidate" || -L "$candidate" ]] || continue
    if ! load_record "$candidate"; then
      echo "event=docker-scope-reconcile status=refused reason=malformed-baseline path=$candidate" >&2
      return 1
    fi
    container="$RECORD_CONTAINER"
    container_id="$RECORD_CONTAINER_ID"
    invocation_id="$RECORD_INVOCATION_ID"
    scope="$RECORD_SCOPE"
    high="$RECORD_HIGH"
    max="$RECORD_MAX"
    swap_max="$RECORD_SWAP_MAX"
    if has_pending_quarantine "$container" "$container_id"; then
      echo "event=docker-scope-baseline status=skipped-pending-quarantine container=$container id=$container_id invocation=$invocation_id" >&2
      continue
    fi
    if record_scope_is_active "$scope" "$invocation_id"; then
      if [[ "$MODE" == restore ]]; then
        if ! set_exact_properties "$container" "$container_id" "$scope" "$invocation_id" \
          "$high" "$max" "$swap_max" "$high" "$max" "$swap_max"; then
          return 1
        fi
        echo "event=docker-scope-restore status=restored-recorded-incarnation container=$container id=$container_id invocation=$invocation_id memory_high=$high memory_max=$max memory_swap_max=$swap_max"
      else
        echo "event=docker-scope-baseline status=active-record-verified container=$container id=$container_id invocation=$invocation_id"
      fi
    else
      result=$?
      if ((result == 2)); then
        echo "event=docker-scope-reconcile status=refused reason=baseline-scope-state-unknown path=$candidate" >&2
        return 1
      fi
      echo "event=docker-scope-baseline status=inactive-record container=$container id=$container_id invocation=$invocation_id"
    fi
  done
}

resolve_named_container() {
  local container="$1" inspect_line
  inspect_line="$(docker inspect --format '{{.Id}} {{.State.Running}}' -- "$container" 2>/dev/null)" || return 1
  read -r RESOLVED_ID RESOLVED_RUNNING <<<"$inspect_line"
  [[ "$RESOLVED_ID" =~ ^[0-9a-f]{64}$ && "$RESOLVED_RUNNING" == true ]] || return 1
  RESOLVED_SCOPE="docker-${RESOLVED_ID}.scope"
  read_scope_snapshot "$RESOLVED_SCOPE" || return 1
  [[ "$SNAP_LOAD" == loaded &&
     "$SNAP_ACTIVE" == active &&
     "$SNAP_INVOCATION" =~ ^[0-9a-f]{32}$ ]] || return 1
  RESOLVED_INVOCATION="$SNAP_INVOCATION"
}

PENDING_QUARANTINE_FAILURES=0
QUARANTINE_NAMESPACE_UNTRUSTED=0
cleanup_orphan_temporaries
audit_recovery_cooldowns
if [[ "$MODE" == check ]]; then
  recover_pending_quarantines
else
  recover_pending_quarantines || true
fi
if ((QUARANTINE_NAMESPACE_UNTRUSTED)); then
  echo "event=docker-scope-reconcile status=refused reason=untrusted-quarantine-namespace" >&2
  exit 1
fi
audit_recorded_baselines

failures="$PENDING_QUARANTINE_FAILURES"
changed=0
for ((i=0; i<${#CONTAINERS[@]}; i++)); do
  container="${CONTAINERS[$i]}"
  if ! resolve_named_container "$container"; then
    if [[ "$MODE" == reconcile ]]; then
      prune_stale_baselines "$container" "" || true
      echo "event=docker-scope-reconcile status=error container=$container reason=missing-or-inactive" >&2
      failures=$((failures + 1))
    else
      echo "event=docker-scope-$MODE status=no-current-name container=$container reason=recorded-active-incarnations-already-processed"
    fi
    continue
  fi
  container_id="$RESOLVED_ID"
  scope="$RESOLVED_SCOPE"
  invocation_id="$RESOLVED_INVOCATION"
  path="$(baseline_path "$container" "$container_id" "$invocation_id")"

  if [[ "$MODE" == reconcile ]]; then
    if ! capture_baseline "$container" "$container_id" "$invocation_id" "$scope"; then
      failures=$((failures + 1))
      continue
    fi
  elif ! load_baseline "$container" "$container_id" "$invocation_id" "$scope"; then
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=missing-or-malformed-baseline" >&2
    failures=$((failures + 1))
    continue
  fi

  if [[ "$MODE" == check ]]; then
    continue
  fi
  if [[ "$MODE" == restore ]]; then
    if ! set_exact_properties "$container" "$container_id" "$scope" "$invocation_id" \
      "$BASELINE_HIGH" "$BASELINE_MAX" "$BASELINE_SWAP_MAX" \
      "$BASELINE_HIGH" "$BASELINE_MAX" "$BASELINE_SWAP_MAX"; then
      failures=$((failures + 1))
      continue
    fi
    changed=$((changed + 1))
    echo "event=docker-scope-restore status=restored container=$container id=$container_id invocation=$invocation_id memory_high=$BASELINE_HIGH memory_max=$BASELINE_MAX memory_swap_max=$BASELINE_SWAP_MAX"
    continue
  fi

  desired_high="$(bounded_limit "$BASELINE_HIGH" "${MEMORY_HIGH_BYTES[$i]}")"
  desired_max="$(bounded_limit "$BASELINE_MAX" "${MEMORY_MAX_BYTES[$i]}")"
  desired_swap_max="$(bounded_limit "$BASELINE_SWAP_MAX" "${MEMORY_SWAP_MAX_BYTES[$i]}")"
  if ((desired_high > desired_max)); then
    desired_high="$desired_max"
  fi

  read_scope_snapshot "$scope" || {
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=memory-evidence-unavailable" >&2
    failures=$((failures + 1))
    continue
  }
  if [[ "$SNAP_LOAD" != loaded ||
        "$SNAP_ACTIVE" != active ||
        "$SNAP_INVOCATION" != "$invocation_id" ]]; then
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=identity-changed-before-evidence" >&2
    failures=$((failures + 1))
    continue
  fi
  if [[ "$SNAP_HIGH" == "$desired_high" &&
        "$SNAP_MAX" == "$desired_max" &&
        "$SNAP_SWAP_MAX" == "$desired_swap_max" ]]; then
    echo "event=docker-scope-reconcile status=already-capped container=$container id=$container_id invocation=$invocation_id memory_high=$desired_high memory_max=$desired_max memory_swap_max=$desired_swap_max"
    continue
  fi
  if [[ ! "$SNAP_CURRENT" =~ ^(0|[1-9][0-9]*)$ ||
        ! "$SNAP_PEAK" =~ ^(0|[1-9][0-9]*)$ ||
        ! "$SNAP_SWAP_CURRENT" =~ ^(0|[1-9][0-9]*)$ ||
        ! "$SNAP_SWAP_PEAK" =~ ^(0|[1-9][0-9]*)$ ]]; then
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=memory-evidence-invalid" >&2
    failures=$((failures + 1))
    continue
  fi
  if ((SNAP_SWAP_CURRENT + HEADROOM_BYTES > desired_swap_max ||
       SNAP_SWAP_PEAK + HEADROOM_BYTES > desired_swap_max)); then
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=insufficient-swap-headroom current=$SNAP_SWAP_CURRENT peak=$SNAP_SWAP_PEAK proposed_swap_max=$desired_swap_max" >&2
    failures=$((failures + 1))
    continue
  fi
  if ((SNAP_CURRENT + HEADROOM_BYTES > desired_max ||
       SNAP_PEAK + HEADROOM_BYTES > desired_max)); then
    echo "event=docker-scope-reconcile status=refused container=$container id=$container_id invocation=$invocation_id reason=insufficient-headroom current=$SNAP_CURRENT peak=$SNAP_PEAK proposed_max=$desired_max" >&2
    failures=$((failures + 1))
    continue
  fi
  if ! set_exact_properties "$container" "$container_id" "$scope" "$invocation_id" \
    "$desired_high" "$desired_max" "$desired_swap_max" \
    "$BASELINE_HIGH" "$BASELINE_MAX" "$BASELINE_SWAP_MAX"; then
    failures=$((failures + 1))
    continue
  fi
  changed=$((changed + 1))
  echo "event=docker-scope-reconcile status=capped container=$container id=$container_id invocation=$invocation_id memory_high=$desired_high memory_max=$desired_max memory_swap_max=$desired_swap_max"
done

if ((failures)); then
  echo "event=docker-scope-reconcile status=partial mode=$MODE checked=${#CONTAINERS[@]} changed=$changed failures=$failures" >&2
  exit 1
fi
echo "event=docker-scope-reconcile status=ok mode=$MODE checked=${#CONTAINERS[@]} changed=$changed failures=0"
