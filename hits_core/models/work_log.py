"""Work log model for recording user activities."""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class WorkLogSource(str, Enum):
    GIT = "git"
    SHELL = "shell"
    LINK_CLICK = "link_click"
    SHELL_EXEC = "shell_exec"
    AI_SESSION = "ai_session"
    MANUAL = "manual"
    BROWSER_HISTORY = "browser_history"


class WorkLogResultType(str, Enum):
    COMMIT = "commit"
    PR = "pr"
    FILE = "file"
    URL = "url"
    COMMAND = "command"
    NONE = "none"
    AI_RESPONSE = "ai_response"


class WorkLog(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    id: str = Field(..., description="Unique log identifier")
    
    source: WorkLogSource = Field(..., description="Where this log came from")
    
    request_text: Optional[str] = Field(default=None, description="Original request/prompt")
    request_by: Optional[str] = Field(default=None, description="Who made the request")
    
    performed_by: str = Field(..., description="Who/what performed the action")
    performed_at: datetime = Field(default_factory=datetime.now)
    
    result_type: WorkLogResultType = Field(default=WorkLogResultType.NONE)
    result_ref: Optional[str] = Field(default=None, description="Reference to result (commit hash, URL, etc)")
    result_data: Optional[dict] = Field(default=None, description="Additional result metadata")
    
    context: Optional[str] = Field(default=None, description="Why this action was taken")
    tags: list[str] = Field(default_factory=list, description="Tags for search")
    
    project_path: Optional[str] = Field(default=None, description="Project directory if applicable")
    
    node_id: Optional[str] = Field(default=None, description="Linked knowledge node ID")
    category: Optional[str] = Field(default=None, description="Category name from HITS UI")
    
    created_at: datetime = Field(default_factory=datetime.now)
    
    def has_result(self) -> bool:
        return self.result_type != WorkLogResultType.NONE and self.result_ref is not None
    
    def get_summary(self) -> str:
        if self.request_text:
            return self.request_text[:100]
        if self.result_ref:
            return f"[{self.result_type}] {self.result_ref[:50]}"
        return f"[{self.source}] {self.performed_by}"
