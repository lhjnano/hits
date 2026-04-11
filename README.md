# HITS - Hybrid Intel Trace System

> AI를 가장 적게 쓰면서, 전임자의 뇌를 가장 완벽하게 복제하는 시스템

## 개요

HITS는 기업의 핵심 지식과 의사결정 맥락을 보존하기 위한 하이브리드 지식 관리 시스템입니다. AI 도구 간(Claude, OpenCode, Cursor 등) 세션 전환 시 프로젝트별 인수인계를 자동화합니다.

### 핵심 가치

- **토큰 최적화**: AI 비용 절감을 위한 시멘틱 압축과 온디맨드 분석
- **맥락 보존**: Why-How-What 계층 구조로 의사결정 과정 저장
- **실패 경험**: Negative Path로 실패한 접근법도 함께 기록
- **크로스플랫폼**: Linux, Windows, macOS, WSL 지원
- **AI 세션 인수인계**: 토큰 한계로 AI 교체 시 프로젝트별 컨텍스트 자동 전달
- **중앙 집중 저장**: `~/.hits/data/`에 모든 AI 도구의 작업 기록이 통합 저장

## 지원 플랫폼

| 플랫폼 | 상태 | 비고 |
|--------|------|------|
| Linux | ✅ 완전 지원 | gnome-terminal, konsole, alacritty 등 자동 감지 |
| Windows 10/11 | ✅ 완전 지원 | Windows Terminal, cmd 지원 |
| macOS | ✅ 완전 지원 | Terminal.app 지원 |
| WSL (1/2) | ✅ 완전 지원 | Windows Terminal 자동 감지 |

## 설치

### 요구사항

- Python 3.10 이상
- Redis (선택사항, 없으면 파일 저장소 사용)

### 빠른 시작

#### Linux / macOS / WSL

```bash
cd hits
./run.sh
```

#### Windows

```cmd
cd hits
run.bat
```

또는 수동 설치:

```bash
python3 -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m hits_ui.main
```

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

### 프로젝트별 격리

서로 다른 프로젝트의 작업 기록은 `project_path`로 완전히 격리됩니다:

```
~/.hits/data/
├── work_logs/
│   ├── index.json
│   └── *.json             ← project_path 필드로 구분
├── trees/
└── workflows/
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

### API 엔드포인트

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/work-log` | 작업 기록 |
| GET | `/api/work-logs` | 작업 목록 (`project_path` 필터) |
| GET | `/api/work-logs/search?q=...` | 작업 검색 |
| GET | `/api/handover?project_path=...` | 인수인계 요약 |
| GET | `/api/handover/projects` | 프로젝트 목록 |
| GET | `/api/handover/project-stats?project_path=...` | 프로젝트 통계 |

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
│                     hits_ui (LGPL v3)                    │
│              PySide6 GUI - 동적 링크                      │
│  ┌──────────┬──────────┬──────────────────────────┐      │
│  │ Panel    │ Timeline │ HandoverDialog           │      │
│  │ TreeView │ (프로젝트 │ (인수인계 요약 뷰)         │      │
│  │          │  필터)   │                          │      │
│  └──────────┴──────────┴──────────────────────────┘      │
├──────────────────────────────────────────────────────────┤
│                   hits_core (Apache 2.0)                  │
│         순수 Python - 상업적 사용 가능                      │
│  ┌──────────┬──────────┬──────────┬──────────┐           │
│  │  Models  │ Storage  │    AI    │ Platform │           │
│  │  Tree    │ Redis    │ Compress │ Actions  │           │
│  │  Node    │ File     │ SLM/LLM  │ OS Utils │           │
│  │  WorkLog │(~/.hits) │ Filter   │          │           │
│  └──────────┴──────────┴──────────┴──────────┘           │
│  ┌──────────┬──────────┬──────────┐                      │
│  │  API     │ Collector│   MCP    │                      │
│  │ FastAPI  │ Git/Shell│ Server   │                      │
│  │ Routes   │ AI Sess. │ 5 Tools  │                      │
│  └──────────┴──────────┴──────────┘                      │
│  ┌──────────────────────────────┐                        │
│  │       Service Layer          │                        │
│  │  TreeService  HandoverService│                        │
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

### Negative Path

실패한 접근법과 그 원인을 기록합니다:

```yaml
- id: how-rollback
  layer: how
  title: "긴급 롤백 절차"
  node_type: "negative_path"  # 실패 경로 표시
  description: |
    ⚠ 주의: 이 방법은 실패할 수 있음
    ...
```

## 토큰 최적화 전략

### 1. SLM 전처리

```python
from hits_core.ai.slm_filter import SLMFilter

filter = SLMFilter()
important, noise = filter.filter_batch(contents)
# CRITICAL/IMPORTANT만 LLM으로 전송, NOISE는 필터링
```

### 2. 시멘틱 압축

```python
from hits_core.ai.compressor import SemanticCompressor

compressor = SemanticCompressor()
compressed = compressor.compress("따라서 이 작업은 필수입니다")
# 결과: "→ 이 작업 →!"
```

### 3. 온디맨드 분석

- 기본: 메타데이터만 표시 (토큰 0)
- 줌인: 상세 데이터 로드
- AI 분석: 버튼 클릭 시에만 LLM 호출

## 저장소

### 파일 기반 (기본)

```python
from hits_core.storage.file_store import FileStorage

# 기본: ~/.hits/data/
storage = FileStorage()

# 명시적 경로
storage = FileStorage(base_path="/custom/path")

# 환경변수
# HITS_DATA_PATH=/custom/path
```

### Redis (선택)

```python
from hits_core.storage.redis_store import RedisStorage

storage = RedisStorage(host="localhost", port=6379)
```

## 크로스플랫폼 실행

```python
from hits_core.platform.actions import PlatformAction, get_platform_info

# URL 열기
PlatformAction.execute("url", "https://example.com")

# 셸 명령 실행
PlatformAction.execute("shell", "bash ~/scripts/deploy.sh")

# 플랫폼 정보 확인
info = get_platform_info()
# {'system': 'linux', 'is_wsl': True, 'terminal': 'gnome-terminal'}
```

| OS | 터미널 |
|----|--------|
| Windows | Windows Terminal / cmd |
| macOS | Terminal.app |
| Linux | gnome-terminal, konsole, alacritty, xterm 등 |
| WSL | Windows Terminal (wt.exe) |

## 개발

### 테스트

```bash
# 전체 테스트
pytest tests/

# 커버리지 포함
pytest --cov=hits_core --cov=hits_ui tests/

# 특정 테스트만
pytest tests/core/test_ai.py -v
```

### 가상환경

```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

## 라이선스

| 패키지 | 라이선스 | 상업적 사용 |
|--------|---------|-------------|
| `hits_core` | Apache 2.0 | ✅ 자유로움 |
| `hits_ui` | LGPL v3 | ✅ 동적 링크 조건 준수 |

## 로드맵

- [x] 프로젝트별 AI 세션 인수인계
- [x] MCP 서버 인터페이스
- [x] 중앙 집중 저장소 (~/.hits/data/)
- [x] 인수인계 요약 UI (HandoverDialog)
- [x] 프로젝트 필터링 타임라인
- [ ] Redis WorkLog CRUD 구현
- [ ] Web UI 버전
- [ ] CLI 모듈
- [ ] 다국어 지원
- [ ] AI 모델 플러그인 시스템

## 문제 해결

### WSL에서 GUI가 보이지 않음

```bash
echo $DISPLAY
# 출력이 있으면 WSLg 활성화됨
```

WSLg가 없으면 Windows에서 X Server (VcXsrv, X410 등)를 설치하세요.

### Redis 연결 실패

Redis 없이도 HITS는 정상 작동합니다. 파일 기반 저장소를 자동으로 사용합니다.

### 데이터가 어디에 저장되나요?

```
~/.hits/data/              ← 모든 데이터의 기본 위치
├── work_logs/             ← AI 세션 작업 기록
├── trees/                 ← 지식 트리
└── workflows/             ← 워크플로우

HITS_DATA_PATH 환경변수로 경로 변경 가능
```
