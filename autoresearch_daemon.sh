#!/bin/bash
# Autoresearch Daemon — Continuous Self-Improvement
# 
# This script runs the autoresearch loop continuously in the background.
# It restarts the loop if it crashes and logs everything.
#
# Usage:
#   ./autoresearch_daemon.sh start    # Start daemon
#   ./autoresearch_daemon.sh stop     # Stop daemon
#   ./autoresearch_daemon.sh status   # Check status
#   ./autoresearch_daemon.sh logs     # View logs

REPO_ROOT="/root/.openclaw/workspace/repos/dharma_swarm"
PIDFILE="$REPO_ROOT/.autoresearch.pid"
LOGFILE="$REPO_ROOT/autoresearch_daemon.log"
VENV="$REPO_ROOT/.venv/bin/activate"

start() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Autoresearch daemon already running (PID: $(cat "$PIDFILE"))"
        exit 1
    fi
    
    echo "Starting autoresearch daemon..."
    (
        source "$VENV"
        cd "$REPO_ROOT"
        
        while true; do
            echo "[$(date)] Starting autoresearch loop..." >> "$LOGFILE"
            
            # Run 20 iterations in dry-run mode (measure only)
            # Remove --dry-run to enable actual code changes (requires API key)
            python3 run_autoresearch.py \
                --dry-run \
                --iterations 20 \
                --sleep 5 \
                2>&1 | tee -a "$LOGFILE"
            
            EXIT_CODE=${PIPESTATUS[0]}
            echo "[$(date)] Loop exited with code $EXIT_CODE. Restarting in 30s..." >> "$LOGFILE"
            sleep 30
        done
    ) &
    
    echo $! > "$PIDFILE"
    echo "Autoresearch daemon started (PID: $!)"
    echo "Logs: tail -f $LOGFILE"
}

stop() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping autoresearch daemon (PID: $PID)..."
            kill "$PID"
            rm "$PIDFILE"
            echo "Stopped."
        else
            echo "Daemon not running (stale PID file)"
            rm "$PIDFILE"
        fi
    else
        echo "Daemon not running"
    fi
}

status() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Autoresearch daemon is running (PID: $(cat "$PIDFILE"))"
        echo "Recent activity:"
        tail -20 "$LOGFILE" 2>/dev/null || echo "No logs yet"
    else
        echo "Autoresearch daemon is not running"
        [ -f "$PIDFILE" ] && rm "$PIDFILE"
    fi
}

logs() {
    tail -f "$LOGFILE"
}

case "${1:-status}" in
    start) start ;;
    stop) stop ;;
    restart) stop; sleep 2; start ;;
    status) status ;;
    logs) logs ;;
    *) echo "Usage: $0 {start|stop|restart|status|logs}" ;;
esac
