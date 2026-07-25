#!/bin/bash
# Garden Daemon launcher
# Usage:
#   bash run_garden.sh              # One full cycle (immediate)
#   bash run_garden.sh --quick      # Quick cycle (pulse + research only)
#   bash run_garden.sh --daemon     # Loop forever (for launchd)
#   bash run_garden.sh --skill hum  # Single skill

set -euo pipefail

cd "$(dirname "$0")"

# Source runtime env (launchd-safe).
if [ -f "$PWD/scripts/load_runtime_env.sh" ]; then
    # shellcheck disable=SC1091
    source "$PWD/scripts/load_runtime_env.sh"
else
    echo "[run_garden] WARNING: scripts/load_runtime_env.sh not found; continuing with current environment" >&2
fi

# Ensure output dirs
mkdir -p "$HOME/.dharma/garden" "$HOME/.dharma/seeds" "$HOME/.dharma/subconscious" "$HOME/.dharma/logs"

# Log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Garden Daemon starting: $*" >> "$HOME/.dharma/logs/garden.log"

# Run
exec /opt/homebrew/bin/python3 -u garden_daemon.py "$@" 2>&1 | tee -a "$HOME/.dharma/logs/garden.log"
