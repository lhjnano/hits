from datetime import datetime
from typing import Optional, Any
from uuid import uuid4

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from hits_core.storage.file_store import FileStorage
from hits_core.models.work_log import WorkLog, WorkLogSource, WorkLogResultType


router = APIRouter()

_storage: Optional[FileStorage] = None


def get_storage() -> FileStorage:
    global _storage
    if _storage is None:
        _storage = FileStorage()
    return _storage


class WorkLogCreate(BaseModel):
    source: str
    performed_by: str
    request_text: str = Field(..., min_length=1, description="Summary of work performed")
    request_by: Optional[str] = None
    result_type: Optional[str] = "none"
    result_ref: Optional[str] = None
    result_data: Optional[dict] = None
    context: Optional[str] = None
    tags: Optional[list[str]] = None
    project_path: Optional[str] = None
    node_id: Optional[str] = None
    category: Optional[str] = None


class WorkLogUpdate(BaseModel):
    context: Optional[str] = None
    tags: Optional[list[str]] = None
    category: Optional[str] = None
    node_id: Optional[str] = None


class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@router.post("/work-log", response_model=APIResponse)
async def create_work_log(body: WorkLogCreate):
    storage = get_storage()
    
    log = WorkLog(
        id=str(uuid4())[:8],
        source=WorkLogSource(body.source),
        performed_by=body.performed_by,
        request_text=body.request_text,
        request_by=body.request_by,
        result_type=WorkLogResultType(body.result_type or "none"),
        result_ref=body.result_ref,
        result_data=body.result_data,
        context=body.context,
        tags=body.tags or [],
        project_path=body.project_path,
        node_id=body.node_id,
        category=body.category,
    )
    
    success = await storage.save_work_log(log)
    if not success:
        return APIResponse(success=False, error="Failed to save work log")
    
    return APIResponse(success=True, data=log.model_dump())


@router.get("/work-log/{log_id}", response_model=APIResponse)
async def get_work_log(log_id: str):
    storage = get_storage()
    log = await storage.load_work_log(log_id)
    
    if log is None:
        return APIResponse(success=False, error="Work log not found")
    
    return APIResponse(success=True, data=log.model_dump())


@router.put("/work-log/{log_id}", response_model=APIResponse)
async def update_work_log(log_id: str, body: WorkLogUpdate):
    storage = get_storage()
    log = await storage.load_work_log(log_id)
    
    if log is None:
        return APIResponse(success=False, error="Work log not found")
    
    if body.context is not None:
        log.context = body.context
    if body.tags is not None:
        log.tags = body.tags
    if body.category is not None:
        log.category = body.category
    if body.node_id is not None:
        log.node_id = body.node_id
    
    success = await storage.save_work_log(log)
    if not success:
        return APIResponse(success=False, error="Failed to update work log")
    
    return APIResponse(success=True, data=log.model_dump())


@router.delete("/work-log/{log_id}", response_model=APIResponse)
async def delete_work_log(log_id: str):
    storage = get_storage()
    success = await storage.delete_work_log(log_id)
    
    if not success:
        return APIResponse(success=False, error="Failed to delete work log")
    
    return APIResponse(success=True, data={"id": log_id})


@router.get("/work-logs", response_model=APIResponse)
async def list_work_logs(
    source: Optional[str] = Query(None),
    performed_by: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    project_path: Optional[str] = Query(None, description="Filter by project path"),
    limit: int = Query(100, ge=1, le=1000),
):
    storage = get_storage()
    
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            return APIResponse(success=False, error="Invalid since format. Use ISO format.")
    
    logs = await storage.list_work_logs(
        source=source,
        performed_by=performed_by,
        since=since_dt,
        project_path=project_path,
        limit=limit,
    )
    
    return APIResponse(
        success=True,
        data=[log.model_dump() for log in logs]
    )


@router.get("/work-logs/search", response_model=APIResponse)
async def search_work_logs(
    q: str = Query(..., description="Search query"),
    project_path: Optional[str] = Query(None, description="Filter by project path"),
    limit: int = Query(50, ge=1, le=200),
):
    """Search work logs by keyword, optionally scoped to a project."""
    storage = get_storage()
    
    logs = await storage.search_work_logs(
        query=q,
        project_path=project_path,
        limit=limit,
    )
    
    return APIResponse(
        success=True,
        data=[log.model_dump() for log in logs]
    )
