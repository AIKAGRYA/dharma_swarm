#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  echo "Usage: $0 [--host rushabdev|agni|meghadharma] [--dry-run] [--purge]" >&2
}

HOST_NAME=""
DRY_RUN=0
PURGE=0
while (($#)); do
  case "$1" in
    --host)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      HOST_NAME="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --purge)
      PURGE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

PREINSTALL_DIR=/var/lib/vps-resource-guard/preinstall
if [[ -r "$PREINSTALL_DIR/host" ]]; then
  SAVED_HOST="$(<"$PREINSTALL_DIR/host")"
  if [[ -n "$HOST_NAME" && "$HOST_NAME" != "$SAVED_HOST" ]]; then
    echo "Requested host does not match saved preinstall state ($SAVED_HOST)." >&2
    exit 2
  fi
  HOST_NAME="$SAVED_HOST"
elif [[ -z "$HOST_NAME" ]]; then
  echo "No saved host policy. Pass --host only for a dry-run; refusing an ambiguous uninstall." >&2
  exit 2
fi

SYSTEM_UNITS=()
USER_UNITS=()
DOCKER_CONTAINERS=()
case "$HOST_NAME" in
  rushabdev)
    SYSTEM_UNITS=("ollama.service")
    USER_UNITS=("hermes-gateway.service" "openclaw-gateway.service")
    ;;
  agni)
    SYSTEM_UNITS=("ollama.service")
    USER_UNITS=("hermes-gateway.service")
    ;;
  meghadharma)
    DOCKER_CONTAINERS=(
      "dharma-command-backend"
      "hermes"
      "dharma-swarm"
      "dharma-command-edge"
    )
    ;;
  *)
    echo "Invalid saved host policy: $HOST_NAME" >&2
    exit 2
    ;;
esac

MANAGED_KEYS=(guard config service probe-service journald readme)
MANAGED_DESTS=(
  /usr/local/lib/vps-resource-guard/vps_resource_guard.py
  /etc/vps-resource-guard/config.toml
  /etc/systemd/system/vps-resource-guard.service
  /etc/systemd/system/vps-resource-guard-self-test.service
  /etc/systemd/journald.conf.d/zz-vps-resource-guard.conf
  /usr/local/share/doc/vps-resource-guard/README.md
)
for ((unit_i=0; unit_i<${#SYSTEM_UNITS[@]}; unit_i++)); do
  unit="${SYSTEM_UNITS[$unit_i]}"
  unit_stem="${unit%.service}"
  MANAGED_KEYS+=("system-${unit_stem}")
  MANAGED_DESTS+=("/etc/systemd/system/$unit.d/90-vps-resource-guard.conf")
done
for ((unit_i=0; unit_i<${#USER_UNITS[@]}; unit_i++)); do
  unit="${USER_UNITS[$unit_i]}"
  unit_stem="${unit%.service}"
  MANAGED_KEYS+=("user-${unit_stem}")
  MANAGED_DESTS+=("/root/.config/systemd/user/$unit.d/90-vps-resource-guard.conf")
done
if [[ "$HOST_NAME" == meghadharma ]]; then
  MANAGED_KEYS+=(docker-reconciler docker-reconciler-service docker-reconciler-timer)
  MANAGED_DESTS+=(
    /usr/local/lib/vps-resource-guard/reconcile-meghadharma-docker-limits.sh
    /etc/systemd/system/vps-resource-guard-docker-reconcile.service
    /etc/systemd/system/vps-resource-guard-docker-reconcile.timer
  )
fi

if ((DRY_RUN)); then
  echo "DRY-RUN: prevalidate every saved file/property record before mutation"
  echo "DRY-RUN: disable, stop, and verify inactive vps-resource-guard.service"
  for i in "${!MANAGED_DESTS[@]}"; do
    printf 'DRY-RUN: transactionally restore collision or remove package-created %q\n' "${MANAGED_DESTS[$i]}"
  done
  echo "DRY-RUN: restore saved target runtime properties"
  for ((container_i=0; container_i<${#DOCKER_CONTAINERS[@]}; container_i++)); do
    printf 'DRY-RUN: restore the exact current Docker ID + scope InvocationID baseline: %q\n' \
      "${DOCKER_CONTAINERS[$container_i]}"
  done
  echo "DRY-RUN: daemon-reload managers and restart journald (vacuumed history cannot be restored)"
  echo "DRY-RUN: rotate this install baseline to immutable uninstall evidence"
  if ((PURGE)); then echo "DRY-RUN: purge guard state, receipts, and this install's restore evidence"; fi
  exit 0
fi

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run as root, or use --dry-run." >&2
  exit 2
fi
for command_name in systemctl install cp rm mktemp mv date awk flock sha256sum stat sync; do
  command -v "$command_name" >/dev/null || {
    echo "Required command not found: $command_name" >&2
    exit 2
  }
done
if ((${#DOCKER_CONTAINERS[@]})); then
  command -v docker >/dev/null || { echo "Required command not found: docker" >&2; exit 2; }
fi
[[ -d "$PREINSTALL_DIR" && ! -L "$PREINSTALL_DIR" && \
   "$(stat -c '%u:%g:%a' "$PREINSTALL_DIR")" == 0:0:700 && \
   -d "$PREINSTALL_DIR/files" && ! -L "$PREINSTALL_DIR/files" && \
   -d "$PREINSTALL_DIR/values" && ! -L "$PREINSTALL_DIR/values" ]] || {
  echo "Saved preinstall records are incomplete; refusing to guess what to remove." >&2
  exit 2
}
SUPERSEDED_ROOT="$PREINSTALL_DIR/superseded-files"
if [[ -e "$SUPERSEDED_ROOT" || -L "$SUPERSEDED_ROOT" ]]; then
  [[ -d "$SUPERSEDED_ROOT" && ! -L "$SUPERSEDED_ROOT" && \
     "$(stat -c '%u:%g:%a' "$SUPERSEDED_ROOT")" == 0:0:700 ]] || {
    echo "Saved superseded-file evidence root is unsafe; refusing uninstall." >&2
    exit 2
  }
fi

export XDG_RUNTIME_DIR=/run/user/0
STATE_DIR=/var/lib/vps-resource-guard
LOCK_FILE="$STATE_DIR/operation.lock"
SCOPE_BASELINE_DIR="$STATE_DIR/preinstall/docker-scope-baselines"
RECONCILER_PATH=/usr/local/lib/vps-resource-guard/reconcile-meghadharma-docker-limits.sh
[[ ! -L "$STATE_DIR" ]] || { echo "Refusing symlink at guard state directory." >&2; exit 2; }
install -d -o root -g root -m 0700 "$STATE_DIR"
[[ ! -L "$LOCK_FILE" && ( ! -e "$LOCK_FILE" || -f "$LOCK_FILE" ) ]] || {
  echo "Refusing malformed guard operation lock." >&2
  exit 2
}
exec 9>"$LOCK_FILE"
flock -w 60 9 || { echo "Timed out waiting for the VPS resource guard operation lock." >&2; exit 1; }

user_systemctl() {
  XDG_RUNTIME_DIR=/run/user/0 systemctl --user "$@"
}

read_saved_size() {
  local key="$1"
  local path="$PREINSTALL_DIR/values/$key"
  local value
  [[ -r "$path" ]] || return 1
  value="$(<"$path")"
  [[ "$value" =~ ^([0-9]+|infinity)$ ]] || return 1
  printf '%s\n' "$value"
}

read_saved_integer() {
  local key="$1"
  local path="$PREINSTALL_DIR/values/$key"
  local value
  [[ -r "$path" ]] || return 1
  value="$(<"$path")"
  [[ "$value" =~ ^[0-9]+$ ]] || return 1
  printf '%s\n' "$value"
}

valid_size_value() {
  [[ "$1" =~ ^([0-9]+|infinity)$ ]]
}

assert_system_property() {
  local unit="$1" property="$2" expected="$3" actual
  actual="$(systemctl show "$unit" --property="$property" --value)"
  [[ "$actual" == "$expected" ]] || {
    echo "$unit $property=$actual, expected restored value $expected." >&2
    return 1
  }
}

assert_user_property() {
  local unit="$1" property="$2" expected="$3" actual
  actual="$(user_systemctl show "$unit" --property="$property" --value)"
  [[ "$actual" == "$expected" ]] || {
    echo "root user $unit $property=$actual, expected restored value $expected." >&2
    return 1
  }
}

# Validate the complete restoration contract before stopping anything.
for i in "${!MANAGED_DESTS[@]}"; do
  key="${MANAGED_KEYS[$i]}"
  base="$PREINSTALL_DIR/files/$key"
  if [[ -e "$base.present" ]]; then
    [[ ! -e "$base.absent" && -f "$base.content" && ! -L "$base.content" ]] || {
      echo "Invalid original-file record for ${MANAGED_DESTS[$i]}." >&2
      exit 2
    }
  elif [[ -e "$base.absent" ]]; then
    [[ ! -e "$base.present" && ! -e "$base.content" ]] || {
      echo "Invalid absent-file record for ${MANAGED_DESTS[$i]}." >&2
      exit 2
    }
  else
    echo "Missing original-file record for ${MANAGED_DESTS[$i]}." >&2
    exit 2
  fi
done

RESTORE_SYSTEM_HIGHS=()
RESTORE_SYSTEM_MAXES=()
RESTORE_USER_HIGHS=()
RESTORE_USER_MAXES=()
for ((i=0; i<${#SYSTEM_UNITS[@]}; i++)); do
  key="system.${SYSTEM_UNITS[$i]}"
  RESTORE_SYSTEM_HIGHS+=("$(read_saved_size "$key.MemoryHigh")") || exit 2
  RESTORE_SYSTEM_MAXES+=("$(read_saved_size "$key.MemoryMax")") || exit 2
done
for ((i=0; i<${#USER_UNITS[@]}; i++)); do
  key="user.${USER_UNITS[$i]}"
  RESTORE_USER_HIGHS+=("$(read_saved_size "$key.MemoryHigh")") || exit 2
  RESTORE_USER_MAXES+=("$(read_saved_size "$key.MemoryMax")") || exit 2
done
RESTORE_GUARD_ENABLED="$(read_saved_integer guard.was-enabled)" || exit 2
RESTORE_GUARD_ACTIVE="$(read_saved_integer guard.was-active)" || exit 2
RESTORE_PROBE_ENABLED="$(read_saved_integer probe.was-enabled)" || exit 2
RESTORE_PROBE_ACTIVE="$(read_saved_integer probe.was-active)" || exit 2
RESTORE_RECONCILER_ENABLED=0
RESTORE_RECONCILER_ACTIVE=0
RESTORE_RECONCILER_TIMER_ENABLED=0
RESTORE_RECONCILER_TIMER_ACTIVE=0
if [[ "$HOST_NAME" == meghadharma ]]; then
  RESTORE_RECONCILER_ENABLED="$(read_saved_integer reconciler.was-enabled)" || exit 2
  RESTORE_RECONCILER_ACTIVE="$(read_saved_integer reconciler.was-active)" || exit 2
  RESTORE_RECONCILER_TIMER_ENABLED="$(read_saved_integer reconciler-timer.was-enabled)" || exit 2
  RESTORE_RECONCILER_TIMER_ACTIVE="$(read_saved_integer reconciler-timer.was-active)" || exit 2
fi
for flag in "$RESTORE_GUARD_ENABLED" "$RESTORE_GUARD_ACTIVE" "$RESTORE_PROBE_ENABLED" "$RESTORE_PROBE_ACTIVE" "$RESTORE_RECONCILER_ENABLED" "$RESTORE_RECONCILER_ACTIVE" "$RESTORE_RECONCILER_TIMER_ENABLED" "$RESTORE_RECONCILER_TIMER_ACTIVE"; do
  [[ "$flag" == 0 || "$flag" == 1 ]] || { echo "Invalid saved service-state flag." >&2; exit 2; }
done

TX_DIR="$(mktemp -d /var/lib/vps-resource-guard-uninstall.XXXXXX)"
TX_FILES_DIR="$TX_DIR/files"
install -d -m 0700 "$TX_FILES_DIR"
TX_PRESENT=()
TX_SYSTEM_HIGHS=()
TX_SYSTEM_MAXES=()
TX_USER_HIGHS=()
TX_USER_MAXES=()
TX_DOCKER_HIGHS=()
TX_DOCKER_MAXES=()
TX_DOCKER_SWAP_MAXES=()
TX_DOCKER_IDS=()
TX_DOCKER_INVOCATIONS=()

ensure_private_evidence_directory() {
  local path="$1" parent="$2"
  [[ -d "$parent" && ! -L "$parent" ]] || return 1
  if [[ -e "$path" || -L "$path" ]]; then
    [[ -d "$path" && ! -L "$path" && \
       "$(stat -c '%u:%g:%a' "$path")" == 0:0:700 ]]
    return
  fi
  install -d -o root -g root -m 0700 "$path"
  [[ -d "$path" && ! -L "$path" && \
     "$(stat -c '%u:%g:%a' "$path")" == 0:0:700 ]] || return 1
  sync -f "$parent"
}

preserve_uninstall_current_file() {
  local key="$1" current_path="$2"
  local digest evidence_root evidence_dir destination partial
  digest="$(sha256sum "$current_path" | awk '{print $1}')"
  [[ "$digest" =~ ^[0-9a-f]{64}$ ]] || return 1
  evidence_root="$PREINSTALL_DIR/superseded-files"
  ensure_private_evidence_directory "$evidence_root" "$PREINSTALL_DIR" || return 1
  evidence_dir="$evidence_root/$key"
  ensure_private_evidence_directory "$evidence_dir" "$evidence_root" || return 1
  destination="$evidence_dir/$digest"
  if [[ -e "$destination" ]]; then
    [[ -f "$destination" && ! -L "$destination" &&
       "$(sha256sum "$destination" | awk '{print $1}')" == "$digest" ]] || return 1
    return 0
  fi
  partial="$evidence_dir/.${digest}.partial"
  [[ ! -L "$partial" && ( ! -e "$partial" || -f "$partial" ) ]] || return 1
  rm -f -- "$partial"
  install -o root -g root -m 0600 "$current_path" "$partial"
  [[ "$(sha256sum "$partial" | awk '{print $1}')" == "$digest" ]] || {
    rm -f -- "$partial"
    return 1
  }
  sync -f "$partial"
  mv -- "$partial" "$destination"
  sync -f "$evidence_dir"
  echo "Preserved uninstall-time managed file evidence: key=$key sha256=$digest"
}

for ((i=0; i<${#SYSTEM_UNITS[@]}; i++)); do
  TX_SYSTEM_HIGHS+=("$(systemctl show "${SYSTEM_UNITS[$i]}" --property=MemoryHigh --value)")
  TX_SYSTEM_MAXES+=("$(systemctl show "${SYSTEM_UNITS[$i]}" --property=MemoryMax --value)")
  if ! valid_size_value "${TX_SYSTEM_HIGHS[$i]}" || ! valid_size_value "${TX_SYSTEM_MAXES[$i]}"; then
    echo "Cannot capture current limits for ${SYSTEM_UNITS[$i]}." >&2
    exit 2
  fi
done
for ((i=0; i<${#USER_UNITS[@]}; i++)); do
  TX_USER_HIGHS+=("$(user_systemctl show "${USER_UNITS[$i]}" --property=MemoryHigh --value)")
  TX_USER_MAXES+=("$(user_systemctl show "${USER_UNITS[$i]}" --property=MemoryMax --value)")
  if ! valid_size_value "${TX_USER_HIGHS[$i]}" || ! valid_size_value "${TX_USER_MAXES[$i]}"; then
    echo "Cannot capture current limits for ${USER_UNITS[$i]}." >&2
    exit 2
  fi
done
for ((i=0; i<${#DOCKER_CONTAINERS[@]}; i++)); do
  container="${DOCKER_CONTAINERS[$i]}"
  if ! docker inspect "$container" >/dev/null 2>&1; then
    TX_DOCKER_IDS+=("")
    TX_DOCKER_INVOCATIONS+=("")
    TX_DOCKER_HIGHS+=("")
    TX_DOCKER_MAXES+=("")
    TX_DOCKER_SWAP_MAXES+=("")
    continue
  fi
  container_id="$(docker inspect --format '{{.Id}}' "$container")"
  scope="docker-${container_id}.scope"
  TX_DOCKER_IDS+=("$container_id")
  if [[ ! "$container_id" =~ ^[0-9a-f]{64}$ || \
    "$(systemctl show "$scope" --property=ActiveState --value)" != active ]]; then
    TX_DOCKER_INVOCATIONS+=("")
    TX_DOCKER_HIGHS+=("")
    TX_DOCKER_MAXES+=("")
    TX_DOCKER_SWAP_MAXES+=("")
    continue
  fi
  invocation_id="$(systemctl show "$scope" --property=InvocationID --value)"
  [[ "$invocation_id" =~ ^[0-9a-f]{32}$ ]] || {
    echo "Cannot capture current Docker scope incarnation for $container." >&2
    exit 2
  }
  TX_DOCKER_INVOCATIONS+=("$invocation_id")
  TX_DOCKER_HIGHS+=("$(systemctl show "$scope" --property=MemoryHigh --value)")
  TX_DOCKER_MAXES+=("$(systemctl show "$scope" --property=MemoryMax --value)")
  TX_DOCKER_SWAP_MAXES+=("$(systemctl show "$scope" --property=MemorySwapMax --value)")
  if ! valid_size_value "${TX_DOCKER_HIGHS[$i]}" || \
    ! valid_size_value "${TX_DOCKER_MAXES[$i]}" || \
    ! valid_size_value "${TX_DOCKER_SWAP_MAXES[$i]}"; then
    echo "Cannot capture current Docker identity and limits for $container." >&2
    exit 2
  fi
done
if [[ "$HOST_NAME" == meghadharma ]]; then
  [[ -f "$RECONCILER_PATH" && ! -L "$RECONCILER_PATH" ]] || {
    echo "Installed Docker reconciler is unavailable or unsafe; refusing uninstall." >&2
    exit 2
  }
  VPS_RESOURCE_GUARD_LOCK_HELD=1 "$RECONCILER_PATH" --check-baselines
fi
for i in "${!MANAGED_DESTS[@]}"; do
  path="${MANAGED_DESTS[$i]}"
  [[ ! -L "$path" ]] || { echo "Refusing symlink at managed path: $path" >&2; exit 2; }
  if [[ -e "$path" ]]; then
    [[ -f "$path" ]] || { echo "Refusing non-regular managed path: $path" >&2; exit 2; }
    cp -a -- "$path" "$TX_FILES_DIR/$i"
    preserve_uninstall_current_file "${MANAGED_KEYS[$i]}" "$path"
    TX_PRESENT+=(1)
  else
    TX_PRESENT+=(0)
  fi
done
sync -f "$PREINSTALL_DIR"
TX_GUARD_ACTIVE=0
TX_GUARD_ENABLED=0
TX_PROBE_ACTIVE=0
TX_PROBE_ENABLED=0
TX_RECONCILER_ACTIVE=0
TX_RECONCILER_ENABLED=0
TX_RECONCILER_TIMER_ACTIVE=0
TX_RECONCILER_TIMER_ENABLED=0
if systemctl is-active --quiet vps-resource-guard.service; then TX_GUARD_ACTIVE=1; fi
if systemctl is-enabled --quiet vps-resource-guard.service 2>/dev/null; then TX_GUARD_ENABLED=1; fi
if systemctl is-active --quiet vps-resource-guard-self-test.service; then TX_PROBE_ACTIVE=1; fi
if systemctl is-enabled --quiet vps-resource-guard-self-test.service 2>/dev/null; then TX_PROBE_ENABLED=1; fi
if [[ "$HOST_NAME" == meghadharma ]]; then
  if systemctl is-active --quiet vps-resource-guard-docker-reconcile.service; then TX_RECONCILER_ACTIVE=1; fi
  if systemctl is-enabled --quiet vps-resource-guard-docker-reconcile.service 2>/dev/null; then TX_RECONCILER_ENABLED=1; fi
  if systemctl is-active --quiet vps-resource-guard-docker-reconcile.timer; then TX_RECONCILER_TIMER_ACTIVE=1; fi
  if systemctl is-enabled --quiet vps-resource-guard-docker-reconcile.timer 2>/dev/null; then TX_RECONCILER_TIMER_ENABLED=1; fi
fi
MUTATED=0
COMMITTED=0
EVIDENCE_DIR=""
EVIDENCE_PREINSTALL_MOVED=0

restore_transaction_files() {
  local i path
  for ((i=${#MANAGED_DESTS[@]} - 1; i >= 0; i--)); do
    path="${MANAGED_DESTS[$i]}"
    rm -f -- "$path"
    if [[ "${TX_PRESENT[$i]}" == 1 ]]; then
      install -d -m 0755 "$(dirname -- "$path")"
      cp -a -- "$TX_FILES_DIR/$i" "$path"
    fi
  done
}

restore_original_files() {
  local i key path base
  for i in "${!MANAGED_DESTS[@]}"; do
    key="${MANAGED_KEYS[$i]}"
    path="${MANAGED_DESTS[$i]}"
    base="$PREINSTALL_DIR/files/$key"
    rm -f -- "$path"
    if [[ -e "$base.present" ]]; then
      install -d -m 0755 "$(dirname -- "$path")"
      cp -a -- "$base.content" "$path"
    fi
  done
}

restore_unit_state() {
  local unit="$1" enabled="$2" active="$3"
  if ((enabled)); then
    systemctl enable "$unit" >/dev/null 2>&1 || return 1
  else
    systemctl disable "$unit" >/dev/null 2>&1 || true
    if systemctl is-enabled --quiet "$unit" 2>/dev/null; then return 1; fi
  fi
  if ((active)); then
    systemctl start "$unit" >/dev/null 2>&1 || return 1
  else
    systemctl stop "$unit" >/dev/null 2>&1 || true
    if systemctl is-active --quiet "$unit" 2>/dev/null; then return 1; fi
  fi
}

rollback() {
  local rc="$1" i current_id current_invocation
  set +e
  if ((MUTATED == 0)); then return "$rc"; fi
  echo "Uninstall failed; restoring the pre-attempt installed state." >&2
  # Evidence rotation uses same-filesystem renames. Return any generation that
  # moved before a later failure so the normal rollback paths remain available.
  if ((EVIDENCE_PREINSTALL_MOVED)) && [[ -e "$EVIDENCE_DIR/preinstall" ]]; then
    mv -- "$EVIDENCE_DIR/preinstall" "$PREINSTALL_DIR" || \
      echo "Rollback could not return the preinstall evidence generation." >&2
  fi
  [[ -z "$EVIDENCE_DIR" ]] || rmdir "$EVIDENCE_DIR" 2>/dev/null || true
  systemctl stop vps-resource-guard.service vps-resource-guard-self-test.service >/dev/null 2>&1
  systemctl stop vps-resource-guard-docker-reconcile.timer vps-resource-guard-docker-reconcile.service >/dev/null 2>&1
  restore_transaction_files
  systemctl daemon-reload >/dev/null 2>&1
  user_systemctl daemon-reload >/dev/null 2>&1
  for ((i=0; i<${#SYSTEM_UNITS[@]}; i++)); do
    systemctl set-property --runtime "${SYSTEM_UNITS[$i]}" \
      "MemoryHigh=${TX_SYSTEM_HIGHS[$i]}" "MemoryMax=${TX_SYSTEM_MAXES[$i]}" >/dev/null 2>&1
  done
  for ((i=0; i<${#USER_UNITS[@]}; i++)); do
    user_systemctl set-property --runtime "${USER_UNITS[$i]}" \
      "MemoryHigh=${TX_USER_HIGHS[$i]}" "MemoryMax=${TX_USER_MAXES[$i]}" >/dev/null 2>&1
  done
  for ((i=0; i<${#DOCKER_CONTAINERS[@]}; i++)); do
    current_id="$(docker inspect --format '{{.Id}}' "${DOCKER_CONTAINERS[$i]}" 2>/dev/null)"
    if [[ -n "$current_id" && "$current_id" == "${TX_DOCKER_IDS[$i]}" ]] && \
      valid_size_value "${TX_DOCKER_HIGHS[$i]:-}" && \
      valid_size_value "${TX_DOCKER_MAXES[$i]:-}" && \
      valid_size_value "${TX_DOCKER_SWAP_MAXES[$i]:-}"; then
      scope="docker-${current_id}.scope"
      current_invocation="$(systemctl show "$scope" --property=InvocationID --value 2>/dev/null || true)"
      [[ "$current_invocation" == "${TX_DOCKER_INVOCATIONS[$i]:-}" ]] || continue
      systemctl set-property --runtime "$scope" \
        "MemoryHigh=${TX_DOCKER_HIGHS[$i]}" \
        "MemoryMax=${TX_DOCKER_MAXES[$i]}" \
        "MemorySwapMax=${TX_DOCKER_SWAP_MAXES[$i]}" >/dev/null 2>&1
    fi
  done
  systemctl restart systemd-journald.service >/dev/null 2>&1
  restore_unit_state vps-resource-guard.service "$TX_GUARD_ENABLED" "$TX_GUARD_ACTIVE"
  restore_unit_state vps-resource-guard-self-test.service "$TX_PROBE_ENABLED" "$TX_PROBE_ACTIVE"
  if [[ "$HOST_NAME" == meghadharma ]]; then
    restore_unit_state vps-resource-guard-docker-reconcile.service "$TX_RECONCILER_ENABLED" "$TX_RECONCILER_ACTIVE"
    restore_unit_state vps-resource-guard-docker-reconcile.timer "$TX_RECONCILER_TIMER_ENABLED" "$TX_RECONCILER_TIMER_ACTIVE"
  fi
  return "$rc"
}

finish() {
  local rc=$?
  trap - EXIT
  if ((rc != 0 && COMMITTED == 0)); then rollback "$rc" || true; fi
  rm -rf -- "$TX_DIR"
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT TERM

MUTATED=1
systemctl disable --now vps-resource-guard.service
guard_state="$(systemctl show vps-resource-guard.service --property=ActiveState --value)"
[[ "$guard_state" == inactive || "$guard_state" == failed ]] || {
  echo "Guard did not reach a verified inactive state ($guard_state)." >&2
  exit 1
}
systemctl stop vps-resource-guard-self-test.service 2>/dev/null || true
probe_state="$(systemctl show vps-resource-guard-self-test.service --property=ActiveState --value)"
[[ "$probe_state" == inactive || "$probe_state" == failed ]] || {
  echo "Probe did not reach a verified inactive state ($probe_state)." >&2
  exit 1
}
if [[ "$HOST_NAME" == meghadharma ]]; then
  systemctl disable --now vps-resource-guard-docker-reconcile.timer
  timer_state="$(systemctl show vps-resource-guard-docker-reconcile.timer --property=ActiveState --value)"
  [[ "$timer_state" == inactive || "$timer_state" == failed ]] || {
    echo "Docker reconciler timer did not reach a verified inactive state ($timer_state)." >&2
    exit 1
  }
  systemctl stop vps-resource-guard-docker-reconcile.service 2>/dev/null || true
  reconciler_state="$(systemctl show vps-resource-guard-docker-reconcile.service --property=ActiveState --value)"
  [[ "$reconciler_state" == inactive || "$reconciler_state" == failed ]] || {
    echo "Docker reconciler did not reach a verified inactive state ($reconciler_state)." >&2
    exit 1
  }
fi

if [[ "$HOST_NAME" == meghadharma ]]; then
  # This re-resolves every currently live container scope while the operation
  # lock is held. A missing/malformed ID+InvocationID baseline aborts instead of
  # silently leaving a capped scope behind.
  VPS_RESOURCE_GUARD_LOCK_HELD=1 "$RECONCILER_PATH" --restore-current
fi

restore_original_files
systemctl daemon-reload
if ((${#USER_UNITS[@]})); then user_systemctl daemon-reload; fi
for ((i=0; i<${#SYSTEM_UNITS[@]}; i++)); do
  systemctl set-property --runtime "${SYSTEM_UNITS[$i]}" \
    "MemoryHigh=${RESTORE_SYSTEM_HIGHS[$i]}" "MemoryMax=${RESTORE_SYSTEM_MAXES[$i]}"
  assert_system_property "${SYSTEM_UNITS[$i]}" MemoryHigh "${RESTORE_SYSTEM_HIGHS[$i]}"
  assert_system_property "${SYSTEM_UNITS[$i]}" MemoryMax "${RESTORE_SYSTEM_MAXES[$i]}"
done
for ((i=0; i<${#USER_UNITS[@]}; i++)); do
  user_systemctl set-property --runtime "${USER_UNITS[$i]}" \
    "MemoryHigh=${RESTORE_USER_HIGHS[$i]}" "MemoryMax=${RESTORE_USER_MAXES[$i]}"
  assert_user_property "${USER_UNITS[$i]}" MemoryHigh "${RESTORE_USER_HIGHS[$i]}"
  assert_user_property "${USER_UNITS[$i]}" MemoryMax "${RESTORE_USER_MAXES[$i]}"
done
systemctl restart systemd-journald.service
restore_unit_state vps-resource-guard.service "$RESTORE_GUARD_ENABLED" "$RESTORE_GUARD_ACTIVE"
restore_unit_state vps-resource-guard-self-test.service "$RESTORE_PROBE_ENABLED" "$RESTORE_PROBE_ACTIVE"
if [[ "$HOST_NAME" == meghadharma ]]; then
  restore_unit_state vps-resource-guard-docker-reconcile.service "$RESTORE_RECONCILER_ENABLED" "$RESTORE_RECONCILER_ACTIVE"
  restore_unit_state vps-resource-guard-docker-reconcile.timer "$RESTORE_RECONCILER_TIMER_ENABLED" "$RESTORE_RECONCILER_TIMER_ACTIVE"
fi

evidence_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_DIR="/var/lib/vps-resource-guard/uninstall-evidence-$evidence_stamp-$$"
[[ ! -e "$EVIDENCE_DIR" ]]
install -d -m 0700 "$EVIDENCE_DIR"
if [[ "$HOST_NAME" == meghadharma ]]; then
  [[ -d "$SCOPE_BASELINE_DIR" && ! -L "$SCOPE_BASELINE_DIR" ]] || {
    echo "Docker scope baseline generation disappeared before uninstall commit." >&2
    exit 1
  }
fi
# Scope baselines live inside PREINSTALL_DIR, so this one same-filesystem rename
# atomically rotates the file/property inverse and Docker incarnation inverse as
# a single generation. There is no crash window with only one half moved.
EVIDENCE_PREINSTALL_MOVED=1
mv -- "$PREINSTALL_DIR" "$EVIDENCE_DIR/preinstall"
# Persist the generation-root rename before declaring the uninstall committed.
sync -f "$STATE_DIR"
COMMITTED=1

if ((PURGE)); then
  rm -f -- /var/lib/vps-resource-guard/state.json
  rm -f -- /var/lib/vps-resource-guard/state.json.corrupt
  rm -f -- /var/log/vps-resource-guard/receipts.jsonl
  rm -f -- /var/log/vps-resource-guard/receipts.jsonl.1
  rm -rf -- "$EVIDENCE_DIR"
  # Keep operation.lock and state.json.lock as stable inode namespaces. Removing
  # either while another process waits can split serialization across inodes.
  rmdir /var/lib/vps-resource-guard 2>/dev/null || true
  rmdir /var/log/vps-resource-guard 2>/dev/null || true
fi

echo "Uninstalled vps-resource-guard and restored validated preinstall settings."
if ((PURGE == 0)); then echo "Restore evidence retained at $EVIDENCE_DIR."; fi
echo "Journal segments removed by the install-time vacuum cannot be restored."
