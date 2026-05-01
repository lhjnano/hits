"""Context DAG HTTP routes — expose ContextDAGService via API.

Provides endpoints for:
- Listing project DAGs
- Viewing DAG structure (nodes, edges, levels)
- Getting statistics
- Searching context
- Viewing node lineage
"""

from fastapi import APIRouter, Query as QueryParam
from typing import Optional
from pydantic import BaseModel

from hits_core.service.context_dag_service import ContextDAGService


class APIResponse(BaseModel):
    success: bool = True
    data: Optional[dict | list] = None
    error: Optional[str] = None

router = APIRouter(prefix="/dag", tags=["dag"])

_svc: Optional[ContextDAGService] = None


def _get_service() -> ContextDAGService:
    global _svc
    if _svc is None:
        _svc = ContextDAGService()
    return _svc


@router.get("/list")
async def list_dags():
    """List all projects that have DAG data.

    Scans ~/.hits/data/context_dags/ for .json files and returns
    project name + statistics for each.
    """
    svc = _get_service()
    from pathlib import Path

    dag_dir = svc._dag_dir
    results = []

    for path in sorted(dag_dir.glob("*.json")):
        try:
            from ..models.context_dag import ContextDAG
            dag = ContextDAG.model_validate_json(path.read_text(encoding="utf-8"))
            stats = dag.get_statistics()
            results.append({
                "project_path": dag.project_path,
                "project_name": dag.project_name,
                "dag_id": dag.id,
                "total_nodes": stats["total_nodes"],
                "raw_nodes": stats["raw_nodes"],
                "summary_nodes": stats["summary_nodes"],
                "total_tokens_preserved": stats["total_tokens_preserved"],
                "has_root": stats["has_root"],
                "updated_at": dag.updated_at.isoformat() if dag.updated_at else None,
            })
        except Exception:
            continue

    return APIResponse(success=True, data=results)


@router.get("/project/{project_path:path}")
async def get_dag(project_path: str):
    """Get the full DAG structure for a project.

    Returns nodes, edges, and statistics suitable for visualization.
    """
    svc = _get_service()
    dag = await svc.get_or_create_dag(project_path)

    stats = dag.get_statistics()

    # Build edges list for visualization
    edges = []
    for node in dag.nodes.values():
        for child_id in node.child_ids:
            edges.append({"from": node.id, "to": child_id})

    # Build nodes list sorted by level then created_at
    nodes_list = sorted(
        dag.nodes.values(),
        key=lambda n: (n.level, n.created_at),
    )

    return APIResponse(success=True, data={
        "dag_id": dag.id,
        "project_path": dag.project_path,
        "project_name": dag.project_name,
        "root_id": dag.root_id,
        "stats": stats,
        "nodes": [n.model_dump() for n in nodes_list],
        "edges": edges,
        "levels": stats.get("levels", {}),
    })


@router.get("/project/{project_path:path}/stats")
async def get_dag_stats(project_path: str):
    """Get DAG statistics for a project."""
    svc = _get_service()
    stats = await svc.get_statistics(project_path)
    return APIResponse(success=True, data=stats)


@router.get("/project/{project_path:path}/search")
async def search_dag(
    project_path: str,
    q: str = QueryParam(default=""),
    limit: int = QueryParam(default=10, ge=1, le=50),
):
    """Search for context nodes in a project's DAG."""
    if not q.strip():
        return APIResponse(success=True, data=[])
    svc = _get_service()
    results = await svc.search_context(project_path, q, limit=limit)
    return APIResponse(success=True, data=[n.model_dump() for n in results])


@router.get("/project/{project_path:path}/lineage/{node_id}")
async def get_lineage(project_path: str, node_id: str):
    """Get full lineage of a node (ancestors + descendants) for audit."""
    svc = _get_service()
    lineage = await svc.get_lineage(project_path, node_id)
    return APIResponse(success=True, data=[n.model_dump() for n in lineage])


@router.get("/project/{project_path:path}/context")
async def get_resume_context(
    project_path: str,
    token_budget: int = QueryParam(default=2000, ge=100, le=10000),
):
    """Get context for resuming a project, respecting token budget."""
    svc = _get_service()
    context = await svc.get_context_for_resume(project_path, token_budget=token_budget)
    return APIResponse(success=True, data={"context": context})
