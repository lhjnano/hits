"""API routes for task management."""

import json
import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from hits_core.auth.dependencies import require_auth

router = APIRouter()

TASKS_DIR = Path(os.environ.get("HITS_DATA_PATH", Path.home() / ".hits" / "data")) / "tasks"
SLACK_CONFIG_FILE = Path(os.environ.get("HITS_DATA_PATH", Path.home() / ".hits" / "data")) / "slack_config.json"


class TaskStart(BaseModel):
    """Start or resume working on a task — links it to a checkpoint."""
    pass


class TaskCreate(BaseModel):
    title: str
    project_path: str = ""
    project_name: str = ""
    priority: str = "medium"
    context: str = ""
    created_by: str = "manual"
    checkpoint_id: Optional[str] = None


class SlackChannelConfig(BaseModel):
    name: str
    webhook_url: str
    channel_id: Optional[str] = None


def _ensure_tasks_dir():
    TASKS_DIR.mkdir(parents=True, exist_ok=True)


def _get_current_env() -> dict:
    return {
        "hostname": platform.node(),
        "username": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
        "os": platform.system(),
    }


def _load_tasks() -> list[dict]:
    _ensure_tasks_dir()
    index_file = TASKS_DIR / "index.json"
    if not index_file.exists():
        return []
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_tasks(tasks: list[dict]) -> bool:
    _ensure_tasks_dir()
    index_file = TASKS_DIR / "index.json"
    try:
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2, default=str)
        return True
    except IOError:
        return False


def _load_slack_config() -> list[dict]:
    if not SLACK_CONFIG_FILE.exists():
        return []
    try:
        with open(SLACK_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_slack_config(channels: list[dict]) -> bool:
    SLACK_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(SLACK_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(channels, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


@router.get("/tasks")
async def list_tasks(
    project_path: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    _auth=Depends(require_auth),
):
    """List all tasks."""
    tasks = _load_tasks()
    
    if project_path:
        tasks = [t for t in tasks if t.get("project_path") == project_path]
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    
    return {"success": True, "data": tasks}


@router.post("/tasks")
async def create_task(
    body: TaskCreate,
    _auth=Depends(require_auth),
):
    """Create a new task."""
    task_id = f"task_{uuid4().hex[:8]}"
    current_env = _get_current_env()
    
    task = {
        "id": task_id,
        "title": body.title,
        "project_path": body.project_path,
        "project_name": body.project_name or (body.project_path.split("/")[-1] if body.project_path else ""),
        "priority": body.priority,
        "context": body.context,
        "source": "local",
        "slack_channel": None,
        "source_env": current_env,
        "environment_note": "",
        "created_by": body.created_by,
        "created_at": datetime.now().isoformat(),
        "status": "pending",
        "completed_at": None,
        "checkpoint_id": body.checkpoint_id,
        "exported_to": [],
    }
    
    tasks = _load_tasks()
    tasks.insert(0, task)
    _save_tasks(tasks)
    
    return {"success": True, "data": task}


@router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    body: dict,
    _auth=Depends(require_auth),
):
    """Update a task (status, title, etc)."""
    tasks = _load_tasks()
    
    for task in tasks:
        if task["id"] == task_id:
            if "status" in body:
                task["status"] = body["status"]
                if body["status"] == "done":
                    task["completed_at"] = datetime.now().isoformat()
            if "title" in body:
                task["title"] = body["title"]
            if "priority" in body:
                task["priority"] = body["priority"]
            if "context" in body:
                task["context"] = body["context"]
            
            _save_tasks(tasks)
            return {"success": True, "data": task}
    
    return {"success": False, "error": "Task not found"}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    _auth=Depends(require_auth),
):
    """Delete a task."""
    tasks = _load_tasks()
    new_tasks = [t for t in tasks if t["id"] != task_id]
    
    if len(new_tasks) == len(tasks):
        return {"success": False, "error": "Task not found"}
    
    _save_tasks(new_tasks)
    return {"success": True}


@router.post("/tasks/{task_id}/start")
async def start_task(
    task_id: str,
    _auth=Depends(require_auth),
):
    """Start or resume working on a task.
    
    Sets status to 'in_progress' and creates a checkpoint linked to this task.
    If the task already has a checkpoint, returns that checkpoint for resume.
    """
    from hits_core.models.checkpoint import Checkpoint, NextStep
    from hits_core.service.checkpoint_service import CheckpointService
    
    tasks = _load_tasks()
    task = None
    for t in tasks:
        if t["id"] == task_id:
            task = t
            break
    
    if not task:
        return {"success": False, "error": "Task not found"}
    
    # If already done, reopen
    if task["status"] == "done":
        task["status"] = "in_progress"
        task["completed_at"] = None
    
    cp_service = CheckpointService()
    project_path = task.get("project_path", "")
    
    # If already in_progress with a checkpoint, return it for resume
    if task["status"] == "in_progress" and task.get("checkpoint_id"):
        try:
            checkpoint = await cp_service.get_checkpoint(task["checkpoint_id"], project_path)
            if checkpoint:
                _save_tasks(tasks)
                return {
                    "success": True,
                    "data": {
                        "task": task,
                        "checkpoint": checkpoint.model_dump(),
                        "action": "resumed",
                    }
                }
        except Exception:
            pass  # Fall through to create new
    
    # Create a lightweight checkpoint directly (avoid auto_checkpoint's subprocess/git calls)
    checkpoint_id = f"cp_{uuid4().hex[:8]}"
    
    checkpoint = Checkpoint(
        id=checkpoint_id,
        purpose=task["title"],
        current_state=task.get("context", ""),
        completion_pct=0,
        next_steps=[],
        required_context=[],
        decisions_made=[],
        blocks=[],
        files_delta=[],
        performer="manual",
        project_path=project_path,
        git_branch=None,
        created_at=datetime.now().isoformat(),
        commands_run=[],
        resume_command=f"npx @purpleraven/hits resume --project {project_path}" if project_path else "",
    )
    
    # Save checkpoint
    try:
        await cp_service._save_checkpoint(checkpoint)
    except Exception:
        pass  # Non-critical — task still starts
    
    # Link to task
    task["status"] = "in_progress"
    task["checkpoint_id"] = checkpoint_id
    _save_tasks(tasks)
    
    return {
        "success": True,
        "data": {
            "task": task,
            "checkpoint": checkpoint.model_dump(),
            "action": "started",
        }
    }


@router.post("/tasks/{task_id}/export")
async def export_task_to_slack(
    task_id: str,
    body: dict,
    _auth=Depends(require_auth),
):
    """Export a task to a Slack channel."""
    import urllib.request
    
    channel_name = body.get("channel", "")
    if not channel_name:
        return {"success": False, "error": "Channel name required"}
    
    # Find webhook URL
    channels = _load_slack_config()
    webhook_url = None
    for ch in channels:
        if ch["name"] == channel_name:
            webhook_url = ch["webhook_url"]
            break
    
    if not webhook_url:
        return {"success": False, "error": f"Channel '{channel_name}' not configured"}
    
    # Find task
    tasks = _load_tasks()
    task = None
    for t in tasks:
        if t["id"] == task_id:
            task = t
            break
    
    if not task:
        return {"success": False, "error": "Task not found"}
    
    # Build Slack message
    priority_emoji = {"critical": "🔴", "high": "🟡", "medium": "🔵", "low": "⚪"}.get(task["priority"], "🔵")
    lines = [
        f"{priority_emoji} *{task['title']}*",
    ]
    if task.get("project_name"):
        lines.append(f"📂 {task['project_name']}")
    if task.get("context"):
        lines.append(f"📝 {task['context']}")
    src_env = task.get("source_env", {})
    lines.append(f"👤 {task.get('created_by', '?')} · {src_env.get('hostname', 'local')}")
    lines.append(f"🆔 `{task['id']}`")
    
    payload = {
        "text": "\n".join(lines),
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Priority: {task['priority']} | ID: {task['id']}"}]},
        ]
    }
    
    # Send to Slack
    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                # Mark as exported
                if channel_name not in task.get("exported_to", []):
                    task.setdefault("exported_to", []).append(channel_name)
                    _save_tasks(tasks)
                return {"success": True, "data": {"exported_to": channel_name}}
            else:
                return {"success": False, "error": f"Slack returned {resp.status}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/tasks/slack/channels")
async def list_slack_channels(_auth=Depends(require_auth)):
    """List configured Slack channels."""
    channels = _load_slack_config()
    return {"success": True, "data": channels}


@router.post("/tasks/slack/channels")
async def add_slack_channel(
    body: dict,
    _auth=Depends(require_auth),
):
    """Add a Slack channel configuration."""
    name = body.get("name", "")
    webhook_url = body.get("webhook_url", "")
    
    if not name or not webhook_url:
        return {"success": False, "error": "name and webhook_url required"}
    
    channels = _load_slack_config()
    
    # Update existing or add new
    for ch in channels:
        if ch["name"] == name:
            ch["webhook_url"] = webhook_url
            _save_slack_config(channels)
            return {"success": True, "data": ch}
    
    new_ch = {
        "name": name, 
        "webhook_url": webhook_url,
        "bot_token": body.get("bot_token", ""),
        "channel_id": body.get("channel_id", ""),
    }
    channels.append(new_ch)
    _save_slack_config(channels)
    
    return {"success": True, "data": new_ch}


@router.delete("/tasks/slack/channels/{name}")
async def delete_slack_channel(
    name: str,
    _auth=Depends(require_auth),
):
    """Remove a Slack channel configuration."""
    channels = _load_slack_config()
    new_channels = [ch for ch in channels if ch["name"] != name]
    _save_slack_config(new_channels)
    return {"success": True}


@router.post("/tasks/slack/import")
async def import_from_slack(
    body: dict,
    _auth=Depends(require_auth),
):
    """Import tasks from Slack channel messages.
    
    NOTE: This requires a Slack Bot Token (not webhook).
    Webhooks are send-only. For reading, use Slack's conversations.history API.
    
    For now, this is a placeholder that demonstrates the structure.
    Full implementation requires Slack Bot OAuth token setup.
    """
    channel_name = body.get("channel", "")
    limit = body.get("limit", 10)
    
    channels = _load_slack_config()
    channel_config = None
    for ch in channels:
        if ch["name"] == channel_name:
            channel_config = ch
            break
    
    if not channel_config:
        return {"success": False, "error": f"Channel '{channel_name}' not configured"}
    
    bot_token = channel_config.get("bot_token")
    if not bot_token:
        return {
            "success": False, 
            "error": "Slack Bot Token required for reading. Add 'bot_token' to channel config.",
            "hint": "Go to api.slack.com/apps → Create App → OAuth & Permissions → Add 'channels:history' scope → Install → Copy Bot Token",
        }
    
    # Fetch messages from Slack
    import urllib.request
    
    channel_id = channel_config.get("channel_id", "")
    if not channel_id:
        return {"success": False, "error": "channel_id required for reading messages"}
    
    try:
        url = f"https://slack.com/api/conversations.history?channel={channel_id}&limit={limit}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {bot_token}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        if not data.get("ok"):
            return {"success": False, "error": data.get("error", "Slack API error")}
        
        # Convert messages to tasks
        current_env = _get_current_env()
        existing_tasks = _load_tasks()
        existing_ids = {t["id"] for t in existing_tasks}
        
        imported = []
        for msg in data.get("messages", []):
            text = msg.get("text", "")
            if not text or len(text) < 5:
                continue
            
            # Skip bot messages that are our own exports (they have ID markers)
            import re
            id_match = re.search(r'🆔 `?(task_\w+)`?', text)
            if id_match and id_match.group(1) in existing_ids:
                continue
            
            task_id = f"task_{uuid4().hex[:8]}"
            
            # Parse priority from emoji
            priority = "medium"
            if "🔴" in text:
                priority = "critical"
            elif "🟡" in text:
                priority = "high"
            elif "⚪" in text:
                priority = "low"
            
            # Clean title (remove emoji markers)
            title = re.sub(r'[🔴🟡🔵⚪🟢📂📝👤🆔]', '', text).strip()
            title = re.sub(r'\*([^*]+)\*', r'\1', title)  # Remove bold
            title_lines = [l.strip() for l in title.split('\n') if l.strip()]
            title = title_lines[0] if title_lines else text[:80]
            
            task = {
                "id": task_id,
                "title": title[:120],
                "project_path": "",
                "project_name": "",
                "priority": priority,
                "context": "\n".join(title_lines[1:3]) if len(title_lines) > 1 else "",
                "source": "slack",
                "slack_channel": channel_name,
                "source_env": {
                    "hostname": "remote",
                    "source": f"slack:{channel_name}",
                },
                "environment_note": f"Slack {channel_name}에서 가져옴",
                "created_by": "slack-import",
                "created_at": datetime.now().isoformat(),
                "status": "pending",
                "completed_at": None,
                "checkpoint_id": None,
                "exported_to": [],
            }
            
            existing_tasks.insert(0, task)
            imported.append(task)
        
        if imported:
            _save_tasks(existing_tasks)
        
        return {"success": True, "data": {"imported": len(imported), "tasks": imported}}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
