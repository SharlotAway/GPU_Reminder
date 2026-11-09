#!/bin/bash

set -e

PROJECT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"

cd "$PROJECT_DIR"

# 加载环境变量
set -a
source "$PROJECT_DIR/.env"
set +a

mkdir -p logs run
exec 9>run/monitor.lock
flock -x 9

PID_FILE="$PROJECT_DIR/run/monitor.pid"
LOG_DIR="$PROJECT_DIR/logs"

# 检查是否已经运行
if [ -f "$PID_FILE" ]; then

    OLD_PID=$(cat "$PID_FILE")

    if [[ "$OLD_PID" =~ ^[0-9]+$ ]] && kill -0 "$OLD_PID" 2>/dev/null &&
        grep -azFxq gpu_idle_monitor.py "/proc/$OLD_PID/cmdline"; then
        echo "GPU Monitor is already running. PID: $OLD_PID"
        if [ -f "$LOG_DIR/latest/monitor.log" ]; then
            echo "Log: $LOG_DIR/latest/monitor.log"
        fi
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# 每个后台进程写入独立的日志。时间戳后的后缀避免同秒碰撞。
SESSION_DIR=$(mktemp -d "$LOG_DIR/$(date +%Y%m%d-%H%M%S)-XXXXXX")
LOG_FILE="$SESSION_DIR/monitor.log"

# 后台启动
if [ -z "${PYTHON_BIN:-}" ]; then
    if [ -x "$PROJECT_DIR/../.vlm-tools/envs/gpu_monitor/bin/python" ]; then
        PYTHON_BIN="$PROJECT_DIR/../.vlm-tools/envs/gpu_monitor/bin/python"
    else
        PYTHON_BIN=python
    fi
fi
nohup "$PYTHON_BIN" -u gpu_idle_monitor.py \
    </dev/null >> "$LOG_FILE" 2>&1 9>&- &

PID=$!

echo "$PID" > "$PID_FILE"

sleep 2

if kill -0 "$PID" 2>/dev/null; then
    ln -s -- "$(basename -- "$SESSION_DIR")" "$SESSION_DIR/latest-link"
    mv -Tf -- "$SESSION_DIR/latest-link" "$LOG_DIR/latest"
    echo "GPU Monitor started successfully."
    echo "PID: $PID"
    echo "Log: $LOG_FILE"
else
    rm -f "$PID_FILE"
    echo "GPU Monitor failed to start."
    echo "Log: $LOG_FILE"
    tail -n 30 "$LOG_FILE"
    exit 1
fi
