#!/bin/bash
# ──────────────────────────────────────────────────────────────
# HITS Signal Watcher for OpenCode
#
# OpenCode에서 파일 감시 방식으로 사용:
#   ~/.config/opencode/opencode.json hooks 설정 또는
#   프로젝트 .opencode/hooks/ 에 배치
#
# 두 가지 사용 방식:
#   1. SessionStart에서 실행 (세션 시작 시 1회 확인)
#   2. FileChanged 훅으로 ~/.hits/signals/pending/ 감시
#
# 동작: ~/.hits/signals/pending/ 에 대기 중인 시그널이 있으면
#       stderr로 메시지를 출력하여 OpenCode 세션에 자동 주입
# ──────────────────────────────────────────────────────────────

SIGNALS_DIR="$HOME/.hits/data/signals/pending"
RECIPIENT=""  # Empty = show all pending signals

# 시그널 디렉토리가 없으면 종료
if [ ! -d "$SIGNALS_DIR" ]; then
    exit 0
fi

# pending/ 에서 opencode 또는 any 대상 시그널 찾기
FOUND=0
for sig_file in "$SIGNALS_DIR"/*.json; do
    [ -f "$sig_file" ] || continue

    # JSON에서 recipient 추출
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
# 현재 프로젝트에 checkpoint가 있으면 자동으로 resume 정보 제공
CHECKPOINT_DIR="$HOME/.hits/data/checkpoints"
CWD_PROJECT=""

# CWD에서 git root 탐색
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
