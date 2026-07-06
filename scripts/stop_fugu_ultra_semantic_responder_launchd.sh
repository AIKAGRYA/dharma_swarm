#!/usr/bin/env bash
set -euo pipefail
DOMAIN="gui/$(id -u)"
LABEL="com.dharma.fugu-ultra-semantic-responder"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
LAUNCHCTL_BIN="${LAUNCHCTL_BIN:-launchctl}"
CONFIRM_STOP="${CONFIRM_STOP:-0}"
REMOVE_PLIST="${REMOVE_PLIST:-0}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirm-stop) CONFIRM_STOP=1; shift ;;
    --remove-plist) REMOVE_PLIST=1; shift ;;
    -h|--help) echo "Usage: $0 [--confirm-stop] [--remove-plist]"; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done
if "${LAUNCHCTL_BIN}" print "${DOMAIN}/${LABEL}" >/dev/null 2>&1; then
  if [[ "${CONFIRM_STOP}" == "1" ]]; then
    "${LAUNCHCTL_BIN}" bootout "${DOMAIN}/${LABEL}"
    echo "stopped label=${LABEL}"
  else
    echo "would_stop label=${LABEL}"
  fi
else
  echo "not_loaded label=${LABEL}"
fi
plist="${LAUNCH_AGENTS_DIR}/${LABEL}.plist"
if [[ "${REMOVE_PLIST}" == "1" && -f "${plist}" ]]; then
  if [[ "${CONFIRM_STOP}" == "1" ]]; then
    rm "${plist}"
    echo "removed plist=${plist}"
  else
    echo "would_remove plist=${plist}"
  fi
fi
if [[ "${CONFIRM_STOP}" != "1" ]]; then
  echo "Dry-run only. Re-run with --confirm-stop only after explicit approval."
fi
