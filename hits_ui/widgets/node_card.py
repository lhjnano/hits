"""Node card widget for individual knowledge nodes."""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QMenu
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction

from ..theme.material_dark import Theme
from hits_core.collector import HitsActionCollector
from typing import Callable, Optional

_collector: HitsActionCollector | None = None

def set_hits_action_collector(collector: HitsActionCollector):
    global _collector
    _collector = collector

def get_hits_action_collector() -> HitsActionCollector:
    global _collector
    if _collector is None:
        _collector = HitsActionCollector()
    return _collector


LAYER_COLORS = {
    "why": "#FFA726",
    "how": "#66BB6A",
    "what": "#29B6F6",
}

LAYER_ICONS = {
    "why": "🎯",
    "how": "⚙️",
    "what": "●",
}


class NodeCard(QWidget):
    edit_requested = Signal()
    delete_requested = Signal()
    
    def __init__(
        self,
        title: str,
        layer: str = "what",
        action: str = "",
        action_type: str = "url",
        is_negative: bool = False,
        category_name: str = "",
        node_index: int = -1,
        on_edit: Optional[Callable] = None,
        on_delete: Optional[Callable] = None,
    ):
        super().__init__()
        self.layer = layer
        self.action = action
        self.action_type = action_type
        self.is_negative = is_negative
        self._title = title
        self._category_name = category_name
        self._node_index = node_index
        self._on_edit = on_edit
        self._on_delete = on_delete
        
        self._build_ui(title)
    
    def _build_ui(self, title: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(36, 0, 12, 0)
        layout.setSpacing(8)
        
        layer_color = LAYER_COLORS.get(self.layer, "#90A4AE")
        layer_icon = LAYER_ICONS.get(self.layer, "●")
        
        if self.is_negative:
            layer_color = "#EF5350"
            layer_icon = "✗"
        
        icon_label = QLabel(layer_icon)
        icon_label.setStyleSheet(f"color:{layer_color};font-size:10px;background:transparent;")
        icon_label.setFixedWidth(16)
        layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_style = f"color:{Theme.COLORS['on_surface_med']};font-size:12px;background:transparent;"
        if self.is_negative:
            title_style = f"color:#EF5350;font-size:12px;background:transparent;text-decoration:line-through;"
        title_label.setStyleSheet(title_style)
        self._title_label = title_label
        layout.addWidget(title_label, 1)
        
        self.setFixedHeight(34)
        self.setCursor(Qt.PointingHandCursor)
        
        bg_hover = Theme.COLORS['surface3']
        self.setStyleSheet(f"""
            QWidget {{background:transparent;border:none;border-radius:6px;}}
            QWidget:hover {{background:{bg_hover};}}
        """)
        
        self.setToolTip(f"[{self.layer.upper()}] {self.action}")
    
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._execute_action()
        elif e.button() == Qt.RightButton:
            self._show_context_menu(e.pos())
    
    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Theme.COLORS['surface2']};
                color: {Theme.COLORS['on_surface']};
                border: 1px solid {Theme.COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 24px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {Theme.COLORS['primary']};
            }}
        """)
        
        edit_action = QAction("편집", self)
        edit_action.triggered.connect(self._on_edit_click)
        menu.addAction(edit_action)
        
        delete_action = QAction("삭제", self)
        delete_action.triggered.connect(self._on_delete_click)
        menu.addAction(delete_action)
        
        menu.exec(self.mapToGlobal(pos))
    
    def _on_edit_click(self):
        if self._on_edit:
            self._on_edit(self._category_name, self._node_index, self)
        self.edit_requested.emit()
    
    def _on_delete_click(self):
        if self._on_delete:
            self._on_delete(self._category_name, self._node_index, self)
        self.delete_requested.emit()
    
    def _execute_action(self):
        collector = get_hits_action_collector()
        if self.action_type == "url":
            collector.record_link_click(
                url=self.action,
                title=self.toolTip(),
                category=self.layer,
                node_id=f"{self.layer}:{self.action}",
            )
        elif self.action_type == "shell":
            collector.record_shell_exec(
                command=self.action,
                category=self.layer,
                node_id=f"{self.layer}:{self.action}",
            )
        from hits_core.platform.actions import PlatformAction
        PlatformAction.execute(self.action_type, self.action)
    
    def update_from_node(self, node):
        from hits_core.service.knowledge_service import KnowledgeNode
        if isinstance(node, KnowledgeNode):
            self._title = node.name
            self.layer = node.layer
            self.action = node.action
            self.action_type = node.type
            self.is_negative = node.negative_path
        
        self._update_ui()
    
    def _update_ui(self):
        layer_color = LAYER_COLORS.get(self.layer, "#90A4AE")
        layer_icon = LAYER_ICONS.get(self.layer, "●")
        
        if self.is_negative:
            layer_color = "#EF5350"
            layer_icon = "✗"
        
        self._title_label.setText(self._title)
        
        title_style = f"color:{Theme.COLORS['on_surface_med']};font-size:12px;background:transparent;"
        if self.is_negative:
            title_style = f"color:#EF5350;font-size:12px;background:transparent;text-decoration:line-through;"
        self._title_label.setStyleSheet(title_style)
        
        self.setToolTip(f"[{self.layer.upper()}] {self.action}")
