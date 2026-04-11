"""Main panel window with knowledge tree view."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QScrollArea, QFrame, QMessageBox, QStackedWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ..theme.material_dark import Theme
from .tree_view import TreeView
from .timeline import TimelineView


class PanelWindow(QWidget):
    def __init__(self, config: dict, settings: dict):
        super().__init__()
        self.config = config
        self.settings = settings
        self._setup_window()
        self._build_ui()
    
    def _setup_window(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background:transparent;")
    
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        
        container = QWidget()
        container.setObjectName("panel_container")
        container.setStyleSheet(f"""
            #panel_container {{
                background: {Theme.COLORS['surface']};
                border-radius: 10px;
            }}
        """)
        outer.addWidget(container)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(0)
        
        header = self._build_header()
        layout.addWidget(header)
        layout.addSpacing(8)
        
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background:transparent;")
        
        self.tree_view = TreeView(self.config)
        self.timeline_view = TimelineView(self.config)
        
        self.stack.addWidget(self.tree_view)
        self.stack.addWidget(self.timeline_view)
        layout.addWidget(self.stack)
        
        layout.addSpacing(6)
        bottom = self._build_bottom_bar()
        layout.addWidget(bottom)
    
    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(f"""
            background: qlineardient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {Theme.COLORS['primary_dark']}, stop:1 {Theme.COLORS['primary']});
            border-radius: 10px 10px 0 0;
        """)
        header.setCursor(Qt.SizeAllCursor)
        
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 12, 0)
        
        title = QLabel("🌳  HITS")
        title.setStyleSheet("color:white;font-size:14px;font-weight:700;background:transparent;")
        hl.addWidget(title)
        
        hl.addStretch()
        
        tab_container = QWidget()
        tab_container.setStyleSheet("background:transparent;")
        tab_layout = QHBoxLayout(tab_container)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(2)
        
        self.tab_knowledge = QPushButton("🌳 지식")
        self.tab_timeline = QPushButton("📋 타임라인")
        
        for btn in [self.tab_knowledge, self.tab_timeline]:
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: rgba(255,255,255,0.6);
                    border: none;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.15);
                    color: white;
                }}
            """)
            tab_layout.addWidget(btn)
        
        self.tab_knowledge.clicked.connect(lambda: self._switch_tab(0))
        self.tab_timeline.clicked.connect(lambda: self._switch_tab(1))
        
        self._update_tab_styles(0)
        hl.addWidget(tab_container)
        
        self._drag_pos = None
        header.mousePressEvent = lambda e: setattr(self, '_drag_pos', e.globalPos() - self.frameGeometry().topLeft()) if e.button() == Qt.LeftButton else None
        header.mouseMoveEvent = lambda e: self.move(e.globalPos() - self._drag_pos) if e.buttons() & Qt.LeftButton and hasattr(self, '_drag_pos') and self._drag_pos else None
        header.mouseReleaseEvent = lambda e: setattr(self, '_drag_pos', None)
        
        return header
    
    def _switch_tab(self, index: int):
        self.stack.setCurrentIndex(index)
        self._update_tab_styles(index)
        if index == 1:
            self.timeline_view.refresh()
    
    def _update_tab_styles(self, active_index: int):
        active_style = f"""
            QPushButton {{
                background: rgba(255,255,255,0.2);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background: transparent;
                color: rgba(255,255,255,0.6);
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.15);
                color: white;
            }}
        """
        
        self.tab_knowledge.setStyleSheet(active_style if active_index == 0 else inactive_style)
        self.tab_timeline.setStyleSheet(active_style if active_index == 1 else inactive_style)
    
    def _build_bottom_bar(self) -> QWidget:
        bottom = QWidget()
        bottom.setStyleSheet(f"background:{Theme.COLORS['surface2']};border-radius:8px;margin:0 10px;")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(8, 4, 8, 4)
        bl.setSpacing(4)
        
        def small_btn(text: str, danger: bool = False) -> QPushButton:
            b = QPushButton(text)
            b.setFixedHeight(28)
            hover_bg = Theme.COLORS['danger'] if danger else Theme.COLORS['surface3']
            b.setStyleSheet(f"""
                QPushButton {{background:transparent;color:{Theme.COLORS['on_surface_low']};
                    border:none;font-size:11px;border-radius:4px;padding:0 8px;}}
                QPushButton:hover {{background:{hover_bg};color:{Theme.COLORS['on_surface']};}}
            """)
            b.setCursor(Qt.PointingHandCursor)
            return b
        
        reload_btn = small_btn("↻  새로고침")
        reload_btn.clicked.connect(self._reload)
        bl.addWidget(reload_btn)
        
        bl.addStretch()
        
        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{Theme.COLORS['accent']};font-size:10px;background:transparent;")
        bl.addWidget(self.status)
        
        quit_btn = small_btn("✕  종료", danger=True)
        quit_btn.clicked.connect(self._confirm_quit)
        bl.addWidget(quit_btn)
        
        return bottom
    
    def _reload(self):
        current_index = self.stack.currentIndex()
        if current_index == 0:
            self.tree_view.refresh()
        else:
            self.timeline_view.refresh()
        self.status.setText("완료")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.status.setText(""))
    
    def _confirm_quit(self):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("HITS 종료")
        dlg.setText("HITS를 종료하시겠습니까?")
        dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dlg.setDefaultButton(QMessageBox.No)
        dlg.button(QMessageBox.Yes).setText("종료")
        dlg.button(QMessageBox.No).setText("취소")
        
        dlg.setStyleSheet(f"""
            QMessageBox {{
                background: {Theme.COLORS['surface']};
            }}
            QLabel {{
                color: {Theme.COLORS['on_surface']};
                font-size: 13px;
                min-width: 200px;
            }}
            QPushButton {{
                background: {Theme.COLORS['surface2']};
                color: {Theme.COLORS['on_surface']};
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                min-width: 60px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {Theme.COLORS['primary']};
            }}
        """)
        
        if dlg.exec() == QMessageBox.Yes:
            from PySide6.QtWidgets import QApplication
            QApplication.quit()
    
    def reload_config(self):
        self._reload()
