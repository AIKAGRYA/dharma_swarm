#!/bin/bash
# dharma_swarm daemon launcher
# Runs the swarm in daemon mode (6h heartbeat from Garden Daemon config)
#
# Usage:
#   bash ~/dharma_swarm/run_daemon.sh          # foreground
#   bash ~/dharma_swarm/run_daemon.sh &         # background
#   launchctl load ~/Library/LaunchAgents/com.dhyana.dharma-swarm.plist  # persistent

set -e

cd ~/dharma_swarm
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_ENV_HELPER="${SCRIPT_DIR}/scripts/load_runtime_env.sh"

export PATH="${HOME}/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

if [ -f "$RUNTIME_ENV_HELPER" ]; then
  # shellcheck disable=SC1090
  source "$RUNTIME_ENV_HELPER"
fi

STATE_DIR="${HOME}/.dharma"
LOG_DIR="${STATE_DIR}/logs"
PID_FILE="${STATE_DIR}/daemon.pid"
mkdir -p "$LOG_DIR"

# --- PID lock: prevent double daemon ---
if [ -f "$PID_FILE" ]; then
  EXISTING_PID=$(cat "$PID_FILE")
  if kill -0 "$EXISTING_PID" 2>/dev/null; then
    echo "[run_daemon] Daemon already running (PID $EXISTING_PID). Aborting." >&2
    exit 1
  else
    echo "[run_daemon] Stale PID file (PID $EXISTING_PID not running). Cleaning up."
    rm -f "$PID_FILE"
  fi
fi

# --- Mission preflight (fail-closed) ---
MISSION_PREFLIGHT="${MISSION_PREFLIGHT:-1}"
if [[ "${MISSION_PREFLIGHT}" == "1" ]]; then
  scripts/mission_preflight.sh || {
    echo "[run_daemon] Preflight failed — daemon aborted." >&2
    exit 1
  }
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) dharma_swarm daemon starting" | tee -a "$LOG_DIR/daemon.log"
echo "  state_dir: $STATE_DIR"
echo "  pid: $$"

# Write PID file
echo $$ > "$PID_FILE"

# Interval: 30s for interactive testing, omit --interval for full 6h daemon mode
INTERVAL="${DHARMA_INTERVAL:-30}"
export DHARMA_FAST_BOOT="${DHARMA_FAST_BOOT:-1}"

# Enable verbose logging
export DHARMA_LOG_LEVEL="${DHARMA_LOG_LEVEL:-INFO}"

# Bare `python3` resolved to the Homebrew interpreter (no dharma deps →
# ModuleNotFoundError: icontract on boot); pin the repo venv, overridable.
exec "${DHARMA_PYTHON:-${SCRIPT_DIR}/.venv/bin/python}" -u -c "
import asyncio, logging, sys
logging.basicConfig(
    level=getattr(logging, '$DHARMA_LOG_LEVEL'),
    format='%(asctime)s %(name)s [%(levelname)s] %(message)s',
    stream=sys.stdout,
)

from dharma_swarm.swarm import SwarmManager
from dharma_swarm.startup_crew import spawn_cybernetics_crew

async def main():
    swarm = SwarmManager(state_dir='$STATE_DIR')
    await swarm.init()
    cyber_crew = await spawn_cybernetics_crew(swarm)
    if cyber_crew:
        print(f'Cybernetics crew asserted: {len(cyber_crew)} seats', flush=True)
    print(f'Crew ready. Thread: {swarm.current_thread}', flush=True)
    try:
        await swarm.run(interval=$INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        await swarm.shutdown()
        print('Daemon stopped.', flush=True)

asyncio.run(main())
" >> "$LOG_DIR/daemon.log" 2>&1
