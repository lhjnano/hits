# MCP Tools Reference

HITS exposes 11 MCP tools via stdio transport. Once registered with your AI tool, your AI can call these directly — no HTTP requests needed.

## Setup

### Claude Code

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

### OpenCode (`~/.config/opencode/mcp.json`)

```json
{
  "mcpServers": {
    "hits": {
      "command": "npx",
      "args": ["-y", "-p", "@puraven/hits", "hits-mcp"]
    }
  }
}
```

> **Important:** You must use `npx -p @purpleraven/hits hits-mcp` (specify the package), not just `npx hits-mcp`. The `hits-mcp` binary is inside the `@purpleraven/hits` package.
>
> **How it works:** `npx` downloads the package, auto-detects Python, creates a venv, installs dependencies, and spawns the MCP server over stdio — all automatically on first run.

---

## Checkpoint Tools (Recommended)

These are the primary tools. They combine multiple actions into single calls for the simplest possible workflow.

### `hits_auto_checkpoint`

**Call this when your session is ending.** One call does everything:
1. Records a work log
2. Generates a structured checkpoint (with next steps, context, decisions)
3. Sends a handover signal to the next AI tool

```python
hits_auto_checkpoint(
    performer="claude",                    # Your tool name
    purpose="Implement JWT authentication", # What this session was trying to do
    current_state="Argon2id + JWT done",   # What was actually achieved
    completion_pct=60,                     # 0-100 estimated completion

    # Optional — provide explicit structured data:
    next_steps=[
        {"action": "Add refresh tokens", "command": "edit auth.py", "priority": "high"},
        {"action": "Write tests", "file": "tests/test_auth.py", "priority": "medium"},
    ],
    required_context=["Using Argon2id, not bcrypt"],
    files_modified=["auth/manager.py", "auth/middleware.py"],
    commands_run=["pytest tests/"],
    blocks=[{"issue": "Redis down in test env", "workaround": "Use mock"}],
    decisions=[{"decision": "HttpOnly cookies for JWT", "rationale": "More secure"}],

    # Signal options
    send_signal=True,                      # Also send handover signal (default: true)
    signal_recipient="any",                # Target tool (default: "any")

    # Output control
    token_budget=2000,                     # Max tokens for compressed output
)
```

Even if you don't provide explicit fields, it **auto-extracts** next steps, decisions, blocks, and context from your existing work logs.

**Returns:** Compressed checkpoint text that can be pasted into the next session.

### `hits_resume`

**Call this when a new session starts.** One call does everything:
1. Loads the latest checkpoint for the current project
2. Checks for pending handover signals
3. Auto-consumes signals addressed to you
4. Returns compressed, actionable context

```python
hits_resume(
    performer="opencode",       # Your tool name (for consuming signals)
    token_budget=2000,          # Max tokens for response
    # project_path auto-detected from CWD
)
```

**Returns:**
```
📬 PENDING SIGNALS:
  🟢 [claude] JWT auth done
    • Add refresh tokens
    • Write tests

--- RESUME CONTEXT ---

## CHECKPOINT: my-project
path: /home/user/my-project
git: feature/auth (3 changes)

PURPOSE: Implement JWT authentication
ACHIEVED: Argon2id hashing + JWT issuance complete

NEXT STEPS:
  1. 🟡 Add refresh token rotation → edit auth/manager.py
  2. 🟢 Write auth middleware tests → pytest tests/

MUST KNOW:
  • Using Argon2id (not bcrypt)

FILES: [~] auth/manager.py  [+] tests/test_auth.py

--- END RESUME ---
```

### `hits_list_checkpoints`

List available resume points (checkpoints) for a project.

```python
hits_list_checkpoints(
    limit=5,                     # Max results
    # project_path auto-detected from CWD
)
```

**Returns:**
```
📍 Resume Points (2)

  1. [2026-04-21 13:02] claude
     purpose: Add checkpoint system
     progress: ████████░░ 80%
     next: Run full test suite
     git: main
     ID: cp_e0aa1eac

  2. [2026-04-21 11:30] opencode
     purpose: Fix auth middleware
     progress: ██████████ 100%
     git: fix/middleware
     ID: cp_a1b2c3d4
```

---

## Core Tools

Lower-level tools for granular control. The checkpoint tools above combine these automatically.

### `hits_record_work`

Record a work log entry. Auto-detects project path from CWD.

```python
hits_record_work(
    request_text="Added rate limiting to login endpoint",   # Required
    performed_by="claude",                                   # Required
    context="10 req/min per IP, 429 on limit",
    tags=["security", "api"],
    files_modified=["auth/middleware.py"],
    commands_run=["pytest tests/"],
    project_path="/abs/path",                                # Optional, auto-detected
)
```

### `hits_get_handover`

Get a handover summary for the current project. Legacy tool — `hits_resume` is recommended instead.

```python
hits_get_handover(
    format="text",    # "text" or "dict"
    # project_path auto-detected
)
```

### `hits_search_works`

Search past work logs by keyword.

```python
hits_search_works(
    query="auth",      # Required
    limit=10,
    # project_path auto-detected
)
```

### `hits_list_projects`

List all projects that have recorded work logs.

```python
hits_list_projects()
```

### `hits_get_recent`

Get recent work logs — lighter than full handover.

```python
hits_get_recent(
    limit=10,
    performed_by="claude",    # Optional filter
    # project_path auto-detected
)
```

---

## Signal Tools

For real-time handover between AI tools. See [signals.md](signals.md) for the full guide.

### `hits_signal_send`

Send a handover signal to another AI tool.

```python
hits_signal_send(
    sender="claude",                  # Required
    summary="JWT auth done",          # Required
    recipient="any",                  # "claude", "opencode", "cursor", or "any"
    signal_type="session_end",        # session_end | task_ready | question | urgent
    priority="normal",                # normal | high | urgent
    pending_items=["rate limiting"],
    tags=["auth"],
    context="Full context here...",
)
```

### `hits_signal_check`

Check for pending signals addressed to you.

```python
hits_signal_check(
    recipient="any",      # Your tool name, or "any"
    limit=10,
)
```

### `hits_signal_consume`

Acknowledge and archive a signal.

```python
hits_signal_consume(
    signal_id="sig_abc12345",     # Required
    consumed_by="opencode",        # Required
)
```

---

## Example Workflow

### Before (4 manual steps)

```
Session End:   hits_record_work() + hits_signal_send()
Session Start: hits_signal_check() + hits_get_handover() + hits_signal_consume()
```

### After (2 automated steps)

```
Session End:   hits_auto_checkpoint()      # Does everything
Session Start: hits_resume()               # Gets everything
```
