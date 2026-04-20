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

When an AI session is replaced due to token limits, project-specific handover activates automatically.
All data is centrally stored at `~/.hits/data/` and isolated by project path.

### 🚀 Quick Start (Recommended)

```bash
# At session START - resume where you left off
npx @purpleraven/hits resume              # Auto-detects project from CWD
npx @purpleraven/hits resume -l           # List all projects
npx @purpleraven/hits resume -p /path     # Resume specific project

# Via MCP tool (when HITS MCP is configured):
# hits_resume() → Get structured checkpoint with next steps + pending signals
```

### On Session Start

```bash
# Option 1: MCP tool (recommended)
hits_resume()                              # Gets checkpoint + signals in one call

# Option 2: HTTP API
curl -s "http://localhost:8765/api/checkpoint/resume?project_path=$(pwd)"

# Option 3: CLI
npx @purpleraven/hits resume
```

### On Session End (MUST do - one call does everything!)

```bash
# MCP tool: hits_auto_checkpoint (recommended)
# This ONE call automatically:
#   1. Records the work log
#   2. Generates a structured checkpoint with next steps
#   3. Sends a handover signal to the next AI tool
#   4. Compresses output within token budget

hits_auto_checkpoint(
    performer="claude",
    purpose="What this session was trying to accomplish",
    current_state="What was actually achieved",
    completion_pct=60,
    next_steps=[
        {"action": "Add feature X", "command": "edit file.py", "file": "file.py", "priority": "high"},
        {"action": "Write tests", "command": "pytest tests/", "priority": "medium"},
    ],
    required_context=[
        "Critical fact the next session must know",
    ],
    files_modified=["path/to/file1.py", "path/to/file2.py"],
    blocks=[{"issue": "Something blocking", "workaround": "How to work around"}],
    decisions=[{"decision": "What was decided", "rationale": "Why"}],
)
```

### 🆕 Checkpoint System (v0.6+)

The **Checkpoint** is the evolution of the Handover summary. Instead of a passive summary,
it's an **executable snapshot** with:

| Field | Description |
|-------|-------------|
| `purpose` | What this session was trying to accomplish |
| `current_state` | What was actually achieved |
| `next_steps` | Priority-ordered actionable steps with commands and files |
| `required_context` | Critical facts the next session MUST know |
| `decisions_made` | Architectural decisions with rationale |
| `blocks` | Current blockers with workarounds |
| `files_delta` | File changes (created/modified/deleted) |

**Token-Aware Compression**: Checkpoints automatically compress to fit within a token budget.
At lower budgets, low-priority items are dropped first, preserving critical info.

**Project Resume Points**: Each project maintains a history of checkpoints.
Use `hits_list_checkpoints()` or `npx @purpleraven/hits resume -l` to see all resume points.

### MCP Tools (Updated)

**Core Tools:**
```
hits_record_work          → Record work entry (auto-detects project_path)
hits_get_handover         → Query handover summary (legacy)
hits_search_works         → Search past work
hits_list_projects        → List projects
hits_get_recent           → Get recent work
```

**Signal Tools:**
```
hits_signal_send          → Send a handover signal
hits_signal_check         → Check for pending signals
hits_signal_consume       → Acknowledge and archive a signal
```

**🆕 Checkpoint Tools (Recommended):**
```
hits_auto_checkpoint      → Auto-checkpoint at session end (record + checkpoint + signal)
hits_resume               → Resume at session start (checkpoint + signals + consume)
hits_list_checkpoints     → List available resume points
```

### Session Flow (Simplified)

**Before (manual, 4 steps):**
```
Session End:   hits_record_work() + hits_signal_send()
Session Start: hits_signal_check() + hits_get_handover() + hits_signal_consume()
```

**After (automated, 2 steps):**
```
Session End:   hits_auto_checkpoint()     # Does everything
Session Start: hits_resume()              # Gets everything
```

**CLI Alternative:**
```
Session End:   hits_auto_checkpoint()     # Via MCP
Session Start: npx @purpleraven/hits resume   # Via CLI
```

### Data Store

| Location | Description |
|----------|-------------|
| `~/.hits/data/work_logs/` | Work logs (JSON) |
| `~/.hits/data/checkpoints/` | **Structured checkpoints per project** |
| `~/.hits/data/trees/` | Knowledge trees |
| `~/.hits/data/workflows/` | Workflows |
| `~/.hits/data/signals/pending/` | Pending handover signals |
| `~/.hits/data/signals/consumed/` | Archived signals (auto-cleaned 72h) |
| `~/.hits/.auth/` | Auth data (permissions 600/700) |
| `HITS_DATA_PATH` env var | Override storage path |

## API Endpoints

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/status` | Auth status (initialized, logged in) |
| POST | `/api/auth/register` | Register user (first user = admin) |
| POST | `/api/auth/login` | Login (sets HttpOnly cookies) |
| POST | `/api/auth/logout` | Logout |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/me` | Current user info |
| PUT | `/api/auth/password` | Change password |

### Work Logs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Server health check |
| POST | `/api/work-log` | Create work log |
| GET | `/api/work-logs` | List work logs (supports `project_path` filter) |
| GET | `/api/work-logs/search?q=keyword` | Search work logs (supports `project_path` filter) |
| GET | `/api/work-log/{id}` | Get single entry |
| PUT | `/api/work-log/{id}` | Update entry |
| DELETE | `/api/work-log/{id}` | Delete entry |

### Handover

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/handover?project_path=...` | Project handover summary |
| GET | `/api/handover/projects` | List projects |
| GET | `/api/handover/project-stats?project_path=...` | Project stats |

### Knowledge Categories

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/knowledge/categories` | List categories |
| POST | `/api/knowledge/category` | Create category |
| PUT | `/api/knowledge/category/{name}` | Update category |
| DELETE | `/api/knowledge/category/{name}` | Delete category |
| POST | `/api/knowledge/category/{name}/nodes` | Add node |
| PUT | `/api/knowledge/category/{name}/nodes/{idx}` | Update node |
| DELETE | `/api/knowledge/category/{name}/nodes/{idx}` | Delete node |

### Knowledge Tree (Node-based)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/node` | Create knowledge node |
| PUT | `/api/node/{id}` | Update knowledge node |
| DELETE | `/api/node/{id}` | Delete knowledge node |

### Signals (Cross-Tool Handover)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/signals/send` | Send a handover signal |
| GET | `/api/signals/check` | Check pending signals (filter by recipient, project) |
| POST | `/api/signals/consume` | Consume (acknowledge) a signal |
| GET | `/api/signals/pending` | List all pending signals |
| DELETE | `/api/signals/{signal_id}` | Delete a signal |

### Checkpoints (Session Resume)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/checkpoint/resume?project_path=...` | Get latest checkpoint + signals for resume |
| GET | `/api/checkpoint/latest?project_path=...` | Get latest checkpoint only |
| GET | `/api/checkpoint/list?project_path=...` | List checkpoints for a project |
| POST | `/api/checkpoint/auto` | Generate auto-checkpoint (record + checkpoint + signal) |
| GET | `/api/checkpoint/projects` | List all projects with checkpoints |

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
├── models/                 # Node, Tree, Workflow, WorkLog, HandoverSignal, Checkpoint
│   ├── checkpoint.py       # 🆕 Structured checkpoint model
│   └── ...
├── storage/                # Redis, File storage (~/.hits/data/)
├── ai/                     # Compression, SLM filter, LLM client
│   ├── compressor.py       # Basic semantic compression
│   └── checkpoint_compressor.py  # 🆕 Token-aware checkpoint compression
├── platform/               # Cross-platform utilities
├── service/                # TreeService, HandoverService, KnowledgeService, SignalService
│   └── checkpoint_service.py     # 🆕 Checkpoint generation & management
├── api/                    # FastAPI server + routes
│   └── routes/             # health, work_log, node, handover, auth, knowledge, signal, checkpoint
├── collector/              # Git, Shell, AI session collectors
├── mcp/                    # MCP server (stdio transport)
│   └── server.py           # 🆕 Updated with checkpoint tools
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

hooks/                        # Cross-tool signal detection scripts
├── claude_signal_watcher.sh  # Claude Code SessionStart hook
└── opencode_signal_watcher.sh # OpenCode startup hook

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
