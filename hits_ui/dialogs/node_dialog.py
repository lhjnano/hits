"""Node add/edit dialog for knowledge tree."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QPushButton,
    QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QInputMethodEvent

from ..theme.material_dark import Theme


class NodeDialog(QDialog):
    LAYERS = [
        ("why", "🎯 WHY (의도)"),
        ("how", "⚙️ HOW (논리)"),
        ("what", "📄 WHAT (실행)"),
    ]
    
    ACTION_TYPES = [
        ("url", "URL"),
        ("shell", "Shell"),
    ]

    def __init__(
        self,
        parent=None,
        category_name: str = "",
        node_data: dict = None,
        is_edit: bool = False,
    ):
        super().__init__(parent)
        self.category_name = category_name
        self.node_data = node_data or {}
        self.is_edit = is_edit
        self.result_data = None
        
        self._setup_dialog()
        self._build_ui()
        self._load_data()
    
    def _setup_dialog(self):
        title = "노드 편집" if self.is_edit else "노드 추가"
        self.setWindowTitle(title)
        self.setFixedWidth(400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.COLORS['surface1']};
                border: 1px solid {Theme.COLORS['border']};
                border-radius: 12px;
            }}
            QLabel {{
                color: {Theme.COLORS['on_surface']};
                font-size: 12px;
                background: transparent;
            }}
            QLineEdit {{
                background-color: {Theme.COLORS['surface2']};
                color: {Theme.COLORS['on_surface']};
                border: 1px solid {Theme.COLORS['border']};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {Theme.COLORS['accent']};
            }}
            QComboBox {{
                background-color: {Theme.COLORS['surface2']};
                color: {Theme.COLORS['on_surface']};
                border: 1px solid {Theme.COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                min-height: 28px;
            }}
            QComboBox:hover {{
                border-color: {Theme.COLORS['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Theme.COLORS['surface2']};
                color: {Theme.COLORS['on_surface']};
                selection-background-color: {Theme.COLORS['primary']};
                border: 1px solid {Theme.COLORS['border']};
                border-radius: 4px;
            }}
            QCheckBox {{
                color: {Theme.COLORS['on_surface']};
                font-size: 12px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid {Theme.COLORS['border']};
                background: {Theme.COLORS['surface2']};
            }}
            QCheckBox::indicator:checked {{
                background: {Theme.COLORS['accent']};
                border-color: {Theme.COLORS['accent']};
            }}
            QPushButton {{
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: 600;
            }}
        """)
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        header_layout = QHBoxLayout()
        title_text = "노드 편집" if self.is_edit else "노드 추가"
        title_label = QLabel(title_text)
        title_label.setStyleSheet(f"font-size:16px;font-weight:600;color:{Theme.COLORS['accent']};")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                color:{Theme.COLORS['on_surface_low']};
                border:none;
                font-size:14px;
            }}
            QPushButton:hover {{
                color:{Theme.COLORS['error']};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)
        layout.addLayout(header_layout)
        
        if self.category_name:
            cat_label = QLabel(f"📁 카테고리: {self.category_name}")
            cat_label.setStyleSheet(f"color:{Theme.COLORS['on_surface_low']};font-size:11px;")
            layout.addWidget(cat_label)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("노드 이름")
        self.name_input.setInputMethodHints(Qt.InputMethodHint.ImhPreferLatin)
        layout.addWidget(self._create_field("이름", self.name_input))
        
        self.layer_combo = QComboBox()
        for value, label in self.LAYERS:
            self.layer_combo.addItem(label, value)
        layout.addWidget(self._create_field("레이어", self.layer_combo))
        
        self.action_input = QLineEdit()
        self.action_input.setPlaceholderText("URL 또는 Shell 명령어")
        layout.addWidget(self._create_field("액션", self.action_input))
        
        self.action_type_combo = QComboBox()
        for value, label in self.ACTION_TYPES:
            self.action_type_combo.addItem(label, value)
        layout.addWidget(self._create_field("액션 타입", self.action_type_combo))
        
        self.negative_check = QCheckBox("부정 경로 (Negative Path)")
        self.negative_check.setToolTip("이 옵션을 선택하면 해당 노드가 부정 경로로 표시됩니다.")
        layout.addWidget(self.negative_check)
        
        layout.addSpacing(8)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        cancel_btn = QPushButton("취소")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background:{Theme.COLORS['surface3']};
                color:{Theme.COLORS['on_surface']};
                border:none;
            }}
            QPushButton:hover {{
                background:{Theme.COLORS['surface2']};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("저장")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background:{Theme.COLORS['accent']};
                color:white;
                border:none;
            }}
            QPushButton:hover {{
                background:{Theme.COLORS['primary']};
            }}
        """)
        save_btn.clicked.connect(self._on_save)
        save_btn.setDefault(True)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _create_field(self, label_text: str, widget: QWidget) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        vlayout = QVBoxLayout(container)
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.setSpacing(6)
        
        label = QLabel(label_text)
        label.setStyleSheet(f"color:{Theme.COLORS['on_surface_med']};font-size:11px;")
        vlayout.addWidget(label)
        vlayout.addWidget(widget)
        
        return container
    
    def _load_data(self):
        if self.node_data:
            self.name_input.setText(self.node_data.get("name", ""))
            
            layer = self.node_data.get("layer", "what")
            for i, (value, _) in enumerate(self.LAYERS):
                if value == layer:
                    self.layer_combo.setCurrentIndex(i)
                    break
            
            self.action_input.setText(self.node_data.get("action", ""))
            
            action_type = self.node_data.get("type", "url")
            for i, (value, _) in enumerate(self.ACTION_TYPES):
                if value == action_type:
                    self.action_type_combo.setCurrentIndex(i)
                    break
            
            self.negative_check.setChecked(self.node_data.get("negative_path", False))
    
    def _on_save(self):
        name = self.name_input.text().strip()
        if not name:
            self.name_input.setFocus()
            return
        
        self.result_data = {
            "name": name,
            "layer": self.layer_combo.currentData(),
            "type": self.action_type_combo.currentData(),
            "action": self.action_input.text().strip(),
            "negative_path": self.negative_check.isChecked(),
        }
        self.accept()
    
    def inputMethodEvent(self, event: QInputMethodEvent):
        if event.commitString():
            self.name_input.insert(event.commitString())
        super().inputMethodEvent(event)
    
    def get_result(self) -> dict:
        return self.result_data
