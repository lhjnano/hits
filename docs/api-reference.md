# REST API Reference

All HITS features are accessible via HTTP API at `http://localhost:8765/api/`. Authentication required for most endpoints (HttpOnly JWT cookies).

---

## Authentication

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/status` | Check if auth is initialized, current login status |
| POST | `/api/auth/register` | Register user (first user = admin) |
| POST | `/api/auth/login` | Login — sets HttpOnly cookies |
| POST | `/api/auth/logout` | Logout — clears cookies |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/me` | Get current user info |
| PUT | `/api/auth/password` | Change password |

```bash
# Register (first user becomes admin)
curl -X POST http://localhost:8765/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-secure-password"}'

# Login
curl -X POST http://localhost:8765/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-secure-password"}' \
  -c cookies.txt

# All subsequent requests use the cookie
curl http://localhost:8765/api/auth/me -b cookies.txt
```

---

## Checkpoints (Session Resume)

### Get Resume Context

**`GET /api/checkpoint/resume?project_path=...`**

Get latest checkpoint + pending signals for project resume. This is the API equivalent of `hits_resume()`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_path` | string | **Required.** Project absolute path |
| `token_budget` | int | Max tokens for compressed output (default: 2000) |
| `performer` | string | Tool name for auto-consuming signals |

```bash
curl "http://localhost:8765/api/checkpoint/resume?project_path=/home/user/my-project" \
  -b cookies.txt
```

### Get Latest Checkpoint

**`GET /api/checkpoint/latest?project_path=...`**

Get the latest checkpoint for a project (without signals).

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_path` | string | **Required.** Project absolute path |
| `token_budget` | int | Max tokens (default: 2000) |
| `format` | string | `text` (default) or `json` |

### List Checkpoints

**`GET /api/checkpoint/list?project_path=...`**

List available checkpoints for a project, most recent first.

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_path` | string | **Required.** Project absolute path |
| `limit` | int | Max results (default: 10) |

### Auto-Checkpoint

**`POST /api/checkpoint/auto`**

Generate an auto-checkpoint for the current session. This is the API equivalent of `hits_auto_checkpoint()`.

```bash
curl -X POST http://localhost:8765/api/checkpoint/auto \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "project_path": "/home/user/my-project",
    "performer": "claude",
    "purpose": "Implement JWT authentication",
    "current_state": "Argon2id hashing done",
    "completion_pct": 60,
    "next_steps": [
      {"action": "Add refresh tokens", "command": "edit auth.py", "priority": "high"}
    ],
    "required_context": ["Using Argon2id, not bcrypt"],
    "files_modified": ["auth/manager.py"],
    "send_signal": true
  }'
```

### List Projects

**`GET /api/checkpoint/projects`**

List all projects that have checkpoint history.

---

## Work Logs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/work-log` | Create work log |
| GET | `/api/work-logs` | List logs (filter by `project_path`) |
| GET | `/api/work-logs/search?q=...` | Search logs by keyword |
| GET | `/api/work-log/{id}` | Get single entry |
| PUT | `/api/work-log/{id}` | Update entry |
| DELETE | `/api/work-log/{id}` | Delete entry |

```bash
# Create work log
curl -X POST http://localhost:8765/api/work-log \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "performed_by": "claude",
    "source": "ai_session",
    "request_text": "Added rate limiting to login endpoint",
    "context": "10 req/min per IP, 429 response on limit",
    "project_path": "/home/user/my-project",
    "tags": ["security", "api"],
    "result_data": {
      "files_modified": ["auth/middleware.py"],
      "commands_run": ["pytest tests/"]
    }
  }'

# Search
curl "http://localhost:8765/api/work-logs/search?q=auth&project_path=/home/user/my-project" \
  -b cookies.txt
```

---

## Handover (Legacy)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/handover?project_path=...` | Get project handover summary |
| GET | `/api/handover/projects` | List all projects |
| GET | `/api/handover/project-stats?project_path=...` | Get project statistics |

> **Note:** For new projects, prefer the Checkpoint API above. Handover provides informational summaries; Checkpoints provide actionable structured data.

---

## Knowledge

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/knowledge/categories` | List categories |
| POST | `/api/knowledge/category` | Create category |
| PUT | `/api/knowledge/category/{name}` | Update category |
| DELETE | `/api/knowledge/category/{name}` | Delete category |
| POST | `/api/knowledge/category/{name}/nodes` | Add node to category |
| PUT | `/api/knowledge/category/{name}/nodes/{idx}` | Update node |
| DELETE | `/api/knowledge/category/{name}/nodes/{idx}` | Delete node |

---

## Signals (Cross-Tool Handover)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/signals/send` | Send a handover signal |
| GET | `/api/signals/check` | Check pending signals |
| POST | `/api/signals/consume` | Consume (acknowledge) a signal |
| GET | `/api/signals/pending` | List all pending signals |
| DELETE | `/api/signals/{signal_id}` | Delete a signal |

```bash
# Send signal
curl -X POST http://localhost:8765/api/signals/send \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"sender":"claude","recipient":"opencode","summary":"JWT auth done","pending_items":["rate limiting"]}'

# Check signals
curl "http://localhost:8765/api/signals/check?recipient=opencode" -b cookies.txt

# Consume signal
curl -X POST http://localhost:8765/api/signals/consume \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"signal_id":"sig_abc12345","consumed_by":"opencode"}'
```

See [signals.md](signals.md) for the full cross-tool signal guide.

---

## Health

**`GET /api/health`** — No auth required. Returns server status.
