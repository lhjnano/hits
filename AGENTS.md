# AGENTS.md

Development guidelines for AI assistants (opencode, Claude, Cursor, etc.) working on this project.

## Pre-flight Checks

**ALWAYS run before making code changes:**

```bash
./run.sh --check
```

This verifies:
1. Core imports work correctly
2. UI imports work correctly
3. Configuration files exist

If pre-flight checks fail, fix the errors before proceeding.

## AI Session Handover Protocol

토큰 한계 등으로 AI 세션이 교체될 때, 프로젝트별 인수인계가 자동으로 동작합니다.
모든 데이터는 `~/.hits/data/`에 중앙 집중 저장되며, 프로젝트 경로로 격리됩니다.

### 세션 시작 시

```bash
# HTTP API (HITS 서버 실행 중일 때)
curl -s "http://localhost:8765/api/handover?project_path=$(pwd)" | python -m json.tool

# 또는 MCP 툴 (HITS MCP가 설정된 경우):
# hits_get_handover → 이전 세션의 작업 내용, 결정 사항, 미완료 항목 조회
```

### 세션 종료 시 (반드시 기록)

```bash
curl -X POST http://localhost:8765/api/work-log \
  -H "Content-Type: application/json" \
  -d '{
    "performed_by": "<AI_도구_이름>",
    "request_text": "<작업 요약>",
    "context": "<상세 내용, 결정 사항>",
    "source": "ai_session",
    "tags": ["<태그>"],
    "project_path": "<프로젝트_절대경로>",
    "result_data": {
      "files_modified": ["<수정한_파일>"],
      "commands_run": ["<실행한_명령>"]
    }
  }'
```

### performed_by 규칙

| AI 도구 | performed_by 값 |
|---------|----------------|
| OpenCode | `"opencode"` |
| Claude Code | `"claude"` |
| Cursor | `"cursor"` |
| GitHub Copilot | `"copilot"` |
| 사용자 직접 | `"manual"` 또는 사용자명 |

### project_path 규칙

- **항상 절대경로 사용**: `"/home/user/source/my-project"` (O), `"./my-project"` (X)
- **자동 감지**: CWD에서 `.git` 디렉토리가 있는 루트를 프로젝트 경로로 사용
- **프로젝트별 격리**: 서로 다른 `project_path`는 완전히 독립된 인수인계 컨텍스트를 가짐

### MCP 툴 사용 (권장)

HITS MCP 서버가 설정된 경우, HTTP API 대신 직접 툴 호출:

```
hits_record_work    → 작업 기록 (project_path 자동 감지)
hits_get_handover   → 인수인계 요약 조회
hits_search_works   → 이전 작업 검색
hits_list_projects  → 프로젝트 목록
hits_get_recent     → 최근 작업 조회
```

### 기록 시점

- 사용자와 긴 작업 세션 종료 시
- 주요 기능 구현 완료 시
- 버그 수정 완료 시
- 사용자가 명시적으로 종료 요청 시
- **토큰 한계 경고 수신 시** (즉시 기록!)

### 데이터 저장소

| 위치 | 설명 |
|------|------|
| `~/.hits/data/work_logs/` | 작업 기록 (JSON) |
| `~/.hits/data/trees/` | 지식 트리 |
| `~/.hits/data/workflows/` | 워크플로우 |
| `HITS_DATA_PATH` 환경변수 | 저장소 경로 오버라이드 |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | 서버 상태 확인 |
| POST | `/api/work-log` | 작업 기록 생성 |
| GET | `/api/work-logs` | 작업 기록 목록 (`project_path` 필터 지원) |
| GET | `/api/work-logs/search?q=키워드` | 작업 검색 (`project_path` 필터 지원) |
| GET | `/api/work-log/{id}` | 단건 조회 |
| PUT | `/api/work-log/{id}` | 수정 |
| DELETE | `/api/work-log/{id}` | 삭제 |
| GET | `/api/handover?project_path=...` | 프로젝트별 인수인계 요약 |
| GET | `/api/handover/projects` | 프로젝트 목록 |
| GET | `/api/handover/project-stats?project_path=...` | 프로젝트 통계 |
| POST | `/api/node` | 지식 노드 생성 |
| PUT | `/api/node/{id}` | 지식 노드 수정 |
| DELETE | `/api/node/{id}` | 지식 노드 삭제 |

## Development Workflow

1. Before making changes:
   ```bash
   ./run.sh --check
   ```

2. After code changes:
   ```bash
   # Clear cache
   find . -type d -name "__pycache__" -exec rm -rf {} +

   # Run checks again
   ./run.sh --check

   # Run tests if needed
   ./run.sh --test
   ```

3. If UI changes:
   - Test GUI manually: `./run.sh`
   - Verify Korean fonts render correctly
   - Check window positioning

## Project Structure

```
hits_core/                    # Apache 2.0 - No GUI dependencies
├── models/                # Node, Tree, Workflow, WorkLog
├── storage/               # Redis, File storage (~/.hits/data/)
├── ai/                    # Compression, SLM filter, LLM client
├── platform/              # Cross-platform utilities
├── service/               # TreeService, HandoverService
├── api/                   # FastAPI server + routes
│   └── routes/            # health, work_log, node, handover
├── collector/             # Git, Shell, AI session collectors
└── mcp/                   # MCP server (stdio transport)

hits_ui/                      # LGPL v3.0 - PySide6 GUI
├── panel/                 # PanelWindow, TimelineView, TreeView
├── widgets/               # ContextCard, NodeCard
├── dialogs/               # WorkLogDialog, HandoverDialog, NodeDialog
├── theme/                 # Material Dark theme
└── main.py               # Entry point

config/                       # Configuration files
├── settings.yaml          # Main config
└── schema.json            # JSON schema

tests/                       # Test files
├── core/                  # Core tests (no GUI)
└── ui/                    # UI tests
```

## Common Issues and Solutions

### Import Errors
```
ModuleNotFoundError: No module named 'hits_ui.xxx'
```

**Solution:**
1. Check file exists: `ls hits_ui/xxx/`
2. Check `__init__.py` has correct exports
3. Run: `./run.sh --check`

### Korean Font Issues
```
Text appears as boxes or garbled
```

**Solution:**
1. Fonts load automatically from Windows (WSL) or bundled fonts
2. Check: `./run.sh` and look for font loading messages
3. Settings dialog: click ⚙ → change font

### Window Position Issues
```
Window jumps around when toggling
```

**Solution:**
- Panel position is now remembered between toggles
- Position resets only on explicit request

## Testing

Run tests with:
```bash
./run.sh --test
```

Or for specific tests:
```bash
source venv/bin/activate
python -m pytest tests/core/test_ai.py -v
```

## Key Reminders

- **hits_core**: Must NEVER import PySide6 or any GUI library
- **hits_ui**: Can import from hits_core, but not vice versa
- **Cross-platform**: Test on Linux, Windows, and macOS if possible
- **Korean support**: Always verify fonts load correctly on WSL
- **Centralized storage**: All data goes to `~/.hits/data/`, not `./data/`
