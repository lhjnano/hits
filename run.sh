#!/bin/bash
# HITS Launcher for Linux/macOS/WSL

cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${GREEN}HITS - Hybrid Intel Trace System${NC}"
echo ""

VENV_PATH="$PWD/venv"

setup_venv() {
    echo -e "${CYAN}Setting up virtual environment...${NC}"
    python3 -m venv "$VENV_PATH"
    source "$VENV_PATH/bin/activate"
    
    echo -e "${CYAN}Installing dependencies...${NC}"
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
from hits_core.ai import SemanticCompressor
print('OK')
" 2>/dev/null; then
        echo -e "${RED}    ✗ Core imports failed${NC}"
        echo "    Run: ./run.sh --setup"
        failed=1
    else
        echo -e "${GREEN}    ✓ Core imports OK${NC}"
    fi
    
    echo "  [2/3] Checking UI imports..."
    if ! python -c "
from hits_ui.panel import PanelWindow
from hits_ui.widgets import NodeCard
from hits_ui.theme import Theme
print('OK')
" 2>/dev/null; then
        echo -e "${RED}    ✗ UI imports failed${NC}"
        echo "    Run: ./run.sh --setup"
        failed=1
    else
        echo -e "${GREEN}    ✓ UI imports OK${NC}"
    fi
    
    echo "  [3/3] Checking config..."
    if [ ! -f "config/settings.yaml" ]; then
        echo -e "${RED}    ✗ config/settings.yaml not found${NC}"
        failed=1
    else
        echo -e "${GREEN}    ✓ Config OK${NC}"
    fi
    
    echo ""
    return $failed
}

run_tests() {
    echo -e "${CYAN}Running import verification tests...${NC}"
    echo ""
    
    if [ ! -d "$VENV_PATH" ]; then
        setup_venv
    else
        activate_venv
    fi
    
    pip install pytest pytest-asyncio -q 2>/dev/null
    
    python -m pytest tests/ui/test_imports.py -v --tb=short
    local result=$?
    
    if [ $result -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ All import tests passed!${NC}"
    else
        echo ""
        echo -e "${RED}✗ Some tests failed. Please fix the errors above.${NC}"
    fi
    return $result
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

run_app() {
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
    echo -e "${GREEN}Starting HITS...${NC}"
    python -m hits_ui.main
}

# Main
check_python

case "${1:-}" in
    --test|-t)
        run_tests
        ;;
    --setup|-s)
        setup_venv
        echo -e "${GREEN}Setup complete! Run './run.sh' to start HITS.${NC}"
        ;;
    --check|-c)
        preflight_checks
        ;;
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --test, -t    Run import verification tests"
        echo "  --setup, -s   Setup virtual environment only"
        echo "  --check, -c   Run pre-flight checks only"
        echo "  --help, -h    Show this help"
        echo ""
        echo "Without options, HITS will start normally."
        ;;
    *)
        run_app
        ;;
esac
