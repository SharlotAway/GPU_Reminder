#!/bin/bash

PROJECT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"

PID_FILE="$PROJECT_DIR/run/monitor.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "GPU Monitor is not running."
    exit 0
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then

    kill "$PID"

    echo "Stopping GPU Monitor..."

    for i in $(seq 1 10); do
        if ! kill -0 "$PID" 2>/dev/null; then
            break
        fi
        sleep 1
    done

    if kill -0 "$PID" 2>/dev/null; then
        echo "Process did not stop gracefully."
        kill -9 "$PID"
    fi

    echo "GPU Monitor stopped."

else

    echo "GPU Monitor process not found."

fi

rm -f "$PID_FILE"