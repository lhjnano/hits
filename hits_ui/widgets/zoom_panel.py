"""Zoom-in detail panel for on-demand knowledge exploration."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit
)
from PySide6.QtCore import Qt, Signal

from ..theme.material_dark import Theme


class ZoomPanel(QWidget):
    ai_analysis_requested = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_node_id = None
        self._setup_window()
        self._build_ui()
    
    def _setup_window(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(400, 500)
    
    def _build_ui(self):
        container = QWidget(self)
        container.setGeometry(0, 0, 400, 500)
        container.setStyleSheet(f"""
            QWidget {{
                background: {Theme.COLORS['surface']};
                border-radius: 10px;
                border: 1px solid {Theme.COLORS['divider']};
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)
        
        header = QHBoxLayout()
        self.title_label = QLabel("상세 보기")
        self.title_label.setStyleSheet(f"color:{Theme.COLORS['on_surface']};font-size:16px;font-weight:700;")
        header.addWidget(self.title_label, 1)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton {{background:transparent;color:{Theme.COLORS['on_surface_low']};border:none;border-radius:4px;}}
            QPushButton:hover {{background:{Theme.COLORS['surface3']};color:{Theme.COLORS['on_surface']};}}
        """)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        layout.addLayout(header)
        
        self.path_label = QLabel("")
        self.path_label.setStyleSheet(f"color:{Theme.COLORS['on_surface_low']};font-size:11px;")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)
        
        self.layer_indicator = QLabel("")
        self.layer_indicator.setStyleSheet(f"""
            background:{Theme.COLORS['primary']};color:white;
            font-size:10px;font-weight:600;border-radius:3px;
            padding:2px 8px;
        """)
        layout.addWidget(self.layer_indicator)
        
        self.content = QTextEdit()
        self.content.setReadOnly(True)
        self.content.setStyleSheet(f"""
            QTextEdit {{
                background:{Theme.COLORS['surface2']};
                color:{Theme.COLORS['on_surface']};
                border:1px solid {Theme.COLORS['divider']};
                border-radius:6px;
                padding:8px;
                font-size:12px;
            }}
        """)
        layout.addWidget(self.content, 1)
        
        self.tokens_label = QLabel("토큰 절약: 0")
        self.tokens_label.setStyleSheet(f"color:{Theme.COLORS['accent']};font-size:11px;")
        layout.addWidget(self.tokens_label)
        
        btn_row = QHBoxLayout()
        
        ai_btn = QPushButton("🤖 AI 분석")
        ai_btn.setStyleSheet(f"""
            QPushButton {{
                background:{Theme.COLORS['primary']};color:white;
                border:none;border-radius:6px;padding:8px 16px;font-size:12px;
            }}
            QPushButton:hover {{background:{Theme.COLORS['primary_light']};}}
        """)
        ai_btn.clicked.connect(self._on_ai_request)
        btn_row.addWidget(ai_btn)
        
        exec_btn = QPushButton("▶ 실행")
        exec_btn.setStyleSheet(f"""
            QPushButton {{
                background:{Theme.COLORS['surface3']};color:{Theme.COLORS['on_surface']};
                border:none;border-radius:6px;padding:8px 16px;font-size:12px;
            }}
            QPushButton:hover {{background:{Theme.COLORS['accent']};color:white;}}
        """)
        btn_row.addWidget(exec_btn)
        
        layout.addLayout(btn_row)
    
    def show_node(self, node_data: dict):
        self.current_node_id = node_data.get("id")
        self.title_label.setText(node_data.get("title", "상세 보기"))
        
        path = node_data.get("path", [])
        self.path_label.setText(" → ".join(path) if path else "")
        
        layer = node_data.get("layer", "what").upper()
        self.layer_indicator.setText(f"  {layer}  ")
        
        self.content.setPlainText(node_data.get("description", "상세 내용이 없습니다."))
        
        tokens = node_data.get("tokens_saved", 0)
        self.tokens_label.setText(f"토큰 절약: {tokens}")
        
        self.show()
    
    def _on_ai_request(self):
        if self.current_node_id:
            self.ai_analysis_requested.emit(self.current_node_id)
