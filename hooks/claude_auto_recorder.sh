#!/bin/bash
# ──────────────────────────────────────────────────────────────
# HITS Auto-Recorder for Claude Code
#
# Run from Claude Code Stop hook:
#   When Claude finishes responding, this script automatically
#   records a work log entry via the HITS Python backend.
#
# Input: JSON on stdin from Claude Code (Stop event)
# ──────────────────────────────────────────────────────────────

HITS_DIR="$HOME/.hits/data/work_logs"
SIGNALS_DIR="$HOME/.hits/data/signals/pending"

# Read hook input from stdin
INPUT=$(cat)

# Extract fields from JSON input
SESSION_ID=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('session_id', ''))
except: print('')
" 2>/dev/null)

TRANSCRIPT_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('transcript_path', ''))
except: print('')
" 2>/dev/null)

CWD=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('cwd', ''))
except: print('')
" 2>/dev/null)

# Skip if no meaningful context
if [ -z "$CWD" ]; then
    exit 0
fi

# Detect project path (git root from cwd)
PROJECT_PATH="$CWD"
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

# Extract last user prompt from transcript for request_text
REQUEST_TEXT=""
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    REQUEST_TEXT=$(python3 -c "
import json, sys
try:
    last_human = ''
    with open('$TRANSCRIPT_PATH') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                msg = json.loads(line)
                if msg.get('type') == 'human' or msg.get('role') == 'user':
                    content = msg.get('message', {})
                    if isinstance(content, dict):
                        content = content.get('content', '')
                    if isinstance(content, list):
                        content = ' '.join(
                            c.get('text', '') for c in content
                            if isinstance(c, dict) and c.get('type') == 'text'
                        )
                    if content:
                        last_human = str(content)[:200]
            except: pass
    print(last_human)
except: pass
" 2>/dev/null)
fi

if [ -z "$REQUEST_TEXT" ]; then
    REQUEST_TEXT="Claude Code session"
fi

# Count tool uses from transcript for context
TOOL_COUNT=0
FILES_MODIFIED=""
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    TOOL_COUNT=$(grep -c '"tool_name"' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
fi

CONTEXT="Auto-recorded by Stop hook. Tools used: ${TOOL_COUNT}."

# Generate work log entry
mkdir -p "$HITS_DIR"

LOG_ID=$(python3 -c "from uuid import uuid4; print(uuid4().hex[:8])" 2>/dev/null || echo "$$")
TIMESTAMP=$(python3 -c "from datetime import datetime; print(datetime.now().isoformat())" 2>/dev/null || date -Iseconds)

LOG_FILE="$HITS_DIR/${LOG_ID}.json"

python3 -c "
import json
log = {
    'id': '$LOG_ID',
    'source': 'ai_session',
    'request_text': '''${REQUEST_TEXT}''',
    'performed_by': 'claude',
    'performed_at': '$TIMESTAMP',
    'project_path': '$PROJECT_PATH',
    'context': '$CONTEXT',
    'tags': ['auto', 'stop-hook'],
    'result_type': 'none',
    'result_data': {},
    'created_at': '$TIMESTAMP'
}
with open('$LOG_FILE', 'w') as f:
    json.dump(log, f, indent=2, ensure_ascii=False)
" 2>/dev/null

# Update index
INDEX_FILE="$HITS_DIR/index.json"
if [ -f "$INDEX_FILE" ]; then
    python3 -c "
import json
try:
    with open('$INDEX_FILE') as f:
        index = json.load(f)
    index['total'] = index.get('total', 0) + 1
    entries = index.get('entries', [])
    entries.append({'id': '$LOG_ID', 'file': '${LOG_ID}.json'})
    index['entries'] = entries[-100:]  # Keep last 100
    with open('$INDEX_FILE', 'w') as f:
        json.dump(index, f, indent=2)
except:
    pass
" 2>/dev/null
else
    python3 -c "
import json
index = {'total': 1, 'entries': [{'id': '$LOG_ID', 'file': '${LOG_ID}.json'}]}
with open('$INDEX_FILE', 'w') as f:
    json.dump(index, f, indent=2)
" 2>/dev/null
fi

# Silent success - no output to avoid cluttering Claude's context
exit 0
