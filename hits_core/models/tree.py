"""Knowledge tree structure with Why-How-What hierarchy."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from .node import Node, NodeLayer


class KnowledgeTree(BaseModel):
    id: str = Field(..., description="Tree unique identifier")
    name: str = Field(..., description="Tree name")
    description: Optional[str] = Field(default=None, description="Tree description")
    
    root_ids: list[str] = Field(default_factory=list, description="Root node IDs (WHY layer)")
    nodes: dict[str, Node] = Field(default_factory=dict, description="All nodes by ID")
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node
        if node.is_root() and node.id not in self.root_ids:
            self.root_ids.append(node.id)
        elif node.parent_id and node.parent_id in self.nodes:
            self.nodes[node.parent_id].add_child(node.id)
    
    def remove_node(self, node_id: str) -> Optional[Node]:
        if node_id not in self.nodes:
            return None
        
        node = self.nodes.pop(node_id)
        
        if node_id in self.root_ids:
            self.root_ids.remove(node_id)
        
        if node.parent_id and node.parent_id in self.nodes:
            self.nodes[node.parent_id].remove_child(node_id)
        
        for child_id in node.children_ids[:]:
            self.remove_node(child_id)
        
        return node
    
    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)
    
    def get_children(self, node_id: str) -> list[Node]:
        node = self.get_node(node_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.children_ids if cid in self.nodes]
    
    def get_path(self, node_id: str) -> list[Node]:
        path = []
        current = self.get_node(node_id)
        while current:
            path.insert(0, current)
            current = self.get_node(current.parent_id) if current.parent_id else None
        return path
    
    def get_nodes_by_layer(self, layer: NodeLayer) -> list[Node]:
        return [n for n in self.nodes.values() if n.layer == layer]
    
    def get_negative_paths(self) -> list[Node]:
        return [n for n in self.nodes.values() if n.is_negative_path()]
    
    def total_tokens_saved(self) -> int:
        return sum(n.tokens_saved for n in self.nodes.values())
