"""Timeline view for work logs with project-scoped handover."""

import json
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QFrame, QLineEdit, QPushButton,
    QComboBox, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer

from ..theme.material_dark import Theme
from ..widgets.context_card import ContextCard
from ..dialogs.work_log_dialog import WorkLogDialog
from hits_core.models.work_log import WorkLog
from hits_core.storage.file_store import FileStorage


class TimelineView(QWidget):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self._storage = FileStorage()  # centralized ~/.hits/data/
        self._logs: list[WorkLog] = []
        self._search_query = ""
        self._selected_project: Optional[str] = None
        
        self.setStyleSheet("background:transparent;")
        self._build_ui()
        
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._load_data)
        self._refresh_timer.start(60000)
    
    def _build_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 6, 0)
        self.layout.setSpacing(8)
        
        search_bar = self._build_search_bar()
        self.layout.addWidget(search_bar)
        
        # Project selector
        project_bar = self._build_project_selector()
        self.layout.addWidget(project_bar)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{border:none;background:transparent;}}
            QScrollBar:vertical {{background:{Theme.COLORS['surface2']};width:4px;border-radius:2px;}}
            QScrollBar::handle:vertical {{background:{Theme.COLORS['primary']};border-radius:2px;min-height:20px;}}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height:0;}}
        """)
        
        self.content = QWidget()
        self.content.setStyleSheet("background:transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(4)
        
        scroll.setWidget(self.content)
        self.layout.addWidget(scroll)
        
        QTimer.singleShot(100, self._load_data)
    
    def _build_search_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"background:{Theme.COLORS['surface2']};border-radius:8px;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 6, 12, 6)
        
        icon = QLabel("🔍")
        icon.setStyleSheet("background:transparent;")
        bl.addWidget(icon)
        
        self.search_input = QLineEdit()
        self.search_input.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.search_input.setPlaceholderText("작업 기록 검색...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background:transparent;
                border:none;
                color:{Theme.COLORS['on_surface']};
                font-size:12px;
            }}
            QLineEdit::placeholder {{
                color:{Theme.COLORS['on_surface_low']};
            }}
        """)
        self.search_input.textChanged.connect(self._on_search)
        bl.addWidget(self.search_input, 1)
        
        add_btn = QPushButton("➕ 추가")
        add_btn.setStyleSheet(Theme.button_style())
        add_btn.clicked.connect(self._on_add_log)
        bl.addWidget(add_btn)
        
        bar.setFixedHeight(36)
        return bar
    
    def _build_project_selector(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"background:{Theme.COLORS['surface2']};border-radius:8px;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 4, 12, 4)
        
        icon = QLabel("📁")
        icon.setStyleSheet("background:transparent;font-size:12px;")
        bl.addWidget(icon)
        
        self.project_combo = QComboBox()
        self.project_combo.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.project_combo.addItem("전체 프로젝트", None)
        self.project_combo.setStyleSheet(f"""
            QComboBox {{
                background:transparent;
                border:none;
                color:{Theme.COLORS['on_surface']};
                font-size:11px;
                padding:2px 4px;
                min-width: 100px;
            }}
            QComboBox::drop-down {{
                border:none;
                width:16px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {Theme.COLORS['on_surface_low']};
                margin-right: 4px;
            }}
            QComboBox QAbstractItemView {{
                background:{Theme.COLORS['surface']};
                color:{Theme.COLORS['on_surface']};
                border: 1px solid {Theme.COLORS['divider']};
                selection-background-color:{Theme.COLORS['primary']};
                font-size:11px;
            }}
        """)
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        bl.addWidget(self.project_combo, 1)
        
        # Handover summary button
        handover_btn = QPushButton("📋 인수인계")
        handover_btn.setFixedHeight(24)
        handover_btn.setStyleSheet(f"""
            QPushButton {{
                background:{Theme.COLORS['accent']};
                color:#1A1A2E;
                border:none;
                border-radius:4px;
                padding:2px 8px;
                font-size:10px;
                font-weight:600;
            }}
            QPushButton:hover {{
                background:#26C6DA;
            }}
        """)
        handover_btn.clicked.connect(self._show_handover)
        bl.addWidget(handover_btn)
        
        bar.setFixedHeight(32)
        return bar
    
    def _on_project_changed(self, index: int):
        self._selected_project = self.project_combo.itemData(index)
        self._load_data()
    
    def _on_add_log(self):
        dialog = WorkLogDialog(self)
        if dialog.exec():
            self._load_data()
    
    def _on_search(self, text: str):
        self._search_query = text.lower()
        self._render_logs()
    
    def _load_data(self):
        import asyncio
        
        # Update project list
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in a Qt event loop, use run_coroutine won't work
                # Fall back to synchronous file reading
                self._load_data_sync()
                return
        except RuntimeError:
            pass
        
        try:
            loop = asyncio.new_event_loop()
            paths = loop.run_until_complete(self._storage.list_project_paths())
            self._update_project_combo(paths)
            logs = loop.run_until_complete(self._storage.list_work_logs(
                project_path=self._selected_project,
                limit=100,
            ))
            loop.close()
            self._logs = logs
        except Exception:
            self._load_data_sync()
            return
        
        self._render_logs()
    
    def _load_data_sync(self):
        """Synchronous fallback for loading data."""
        work_log_dir = self._storage.work_log_dir
        
        if not work_log_dir.exists():
            self._logs = []
            self._render_logs()
            return
        
        index_file = work_log_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    log_ids = json.load(f)
            except Exception:
                log_ids = [p.stem for p in work_log_dir.glob("*.json") if p.name != "index.json"]
        else:
            log_ids = [p.stem for p in work_log_dir.glob("*.json") if p.name != "index.json"]
        
        # Collect unique project paths
        project_paths: set[str] = set()
        
        logs = []
        for log_id in log_ids:
            log_file = work_log_dir / f"{log_id}.json"
            if not log_file.exists():
                continue
            
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                log = WorkLog.model_validate(data)
                
                if log.project_path:
                    project_paths.add(log.project_path)
                
                if self._selected_project and log.project_path != self._selected_project:
                    continue
                
                logs.append(log)
            except Exception:
                continue
        
        logs.sort(key=lambda x: x.performed_at, reverse=True)
        self._logs = logs[:100]
        
        self._update_project_combo(sorted(project_paths))
        self._render_logs()
    
    def _update_project_combo(self, paths: list[str]):
        """Update project combo box without triggering reload."""
        self.project_combo.blockSignals(True)
        
        current_data = self._selected_project
        
        # Keep "All projects" item, remove others
        while self.project_combo.count() > 1:
            self.project_combo.removeItem(1)
        
        for path in paths:
            name = Path(path).name
            self.project_combo.addItem(f"📁 {name}", path)
        
        # Restore selection
        if current_data:
            for i in range(self.project_combo.count()):
                if self.project_combo.itemData(i) == current_data:
                    self.project_combo.setCurrentIndex(i)
                    break
        
        self.project_combo.blockSignals(False)
    
    def _render_logs(self):
        while self.content_layout.count() > 0:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        filtered = self._logs
        if self._search_query:
            filtered = [
                log for log in self._logs
                if self._search_query in (log.request_text or "").lower()
                or self._search_query in (log.context or "").lower()
                or self._search_query in log.performed_by.lower()
                or self._search_query in " ".join(log.tags).lower()
                or self._search_query in (log.project_path or "").lower()
            ]
        
        if not filtered:
            empty = QLabel("기록된 작업이 없습니다.")
            empty.setStyleSheet(f"""
                color:{Theme.COLORS['on_surface_low']};
                font-size:12px;
                background:transparent;
                padding:20px;
            """)
            empty.setAlignment(Qt.AlignCenter)
            self.content_layout.addWidget(empty)
            self.content_layout.addStretch()
            return
        
        grouped = defaultdict(list)
        for log in filtered:
            date_key = log.performed_at.strftime("%Y-%m-%d")
            grouped[date_key].append(log)
        
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        for date_key in sorted(grouped.keys(), reverse=True):
            logs = grouped[date_key]
            
            if date_key == today:
                label = "오늘"
            elif date_key == yesterday:
                label = "어제"
            else:
                label = date_key
            
            # Show project name in header if viewing all projects
            project_label = ""
            if not self._selected_project:
                projects_in_group = set()
                for log in logs:
                    if log.project_path:
                        projects_in_group.add(Path(log.project_path).name)
                if projects_in_group:
                    project_label = f" ({', '.join(sorted(projects_in_group))})"
            
            header = QLabel(f"📅 {label}{project_label} — {len(logs)}건")
            header.setStyleSheet(f"""
                color:{Theme.COLORS['accent']};
                font-size:11px;
                font-weight:600;
                background:transparent;
                padding:8px 0 4px 0;
            """)
            self.content_layout.addWidget(header)
            
            for log in sorted(logs, key=lambda x: x.performed_at, reverse=True):
                card = ContextCard(log, show_project=not bool(self._selected_project))
                self.content_layout.addWidget(card)
        
        self.content_layout.addStretch()
    
    def _show_handover(self):
        """Show handover summary dialog for the selected project."""
        from ..dialogs.handover_dialog import HandoverDialog
        
        project_path = self._selected_project
        dialog = HandoverDialog(self, project_path=project_path)
        dialog.exec()
    
    def refresh(self):
        self._load_data()
