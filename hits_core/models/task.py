"""Task model - lightweight actionable work items.

Tasks are the simplest unit of work in HITS. Unlike checkpoints (which capture
full session state), tasks are just "something to do" that can be:
- Created manually or by AI
- Exported to Slack channels
- Imported from Slack channels (from other machines/environments)
- Resumed with environment-awareness (path mapping)
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class TaskSource:
    LOCAL = "local"
    SLACK = "slack"
    MANUAL = "manual"
    CHECKPOINT = "checkpoint"


class Task(BaseModel):
    """A single actionable work item."""
    
    id: str = Field(..., description="Unique task ID")
    title: str = Field(..., description="What to do")
    project_path: str = Field(default="", description="Project path (may differ from local)")
    project_name: str = Field(default="", description="Display name")
    priority: str = Field(default="medium", description="critical/high/medium/low")
    context: str = Field(default="", description="Additional details")
    
    # Source tracking
    source: str = Field(default=TaskSource.LOCAL, description="Where this task came from")
    slack_channel: Optional[str] = Field(default=None, description="Slack channel if source=slack")
    
    # Environment awareness
    source_env: dict = Field(default_factory=dict, description="Original environment {hostname, username, os}")
    environment_note: str = Field(default="", description="Auto-generated env diff note")
    
    # Creator
    created_by: str = Field(default="manual", description="Who created (manual/claude/opencode/etc)")
    created_at: datetime = Field(default_factory=datetime.now)
    
    # Status
    status: str = Field(default="pending", description="pending/done/skipped")
    completed_at: Optional[datetime] = Field(default=None)
    
    # Optional link to checkpoint
    checkpoint_id: Optional[str] = Field(default=None)
    
    # Export tracking
    exported_to: list[str] = Field(default_factory=list, description="Slack channels exported to")
    
    def is_remote(self) -> bool:
        """Check if this task came from another environment."""
        return self.source != TaskSource.LOCAL and bool(self.source_env)
    
    def env_diff(self, current_hostname: str = "", current_username: str = "") -> str:
        """Generate environment difference note."""
        if not self.source_env:
            return ""
        
        parts = []
        src_host = self.source_env.get("hostname", "")
        src_user = self.source_env.get("username", "")
        
        if src_host and src_host != current_hostname:
            parts.append(f"원본 머신: {src_host}")
        if src_user and src_user != current_username:
            parts.append(f"원본 사용자: {src_user}")
        
        return " / ".join(parts) if parts else ""
    
    def to_slack_message(self) -> dict:
        """Convert to Slack message format."""
        priority_emoji = {"critical": "🔴", "high": "🟡", "medium": "🔵", "low": "⚪"}.get(self.priority, "🔵")
        
        text_lines = [
            f"{priority_emoji} *{self.title}*",
        ]
        
        if self.project_name:
            text_lines.append(f"📂 {self.project_name}")
        
        if self.context:
            text_lines.append(f"📝 {self.context}")
        
        text_lines.append(f"👤 {self.created_by} · {self.source_env.get('hostname', 'local')}")
        text_lines.append(f"🆔 `{self.id}`")
        
        return {
            "text": "\n".join(text_lines),
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "\n".join(text_lines)
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Priority: {self.priority} | Project: {self.project_name or '-'} | ID: {self.id}"
                        }
                    ]
                }
            ]
        }
