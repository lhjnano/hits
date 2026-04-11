# HITS - Hybrid Intel Trace System

> Replicate your predecessor's brain as perfectly as possible, using the least amount of AI.

## Overview

HITS is a hybrid knowledge management system designed to preserve organizational core knowledge and decision-making context. It automates project-specific handover when switching between AI tool sessions (Claude, OpenCode, Cursor, etc.).

### Core Values

- **Token Optimization**: Semantic compression and on-demand analysis to reduce AI costs
- **Context Preservation**: Store decision-making processes in a Why-How-What hierarchy
- **Failure Experience**: Record failed approaches alongside successes as Negative Paths
- **Security Hardened**: Argon2id hashing, JWT HttpOnly cookies, CSP, Rate Limiting
- **AI Session Handover**: Automatically transfer project context when AI sessions rotate due to token limits
- **Centralized Storage**: All AI tool work logs are consolidated at `~/.hits/data/`
- **Project Isolation**: Completely independent context management based on project path

## Tech Stack

| Area | Technology |
|------|-----------|
| **Backend** | Python 3.10+, FastAPI, Pydantic v2 |
| **Frontend** | Svelte 5, Vite, TypeScript |
| **Authentication** | Argon2id (passwords), JWT HS256 (HttpOnly cookies) |
| **Storage** | File-based (`~/.hits/data/`), Redis (optional) |
| **Security** | CSP, CORS, Rate Limiting, Secure Headers |

## Installation

### Requirements

- Python 3.10 or later
- Node.js 18+ (for frontend build)
- Redis (optional — falls back to file storage)

### Quick Start

```bash
cd hits
./run.sh          # Auto-install + start server
```

#### Development Mode

```bash
./run.sh --dev    # Vite HMR + FastAPI backend
```

#### Manual Installation

```bash
# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend build
cd hits_web
npm install
npm run build
cd ..

# Start server
python -m hits_core.main --port 8765
```

## Security

### Authentication System

| Feature | Implementation |
|---------|---------------|
| **Password Hashing** | Argon2id (memory=64MB, iterations=3, parallelism=1) |
| **Minimum Password Length** | 8 characters |
| **JWT Tokens** | HttpOnly + Secure + SameSite=Lax cookies |
| **Access Token** | 15-minute expiry |
| **Refresh Token** | 7-day expiry, sent only to `/api/auth/refresh` |
| **First User** | Automatically assigned admin role |
| **Subsequent Users** | Can only be created by admin |

### Security Headers

```
Content-Security-Policy: default-src 'self'; script-src 'self'; ...
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

### Rate Limiting

- Login endpoint: 10 requests/minute (per IP)
- Responds with 429 Too Many Requests when exceeded

### Data Protection

| Item | Permissions | Description |
|------|-------------|-------------|
| `~/.hits/.auth/users.json` | 600 | User data (owner only) |
| `~/.hits/.pepper` | 600 | HMAC pepper (owner only) |
| `~/.hits/.jwt_secret` | 600 | JWT signing key (owner only) |
| `~/.hits/.auth/` | 700 | Auth directory (owner only) |

## Web UI

### Layout

```
┌─────────────┬───────────────────────────────────┐
│  Sidebar    │  Header (tabs + user menu)         │
│             ├───────────────────────────────────┤
│  📂 Projects│                                   │
│  ────────── │  Main content area                 │
│  /project-a │                                   │
│  /project-b │  📋 Knowledge | 📝 Timeline | 🔄 Handover │
│  /project-c │                                   │
│             │                                   │
└─────────────┴───────────────────────────────────┘
```

### Features

- **Knowledge Tree**: Manage Why-How-What nodes by category (full CRUD)
- **Timeline**: Project work logs, grouped by date, with search
- **Handover**: Auto-generated handover summary when a project is selected
- **Project Switching**: Instant context switch via sidebar
- **User Management**: Password change, logout

## AI Session Handover

### How It Works

```
[OpenCode Session]                  [Claude Session]
       │                                  │
   Perform work                        Session start
       │                                  │
   Record work ──────────────────────→ Query handover
   POST /api/work-log               GET /api/handover
   project_path: /my-project        project_path: /my-project
       │                                  │
       └──→ ~/.hits/data/ ←──┘            │
            (centralized)            Understand previous context
                                          │
                                     Continue work seamlessly
```

### MCP Configuration

Add to your OpenCode or Claude MCP settings:

```json
{
  "hits": {
    "type": "local",
    "command": ["python", "-m", "hits_core.mcp.server"],
    "cwd": "/path/to/hits"
  }
}
```

MCP Tools:
- `hits_record_work`: Record work entry
- `hits_get_handover`: Get handover summary
- `hits_search_works`: Search past work
- `hits_list_projects`: List projects
- `hits_get_recent`: Get recent work

## API Endpoints

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/status` | Check auth status |
| POST | `/api/auth/register` | Register user |
| POST | `/api/auth/login` | Login (sets HttpOnly cookies) |
| POST | `/api/auth/logout` | Logout |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/me` | Get current user info |
| PUT | `/api/auth/password` | Change password |

### Work Logs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/work-log` | Create work log |
| GET | `/api/work-logs` | List work logs (supports `project_path` filter) |
| GET | `/api/work-logs/search?q=...` | Search work logs |
| GET | `/api/work-log/{id}` | Get single entry |
| PUT | `/api/work-log/{id}` | Update entry |
| DELETE | `/api/work-log/{id}` | Delete entry |

### Handover

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/handover?project_path=...` | Get project handover summary |
| GET | `/api/handover/projects` | List projects |
| GET | `/api/handover/project-stats?project_path=...` | Get project stats |

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

### performed_by Values

| AI Tool | Value |
|---------|-------|
| OpenCode | `opencode` |
| Claude Code | `claude` |
| Cursor | `cursor` |
| Manual | `manual` |

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   hits_web (Svelte 5 + Vite)              │
│              Material Dark theme · TypeScript              │
│  ┌──────────┬──────────┬──────────────────────────┐       │
│  │ Sidebar  │ Knowledge│ HandoverPanel            │       │
│  │ Projects │ Tree     │ Handover summary view    │       │
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

## Knowledge Tree Structure

### Why-How-What Hierarchy

```
├── WHY (Intent/Purpose)
│   ├── "Why was this system built?"
│   └── "What is the business goal?"
│
├── HOW (Logic/Method)
│   ├── "How was it implemented?"
│   └── "What decisions were made?"
│
└── WHAT (Execution/Tasks)
    ├── "What specifically does it do?"
    └── "Actionable tasks"
```

## Development

### Development Mode

```bash
./run.sh --dev    # Vite HMR + FastAPI
```

### Testing

```bash
./run.sh --test   # Run pytest
```

### Frontend Development

```bash
cd hits_web
npm install        # Install dependencies
npm run dev        # Vite dev server (http://localhost:5173)
npm run build      # Production build
```

## License

| Package | License | Commercial Use |
|---------|---------|---------------|
| `hits_core` | Apache 2.0 | ✅ Free |
| `hits_web` | Apache 2.0 | ✅ Free |

## Troubleshooting

### Node.js Not Found

```bash
# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

### Redis Connection Failed

HITS works fine without Redis. It automatically falls back to file-based storage.

### Where Is Data Stored?

```
~/.hits/
├── data/                ← Default location for all data
│   ├── work_logs/       ← AI session work logs
│   ├── trees/           ← Knowledge trees
│   └── workflows/       ← Workflows
├── .auth/               ← Authentication data
│   └── users.json       ← User info (permissions 600)
├── .pepper              ← HMAC pepper (permissions 600)
└── .jwt_secret          ← JWT signing key (permissions 600)

Override with HITS_DATA_PATH environment variable
```
