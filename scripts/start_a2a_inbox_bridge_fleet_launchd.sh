#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="gui/$(id -u)"
STREAM="${STREAM:-DHARMA_FLEET}"
ENDPOINT="${ENDPOINT:-nats://127.0.0.1:4222}"
FETCH_TIMEOUT="${FETCH_TIMEOUT:-30}"
POLL_INTERVAL="${POLL_INTERVAL:-1}"
MAX_MESSAGES="${MAX_MESSAGES:-10}"
UV_BIN="${UV_BIN:-/Users/dhyana/.local/bin/uv}"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
LOG_DIR="${HOME}/.dharma/logs/a2a_inbox_bridge"
HEARTBEAT_DIR="${HOME}/.dharma/a2a_bus/bridge_heartbeats"
PATH_FOR_LAUNCHD="${PATH_FOR_LAUNCHD:-/Users/dhyana/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin}"

FLEET_ROWS=(
  "hermes-m5|hermes_inbox|com.dharma.a2a-inbox-bridge.hermes-m5"
  "codex_composer|codex_composer_inbox|com.dharma.a2a-inbox-bridge.codex-composer"
  "fable_composer|fable_composer_inbox|com.dharma.a2a-inbox-bridge.fable-composer"
  "opus_composer|opus_composer_inbox|com.dharma.a2a-inbox-bridge.opus-composer"
  "devin-roaming-2987d222|devin_roaming_2987d222_inbox|com.dharma.a2a-inbox-bridge.devin-roaming-2987d222"
  "perplexity-computer|perplexity_computer_inbox|com.dharma.a2a-inbox-bridge.perplexity-computer"
)

mkdir -p "${LAUNCH_AGENTS_DIR}" "${LOG_DIR}" "${HEARTBEAT_DIR}"

write_plist() {
  local agent_uid="$1"
  local consumer="$2"
  local label="$3"
  local plist_path="${LAUNCH_AGENTS_DIR}/${label}.plist"
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
  plutil -lint "${plist_path}" >/dev/null
  echo "${plist_path}"
}

start_label() {
  local label="$1"
  local plist_path="$2"
  if launchctl print "${DOMAIN}/${label}" >/dev/null 2>&1; then
    launchctl kickstart -k "${DOMAIN}/${label}"
  else
    launchctl bootstrap "${DOMAIN}" "${plist_path}"
    launchctl kickstart -k "${DOMAIN}/${label}"
  fi
}

for row in "${FLEET_ROWS[@]}"; do
  IFS='|' read -r agent_uid consumer label <<< "${row}"
  plist_path="$(write_plist "${agent_uid}" "${consumer}" "${label}")"
  start_label "${label}" "${plist_path}"
  echo "started label=${label} agent_uid=${agent_uid} consumer=${consumer} plist=${plist_path}"
done

echo "Status: bash scripts/status_a2a_inbox_bridge_fleet_launchd.sh"
