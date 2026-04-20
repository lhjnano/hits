# Architecture

## How It Works Under the Hood

```
npx @purpleraven/hits
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

## Data Storage

All data is stored centrally at `~/.hits/`. No database required.

```
~/.hits/
├── data/
│   ├── work_logs/          ← AI session work logs (JSON)
│   ├── checkpoints/        ← Structured checkpoints per project
│   │   ├── _home_user_projA/
│   │   │   ├── latest.json           ← Latest checkpoint (for quick resume)
│   │   │   ├── cp_a1b2c3d4.json      ← Checkpoint history
│   │   │   └── cp_e5f6g7h8.json
│   │   └── _home_user_projB/
│   │       └── latest.json
│   ├── trees/              ← Knowledge trees
│   ├── workflows/          ← Workflows
│   └── signals/
│       ├── pending/        ← Active signals (auto-cleaned 72h)
│       └── consumed/       ← Archived signals
├── backups/                ← CLI backups (tar.gz)
├── .auth/
│   └── users.json          ← User data (chmod 600)
├── .pepper                 ← HMAC pepper (chmod 600)
└── .jwt_secret             ← JWT signing key (chmod 600)
```

Override with `HITS_DATA_PATH` environment variable.

## Checkpoint Structure

A checkpoint is the evolution of a handover summary. Instead of passive information, it's an **executable snapshot**:

```json
{
  "id": "cp_a1b2c3d4",
  "project_path": "/home/user/my-project",
  "performer": "claude",
  "created_at": "2026-04-21T15:30:00",
  "purpose": "Implement JWT authentication",
  "current_state": "Argon2id hashing + JWT issuance complete",
  "completion_pct": 60,
  "next_steps": [
    {
      "action": "Add refresh token rotation",
      "command": "edit auth/manager.py",
      "file": "auth/manager.py",
      "priority": "high"
    }
  ],
  "required_context": ["Using Argon2id, not bcrypt"],
  "files_delta": [
    {"path": "auth/manager.py", "change_type": "modified"}
  ],
  "decisions_made": [
    {"decision": "HttpOnly cookies for JWT", "rationale": "More secure than localStorage"}
  ],
  "blocks": [
    {"issue": "Redis down in test env", "workaround": "Use mock Redis", "severity": "medium"}
  ],
  "git_branch": "feature/auth",
  "resume_command": "npx @purpleraven/hits resume --project /home/user/my-project"
}
```

## Token-Aware Compression

Checkpoints automatically compress to fit within a token budget. Four compression levels:

| Level | What's Included | When Used |
|-------|----------------|-----------|
| **L0** | All fields, full descriptions | Fits within budget |
| **L1** | Drop low-priority steps, truncate descriptions | Slightly over budget |
| **L2** | Only critical/high steps, essential context | Significantly over budget |
| **L3** | Single paragraph — purpose + next step | Very tight budget |

Compression is token-aware: Korean text (~2 chars/token) and English (~4 chars/token) are estimated separately.

## Security

| Feature | Implementation |
|---------|---------------|
| **Password Hashing** | Argon2id (64MB memory, 3 iterations, parallelism=1) |
| **JWT Tokens** | HttpOnly + Secure + SameSite=Lax cookies |
| **Access Token** | 15-minute expiry |
| **Refresh Token** | 7-day expiry, restricted to `/api/auth/refresh` path |
| **Brute Force Protection** | 10 login attempts/minute per IP |
| **Security Headers** | CSP, X-Frame-Options: DENY, HSTS preload, nosniff |
| **Data Protection** | Auth files stored with `chmod 600` (owner-only) |
| **First User Policy** | First registered user becomes admin |

## Project Structure

```
hits_core/                    # Apache 2.0 - Backend
├── auth/                   # Authentication & security
│   ├── manager.py          # Argon2id + JWT + user management
│   ├── middleware.py        # CSP, security headers
│   └── dependencies.py     # FastAPI auth dependencies
├── models/                 # Data models
│   ├── checkpoint.py       # Structured checkpoint model
│   ├── work_log.py         # Work log model
│   ├── signal.py           # Handover signal model
│   └── ...
├── storage/                # File-based storage (~/.hits/data/)
├── ai/
│   ├── checkpoint_compressor.py  # Token-aware compression
│   └── compressor.py             # Basic semantic compression
├── service/
│   ├── checkpoint_service.py     # Checkpoint generation & management
│   ├── handover_service.py       # Handover summary (legacy)
│   └── signal_service.py         # Cross-tool signals
├── api/routes/             # FastAPI endpoints
│   ├── checkpoint.py       # Checkpoint API
│   ├── auth.py             # Authentication API
│   └── ...
├── mcp/                    # MCP server (stdio transport)
│   └── server.py           # 11 MCP tools
└── cli.py                  # CLI (server, resume, backup, status)

hits_web/                    # Svelte 5 Web UI
├── src/components/
│   ├── ResumePanel.svelte  # Resume tab (default)
│   ├── MainLayout.svelte   # App shell
│   └── ...
└── dist/                   # Built static files (served by FastAPI)

hooks/                       # Cross-tool signal detection scripts
├── claude_signal_watcher.sh
└── opencode_signal_watcher.sh
```

## CLI Commands

```bash
# Web server
npx @purpleraven/hits                      # Start server
npx @purpleraven/hits --port 9000          # Custom port
npx @purpleraven/hits --dev                # Development mode

# Resume (the killer feature)
npx @purpleraven/hits resume               # Resume current project
npx @purpleraven/hits resume -l            # List all projects
npx @purpleraven/hits resume -p /path      # Resume specific project
npx @purpleraven/hits resume -t 1000       # Token budget limit

# Python CLI (installed automatically)
hits server --port 9000 --dev
hits backup                  # Backup all data
hits backup --list           # List backups
hits restore                 # Restore latest backup
hits status                  # Show data status

# Environment variables
HITS_PORT=9000               # Server port override
HITS_PYTHON=/usr/bin/python3 # Python path override
HITS_DATA_PATH=~/.hits/data  # Data storage path override
```
