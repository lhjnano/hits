#!/bin/bash
# ──────────────────────────────────────────────────────────────
# HITS Prompt Capture for Claude Code
#
# Run from Claude Code UserPromptSubmit hook:
#   Saves the user's prompt to a temp file for the Stop hook to use.
#
# Input: JSON on stdin with {"prompt": "user's message", "session_id": "...", ...}
# ──────────────────────────────────────────────────────────────

INPUT=$(cat)

PROMPT=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('prompt', ''))
except: print('')
" 2>/dev/null)

SESSION_ID=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('session_id', ''))
except: print('')
" 2>/dev/null)

# Save to a per-session temp file
if [ -n "$PROMPT" ] && [ -n "$SESSION_ID" ]; then
    mkdir -p "$HOME/.hits/data/tmp"
    echo "$PROMPT" > "$HOME/.hits/data/tmp/prompt_${SESSION_ID}.txt"
fi

exit 0
