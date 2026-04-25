<div align="center">

# 🧠 HITS

### **Your AI session died. Your work didn't.**

**The checkpoint system for AI coding sessions. Token limits, session swaps, tool switches — pick up exactly where you left off, instantly.**

[![npm version](https://img.shields.io/npm/v/@purpleraven/hits?color=blue&label=npm)](https://www.npmjs.com/package/@purpleraven/hits)
[![license](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)

</div>

---

```
⚠️  Token limit reached. Session ending...

                                  Next session:

    $ npx @purpleraven/hits resume

    ▶ RESUME: my-project
      Purpose: Implement JWT authentication
      Progress: 60% (by claude)
      Achieved: Argon2id hashing + JWT issuance complete

      Next Steps:
        1. 🟡 Add refresh token rotation → edit auth/manager.py
        2. 🟢 Write auth middleware tests  → pytest tests/

    ✅ Back to work in 0 seconds — exactly where you stopped.
```

**3 seconds to install → 1 second to checkpoint at session end → 0 seconds to resume next session**

---

## How It Works — Two Commands, That's It

```
  ┌──────────────────────────────┐       ┌──────────────────────────────┐
  │      Session End             │       │      Session Start           │
  │                              │       │                              │
  │   hits_auto_checkpoint()     │       │   $ npx @purpleraven/hits    │
  │                              │       │         resume               │
  │   ① Records your work        │  ───▶ │                              │
  │   ② Saves structured context │       │   → Loads checkpoint         │
  │   ③ Sends signal to next AI  │       │   → Checks pending signals   │
  │   ④ Token-aware compression  │       │   → Full context restored    │
  │                              │       │                              │
  └──────────────────────────────┘       └──────────────────────────────┘
```

That's the whole loop. Your AI calls one tool when finishing, you run one command when starting. Everything else is automatic.

## Quick Start

### Install & Run

```bash
npx @purpleraven/hits
```

Opens **http://127.0.0.1:8765** — create your admin account on first visit. Done.

### Connect Your AI (MCP)

```bash
# Claude Code
claude mcp add hits -- npx -y -p @purpleraven/hits hits-mcp

# Or add to .mcp.json / opencode config — see docs/mcp-tools.md
```

**Now your AI knows about checkpoints.** It will:
- Auto-call `hits_auto_checkpoint()` when a session ends
- Auto-call `hits_resume()` when a session starts
- Or you can run `npx @purpleraven/hits resume` from the terminal

### Resume Where You Left Off

This is the core of HITS. Whenever you start a new session — because tokens ran out, you switched tools, or you're coming back tomorrow:

```bash
cd ~/source/my-project
npx @purpleraven/hits resume
```

You get a **structured checkpoint** — not a vague summary, but actionable data:

| Field | What You See |
|-------|-------------|
| **Purpose** | What the previous session was trying to accomplish |
| **Achieved** | What was actually done |
| **Next Steps** | Priority-ordered actions with shell commands and file paths |
| **Must Know** | Critical context the next session needs (decisions, constraints) |
| **Files** | What was created, modified, or deleted |
| **Blockers** | What's preventing progress, with known workarounds |

Everything is **token-aware compressed** — it fits within your AI's context budget automatically, dropping low-priority items first.

### List All Resume Points

```bash
npx @purpleraven/hits resume --list
```

```
📍 Resume Points (3 projects)

  1. auth-service
     path: /home/user/auth-service
     progress: ████████░░ 80%  by claude  at 2026-04-21T15:30
     purpose: Implement JWT authentication
     git: feature/auth

  2. data-pipeline
     path: /home/user/data-pipeline
     progress: ████░░░░░░ 40%  by opencode  at 2026-04-20T09:15
     purpose: Build ETL pipeline for analytics
```

## Why This Matters

> Working with Claude Code for hours... **Token limit reached.**  
> A new session starts, but it has **no idea** what you did, what was decided, or what's left.

| The Problem | HITS Solution |
|------|-----------|
| 🔴 Token limit kills your session | ✅ **Auto-checkpoint** — next session picks up exactly where you stopped |
| 🔴 Switching AI tools (Claude ↔ OpenCode ↔ Cursor) | ✅ **Cross-tool signals** — real-time handover between any AI |
| 🔴 "What was I doing?" | ✅ **Actionable Next Steps** — with commands, not just descriptions |
| 🔴 Previous decisions forgotten | ✅ **Structured Decision log** — what was decided and why |
| 🔴 Too much context, wasting tokens | ✅ **Token-aware compression** — fits your budget automatically |

## What You Get

### 🆕 Resume Tab (Web UI)

The default landing page — your latest checkpoint at a glance:

```
┌─────────────────────────────────────────────────────────┐
│  ▶ Resume   📌 Tasks   📋 Knowledge   📝 Timeline       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  💾 my-project                          ██████░░ 60%    │
│     Implement JWT authentication                        │
│     🔀 feature/auth   claude   2026-04-21 15:30        │
│                                                         │
│  ▶ Next Steps                                           │
│    1. 🟡 Add refresh token rotation                     │
│       → edit auth/manager.py                            │
│    2. 🟢 Write auth middleware tests                    │
│       → pytest tests/                                   │
│                                                         │
│  ⚠ Must Know                                           │
│    • Using Argon2id (not bcrypt)                        │
│    • JWT expires after 15 minutes                       │
│                                                         │
│  💡 Project Know-How (auto-injected from Knowledge)     │
│    • HOW: Argon2id + JWT HttpOnly cookies               │
│    • HOW: Use Argon2id, NOT bcrypt                      │
│    • WHAT: POST /api/auth/login → Set-Cookie            │
│                                                         │
│  📄 Files (3)                                           │
│    [~] auth/manager.py  [~] middleware.py  [+] test.py  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Knowledge Tree

Organize project knowledge as Why-How-What nodes with negative paths:

```
📁 Authentication
  ├── WHY  "Need secure user auth for web UI"
  ├── HOW  "Argon2id hashing + JWT HttpOnly cookies"
  └── WHAT "POST /api/auth/login → Set-Cookie"
      └── ❌ "Tried bcrypt first — too fast, GPU-vulnerable"
```

### Timeline

Chronological work log grouped by date. Click to expand context, files modified, commands run.

### Cross-Tool Signals

Claude → OpenCode → Cursor. File-based, no server needed. Hooks auto-inject on session start.

---

## 🧪 Experimental Features

These features are in early development. They work, but APIs and UX may change.

### Task Management with Slack Sync

A lightweight task board built into HITS — designed for **solo developers and small teams** who track work across machines and want to sync via Slack.

```
┌──────────────────────────────────────────────────────────┐
│  📌 Tasks                                  + Add Task    │
│                                                           │
│  ● 2 channels connected            ⚙️ Slack Settings     │
│                                                           │
│  All (5)  |  Active (3)  |  Done (2)  |  💬 #dev-tasks   │
│  ─────────────────────────────────────────────────────── │
│                                                           │
│  🔴 Fix login 500 error              📂 app  💻 Local    │
│     Users report 500 on POST /login                      │
│     [✅ Done]  [📤 Export]  [✏️ Edit]                     │
│                                                           │
│  🔵 Add dark mode toggle                       💻 Local   │
│     [✅ Done]  [📤 Export]  [✏️ Edit]                     │
│                                                           │
│  🟠 Review API docs                  💬 #dev-tasks        │
│     ⚠️ Different environment — DESKTOP-OFFICE Windows     │
│     [✅ Done]  [📤 Export]  [✏️ Edit]                     │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

**What it does:**

- **Create, edit, reopen, complete tasks** — full lifecycle, not just done/delete
- **Filter by status or Slack channel** — see only what matters
- **Export tasks to Slack** — send a task to a channel via webhook
- **Import tasks from Slack** — pull messages from a channel as tasks
- **Environment-awareness** — tasks created on another machine carry hostname, OS info. UI warns you to verify paths before acting on them.
- **Priority levels** — Critical 🔴 / High 🟠 / Medium 🔵 / Low ⚪

**How to set up Slack sync:**

```bash
# 1. Open HITS Web UI → 📌 Tasks tab → ⚙️ Slack Settings
# 2. Add a channel:
#    Name:   #dev-tasks
#    Webhook: https://hooks.slack.com/services/T.../B.../xxx
# 3. Now you can export tasks to that channel, or import from it
```

> **Why Slack, not Git?** Designers, PMs, and office workers don't use Git. Slack is the common ground. Tasks flow in from Slack, get worked on locally, and results flow back out.

**API endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/tasks` | List all tasks |
| `POST` | `/api/tasks` | Create a task |
| `PUT` | `/api/tasks/{id}` | Update a task |
| `DELETE` | `/api/tasks/{id}` | Delete a task |
| `POST` | `/api/tasks/{id}/export` | Export task to Slack channel |
| `GET` | `/api/tasks/slack/channels` | List configured Slack channels |
| `POST` | `/api/tasks/slack/channels` | Add a Slack channel |
| `DELETE` | `/api/tasks/slack/channels/{name}` | Remove a Slack channel |
| `POST` | `/api/tasks/slack/import` | Import tasks from Slack channel |

> ⚠️ **Feedback wanted.** This is an experiment. If you use it, please share your experience in [GitHub Discussions](https://github.com/lhjnano/hits/discussions).

## Requirements

| Requirement | Version | Why |
|-------------|---------|-----|
| **Node.js** | ≥ 18 | Runs the web server |
| **Python** | ≥ 3.10 | Runs the FastAPI backend (auto-installed) |

No database. File-based storage at `~/.hits/data/`.

## CLI

```bash
npx @purpleraven/hits                       # Start web server
npx @purpleraven/hits resume                # Resume current project
npx @purpleraven/hits resume -l             # List all resume points
npx @purpleraven/hits resume -p /path       # Resume specific project
npx @purpleraven/hits resume -t 1000        # Limit output to ~1000 tokens
npx @purpleraven/hits --port 9000           # Custom port
```

## Documentation

| Document | Description |
|----------|-------------|
| [MCP Tools Reference](docs/mcp-tools.md) | All 11 MCP tools with parameters and examples |
| [REST API Reference](docs/api-reference.md) | Full API endpoint documentation |
| [Architecture](docs/architecture.md) | How it works under the hood, data storage, security |
| [Cross-Tool Signals](docs/signals.md) | Signal system, hooks setup, Claude/OpenCode/Cursor |

## Development

```bash
git clone https://github.com/lhjnano/hits.git
cd hits
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd hits_web && npm install && npm run build && cd ..
./run.sh --dev
```

## License

Apache 2.0 — free for commercial use.

## Community

💬 **Have questions? Ideas? Want to share how you use HITS?**

[![GitHub Discussions](https://img.shields.io/badge/GitHub-Discussions-blue?logo=github&style=social)](https://github.com/lhjnano/hits/discussions)

Join the conversation — feature requests, bug reports, workflows, tips & tricks.

## Links

- **npm**: [https://www.npmjs.com/package/@purpleraven/hits](https://www.npmjs.com/package/@purpleraven/hits)
- **GitHub**: [https://github.com/lhjnano/hits](https://github.com/lhjnano/hits)
- **Issues**: [https://github.com/lhjnano/hits/issues](https://github.com/lhjnano/hits/issues)
- **Discussions**: [https://github.com/lhjnano/hits/discussions](https://github.com/lhjnano/hits/discussions)
