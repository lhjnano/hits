"""Knowledge extractor - automatically builds knowledge tree from work logs.

Reads work logs and checkpoints, extracts meaningful knowledge nodes,
auto-categorizes by project, and saves to the knowledge store.

Extraction rules:
- request_text → WHY node (what the user wanted)
- decisions from assistant summary → HOW node (approach/decision)
- files_modified → WHAT nodes (concrete artifacts)
- error patterns → negative_path nodes (what NOT to do)

Deduplication: skips nodes that already exist in the category.
"""

import json
import re
from pathlib import Path
from typing import Optional
from datetime import datetime

from .knowledge_service import KnowledgeService, KnowledgeNode, KnowledgeCategory


class KnowledgeExtractor:
    """Extract knowledge from work logs and populate the knowledge tree."""

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".hits" / "data"
        self.data_dir = data_dir
        self.knowledge_file = data_dir / "knowledge.json"
        self.work_log_dir = data_dir / "work_logs"
        self.checkpoint_dir = data_dir / "checkpoints"
        self.ks = KnowledgeService(data_path=self.knowledge_file)

    def extract_from_work_log(self, log_id: str) -> int:
        """Extract knowledge from a single work log. Returns number of nodes added."""
        log_path = self.work_log_dir / f"{log_id}.json"
        if not log_path.exists():
            return 0

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log = json.load(f)
        except (json.JSONDecodeError, IOError):
            return 0

        return self._extract(log)

    def extract_from_checkpoint(self, project_path: str) -> int:
        """Extract knowledge from the latest checkpoint for a project."""
        cp_dir = self.checkpoint_dir / project_path.replace("/", "_")
        latest_path = cp_dir / "_latest.json"
        
        if not latest_path.exists():
            latest_path = cp_dir / "latest.json"
        
        if not latest_path.exists():
            # Fallback: most recent json file
            candidates = [p for p in cp_dir.glob("*.json")
                          if p.name not in ("latest.json", "_latest.json", "index.json")]
            if candidates:
                latest_path = max(candidates, key=lambda p: p.stat().st_mtime)
            else:
                return 0

        try:
            with open(latest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # If it's a pointer, follow it
            if "file" in data and "id" in data and "purpose" not in data:
                cp_file = Path(data["file"])
                if cp_file.exists():
                    with open(cp_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return 0

        # Convert checkpoint to work_log-like format for extraction
        log = {
            "id": data.get("id", ""),
            "request_text": data.get("purpose", ""),
            "context": data.get("current_state", ""),
            "project_path": data.get("project_path", project_path),
            "performed_by": data.get("performer", "unknown"),
            "files_modified": data.get("files_modified", []),
            "result_data": {
                "last_assistant_message": data.get("current_state", ""),
                "tool_names": data.get("tool_summary", ""),
                "error_type": data.get("error_type", ""),
            },
            "tags": data.get("tags", []),
        }
        return self._extract(log)

    def extract_all_unprocessed(self, limit: int = 50) -> dict:
        """Extract knowledge from all unprocessed work logs.
        Returns {project: nodes_added}."""
        results = {}
        
        # Load processed log IDs
        processed_file = self.data_dir / "knowledge_extracted.json"
        processed = set()
        if processed_file.exists():
            try:
                with open(processed_file, "r") as f:
                    processed = set(json.load(f))
            except:
                pass

        # Get all log IDs from index
        index_file = self.work_log_dir / "index.json"
        if not index_file.exists():
            return results

        try:
            with open(index_file, "r") as f:
                index = json.load(f)
        except:
            return results

        newly_processed = []
        for log_id in index:
            if log_id in processed:
                continue

            count = self.extract_from_work_log(log_id)
            if count > 0:
                # Read the log to get project path
                log_path = self.work_log_dir / f"{log_id}.json"
                try:
                    with open(log_path, "r") as f:
                        log = json.load(f)
                    project = log.get("project_path", "unknown").split("/")[-1]
                    results[project] = results.get(project, 0) + count
                except:
                    results["unknown"] = results.get("unknown", 0) + count

            newly_processed.append(log_id)

        # Save processed IDs
        processed.update(newly_processed)
        try:
            with open(processed_file, "w") as f:
                json.dump(sorted(processed), f)
        except:
            pass

        return results

    def _extract(self, log: dict) -> int:
        """Core extraction logic. Returns number of nodes added."""
        project_path = log.get("project_path", "")
        if not project_path:
            return 0

        project_name = project_path.rstrip("/").split("/")[-1]
        if not project_name:
            return 0

        # Ensure category exists for this project
        category = self.ks.get_category(project_name)
        if category is None:
            self.ks.add_category(project_name, icon="📂")
        
        added = 0
        existing_names = set()
        category = self.ks.get_category(project_name)
        if category:
            existing_names = {item.name for item in category.items}

        # ── WHY: User's intent (from request_text) ──
        request_text = (log.get("request_text") or "").strip()
        if request_text and request_text != "Claude Code session":
            name = f"📋 {request_text[:80]}"
            if name not in existing_names:
                node = KnowledgeNode(
                    name=name,
                    layer="why",
                    type="text",
                    action="",
                )
                if self.ks.add_node(project_name, node):
                    added += 1

        # ── HOW: Key decisions/approaches (from context/assistant summary) ──
        context = (log.get("context") or "").strip()
        result_data = log.get("result_data") or {}
        assistant_msg = result_data.get("last_assistant_message", "")

        # Extract decision-like sentences
        how_text = self._extract_decisions(context or assistant_msg)
        if how_text:
            name = f"🔧 {how_text[:80]}"
            if name not in existing_names:
                node = KnowledgeNode(
                    name=name,
                    layer="how",
                    type="text",
                    action="",
                )
                if self.ks.add_node(project_name, node):
                    added += 1

        # ── WHAT: Files modified ──
        files_modified = log.get("files_modified", [])
        if not files_modified and result_data:
            files_modified = result_data.get("files_modified", [])

        for filepath in files_modified:
            # Only store relative path from project
            rel_path = filepath
            if project_path in filepath:
                rel_path = filepath.replace(project_path, "").lstrip("/")
            
            name = f"📄 {rel_path}"
            if name not in existing_names:
                node = KnowledgeNode(
                    name=name,
                    layer="what",
                    type="file",
                    action=filepath,
                )
                if self.ks.add_node(project_name, node):
                    added += 1

        # ── Negative path: error patterns ──
        error_type = result_data.get("error_type", "")
        if error_type and error_type not in ("", "none"):
            name = f"🚫 Error: {error_type}"
            if name not in existing_names:
                node = KnowledgeNode(
                    name=name,
                    layer="what",
                    type="text",
                    action="",
                    negative_path=True,
                )
                if self.ks.add_node(project_name, node):
                    added += 1

        # ── Tool usage patterns (aggregate) ──
        tool_names = result_data.get("tool_names", "")
        if tool_names:
            # Extract top tools
            tools = []
            for line in tool_names.strip().split("\n"):
                line = line.strip()
                if line:
                    # Parse "ToolName(count)" format
                    match = re.match(r"(\w+)\((\d+)\)", line)
                    if match:
                        tools.append((match.group(1), int(match.group(2))))
            
            if tools:
                top_tools = sorted(tools, key=lambda x: -x[1])[:5]
                tool_summary = ", ".join(f"{t}({c})" for t, c in top_tools)
                name = f"⚡ Tools: {tool_summary}"
                if name not in existing_names:
                    node = KnowledgeNode(
                        name=name,
                        layer="what",
                        type="text",
                        action="",
                    )
                    if self.ks.add_node(project_name, node):
                        added += 1

        return added

    def _extract_decisions(self, text: str) -> str:
        """Extract key decision or approach from text."""
        if not text:
            return ""

        # Try to find sentences with decision-like keywords
        decision_keywords = [
            "수정", "변경", "추가", "제거", "삭제", "적용",
            "fix", "change", "update", "add", "remove", "implement",
            "refactor", "rewrite", "configure", "enable", "disable",
        ]

        lines = text.split("\n")
        for line in lines:
            line = line.strip().strip("-•*→")
            if not line or len(line) < 10:
                continue

            # Check if line contains a decision keyword
            line_lower = line.lower()
            if any(kw in line_lower for kw in decision_keywords):
                # Clean up and return first match
                clean = re.sub(r'[`#|]', '', line).strip()
                if len(clean) > 10:
                    return clean[:200]

        # Fallback: first substantive line
        for line in lines:
            line = line.strip().strip("-•*→")
            if len(line) > 20:
                clean = re.sub(r'[`#|]', '', line).strip()
                return clean[:200]

        return text[:200]
