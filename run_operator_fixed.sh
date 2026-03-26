#!/usr/bin/env bash
# run_operator_fixed.sh — Fixed DHARMA COMMAND launcher
# Uses venv, proper error handling, health checks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Use venv
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"
VENV_UVICORN="$SCRIPT_DIR/.venv/bin/uvicorn"

if [[ ! -f "$VENV_PYTHON" ]]; then
    echo "❌ Virtual environment not found. Run:"
    echo "   cd $SCRIPT_DIR && python3 -m venv .venv"
    echo "   source .venv/bin/activate && pip install -e ."
    exit 1
fi

STATE_DIR="${HOME}/.dharma"
PID_FILE="${STATE_DIR}/operator.pid"
LOG_FILE="${STATE_DIR}/logs/operator.log"
PORT="${OPERATOR_PORT:-8420}"
HOST="${OPERATOR_HOST:-127.0.0.1}"

mkdir -p "${STATE_DIR}/logs"

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down operator..."
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid="$(cat "$PID_FILE" 2>/dev/null || true)"
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
        rm -f "$PID_FILE"
    fi
}
trap cleanup EXIT INT TERM

# Check if already running
if [[ -f "$PID_FILE" ]]; then
    old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
        echo "✅ Operator already running (PID $old_pid)"
        echo "   Access: http://${HOST}:${PORT}"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

# Pre-flight checks
echo "🔍 Pre-flight checks..."

if ! "$VENV_PYTHON" -c "import dharma_swarm" 2>/dev/null; then
    echo "❌ dharma_swarm not installed in venv"
    echo "   Run: source .venv/bin/activate && pip install -e ."
    exit 1
fi

if ! "$VENV_PYTHON" -c "import fastapi" 2>/dev/null; then
    echo "❌ fastapi not installed"
    exit 1
fi

echo "✅ Pre-flight checks passed"
echo ""
echo "🚀 Starting DHARMA COMMAND operator..."
echo "   Host: $HOST"
echo "   Port: $PORT"
echo "   Logs: $LOG_FILE"
echo ""

# Start server
if [[ "${1:-}" == "--background" ]]; then
    nohup "$VENV_UVICORN" api.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --log-level info \
        --no-access-log \
        >> "$LOG_FILE" 2>&1 &
    
    new_pid="$!"
    echo "$new_pid" > "$PID_FILE"
    
    # Wait for startup
    for i in {1..10}; do
        if curl -s "http://${HOST}:${PORT}/api/health" > /dev/null 2>&1; then
            echo "✅ Operator started in background (PID $new_pid)"
            echo "   Health: http://${HOST}:${PORT}/api/health"
            exit 0
        fi
        sleep 0.5
    done
    
    echo "⚠️  Operator may not have started properly. Check logs: $LOG_FILE"
    exit 1
else
    echo "Press Ctrl+C to stop"
    echo ""
    exec "$VENV_UVICORN" api.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --log-level info \
        --reload
fi
