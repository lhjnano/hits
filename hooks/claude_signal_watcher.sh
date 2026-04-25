#!/bin/bash
# ──────────────────────────────────────────────────────────────
# HITS Signal Watcher for Claude Code
#
# Run from Claude Code SessionStart hook:
#   ~/.claude/settings.json:
#   {
#     "hooks": {
#       "SessionStart": [{
#         "matcher": "",
#         "hooks": [{
#           "type": "command",
#           "command": "bash $HOME/.claude/hooks/claude_signal_watcher.sh"
#         }]
#       }]
#     }
#   }
#
# Input: JSON on stdin from Claude Code SessionStart event
#   {"session_id": "...", "cwd": "/path/to/project"}
#
# Behavior:
#   1. Checks ~/.hits/data/signals/pending/ for incoming signals
#   2. Auto-resumes from checkpoint if available for the project
#   3. Outputs to stderr for auto-injection into Claude session
# ──────────────────────────────────────────────────────────────

SIGNALS_DIR="$HOME/.hits/data/signals/pending"
CHECKPOINT_DIR="$HOME/.hits/data/checkpoints"
# Show ALL pending signals regardless of recipient
# User may have sent from Web UI to opencode, claude, or any
RECIPIENT=""  # Empty = match all

# ── Parse hook input from stdin ───────────────────────────────

INPUT=$(cat)

CWD=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('cwd', ''))
except: print('')
" 2>/dev/null)

# Fallback to pwd if cwd not provided
if [ -z "$CWD" ]; then
    CWD="$(pwd)"
fi

# ── Detect project path from CWD ─────────────────────────────

PROJECT_PATH=""
current="$CWD"
for i in $(seq 1 10); do
    if [ -d "$current/.git" ]; then
        PROJECT_PATH="$current"
        break
    fi
    parent=$(dirname "$current")
    [ "$parent" = "$current" ] && break
    current="$parent"
done

# ── Part 1: Check for pending handover signals ────────────────

FOUND=0
if [ -d "$SIGNALS_DIR" ]; then
    for sig_file in "$SIGNALS_DIR"/*.json; do
        [ -f "$sig_file" ] || continue

        recipient=$(python3 -c "
import json
try:
    d = json.load(open('$sig_file'))
    print(d.get('recipient', 'any'))
except: print('any')
" 2>/dev/null)

        if [ "$recipient" = "$RECIPIENT" ] || [ "$recipient" = "any" ] || [ "$recipient" = "opencode" ] || [ "$recipient" = "claude" ] || [ -n "$recipient" ]; then
            summary=$(python3 -c "
import json
try:
    d = json.load(open('$sig_file'))
    sender = d.get('sender', 'unknown')
    summary = d.get('summary', '')
    sig_type = d.get('signal_type', '')
    priority = d.get('priority', 'normal')
    pending = d.get('pending_items', [])
    sig_id = d.get('id', '')

    lines = []
    lines.append(f'HITS handover signal detected!')
    lines.append(f'  From: {sender}')
    lines.append(f'  Type: {sig_type}')
    lines.append(f'  Priority: {priority}')
    lines.append(f'  Summary: {summary}')
    if pending:
        lines.append(f'  Pending items:')
        for item in pending[:5]:
            lines.append(f'    - {item}')
    lines.append(f'  Signal ID: {sig_id}')
    lines.append(f'')
    lines.append(f'Use hits_resume() to load full context.')
    lines.append(f'Use hits_signal_consume(signal_id=\"{sig_id}\", consumed_by=\"claude\") to acknowledge.')
    print(chr(10).join(lines))
except Exception as e:
    pass
" 2>/dev/null)

            if [ -n "$summary" ]; then
                echo "$summary" >&2
                FOUND=1
            fi
        fi
    done
fi

if [ "$FOUND" -eq 0 ]; then
    echo "HITS: No pending handover signals." >&2
fi

# ── Part 2: Auto-resume from checkpoint ───────────────────────

if [ -n "$PROJECT_PATH" ]; then
    PROJECT_KEY=$(echo "$PROJECT_PATH" | sed 's|/|_|g')
    LATEST_CP="$CHECKPOINT_DIR/$PROJECT_KEY/latest.json"

    if [ -f "$LATEST_CP" ]; then
        python3 -c "
import json
try:
    d = json.load(open('$LATEST_CP'))
    purpose = d.get('purpose', 'No purpose set')
    state = d.get('current_state', '')
    pct = d.get('completion_pct', 0)
    performer = d.get('performer', '?')
    steps = d.get('next_steps', [])
    git_branch = d.get('git_branch', '')

    lines = []
    lines.append('HITS RESUME: Last session state')
    lines.append(f'  Purpose: {purpose}')
    lines.append(f'  Progress: {pct}% (by {performer})')
    if git_branch:
        lines.append(f'  git: {git_branch}')
    if state:
        lines.append(f'  Achieved: {state}')
    if steps:
        lines.append(f'  Next steps:')
        for i, s in enumerate(steps[:3], 1):
            action = s.get('action', '')
            cmd = s.get('command', '')
            priority = s.get('priority', 'medium')
            line = f'    {i}. [{priority}] {action}'
            if cmd:
                line += f' -> {cmd}'
            lines.append(line)
    lines.append('')
    lines.append('Use hits_resume() to load full context.')
    print(chr(10).join(lines))
except:
    pass
" >&2 2>/dev/null
    fi
fi
