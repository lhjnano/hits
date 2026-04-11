# AGENTS.md

Development guidelines for AI assistants (opencode, Claude, Cursor, etc.) working on this project.

## Pre-flight Checks

**ALWAYS run before making code changes:**

```bash
./run.sh --check
```

This verifies:
1. Core imports work correctly (models, storage, auth, API)
2. Configuration files exist
3. Frontend is built

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
| `~/.hits/.auth/` | 인증 데이터 (권한 600/700) |
| `HITS_DATA_PATH` 환경변수 | 저장소 경로 오버라이드 |

## API Endpoints

### 인증

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/status` | 인증 상태 (초기화 여부, 로그인 여부) |
| POST | `/api/auth/register` | 사용자 등록 (첫 사용자 = admin) |
| POST | `/api/auth/login` | 로그인 (HttpOnly 쿠키 설정) |
| POST | `/api/auth/logout` | 로그아웃 |
| POST | `/api/auth/refresh` | 액세스 토큰 갱신 |
| GET | `/api/auth/me` | 현재 사용자 정보 |
| PUT | `/api/auth/password` | 비밀번호 변경 |

### 작업 기록

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | 서버 상태 확인 |
| POST | `/api/work-log` | 작업 기록 생성 |
| GET | `/api/work-logs` | 작업 기록 목록 (`project_path` 필터 지원) |
| GET | `/api/work-logs/search?q=키워드` | 작업 검색 (`project_path` 필터 지원) |
| GET | `/api/work-log/{id}` | 단건 조회 |
| PUT | `/api/work-log/{id}` | 수정 |
| DELETE | `/api/work-log/{id}` | 삭제 |

### 인수인계

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/handover?project_path=...` | 프로젝트별 인수인계 요약 |
| GET | `/api/handover/projects` | 프로젝트 목록 |
| GET | `/api/handover/project-stats?project_path=...` | 프로젝트 통계 |

### 지식 카테고리

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/knowledge/categories` | 카테고리 목록 |
| POST | `/api/knowledge/category` | 카테고리 생성 |
| PUT | `/api/knowledge/category/{name}` | 카테고리 수정 |
| DELETE | `/api/knowledge/category/{name}` | 카테고리 삭제 |
| POST | `/api/knowledge/category/{name}/nodes` | 노드 추가 |
| PUT | `/api/knowledge/category/{name}/nodes/{idx}` | 노드 수정 |
| DELETE | `/api/knowledge/category/{name}/nodes/{idx}` | 노드 삭제 |

### 지식 트리 (노드 기반)

| Method | Path | Description |
|--------|------|-------------|
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

3. If frontend changes:
   ```bash
   cd hits_web && npm run build
   ```

4. Development mode (hot reload):
   ```bash
   ./run.sh --dev
   ```

## Project Structure

```
hits_core/                    # Apache 2.0 - Backend
├── auth/                   # Authentication & security
│   ├── manager.py          # Argon2id + JWT + user management
│   ├── middleware.py        # CSP, security headers
│   └── dependencies.py     # FastAPI auth dependencies
├── models/                 # Node, Tree, Workflow, WorkLog
├── storage/                # Redis, File storage (~/.hits/data/)
├── ai/                     # Compression, SLM filter, LLM client
├── platform/               # Cross-platform utilities
├── service/                # TreeService, HandoverService, KnowledgeService
├── api/                    # FastAPI server + routes
│   └── routes/             # health, work_log, node, handover, auth, knowledge
├── collector/              # Git, Shell, AI session collectors
├── mcp/                    # MCP server (stdio transport)
└── main.py                 # Web server entry point

hits_web/                      # Apache 2.0 - Svelte 5 Web UI
├── src/
│   ├── lib/                # API client, stores, CSS
│   ├── components/         # Svelte components
│   │   ├── Login.svelte    # Authentication page
│   │   ├── MainLayout.svelte  # App shell with sidebar + header
│   │   ├── KnowledgeTree.svelte  # Knowledge category CRUD
│   │   ├── Timeline.svelte    # Work log timeline
│   │   └── HandoverPanel.svelte  # Handover summary view
│   ├── App.svelte          # Root component
│   └── main.ts             # Entry point
├── dist/                   # Built static files (served by FastAPI)
├── package.json
├── vite.config.ts
└── tsconfig.json

config/                       # Configuration files
├── settings.yaml          # Main config
└── schema.json            # JSON schema

tests/                       # Test files
└── core/                  # Core tests
```

## Security Architecture

### Authentication Flow

```
Browser → POST /api/auth/login → Argon2id verify → JWT HttpOnly cookies
         ← Set-Cookie: access_token (15min, /)
         ← Set-Cookie: refresh_token (7d, /api/auth/refresh)
```

### Protected Endpoints

All `/api/*` endpoints except `/api/health`, `/api/auth/*` require authentication via:
- `access_token` HttpOnly cookie, OR
- `Authorization: Bearer <token>` header

### Data Protection

- Password files: `chmod 600` (owner read/write only)
- Auth directory: `chmod 700` (owner access only)
- Pepper/JWT secret: auto-generated, stored in `~/.hits/`

## Common Issues and Solutions

### Import Errors
```
ModuleNotFoundError: No module named 'hits_core.auth'
```

**Solution:**
1. Reinstall dependencies: `./run.sh --setup`
2. Run: `./run.sh --check`

### Frontend Not Loading
```
HITS Web UI not built yet
```

**Solution:**
```bash
cd hits_web && npm install && npm run build
```

### Auth System Not Initialized

First run requires creating an admin account through the web UI or API:
```bash
curl -X POST http://localhost:8765/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-secure-password"}'
```

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

- **hits_core**: No GUI dependencies. FastAPI serves both API and static frontend.
- **hits_web**: Svelte 5 frontend, built to `dist/` and served by FastAPI.
- **Security**: All sensitive endpoints require auth. Use `Depends(require_auth)`.
- **Centralized storage**: All data goes to `~/.hits/data/`, not `./data/`
- **Argon2id**: Preferred password hasher. Falls back to HMAC-SHA256 if not installed.
- **JWT**: Uses `python-jose` if available, falls back to HMAC-based tokens.
