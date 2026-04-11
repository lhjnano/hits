"""Workflow model for causal relationships between nodes."""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class StepType(str, Enum):
    TRIGGER = "trigger"
    DECISION = "decision"
    ACTION = "action"
    OUTCOME = "outcome"
    FAILURE = "failure"


class WorkflowStep(BaseModel):
    id: str = Field(..., description="Step unique identifier")
    name: str = Field(..., description="Step name")
    step_type: StepType = Field(default=StepType.ACTION, description="Step type")
    node_id: Optional[str] = Field(default=None, description="Linked knowledge node ID")
    description: Optional[str] = Field(default=None, description="Step description")
    
    next_steps: list[str] = Field(default_factory=list, description="Next step IDs")
    condition: Optional[str] = Field(default=None, description="Condition for branching")
    
    estimated_tokens: int = Field(default=0, description="Estimated tokens for this step")
    
    class Config:
        use_enum_values = True


class Workflow(BaseModel):
    id: str = Field(..., description="Workflow unique identifier")
    name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(default=None, description="Workflow description")
    
    entry_step_id: Optional[str] = Field(default=None, description="Entry point step ID")
    steps: dict[str, WorkflowStep] = Field(default_factory=dict, description="All steps by ID")
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def add_step(self, step: WorkflowStep, is_entry: bool = False) -> None:
        self.steps[step.id] = step
        if is_entry or not self.entry_step_id:
            self.entry_step_id = step.id
    
    def remove_step(self, step_id: str) -> Optional[WorkflowStep]:
        if step_id not in self.steps:
            return None
        
        step = self.steps.pop(step_id)
        
        if self.entry_step_id == step_id:
            self.entry_step_id = None
        
        for s in self.steps.values():
            if step_id in s.next_steps:
                s.next_steps.remove(step_id)
        
        return step
    
    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        return self.steps.get(step_id)
    
    def get_next_steps(self, step_id: str) -> list[WorkflowStep]:
        step = self.get_step(step_id)
        if not step:
            return []
        return [self.steps[sid] for sid in step.next_steps if sid in self.steps]
    
    def get_execution_order(self) -> list[WorkflowStep]:
        if not self.entry_step_id:
            return []
        
        visited = set()
        order = []
        
        def dfs(step_id: str):
            if step_id in visited or step_id not in self.steps:
                return
            visited.add(step_id)
            order.append(self.steps[step_id])
            for next_id in self.steps[step_id].next_steps:
                dfs(next_id)
        
        dfs(self.entry_step_id)
        return order
    
    def total_estimated_tokens(self) -> int:
        return sum(s.estimated_tokens for s in self.steps.values())
