"""Handover dialog - human-readable project handover summary.

Shows a clean, formatted summary that a person (or next AI session)
can read to understand what was done on a project.
"""

import asyncio
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QTextEdit,
    QSizePolicy, QWidget, QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ..theme.material_dark import Theme
from hits_core.storage.file_store import FileStorage
from hits_core.service.handover_service import HandoverService


class HandoverDialog(QDialog):
    def __init__(self, parent=None, project_path: Optional[str] = None):
        super().__init__(parent)
        self._project_path = project_path
        self._service = HandoverService()
        self._summary_text = ""
        
        self._setup_window()
        self._build_ui()
        self._load_handover()
    
    def _setup_window(self):
        self.setWindowTitle("인수인계 요약")
        self.setMinimumSize(480, 520)
        self.setStyleSheet(f"""
            QDialog {{
                background: {Theme.COLORS['surface']};
            }}
        """)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = self._build_header()
        layout.addWidget(header)
        
        # Content
        self.content_area = QTextEdit()
        self.content_area.setReadOnly(True)
        self.content_area.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.content_area.setStyleSheet(f"""
            QTextEdit {{
                background: {Theme.COLORS['surface']};
                color: {Theme.COLORS['on_surface']};
                border: none;
                padding: 16px 20px;
                font-size: 13px;
                line-height: 1.6;
            }}
        """)
        self.content_area.setPlaceholderText("인수인계 데이터를 불러오는 중...")
        layout.addWidget(self.content_area, 1)
        
        # Bottom bar
        bottom = self._build_bottom_bar()
        layout.addWidget(bottom)
    
    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {Theme.COLORS['primary_dark']}, stop:1 {Theme.COLORS['primary']});
        """)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 16, 0)
        
        title = QLabel("📋 인수인계 요약")
        title.setStyleSheet("color:white;font-size:15px;font-weight:700;background:transparent;")
        hl.addWidget(title)
        
        hl.addStretch()
        
        # Project name badge
        if self._project_path:
            name = Path(self._project_path).name
            badge = QLabel(f"📁 {name}")
            badge.setStyleSheet("""
                color:white;font-size:11px;background:rgba(255,255,255,0.15);
                padding:4px 10px;border-radius:4px;
            """)
            hl.addWidget(badge)
        else:
            badge = QLabel("전체 프로젝트")
            badge.setStyleSheet("""
                color:white;font-size:11px;background:rgba(255,255,255,0.15);
                padding:4px 10px;border-radius:4px;
            """)
            hl.addWidget(badge)
        
        return header
    
    def _build_bottom_bar(self) -> QWidget:
        bottom = QWidget()
        bottom.setFixedHeight(48)
        bottom.setStyleSheet(f"background:{Theme.COLORS['surface2']};")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(16, 8, 16, 8)
        
        copy_btn = QPushButton("📋 복사")
        copy_btn.setStyleSheet(Theme.button_style())
        copy_btn.clicked.connect(self._copy_to_clipboard)
        bl.addWidget(copy_btn)
        
        bl.addStretch()
        
        close_btn = QPushButton("닫기")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background:{Theme.COLORS['surface3']};
                color:{Theme.COLORS['on_surface']};
                border:none;
                border-radius:6px;
                padding:8px 20px;
                font-size:12px;
            }}
            QPushButton:hover {{
                background:{Theme.COLORS['primary']};
            }}
        """)
        close_btn.clicked.connect(self.accept)
        bl.addWidget(close_btn)
        
        return bottom
    
    def _load_handover(self):
        try:
            loop = asyncio.new_event_loop()
            if self._project_path:
                summary = loop.run_until_complete(
                    self._service.get_handover(self._project_path)
                )
            else:
                # No specific project - show overview
                summary = loop.run_until_complete(
                    self._service.get_all_handovers()
                )
            loop.close()
            
            self._summary_text = summary.to_text()
            
            # Format as HTML for better readability
            html = self._format_as_html(summary)
            self.content_area.setHtml(html)
            
        except Exception as e:
            self.content_area.setHtml(f"""
                <p style="color:{Theme.COLORS['danger']}">
                    인수인계 데이터를 불러오지 못했습니다.<br>
                    {str(e)}
                </p>
            """)
    
    def _format_as_html(self, summary) -> str:
        """Format handover summary as readable HTML."""
        bg = Theme.COLORS['surface']
        text = Theme.COLORS['on_surface']
        med = Theme.COLORS['on_surface_med']
        low = Theme.COLORS['on_surface_low']
        accent = Theme.COLORS['accent']
        primary = Theme.COLORS['primary']
        warning = Theme.COLORS['warning']
        success = Theme.COLORS['success']
        danger = Theme.COLORS['danger']
        
        html_parts = []
        
        # Project header
        html_parts.append(f"""
            <div style="margin-bottom:16px;">
                <h2 style="color:{accent};font-size:16px;margin:0 0 4px 0;">
                    {summary.project_name}
                </h2>
                <span style="color:{low};font-size:11px;">
                    {summary.project_path}
                </span>
        """)
        
        if summary.git_branch:
            html_parts.append(f"""
                <br><span style="color:{primary};font-size:11px;">
                    🔀 {summary.git_branch}
                </span>
                <span style="color:{low};font-size:11px;">
                    ({summary.git_status or '상태 unknown'})
                </span>
            """)
        
        html_parts.append(f"""
                <br><span style="color:{low};font-size:10px;">
                    생성: {summary.generated_at.strftime('%Y-%m-%d %H:%M')}
                </span>
            </div>
        """)
        
        # Session history
        if summary.session_history:
            html_parts.append(f"""
                <div style="margin-bottom:12px;">
                    <h3 style="color:{accent};font-size:12px;margin:0 0 6px 0;">
                        👥 세션 이력
                    </h3>
            """)
            for session in summary.session_history:
                tool = session.get("performed_by", "unknown")
                count = session.get("log_count", 0)
                last = session.get("last_activity", "")[:16]
                
                tool_color = {
                    "opencode": "#4FC3F7",
                    "claude": "#FF8A65",
                    "cursor": "#AED581",
                }.get(tool, accent)
                
                html_parts.append(f"""
                    <div style="margin:2px 0;padding:4px 8px;background:rgba(255,255,255,0.03);border-radius:4px;">
                        <span style="color:{tool_color};font-weight:600;font-size:11px;">{tool}</span>
                        <span style="color:{med};font-size:11px;">
                            &nbsp;· {count}건 &nbsp;· 마지막: {last}
                        </span>
                    </div>
                """)
            html_parts.append("</div>")
        
        # Key decisions
        if summary.key_decisions:
            html_parts.append(f"""
                <div style="margin-bottom:12px;">
                    <h3 style="color:{warning};font-size:12px;margin:0 0 6px 0;">
                        ★ 주요 결정 사항
                    </h3>
            """)
            for decision in summary.key_decisions:
                html_parts.append(f"""
                    <div style="margin:2px 0;padding:6px 10px;
                        background:rgba(255,167,38,0.08);border-left:3px solid {warning};
                        border-radius:0 4px 4px 0;color:{text};font-size:12px;">
                        {decision}
                    </div>
                """)
            html_parts.append("</div>")
        
        # Pending items
        if summary.pending_items:
            html_parts.append(f"""
                <div style="margin-bottom:12px;">
                    <h3 style="color:{danger};font-size:12px;margin:0 0 6px 0;">
                        ⚠ 미완료 / 후속 작업
                    </h3>
            """)
            for item in summary.pending_items:
                html_parts.append(f"""
                    <div style="margin:2px 0;padding:6px 10px;
                        background:rgba(239,83,80,0.08);border-left:3px solid {danger};
                        border-radius:0 4px 4px 0;color:{text};font-size:12px;">
                        {item}
                    </div>
                """)
            html_parts.append("</div>")
        
        # Files modified
        if summary.files_modified:
            unique_files = sorted(set(summary.files_modified))
            html_parts.append(f"""
                <div style="margin-bottom:12px;">
                    <h3 style="color:{success};font-size:12px;margin:0 0 6px 0;">
                        📄 수정된 파일 ({len(unique_files)}개)
                    </h3>
                    <div style="padding:6px 10px;background:rgba(102,187,106,0.06);
                        border-radius:4px;">
            """)
            for f in unique_files[:20]:
                html_parts.append(f"""
                    <div style="color:{med};font-size:11px;font-family:monospace;">
                        &nbsp;· {f}
                    </div>
                """)
            if len(unique_files) > 20:
                html_parts.append(f"""
                    <div style="color:{low};font-size:11px;">
                        &nbsp;... 외 {len(unique_files) - 20}개
                    </div>
                """)
            html_parts.append("</div></div>")
        
        # Recent work logs
        if summary.recent_logs:
            html_parts.append(f"""
                <div style="margin-bottom:12px;">
                    <h3 style="color:{accent};font-size:12px;margin:0 0 6px 0;">
                        📝 최근 작업 기록
                    </h3>
            """)
            for log in summary.recent_logs[:10]:
                ts = log.performed_at.strftime("%m/%d %H:%M")
                tool = log.performed_by
                text = log.request_text or log.context or "(내용 없음)"
                
                tool_color = {
                    "opencode": "#4FC3F7",
                    "claude": "#FF8A65",
                    "cursor": "#AED581",
                }.get(tool, accent)
                
                tags_html = ""
                if log.tags:
                    tag_spans = []
                    for tag in log.tags[:3]:
                        tag_spans.append(
                            f'<span style="background:rgba(21,101,192,0.2);'
                            f'color:{primary};padding:1px 5px;border-radius:3px;'
                            f'font-size:9px;">#{tag}</span>'
                        )
                    tags_html = " ".join(tag_spans)
                
                html_parts.append(f"""
                    <div style="margin:3px 0;padding:6px 10px;
                        background:rgba(255,255,255,0.02);border-radius:4px;">
                        <span style="color:{low};font-size:10px;">[{ts}]</span>
                        <span style="color:{tool_color};font-size:10px;font-weight:600;">
                            ({tool})
                        </span>
                        <span style="color:{text};font-size:11px;">
                            {text[:80]}
                        </span>
                        {'&nbsp;' + tags_html if tags_html else ''}
                    </div>
                """)
            html_parts.append("</div>")
        
        # Empty state
        if not summary.session_history and not summary.recent_logs:
            html_parts.append(f"""
                <div style="text-align:center;padding:40px 20px;">
                    <p style="color:{low};font-size:14px;">
                        📭 기록된 작업이 없습니다
                    </p>
                    <p style="color:{low};font-size:11px;">
                        AI 세션에서 작업을 수행하면 자동으로 기록됩니다.
                    </p>
                </div>
            """)
        
        return f"""
            <div style="background:{bg};color:{text};font-family:sans-serif;">
                {''.join(html_parts)}
            </div>
        """
    
    def _copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self._summary_text)
        
        # Visual feedback
        self.content_area.setHtml(
            self.content_area.toHtml() +
            f'<p style="color:{Theme.COLORS["success"]};font-size:11px;text-align:center;">'
            f'✅ 클립보드에 복사되었습니다</p>'
        )
