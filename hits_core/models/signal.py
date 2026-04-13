"""Signal model for cross-tool handover notifications."""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class SignalStatus(str, Enum):
    PENDING = "pending"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class SignalType(str, Enum):
    SESSION_END = "session_end"       # AI 세션 종료, 인수인계 요청
    TASK_READY = "task_ready"         # 특정 작업이 준비됨
    QUESTION = "question"             # 다른 도구에 질문
    URGENT = "urgent"                 # 긴급 알림


# 지원하는 AI 도구 식별자
VALID_PERFORMERS = {"claude", "opencode", "cursor", "copilot", "manual", "unknown"}


class HandoverSignal(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(..., description="Unique signal ID (sig_xxxxxxxx)")
    status: SignalStatus = Field(default=SignalStatus.PENDING)

    # 송수신자
    sender: str = Field(..., description="AI tool that sent this signal (claude/opencode/...)")
    recipient: str = Field(default="any", description="Target AI tool, or 'any' for broadcast")

    # 내용
    signal_type: SignalType = Field(default=SignalType.SESSION_END)
    project_path: Optional[str] = Field(default=None, description="Project absolute path")
    summary: str = Field(..., description="Brief summary of what was done / what needs to be done")
    context: Optional[str] = Field(default=None, description="Detailed context for the next session")
    pending_items: list[str] = Field(default_factory=list, description="List of unfinished tasks")
    tags: list[str] = Field(default_factory=list)

    # 메타
    priority: str = Field(default="normal", description="normal | high | urgent")
    handover_available: bool = Field(default=True, description="Whether full handover data exists in HITS")
    created_at: datetime = Field(default_factory=datetime.now)
    consumed_at: Optional[datetime] = Field(default=None)
    consumed_by: Optional[str] = Field(default=None, description="Which tool consumed this signal")
    expires_at: Optional[datetime] = Field(default=None, description="Auto-expire time (optional)")

    def filename(self) -> str:
        """Generate filename for this signal."""
        ts = self.created_at.strftime("%Y%m%d_%H%M%S")
        return f"{self.sender}_to_{self.recipient}_{ts}_{self.id}.json"

    def is_expired(self) -> bool:
        if self.expires_at and datetime.now() > self.expires_at:
            return True
        return self.status == SignalStatus.EXPIRED
