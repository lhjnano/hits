#!/bin/bash
# ──────────────────────────────────────────────────────────────
# HITS Test Server Manager
# ──────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="/tmp/hits_test_server.log"
PID_FILE="/tmp/hits_test_server.pid"
PORT=8765

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if server is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Start server
start_server() {
    if is_running; then
        log_warn "Server already running (PID: $(cat $PID_FILE))"
        return 0
    fi

    log_info "Starting HITS test server on port $PORT..."

    cd "$PROJECT_ROOT"
    source venv/bin/activate
    python -m hits_core.main --port $PORT --dev > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    # Wait for server to be ready
    local max_wait=15
    local waited=0
    while [ $waited -lt $max_wait ]; do
        if curl -s "http://localhost:$PORT/api/health" > /dev/null 2>&1; then
            log_info "Server started successfully (PID: $(cat $PID_FILE))"
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done

    log_error "Server failed to start within ${max_wait}s"
    tail -20 "$LOG_FILE"
    return 1
}

# Stop server
stop_server() {
    if ! is_running; then
        log_warn "Server not running"
        return 0
    fi

    local pid=$(cat "$PID_FILE")
    log_info "Stopping server (PID: $pid)..."

    kill "$pid" 2>/dev/null || true
    local max_wait=5
    local waited=0
    while [ $waited -lt $max_wait ]; do
        if ! ps -p "$pid" > /dev/null 2>&1; then
            break
        fi
        sleep 1
        waited=$((waited + 1))
    done

    if ps -p "$pid" > /dev/null 2>&1; then
        log_warn "Force killing server..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    log_info "Server stopped"
}

# Restart server
restart_server() {
    stop_server
    sleep 2
    start_server
}

# Show server status
status() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        log_info "Server is running (PID: $pid)"
        curl -s "http://localhost:$PORT/api/health" | jq . 2>/dev/null || curl -s "http://localhost:$PORT/api/health"
    else
        log_warn "Server is not running"
    fi
}

# Show logs
logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        log_error "Log file not found: $LOG_FILE"
    fi
}

# Show recent logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -50 "$LOG_FILE"
    else
        log_error "Log file not found: $LOG_FILE"
    fi
}

# Clean test data
clean_data() {
    log_info "Cleaning test data..."
    rm -rf ~/.hits/data/work_logs/*.json 2>/dev/null || true
    rm -rf ~/.hits/data/signals/pending/*.json 2>/dev/null || true
    rm -rf ~/.hits/data/signals/consumed/*.json 2>/dev/null || true
    rm -rf ~/.hits/data/checkpoints/* 2>/dev/null || true
    log_info "Test data cleaned"
}

# Main
case "${1:-start}" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    show-logs)
        show_logs
        ;;
    clean)
        clean_data
        ;;
    clean-all)
        stop_server
        sleep 1
        clean_data
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|show-logs|clean|clean-all}"
        exit 1
        ;;
esac
