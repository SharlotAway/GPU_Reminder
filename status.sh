#!/bin/bash

PROJECT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"

PID_FILE="$PROJECT_DIR/run/monitor.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "GPU Monitor is not running."
    exit 0
fi

PID=$(cat "$PID_FILE")

if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null &&
    grep -azFxq gpu_idle_monitor.py "/proc/$PID/cmdline"; then

    echo "GPU Monitor is running."
    echo "PID: $PID"

    echo ""
    LOG_FILE="$PROJECT_DIR/logs/latest/monitor.log"
    if [ ! -f "$LOG_FILE" ]; then
        LOG_FILE="$PROJECT_DIR/logs/monitor.log"
    fi
    echo "Log: $(readlink -f -- "$LOG_FILE")"
    tail -n 20 "$LOG_FILE"

else

    echo "GPU Monitor is not running."

fi
