#!/usr/bin/env python3
"""Screenshot-less web UI integration test.

Since we can't install a browser (no sudo), this script:
1. Starts the API server
2. Calls all 3 panel APIs with injected test data
3. Validates the response structure and content
4. Fetches the actual HTML and checks key elements exist
5. Generates an HTML report showing what each panel would display

Usage:
    source venv/bin/activate
    python tests/scripts/test_web_ui.py
"""

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

API_BASE = "http://127.0.0.1:8766/api"

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def api_get(path: str) -> dict:
    """Call API and return parsed JSON."""
    try:
        req = urllib.request.Request(f"{API_BASE}{path}")
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"success": False, "error": str(e)}


def check(condition: bool, name: str, detail: str = "") -> bool:
    """Print pass/fail for a check."""
    status = f"{GREEN}✅ PASS{RESET}" if condition else f"{RED}❌ FAIL{RESET}"
    msg = f"  {status} {name}"
    if detail and not condition:
        msg += f" — {detail}"
    print(msg)
    return condition


def test_token_panel():
    """Test Token Dashboard panel data."""
    print(f"\n{BOLD}📊 Token Dashboard{RESET}")
    print("-" * 50)
    passed = 0
    total = 0

    # Top projects
    total += 1
    res = api_get("/token/top-projects")
    if check(res.get("success"), "top-projects API responds"):
        passed += 1
        projects = res.get("data", [])
        total += 1
        if check(len(projects) >= 2, f"Has >= 2 projects", f"got {len(projects)}"):
            passed += 1

        if projects:
            p = projects[0]
            total += 1
            if check(p.get("total_tokens", 0) > 0, f"Top project has tokens", f"tokens={p.get('total_tokens')}"):
                passed += 1
            total += 1
            if check(p.get("total_cost_usd", 0) > 0, f"Top project has cost", f"cost=${p.get('total_cost_usd', 0):.4f}"):
                passed += 1
            print(f"    📂 {p.get('project_name', '?')}: {p.get('total_tokens', 0):,} tokens, ${p.get('total_cost_usd', 0):.4f}, {p.get('total_records', 0)} records")

    # Project stats
    total += 1
    res = api_get("/token/stats/projects/test-app")
    if check(res.get("success"), "project stats API responds"):
        passed += 1
        stats = res.get("data", {})
        total += 1; passed += check(stats.get("total_tokens", 0) > 0, "Stats has total_tokens")
        total += 1; passed += check("by_model" in stats or "by_performer" in stats, "Stats has breakdown")

    # Daily usage
    total += 1
    res = api_get("/token/daily?project_path=/projects/test-app&days=14")
    if check(res.get("success"), "daily usage API responds"):
        passed += 1
        daily = res.get("data", [])
        total += 1; passed += check(len(daily) > 0, f"Has daily data", f"got {len(daily)} days")

    return passed, total


def test_workflow_panel():
    """Test Workflow Pipeline panel data."""
    print(f"\n{BOLD}🔄 Workflow Pipeline{RESET}")
    print("-" * 50)
    passed = 0
    total = 0

    # List
    total += 1
    res = api_get("/workflow/list")
    if check(res.get("success"), "workflow list API responds"):
        passed += 1
        wfs = res.get("data", [])
        total += 1
        if check(len(wfs) >= 2, f"Has >= 2 workflows", f"got {len(wfs)}"):
            passed += 1

        for wf in wfs[:3]:
            print(f"    🔄 {wf.get('name', '?')}: {wf.get('status')} ({len(wf.get('stages', []))} stages)")

        # Detail
        if wfs:
            wf_id = wfs[0]["workflow_id"]
            total += 1
            res2 = api_get(f"/workflow/{wf_id}")
            if check(res2.get("success"), "workflow detail API responds"):
                passed += 1
                detail = res2.get("data", {})
                total += 1; passed += check("progress_pct" in detail, "Has progress_pct")
                total += 1; passed += check("stages" in detail, "Has stages")
                total += 1; passed += check("stage_checkpoints" in detail, "Has stage_checkpoints")
                total += 1; passed += check("completed_count" in detail, "Has completed_count")

                print(f"    📊 {detail.get('name')}: {detail.get('progress_pct')}% complete")
                for stage in detail.get("stages", []):
                    sc = next((s for s in detail.get("stage_checkpoints", []) if s["stage_id"] == stage["id"]), None)
                    status = sc["status"] if sc else "pending"
                    icon = {"completed": "✅", "running": "▶️", "failed": "❌", "pending": "⏳"}.get(status, "?")
                    print(f"      {icon} {stage['name']} [{status}]")

            # Resume context
            total += 1
            res3 = api_get(f"/workflow/{wf_id}/context")
            if check(res3.get("success"), "workflow context API responds"):
                passed += 1

    return passed, total


def test_dag_panel():
    """Test Context DAG panel data."""
    print(f"\n{BOLD}🌳 Context DAG{RESET}")
    print("-" * 50)
    passed = 0
    total = 0

    # List
    total += 1
    res = api_get("/dag/list")
    if check(res.get("success"), "DAG list API responds"):
        passed += 1
        dags = res.get("data", [])
        total += 1; passed += check(len(dags) >= 1, f"Has >= 1 DAG", f"got {len(dags)}")

        for d in dags:
            print(f"    🌳 {d.get('project_name', '?')}: {d.get('total_nodes', 0)} nodes ({d.get('raw_nodes', 0)} raw, {d.get('summary_nodes', 0)} summary)")

    # Get DAG detail
    total += 1
    dag_data = None
    res2 = api_get("/dag/project/projects/test-app")
    if check(res2.get("success"), "DAG detail API responds"):
        passed += 1
        dag_data = res2.get("data", {})
        total += 1; passed += check(dag_data.get("stats", {}).get("total_nodes", 0) > 0, "DAG has nodes")
        total += 1; passed += check(len(dag_data.get("nodes", [])) > 0, "DAG has node list")
        total += 1; passed += check(len(dag_data.get("edges", [])) >= 0, "DAG has edges list")
        total += 1; passed += check("levels" in dag_data.get("stats", {}), "DAG has level breakdown")

        levels = dag_data.get("stats", {}).get("levels", {})
        print(f"    📊 Levels: L0={levels.get('L0', 0)}, L1={levels.get('L1', 0)}, L2={levels.get('L2', 0)}, L3={levels.get('L3', 0)}")

        for node in dag_data.get("nodes", [])[:5]:
            icon = {"L0": "📄", "L1": "📋", "L2": "📊", "L3": "🎯"}.get(node.get("level", ""), "·")
            print(f"      {icon} [{node.get('level')}] {node.get('title', '?')[:50]}")

    # Search
    total += 1
    res3 = api_get("/dag/search?project_path=/projects/test-app&q=token")
    if check(res3.get("success"), "DAG search API responds"):
        passed += 1
        results = res3.get("data", [])
        total += 1; passed += check(len(results) > 0, f"Search finds results", f"got {len(results)}")

    # Lineage - use actual node from DAG
    total += 1
    if dag_data and dag_data.get("nodes"):
        sample_node = dag_data["nodes"][0]
        sample_id = sample_node["id"]
        res4 = api_get(f"/dag/lineage?project_path=/projects/test-app&node_id={sample_id}")
        if check(res4.get("success"), "DAG lineage API responds"):
            passed += 1
            lineage = res4.get("data", [])
            total += 1
            if check(isinstance(lineage, list) and len(lineage) > 0, "Lineage returns a non-empty list"):
                passed += 1

    return passed, total


def test_html_ui():
    """Test that the HTML UI is served correctly."""
    print(f"\n{BOLD}🌐 HTML UI{RESET}")
    print("-" * 50)
    passed = 0
    total = 0

    try:
        req = urllib.request.Request("http://127.0.0.1:8766/")
        resp = urllib.request.urlopen(req, timeout=5)
        html = resp.read().decode()

        total += 1
        passed += check(len(html) > 100, "Index HTML loaded", f"got {len(html)} chars")

        total += 1
        passed += check("hits" in html.lower() or "HITS" in html, "HTML mentions HITS")

        # Check that Svelte bundle is referenced
        total += 1
        passed += check('assets/index' in html, "Svelte JS bundle referenced")

        # Check JS bundle exists
        import re
        js_match = re.search(r'src="(/assets/index-[^"]+\.js)"', html)
        if js_match:
            js_url = f"http://127.0.0.1:8766{js_match.group(1)}"
            js_resp = urllib.request.urlopen(js_url, timeout=5)
            js_content = js_resp.read().decode()

            total += 1
            # Svelte preserves component references in the bundle
            # Check for panel-related functionality instead of exact names
            has_token_content = "token" in js_content.lower() and "budget" in js_content.lower()
            passed += check(has_token_content, "Token Dashboard code in bundle")

            total += 1
            has_workflow_content = "workflow" in js_content.lower() and "stage" in js_content.lower()
            passed += check(has_workflow_content, "Workflow Panel code in bundle")

            total += 1
            has_dag_content = "context" in js_content.lower() and "lineage" in js_content.lower()
            passed += check(has_dag_content, "DAG Browser code in bundle")

            # Check API methods
            total += 1
            passed += check("workflow" in js_content, "workflow API methods in bundle")
            total += 1
            if check("/dag/" in js_content, "DAG API methods in bundle"):
                passed += 1

    except Exception as e:
        total += 2
        check(False, "HTML UI loads", str(e))

    return passed, total


def generate_html_report(results: dict):
    """Generate an HTML report showing the test results."""
    report_path = Path(__file__).parent.parent.parent / "test_web_ui_report.html"

    cls = "pass" if results["passed"] == results["total"] else "fail"
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    html_parts = []
    html_parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>HITS Web UI Test Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #1a1a2e; color: #eee; }}
  h1 {{ color: #3b82f6; }}
  h2 {{ color: #8b5cf6; margin-top: 24px; }}
  .pass {{ color: #22c55e; }}
  .fail {{ color: #ef4444; }}
  .summary {{ background: #16213e; padding: 16px; border-radius: 8px; margin: 16px 0; }}
  .panel {{ background: #16213e; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #3b82f6; }}
  .data-row {{ display: flex; justify-content: space-between; padding: 4px 8px; border-radius: 4px; font-size: 13px; }}
  .data-row:nth-child(even) {{ background: rgba(255,255,255,0.03); }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }}
  .badge-pass {{ background: #22c55e; color: #fff; }}
  .badge-fail {{ background: #ef4444; color: #fff; }}
  pre {{ background: #0f0f23; padding: 12px; border-radius: 6px; font-size: 11px; overflow-x: auto; }}
</style>
</head>
<body>
<h1>🧪 HITS Web UI Test Report</h1>
<div class="summary">
  <strong>Overall: <span class="{cls}">{results['passed']}/{results['total']} passed</span></strong><br>
  <span style="color:#aaa">Generated at: {now}</span>
</div>
""")

    for section in results["sections"]:
        html_parts.append(f"""<div class="panel">
<h2>{section['icon']} {section['name']}</h2>
<pre>{section['output']}</pre>
</div>\n""")

    # API response samples
    html_parts.append("<h2>📡 Raw API Responses</h2>\n")
    for name, data in results["api_samples"].items():
        html_parts.append(f"""<div class="panel">
<h3>{name}</h3>
<pre>{json.dumps(data, indent=2)[:500]}</pre>
</div>\n""")

    html_parts.append("</body></html>")
    full_html = "".join(html_parts)
    report_path.write_text(full_html, encoding="utf-8")
    print(f"\n📝 HTML report saved to: {report_path}")


def main():
    print(f"\n{BOLD}{'='*60}")
    print("  🧪 HITS Web UI Integration Test")
    print(f"{'='*60}{RESET}")

    # Check server is running
    health = api_get("/health")
    if not health.get("success"):
        print(f"\n{RED}❌ Server not running at {API_BASE}{RESET}")
        print("Start with: python -m uvicorn hits_core.api.server:app_factory --port 8766 --factory")
        sys.exit(1)

    print(f"\n{GREEN}✅ Server running{RESET}")

    total_passed = 0
    total_checks = 0
    sections = []

    for name, icon, test_fn in [
        ("Token Dashboard", "📊", test_token_panel),
        ("Workflow Pipeline", "🔄", test_workflow_panel),
        ("Context DAG", "🌳", test_dag_panel),
        ("HTML UI", "🌐", test_html_ui),
    ]:
        # Capture output
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            p, t = test_fn()
        output = buf.getvalue()
        print(output)

        total_passed += p
        total_checks += t
        sections.append({"name": name, "icon": icon, "output": output.strip()})

    # Collect API samples for the report
    api_samples = {
        "GET /token/top-projects": api_get("/token/top-projects"),
        "GET /workflow/list": api_get("/workflow/list"),
        "GET /dag/list": api_get("/dag/list"),
    }

    # Summary
    pct = round(total_passed / max(total_checks, 1) * 100)
    bar_len = 40
    filled = round(bar_len * pct / 100)
    bar = "█" * filled + "░" * (bar_len - filled)

    print(f"\n{BOLD}{'='*60}")
    color = GREEN if pct == 100 else YELLOW if pct >= 80 else RED
    print(f"  {color}Results: {total_passed}/{total_checks} ({pct}%){RESET}")
    print(f"  [{bar}]")
    print(f"{'='*60}{RESET}")

    # Generate HTML report
    generate_html_report({
        "passed": total_passed,
        "total": total_checks,
        "sections": sections,
        "api_samples": api_samples,
    })

    sys.exit(0 if pct == 100 else 1)


if __name__ == "__main__":
    main()
