#!/bin/bash
# ──────────────────────────────────────────────────────────────
# HITS Signal Watcher for Claude Code
#
# Run from Claude Code SessionStart hook:
#   ~/.claude/settings.json:
#   {
#     "hooks": {
#       "SessionStart": [{
#         "type": "command",
#         "command": "bash /home/lhjnano/source/hits/hooks/claude_signal_watcher.sh"
#       }]
#     }
#   }
#
# Behavior: checks ~/.hits/signals/pending/ for incoming signals
#           and outputs them to stderr for auto-injection into Claude session
# ──────────────────────────────────────────────────────────────

SIGNALS_DIR="$HOME/.hits/data/signals/pending"
RECIPIENT="claude"

# Exit if signals directory doesn't exist
if [ ! -d "$SIGNALS_DIR" ]; then
    exit 0
fi

# pending/ 에서 claude 또는 any 대상 시그널 찾기
FOUND=0
for sig_file in "$SIGNALS_DIR"/*.json; do
    [ -f "$sig_file" ] || continue

    # JSON에서 recipient 추출
    recipient=$(python3 -c "
import json, sys
try:
    d = json.load(open('$sig_file'))
    print(d.get('recipient', 'any'))
except: print('any')
" 2>/dev/null)

    # recipient가 'claude' 또는 'any'인지 확인
    if [ "$recipient" = "$RECIPIENT" ] || [ "$recipient" = "any" ]; then
        # 시그널 내용 추출
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
    lines.append(f'👉 Use hits_signal_consume(signal_id="{sig_id}", consumed_by="claude") to acknowledge.')
    print('\\n'.join(lines))
except Exception as e:
    print(f'Signal read error: {e}')
" 2>/dev/null)

        if [ -n "$summary" ]; then
            # stderr로 출력하면 Claude Code에 시스템 메시지로 주입됨
            echo "$summary" >&2
            FOUND=1
        fi
    fi
done

if [ "$FOUND" -eq 0 ]; then
    echo "ℹ️ HITS: No pending handover signals." >&2
fi

# ── Auto Resume ────────────────────────────────────────────
# 현재 프로젝트에 checkpoint가 있으면 자동으로 resume 정보 제공
CHECKPOINT_DIR="$HOME/.hits/data/checkpoints"
CWD_PROJECT=""

# CWD에서 git root 탐색
current="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
    # 프로젝트 경로를 디렉토리명으로 변환 (/home/user/project → _home_user_project)
    PROJECT_KEY=$(echo "$CWD_PROJECT" | sed 's|/|_|g')
    LATEST_CP="$CHECKPOINT_DIR/$PROJECT_KEY/latest.json"

    if [ -f "$LATEST_CP" ]; then
        # Checkpoint 내용을 stderr로 출력
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

# ── Background Signal Watcher ────────────────────────────────
# Poll for new signals every 30s in background (if not already running)
WATCHER_MARKER="/tmp/hits_signal_watcher_claude_$$.pid"

if [ -z "$HITS_WATCHER_RUNNING" ]; then
    export HITS_WATCHER_RUNNING=1
    
    _watch_signals() {
        while true; do
            sleep 30
            for sig_file in "$SIGNALS_DIR"/*.json; do
                [ -f "$sig_file" ] || continue
                recipient=$(python3 -c "
import json
try:
    d = json.load(open('$sig_file'))
    print(d.get('recipient', 'any'))
except: print('any')
" 2>/dev/null)
                if [ "$recipient" = "$RECIPIENT" ] || [ "$recipient" = "any" ]; then
                    echo "📬 HITS: New handover signal detected! Run hits_resume() or hits_signal_check() to load." >&2
                    break
                fi
            done
        done
    }
    
    _watch_signals &
    echo "$!" > "$WATCHER_MARKER"
fi
