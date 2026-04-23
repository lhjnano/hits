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
                # Claude Code transcript format: {"type": "human", "message": {"content": ...}}
                # or {"role": "user", "content": ...}
                content = None

                # Format 1: type=human with nested message
                if msg.get('type') == 'human':
                    m = msg.get('message', {})
                    content = m.get('content', '') if isinstance(m, dict) else ''

                # Format 2: role=user
                elif msg.get('role') == 'user':
                    content = msg.get('content', '')

                if content is None:
                    continue

                # Handle content as list of blocks
                if isinstance(content, list):
                    texts = []
                    for c in content:
                        if isinstance(c, dict) and c.get('type') == 'text':
                            texts.append(c.get('text', ''))
                        elif isinstance(c, str):
                            texts.append(c)
                    content = ' '.join(texts)

                if content and str(content).strip():
                    last_human = str(content).strip()[:200]
            except: pass
    if last_human:
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
    TOOL_COUNT=$(grep -c '"tool_name"\|"type":"tool_use"\|"type":"tool_result"' "$TRANSCRIPT_PATH" 2>/dev/null || true)
fi

CONTEXT="Auto-recorded by Stop hook. Tools used: ${TOOL_COUNT}."

# Generate work log entry
mkdir -p "$HITS_DIR"

LOG_ID=$(python3 -c "from uuid import uuid4; print(uuid4().hex[:8])" 2>/dev/null || echo "$$")
TIMESTAMP=$(python3 -c "from datetime import datetime; print(datetime.now().isoformat())" 2>/dev/null || date -Iseconds)

LOG_FILE="$HITS_DIR/${LOG_ID}.json"

python3 -c "
import json, sys
request_text = sys.argv[1]
log = {
    'id': sys.argv[2],
    'source': 'ai_session',
    'request_text': request_text,
    'performed_by': 'claude',
    'performed_at': sys.argv[3],
    'project_path': sys.argv[4],
    'context': sys.argv[5],
    'tags': ['auto', 'stop-hook'],
    'result_type': 'none',
    'result_data': {},
    'created_at': sys.argv[3]
}
with open(sys.argv[6], 'w') as f:
    json.dump(log, f, indent=2, ensure_ascii=False)
" "$REQUEST_TEXT" "$LOG_ID" "$TIMESTAMP" "$PROJECT_PATH" "$CONTEXT" "$LOG_FILE" 2>/dev/null

# Update index — use list[str] format to match file_store.py
INDEX_FILE="$HITS_DIR/index.json"
python3 -c "
import json, sys
try:
    # Read existing index (supports both list and dict formats)
    with open('$INDEX_FILE') as f:
        data = json.load(f)

    # Normalize to list[str] format (file_store.py format)
    if isinstance(data, dict):
        entries = [e['id'] if isinstance(e, dict) else e for e in data.get('entries', [])]
    elif isinstance(data, list):
        entries = data
    else:
        entries = []

    # Append new entry
    if '$LOG_ID' not in entries:
        entries.append('$LOG_ID')

    # Write as list[str]
    with open('$INDEX_FILE', 'w') as f:
        json.dump(entries, f)
except Exception as e:
    # If index file doesn't exist or is corrupt, create fresh
    try:
        import os
        os.makedirs('$HITS_DIR', exist_ok=True)
        with open('$INDEX_FILE', 'w') as f:
            json.dump(['$LOG_ID'], f)
    except:
        pass
" 2>/dev/null

# Silent success - no output to avoid cluttering Claude's context
exit 0
