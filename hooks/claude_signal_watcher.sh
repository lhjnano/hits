#!/bin/bash
# ──────────────────────────────────────────────────────────────
# HITS Signal Watcher for Claude Code
#
# Claude Code SessionStart 훅에서 실행:
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
# 동작: ~/.hits/signals/pending/ 에 대기 중인 시그널이 있으면
#       stderr로 메시지를 출력하여 Claude 세션에 자동 주입
# ──────────────────────────────────────────────────────────────

SIGNALS_DIR="$HOME/.hits/data/signals/pending"
RECIPIENT="claude"

# 시그널 디렉토리가 없으면 종료
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
    lines.append(f'📬 HITS 인수인계 시그널 감지!')
    lines.append(f'  보낸이: {sender}')
    lines.append(f'  유형: {sig_type}')
    lines.append(f'  우선순위: {priority}')
    lines.append(f'  요약: {summary}')
    if pending:
        lines.append(f'  미완료 항목:')
        for item in pending[:5]:
            lines.append(f'    - {item}')
    lines.append(f'  시그널 ID: {sig_id}')
    lines.append(f'')
    lines.append(f'👉 hits_get_handover()로 전체 컨텍스트를 확인하고,')
    lines.append(f'👉 hits_signal_consume(signal_id=\"{sig_id}\", consumed_by=\"claude\")로 시그널을 소진하세요.')
    print('\\n'.join(lines))
except Exception as e:
    print(f'시그널 읽기 오류: {e}')
" 2>/dev/null)

        if [ -n "$summary" ]; then
            # stderr로 출력하면 Claude Code에 시스템 메시지로 주입됨
            echo "$summary" >&2
            FOUND=1
        fi
    fi
done

if [ "$FOUND" -eq 0 ]; then
    echo "ℹ️ HITS: 대기 중인 인수인계 시그널이 없습니다." >&2
fi
