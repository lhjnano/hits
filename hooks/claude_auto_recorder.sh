#!/bin/bash
# ──────────────────────────────────────────────────────────────
# HITS Auto-Recorder for Claude Code
#
# Run from Claude Code Stop / StopFailure hook.
# Captures rich session summary including:
#   - User prompt (from UserPromptSubmit hook or transcript)
#   - Assistant's last message (from hook input)
#   - Modified files (from git diff + transcript tool_use)
#   - Tool usage summary
#   - Session context for handover
#
# Input: JSON on stdin from Claude Code (Stop/StopFailure event)
# ──────────────────────────────────────────────────────────────

HITS_DIR="$HOME/.hits/data/work_logs"
CHECKPOINT_DIR="$HOME/.hits/data/checkpoints"
PROMPT_DIR="$HOME/.hits/data/tmp"

# Read hook input from stdin
INPUT=$(cat)

# ── Extract fields from JSON input ────────────────────────────

extract_field() {
    echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('$1', ''))
except: print('')
" 2>/dev/null
}

SESSION_ID=$(extract_field 'session_id')
TRANSCRIPT_PATH=$(extract_field 'transcript_path')
CWD=$(extract_field 'cwd')
LAST_ASSISTANT_MSG=$(extract_field 'last_assistant_message')
HOOK_EVENT=$(extract_field 'hook_event_name')
STOP_HOOK_ACTIVE=$(extract_field 'stop_hook_active')
ERROR_TYPE=$(extract_field 'error')

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

# ── Get request_text (3 fallback levels) ─────────────────────

REQUEST_TEXT=""

# Level 1: Read prompt saved by UserPromptSubmit hook
if [ -z "$REQUEST_TEXT" ] && [ -n "$SESSION_ID" ]; then
    PROMPT_FILE="$PROMPT_DIR/prompt_${SESSION_ID}.txt"
    if [ -f "$PROMPT_FILE" ]; then
        REQUEST_TEXT=$(head -c 500 "$PROMPT_FILE" 2>/dev/null)
    fi
fi

# Level 2: Parse transcript (last human message)
if [ -z "$REQUEST_TEXT" ] && [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
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
                content = None

                if msg.get('type') == 'human':
                    m = msg.get('message', {})
                    content = m.get('content', '') if isinstance(m, dict) else ''
                elif msg.get('role') == 'user':
                    content = msg.get('content', '')

                if content is None:
                    continue

                if isinstance(content, list):
                    texts = []
                    for c in content:
                        if isinstance(c, dict) and c.get('type') == 'text':
                            texts.append(c.get('text', ''))
                        elif isinstance(c, str):
                            texts.append(c)
                    content = ' '.join(texts)

                if content and str(content).strip():
                    last_human = str(content).strip()[:500]
            except: pass
    if last_human:
        print(last_human)
except: pass
" 2>/dev/null)
fi

# Level 3: Fallback
if [ -z "$REQUEST_TEXT" ]; then
    REQUEST_TEXT="Claude Code session"
fi

# ── Extract modified files from git ──────────────────────────
# Only look at files changed during this session (not staged/unstaged diff)

MODIFIED_FILES=""
if [ -d "$PROJECT_PATH/.git" ]; then
    MODIFIED_FILES=$(git -C "$PROJECT_PATH" diff --name-only HEAD 2>/dev/null || true)
    if [ -z "$MODIFIED_FILES" ]; then
        MODIFIED_FILES=$(git -C "$PROJECT_PATH" diff --name-only --cached 2>/dev/null || true)
    fi
fi

# ── Extract tool_use file paths from transcript ───────────────
# Catches files that were edited/read/written during the session

TRANSCRIPT_FILES=""
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    TRANSCRIPT_FILES=$(python3 -c "
import json, sys, re
try:
    files = set()
    with open('$TRANSCRIPT_PATH') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                msg = json.loads(line)

                # Extract from tool_use input (edit, write, read paths)
                if msg.get('type') == 'assistant':
                    content = msg.get('message', {}).get('content', [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get('type') == 'tool_use':
                                inp = block.get('input', {})
                                for key in ['file_path', 'filePath', 'path', 'destination']:
                                    val = inp.get(key, '')
                                    if val and isinstance(val, str) and not val.startswith('~'):
                                        files.add(val)
            except: pass

    if files:
        print('\\n'.join(sorted(files)))
except: pass
" 2>/dev/null)
fi

# Merge unique file lists
ALL_FILES=$(echo -e "${MODIFIED_FILES}\n${TRANSCRIPT_FILES}" | sort -u | grep -v '^$' | head -20)

# ── Count tool uses from transcript ──────────────────────────

TOOL_COUNT=0
TOOL_NAMES=""
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    TOOL_COUNT=$(grep -c '"tool_name"\|"type":"tool_use"\|"type":"tool_result"' "$TRANSCRIPT_PATH" 2>/dev/null || true)
    TOOL_NAMES=$(python3 -c "
import json, sys
from collections import Counter
try:
    names = Counter()
    with open('$TRANSCRIPT_PATH') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                msg = json.loads(line)
                if msg.get('type') == 'assistant':
                    content = msg.get('message', {}).get('content', [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get('type') == 'tool_use':
                                names[block.get('name', 'unknown')] += 1
            except: pass
    for name, count in names.most_common(10):
        print(f'{name}({count})')
except: pass
" 2>/dev/null)
fi

# ── Build rich context ───────────────────────────────────────

CONTEXT_PARTS=""

# Add last assistant message (truncated)
if [ -n "$LAST_ASSISTANT_MSG" ]; then
    # Truncate to 1000 chars for context
    ASSISTANT_SUMMARY=$(echo "$LAST_ASSISTANT_MSG" | head -c 1000)
    CONTEXT_PARTS="${CONTEXT_PARTS}Assistant summary: ${ASSISTANT_SUMMARY}"
fi

# Add tool usage
if [ -n "$TOOL_NAMES" ]; then
    CONTEXT_PARTS="${CONTEXT_PARTS}\n\nTools used (${TOOL_COUNT}): ${TOOL_NAMES}"
else
    CONTEXT_PARTS="${CONTEXT_PARTS}\n\nTools used: ${TOOL_COUNT}"
fi

# Add error info for StopFailure
if [ -n "$ERROR_TYPE" ]; then
    CONTEXT_PARTS="${CONTEXT_PARTS}\n\nSession ended with error: ${ERROR_TYPE}"
    if [ "$ERROR_TYPE" = "max_output_tokens" ]; then
        CONTEXT_PARTS="${CONTEXT_PARTS} (token limit reached — session incomplete)"
    fi
fi

# ── Build files_modified list ────────────────────────────────

FILES_JSON="[]"
if [ -n "$ALL_FILES" ]; then
    FILES_JSON=$(echo "$ALL_FILES" | python3 -c "
import json, sys
files = [line.strip() for line in sys.stdin if line.strip()]
print(json.dumps(files))
" 2>/dev/null)
fi

# ── Generate work log entry ──────────────────────────────────

mkdir -p "$HITS_DIR"

LOG_ID=$(python3 -c "from uuid import uuid4; print(uuid4().hex[:8])" 2>/dev/null || echo "$$")
TIMESTAMP=$(python3 -c "from datetime import datetime; print(datetime.now().isoformat())" 2>/dev/null || date -Iseconds)

LOG_FILE="$HITS_DIR/${LOG_ID}.json"

# Determine tags based on event type
TAGS='["auto", "stop-hook"]'
if [ -n "$ERROR_TYPE" ]; then
    TAGS='["auto", "stop-hook", "error", "'"${ERROR_TYPE}"'"]'
fi

python3 -c "
import json, sys

request_text = sys.argv[2]
context_raw = sys.argv[5]

# Properly join context
context_parts = context_raw.split('\\n')
context = '\\n'.join(context_parts)

files_json = sys.argv[7]
try:
    files = json.loads(files_json)
except:
    files = []

tags_raw = sys.argv[8]
try:
    tags = json.loads(tags_raw)
except:
    tags = ['auto', 'stop-hook']

log = {
    'id': sys.argv[1],
    'source': 'ai_session',
    'request_text': request_text,
    'performed_by': 'claude',
    'performed_at': sys.argv[3],
    'project_path': sys.argv[4],
    'context': context,
    'tags': tags,
    'files_modified': files,
    'result_type': 'summary',
    'result_data': {
        'last_assistant_message': sys.argv[6][:2000],
        'tool_count': int(sys.argv[9]) if sys.argv[9].isdigit() else 0,
        'tool_names': sys.argv[10],
        'error_type': sys.argv[11],
        'hook_event': sys.argv[12]
    },
    'created_at': sys.argv[3]
}
with open(sys.argv[13], 'w') as f:
    json.dump(log, f, indent=2, ensure_ascii=False)
" "$LOG_ID" "$REQUEST_TEXT" "$TIMESTAMP" "$PROJECT_PATH" "$CONTEXT_PARTS" \
  "${LAST_ASSISTANT_MSG}" "$FILES_JSON" "$TAGS" "$TOOL_COUNT" "$TOOL_NAMES" \
  "$ERROR_TYPE" "$HOOK_EVENT" "$LOG_FILE" 2>/dev/null

# ── Update index — list[str] format (matches file_store.py) ──

INDEX_FILE="$HITS_DIR/index.json"
python3 -c "
import json
try:
    with open('$INDEX_FILE') as f:
        data = json.load(f)
    if isinstance(data, dict):
        entries = [e['id'] if isinstance(e, dict) else e for e in data.get('entries', [])]
    elif isinstance(data, list):
        entries = data
    else:
        entries = []
    if '$LOG_ID' not in entries:
        entries.append('$LOG_ID')
    with open('$INDEX_FILE', 'w') as f:
        json.dump(entries, f)
except:
    try:
        import os
        os.makedirs('$HITS_DIR', exist_ok=True)
        with open('$INDEX_FILE', 'w') as f:
            json.dump(['$LOG_ID'], f)
    except:
        pass
" 2>/dev/null

# ── Also save as checkpoint for resume ───────────────────────
# This ensures hits_resume() can pick it up even if hits_auto_checkpoint wasn't called

mkdir -p "$CHECKPOINT_DIR"

python3 -c "
import json, os, sys

project_path = sys.argv[1]
log_id = sys.argv[2]
timestamp = sys.argv[3]
request_text = sys.argv[4]
assistant_msg = sys.argv[5][:2000]
files_json = sys.argv[6]
error_type = sys.argv[7]
tool_names = sys.argv[8]

try:
    files = json.loads(files_json)
except:
    files = []

# Build checkpoint
current_state = 'Session recorded by Stop hook'
if assistant_msg:
    current_state = assistant_msg[:500]

if error_type:
    current_state = f'[Session interrupted: {error_type}] ' + current_state

checkpoint = {
    'id': log_id,
    'project_path': project_path,
    'purpose': request_text[:200],
    'current_state': current_state,
    'completion_pct': 0,
    'next_steps': [],
    'required_context': [],
    'decisions': [],
    'blocks': [],
    'files_modified': files,
    'created_at': timestamp,
    'source': 'stop-hook',
    'tool_summary': tool_names,
    'error_type': error_type
}

# Save to project-specific checkpoint directory
safe_project = project_path.replace('/', '_')
cp_dir = os.path.join('$CHECKPOINT_DIR', safe_project)
os.makedirs(cp_dir, exist_ok=True)

cp_file = os.path.join(cp_dir, f'{log_id}.json')
with open(cp_file, 'w') as f:
    json.dump(checkpoint, f, indent=2, ensure_ascii=False)

# Update latest pointer
latest_file = os.path.join(cp_dir, '_latest.json')
with open(latest_file, 'w') as f:
    json.dump({'id': log_id, 'file': cp_file, 'created_at': timestamp}, f, indent=2)
" "$PROJECT_PATH" "$LOG_ID" "$TIMESTAMP" "$REQUEST_TEXT" \
  "${LAST_ASSISTANT_MSG}" "$FILES_JSON" "$ERROR_TYPE" "$TOOL_NAMES" 2>/dev/null

# ── Clean up prompt temp file ────────────────────────────────

if [ -n "$SESSION_ID" ]; then
    rm -f "$PROMPT_DIR/prompt_${SESSION_ID}.txt" 2>/dev/null
fi

# ── Trigger knowledge extraction ──────────────────────────────
# Async: fire and forget, don't block the hook
# Tries local HITS server first, falls back to direct Python extraction

HITS_PORT="${HITS_PORT:-8765}"

# Try API first (fast, no Python startup if server is running)
curl -s -X POST "http://localhost:${HITS_PORT}/api/knowledge/extract" \
    -H "Content-Type: application/json" \
    -d "{\"log_id\": \"${LOG_ID}\"}" > /dev/null 2>&1 &

# Also try direct extraction as fallback (for when server isn't running)
python3 -c "
import sys, json, os
sys.path.insert(0, os.path.expanduser('~/.hits'))
try:
    from pathlib import Path
    sys.path.insert(0, str(Path.home() / 'node_modules' / '@purpleraven' / 'hits'))
    from hits_core.service.knowledge_extractor import KnowledgeExtractor
    ext = KnowledgeExtractor()
    ext.extract_from_work_log('${LOG_ID}')
except:
    pass
" 2>/dev/null &

exit 0
