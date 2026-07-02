#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="gui/$(id -u)"
STREAM="${STREAM:-DHARMA_FLEET}"
ENDPOINT="${ENDPOINT:-nats://127.0.0.1:4222}"
FETCH_TIMEOUT="${FETCH_TIMEOUT:-30}"
POLL_INTERVAL="${POLL_INTERVAL:-1}"
MAX_MESSAGES="${MAX_MESSAGES:-10}"
UV_BIN="${UV_BIN:-/opt/homebrew/bin/uv}"
LAUNCHCTL_BIN="${LAUNCHCTL_BIN:-launchctl}"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
PLAN_DIR="${PLAN_DIR:-${ROOT}/reports/a2a/launchd_plans}"
LOG_DIR="${HOME}/.dharma/logs/a2a_inbox_bridge"
HEARTBEAT_DIR="${HOME}/.dharma/a2a_bus/bridge_heartbeats"
PATH_FOR_LAUNCHD="${PATH_FOR_LAUNCHD:-/Users/dhyana/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin}"
INSTALL_LAUNCHD="${INSTALL_LAUNCHD:-0}"
SELECTED_AGENTS="${AGENT_UIDS:-codex_composer}"

FLEET_ROWS=(
  "hermes-m5|hermes_inbox|com.dharma.a2a-inbox-bridge.hermes-m5|"
  "codex_composer|codex_composer_inbox|com.dharma.a2a.codex-composer-inbox-bridge|com.dharma.a2a-inbox-bridge.codex-composer"
  "fable_composer|fable_composer_inbox|com.dharma.a2a-inbox-bridge.fable-composer|"
  "opus_composer|opus_composer_inbox|com.dharma.a2a-inbox-bridge.opus-composer|"
  "devin-roaming-2987d222|devin_roaming_2987d222_inbox|com.dharma.a2a-inbox-bridge.devin-roaming-2987d222|"
  "perplexity-computer|perplexity_computer_inbox|com.dharma.a2a-inbox-bridge.perplexity-computer|"
)

usage() {
  cat <<'EOF'
Usage: scripts/start_a2a_inbox_bridge_fleet_launchd.sh [--render-only|--install] [--agent AGENT_UID|--all]

Defaults are intentionally review-only and Codex-scoped:
  --render-only             render plist plan(s), do not call launchctl
  --agent codex_composer    render the Workstream 2 target only

Installation is a live launchd mutation and requires explicit operator approval:
  --install                 write plist(s) to ~/Library/LaunchAgents and bootstrap/kickstart
  --all                     include every fleet row instead of only the selected agent

Environment overrides:
  AGENT_UIDS=codex_composer,fable_composer
  INSTALL_LAUNCHD=1
  PLAN_DIR=/path/to/rendered/plans
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --render-only)
      INSTALL_LAUNCHD=0
      shift
      ;;
    --install)
      INSTALL_LAUNCHD=1
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

write_plist() {
  local agent_uid="$1"
  local consumer="$2"
  local label="$3"
  local destination_dir="$4"
  local plist_path="${destination_dir}/${label}.plist"
  local heartbeat_file="${HEARTBEAT_DIR}/${agent_uid}.json"
  local stdout_log="${LOG_DIR}/${label}.stdout.log"
  local stderr_log="${LOG_DIR}/${label}.stderr.log"

  cat > "${plist_path}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${UV_BIN}</string>
    <string>run</string>
    <string>--with</string>
    <string>nats-py</string>
    <string>python</string>
    <string>scripts/runtime/a2a_inbox_bridge.py</string>
    <string>--agent-uid</string>
    <string>${agent_uid}</string>
    <string>--consumer</string>
    <string>${consumer}</string>
    <string>--stream</string>
    <string>${STREAM}</string>
    <string>--endpoint</string>
    <string>${ENDPOINT}</string>
    <string>--fetch-timeout</string>
    <string>${FETCH_TIMEOUT}</string>
    <string>--poll-interval</string>
    <string>${POLL_INTERVAL}</string>
    <string>--max-messages</string>
    <string>${MAX_MESSAGES}</string>
    <string>--heartbeat-file</string>
    <string>${heartbeat_file}</string>
    <string>--loop</string>
    <string>--suppress-no-messages</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>StandardOutPath</key>
  <string>${stdout_log}</string>
  <key>StandardErrorPath</key>
  <string>${stderr_log}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key>
    <string>${HOME}</string>
    <key>PATH</key>
    <string>${PATH_FOR_LAUNCHD}</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>
</dict>
</plist>
EOF
  if command -v plutil >/dev/null 2>&1; then
    plutil -lint "${plist_path}" >/dev/null
  fi
  echo "${plist_path}"
}

start_label() {
  local label="$1"
  local plist_path="$2"
  local legacy_label="${3:-}"
  if [[ -n "${legacy_label}" ]] && "${LAUNCHCTL_BIN}" print "${DOMAIN}/${legacy_label}" >/dev/null 2>&1; then
    echo "ERROR: legacy launchd label is already loaded: ${legacy_label}" >&2
    echo "Refusing to start duplicate consumer for target label: ${label}" >&2
    return 3
  fi
  if "${LAUNCHCTL_BIN}" print "${DOMAIN}/${label}" >/dev/null 2>&1; then
    "${LAUNCHCTL_BIN}" kickstart -k "${DOMAIN}/${label}"
  else
    "${LAUNCHCTL_BIN}" bootstrap "${DOMAIN}" "${plist_path}"
    "${LAUNCHCTL_BIN}" kickstart -k "${DOMAIN}/${label}"
  fi
}

if [[ "${INSTALL_LAUNCHD}" == "1" ]]; then
  TARGET_DIR="${LAUNCH_AGENTS_DIR}"
else
  TARGET_DIR="${PLAN_DIR}"
fi

mkdir -p "${TARGET_DIR}" "${LOG_DIR}" "${HEARTBEAT_DIR}"

selected_count=0
for row in "${FLEET_ROWS[@]}"; do
  IFS='|' read -r agent_uid consumer label legacy_label <<< "${row}"
  if ! should_include_agent "${agent_uid}"; then
    continue
  fi
  selected_count=$((selected_count + 1))
  plist_path="$(write_plist "${agent_uid}" "${consumer}" "${label}" "${TARGET_DIR}")"
  if [[ "${INSTALL_LAUNCHD}" == "1" ]]; then
    start_label "${label}" "${plist_path}" "${legacy_label}"
    echo "started label=${label} agent_uid=${agent_uid} consumer=${consumer} plist=${plist_path}"
  else
    echo "rendered label=${label} agent_uid=${agent_uid} consumer=${consumer} plist=${plist_path}"
    echo "review_command=plutil -lint ${plist_path}"
    echo "install_command=INSTALL_LAUNCHD=1 bash scripts/start_a2a_inbox_bridge_fleet_launchd.sh --install --agent ${agent_uid}"
  fi
done

if [[ "${selected_count}" -eq 0 ]]; then
  echo "ERROR: no fleet rows matched AGENT_UIDS=${SELECTED_AGENTS}" >&2
  exit 2
fi

if [[ "${INSTALL_LAUNCHD}" != "1" ]]; then
  echo "No launchctl bootstrap/kickstart commands were run. Re-run with --install only after explicit approval."
fi
echo "Status: bash scripts/status_a2a_inbox_bridge_fleet_launchd.sh --agent codex_composer"
