# HITS - Hybrid Intel Trace System

> AI를 가장 적게 쓰면서, 전임자의 뇌를 가장 완벽하게 복제하는 시스템

## 개요

HITS는 기업의 핵심 지식과 의사결정 맥락을 보존하기 위한 하이브리드 지식 관리 시스템입니다. AI 도구 간(Claude, OpenCode, Cursor 등) 세션 전환 시 프로젝트별 인수인계를 자동화합니다.

### 핵심 가치

- **토큰 최적화**: AI 비용 절감을 위한 시멘틱 압축과 온디맨드 분석
- **맥락 보존**: Why-How-What 계층 구조로 의사결정 과정 저장
- **실패 경험**: Negative Path로 실패한 접근법도 함께 기록
- **보안 강화**: Argon2id 해싱, JWT HttpOnly 쿠키, CSP, Rate Limiting
- **AI 세션 인수인계**: 토큰 한계로 AI 교체 시 프로젝트별 컨텍스트 자동 전달
- **중앙 집중 저장**: `~/.hits/data/`에 모든 AI 도구의 작업 기록이 통합 저장
- **프로젝트별 격리**: 프로젝트 경로 기반으로 완전히 독립된 컨텍스트 관리

## 기술 스택

| 영역 | 기술 |
|------|------|
| **백엔드** | Python 3.10+, FastAPI, Pydantic v2 |
| **프론트엔드** | Svelte 5, Vite, TypeScript |
| **인증** | Argon2id (비밀번호), JWT HS256 (HttpOnly 쿠키) |
| **저장소** | 파일 기반 (`~/.hits/data/`), Redis (선택) |
| **보안** | CSP, CORS, Rate Limiting, Secure Headers |

## 설치

### 요구사항

- Python 3.10 이상
- Node.js 18+ (프론트엔드 빌드용)
- Redis (선택사항, 없으면 파일 저장소 사용)

### 빠른 시작

```bash
cd hits
./run.sh          # 자동 설치 + 서버 시작
```

#### 개발 모드

```bash
./run.sh --dev    # Vite HMR + FastAPI 백엔드
```

#### 수동 설치

```bash
# Python 환경
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 프론트엔드 빌드
cd hits_web
npm install
npm run build
cd ..

# 서버 실행
python -m hits_core.main --port 8765
```

## 보안

### 인증 시스템

| 기능 | 구현 |
|------|------|
| **비밀번호 해싱** | Argon2id (memory=64MB, iterations=3, parallelism=1) |
| **비밀번호 최소 길이** | 8자 |
| **JWT 토큰** | HttpOnly + Secure + SameSite=Lax 쿠키 |
| **액세스 토큰** | 15분 만료 |
| **리프레시 토큰** | 7일 만료, `/api/auth/refresh` 경로에서만 전송 |
| **첫 사용자** | 자동으로 admin 역할 부여 |
| **이후 사용자** | admin만 생성 가능 |

### 보안 헤더

```
Content-Security-Policy: default-src 'self'; script-src 'self'; ...
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

### Rate Limiting

- 로그인 엔드포인트: 10회/분 (IP 기준)
- 429 Too Many Requests 응답으로 제한

### 데이터 보호

| 항목 | 권한 | 설명 |
|------|------|------|
| `~/.hits/.auth/users.json` | 600 | 사용자 데이터 (소유자만) |
| `~/.hits/.pepper` | 600 | HMAC 페퍼 (소유자만) |
| `~/.hits/.jwt_secret` | 600 | JWT 서명 키 (소유자만) |
| `~/.hits/.auth/` | 700 | 인증 디렉토리 (소유자만) |

## 웹 UI

### 화면 구성

```
┌─────────────┬───────────────────────────────────┐
│  사이드바    │  헤더 (탭 + 사용자 메뉴)            │
│             ├───────────────────────────────────┤
│  📂 프로젝트 │                                   │
│  ────────── │  메인 컨텐츠 영역                   │
│  /project-a │                                   │
│  /project-b │  📋 지식 트리 | 📝 타임라인 | 🔄 인수인계 │
│  /project-c │                                   │
│             │                                   │
└─────────────┴───────────────────────────────────┘
```

### 주요 기능

- **지식 트리**: 카테고리별 Why-How-What 노드 관리 (CRUD)
- **타임라인**: 프로젝트별 작업 기록, 날짜별 그룹핑, 검색
- **인수인계**: 프로젝트 선택 시 자동 생성된 인수인계 요약
- **프로젝트 전환**: 사이드바에서 프로젝트 선택으로 즉시 전환
- **사용자 관리**: 비밀번호 변경, 로그아웃

## AI 세션 인수인계

### 작동 방식

```
[OpenCode 세션]                    [Claude 세션]
      │                                  │
  작업 수행                           세션 시작
      │                                  │
  작업 기록 ──────────────────────→ 인수인계 조회
  POST /api/work-log               GET /api/handover
  project_path: /my-project        project_path: /my-project
      │                                  │
      └──→ ~/.hits/data/ ←──┘            │
           (중앙 집중)              이전 컨텍스트 파악
                                         │
                                    작업 이어서 수행
```

### MCP 설정

OpenCode 또는 Claude의 MCP 설정에 추가:

```json
{
  "hits": {
    "type": "local",
    "command": ["python", "-m", "hits_core.mcp.server"],
    "cwd": "/path/to/hits"
  }
}
```

MCP 툴:
- `hits_record_work`: 작업 기록
- `hits_get_handover`: 인수인계 요약
- `hits_search_works`: 작업 검색
- `hits_list_projects`: 프로젝트 목록
- `hits_get_recent`: 최근 작업

## API 엔드포인트

### 인증

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/status` | 인증 상태 확인 |
| POST | `/api/auth/register` | 사용자 등록 |
| POST | `/api/auth/login` | 로그인 (HttpOnly 쿠키 설정) |
| POST | `/api/auth/logout` | 로그아웃 |
| POST | `/api/auth/refresh` | 액세스 토큰 갱신 |
| GET | `/api/auth/me` | 현재 사용자 정보 |
| PUT | `/api/auth/password` | 비밀번호 변경 |

### 작업 기록

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/work-log` | 작업 기록 생성 |
| GET | `/api/work-logs` | 작업 목록 (`project_path` 필터) |
| GET | `/api/work-logs/search?q=...` | 작업 검색 |
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

### performed_by 규칙

| AI 도구 | 값 |
|---------|-----|
| OpenCode | `opencode` |
| Claude Code | `claude` |
| Cursor | `cursor` |
| 사용자 직접 | `manual` |

## 아키텍처

```
┌──────────────────────────────────────────────────────────┐
│                   hits_web (Svelte 5 + Vite)              │
│              Material Dark 테마 · TypeScript               │
│  ┌──────────┬──────────┬──────────────────────────┐       │
│  │ Sidebar  │ Knowledge│ HandoverPanel            │       │
│  │ Projects │ Tree     │ 인수인계 요약 뷰          │       │
│  │ Filter   │ Timeline │                          │       │
│  └──────────┴──────────┴──────────────────────────┘       │
│         ↕ API Client (fetch + HttpOnly cookies)           │
├──────────────────────────────────────────────────────────┤
│                   hits_core (Apache 2.0)                  │
│  ┌──────────┬──────────┬──────────┬──────────┐           │
│  │  Models  │ Storage  │    AI    │ Auth     │           │
│  │  Tree    │ Redis    │ Compress │ Argon2id │           │
│  │  Node    │ File     │ SLM/LLM  │ JWT      │           │
│  │  WorkLog │(~/.hits) │ Filter   │ Middleware│           │
│  └──────────┴──────────┴──────────┴──────────┘           │
│  ┌──────────┬──────────┬──────────┐                      │
│  │  API     │ Collector│   MCP    │                      │
│  │ FastAPI  │ Git/Shell│ Server   │                      │
│  │ + Static │ AI Sess. │ 5 Tools  │                      │
│  │  Serve   │          │          │                      │
│  └──────────┴──────────┴──────────┘                      │
│  ┌──────────────────────────────┐                        │
│  │       Service Layer          │                        │
│  │  TreeService  HandoverService│                        │
│  │  KnowledgeService            │                        │
│  └──────────────────────────────┘                        │
└──────────────────────────────────────────────────────────┘
```

## 지식 트리 구조

### Why-How-What 계층

```
├── WHY (의도/목적)
│   ├── "왜 이 시스템을 만들었나?"
│   └── "비즈니스 목표가 무엇인가?"
│
├── HOW (논리/방법)
│   ├── "어떻게 구현했나?"
│   └── "어떤 의사결정을 내렸나?"
│
└── WHAT (실행/작업)
    ├── "구체적으로 무엇을 하나?"
    └── "실행 가능한 액션"
```

## 개발

### 개발 모드

```bash
./run.sh --dev    # Vite HMR + FastAPI
```

### 테스트

```bash
./run.sh --test   # pytest 실행
```

### 프론트엔드 개발

```bash
cd hits_web
npm install        # 의존성 설치
npm run dev        # Vite 개발 서버 (http://localhost:5173)
npm run build      # 프로덕션 빌드
```

## 라이선스

| 패키지 | 라이선스 | 상업적 사용 |
|--------|---------|-------------|
| `hits_core` | Apache 2.0 | ✅ 자유로움 |
| `hits_web` | Apache 2.0 | ✅ 자유로움 |

## 문제 해결

### Node.js가 없습니다

```bash
# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

### Redis 연결 실패

Redis 없이도 HITS는 정상 작동합니다. 파일 기반 저장소를 자동으로 사용합니다.

### 데이터가 어디에 저장되나요?

```
~/.hits/
├── data/                ← 모든 데이터의 기본 위치
│   ├── work_logs/       ← AI 세션 작업 기록
│   ├── trees/           ← 지식 트리
│   └── workflows/       ← 워크플로우
├── .auth/               ← 인증 데이터
│   └── users.json       ← 사용자 정보 (권한 600)
├── .pepper              ← HMAC 페퍼 (권한 600)
└── .jwt_secret          ← JWT 서명 키 (권한 600)

HITS_DATA_PATH 환경변수로 경로 변경 가능
```
