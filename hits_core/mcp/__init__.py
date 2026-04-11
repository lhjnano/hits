"""HITS MCP Server - Model Context Protocol interface.

Enables AI tools (Claude, OpenCode, Cursor, etc.) to interact with HITS
directly through MCP, without needing the HTTP API server running.

Usage in opencode.json or Claude MCP config:
  {
    "hits": {
      "type": "local",
      "command": ["python", "-m", "hits_core.mcp.server"]
    }
  }

Tools provided:
  - hits_record_work: Record a work log for the current project
  - hits_get_handover: Get handover summary for a project
  - hits_search_works: Search previous work logs
  - hits_list_projects: List all projects with activity
  - hits_get_recent: Get recent work logs for a project
"""
