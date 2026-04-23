"""Knowledge category API routes.

These routes expose the KnowledgeService (config-based categories)
through the API, enabling the web UI to manage knowledge categories
and their nodes per-project.

Endpoints:
- GET    /api/knowledge/categories        → List all categories with nodes
- POST   /api/knowledge/category          → Create a new category
- PUT    /api/knowledge/category/{name}   → Update a category
- DELETE /api/knowledge/category/{name}   → Delete a category
- POST   /api/knowledge/category/{name}/nodes      → Add node
- PUT    /api/knowledge/category/{name}/nodes/{idx} → Update node
- DELETE /api/knowledge/category/{name}/nodes/{idx} → Delete node
"""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from hits_core.service.knowledge_service import KnowledgeService, KnowledgeNode
from hits_core.service.knowledge_extractor import KnowledgeExtractor
from hits_core.auth.dependencies import require_auth


router = APIRouter()

_service: Optional[KnowledgeService] = None


def get_service() -> KnowledgeService:
    global _service
    if _service is None:
        _service = KnowledgeService()
    return _service


class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


# --- Models ---

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    icon: str = Field("📁", max_length=4)


class CategoryUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    icon: Optional[str] = Field(None, max_length=4)


class NodeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    layer: str = Field("what", pattern=r"^(why|how|what)$")
    type: str = Field("url", pattern=r"^(url|shell)$")
    action: str = Field("")
    negative_path: bool = Field(False)


class NodeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    layer: Optional[str] = Field(None, pattern=r"^(why|how|what)$")
    type: Optional[str] = Field(None, pattern=r"^(url|shell)$")
    action: Optional[str] = None
    negative_path: Optional[bool] = None


# --- Endpoints ---

@router.get("/knowledge/categories", response_model=APIResponse)
async def list_categories(user: dict = Depends(require_auth)):
    """List all knowledge categories with their nodes."""
    service = get_service()
    categories = service.list_categories()
    return APIResponse(
        success=True,
        data=[cat.to_dict() for cat in categories],
    )


@router.post("/knowledge/category", response_model=APIResponse)
async def create_category(body: CategoryCreate, user: dict = Depends(require_auth)):
    """Create a new knowledge category."""
    service = get_service()
    cat = service.add_category(body.name, body.icon)
    if cat is None:
        return APIResponse(success=False, error="Category already exists")
    return APIResponse(success=True, data=cat.to_dict())


@router.put("/knowledge/category/{category_name}", response_model=APIResponse)
async def update_category(
    category_name: str,
    body: CategoryUpdate,
    user: dict = Depends(require_auth),
):
    """Update a category's name and/or icon."""
    service = get_service()
    success = service.update_category(category_name, body.name, body.icon)
    if not success:
        return APIResponse(success=False, error="Category not found")
    return APIResponse(success=True, data={"name": body.name})


@router.delete("/knowledge/category/{category_name}", response_model=APIResponse)
async def delete_category(category_name: str, user: dict = Depends(require_auth)):
    """Delete a category and all its nodes."""
    service = get_service()
    success = service.delete_category(category_name)
    if not success:
        return APIResponse(success=False, error="Category not found")
    return APIResponse(success=True, data={"deleted": category_name})


@router.post("/knowledge/category/{category_name}/nodes", response_model=APIResponse)
async def add_node(
    category_name: str,
    body: NodeCreate,
    user: dict = Depends(require_auth),
):
    """Add a node to a category."""
    service = get_service()
    node = KnowledgeNode(
        name=body.name,
        layer=body.layer,
        type=body.type,
        action=body.action,
        negative_path=body.negative_path,
    )
    success = service.add_node(category_name, node)
    if not success:
        return APIResponse(success=False, error="Category not found")
    return APIResponse(success=True, data=node.to_dict())


@router.put("/knowledge/category/{category_name}/nodes/{node_index}", response_model=APIResponse)
async def update_node(
    category_name: str,
    node_index: int,
    body: NodeUpdate,
    user: dict = Depends(require_auth),
):
    """Update a specific node in a category."""
    service = get_service()
    existing = service.get_node(category_name, node_index)
    if existing is None:
        return APIResponse(success=False, error="Node not found")

    updated = KnowledgeNode(
        name=body.name or existing.name,
        layer=body.layer or existing.layer,
        type=body.type or existing.type,
        action=body.action if body.action is not None else existing.action,
        negative_path=body.negative_path if body.negative_path is not None else existing.negative_path,
    )
    success = service.update_node(category_name, node_index, updated)
    if not success:
        return APIResponse(success=False, error="Failed to update node")
    return APIResponse(success=True, data=updated.to_dict())


@router.delete("/knowledge/category/{category_name}/nodes/{node_index}", response_model=APIResponse)
async def delete_node(
    category_name: str,
    node_index: int,
    user: dict = Depends(require_auth),
):
    """Delete a node from a category."""
    service = get_service()
    success = service.delete_node(category_name, node_index)
    if not success:
        return APIResponse(success=False, error="Node not found")
    return APIResponse(success=True, data={"deleted_index": node_index})


# --- Auto-extract from work logs ---

class ExtractRequest(BaseModel):
    log_id: Optional[str] = Field(None, description="Specific work log ID to extract from")
    project_path: Optional[str] = Field(None, description="Extract from latest checkpoint for this project")
    extract_all: bool = Field(False, description="Extract from all unprocessed work logs")


@router.post("/knowledge/extract", response_model=APIResponse)
async def extract_knowledge(body: ExtractRequest = ExtractRequest()):
    """Extract knowledge from work logs / checkpoints and add to knowledge tree.

    This endpoint can be called:
    - With log_id: extract from a specific work log
    - With project_path: extract from latest checkpoint
    - With extract_all: process all unprocessed work logs

    No auth required — called by Stop hooks.
    """
    extractor = KnowledgeExtractor()

    if body.log_id:
        count = extractor.extract_from_work_log(body.log_id)
        return APIResponse(success=True, data={"log_id": body.log_id, "nodes_added": count})

    if body.project_path:
        count = extractor.extract_from_checkpoint(body.project_path)
        return APIResponse(success=True, data={"project_path": body.project_path, "nodes_added": count})

    if body.extract_all:
        results = extractor.extract_all_unprocessed()
        total = sum(results.values())
        return APIResponse(success=True, data={"total_nodes_added": total, "by_project": results})

    return APIResponse(success=False, error="Provide log_id, project_path, or extract_all=true")
