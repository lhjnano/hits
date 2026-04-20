# Cross-Tool Signals

HITS provides a file-based signal system for real-time handover between AI tools (Claude ↔ OpenCode ↔ Cursor). No running server required — signals are just JSON files in `~/.hits/data/signals/`.

## How It Works

```
┌─────────────────┐     ~/.hits/data/signals/pending/     ┌─────────────────┐
│   Claude Code   │  ──── signal JSON file ─────────────►  │    OpenCode     │
│                 │                                       │                 │
│  hits_signal_   │                                       │  hook detects   │
│  send()         │                                       │  signal file    │
│                 │                                       │  hits_signal_   │
│                 │  ◄──── signal JSON file ─────────────  │  check()        │
└─────────────────┘                                       └─────────────────┘
```

## Signal Flow

### Manual Flow (3 steps)

```python
# 1. Send signal at session end (Claude → OpenCode)
hits_signal_send(
    sender="claude",
    recipient="opencode",        # or "any" for broadcast
    summary="JWT auth implementation done, rate limiting remaining",
    pending_items=["Add rate limiting", "Configure CORS"],
    priority="high"              # normal | high | urgent
)

# 2. Check signals at session start
hits_signal_check(recipient="opencode")
# → 🟡 [04/14 14:30] claude → opencode
#    Summary: JWT auth implementation done, rate limiting remaining
#    Pending: Add rate limiting, Configure CORS

# 3. Consume signal (acknowledge)
hits_signal_consume(signal_id="sig_abc12345", consumed_by="opencode")
```

### Automated Flow (Recommended)

Just use the checkpoint tools — they handle signals automatically:

```python
# Session end — sends signal as part of checkpoint
hits_auto_checkpoint(performer="claude", purpose="...", send_signal=True)

# Session start — auto-checks and auto-consumes signals
hits_resume(performer="opencode")
```

## Hook Setup (Automatic Detection)

Instead of manually calling `hits_signal_check`, configure hooks so signals and checkpoints are **automatically injected** when a session starts.

### Claude Code — SessionStart Hook

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
📬 HITS handover signal detected!
  From: opencode
  Type: session_end
  Priority: high
  Summary: LVM DR script debugging complete
  Pending items:
    - Test remote backup
    - Write CronJob manifest
  Signal ID: sig_fb5bd38c

👉 Use hits_resume() to load full context.

▶ HITS RESUME: Last session state
  Purpose: LVM DR script debugging
  Progress: 80% (by opencode)
  git: fix/lvm-dr
  Achieved: Debugging complete, tests passing

  Next Steps:
    1. 🟡 Test remote backup → bash scripts/test-backup.sh
    2. 🟢 Write CronJob manifest → k8s/cronjob.yaml
```

### OpenCode — SessionStart Hook

`~/.config/opencode/opencode.json` or project `.opencode/hooks/`:

```bash
mkdir -p ~/.opencode/hooks
npx -y -p @purpleraven/hits cat hooks/opencode_signal_watcher.sh > ~/.opencode/hooks/hits_signal_watcher.sh
chmod +x ~/.opencode/hooks/hits_signal_watcher.sh
```

Configure as a startup hook in your OpenCode settings.

## Signal Directory Structure

```
~/.hits/data/signals/
├── pending/                              ← Active signals
│   └── claude_to_opencode_20260414_143022_sig_fb5bd38c.json
└── consumed/                             ← Archived (auto-cleaned after 72h)
    └── opencode_to_claude_20260414_130000_sig_a1b2c3d4.json
```

## Signal JSON Format

```json
{
  "id": "sig_fb5bd38c",
  "sender": "claude",
  "recipient": "opencode",
  "signal_type": "session_end",
  "project_path": "/home/user/my-project",
  "summary": "JWT auth done, rate limiting remaining",
  "context": "Compressed checkpoint data...",
  "pending_items": ["Add rate limiting", "Configure CORS"],
  "priority": "high",
  "tags": ["checkpoint", "auto"],
  "created_at": "2026-04-14T14:30:22"
}
```

## Full Handover Flow

```
1. Claude session ends:
   → hits_auto_checkpoint()             # One call
     → records work log
     → generates checkpoint
     → sends signal to opencode

2. OpenCode session starts:
   → Hook auto-detects signal (injected via stderr)
   → hits_resume()                      # One call
     → loads checkpoint
     → checks signals
     → auto-consumes signals

3. OpenCode session ends:
   → hits_auto_checkpoint()
     → records work log
     → generates checkpoint
     → sends signal back to claude
```
