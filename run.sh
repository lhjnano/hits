#!/bin/bash
# HITS Launcher
# Primary: Node.js server (Express + Python backend)
# Fallback: Python-only mode (FastAPI serves everything)

cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${GREEN}HITS - Hybrid Intel Trace System${NC}"
echo ""

VENV_PATH="$PWD/venv"
WEB_DIR="$PWD/hits_web"
PORT="${HITS_PORT:-8765}"

setup_venv() {
    echo -e "${CYAN}Setting up virtual environment...${NC}"
    python3 -m venv "$VENV_PATH"
    source "$VENV_PATH/bin/activate"
    
    echo -e "${CYAN}Installing Python dependencies...${NC}"
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
}

activate_venv() {
    if [ -d "$VENV_PATH" ]; then
        source "$VENV_PATH/bin/activate"
        echo -e "${GREEN}Virtual environment activated${NC}"
        return 0
    fi
    return 1
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: Python 3 is not installed${NC}"
        echo "Please install Python 3.10 or later"
        exit 1
    fi
    echo -e "${GREEN}Python: $(python3 --version)${NC}"
}

check_node() {
    if ! command -v node &> /dev/null; then
        echo -e "${YELLOW}Node.js not found. Falling back to Python-only mode.${NC}"
        return 1
    fi
    echo -e "${GREEN}Node.js: $(node --version)${NC}"
    return 0
}

build_frontend() {
    if [ ! -d "$WEB_DIR/node_modules" ]; then
        echo -e "${CYAN}Installing frontend dependencies...${NC}"
        (cd "$WEB_DIR" && npm install)
    fi

    if [ ! -f "$WEB_DIR/dist/index.html" ] || [ "$HITS_REBUILD" = "1" ]; then
        echo -e "${CYAN}Building frontend...${NC}"
        (cd "$WEB_DIR" && npm run build)
    fi

    if [ -f "$WEB_DIR/dist/index.html" ]; then
        echo -e "${GREEN}Frontend built OK${NC}"
    else
        echo -e "${YELLOW}Warning: Frontend not built. Run: cd hits_web && npm run build${NC}"
    fi
}

preflight_checks() {
    echo -e "${CYAN}Running pre-flight checks...${NC}"
    echo ""
    
    if [ -d "$VENV_PATH" ]; then
        source "$VENV_PATH/bin/activate"
    else
        echo -e "${RED}Virtual environment not found. Run: ./run.sh --setup${NC}"
        return 1
    fi
    
    local failed=0
    
    echo "  [1/3] Checking core imports..."
    if ! python -c "
from hits_core.models import Node, KnowledgeTree
from hits_core.storage import FileStorage
from hits_core.auth import AuthManager
from hits_core.api.server import APIServer
print('OK')
" 2>/dev/null; then
        echo -e "${RED}    ✗ Core imports failed${NC}"
        echo "    Run: ./run.sh --setup"
        failed=1
    else
        echo -e "${GREEN}    ✓ Core imports OK${NC}"
    fi
    
    echo "  [2/3] Checking config..."
    if [ ! -f "config/settings.yaml" ]; then
        echo -e "${RED}    ✗ config/settings.yaml not found${NC}"
        failed=1
    else
        echo -e "${GREEN}    ✓ Config OK${NC}"
    fi
    
    echo "  [3/3] Checking frontend..."
    if [ -f "$WEB_DIR/dist/index.html" ]; then
        echo -e "${GREEN}    ✓ Frontend OK${NC}"
    else
        echo -e "${YELLOW}    ⚠ Frontend not built${NC}"
        echo "    Run: cd hits_web && npm install && npm run build"
    fi
    
    echo ""
    return $failed
}

check_redis() {
    if command -v redis-cli &> /dev/null; then
        if redis-cli ping 2>/dev/null | grep -q "PONG"; then
            echo -e "${GREEN}Redis: Connected${NC}"
            return 0
        fi
    fi
    echo -e "${YELLOW}Redis: Not available (using file storage)${NC}"
    echo "  To start Redis: cd scripts && ./setup_redis.sh --apt"
}

# ─── Node.js Server Mode (primary) ──────────────────────────────

run_node_server() {
    if [ ! -d "$VENV_PATH" ]; then
        setup_venv
    fi

    build_frontend
    check_redis
    echo ""

    if [ ! -f "$WEB_DIR/dist/index.html" ]; then
        echo -e "${RED}Error: Frontend not built.${NC}"
        echo "Run: cd hits_web && npm install && npm run build"
        exit 1
    fi

    echo -e "${CYAN}Starting HITS via Node.js server...${NC}"
    echo -e "${GREEN}http://127.0.0.1:${PORT}${NC}"
    echo -e "${CYAN}Press Ctrl+C to stop${NC}"
    echo ""

    node bin/hits.js --port "$PORT" "$@"
}

# ─── Python-Only Mode (fallback) ────────────────────────────────

run_python_server() {
    if [ ! -d "$VENV_PATH" ]; then
        setup_venv
    elif ! activate_venv; then
        setup_venv
    fi

    if ! preflight_checks; then
        echo -e "${RED}Pre-flight checks failed. Fix errors above.${NC}"
        exit 1
    fi

    check_redis
    echo ""
    echo -e "${GREEN}Starting HITS web server on http://127.0.0.1:${PORT}${NC}"
    echo -e "${CYAN}Press Ctrl+C to stop${NC}"
    echo ""

    python -m hits_core.main --port "$PORT"
}

run_dev() {
    if [ ! -d "$VENV_PATH" ]; then
        setup_venv
    else
        activate_venv
    fi
    
    pip install -r requirements.txt -q 2>/dev/null
    
    echo -e "${CYAN}Starting backend API on port ${PORT} (dev mode)...${NC}"
    python -m hits_core.main --port "$PORT" --dev &
    BACKEND_PID=$!
    
    sleep 2
    
    if check_node; then
        if [ ! -d "$WEB_DIR/node_modules" ]; then
            echo -e "${CYAN}Installing frontend dependencies...${NC}"
            (cd "$WEB_DIR" && npm install)
        fi
        echo -e "${GREEN}Starting Vite dev server on http://localhost:5173${NC}"
        echo -e "${CYAN}Backend API proxy at http://localhost:${PORT}${NC}"
        (cd "$WEB_DIR" && npm run dev)
    fi
    
    kill $BACKEND_PID 2>/dev/null
}

# ─── Main ───────────────────────────────────────────────────────

check_python

case "${1:-}" in
    --test|-t)
        if [ -d "$VENV_PATH" ]; then activate_venv; else setup_venv; fi
        pip install pytest pytest-asyncio -q 2>/dev/null
        python -m pytest tests/core/ -v --tb=short
        ;;
    --setup|-s)
        setup_venv
        if check_node; then build_frontend; fi
        echo -e "${GREEN}Setup complete! Run './run.sh' to start HITS.${NC}"
        ;;
    --check|-c)
        if activate_venv; then preflight_checks; fi
        ;;
    --dev|-d)
        run_dev
        ;;
    --build|-b)
        if check_node; then build_frontend; fi
        ;;
    --python-only)
        run_python_server
        ;;
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --test, -t          Run tests"
        echo "  --setup, -s         Setup environment (Python + frontend)"
        echo "  --check, -c         Run pre-flight checks"
        echo "  --dev,   -d         Start in development mode (Vite HMR)"
        echo "  --build, -b         Build frontend only"
        echo "  --python-only       Use Python-only mode (no Node.js)"
        echo "  --help,  -h         Show this help"
        echo ""
        echo "Without options, HITS starts the production server."
        echo "  - With Node.js: uses Express server + Python backend"
        echo "  - Without Node.js: falls back to Python-only mode"
        echo ""
        echo "Environment variables:"
        echo "  HITS_PORT           Server port (default: 8765)"
        echo "  HITS_REBUILD        Set to '1' to force frontend rebuild"
        ;;
    *)
        # Primary: Node.js mode if available, fallback to Python-only
        NODE_ARGS=""
        if [ "${1:-}" = "--dev" ]; then
            NODE_ARGS="--dev"
        fi

        if check_node; then
            run_node_server $NODE_ARGS
        else
            run_python_server
        fi
        ;;
esac
