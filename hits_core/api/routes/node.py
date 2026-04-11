from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from hits_core.service.tree_service import TreeService
from hits_core.models.node import Node, NodeLayer, NodeType


router = APIRouter()

_service: Optional[TreeService] = None


def get_service() -> TreeService:
    global _service
    if _service is None:
        _service = TreeService()
    return _service


class NodeCreate(BaseModel):
    tree_id: str
    layer: str
    title: str
    description: Optional[str] = None
    node_type: Optional[str] = "standard"
    parent_id: Optional[str] = None
    action: Optional[str] = None
    action_type: Optional[str] = None
    metadata: Optional[dict] = None


class NodeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    node_type: Optional[str] = None
    action: Optional[str] = None
    action_type: Optional[str] = None
    metadata: Optional[dict] = None


class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@router.post("/node", response_model=APIResponse)
async def create_node(body: NodeCreate):
    service = get_service()
    
    tree = await service.get_tree(body.tree_id)
    if tree is None:
        return APIResponse(success=False, error="Tree not found")
    
    node = Node(
        id=str(uuid4())[:8],
        layer=NodeLayer(body.layer),
        title=body.title,
        description=body.description,
        node_type=NodeType(body.node_type or "standard"),
        parent_id=body.parent_id,
        action=body.action,
        action_type=body.action_type,
        metadata=body.metadata or {},
    )
    
    success = await service.add_node(body.tree_id, node)
    if not success:
        return APIResponse(success=False, error="Failed to add node")
    
    return APIResponse(success=True, data=node.model_dump())


@router.put("/node/{node_id}", response_model=APIResponse)
async def update_node(
    node_id: str,
    tree_id: str = Query(...),
    body: NodeUpdate = None,
):
    service = get_service()
    
    node = await service.get_node(tree_id, node_id)
    if node is None:
        return APIResponse(success=False, error="Node not found")
    
    if body.title is not None:
        node.title = body.title
    if body.description is not None:
        node.description = body.description
    if body.node_type is not None:
        node.node_type = NodeType(body.node_type)
    if body.action is not None:
        node.action = body.action
    if body.action_type is not None:
        node.action_type = body.action_type
    if body.metadata is not None:
        node.metadata = body.metadata
    
    tree = await service.get_tree(tree_id)
    if tree:
        tree.nodes[node_id] = node
        await service.save_tree(tree)
    
    return APIResponse(success=True, data=node.model_dump())


@router.delete("/node/{node_id}", response_model=APIResponse)
async def delete_node(
    node_id: str,
    tree_id: str = Query(...),
):
    service = get_service()
    
    node = await service.remove_node(tree_id, node_id)
    if node is None:
        return APIResponse(success=False, error="Node not found or failed to delete")
    
    return APIResponse(success=True, data={"id": node_id})
