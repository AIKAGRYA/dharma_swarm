#!/usr/bin/env bash
set -euo pipefail

DOMAIN="gui/$(id -u)"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
REMOVE_PLISTS="${REMOVE_PLISTS:-0}"

FLEET_ROWS=(
  "hermes-m5|hermes_inbox|com.dharma.a2a-inbox-bridge.hermes-m5"
  "codex_composer|codex_composer_inbox|com.dharma.a2a-inbox-bridge.codex-composer"
  "fable_composer|fable_composer_inbox|com.dharma.a2a-inbox-bridge.fable-composer"
  "opus_composer|opus_composer_inbox|com.dharma.a2a-inbox-bridge.opus-composer"
  "devin-roaming-2987d222|devin_roaming_2987d222_inbox|com.dharma.a2a-inbox-bridge.devin-roaming-2987d222"
  "perplexity-computer|perplexity_computer_inbox|com.dharma.a2a-inbox-bridge.perplexity-computer"
)

for row in "${FLEET_ROWS[@]}"; do
  IFS='|' read -r agent_uid consumer label <<< "${row}"
  plist_path="${LAUNCH_AGENTS_DIR}/${label}.plist"
  if launchctl print "${DOMAIN}/${label}" >/dev/null 2>&1; then
    launchctl bootout "${DOMAIN}/${label}"
    echo "stopped label=${label} agent_uid=${agent_uid}"
  else
    echo "not_loaded label=${label} agent_uid=${agent_uid}"
  fi
  if [[ "${REMOVE_PLISTS}" == "1" && -f "${plist_path}" ]]; then
    rm "${plist_path}"
    echo "removed plist=${plist_path}"
  fi
done
