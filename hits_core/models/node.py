"""Node entity model for knowledge tree."""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class NodeLayer(str, Enum):
    WHY = "why"
    HOW = "how"
    WHAT = "what"


class NodeType(str, Enum):
    STANDARD = "standard"
    NEGATIVE_PATH = "negative_path"
    DECISION = "decision"
    ACTION = "action"


class Node(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    id: str = Field(..., description="Unique node identifier")
    layer: NodeLayer = Field(..., description="Tree layer (why/how/what)")
    title: str = Field(..., description="Node display title")
    description: Optional[str] = Field(default=None, description="Detailed description")
    node_type: NodeType = Field(default=NodeType.STANDARD, description="Node type")
    
    parent_id: Optional[str] = Field(default=None, description="Parent node ID")
    children_ids: list[str] = Field(default_factory=list, description="Child node IDs")
    
    action: Optional[str] = Field(default=None, description="Executable action (URL, command, etc.)")
    action_type: Optional[str] = Field(default=None, description="Action type: url, shell, app")
    
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    tokens_saved: int = Field(default=0, description="Estimated tokens saved by compression")
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def is_root(self) -> bool:
        return self.parent_id is None
    
    def is_negative_path(self) -> bool:
        return self.node_type == NodeType.NEGATIVE_PATH
    
    def add_child(self, child_id: str) -> None:
        if child_id not in self.children_ids:
            self.children_ids.append(child_id)
    
    def remove_child(self, child_id: str) -> None:
        if child_id in self.children_ids:
            self.children_ids.remove(child_id)
