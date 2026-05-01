#!/usr/bin/env python3
"""Inject test data for web UI screenshot testing.

Creates:
- 2 workflows with different stages/statuses
- 1 DAG with nodes at multiple levels
- Token usage records for 2 projects
"""

import json
import sys
import os
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

# Ensure we can import hits_core
sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path.home() / ".hits" / "data"


def clean_test_data():
    """Remove previously injected test data to avoid duplicates."""
    cleaned = 0

    # Clean workflows
    wf_dir = DATA_DIR / "workflows"
    if wf_dir.exists():
        for f in wf_dir.glob("wf_*.json"):
            f.unlink()
            cleaned += 1

    # Clean DAGs
    dag_dir = DATA_DIR / "context_dags"
    if dag_dir.exists():
        for f in dag_dir.glob("*.json"):
            f.unlink()
            cleaned += 1

    # Clean token records
    tk_dir = DATA_DIR / "token_tracking" / "records"
    if tk_dir.exists():
        for f in tk_dir.glob("*.jsonl"):
            f.unlink()
            cleaned += 1

    # Clean old token dir if exists
    old_tk_dir = DATA_DIR / "tokens"
    if old_tk_dir.exists():
        for f in old_tk_dir.glob("*.jsonl"):
            f.unlink()
            cleaned += 1

    # Clean test work logs
    wl_dir = DATA_DIR / "work_logs"
    if wl_dir.exists():
        for f in wl_dir.glob("wl_*.json"):
            try:
                data = json.loads(f.read_text())
                if data.get("project_path", "").startswith("/projects/test"):
                    f.unlink()
                    cleaned += 1
            except Exception:
                pass

    if cleaned:
        print(f"  🧹 Cleaned {cleaned} files from previous runs")


def inject_workflow(name: str, status: str, stages_data: list[dict]) -> str:
    """Create a workflow JSON file directly."""
    wf_id = f"wf_{uuid4().hex[:8]}"
    project_path = "/projects/test-app"

    stages = []
    stage_checkpoints = []
    for i, sd in enumerate(stages_data):
        stages.append({
            "id": sd["id"],
            "name": sd["name"],
            "description": sd.get("description", ""),
            "agent": sd.get("agent"),
            "depends_on": sd.get("depends_on", []),
        })
        if sd.get("started"):
            sc = {
                "stage_id": sd["id"],
                "status": sd["status"],
                "performer": sd.get("performer", "claude"),
                "started_at": (datetime.now() - timedelta(hours=2 - i)).isoformat(),
                "completed_at": (datetime.now() - timedelta(hours=1 - i)).isoformat() if sd["status"] == "completed" else None,
                "error": sd.get("error"),
                "stage_index": i,
            }
            stage_checkpoints.append(sc)

    completed_count = sum(1 for s in stage_checkpoints if s["status"] == "completed")
    total = len(stages)

    if status == "completed":
        wf_status = "completed"
    elif status == "failed":
        wf_status = "failed"
    elif completed_count > 0:
        wf_status = "running"
    else:
        wf_status = "pending"

    wf = {
        "workflow_id": wf_id,
        "project_path": project_path,
        "project_name": "test-app",
        "name": name,
        "stages": stages,
        "stage_checkpoints": stage_checkpoints,
        "status": wf_status,
        "created_at": (datetime.now() - timedelta(hours=3)).isoformat(),
        "updated_at": datetime.now().isoformat(),
        "completed_at": datetime.now().isoformat() if wf_status == "completed" else None,
        "performer": "coordinator",
        "total_files_modified": [
            "src/api/routes/workflow.py",
            "src/api/routes/dag.py",
            "tests/test_workflow.py",
        ] if wf_status in ("completed", "running") else [],
        "total_decisions": [
            "Use urllib instead of requests for zero dependencies",
            "Store DAG as JSON files per project",
        ] if wf_status in ("completed", "running") else [],
        "total_errors": ["Stage validation failed: missing dependency"] if wf_status == "failed" else [],
        "total_tokens_used": 45000 if wf_status == "completed" else 25000,
        "tags": ["ml-development", "automated"],
        "metadata": {},
    }

    wf_dir = DATA_DIR / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / f"{wf_id}.json").write_text(json.dumps(wf, indent=2), encoding="utf-8")
    print(f"  Created workflow: {wf_id} ({name}) — {wf_status}")
    return wf_id


def inject_dag(project_path: str, project_name: str, node_count: int):
    """Create a DAG with multiple levels of nodes."""
    dag_id = f"dag_{uuid4().hex[:8]}"
    nodes = {}
    now = datetime.now()

    # Create raw nodes (L0)
    raw_ids = []
    raw_data = [
        ("Implement token tracker service", "Created TokenTracker class with JSONL storage, budget management, and daily aggregation"),
        ("Fix performer bug in MCP server", "Added fallback chain: performed_by → performer → sender → consumed_by → unknown"),
        ("Add DAG context browser UI", "Built Svelte component with level tree, search, lineage view"),
        ("Write scenario tests", "65 edge-case tests covering API failures, data corruption, budget boundaries"),
        ("WebSocket event bus implementation", "32 tests passed: pub/sub, ring buffer, dead client cleanup"),
    ]
    for i, (title, content) in enumerate(raw_data):
        nid = f"raw_{uuid4().hex[:6]}"
        nodes[nid] = {
            "id": nid,
            "node_type": "raw",
            "level": "L0",
            "title": title,
            "content": content,
            "content_hash": None,
            "child_ids": [],
            "parent_ids": [],
            "project_path": project_path,
            "performer": ["claude", "opencode"][i % 2],
            "session_id": f"sess_{i // 3}",
            "tags": [["feature", "backend"], ["bugfix"], ["frontend", "ui"], ["testing"], ["feature", "realtime"]][i],
            "token_count": len(content) // 3,
            "created_at": (now - timedelta(hours=5 - i)).isoformat(),
            "source_type": "work_log",
            "source_id": f"wl_{uuid4().hex[:6]}",
        }
        raw_ids.append(nid)

    # Create L1 summaries
    l1_ids = []
    for i, batch in enumerate([raw_ids[:3], raw_ids[3:]]):
        nid = f"sum_{uuid4().hex[:6]}"
        title = f"Session {i + 1} summary"
        content = f"Summary of {len(batch)} work items from session {i + 1}"
        nodes[nid] = {
            "id": nid,
            "node_type": "summary",
            "level": "L1",
            "title": title,
            "content": content,
            "child_ids": batch,
            "parent_ids": [],
            "project_path": project_path,
            "performer": "system",
            "token_count": len(content) // 3,
            "created_at": (now - timedelta(hours=2 - i)).isoformat(),
            "tags": ["auto-summary"],
        }
        # Update children's parent_ids
        for cid in batch:
            if cid in nodes:
                nodes[cid]["parent_ids"].append(nid)
        l1_ids.append(nid)

    # Create L2 compact
    l2_id = f"sum_{uuid4().hex[:6]}"
    l2_content = "Day summary: 5 work items completed including token tracking, bug fixes, UI components, and WebSocket support"
    nodes[l2_id] = {
        "id": l2_id,
        "node_type": "summary",
        "level": "L2",
        "title": "Daily compact summary",
        "content": l2_content,
        "child_ids": l1_ids,
        "parent_ids": [],
        "project_path": project_path,
        "performer": "system",
        "token_count": len(l2_content) // 3,
        "created_at": now.isoformat(),
        "tags": ["auto-summary"],
    }
    for cid in l1_ids:
        if cid in nodes:
            nodes[cid]["parent_ids"].append(l2_id)

    dag = {
        "id": dag_id,
        "project_path": project_path,
        "project_name": project_name,
        "nodes": nodes,
        "root_id": l2_id,
        "created_at": (now - timedelta(hours=6)).isoformat(),
        "updated_at": now.isoformat(),
        "total_raw_nodes": len(raw_ids),
        "total_summary_nodes": len(l1_ids) + 1,
        "total_tokens_preserved": sum(n["token_count"] for n in nodes.values()),
    }

    dag_dir = DATA_DIR / "context_dags"
    dag_dir.mkdir(parents=True, exist_ok=True)
    key = project_path.replace("/", "_").strip("_")
    (dag_dir / f"{key}.json").write_text(json.dumps(dag, indent=2), encoding="utf-8")
    print(f"  Created DAG: {dag_id} ({len(nodes)} nodes) — {project_name}")


def inject_token_data():
    """Create token usage JSONL files for testing."""
    from datetime import date

    token_dir = DATA_DIR / "token_tracking" / "records"
    token_dir.mkdir(parents=True, exist_ok=True)

    today = date.today()
    records = []

    # Project 1: test-app (active, various tools)
    for days_ago in range(14):
        d = today - timedelta(days=days_ago)
        for model, tokens_in, tokens_out, performer, operation in [
            ("claude-3.5-sonnet", 5500 + days_ago * 300, 2500 + days_ago * 200, "claude", "hits_auto_checkpoint"),
            ("glm-5.1", 2000 + days_ago * 100, 1000 + days_ago * 100, "opencode", "hits_record_work"),
            ("claude-3.5-sonnet", 1400, 600, "claude", "hits_resume"),
            ("glm-5.1", 1000 + days_ago * 50, 500 + days_ago * 50, "opencode", "hits_signal_send"),
        ]:
            records.append({
                "id": f"tr_{uuid4().hex[:8]}",
                "project_path": "/projects/test-app",
                "performer": performer,
                "session_id": f"sess_{days_ago // 3}",
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "tokens_total": tokens_in + tokens_out,
                "model": model,
                "estimated_cost_usd": (tokens_in + tokens_out) * 0.000003,
                "operation": operation,
                "tags": [],
                "recorded_at": f"{d}T{10 + days_ago % 12}:{30 + days_ago % 30}:00",
            })

    # Project 2: ml-pipeline (less active)
    for days_ago in range(7):
        d = today - timedelta(days=days_ago)
        tokens_in = 3500 + days_ago * 200
        tokens_out = 1500 + days_ago * 100
        records.append({
            "id": f"tr_{uuid4().hex[:8]}",
            "project_path": "/projects/ml-pipeline",
            "performer": "cursor",
            "session_id": f"sess_ml_{days_ago // 2}",
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "tokens_total": tokens_in + tokens_out,
            "model": "claude-3.5-sonnet",
            "estimated_cost_usd": (tokens_in + tokens_out) * 0.000003,
            "operation": "hits_auto_checkpoint",
            "tags": ["ml"],
            "recorded_at": f"{d}T14:{days_ago * 5}:00",
        })

    # Write daily JSONL files (filename format: YYYY-MM-DD.jsonl)
    by_date = {}
    for r in records:
        d = r["recorded_at"][:10]
        by_date.setdefault(d, []).append(r)

    for d, recs in by_date.items():
        filepath = token_dir / f"{d}.jsonl"
        with open(filepath, "w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")

    total = len(records)
    print(f"  Created {total} token records across {len(by_date)} days")


def inject_work_logs():
    """Create a few work logs for the test projects."""
    wl_dir = DATA_DIR / "work_logs"
    wl_dir.mkdir(parents=True, exist_ok=True)

    logs = [
        {
            "id": f"wl_{uuid4().hex[:8]}",
            "request_text": "Implement workflow and DAG API routes with frontend panels",
            "context": "Added 14 API endpoints, rewrote 3 Svelte panels, fixed token path bugs",
            "project_path": "/projects/test-app",
            "performed_by": "claude",
            "tags": ["feature", "api", "frontend"],
            "created_at": datetime.now().isoformat(),
        },
        {
            "id": f"wl_{uuid4().hex[:8]}",
            "request_text": "Set up ML pipeline with data collection and model training stages",
            "context": "Created workflow with 4 stages, DAG nodes for tracking",
            "project_path": "/projects/ml-pipeline",
            "performed_by": "opencode",
            "tags": ["ml", "pipeline"],
            "created_at": (datetime.now() - timedelta(hours=2)).isoformat(),
        },
    ]

    for log in logs:
        filepath = wl_dir / f"{log['id']}.json"
        filepath.write_text(json.dumps(log, indent=2), encoding="utf-8")

    print(f"  Created {len(logs)} work logs")


def main():
    print("🧪 Injecting test data into ~/.hits/data/ ...")
    print()

    # Clean previous test data first
    print("🧹 Cleaning previous test data...")
    clean_test_data()
    print()

    print("📦 Workflows:")
    inject_workflow(
        "ML Development Pipeline",
        "running",
        [
            {"id": "s1", "name": "Data Collection", "status": "completed", "started": True, "performer": "opencode", "agent": "data-collector"},
            {"id": "s2", "name": "Model Design", "status": "completed", "started": True, "performer": "claude", "agent": "designer"},
            {"id": "s3", "name": "Training & Optimization", "status": "running", "started": True, "performer": "claude", "agent": "trainer"},
            {"id": "s4", "name": "Evaluation", "status": "pending", "agent": "evaluator", "depends_on": ["s3"]},
            {"id": "s5", "name": "Deployment", "status": "pending", "agent": "deployer", "depends_on": ["s4"]},
        ]
    )
    inject_workflow(
        "Code Review Pipeline",
        "failed",
        [
            {"id": "s1", "name": "Static Analysis", "status": "completed", "started": True, "performer": "opencode"},
            {"id": "s2", "name": "Security Scan", "status": "failed", "started": True, "error": "Dependency vulnerability found in requests@2.28.0", "performer": "claude"},
            {"id": "s3", "name": "Performance Review", "status": "pending", "depends_on": ["s2"]},
        ]
    )

    print()
    print("🌳 Context DAG:")
    inject_dag("/projects/test-app", "test-app", 8)

    print()
    print("📊 Token Usage:")
    inject_token_data()

    print()
    print("📝 Work Logs:")
    inject_work_logs()

    print()
    print("✅ Test data injection complete!")


if __name__ == "__main__":
    main()
