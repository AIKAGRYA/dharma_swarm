#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="gui/$(id -u)"
LABEL="com.dharma.fugu-ultra-semantic-responder"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
PLAN_DIR="${PLAN_DIR:-${ROOT}/reports/a2a/launchd_plans}"
LOG_DIR="${HOME}/.dharma/logs"
UV_BIN="${UV_BIN:-/opt/homebrew/bin/uv}"
PYTHON_BIN="${PYTHON_BIN:-${ROOT}/.venv/bin/python}"
LAUNCHCTL_BIN="${LAUNCHCTL_BIN:-launchctl}"
INSTALL_LAUNCHD="${INSTALL_LAUNCHD:-0}"
INTERVAL_S="${INTERVAL_S:-60}"
LIMIT="${LIMIT:-1}"
TIMEOUT="${TIMEOUT:-240}"
FLUSH_TIMEOUT="${FLUSH_TIMEOUT:-2}"
NATS_URL_VALUE="${NATS_URL:-nats://127.0.0.1:4222}"
PATH_FOR_LAUNCHD="${PATH_FOR_LAUNCHD:-/Users/dhyana/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin}"

usage() {
  cat <<'EOF'
Usage: scripts/start_fugu_ultra_semantic_responder_launchd.sh [--render-only|--install]

Render-only is default. --install writes ~/Library/LaunchAgents/com.dharma.fugu-ultra-semantic-responder.plist and launchctl bootstrap/kickstart.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --render-only) INSTALL_LAUNCHD=0; shift ;;
    --install) INSTALL_LAUNCHD=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "${INSTALL_LAUNCHD}" == "1" ]]; then
  TARGET_DIR="${LAUNCH_AGENTS_DIR}"
else
  TARGET_DIR="${PLAN_DIR}"
fi
mkdir -p "${TARGET_DIR}" "${LOG_DIR}" "${ROOT}/reports/a2a/launchd_plans"
PLIST="${TARGET_DIR}/${LABEL}.plist"
STDOUT_LOG="${LOG_DIR}/${LABEL}.stdout.log"
STDERR_LOG="${LOG_DIR}/${LABEL}.stderr.log"

cat > "${PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>cd '${ROOT}' || exit 1; set -a; source '${HOME}/.dharma/agent_keys.env' 2&gt;/dev/null; source '${ROOT}/.env' 2&gt;/dev/null; set +a; exec env NATS_URL='${NATS_URL_VALUE}' DHARMA_NATS_URL='${NATS_URL_VALUE}' PYTHONPATH='${ROOT}' PYTHONUNBUFFERED=1 '${PYTHON_BIN}' scripts/runtime/fugu_ultra_semantic_responder.py loop --interval-s '${INTERVAL_S}' --limit '${LIMIT}' --timeout '${TIMEOUT}' --flush-timeout '${FLUSH_TIMEOUT}'</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>StandardOutPath</key>
  <string>${STDOUT_LOG}</string>
  <key>StandardErrorPath</key>
  <string>${STDERR_LOG}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key>
    <string>${HOME}</string>
    <key>PATH</key>
    <string>${PATH_FOR_LAUNCHD}</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
    <key>PYTHONPATH</key>
    <string>${ROOT}</string>
    <key>NATS_URL</key>
    <string>${NATS_URL_VALUE}</string>
    <key>DHARMA_NATS_URL</key>
    <string>${NATS_URL_VALUE}</string>
  </dict>
</dict>
</plist>
EOF

if command -v plutil >/dev/null 2>&1; then
  plutil -lint "${PLIST}" >/dev/null
fi

if [[ "${INSTALL_LAUNCHD}" == "1" ]]; then
  if "${LAUNCHCTL_BIN}" print "${DOMAIN}/${LABEL}" >/dev/null 2>&1; then
    "${LAUNCHCTL_BIN}" kickstart -k "${DOMAIN}/${LABEL}"
  else
    "${LAUNCHCTL_BIN}" bootstrap "${DOMAIN}" "${PLIST}"
    "${LAUNCHCTL_BIN}" kickstart -k "${DOMAIN}/${LABEL}"
  fi
  echo "started label=${LABEL} plist=${PLIST}"
else
  echo "rendered label=${LABEL} plist=${PLIST}"
  echo "review_command=plutil -lint ${PLIST}"
  echo "install_command=INSTALL_LAUNCHD=1 bash scripts/start_fugu_ultra_semantic_responder_launchd.sh --install"
  echo "No launchctl bootstrap/kickstart commands were run. Re-run with --install only after explicit approval."
fi
