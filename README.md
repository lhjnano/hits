# hits

> Replicate your predecessor's brain as perfectly as possible, using the least amount of AI.

A secure web-based knowledge management system that preserves organizational context across AI tool sessions. When your Claude session hits the token limit and you switch to a new one — HITS ensures nothing is lost.

## What Problem Does This Solve?

You're working on a project with Claude Code. After a long session, you hit the token limit. A new session starts — but it has **no idea** what you did, what decisions were made, or what was left unfinished.

**HITS fixes this:**

1. **Record work** during each AI session (manually or via MCP tools)
2. **Query handover** when a new session starts — it gets the full context
3. **Knowledge trees** preserve the WHY/HOW/WHAT of every project
4. **All AI tools share the same data** — Claude, OpenCode, Cursor, it doesn't matter

```
[OpenCode session ends]              [Claude session starts]
        │                                    │
   Record work:                          Query handover:
   "Added JWT auth,                      → Previous: Added JWT auth
    chose Argon2id over                     → Decisions: Argon2id > bcrypt
    bcrypt, still need to                    → Pending: rate limiting
    add rate limiting"                       → Files: auth/manager.py, ...
```

## Quick Start

### One Command — That's It

```bash
npx hits
```

That single command will:

1. **Detect Python 3.10+** on your system
2. **Create a virtual environment** automatically
3. **Install Python dependencies** (FastAPI, Argon2id, etc.)
4. **Start the Python backend** (FastAPI on port 8765)
5. **Start the web server** (Express on port 8765)
6. Open **http://127.0.0.1:8765** in your browser

### First Time Setup

On first visit, you'll create an admin account:

```
┌──────────────────────────────────────┐
│         🌳 HITS                      │
│    Hybrid Intel Trace System         │
│                                      │
│  ┌────────────────────────────────┐  │
│  │  Username: [____________]      │  │
│  │  Password: [____________]      │  │
│  │                                │  │
│  │  [ Create Account ]            │  │
│  │                                │  │
│  │  First account = admin role    │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

### Custom Port

```bash
npx hits --port 9000
# or
HITS_PORT=9000 npx hits
```

## Requirements

| Requirement | Version | Why |
|-------------|---------|-----|
| **Node.js** | ≥ 18 | Runs the web server and manages the Python process |
| **Python** | ≥ 3.10 | Runs the FastAPI backend (auto-installed into venv) |

That's it. No database required — HITS uses file-based storage at `~/.hits/data/`.

## What You Get

### Web UI

```
┌─────────────┬───────────────────────────────────┐
│  Sidebar    │  Header (tabs + user menu 🌐 lang) │
│             ├───────────────────────────────────┤
│  📂 Projects│                                   │
│  ────────── │  Main content area                 │
│  /project-a │                                   │
│  /project-b │  📋 Knowledge | 📝 Timeline | 🔄 Handover │
│  /project-c │                                   │
│             │                                   │
└─────────────┴───────────────────────────────────┘
```

**Knowledge Tree** — Organize project knowledge as Why-How-What nodes:

```
📁 Authentication
  ├── WHY  "Need secure user auth for web UI"
  ├── HOW  "Argon2id hashing + JWT HttpOnly cookies"
  └── WHAT "POST /api/auth/login → Set-Cookie"
      └── ❌ Negative Path: "Tried bcrypt first — too fast, GPU-vulnerable"
```

**Timeline** — Chronological work log, grouped by date, filterable by project. Click any entry to expand full details (context, files modified, commands run).

**Handover** — Auto-generated summary of a project's context, ready to paste into a new AI session

**i18n** — Korean/English toggle (🌐 button in header), instant switch with auto-reload

### MCP Tools for AI Assistants

HITS includes an MCP server so your AI can read and write handover data directly. No need to clone the repo — it works right out of the npm package.

#### Register with Claude Code

```bash
claude mcp add hits -- npx -y -p @purpleraven/hits hits-mcp
```

Or add to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "hits": {
      "command": "npx",
      "args": ["-y", "-p", "@purpleraven/hits", "hits-mcp"]
    }
  }
}
```

#### Register with OpenCode (`~/.config/opencode/mcp.json`)

```json
{
  "mcpServers": {
    "hits": {
      "command": "npx",
      "args": ["-y", "-p", "@purpleraven/hits", "hits-mcp"]
    }
  }
}
```

> **Important:** You must use `npx -p @purpleraven/hits hits-mcp` (specify the package), not just `npx hits-mcp`. The `hits-mcp` binary is inside the `@purpleraven/hits` package.
>
> **How it works:** `npx` downloads the package, auto-detects Python, creates a venv, installs dependencies, and spawns the MCP server over stdio — all automatically on first run.

#### 8 MCP Tools

| Tool | What It Does |
|------|-------------|
| `hits_record_work` | Record a work entry (auto-detects project path from CWD) |
| `hits_get_handover` | Get handover summary for the current project |
| `hits_search_works` | Search past work by keyword |
| `hits_list_projects` | List all projects with recorded work |
| `hits_get_recent` | Get the most recent work entries |
| `hits_signal_send` | Send a handover signal to another AI tool (Claude↔OpenCode) |
| `hits_signal_check` | Check for pending signals addressed to you |
| `hits_signal_consume` | Acknowledge and archive a signal |

#### Example AI Workflow

```
User: "Continue working on the auth system"

AI (auto-calls hits_get_handover):
  → Previous session added Argon2id password hashing
  → Decisions: Argon2id (not bcrypt), JWT HS256, HttpOnly cookies
  → Pending: Rate limiting, password change endpoint

AI: "I see the auth system uses Argon2id + JWT. Let me add rate limiting..."

(later)

AI (auto-calls hits_record_work):
  → Recorded: "Added rate limiting (10 req/min on login endpoint)"
```

### REST API

All features are also accessible via HTTP API:

```bash
# Health check
curl http://localhost:8765/api/health

# Record work (source is required)
curl -X POST http://localhost:8765/api/work-log \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "performed_by": "claude",
    "source": "ai_session",
    "request_text": "Added rate limiting to login endpoint",
    "context": "10 req/min per IP, 429 response on limit",
    "project_path": "/home/user/my-project",
    "tags": ["security", "api"]
  }'

# Get handover summary
curl "http://localhost:8765/api/handover?project_path=/home/user/my-project" \
  -b cookies.txt

# Search past work
curl "http://localhost:8765/api/work-logs/search?q=auth" \
  -b cookies.txt
```

## Security

HITS is built with security as a first-class concern:

| Feature | Implementation |
|---------|---------------|
| **Password Hashing** | Argon2id (64MB memory, 3 iterations, parallelism=1) |
| **JWT Tokens** | HttpOnly + Secure + SameSite=Lax cookies |
| **Access Token** | 15-minute expiry |
| **Refresh Token** | 7-day expiry, restricted to `/api/auth/refresh` path |
| **Brute Force Protection** | 10 login attempts/minute per IP |
| **Security Headers** | CSP, X-Frame-Options: DENY, HSTS preload, nosniff |
| **Data Protection** | Auth files stored with `chmod 600` (owner-only) |
| **First User Policy** | First registered user becomes admin; subsequent users need admin approval |

## How It Works Under the Hood

```
npx hits
  │
  ├── 1. findPython()       → Detect Python 3.10+ on system
  ├── 2. setupPython()      → Create venv, install deps
  ├── 3. startBackend()     → Spawn FastAPI process (port 8765)
  └── 4. startExpress()     → Serve frontend + proxy /api → FastAPI

  Browser                    Express (8765)           FastAPI (8765 internal)
     │                           │                         │
     ├── GET /             ───→  static (Svelte SPA)       │
     ├── GET /some/route   ───→  SPA fallback              │
     └── GET /api/*        ───→  proxy  ──────────────→   FastAPI routes
         POST /api/*       ───→  proxy  ──────────────→   FastAPI routes
```

All data is stored centrally:

```
~/.hits/
├── data/                ← All project data
│   ├── work_logs/       ← AI session work logs (JSON)
│   ├── trees/           ← Knowledge trees
│   └── workflows/       ← Workflows
├── backups/             ← CLI backups (tar.gz)
├── .auth/               ← User accounts (chmod 700)
│   └── users.json       ← User data (chmod 600)
├── .pepper              ← HMAC pepper (chmod 600)
└── .jwt_secret          ← JWT signing key (chmod 600)

Override with HITS_DATA_PATH environment variable
```

## CLI Options

### Node.js (npx)

```
npx hits [options]

Options:
  -p, --port <port>   Server port (default: 8765)
  -d, --dev           Development mode (verbose logging)
  -s, --setup         Install dependencies only, don't start
  -h, --help          Show help

Environment:
  HITS_PORT           Server port override
  HITS_PYTHON         Path to python executable (default: auto-detect)
  HITS_DATA_PATH      Data storage path (default: ~/.hits/data)
```

### Python CLI (hits)

```bash
# Start web server
hits                  # or: hits server
hits server --port 9000 --dev

# Backup & restore
hits backup           # Backup all data to ~/.hits/backups/
hits backup --list    # List available backups
hits restore          # Restore latest backup (with auto-backup of current state)
hits restore -n 1     # Restore specific backup by number

# Status
hits status           # Show accounts, work logs, trees, backups
```

Installed via `pip install -e .` or automatically with `npx hits`.

## API Reference

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/status` | Check if auth is initialized, current login status |
| POST | `/api/auth/register` | Register user (first user = admin) |
| POST | `/api/auth/login` | Login — sets HttpOnly cookies |
| POST | `/api/auth/logout` | Logout — clears cookies |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/me` | Get current user info |
| PUT | `/api/auth/password` | Change password |

### Work Logs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/work-log` | Create work log |
| GET | `/api/work-logs` | List logs (filter by `project_path`) |
| GET | `/api/work-logs/search?q=...` | Search logs by keyword |
| GET | `/api/work-log/{id}` | Get single entry |
| PUT | `/api/work-log/{id}` | Update entry |
| DELETE | `/api/work-log/{id}` | Delete entry |

### Handover

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/handover?project_path=...` | Get project handover summary |
| GET | `/api/handover/projects` | List all projects |
| GET | `/api/handover/project-stats?project_path=...` | Get project statistics |

### Knowledge

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/knowledge/categories` | List categories |
| POST | `/api/knowledge/category` | Create category |
| PUT | `/api/knowledge/category/{name}` | Update category |
| DELETE | `/api/knowledge/category/{name}` | Delete category |
| POST | `/api/knowledge/category/{name}/nodes` | Add node to category |
| PUT | `/api/knowledge/category/{name}/nodes/{idx}` | Update node |
| DELETE | `/api/knowledge/category/{name}/nodes/{idx}` | Delete node |

### Signals (Cross-Tool Handover)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/signals/send` | Send a handover signal to another AI tool |
| GET | `/api/signals/check` | Check pending signals (filter by recipient, project) |
| POST | `/api/signals/consume` | Consume (acknowledge) a signal |
| GET | `/api/signals/pending` | List all pending signals |
| DELETE | `/api/signals/{signal_id}` | Delete a signal |

```bash
# Send signal (Claude → OpenCode)
curl -X POST http://localhost:8765/api/signals/send \
  -H "Content-Type: application/json" \
  -d '{"sender":"claude","recipient":"opencode","summary":"JWT auth done","pending_items":["rate limiting"]}'

# Check pending signals
curl "http://localhost:8765/api/signals/check?recipient=opencode"

# Consume signal
curl -X POST http://localhost:8765/api/signals/consume \
  -H "Content-Type: application/json" \
  -d '{"signal_id":"sig_abc12345","consumed_by":"opencode"}'
```

## Cross-Tool Handover Signals

HITS provides a file-based signal system for real-time handover between AI tools (Claude ↔ OpenCode ↔ Cursor). No running server required — signals are just JSON files in `~/.hits/data/signals/`.

### How It Works

```
┌─────────────────┐     ~/.hits/data/signals/pending/     ┌─────────────────┐
│   Claude Code   │  ──── claude_to_opencode.json ────►  │    OpenCode     │
│                 │                                       │                 │
│  hits_signal_   │                                       │  hook detects   │
│  send()         │                                       │  signal file    │
│                 │                                       │  hits_signal_   │
│                 │  ◄──── opencode_to_claude.json ─────  │  check()        │
└─────────────────┘                                       └─────────────────┘
```

### MCP Signal Tools

```python
# 1. 세션 종료 시 시그널 전송 (Claude → OpenCode)
hits_signal_send(
    sender="claude",
    recipient="opencode",        # or "any" for broadcast
    summary="JWT auth 구현 완료, rate limiting 남음",
    pending_items=["rate limiting 추가", "CORS 설정"],
    priority="high"              # normal | high | urgent
)

# 2. 세션 시작 시 시그널 확인
hits_signal_check(recipient="opencode")
# → 🟡 [04/14 14:30] claude → opencode
#    요약: JWT auth 구현 완료, rate limiting 남음
#    미완료: rate limiting 추가, CORS 설정

# 3. 시그널 소진 (확인 완료)
hits_signal_consume(signal_id="sig_abc12345", consumed_by="opencode")
```

### Hook Setup (Automatic Detection)

Instead of manually calling `hits_signal_check`, configure hooks so signals are **automatically injected** when a session starts.

#### Claude Code — SessionStart Hook

`~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "bash <(npx -y -p @purpleraven/hits cat hooks/claude_signal_watcher.sh)"
      }
    ]
  }
}
```

Or install the hook script locally:

```bash
mkdir -p ~/.claude/hooks
npx -y -p @purpleraven/hits cat hooks/claude_signal_watcher.sh > ~/.claude/hooks/hits_signal_watcher.sh
chmod +x ~/.claude/hooks/hits_signal_watcher.sh
```

Then reference it:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "~/.claude/hooks/hits_signal_watcher.sh"
      }
    ]
  }
}
```

When Claude starts a session, it will see:

```
📬 HITS 인수인계 시그널 감지!
  보낸이: opencode
  유형: session_end
  우선순위: high
  요약: LVM DR 스크립트 디버깅 완료
  미완료 항목:
    - 원격 백업 테스트
    - CronJob 매니페스트 작성
  시그널 ID: sig_fb5bd38c

👉 hits_get_handover()로 전체 컨텍스트를 확인하고,
👉 hits_signal_consume(signal_id="sig_fb5bd38c", consumed_by="claude")로 시그널을 소진하세요.
```

#### OpenCode — SessionStart Hook

`~/.config/opencode/opencode.json` or project `.opencode/hooks/`:

```bash
mkdir -p ~/.opencode/hooks
npx -y -p @purpleraven/hits cat hooks/opencode_signal_watcher.sh > ~/.opencode/hooks/hits_signal_watcher.sh
chmod +x ~/.opencode/hooks/hits_signal_watcher.sh
```

Configure as a startup hook in your OpenCode settings.

### Signal Directory Structure

```
~/.hits/data/signals/
├── pending/                              ← Active signals
│   └── claude_to_opencode_20260414_143022_sig_fb5bd38c.json
└── consumed/                             ← Archived (auto-cleaned after 72h)
    └── opencode_to_claude_20260414_130000_sig_a1b2c3d4.json
```

### Full Handover Flow

```
1. Claude 세션 종료:
   → hits_record_work()       # 작업 기록
   → hits_signal_send()       # OpenCode에 시그널 전송

2. OpenCode 세션 시작:
   → hook가 자동 감지 (stderr 주입)
   → hits_get_handover()      # 전체 컨텍스트 조회
   → hits_signal_consume()    # 시그널 소진

3. OpenCode 세션 종료:
   → hits_record_work()
   → hits_signal_send(sender="opencode", recipient="claude")
```

## Troubleshooting

### "Python 3.10+ not found"

Install Python 3.10 or later:
```bash
# Ubuntu/Debian
sudo apt install python3.12

# macOS
brew install python@3.12

# Or set manually:
export HITS_PYTHON=/usr/bin/python3.12
```

### "Frontend not built"

This shouldn't happen with the npm package (frontend is pre-built). If it does:
```bash
npx hits --setup
```

### "ModuleNotFoundError: No module named 'hits_core'"

Python dependencies failed to install. Try:
```bash
npx hits --setup
```

### Redis Connection Failed

Not a problem — HITS automatically uses file-based storage. Redis is optional.

## Development

If you're working on HITS itself:

```bash
git clone https://github.com/lhjnano/hits.git
cd hits

# Backend setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend build
cd hits_web && npm install && npm run build && cd ..

# Development mode (Vite HMR + FastAPI)
./run.sh --dev

# Run tests
./run.sh --test
```

## License

Apache 2.0 — free for commercial use.

## Links

- **GitHub**: [https://github.com/lhjnano/hits](https://github.com/lhjnano/hits)
- **Issues**: [https://github.com/lhjnano/hits/issues](https://github.com/lhjnano/hits/issues)
