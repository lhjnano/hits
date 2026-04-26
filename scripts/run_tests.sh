#!/bin/bash
# ──────────────────────────────────────────────────────────────
# HITS Test Runner
# ──────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_SCRIPT="$SCRIPT_DIR/test_server.sh"
PORT=8765

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

test_passed=0
test_failed=0
test_total=0

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((test_passed++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((test_failed++))
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

# Setup
setup() {
    log_info "Setting up test environment..."

    # Clean data
    $SERVER_SCRIPT clean-all > /dev/null 2>&1 || true
    sleep 1

    # Start server
    $SERVER_SCRIPT start > /dev/null 2>&1
    sleep 3

    # Check server is running
    if ! curl -s "http://localhost:$PORT/api/health" > /dev/null 2>&1; then
        echo "Failed to start server"
        exit 1
    fi

    log_info "Test environment ready"
}

# Teardown
teardown() {
    log_info "Cleaning up..."
    $SERVER_SCRIPT stop > /dev/null 2>&1 || true
    $SERVER_SCRIPT clean > /dev/null 2>&1 || true
}

# API Health Check
test_health() {
    ((test_total++))
    log_test "API Health Check"

    local response=$(curl -s "http://localhost:$PORT/api/health")
    local status=$(echo "$response" | jq -r '.success' 2>/dev/null)

    if [ "$status" = "true" ]; then
        log_pass "Health check returned success"
    else
        log_fail "Health check failed: $response"
    fi
}

# i18n Test - Check if i18n file is valid JSON
test_i18n_file() {
    ((test_total++))
    log_test "i18n file validation"

    local i18n_file="$PROJECT_ROOT/hits_web/src/lib/i18n.ts"

    if [ ! -f "$i18n_file" ]; then
        log_fail "i18n.ts file not found"
        return
    fi

    # Check if file contains expected keys
    if grep -q "'tasks.feedbackStarted':" "$i18n_file"; then
        log_pass "i18n.ts contains new tasks keys"
    else
        log_fail "i18n.ts missing new tasks keys"
    fi

    # Check Korean translations
    if grep -q "'tasks.feedbackStarted': '🚀 작업 시작'," "$i18n_file"; then
        log_pass "Korean translations present"
    else
        log_fail "Korean translations missing"
    fi
}

# Checkpoint API Test
test_checkpoint_resume() {
    ((test_total++))
    log_test "Checkpoint Resume API"

    local response=$(curl -s "http://localhost:$PORT/api/checkpoint/resume?project_path=$PROJECT_ROOT")
    local success=$(echo "$response" | jq -r '.success' 2>/dev/null)

    # Should succeed even if no checkpoint exists
    if [ "$success" = "true" ]; then
        log_pass "Checkpoint resume API endpoint accessible"
    else
        log_fail "Checkpoint resume API failed: $response"
    fi
}

# Signal API Test
test_signal_check() {
    ((test_total++))
    log_test "Signal Check API"

    local response=$(curl -s "http://localhost:$PORT/api/signals/check")
    local success=$(echo "$response" | jq -r '.success' 2>/dev/null)

    if [ "$success" = "true" ]; then
        log_pass "Signal check API endpoint accessible"
    else
        log_fail "Signal check API failed: $response"
    fi
}

# Instructions File Test
test_instructions_file() {
    ((test_total++))
    log_test "OpenCode Instructions File"

    local instructions_file="$HOME/.config/opencode/instructions/hits-resume.md"

    if [ ! -f "$instructions_file" ]; then
        log_fail "Instructions file not found. Run: node postinstall.cjs --opencode"
        return
    fi

    if grep -q "hits_resume()" "$instructions_file"; then
        log_pass "Instructions file contains hits_resume() guidance"
    else
        log_fail "Instructions file missing hits_resume() guidance"
    fi

    if grep -q "hits_auto_checkpoint()" "$instructions_file"; then
        log_pass "Instructions file contains hits_auto_checkpoint() guidance"
    else
        log_fail "Instructions file missing hits_auto_checkpoint() guidance"
    fi
}

# Signal Watcher Test
test_signal_watcher() {
    ((test_total++))
    log_test "OpenCode Signal Watcher"

    local watcher_file="$HOME/.hits/hooks/opencode_signal_watcher.sh"

    if [ ! -f "$watcher_file" ]; then
        log_fail "Signal watcher not found"
        return
    fi

    # Check for RECIPIENT="" setting
    if grep -q 'RECIPIENT=""' "$watcher_file"; then
        log_pass "Signal watcher has RECIPIENT=\"\" setting"
    else
        log_fail "Signal watcher missing RECIPIENT=\"\" setting"
    fi

    # Check for English comments
    if grep -q "Usage with OpenCode file watching:" "$watcher_file"; then
        log_pass "Signal watcher has English comments"
    else
        log_fail "Signal watcher comments not updated to English"
    fi
}

# Postinstall Test
test_postinstall() {
    ((test_total++))
    log_test "Postinstall Script"

    local postinstall_file="$PROJECT_ROOT/postinstall.cjs"

    if [ ! -f "$postinstall_file" ]; then
        log_fail "postinstall.cjs not found"
        return
    fi

    # Check for instructions directory creation
    if grep -q "instructionsDir" "$postinstall_file"; then
        log_pass "Postinstall creates instructions directory"
    else
        log_fail "Postinstall missing instructions directory creation"
    fi

    # Check for hits-resume.md content
    if grep -q "hits-resume.md" "$postinstall_file"; then
        log_pass "Postinstall creates hits-resume.md file"
    else
        log_fail "Postinstall missing hits-resume.md creation"
    fi
}

# Run all tests
run_all_tests() {
    log_info "Starting HITS tests..."
    echo ""

    test_i18n_file
    test_postinstall
    test_instructions_file
    test_signal_watcher

    echo ""
    log_info "Starting API tests (server required)..."
    echo ""

    setup

    test_health
    test_checkpoint_resume
    test_signal_check

    teardown

    echo ""
    echo "=========================================="
    echo "Test Results:"
    echo "  Total:  $test_total"
    echo -e "  ${GREEN}Passed: $test_passed${NC}"
    echo -e "  ${RED}Failed: $test_failed${NC}"
    echo "=========================================="

    if [ $test_failed -eq 0 ]; then
        log_info "All tests passed! ✅"
        return 0
    else
        log_info "Some tests failed ❌"
        return 1
    fi
}

# Main
case "${1:-all}" in
    all)
        run_all_tests
        ;;
    api)
        setup
        test_health
        test_checkpoint_resume
        test_signal_check
        teardown
        ;;
    i18n)
        test_i18n_file
        ;;
    instructions)
        test_instructions_file
        ;;
    watcher)
        test_signal_watcher
        ;;
    postinstall)
        test_postinstall
        ;;
    *)
        echo "Usage: $0 {all|api|i18n|instructions|watcher|postinstall}"
        exit 1
        ;;
esac
