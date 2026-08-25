#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  echo "Usage: $0 --host rushabdev|agni|meghadharma [--dry-run]" >&2
}

HOST_NAME=""
DRY_RUN=0
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

SYSTEM_UNITS=()
SYSTEM_HIGHS=()
SYSTEM_MAXES=()
SYSTEM_HIGH_BYTES=()
SYSTEM_MAX_BYTES=()
USER_UNITS=()
USER_HIGHS=()
USER_MAXES=()
USER_HIGH_BYTES=()
USER_MAX_BYTES=()
DOCKER_CONTAINERS=()
DOCKER_HIGHS=()
DOCKER_MAXES=()
DOCKER_SWAP_MAXES=()
DOCKER_MAX_BYTES=()
DOCKER_SWAP_MAX_BYTES=()
HEADROOM_BYTES=134217728

case "$HOST_NAME" in
  rushabdev)
    SYSTEM_UNITS=("ollama.service")
    SYSTEM_HIGHS=("640M")
    SYSTEM_MAXES=("800M")
    SYSTEM_HIGH_BYTES=(671088640)
    SYSTEM_MAX_BYTES=(838860800)
    USER_UNITS=("hermes-gateway.service" "openclaw-gateway.service")
    USER_HIGHS=("800M" "512M")
    USER_MAXES=("1200M" "768M")
    USER_HIGH_BYTES=(838860800 536870912)
    USER_MAX_BYTES=(1258291200 805306368)
    ;;
  agni)
    SYSTEM_UNITS=("ollama.service")
    SYSTEM_HIGHS=("4G")
    SYSTEM_MAXES=("5G")
    SYSTEM_HIGH_BYTES=(4294967296)
    SYSTEM_MAX_BYTES=(5368709120)
    USER_UNITS=("hermes-gateway.service")
    USER_HIGHS=("1500M")
    USER_MAXES=("2G")
    USER_HIGH_BYTES=(1572864000)
    USER_MAX_BYTES=(2147483648)
    ;;
  meghadharma)
    DOCKER_CONTAINERS=(
      "dharma-command-backend"
      "hermes"
      "dharma-swarm"
      "dharma-command-edge"
    )
    DOCKER_HIGHS=("2G" "1500M" "768M" "384M")
    DOCKER_MAXES=("2560M" "2G" "1G" "512M")
    DOCKER_SWAP_MAXES=("640M" "768M" "256M" "192M")
    DOCKER_MAX_BYTES=(2684354560 2147483648 1073741824 536870912)
    DOCKER_SWAP_MAX_BYTES=(671088640 805306368 268435456 201326592)
    ;;
  *)
    usage
    exit 2
    ;;
esac

SCRIPT_DIR="$(
  unset CDPATH
  cd -- "$(dirname -- "$0")"
  pwd -P
)"
REPO_ROOT="$(
  unset CDPATH
  cd -- "$SCRIPT_DIR/../.."
  pwd -P
)"
GUARD_SOURCE="$REPO_ROOT/scripts/ops/vps_resource_guard.py"
CONFIG_SOURCE="$SCRIPT_DIR/configs/$HOST_NAME.toml"
UNIT_SOURCE="$SCRIPT_DIR/systemd/vps-resource-guard.service"
PROBE_UNIT_SOURCE="$SCRIPT_DIR/systemd/vps-resource-guard-self-test.service"
JOURNALD_SOURCE="$SCRIPT_DIR/systemd/journald-resource-bounds.conf"
README_SOURCE="$SCRIPT_DIR/README.md"
RECONCILER_SOURCE="$SCRIPT_DIR/scripts/reconcile-meghadharma-docker-limits.sh"
RECONCILER_UNIT_SOURCE="$SCRIPT_DIR/systemd/vps-resource-guard-docker-reconcile.service"
RECONCILER_TIMER_SOURCE="$SCRIPT_DIR/systemd/vps-resource-guard-docker-reconcile.timer"
PYTHON_BIN="${PYTHON_BIN:-python3}"

MANAGED_KEYS=(guard config service probe-service journald readme)
MANAGED_SOURCES=(
  "$GUARD_SOURCE"
  "$CONFIG_SOURCE"
  "$UNIT_SOURCE"
  "$PROBE_UNIT_SOURCE"
  "$JOURNALD_SOURCE"
  "$README_SOURCE"
)
MANAGED_DESTS=(
  /usr/local/lib/vps-resource-guard/vps_resource_guard.py
  /etc/vps-resource-guard/config.toml
  /etc/systemd/system/vps-resource-guard.service
  /etc/systemd/system/vps-resource-guard-self-test.service
  /etc/systemd/journald.conf.d/zz-vps-resource-guard.conf
  /usr/local/share/doc/vps-resource-guard/README.md
)
MANAGED_MODES=(0755 0644 0644 0644 0644 0644)

for ((unit_i=0; unit_i<${#SYSTEM_UNITS[@]}; unit_i++)); do
  unit="${SYSTEM_UNITS[$unit_i]}"
  unit_stem="${unit%.service}"
  MANAGED_KEYS+=("system-${unit_stem}")
  MANAGED_SOURCES+=("$SCRIPT_DIR/systemd/target-limits/$HOST_NAME/$unit.conf")
  MANAGED_DESTS+=("/etc/systemd/system/$unit.d/90-vps-resource-guard.conf")
  MANAGED_MODES+=(0644)
done
for ((unit_i=0; unit_i<${#USER_UNITS[@]}; unit_i++)); do
  unit="${USER_UNITS[$unit_i]}"
  unit_stem="${unit%.service}"
  MANAGED_KEYS+=("user-${unit_stem}")
  MANAGED_SOURCES+=("$SCRIPT_DIR/systemd/target-limits/$HOST_NAME/$unit.conf")
  MANAGED_DESTS+=("/root/.config/systemd/user/$unit.d/90-vps-resource-guard.conf")
  MANAGED_MODES+=(0644)
done
if [[ "$HOST_NAME" == meghadharma ]]; then
  MANAGED_KEYS+=(docker-reconciler docker-reconciler-service docker-reconciler-timer)
  MANAGED_SOURCES+=(
    "$RECONCILER_SOURCE"
    "$RECONCILER_UNIT_SOURCE"
    "$RECONCILER_TIMER_SOURCE"
  )
  MANAGED_DESTS+=(
    /usr/local/lib/vps-resource-guard/reconcile-meghadharma-docker-limits.sh
    /etc/systemd/system/vps-resource-guard-docker-reconcile.service
    /etc/systemd/system/vps-resource-guard-docker-reconcile.timer
  )
  MANAGED_MODES+=(0755 0644 0644)
fi

for source_file in "${MANAGED_SOURCES[@]}"; do
  [[ -f "$source_file" ]] || {
    echo "Missing source file: $source_file" >&2
    exit 2
  }
done

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' || {
  echo "Python 3.11 or newer is required (set PYTHON_BIN if needed)." >&2
  exit 2
}
"$PYTHON_BIN" "$GUARD_SOURCE" --config "$CONFIG_SOURCE" --validate-config

if ((DRY_RUN)); then
  echo "DRY-RUN: validated staged sources for $HOST_NAME"
  for i in "${!MANAGED_DESTS[@]}"; do
    printf 'DRY-RUN: install -m %s %q %q (save/restore any collision)\n' \
      "${MANAGED_MODES[$i]}" "${MANAGED_SOURCES[$i]}" "${MANAGED_DESTS[$i]}"
  done
  printf 'DRY-RUN: verify exact hostname binding with --verify-host\n'
  for ((i=0; i<${#SYSTEM_UNITS[@]}; i++)); do
    printf 'DRY-RUN: systemctl set-property --runtime %q MemoryHigh=%q MemoryMax=%q\n' \
      "${SYSTEM_UNITS[$i]}" "${SYSTEM_HIGHS[$i]}" "${SYSTEM_MAXES[$i]}"
  done
  for ((i=0; i<${#USER_UNITS[@]}; i++)); do
    printf 'DRY-RUN: systemctl --user set-property --runtime %q MemoryHigh=%q MemoryMax=%q\n' \
      "${USER_UNITS[$i]}" "${USER_HIGHS[$i]}" "${USER_MAXES[$i]}"
  done
  for ((i=0; i<${#DOCKER_CONTAINERS[@]}; i++)); do
    printf 'DRY-RUN: atomically baseline exact Docker ID + scope InvocationID for %q, then set MemoryHigh=%q MemoryMax=%q MemorySwapMax=%q\n' \
      "${DOCKER_CONTAINERS[$i]}" "${DOCKER_HIGHS[$i]}" "${DOCKER_MAXES[$i]}" \
      "${DOCKER_SWAP_MAXES[$i]}"
  done
  echo "DRY-RUN: reload managers, restart journald, vacuum journal to 512M, restart and self-test guard"
  exit 0
fi

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run as root, or use --dry-run." >&2
  exit 2
fi

for command_name in install systemctl systemd-analyze journalctl mktemp basename cp mv rm awk flock sha256sum stat sync; do
  command -v "$command_name" >/dev/null || {
    echo "Required command not found: $command_name" >&2
    exit 2
  }
done
if ((${#DOCKER_CONTAINERS[@]})); then
  command -v docker >/dev/null || { echo "Required command not found: docker" >&2; exit 2; }
fi

export XDG_RUNTIME_DIR=/run/user/0
STATE_DIR=/var/lib/vps-resource-guard
LOCK_FILE="$STATE_DIR/operation.lock"
SCOPE_BASELINE_DIR="$STATE_DIR/preinstall/docker-scope-baselines"
[[ ! -L "$STATE_DIR" ]] || { echo "Refusing symlink at guard state directory." >&2; exit 2; }
install -d -o root -g root -m 0700 "$STATE_DIR"
[[ ! -L "$LOCK_FILE" && ( ! -e "$LOCK_FILE" || -f "$LOCK_FILE" ) ]] || {
  echo "Refusing malformed guard operation lock." >&2
  exit 2
}
exec 9>"$LOCK_FILE"
flock -w 60 9 || { echo "Timed out waiting for the VPS resource guard operation lock." >&2; exit 1; }
PREINSTALL_DIR=/var/lib/vps-resource-guard/preinstall
if [[ "$HOST_NAME" == meghadharma && \
  ( -e "$PREINSTALL_DIR/files/dharma-swarm-compose-override.present" || \
    -e "$PREINSTALL_DIR/files/dharma-swarm-compose-override.absent" ) ]]; then
  echo "Legacy Compose-managing guard detected; run that installed version's uninstaller before installing this scope-only policy." >&2
  exit 2
fi
TX_DIR="$(mktemp -d /var/lib/vps-resource-guard-install.XXXXXX)"
STAGE_DIR="$TX_DIR/stage"
TX_FILES_DIR="$TX_DIR/files"
install -d -m 0700 "$STAGE_DIR" "$TX_FILES_DIR"
SCOPE_BASELINE_WAS_PRESENT=0
if [[ "$HOST_NAME" == meghadharma && -e "$SCOPE_BASELINE_DIR" ]]; then
  [[ -d "$SCOPE_BASELINE_DIR" && ! -L "$SCOPE_BASELINE_DIR" ]] || {
    echo "Refusing malformed Docker scope baseline directory." >&2
    exit 2
  }
  cp -a -- "$SCOPE_BASELINE_DIR" "$TX_DIR/docker-scope-baselines"
  SCOPE_BASELINE_WAS_PRESENT=1
fi

TX_DESTS=()
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
GUARD_WAS_ACTIVE=0
GUARD_WAS_ENABLED=0
PROBE_WAS_ACTIVE=0
PROBE_WAS_ENABLED=0
RECONCILER_WAS_ACTIVE=0
RECONCILER_WAS_ENABLED=0
RECONCILER_TIMER_WAS_ACTIVE=0
RECONCILER_TIMER_WAS_ENABLED=0
JOURNALD_TOUCHED=0
GUARD_TOUCHED=0
PROBE_TOUCHED=0
SCOPES_TOUCHED=0
MUTATED=0
COMMITTED=0
BASELINE_CREATED=0

user_systemctl() {
  XDG_RUNTIME_DIR=/run/user/0 systemctl --user "$@"
}

valid_size_value() {
  [[ "$1" =~ ^([0-9]+|infinity)$ ]]
}

assert_system_property() {
  local unit="$1"
  local property="$2"
  local expected="$3"
  local actual
  actual="$(systemctl show "$unit" --property="$property" --value)"
  [[ "$actual" == "$expected" ]] || {
    echo "$unit $property=$actual, expected $expected." >&2
    return 1
  }
}

assert_user_property() {
  local unit="$1"
  local property="$2"
  local expected="$3"
  local actual
  actual="$(user_systemctl show "$unit" --property="$property" --value)"
  [[ "$actual" == "$expected" ]] || {
    echo "root user $unit $property=$actual, expected $expected." >&2
    return 1
  }
}

save_value_once() {
  local key="$1"
  local value="$2"
  local path="$PREINSTALL_DIR/values/$key"
  [[ -e "$path" ]] && return 0
  printf '%s\n' "$value" >"$path"
  chmod 0600 "$path"
}

saved_value_matches() {
  local key="$1"
  local pattern="$2"
  local path="$PREINSTALL_DIR/values/$key"
  local value
  [[ -r "$path" ]] || return 1
  value="$(<"$path")"
  [[ "$value" =~ $pattern ]]
}

validate_existing_baseline() {
  local i key base metadata evidence_root evidence_key evidence_entry artifact artifact_name found_key
  [[ -d "$PREINSTALL_DIR" && ! -L "$PREINSTALL_DIR" ]] || return 1
  metadata="$(stat -c '%u:%g:%a' "$PREINSTALL_DIR")"
  [[ "$metadata" == 0:0:700 ]] || return 1
  [[ -d "$PREINSTALL_DIR/files" && ! -L "$PREINSTALL_DIR/files" && \
     -d "$PREINSTALL_DIR/values" && ! -L "$PREINSTALL_DIR/values" && \
     -f "$PREINSTALL_DIR/host" && ! -L "$PREINSTALL_DIR/host" ]] || return 1
  [[ "$(<"$PREINSTALL_DIR/host")" == "$HOST_NAME" ]] || return 1
  evidence_root="$PREINSTALL_DIR/superseded-files"
  if [[ -e "$evidence_root" || -L "$evidence_root" ]]; then
    [[ -d "$evidence_root" && ! -L "$evidence_root" &&
       "$(stat -c '%u:%g:%a' "$evidence_root")" == 0:0:700 ]] || return 1
    for evidence_entry in "$evidence_root"/*; do
      [[ -e "$evidence_entry" || -L "$evidence_entry" ]] || continue
      evidence_key="$(basename -- "$evidence_entry")"
      found_key=0
      for key in "${MANAGED_KEYS[@]}"; do
        if [[ "$evidence_key" == "$key" ]]; then found_key=1; break; fi
      done
      ((found_key)) || return 1
      [[ -d "$evidence_entry" && ! -L "$evidence_entry" &&
         "$(stat -c '%u:%g:%a' "$evidence_entry")" == 0:0:700 ]] || return 1
      for artifact in "$evidence_entry"/*; do
        [[ -e "$artifact" || -L "$artifact" ]] || continue
        artifact_name="$(basename -- "$artifact")"
        [[ "$artifact_name" =~ ^[0-9a-f]{64}$ &&
           -f "$artifact" && ! -L "$artifact" &&
           "$(stat -c '%u:%g:%a' "$artifact")" == 0:0:600 &&
           "$(sha256sum "$artifact" | awk '{print $1}')" == "$artifact_name" ]] || return 1
      done
    done
  fi
  for i in "${!MANAGED_KEYS[@]}"; do
    key="${MANAGED_KEYS[$i]}"
    base="$PREINSTALL_DIR/files/$key"
    if [[ -e "$base.present" ]]; then
      [[ ! -e "$base.absent" && -f "$base.content" && ! -L "$base.content" ]] || return 1
    elif [[ -e "$base.absent" ]]; then
      [[ ! -e "$base.present" && ! -e "$base.content" ]] || return 1
    else
      return 1
    fi
  done
  saved_value_matches guard.was-active '^[01]$' || return 1
  saved_value_matches guard.was-enabled '^[01]$' || return 1
  saved_value_matches probe.was-active '^[01]$' || return 1
  saved_value_matches probe.was-enabled '^[01]$' || return 1
  if [[ "$HOST_NAME" == meghadharma ]]; then
    saved_value_matches reconciler.was-active '^[01]$' || return 1
    saved_value_matches reconciler.was-enabled '^[01]$' || return 1
    saved_value_matches reconciler-timer.was-active '^[01]$' || return 1
    saved_value_matches reconciler-timer.was-enabled '^[01]$' || return 1
  fi
  for ((i=0; i<${#SYSTEM_UNITS[@]}; i++)); do
    key="system.${SYSTEM_UNITS[$i]}"
    saved_value_matches "$key.MemoryHigh" '^([0-9]+|infinity)$' || return 1
    saved_value_matches "$key.MemoryMax" '^([0-9]+|infinity)$' || return 1
  done
  for ((i=0; i<${#USER_UNITS[@]}; i++)); do
    key="user.${USER_UNITS[$i]}"
    saved_value_matches "$key.MemoryHigh" '^([0-9]+|infinity)$' || return 1
    saved_value_matches "$key.MemoryMax" '^([0-9]+|infinity)$' || return 1
  done
  return 0
}

record_original_file() {
  local key="$1"
  local path="$2"
  local base="$PREINSTALL_DIR/files/$key"
  if [[ -e "$base.present" || -e "$base.absent" ]]; then
    return 0
  fi
  if [[ -L "$path" ]]; then
    echo "Refusing to replace symlink at managed path: $path" >&2
    return 1
  fi
  if [[ -e "$path" ]]; then
    [[ -f "$path" ]] || {
      echo "Refusing non-regular managed-path collision: $path" >&2
      return 1
    }
    cp -a -- "$path" "$base.content"
    : >"$base.present"
  else
    : >"$base.absent"
  fi
  chmod 0600 "$base.present" "$base.absent" 2>/dev/null || true
}

capture_transaction_file() {
  local path="$1"
  local index="${#TX_DESTS[@]}"
  if [[ -L "$path" ]]; then
    echo "Refusing to replace symlink at managed path: $path" >&2
    return 1
  fi
  TX_DESTS+=("$path")
  if [[ -e "$path" ]]; then
    [[ -f "$path" ]] || {
      echo "Refusing non-regular managed-path collision: $path" >&2
      return 1
    }
    cp -a -- "$path" "$TX_FILES_DIR/$index"
    TX_PRESENT+=(1)
  else
    TX_PRESENT+=(0)
  fi
}

ensure_private_evidence_directory() {
  local path="$1" parent="$2"
  [[ -d "$parent" && ! -L "$parent" ]] || return 1
  if [[ -e "$path" || -L "$path" ]]; then
    [[ -d "$path" && ! -L "$path" &&
       "$(stat -c '%u:%g:%a' "$path")" == 0:0:700 ]]
    return
  fi
  install -d -o root -g root -m 0700 "$path"
  [[ -d "$path" && ! -L "$path" &&
     "$(stat -c '%u:%g:%a' "$path")" == 0:0:700 ]] || return 1
  sync -f "$parent"
}

preserve_superseded_file() {
  local key="$1" current_path="$2" replacement_path="$3"
  local current_digest replacement_digest evidence_root evidence_dir destination partial
  [[ -f "$current_path" && ! -L "$current_path" ]] || return 0
  current_digest="$(sha256sum "$current_path" | awk '{print $1}')"
  replacement_digest="$(sha256sum "$replacement_path" | awk '{print $1}')"
  [[ "$current_digest" =~ ^[0-9a-f]{64}$ && "$replacement_digest" =~ ^[0-9a-f]{64}$ ]] || return 1
  [[ "$current_digest" != "$replacement_digest" ]] || return 0
  evidence_root="$PREINSTALL_DIR/superseded-files"
  ensure_private_evidence_directory "$evidence_root" "$PREINSTALL_DIR" || return 1
  evidence_dir="$evidence_root/$key"
  ensure_private_evidence_directory "$evidence_dir" "$evidence_root" || return 1
  destination="$evidence_dir/$current_digest"
  if [[ -e "$destination" ]]; then
    [[ -f "$destination" && ! -L "$destination" && \
       "$(sha256sum "$destination" | awk '{print $1}')" == "$current_digest" ]] || return 1
    return 0
  fi
  partial="$evidence_dir/.${current_digest}.partial"
  [[ ! -L "$partial" && ( ! -e "$partial" || -f "$partial" ) ]] || return 1
  rm -f -- "$partial"
  install -o root -g root -m 0600 "$current_path" "$partial"
  [[ "$(sha256sum "$partial" | awk '{print $1}')" == "$current_digest" ]] || {
    rm -f -- "$partial"
    return 1
  }
  sync -f "$partial"
  mv -- "$partial" "$destination"
  sync -f "$evidence_dir"
  echo "Preserved superseded managed file evidence: key=$key sha256=$current_digest"
}

restore_transaction_files() {
  local i path
  for ((i=${#TX_DESTS[@]} - 1; i >= 0; i--)); do
    path="${TX_DESTS[$i]}"
    rm -f -- "$path"
    if [[ "${TX_PRESENT[$i]}" == 1 ]]; then
      install -d -m 0755 "$(dirname -- "$path")"
      cp -a -- "$TX_FILES_DIR/$i" "$path"
    fi
  done
}

rollback() {
  local original_rc="$1"
  local i
  set +e
  if ((MUTATED == 0)); then
    return "$original_rc"
  fi
  echo "Install failed; restoring pre-attempt files and runtime limits." >&2
  if ((GUARD_TOUCHED)); then systemctl stop vps-resource-guard.service >/dev/null 2>&1; fi
  if ((PROBE_TOUCHED)); then systemctl stop vps-resource-guard-self-test.service >/dev/null 2>&1; fi
  # A timer firing while this installer owns the operation lock can leave its
  # oneshot queued in flock. Stop both units unconditionally before restoring
  # files/baselines so no queued process can reapply caps after rollback.
  if [[ "$HOST_NAME" == meghadharma ]]; then
    systemctl stop vps-resource-guard-docker-reconcile.timer \
      vps-resource-guard-docker-reconcile.service >/dev/null 2>&1
  fi
  if ((SCOPES_TOUCHED)); then
    if VPS_RESOURCE_GUARD_LOCK_HELD=1 \
      /usr/local/lib/vps-resource-guard/reconcile-meghadharma-docker-limits.sh \
      --restore-current >/dev/null 2>&1; then
      rm -rf -- "$SCOPE_BASELINE_DIR"
      if ((SCOPE_BASELINE_WAS_PRESENT)); then
        cp -a -- "$TX_DIR/docker-scope-baselines" "$SCOPE_BASELINE_DIR"
      fi
    else
      # Never discard the only inverse for an incarnation that may still carry
      # a runtime property. Leave the current generation in place for recovery
      # by this package or a later operator run.
      echo "Rollback could not restore every exact Docker scope baseline; preserving the active baseline generation." >&2
    fi
    for ((i=0; i<${#DOCKER_CONTAINERS[@]}; i++)); do
      current_id="$(docker inspect --format '{{.Id}}' "${DOCKER_CONTAINERS[$i]}" 2>/dev/null || true)"
      [[ "$current_id" == "${TX_DOCKER_IDS[$i]:-}" ]] || continue
      scope="docker-${current_id}.scope"
      current_invocation="$(systemctl show "$scope" --property=InvocationID --value 2>/dev/null || true)"
      [[ "$current_invocation" == "${TX_DOCKER_INVOCATIONS[$i]:-}" ]] || continue
      if ! systemctl set-property --runtime "$scope" \
        "MemoryHigh=${TX_DOCKER_HIGHS[$i]}" \
        "MemoryMax=${TX_DOCKER_MAXES[$i]}" \
        "MemorySwapMax=${TX_DOCKER_SWAP_MAXES[$i]}" >/dev/null 2>&1; then
        echo "Rollback fallback could not restore ${DOCKER_CONTAINERS[$i]}." >&2
        continue
      fi
      actual_high="$(systemctl show "$scope" --property=MemoryHigh --value 2>/dev/null || true)"
      actual_max="$(systemctl show "$scope" --property=MemoryMax --value 2>/dev/null || true)"
      actual_swap_max="$(systemctl show "$scope" --property=MemorySwapMax --value 2>/dev/null || true)"
      if [[ "$actual_high" != "${TX_DOCKER_HIGHS[$i]}" || \
            "$actual_max" != "${TX_DOCKER_MAXES[$i]}" || \
            "$actual_swap_max" != "${TX_DOCKER_SWAP_MAXES[$i]}" ]]; then
        echo "Rollback fallback readback failed for ${DOCKER_CONTAINERS[$i]}." >&2
      fi
    done
  fi
  restore_transaction_files
  systemctl daemon-reload >/dev/null 2>&1
  user_systemctl daemon-reload >/dev/null 2>&1

  for ((i=0; i<${#SYSTEM_UNITS[@]}; i++)); do
    if valid_size_value "${TX_SYSTEM_HIGHS[$i]:-}" && valid_size_value "${TX_SYSTEM_MAXES[$i]:-}"; then
      systemctl set-property --runtime "${SYSTEM_UNITS[$i]}" \
        "MemoryHigh=${TX_SYSTEM_HIGHS[$i]}" "MemoryMax=${TX_SYSTEM_MAXES[$i]}" >/dev/null 2>&1
    fi
  done
  for ((i=0; i<${#USER_UNITS[@]}; i++)); do
    if valid_size_value "${TX_USER_HIGHS[$i]:-}" && valid_size_value "${TX_USER_MAXES[$i]:-}"; then
      user_systemctl set-property --runtime "${USER_UNITS[$i]}" \
        "MemoryHigh=${TX_USER_HIGHS[$i]}" "MemoryMax=${TX_USER_MAXES[$i]}" >/dev/null 2>&1
    fi
  done
  if ((GUARD_TOUCHED)); then
    if ((GUARD_WAS_ENABLED)); then
      systemctl enable vps-resource-guard.service >/dev/null 2>&1
    else
      systemctl disable vps-resource-guard.service >/dev/null 2>&1
    fi
    if ((GUARD_WAS_ACTIVE)); then
      systemctl start vps-resource-guard.service >/dev/null 2>&1
    fi
  fi
  if ((PROBE_TOUCHED)); then
    if ((PROBE_WAS_ENABLED)); then
      systemctl enable vps-resource-guard-self-test.service >/dev/null 2>&1
    else
      systemctl disable vps-resource-guard-self-test.service >/dev/null 2>&1
    fi
    if ((PROBE_WAS_ACTIVE)); then
      systemctl start vps-resource-guard-self-test.service >/dev/null 2>&1
    fi
  fi
  if [[ "$HOST_NAME" == meghadharma ]]; then
    if ((RECONCILER_WAS_ENABLED)); then
      systemctl enable vps-resource-guard-docker-reconcile.service >/dev/null 2>&1
    else
      systemctl disable vps-resource-guard-docker-reconcile.service >/dev/null 2>&1
    fi
    if ((RECONCILER_WAS_ACTIVE)); then
      systemctl start vps-resource-guard-docker-reconcile.service >/dev/null 2>&1
    fi
    if ((RECONCILER_TIMER_WAS_ENABLED)); then
      systemctl enable vps-resource-guard-docker-reconcile.timer >/dev/null 2>&1
    else
      systemctl disable vps-resource-guard-docker-reconcile.timer >/dev/null 2>&1
    fi
    if ((RECONCILER_TIMER_WAS_ACTIVE)); then
      systemctl start vps-resource-guard-docker-reconcile.timer >/dev/null 2>&1
    fi
  fi
  if ((JOURNALD_TOUCHED)); then
    systemctl restart systemd-journald.service >/dev/null 2>&1
  fi
  return "$original_rc"
}

finish() {
  local rc=$?
  trap - EXIT
  if ((rc != 0 && COMMITTED == 0)); then
    rollback "$rc" || true
    if ((MUTATED == 0 && BASELINE_CREATED)); then
      rm -rf -- "$PREINSTALL_DIR"
    fi
  fi
  rm -rf -- "$TX_DIR"
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT TERM

# Preflight the live targets before writing anything. A hard limit is refused
# if the target already uses at least that much memory.
"$PYTHON_BIN" "$GUARD_SOURCE" --config "$CONFIG_SOURCE" --verify-host
if systemctl is-active --quiet vps-resource-guard.service; then GUARD_WAS_ACTIVE=1; fi
if systemctl is-enabled --quiet vps-resource-guard.service 2>/dev/null; then GUARD_WAS_ENABLED=1; fi
if systemctl is-active --quiet vps-resource-guard-self-test.service; then PROBE_WAS_ACTIVE=1; fi
if systemctl is-enabled --quiet vps-resource-guard-self-test.service 2>/dev/null; then PROBE_WAS_ENABLED=1; fi
if [[ "$HOST_NAME" == meghadharma ]]; then
  if systemctl is-active --quiet vps-resource-guard-docker-reconcile.service; then RECONCILER_WAS_ACTIVE=1; fi
  if systemctl is-enabled --quiet vps-resource-guard-docker-reconcile.service 2>/dev/null; then RECONCILER_WAS_ENABLED=1; fi
  if systemctl is-active --quiet vps-resource-guard-docker-reconcile.timer; then RECONCILER_TIMER_WAS_ACTIVE=1; fi
  if systemctl is-enabled --quiet vps-resource-guard-docker-reconcile.timer 2>/dev/null; then RECONCILER_TIMER_WAS_ENABLED=1; fi
fi

for ((i=0; i<${#SYSTEM_UNITS[@]}; i++)); do
  unit="${SYSTEM_UNITS[$i]}"
  [[ "$(systemctl show "$unit" --property=LoadState --value)" == loaded ]] || {
    echo "Required system unit is not loaded: $unit" >&2
    exit 2
  }
  [[ "$(systemctl show "$unit" --property=ActiveState --value)" == active ]] || {
    echo "Required system unit is not active: $unit" >&2
    exit 2
  }
  current="$(systemctl show "$unit" --property=MemoryCurrent --value)"
  peak="$(systemctl show "$unit" --property=MemoryPeak --value)"
  if [[ ! "$current" =~ ^[0-9]+$ || ! "$peak" =~ ^[0-9]+$ ]]; then
    echo "$unit does not expose numeric MemoryCurrent and MemoryPeak." >&2
    exit 2
  fi
  if ((current + HEADROOM_BYTES > SYSTEM_MAX_BYTES[i] || peak + HEADROOM_BYTES > SYSTEM_MAX_BYTES[i])); then
    echo "$unit current=$current peak=$peak lacks 128MiB headroom below proposed MemoryMax=${SYSTEM_MAXES[$i]}." >&2
    exit 2
  fi
  TX_SYSTEM_HIGHS+=("$(systemctl show "$unit" --property=MemoryHigh --value)")
  TX_SYSTEM_MAXES+=("$(systemctl show "$unit" --property=MemoryMax --value)")
  valid_size_value "${TX_SYSTEM_HIGHS[$i]}" && valid_size_value "${TX_SYSTEM_MAXES[$i]}" || exit 2
done

for ((i=0; i<${#USER_UNITS[@]}; i++)); do
  unit="${USER_UNITS[$i]}"
  [[ "$(user_systemctl show "$unit" --property=LoadState --value)" == loaded ]] || {
    echo "Required root user unit is not loaded: $unit" >&2
    exit 2
  }
  [[ "$(user_systemctl show "$unit" --property=ActiveState --value)" == active ]] || {
    echo "Required root user unit is not active: $unit" >&2
    exit 2
  }
  current="$(user_systemctl show "$unit" --property=MemoryCurrent --value)"
  peak="$(user_systemctl show "$unit" --property=MemoryPeak --value)"
  if [[ ! "$current" =~ ^[0-9]+$ || ! "$peak" =~ ^[0-9]+$ ]]; then
    echo "$unit does not expose numeric MemoryCurrent and MemoryPeak." >&2
    exit 2
  fi
  if ((current + HEADROOM_BYTES > USER_MAX_BYTES[i] || peak + HEADROOM_BYTES > USER_MAX_BYTES[i])); then
    echo "$unit current=$current peak=$peak lacks 128MiB headroom below proposed MemoryMax=${USER_MAXES[$i]}." >&2
    exit 2
  fi
  TX_USER_HIGHS+=("$(user_systemctl show "$unit" --property=MemoryHigh --value)")
  TX_USER_MAXES+=("$(user_systemctl show "$unit" --property=MemoryMax --value)")
  valid_size_value "${TX_USER_HIGHS[$i]}" && valid_size_value "${TX_USER_MAXES[$i]}" || exit 2
done

for ((i=0; i<${#DOCKER_CONTAINERS[@]}; i++)); do
  container="${DOCKER_CONTAINERS[$i]}"
  docker inspect "$container" >/dev/null
  container_id="$(docker inspect --format '{{.Id}}' "$container")"
  running="$(docker inspect --format '{{.State.Running}}' "$container")"
  [[ "$container_id" =~ ^[0-9a-f]{64}$ && "$running" == true ]] || {
    echo "Could not resolve the running Docker container $container." >&2
    exit 2
  }
  scope="docker-${container_id}.scope"
  [[ "$(systemctl show "$scope" --property=LoadState --value)" == loaded && \
    "$(systemctl show "$scope" --property=ActiveState --value)" == active ]] || {
    echo "Required Docker scope is not loaded and active: $scope" >&2
    exit 2
  }
  invocation_id="$(systemctl show "$scope" --property=InvocationID --value)"
  [[ "$invocation_id" =~ ^[0-9a-f]{32}$ ]] || {
    echo "Required Docker scope has no trustworthy InvocationID: $scope" >&2
    exit 2
  }
  scope_high="$(systemctl show "$scope" --property=MemoryHigh --value)"
  scope_max="$(systemctl show "$scope" --property=MemoryMax --value)"
  scope_swap_max="$(systemctl show "$scope" --property=MemorySwapMax --value)"
  if ! valid_size_value "$scope_high" || ! valid_size_value "$scope_max" || \
    ! valid_size_value "$scope_swap_max"; then
    echo "Could not read current systemd memory limits for $scope." >&2
    exit 2
  fi
  TX_DOCKER_HIGHS+=("$scope_high")
  TX_DOCKER_MAXES+=("$scope_max")
  TX_DOCKER_SWAP_MAXES+=("$scope_swap_max")
  TX_DOCKER_IDS+=("$container_id")
  TX_DOCKER_INVOCATIONS+=("$invocation_id")
  current="$(systemctl show "$scope" --property=MemoryCurrent --value)"
  peak="$(systemctl show "$scope" --property=MemoryPeak --value)"
  swap_current="$(systemctl show "$scope" --property=MemorySwapCurrent --value)"
  swap_peak="$(systemctl show "$scope" --property=MemorySwapPeak --value)"
  if [[ ! "$current" =~ ^[0-9]+$ || ! "$peak" =~ ^[0-9]+$ || \
    ! "$swap_current" =~ ^[0-9]+$ || ! "$swap_peak" =~ ^[0-9]+$ ]]; then
    echo "$container does not expose numeric cgroup current/peak memory and swap." >&2
    exit 2
  fi
  if ((current + HEADROOM_BYTES > DOCKER_MAX_BYTES[i] || peak + HEADROOM_BYTES > DOCKER_MAX_BYTES[i])); then
    echo "$container current=$current peak=$peak lacks 128MiB headroom below proposed max=${DOCKER_MAXES[$i]}." >&2
    exit 2
  fi
  if ((swap_current + HEADROOM_BYTES > DOCKER_SWAP_MAX_BYTES[i] || swap_peak + HEADROOM_BYTES > DOCKER_SWAP_MAX_BYTES[i])); then
    echo "$container swap_current=$swap_current swap_peak=$swap_peak lacks 128MiB headroom below proposed MemorySwapMax=${DOCKER_SWAP_MAXES[$i]}." >&2
    exit 2
  fi
done

# Stage every payload and validate the exact staged guard/config pair.
for i in "${!MANAGED_SOURCES[@]}"; do
  install -m "${MANAGED_MODES[$i]}" "${MANAGED_SOURCES[$i]}" "$STAGE_DIR/${MANAGED_KEYS[$i]}"
done
"$PYTHON_BIN" "$STAGE_DIR/guard" --config "$STAGE_DIR/config" --validate-config
"$PYTHON_BIN" "$STAGE_DIR/guard" --config "$STAGE_DIR/config" --verify-host
"$PYTHON_BIN" "$STAGE_DIR/guard" --config "$STAGE_DIR/config" --self-test-targets

if [[ -e "$PREINSTALL_DIR" ]]; then
  validate_existing_baseline || {
    echo "Existing preinstall baseline is incomplete, malformed, or belongs to another host; refusing to reuse it." >&2
    exit 2
  }
else
  install -d -m 0700 "$PREINSTALL_DIR" "$PREINSTALL_DIR/files" "$PREINSTALL_DIR/values"
  BASELINE_CREATED=1
  printf '%s\n' "$HOST_NAME" >"$PREINSTALL_DIR/host"
  chmod 0600 "$PREINSTALL_DIR/host"
fi

save_value_once guard.was-active "$GUARD_WAS_ACTIVE"
save_value_once guard.was-enabled "$GUARD_WAS_ENABLED"
save_value_once probe.was-active "$PROBE_WAS_ACTIVE"
save_value_once probe.was-enabled "$PROBE_WAS_ENABLED"
if [[ "$HOST_NAME" == meghadharma ]]; then
  save_value_once reconciler.was-active "$RECONCILER_WAS_ACTIVE"
  save_value_once reconciler.was-enabled "$RECONCILER_WAS_ENABLED"
  save_value_once reconciler-timer.was-active "$RECONCILER_TIMER_WAS_ACTIVE"
  save_value_once reconciler-timer.was-enabled "$RECONCILER_TIMER_WAS_ENABLED"
fi
for ((i=0; i<${#SYSTEM_UNITS[@]}; i++)); do
  key="system.${SYSTEM_UNITS[$i]}"
  save_value_once "$key.MemoryHigh" "${TX_SYSTEM_HIGHS[$i]}"
  save_value_once "$key.MemoryMax" "${TX_SYSTEM_MAXES[$i]}"
done
for ((i=0; i<${#USER_UNITS[@]}; i++)); do
  key="user.${USER_UNITS[$i]}"
  save_value_once "$key.MemoryHigh" "${TX_USER_HIGHS[$i]}"
  save_value_once "$key.MemoryMax" "${TX_USER_MAXES[$i]}"
done
for i in "${!MANAGED_DESTS[@]}"; do
  record_original_file "${MANAGED_KEYS[$i]}" "${MANAGED_DESTS[$i]}"
  capture_transaction_file "${MANAGED_DESTS[$i]}"
  if ((BASELINE_CREATED == 0)); then
    preserve_superseded_file "${MANAGED_KEYS[$i]}" "${MANAGED_DESTS[$i]}" \
      "$STAGE_DIR/${MANAGED_KEYS[$i]}"
  fi
done
# Make the complete pre-mutation restoration contract durable before changing
# a managed file, service state, or cgroup property.
sync -f "$PREINSTALL_DIR"

MUTATED=1
install -d -m 0755 /usr/local/lib/vps-resource-guard
install -d -m 0755 /usr/local/share/doc/vps-resource-guard
install -d -m 0755 /etc/vps-resource-guard
install -d -m 0755 /etc/systemd/journald.conf.d
install -d -m 0700 /var/lib/vps-resource-guard
install -d -m 0700 /var/log/vps-resource-guard
for i in "${!MANAGED_DESTS[@]}"; do
  install -d -m 0755 "$(dirname -- "${MANAGED_DESTS[$i]}")"
  install -m "${MANAGED_MODES[$i]}" "$STAGE_DIR/${MANAGED_KEYS[$i]}" "${MANAGED_DESTS[$i]}"
done
JOURNALD_TOUCHED=1

"$PYTHON_BIN" /usr/local/lib/vps-resource-guard/vps_resource_guard.py \
  --config /etc/vps-resource-guard/config.toml --validate-config
"$PYTHON_BIN" /usr/local/lib/vps-resource-guard/vps_resource_guard.py \
  --config /etc/vps-resource-guard/config.toml --verify-host
"$PYTHON_BIN" /usr/local/lib/vps-resource-guard/vps_resource_guard.py \
  --config /etc/vps-resource-guard/config.toml --self-test-targets
systemd-analyze verify /etc/systemd/system/vps-resource-guard.service
systemd-analyze verify /etc/systemd/system/vps-resource-guard-self-test.service
if [[ "$HOST_NAME" == meghadharma ]]; then
  systemd-analyze verify /etc/systemd/system/vps-resource-guard-docker-reconcile.service
  systemd-analyze verify /etc/systemd/system/vps-resource-guard-docker-reconcile.timer
fi

systemctl daemon-reload
if ((${#USER_UNITS[@]})); then user_systemctl daemon-reload; fi
systemctl reset-failed vps-resource-guard-self-test.service 2>/dev/null || true
PROBE_TOUCHED=1
systemctl restart vps-resource-guard-self-test.service
[[ "$(systemctl show vps-resource-guard-self-test.service --property=Result --value)" == success ]]

for ((i=0; i<${#SYSTEM_UNITS[@]}; i++)); do
  systemctl set-property --runtime "${SYSTEM_UNITS[$i]}" \
    "MemoryHigh=${SYSTEM_HIGHS[$i]}" "MemoryMax=${SYSTEM_MAXES[$i]}"
done
for ((i=0; i<${#USER_UNITS[@]}; i++)); do
  user_systemctl set-property --runtime "${USER_UNITS[$i]}" \
    "MemoryHigh=${USER_HIGHS[$i]}" "MemoryMax=${USER_MAXES[$i]}"
done
if [[ "$HOST_NAME" == meghadharma ]]; then
  SCOPES_TOUCHED=1
  VPS_RESOURCE_GUARD_LOCK_HELD=1 \
    /usr/local/lib/vps-resource-guard/reconcile-meghadharma-docker-limits.sh
fi

for ((i=0; i<${#SYSTEM_UNITS[@]}; i++)); do
  assert_system_property "${SYSTEM_UNITS[$i]}" MemoryHigh "${SYSTEM_HIGH_BYTES[$i]}"
  assert_system_property "${SYSTEM_UNITS[$i]}" MemoryMax "${SYSTEM_MAX_BYTES[$i]}"
done
for ((i=0; i<${#USER_UNITS[@]}; i++)); do
  assert_user_property "${USER_UNITS[$i]}" MemoryHigh "${USER_HIGH_BYTES[$i]}"
  assert_user_property "${USER_UNITS[$i]}" MemoryMax "${USER_MAX_BYTES[$i]}"
done
assert_system_property vps-resource-guard.service MemoryHigh 201326592
assert_system_property vps-resource-guard.service MemoryMax 268435456
assert_system_property vps-resource-guard-self-test.service MemoryHigh 201326592
assert_system_property vps-resource-guard-self-test.service MemoryMax 268435456
if [[ "$HOST_NAME" == meghadharma ]]; then
  assert_system_property vps-resource-guard-docker-reconcile.service MemoryHigh 100663296
  assert_system_property vps-resource-guard-docker-reconcile.service MemoryMax 134217728
  systemctl enable --now vps-resource-guard-docker-reconcile.timer
  systemctl is-active --quiet vps-resource-guard-docker-reconcile.timer
fi

# Restarting journald rotates its active file so the configured bound applies.
# The following vacuum is authorized fleet cleanup. A rollback can restore the
# prior config file, but deleted historical journal segments are not recoverable.
systemctl restart systemd-journald.service
journalctl --vacuum-size=512M

GUARD_TOUCHED=1
systemctl enable vps-resource-guard.service
systemctl restart vps-resource-guard.service
systemctl is-active --quiet vps-resource-guard.service

COMMITTED=1
echo "Installed and live-probed vps-resource-guard for $HOST_NAME."
