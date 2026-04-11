"""Context card widget for displaying work log details."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

from ..theme.material_dark import Theme
from ..dialogs.work_log_dialog import WorkLogDialog
from hits_core.models.work_log import WorkLog, WorkLogSource, WorkLogResultType
from hits_core.platform.actions import PlatformAction


SOURCE_ICONS = {
    WorkLogSource.GIT: "📝",
    WorkLogSource.SHELL: "⌨️",
    WorkLogSource.LINK_CLICK: "🔗",
    WorkLogSource.SHELL_EXEC: "⚡",
    WorkLogSource.AI_SESSION: "🤖",
    WorkLogSource.MANUAL: "✏️",
    WorkLogSource.BROWSER_HISTORY: "🌐",
}

RESULT_ICONS = {
    WorkLogResultType.COMMIT: "📦",
    WorkLogResultType.PR: "🔀",
    WorkLogResultType.FILE: "📄",
    WorkLogResultType.URL: "🌐",
    WorkLogResultType.COMMAND: "▶️",
    WorkLogResultType.AI_RESPONSE: "💬",
    WorkLogResultType.NONE: "·",
}


class ContextCard(QWidget):
    def __init__(self, log: WorkLog, show_project: bool = False, parent=None):
        super().__init__(parent)
        self.log = log
        self.show_project = show_project
        self._edit_btn = None
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        
        header = self._build_header()
        layout.addWidget(header)
        
        if self.log.request_text:
            body = QLabel(self.log.request_text[:150])
            body.setStyleSheet(f"""
                color:{Theme.COLORS['on_surface']};
                font-size:12px;
                background:transparent;
                line-height:1.4;
            """)
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            body.setAttribute(Qt.WA_InputMethodEnabled, True)
            layout.addWidget(body)
        
        if self.log.context:
            context = QLabel(f"💡 {self.log.context[:100]}")
            context.setStyleSheet(f"""
                color:{Theme.COLORS['on_surface_med']};
                font-size:11px;
                background:transparent;
                font-style:italic;
            """)
            context.setWordWrap(True)
            context.setAttribute(Qt.WA_InputMethodEnabled, True)
            layout.addWidget(context)
        
        if self.log.tags:
            tags_widget = self._build_tags()
            layout.addWidget(tags_widget)
        
        self.setStyleSheet(f"""
            QWidget {{
                background:{Theme.COLORS['surface2']};
                border-radius:8px;
            }}
            QWidget:hover {{
                background:{Theme.COLORS['surface3']};
            }}
        """)
        
        self.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.setCursor(Qt.PointingHandCursor)
    
    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background:transparent;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        
        source_icon = SOURCE_ICONS.get(self.log.source, "·")
        icon = QLabel(source_icon)
        icon.setStyleSheet("background:transparent;font-size:14px;")
        hl.addWidget(icon)
        
        time_str = self.log.performed_at.strftime("%H:%M")
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"""
            color:{Theme.COLORS['on_surface_low']};
            font-size:10px;
            background:transparent;
        """)
        hl.addWidget(time_label)
        
        by_label = QLabel(self.log.performed_by.split()[0] if self.log.performed_by else "?")
        by_label.setStyleSheet(f"""
            color:{Theme.COLORS['accent']};
            font-size:11px;
            font-weight:600;
            background:transparent;
        """)
        hl.addWidget(by_label)
        
        # Show project name when viewing all projects
        if self.show_project and self.log.project_path:
            from pathlib import Path
            proj_name = Path(self.log.project_path).name
            proj_label = QLabel(f"📁 {proj_name}")
            proj_label.setStyleSheet(f"""
                color:{Theme.COLORS['warning']};
                font-size:10px;
                background:transparent;
            """)
            hl.addWidget(proj_label)
        
        hl.addStretch()
        
        self._edit_btn = QPushButton("✏️")
        self._edit_btn.setFixedSize(24, 24)
        self._edit_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                border:none;
                font-size:12px;
            }}
            QPushButton:hover {{
                background:{Theme.COLORS['primary_dark']};
                border-radius:4px;
            }}
        """)
        self._edit_btn.clicked.connect(self._on_edit)
        self._edit_btn.hide()
        hl.addWidget(self._edit_btn)
        
        result_icon = RESULT_ICONS.get(self.log.result_type, "·")
        if self.log.result_ref:
            result_text = f"{result_icon} {self.log.result_ref[:20]}"
        else:
            result_text = result_icon
        result_label = QLabel(result_text)
        result_label.setStyleSheet(f"""
            color:{Theme.COLORS['on_surface_low']};
            font-size:10px;
            background:transparent;
        """)
        hl.addWidget(result_label)
        
        return header
    
    def enterEvent(self, event):
        if self._edit_btn:
            self._edit_btn.show()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        if self._edit_btn:
            self._edit_btn.hide()
        super().leaveEvent(event)
    
    def _on_edit(self):
        from ..panel.timeline import TimelineView
        dialog = WorkLogDialog(self, self.log)
        if dialog.exec():
            parent = self.parent()
            while parent and not isinstance(parent, TimelineView):
                parent = parent.parent()
            if parent:
                parent.refresh()
    
    def _build_tags(self) -> QWidget:
        tags_widget = QWidget()
        tags_widget.setStyleSheet("background:transparent;")
        tl = QHBoxLayout(tags_widget)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(4)
        
        for tag in self.log.tags[:3]:
            tag_label = QLabel(f"#{tag}")
            tag_label.setStyleSheet(f"""
                color:{Theme.COLORS['primary']};
                font-size:10px;
                background:{Theme.COLORS['primary_dark']};
                padding:2px 6px;
                border-radius:4px;
            """)
            tl.addWidget(tag_label)
        
        tl.addStretch()
        return tags_widget
    
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._execute_action()
    
    def _execute_action(self):
        if self.log.result_type == WorkLogResultType.URL and self.log.result_data:
            url = self.log.result_data.get("url", "")
            if url:
                PlatformAction.open_url(url)
        elif self.log.result_type == WorkLogResultType.COMMIT and self.log.project_path:
            PlatformAction.run_shell(f"cd {self.log.project_path} && git show {self.log.result_ref}")
