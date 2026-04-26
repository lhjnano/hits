#!/bin/bash
# ──────────────────────────────────────────────────────────────
# HITS Signal Watcher for OpenCode
#
# Usage with OpenCode file watching:
#   Configure in ~/.config/opencode/opencode.json hooks, or
#   Place in project .opencode/hooks/
#
# Two usage modes:
#   1. Run on SessionStart (check once at session start)
#   2. Use as FileChanged hook watching ~/.hits/signals/pending/
#
# Behavior: When pending signals exist in ~/.hits/signals/pending/,
#           outputs messages to stderr for automatic injection into OpenCode session.
# ──────────────────────────────────────────────────────────────

SIGNALS_DIR="$HOME/.hits/data/signals/pending"
RECIPIENT=""  # Empty = show all pending signals

# Exit if signals directory does not exist
if [ ! -d "$SIGNALS_DIR" ]; then
    exit 0
fi

# Find pending signals targeting opencode or any
FOUND=0
for sig_file in "$SIGNALS_DIR"/*.json; do
    [ -f "$sig_file" ] || continue

    # Extract recipient from JSON
    recipient=$(python3 -c "
import json
try:
    d = json.load(open('$sig_file'))
    print(d.get('recipient', 'any'))
except: print('any')
" 2>/dev/null)

    if [ -n "$recipient" ]; then
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
    lines.append(f'📬 HITS handover signal detected!')
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
    lines.append(f'👉 Use hits_resume() to load full context.')
    lines.append(f'👉 Use hits_signal_consume(signal_id="{sig_id}", consumed_by="opencode") to acknowledge.')
    print('\\n'.join(lines))
except Exception as e:
    print(f'Signal read error: {e}')
" 2>/dev/null)

        if [ -n "$summary" ]; then
            echo "$summary" >&2
            FOUND=1
        fi
    fi
done

if [ "$FOUND" -eq 0 ]; then
    echo "ℹ️ HITS: No pending handover signals." >&2
fi

# ── Auto Resume ────────────────────────────────────────────
# If checkpoint exists for current project, provide resume info automatically
CHECKPOINT_DIR="$HOME/.hits/data/checkpoints"
CWD_PROJECT=""

# Walk up from CWD to find git root
current="$(pwd)"
for i in $(seq 1 10); do
    if [ -d "$current/.git" ]; then
        CWD_PROJECT="$current"
        break
    fi
    parent=$(dirname "$current")
    [ "$parent" = "$current" ] && break
    current="$parent"
done

if [ -n "$CWD_PROJECT" ]; then
    # Convert project path to directory key (/home/user/project → _home_user_project)
    PROJECT_KEY=$(echo "$CWD_PROJECT" | sed 's|/|_|g')
    LATEST_CP="$CHECKPOINT_DIR/$PROJECT_KEY/latest.json"

    if [ -f "$LATEST_CP" ]; then
        # Output checkpoint content to stderr
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
    lines.append('▶ HITS RESUME: Last session state')
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
            icon = {'critical': '🔴', 'high': '🟡'}.get(priority, '🟢')
            line = f'    {i}. {icon} {action}'
            if cmd:
                line += f' → {cmd}'
            lines.append(line)
    lines.append('')
    lines.append('👉 Use hits_resume() to load full context.')
    print('\\n'.join(lines))
except Exception as e:
    pass
" 2>/dev/null | while IFS= read -r line; do echo "$line" >&2; done
    fi
fi
