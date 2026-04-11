"""Tree management service."""

from typing import Optional
from ..models.tree import KnowledgeTree
from ..models.node import Node, NodeLayer
from ..models.workflow import Workflow
from ..storage.base import BaseStorage
from ..storage.file_store import FileStorage
from ..ai.compressor import SemanticCompressor


class TreeService:
    def __init__(self, storage: Optional[BaseStorage] = None):
        self.storage = storage or FileStorage()
        self.compressor = SemanticCompressor()
    
    async def create_tree(
        self,
        tree_id: str,
        name: str,
        description: Optional[str] = None,
    ) -> KnowledgeTree:
        tree = KnowledgeTree(
            id=tree_id,
            name=name,
            description=description,
        )
        await self.storage.save_tree(tree)
        return tree
    
    async def get_tree(self, tree_id: str) -> Optional[KnowledgeTree]:
        return await self.storage.load_tree(tree_id)
    
    async def save_tree(self, tree: KnowledgeTree) -> bool:
        return await self.storage.save_tree(tree)
    
    async def delete_tree(self, tree_id: str) -> bool:
        return await self.storage.delete_tree(tree_id)
    
    async def list_trees(self) -> list[str]:
        return await self.storage.list_trees()
    
    async def add_node(
        self,
        tree_id: str,
        node: Node,
        compress: bool = True,
    ) -> bool:
        tree = await self.get_tree(tree_id)
        if not tree:
            return False
        
        if compress:
            self.compressor.compress_node(node)
        
        tree.add_node(node)
        return await self.save_tree(tree)
    
    async def remove_node(self, tree_id: str, node_id: str) -> Optional[Node]:
        tree = await self.get_tree(tree_id)
        if not tree:
            return None
        
        node = tree.remove_node(node_id)
        if node:
            await self.save_tree(tree)
        return node
    
    async def get_node(self, tree_id: str, node_id: str) -> Optional[Node]:
        tree = await self.get_tree(tree_id)
        if not tree:
            return None
        return tree.get_node(node_id)
    
    async def get_children(self, tree_id: str, node_id: str) -> list[Node]:
        tree = await self.get_tree(tree_id)
        if not tree:
            return []
        return tree.get_children(node_id)
    
    async def get_node_path(self, tree_id: str, node_id: str) -> list[Node]:
        tree = await self.get_tree(tree_id)
        if not tree:
            return []
        return tree.get_path(node_id)
    
    async def get_negative_paths(self, tree_id: str) -> list[Node]:
        tree = await self.get_tree(tree_id)
        if not tree:
            return []
        return tree.get_negative_paths()
    
    async def get_statistics(self, tree_id: str) -> dict:
        tree = await self.get_tree(tree_id)
        if not tree:
            return {}
        
        return {
            "total_nodes": len(tree.nodes),
            "why_nodes": len(tree.get_nodes_by_layer(NodeLayer.WHY)),
            "how_nodes": len(tree.get_nodes_by_layer(NodeLayer.HOW)),
            "what_nodes": len(tree.get_nodes_by_layer(NodeLayer.WHAT)),
            "negative_paths": len(tree.get_negative_paths()),
            "tokens_saved": tree.total_tokens_saved(),
        }
