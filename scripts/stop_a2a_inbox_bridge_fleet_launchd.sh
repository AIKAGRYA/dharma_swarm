#!/usr/bin/env bash
set -euo pipefail

DOMAIN="gui/$(id -u)"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
REMOVE_PLISTS="${REMOVE_PLISTS:-0}"
CONFIRM_STOP="${CONFIRM_STOP:-0}"
STOP_LEGACY="${STOP_LEGACY:-0}"
LAUNCHCTL_BIN="${LAUNCHCTL_BIN:-launchctl}"
SELECTED_AGENTS="${AGENT_UIDS:-codex_composer}"

FLEET_ROWS=(
  "hermes-m5|hermes_inbox|com.dharma.a2a-inbox-bridge.hermes-m5|"
  "codex_composer|codex_composer_inbox|com.dharma.a2a.codex-composer-inbox-bridge|com.dharma.a2a-inbox-bridge.codex-composer"
  "fable_composer|fable_composer_inbox|com.dharma.a2a-inbox-bridge.fable-composer|"
  "fugu_ultra|fugu_ultra_inbox|com.dharma.a2a-inbox-bridge.fugu-ultra|"
  "opus_composer|opus_composer_inbox|com.dharma.a2a-inbox-bridge.opus-composer|"
  "devin-roaming-2987d222|devin_roaming_2987d222_inbox|com.dharma.a2a-inbox-bridge.devin-roaming-2987d222|"
  "perplexity-computer|perplexity_computer_inbox|com.dharma.a2a-inbox-bridge.perplexity-computer|"
)

usage() {
  cat <<'EOF'
Usage: scripts/stop_a2a_inbox_bridge_fleet_launchd.sh [--confirm-stop] [--agent AGENT_UID|--all] [--remove-plists] [--include-legacy]

Defaults are dry-run and Codex-scoped. bootout/rm only happen with --confirm-stop.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirm-stop)
      CONFIRM_STOP=1
      shift
      ;;
    --agent)
      SELECTED_AGENTS="${2:?--agent requires an agent uid}"
      shift 2
      ;;
    --all)
      SELECTED_AGENTS="all"
      shift
      ;;
    --remove-plists)
      REMOVE_PLISTS=1
      shift
      ;;
    --include-legacy)
      STOP_LEGACY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

should_include_agent() {
  local agent_uid="$1"
  if [[ "${SELECTED_AGENTS}" == "all" ]]; then
    return 0
  fi
  [[ ",${SELECTED_AGENTS}," == *",${agent_uid},"* ]]
}

stop_one_label() {
  local agent_uid="$1"
  local label="$2"
  local plist_path="${LAUNCH_AGENTS_DIR}/${label}.plist"
  if "${LAUNCHCTL_BIN}" print "${DOMAIN}/${label}" >/dev/null 2>&1; then
    if [[ "${CONFIRM_STOP}" == "1" ]]; then
      "${LAUNCHCTL_BIN}" bootout "${DOMAIN}/${label}"
      echo "stopped label=${label} agent_uid=${agent_uid}"
    else
      echo "would_stop label=${label} agent_uid=${agent_uid}"
    fi
  else
    echo "not_loaded label=${label} agent_uid=${agent_uid}"
  fi
  if [[ "${REMOVE_PLISTS}" == "1" && -f "${plist_path}" ]]; then
    if [[ "${CONFIRM_STOP}" == "1" ]]; then
      rm "${plist_path}"
      echo "removed plist=${plist_path}"
    else
      echo "would_remove plist=${plist_path}"
    fi
  fi
}

selected_count=0
for row in "${FLEET_ROWS[@]}"; do
  IFS='|' read -r agent_uid consumer label legacy_label <<< "${row}"
  if ! should_include_agent "${agent_uid}"; then
    continue
  fi
  selected_count=$((selected_count + 1))
  stop_one_label "${agent_uid}" "${label}"
  if [[ "${STOP_LEGACY}" == "1" && -n "${legacy_label}" ]]; then
    stop_one_label "${agent_uid}" "${legacy_label}"
  fi
done

if [[ "${selected_count}" -eq 0 ]]; then
  echo "ERROR: no fleet rows matched AGENT_UIDS=${SELECTED_AGENTS}" >&2
  exit 2
fi

if [[ "${CONFIRM_STOP}" != "1" ]]; then
  echo "Dry-run only. Re-run with --confirm-stop only after explicit approval."
fi
