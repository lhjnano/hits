"""Redis storage backend with ReJSON support."""

import json
from typing import Optional
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

from .base import BaseStorage
from ..models.tree import KnowledgeTree
from ..models.workflow import Workflow


class RedisStorage(BaseStorage):
    TREE_PREFIX = "hits:tree:"
    WORKFLOW_PREFIX = "hits:workflow:"
    TREE_LIST_KEY = "hits:trees"
    WORKFLOW_LIST_KEY = "hits:workflows"
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        pool: Optional[ConnectionPool] = None,
    ):
        if pool:
            self.client = redis.Redis(connection_pool=pool)
        else:
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
            )
    
    def _tree_key(self, tree_id: str) -> str:
        return f"{self.TREE_PREFIX}{tree_id}"
    
    def _workflow_key(self, workflow_id: str) -> str:
        return f"{self.WORKFLOW_PREFIX}{workflow_id}"
    
    async def ping(self) -> bool:
        try:
            return await self.client.ping()
        except redis.ConnectionError:
            return False
    
    async def save_tree(self, tree: KnowledgeTree) -> bool:
        try:
            key = self._tree_key(tree.id)
            data = tree.model_dump_json()
            await self.client.set(key, data)
            await self.client.sadd(self.TREE_LIST_KEY, tree.id)
            return True
        except Exception:
            return False
    
    async def load_tree(self, tree_id: str) -> Optional[KnowledgeTree]:
        try:
            key = self._tree_key(tree_id)
            data = await self.client.get(key)
            if not data:
                return None
            return KnowledgeTree.model_validate_json(data)
        except Exception:
            return None
    
    async def delete_tree(self, tree_id: str) -> bool:
        try:
            key = self._tree_key(tree_id)
            await self.client.delete(key)
            await self.client.srem(self.TREE_LIST_KEY, tree_id)
            return True
        except Exception:
            return False
    
    async def list_trees(self) -> list[str]:
        try:
            members = await self.client.smembers(self.TREE_LIST_KEY)
            return list(members) if members else []
        except Exception:
            return []
    
    async def save_workflow(self, workflow: Workflow) -> bool:
        try:
            key = self._workflow_key(workflow.id)
            data = workflow.model_dump_json()
            await self.client.set(key, data)
            await self.client.sadd(self.WORKFLOW_LIST_KEY, workflow.id)
            return True
        except Exception:
            return False
    
    async def load_workflow(self, workflow_id: str) -> Optional[Workflow]:
        try:
            key = self._workflow_key(workflow_id)
            data = await self.client.get(key)
            if not data:
                return None
            return Workflow.model_validate_json(data)
        except Exception:
            return None
    
    async def delete_workflow(self, workflow_id: str) -> bool:
        try:
            key = self._workflow_key(workflow_id)
            await self.client.delete(key)
            await self.client.srem(self.WORKFLOW_LIST_KEY, workflow_id)
            return True
        except Exception:
            return False
    
    async def list_workflows(self) -> list[str]:
        try:
            members = await self.client.smembers(self.WORKFLOW_LIST_KEY)
            return list(members) if members else []
        except Exception:
            return []
    
    async def close(self) -> None:
        await self.client.aclose()
