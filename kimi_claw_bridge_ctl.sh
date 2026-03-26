#!/bin/bash
# Kimi Claw Bridge Control Script

PID_FILE="/root/.dharma/kimi_claw_bridge.pid"
LOG_FILE="/root/.dharma/logs/kimi_claw_bridge.log"

start() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "Bridge already running (PID: $(cat $PID_FILE))"
        exit 1
    fi
    
    cd /root/.openclaw/workspace/repos/dharma_swarm
    source .venv/bin/activate
    nohup python3 kimi_claw_bridge.py --poll-interval 10 >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Bridge started (PID: $(cat $PID_FILE))"
}

stop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm -f "$PID_FILE"
            echo "Bridge stopped"
        else
            echo "Bridge not running"
            rm -f "$PID_FILE"
        fi
    else
        echo "No PID file found"
    fi
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "Bridge RUNNING (PID: $(cat $PID_FILE))"
        echo ""
        echo "Recent activity:"
        tail -20 "$LOG_FILE" 2>/dev/null | grep -E "(INFO|Executing|completed|STIGMERGY)" | tail -10
    else
        echo "Bridge STOPPED"
    fi
}

logs() {
    tail -f "$LOG_FILE"
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) stop; sleep 1; start ;;
    status) status ;;
    logs) logs ;;
    *) echo "Usage: $0 {start|stop|restart|status|logs}" ;;
esac
