"""HITS MCP Server implementation using stdio transport.

This module provides a standalone MCP server that exposes HITS functionality
as MCP tools. It auto-detects the current project from CWD.

Run with: python -m hits_core.mcp.server
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

# Ensure project root is in path
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from hits_core.storage.file_store import FileStorage
from hits_core.models.work_log import WorkLog, WorkLogSource, WorkLogResultType
from hits_core.service.handover_service import HandoverService
from hits_core.service.signal_service import SignalService
from hits_core.service.checkpoint_service import CheckpointService
from hits_core.ai.checkpoint_compressor import CheckpointCompressor


def _detect_project_path() -> str:
    """Auto-detect project path from CWD, walking up to find git root."""
    cwd = Path.cwd().resolve()
    current = cwd

    for _ in range(10):  # Max 10 levels up
        if (current / ".git").exists():
            return str(current)
        parent = current.parent
        if parent == current:
            break
        current = parent

    return str(cwd)


def _json_rpc_response(id_val: Any, result: dict = None, error: dict = None) -> str:
    """Build a JSON-RPC 2.0 response."""
    resp = {"jsonrpc": "2.0", "id": id_val}
    if error:
        resp["error"] = error
    else:
        resp["result"] = result or {}
    return json.dumps(resp, ensure_ascii=False)


def _tool_result(text: str) -> list[dict]:
    """Build MCP tool result content."""
    return [{"type": "text", "text": text}]


class HITSMCPServer:
    """MCP Server for HITS - runs over stdio."""

    TOOLS = [
        {
            "name": "hits_record_work",
            "description": (
                "Record a work log for the current project. "
                "Call this when ending a session or completing a task. "
                "The project_path is auto-detected from CWD but can be overridden."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_text": {
                        "type": "string",
                        "description": "Summary of what was done (1-2 sentences)",
                    },
                    "context": {
                        "type": "string",
                        "description": "Detailed context, decisions made, important notes",
                    },
                    "performed_by": {
                        "type": "string",
                        "description": "AI tool name: 'claude', 'opencode', 'cursor', etc.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags: ['feature', 'bugfix', 'refactor', etc.]",
                    },
                    "files_modified": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of files that were modified",
                    },
                    "commands_run": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Commands that were run",
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Override auto-detected project path",
                    },
                },
                "required": ["request_text", "performed_by"],
            },
        },
        {
            "name": "hits_get_handover",
            "description": (
                "Get a handover summary for a project. "
                "Call this when starting a new session to understand what "
                "previous AI sessions (Claude, OpenCode, etc.) have done. "
                "Returns project-scoped context including recent work, key decisions, "
                "pending items, files modified, and session history."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Project path (default: auto-detect from CWD)",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "dict"],
                        "description": "Output format (default: 'text')",
                    },
                },
            },
        },
        {
            "name": "hits_search_works",
            "description": (
                "Search previous work logs by keyword, scoped to a project. "
                "Use this to find specific past work or decisions."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keyword",
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Scope to project (default: auto-detect from CWD)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "hits_list_projects",
            "description": (
                "List all projects that have recorded work logs. "
                "Use this to discover which projects have accumulated context."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "hits_get_recent",
            "description": (
                "Get recent work logs for a project. "
                "Lighter than full handover - returns raw log entries."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Project path (default: auto-detect from CWD)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent logs (default: 10)",
                    },
                    "performed_by": {
                        "type": "string",
                        "description": "Filter by AI tool name",
                    },
                },
            },
        },
        # ─── Signal Tools ──────────────────────────────────────
        {
            "name": "hits_signal_send",
            "description": (
                "Send a handover signal to another AI tool. "
                "Call this when your session is ending and you want to notify "
                "the next AI tool (e.g., Claude→OpenCode or OpenCode→Claude). "
                "Creates a signal file in ~/.hits/signals/pending/ that the "
                "recipient tool can detect via its hook or MCP call."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "sender": {
                        "type": "string",
                        "description": "Your tool name: 'claude', 'opencode', 'cursor', etc.",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Target tool name, or 'any' for broadcast (default: 'any')",
                    },
                    "signal_type": {
                        "type": "string",
                        "description": "Signal type: 'session_end', 'task_ready', 'question', 'urgent' (default: 'session_end')",
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Project path (default: auto-detect from CWD)",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of what was done / needs to be done",
                    },
                    "context": {
                        "type": "string",
                        "description": "Detailed context for the next session",
                    },
                    "pending_items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of unfinished tasks",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for categorization",
                    },
                    "priority": {
                        "type": "string",
                        "description": "Priority: 'normal', 'high', 'urgent' (default: 'normal')",
                    },
                },
                "required": ["sender", "summary"],
            },
        },
        {
            "name": "hits_signal_check",
            "description": (
                "Check for pending handover signals addressed to you. "
                "Call this at session start to see if another AI tool left work for you. "
                "Returns a list of pending signals from ~/.hits/signals/pending/."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "recipient": {
                        "type": "string",
                        "description": "Your tool name to filter signals (default: 'any' = all pending)",
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Filter by project path (default: auto-detect from CWD)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)",
                    },
                },
            },
        },
        {
            "name": "hits_signal_consume",
            "description": (
                "Mark a signal as consumed (acknowledge and archive). "
                "Call this after reading and acting on a signal. "
                "Moves the signal from pending/ to consumed/."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "signal_id": {
                        "type": "string",
                        "description": "The signal ID to consume (e.g., 'sig_abc12345')",
                    },
                    "consumed_by": {
                        "type": "string",
                        "description": "Your tool name: 'claude', 'opencode', etc.",
                    },
                },
                "required": ["signal_id", "consumed_by"],
            },
        },
        # ─── Checkpoint Tools ──────────────────────────────────
        {
            "name": "hits_auto_checkpoint",
            "description": (
                "AUTO-CHECKPOINT: Call this when your session is ending. "
                "It automatically generates a structured checkpoint from your work logs, "
                "sends a handover signal, AND records the work log - all in one call. "
                "This is the RECOMMENDED way to end a session instead of calling "
                "hits_record_work + hits_signal_send separately.\n\n"
                "The checkpoint includes: purpose, next steps (with commands), "
                "required context, file deltas, decisions, and blockers.\n\n"
                "ALWAYS call this at session end, even if you're not sure what to put. "
                "It auto-extracts most information from your existing work logs."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "performer": {
                        "type": "string",
                        "description": "Your tool name: 'claude', 'opencode', 'cursor', etc.",
                    },
                    "purpose": {
                        "type": "string",
                        "description": "What this session was trying to accomplish (1-2 sentences)",
                    },
                    "current_state": {
                        "type": "string",
                        "description": "What was actually achieved (1-2 sentences)",
                    },
                    "completion_pct": {
                        "type": "integer",
                        "description": "Estimated completion percentage 0-100",
                    },
                    "next_steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string", "description": "What to do (imperative)"},
                                "command": {"type": "string", "description": "Shell command if applicable"},
                                "file": {"type": "string", "description": "Primary file to edit"},
                                "priority": {"type": "string", "description": "critical/high/medium/low"},
                            },
                            "required": ["action"],
                        },
                        "description": "Ordered list of next steps for the next session",
                    },
                    "required_context": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Critical facts the next session MUST know",
                    },
                    "files_modified": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files that were modified in this session",
                    },
                    "commands_run": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Commands that were run",
                    },
                    "blocks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "issue": {"type": "string", "description": "What's blocking"},
                                "workaround": {"type": "string", "description": "Known workaround"},
                                "severity": {"type": "string", "description": "critical/medium/low"},
                            },
                            "required": ["issue"],
                        },
                        "description": "Blockers preventing progress",
                    },
                    "decisions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "decision": {"type": "string", "description": "What was decided"},
                                "rationale": {"type": "string", "description": "Why"},
                            },
                            "required": ["decision"],
                        },
                        "description": "Important decisions made in this session",
                    },
                    "send_signal": {
                        "type": "boolean",
                        "description": "Also send a handover signal (default: true)",
                    },
                    "signal_recipient": {
                        "type": "string",
                        "description": "Signal recipient tool name (default: 'any')",
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Override auto-detected project path",
                    },
                    "token_budget": {
                        "type": "integer",
                        "description": "Token budget for compressed output (default: 2000)",
                    },
                },
                "required": ["performer"],
            },
        },
        {
            "name": "hits_resume",
            "description": (
                "RESUME: Call this when starting a new session to immediately "
                "understand what to do next. Returns a structured checkpoint with "
                "actionable next steps, commands, and required context.\n\n"
                "Also checks for pending handover signals and includes them.\n\n"
                "This is the RECOMMENDED way to start a session instead of calling "
                "hits_get_handover + hits_signal_check separately."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Project path (default: auto-detect from CWD)",
                    },
                    "token_budget": {
                        "type": "integer",
                        "description": "Max tokens for response (default: 2000). "
                        "Automatically compresses to fit.",
                    },
                    "performer": {
                        "type": "string",
                        "description": "Your tool name (for consuming signals)",
                    },
                },
            },
        },
        {
            "name": "hits_list_checkpoints",
            "description": (
                "List available resume points (checkpoints) for a project. "
                "Use this to see the history of session snapshots and choose "
                "which one to resume from."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Project path (default: auto-detect from CWD)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max checkpoints to return (default: 5)",
                    },
                },
            },
        },
    ]

    SERVER_INFO = {
        "name": "hits-mcp",
        "version": "0.1.0",
    }

    CAPABILITIES = {
        "tools": {"listChanged": False},
    }

    def __init__(self, data_path: Optional[str] = None):
        # Use centralized ~/.hits/data/ by default (same as FileStorage)
        self.storage = FileStorage(base_path=data_path)
        self.handover_service = HandoverService(storage=self.storage)
        self.signal_service = SignalService(data_path=data_path)
        self.checkpoint_service = CheckpointService(storage=self.storage)
        self.checkpoint_compressor = CheckpointCompressor()

    async def handle_initialize(self, params: dict, id_val: Any) -> str:
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": self.CAPABILITIES,
            "serverInfo": self.SERVER_INFO,
        }
        return _json_rpc_response(id_val, result=result)

    async def handle_tools_list(self, params: dict, id_val: Any) -> str:
        return _json_rpc_response(id_val, result={"tools": self.TOOLS})

    async def handle_tools_call(self, params: dict, id_val: Any) -> str:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # Check for pending signals on every call
        prefix = ""
        try:
            sig_svc = SignalService()
            signals = await sig_svc.check_signals(recipient="any", limit=3)
            if signals:
                lines = ["📬 HITS: Pending handover signals!"]
                for s in signals[:3]:
                    lines.append(f"  [{s.priority}] {s.sender}: {s.summary}")
                lines.append("Call hits_resume() or hits_signal_check() to load context.")
                prefix = "\n".join(lines) + "\n\n"
        except Exception:
            pass

        try:
            if tool_name == "hits_record_work":
                result = await self._tool_record_work(arguments)
            elif tool_name == "hits_get_handover":
                result = await self._tool_get_handover(arguments)
            elif tool_name == "hits_search_works":
                result = await self._tool_search_works(arguments)
            elif tool_name == "hits_list_projects":
                result = await self._tool_list_projects(arguments)
            elif tool_name == "hits_get_recent":
                result = await self._tool_get_recent(arguments)
            elif tool_name == "hits_signal_send":
                result = await self._tool_signal_send(arguments)
            elif tool_name == "hits_signal_check":
                result = await self._tool_signal_check(arguments)
            elif tool_name == "hits_signal_consume":
                result = await self._tool_signal_consume(arguments)
            elif tool_name == "hits_auto_checkpoint":
                result = await self._tool_auto_checkpoint(arguments)
            elif tool_name == "hits_resume":
                result = await self._tool_resume(arguments)
            elif tool_name == "hits_list_checkpoints":
                result = await self._tool_list_checkpoints(arguments)
            else:
                return _json_rpc_response(
                    id_val,
                    error={"code": -32601, "message": f"Unknown tool: {tool_name}"},
                )

            # Prepend signal notification if any
            if prefix and result:
                result[0]["text"] = prefix + result[0]["text"]

            return _json_rpc_response(
                id_val,
                result={"content": result},
            )

        except Exception as e:
            return _json_rpc_response(
                id_val,
                result={
                    "content": _tool_result(f"Error: {str(e)}"),
                    "isError": True,
                },
            )

    async def _tool_record_work(self, args: dict) -> list[dict]:
        project_path = args.get("project_path") or _detect_project_path()
        performed_by = args.get("performed_by", "unknown")

        log = WorkLog(
            id=str(uuid4())[:8],
            source=WorkLogSource.AI_SESSION,
            performed_by=performed_by,
            request_text=args.get("request_text"),
            context=args.get("context"),
            tags=args.get("tags", []),
            project_path=str(Path(project_path).resolve()),
            result_type=WorkLogResultType.AI_RESPONSE,
            result_data={
                "files_modified": args.get("files_modified", []),
                "commands_run": args.get("commands_run", []),
            },
        )

        success = await self.storage.save_work_log(log)

        if success:
            return _tool_result(
                f"✅ Work recorded\n"
                f"  ID: {log.id}\n"
                f"  Project: {project_path}\n"
                f"  By: {performed_by}\n"
                f"  Summary: {log.request_text}"
            )
        else:
            return _tool_result("❌ Failed to record work")

    async def _tool_get_handover(self, args: dict) -> list[dict]:
        project_path = args.get("project_path") or _detect_project_path()
        project_path = str(Path(project_path).resolve())
        fmt = args.get("format", "text")

        summary = await self.handover_service.get_handover(project_path)

        if fmt == "text":
            return _tool_result(summary.to_text())
        else:
            return _tool_result(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))

    async def _tool_search_works(self, args: dict) -> list[dict]:
        query = args.get("query", "")
        project_path = args.get("project_path") or _detect_project_path()
        project_path = str(Path(project_path).resolve())
        limit = args.get("limit", 10)

        logs = await self.storage.search_work_logs(
            query=query,
            project_path=project_path,
            limit=limit,
        )

        if not logs:
            return _tool_result(f"No results found: '{query}' (project: {project_path})")

        lines = [f"Search results: '{query}' ({len(logs)} entries)\n"]
        for log in logs:
            ts = log.performed_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{ts}] ({log.performed_by}) {log.request_text or log.context}")
            if log.tags:
                lines.append(f"  tags: {', '.join(log.tags)}")

        return _tool_result("\n".join(lines))

    async def _tool_list_projects(self, args: dict) -> list[dict]:
        projects = await self.handover_service.list_projects()

        if not projects:
            return _tool_result("No projects recorded.")

        lines = [f"Projects ({len(projects)})\n"]
        for p in projects:
            name = Path(p["project_path"]).name
            logs = p.get("total_logs", 0)
            last = p.get("last_activity", "N/A")
            performers = ", ".join(p.get("performers", {}).keys())
            lines.append(f"  {name}: {logs} entries (last: {last}) [{performers}]")

        return _tool_result("\n".join(lines))

    async def _tool_get_recent(self, args: dict) -> list[dict]:
        project_path = args.get("project_path") or _detect_project_path()
        project_path = str(Path(project_path).resolve())
        limit = args.get("limit", 10)
        performed_by = args.get("performed_by")

        logs = await self.storage.list_work_logs(
            project_path=project_path,
            performed_by=performed_by,
            limit=limit,
        )

        if not logs:
            return _tool_result(f"No recent work (project: {project_path})")

        lines = [f"Recent work ({len(logs)} entries)\n"]
        for log in logs:
            ts = log.performed_at.strftime("%m/%d %H:%M")
            lines.append(f"[{ts}] ({log.performed_by}) {log.request_text or log.context}")

        return _tool_result("\n".join(lines))

    # ─── Signal Tools ──────────────────────────────────────────

    async def _tool_signal_send(self, args: dict) -> list[dict]:
        sender = args.get("sender", "unknown")
        project_path = args.get("project_path") or _detect_project_path()

        signal = await self.signal_service.send_signal(
            sender=sender,
            recipient=args.get("recipient", "any"),
            signal_type=args.get("signal_type", "session_end"),
            project_path=str(Path(project_path).resolve()),
            summary=args.get("summary", ""),
            context=args.get("context"),
            pending_items=args.get("pending_items", []),
            tags=args.get("tags", []),
            priority=args.get("priority", "normal"),
        )

        return _tool_result(
            f"🚨 Signal sent\n"
            f"  ID: {signal.id}\n"
            f"  {signal.sender} → {signal.recipient}\n"
            f"  Type: {signal.signal_type}\n"
            f"  Priority: {signal.priority}\n"
            f"  Project: {signal.project_path}\n"
            f"  Summary: {signal.summary}\n"
            f"\nThe recipient AI can detect via hits_signal_check() or hook script."
        )

    async def _tool_signal_check(self, args: dict) -> list[dict]:
        recipient = args.get("recipient", "any")
        project_path = args.get("project_path") or _detect_project_path()
        project_path = str(Path(project_path).resolve())
        limit = args.get("limit", 10)

        signals = await self.signal_service.check_signals(
            recipient=recipient,
            project_path=project_path,
            limit=limit,
        )

        if not signals:
            return _tool_result(f"No pending signals (recipient: {recipient}, project: {project_path})")

        lines = [f"📬 Pending signals ({len(signals)})\n"]
        for sig in signals:
            ts = sig.created_at.strftime("%m/%d %H:%M")
            priority_icon = {"urgent": "🔴", "high": "🟡"}.get(sig.priority, "🟢")
            lines.append(f"  {priority_icon} [{ts}] {sig.sender} → {sig.recipient}")
            lines.append(f"     ID: {sig.id}")
            lines.append(f"     Type: {sig.signal_type}")
            lines.append(f"     Summary: {sig.summary}")
            if sig.pending_items:
                lines.append(f"     Pending: {', '.join(sig.pending_items[:3])}")
            lines.append("")

        lines.append("Use hits_signal_consume(signal_id, consumed_by) to acknowledge")
        return _tool_result("\n".join(lines))

    async def _tool_signal_consume(self, args: dict) -> list[dict]:
        signal_id = args.get("signal_id", "")
        consumed_by = args.get("consumed_by", "unknown")

        signal = await self.signal_service.consume_signal(
            signal_id=signal_id,
            consumed_by=consumed_by,
        )

        if not signal:
            return _tool_result(f"❌ Signal not found: {signal_id}")

        return _tool_result(
            f"✅ Signal consumed\n"
            f"  ID: {signal.id}\n"
            f"  {signal.sender} → {consumed_by}\n"
            f"  Status: consumed"
        )

    # ─── Checkpoint Tools ──────────────────────────────────────

    async def _tool_auto_checkpoint(self, args: dict) -> list[dict]:
        """Auto-checkpoint: record work + generate checkpoint + send signal."""
        project_path = args.get("project_path") or _detect_project_path()
        performer = args.get("performer", "unknown")
        token_budget = args.get("token_budget", 2000)

        # 1. Record work log
        log = WorkLog(
            id=str(uuid4())[:8],
            source=WorkLogSource.AI_SESSION,
            performed_by=performer,
            request_text=args.get("purpose") or args.get("current_state") or "Session checkpoint",
            context=args.get("current_state"),
            tags=["checkpoint", "auto"],
            project_path=str(Path(project_path).resolve()),
            result_type=WorkLogResultType.AI_RESPONSE,
            result_data={
                "files_modified": args.get("files_modified", []),
                "commands_run": args.get("commands_run", []),
            },
        )
        await self.storage.save_work_log(log)

        # 2. Generate checkpoint
        from ..models.checkpoint import NextStep as CPNextStep, Block as CPBlock, Decision as CPDecision

        next_steps = []
        for step in args.get("next_steps", []):
            next_steps.append(CPNextStep(
                action=step["action"],
                command=step.get("command"),
                file=step.get("file"),
                priority=step.get("priority", "medium"),
            ))

        blocks = []
        for b in args.get("blocks", []):
            blocks.append(CPBlock(
                issue=b["issue"],
                workaround=b.get("workaround"),
                severity=b.get("severity", "medium"),
            ))

        decisions = []
        for d in args.get("decisions", []):
            decisions.append(CPDecision(
                decision=d["decision"],
                rationale=d.get("rationale"),
            ))

        checkpoint = await self.checkpoint_service.auto_checkpoint(
            project_path=project_path,
            performer=performer,
            purpose=args.get("purpose", ""),
            current_state=args.get("current_state", ""),
            completion_pct=args.get("completion_pct", 0),
            additional_context=args.get("required_context", []),
            additional_steps=next_steps,
            files_modified=args.get("files_modified", []),
            commands_run=args.get("commands_run", []),
        )

        # Override extracted blocks/decisions with explicit ones if provided
        if blocks:
            checkpoint.blocks = blocks
        if decisions:
            checkpoint.decisions_made = decisions

        # 3. Send signal (default: true)
        signal_info = ""
        if args.get("send_signal", True):
            signal = await self.signal_service.send_signal(
                sender=performer,
                recipient=args.get("signal_recipient", "any"),
                signal_type="session_end",
                project_path=str(Path(project_path).resolve()),
                summary=args.get("purpose", checkpoint.purpose),
                context=checkpoint.to_compact(token_budget=500),
                pending_items=[s.action for s in checkpoint.next_steps[:3]],
                tags=["checkpoint", "auto"],
                priority="normal" if checkpoint.completion_pct >= 80 else "high",
            )
            signal_info = f"\n  📨 Signal: {signal.id} ({signal.sender} → {signal.recipient})"

        # 4. Compress output
        compressed = self.checkpoint_compressor.compress_checkpoint(
            checkpoint, token_budget=token_budget
        )

        return _tool_result(
            f"✅ Auto-checkpoint complete\n"
            f"  📝 Work log: {log.id}\n"
            f"  💾 Checkpoint: {checkpoint.id}\n"
            f"  📂 Project: {project_path}\n"
            f"  👤 By: {performer}\n"
            f"  📊 Progress: {checkpoint.completion_pct}%"
            f"{signal_info}\n\n"
            f"--- CHECKPOINT (next session context) ---\n\n"
            f"{compressed}\n\n"
            f"--- END CHECKPOINT ---"
        )

    async def _tool_resume(self, args: dict) -> list[dict]:
        """Resume: get latest checkpoint + check signals."""
        project_path = args.get("project_path") or _detect_project_path()
        project_path = str(Path(project_path).resolve())
        token_budget = args.get("token_budget", 2000)
        performer = args.get("performer", "unknown")

        parts = []

        # 1. Check for pending signals
        signals = await self.signal_service.check_signals(
            recipient="any",
            project_path=project_path,
            limit=3,
        )
        if signals:
            parts.append("📬 PENDING SIGNALS:")
            for sig in signals:
                priority_icon = {"urgent": "🔴", "high": "🟡"}.get(sig.priority, "🟢")
                parts.append(f"  {priority_icon} [{sig.sender}] {sig.summary}")
                if sig.pending_items:
                    for item in sig.pending_items[:3]:
                        parts.append(f"    • {item}")
                parts.append("")

            # Auto-consume signals if performer specified
            if performer and performer != "unknown":
                for sig in signals:
                    await self.signal_service.consume_signal(sig.id, performer)

        # 2. Get latest checkpoint
        checkpoint = await self.checkpoint_service.get_latest_checkpoint(project_path)

        if checkpoint:
            compressed = self.checkpoint_compressor.compress_checkpoint(
                checkpoint, token_budget=token_budget
            )
            parts.append("--- RESUME CONTEXT ---\n")
            parts.append(compressed)
            parts.append("\n--- END RESUME ---")
        else:
            # Fallback to handover summary
            summary = await self.handover_service.get_handover(project_path)
            parts.append("--- RESUME (handover fallback) ---\n")
            parts.append(summary.to_text())
            parts.append("\n--- END RESUME ---")

        return _tool_result("\n".join(parts))

    async def _tool_list_checkpoints(self, args: dict) -> list[dict]:
        """List available checkpoints for a project."""
        project_path = args.get("project_path") or _detect_project_path()
        project_path = str(Path(project_path).resolve())
        limit = args.get("limit", 5)

        checkpoints = await self.checkpoint_service.list_checkpoints(
            project_path, limit=limit
        )

        if not checkpoints:
            return _tool_result(
                f"No checkpoints available.\n"
                f"Project: {project_path}\n"
                f"Call hits_auto_checkpoint() at session end to auto-generate."
            )

        lines = [f"📍 Resume Points ({len(checkpoints)})\n"]
        for i, cp in enumerate(checkpoints, 1):
            ts = cp.created_at.strftime("%Y-%m-%d %H:%M")
            progress = "█" * (cp.completion_pct // 10) + "░" * (10 - cp.completion_pct // 10)
            lines.append(f"  {i}. [{ts}] {cp.performer}")
            lines.append(f"     purpose: {cp.purpose[:80]}")
            lines.append(f"     progress: {progress} {cp.completion_pct}%")
            if cp.next_steps:
                lines.append(f"     next: {cp.next_steps[0].action[:60]}")
            if cp.git_branch:
                lines.append(f"     git: {cp.git_branch}")
            lines.append(f"     ID: {cp.id}")
            lines.append("")

        lines.append(f"Resume: hits_resume() or npx @purpleraven/hits resume")
        return _tool_result("\n".join(lines))

    async def handle_request(self, request: dict) -> Optional[str]:
        """Handle a single JSON-RPC request."""
        method = request.get("method", "")
        id_val = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return await self.handle_initialize(params, id_val)
        elif method == "notifications/initialized":
            # Client acknowledges initialization - no response needed
            return None
        elif method == "tools/list":
            return await self.handle_tools_list(params, id_val)
        elif method == "tools/call":
            return await self.handle_tools_call(params, id_val)
        elif method == "ping":
            return _json_rpc_response(id_val, result={})
        else:
            return _json_rpc_response(
                id_val,
                error={"code": -32601, "message": f"Method not found: {method}"},
            )

    async def run(self):
        """Run the MCP server over stdio."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(
            lambda: protocol, sys.stdin
        )

        writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())
        self._writer = writer

        while True:
            try:
                line = await reader.readline()
                if not line:
                    break

                line = line.decode("utf-8").strip()
                if not line:
                    continue

                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    continue

                response = await self.handle_request(request)
                if response is not None:
                    writer.write((response + "\n").encode("utf-8"))
                    await writer.drain()

            except Exception:
                break


def main():
    """Entry point for running as MCP server."""
    # HITS_DATA_PATH env var can override, otherwise uses ~/.hits/data/
    data_path = os.environ.get("HITS_DATA_PATH")
    server = HITSMCPServer(data_path=data_path)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
