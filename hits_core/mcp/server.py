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
            else:
                return _json_rpc_response(
                    id_val,
                    error={"code": -32601, "message": f"Unknown tool: {tool_name}"},
                )

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
                f"✅ 작업 기록 완료\n"
                f"  ID: {log.id}\n"
                f"  프로젝트: {project_path}\n"
                f"  수행자: {performed_by}\n"
                f"  요약: {log.request_text}"
            )
        else:
            return _tool_result("❌ 작업 기록 실패")

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
            return _tool_result(f"검색 결과 없음: '{query}' (프로젝트: {project_path})")

        lines = [f"검색 결과: '{query}' ({len(logs)}건)\n"]
        for log in logs:
            ts = log.performed_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{ts}] ({log.performed_by}) {log.request_text or log.context}")
            if log.tags:
                lines.append(f"  tags: {', '.join(log.tags)}")

        return _tool_result("\n".join(lines))

    async def _tool_list_projects(self, args: dict) -> list[dict]:
        projects = await self.handover_service.list_projects()

        if not projects:
            return _tool_result("기록된 프로젝트가 없습니다.")

        lines = [f"프로젝트 목록 ({len(projects)}개)\n"]
        for p in projects:
            name = Path(p["project_path"]).name
            logs = p.get("total_logs", 0)
            last = p.get("last_activity", "N/A")
            performers = ", ".join(p.get("performers", {}).keys())
            lines.append(f"  {name}: {logs}건 (마지막: {last}) [{performers}]")

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
            return _tool_result(f"최근 작업 없음 (프로젝트: {project_path})")

        lines = [f"최근 작업 ({len(logs)}건)\n"]
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
            f"🚨 시그널 전송 완료\n"
            f"  ID: {signal.id}\n"
            f"  {signal.sender} → {signal.recipient}\n"
            f"  유형: {signal.signal_type}\n"
            f"  우선순위: {signal.priority}\n"
            f"  프로젝트: {signal.project_path}\n"
            f"  요약: {signal.summary}\n"
            f"\n상대방 AI는 hits_signal_check() 또는 훅 스크립트로 감지합니다."
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
            return _tool_result(f"대기 중인 시그널 없음 (recipient: {recipient}, project: {project_path})")

        lines = [f"📬 대기 중인 시그널 ({len(signals)}개)\n"]
        for sig in signals:
            ts = sig.created_at.strftime("%m/%d %H:%M")
            priority_icon = {"urgent": "🔴", "high": "🟡"}.get(sig.priority, "🟢")
            lines.append(f"  {priority_icon} [{ts}] {sig.sender} → {sig.recipient}")
            lines.append(f"     ID: {sig.id}")
            lines.append(f"     유형: {sig.signal_type}")
            lines.append(f"     요약: {sig.summary}")
            if sig.pending_items:
                lines.append(f"     미완료: {', '.join(sig.pending_items[:3])}")
            lines.append("")

        lines.append("hits_signal_consume(signal_id, consumed_by)로 확인 가능")
        return _tool_result("\n".join(lines))

    async def _tool_signal_consume(self, args: dict) -> list[dict]:
        signal_id = args.get("signal_id", "")
        consumed_by = args.get("consumed_by", "unknown")

        signal = await self.signal_service.consume_signal(
            signal_id=signal_id,
            consumed_by=consumed_by,
        )

        if not signal:
            return _tool_result(f"❌ 시그널을 찾을 수 없음: {signal_id}")

        return _tool_result(
            f"✅ 시그널 확인 완료\n"
            f"  ID: {signal.id}\n"
            f"  {signal.sender} → {consumed_by}\n"
            f"  상태: consumed"
        )

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
