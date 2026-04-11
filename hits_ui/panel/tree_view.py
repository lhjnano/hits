"""Tree view widget for knowledge hierarchy."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt

from ..theme.material_dark import Theme
from ..widgets.node_card import NodeCard
from hits_core.service.knowledge_service import KnowledgeService, KnowledgeNode


LAYER_STYLES = {
    "why": {"icon": "🎯", "color": "#FFA726", "label": "WHY (의도)"},
    "how": {"icon": "⚙️", "color": "#66BB6A", "label": "HOW (논리)"},
    "what": {"icon": "📄", "color": "#29B6F6", "label": "WHAT (실행)"},
}


class TreeView(QWidget):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.knowledge_service = KnowledgeService()
        self._category_widgets = {}
        self._node_callbacks = {}
        self.setStyleSheet("background:transparent;")
        self._build_ui()
    
    def _build_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 6, 0)
        self.layout.setSpacing(6)
        
        self._load_sample_data()
    
    def _load_sample_data(self):
        categories = self.config.get("categories", [])
        
        for cat in categories:
            section = self._create_category_section(cat)
            self.layout.addWidget(section)
        
        self.layout.addStretch()
    
    def _create_category_section(self, category: dict) -> QWidget:
        section = QWidget()
        section.setStyleSheet("background:transparent;")
        section._category_name = category.get("name", "")
        sl = QVBoxLayout(section)
        sl.setContentsMargins(0, 0, 0, 4)
        sl.setSpacing(0)
        
        header = self._create_header(category)
        sl.addWidget(header)
        
        items_widget = QWidget()
        items_widget.setStyleSheet(f"background:{Theme.COLORS['surface2']};border-radius:0 0 8px 8px;")
        il = QVBoxLayout(items_widget)
        il.setContentsMargins(0, 4, 0, 8)
        il.setSpacing(2)
        
        items_widget._item_layout = il
        items_widget._category_name = category.get("name", "")
        
        for idx, item in enumerate(category.get("items", [])):
            layer = item.get("layer", "what")
            card = NodeCard(
                title=item.get("name", ""),
                layer=layer,
                action=item.get("action", ""),
                action_type=item.get("type", "url"),
                is_negative=item.get("negative_path", False),
                category_name=category.get("name", ""),
                node_index=idx,
                on_edit=self._on_node_edit,
                on_delete=self._on_node_delete,
            )
            il.addWidget(card)
        
        items_widget.setVisible(False)
        sl.addWidget(items_widget)
        
        self._category_widgets[category.get("name", "")] = items_widget
        
        header.clicked.connect(lambda checked, w=items_widget: w.setVisible(checked))
        
        return section
    
    def _create_header(self, category: dict) -> "CategoryHeader":
        from ..widgets.ripple_button import CategoryHeader
        
        header = CategoryHeader(
            icon=category.get("icon", "▸"),
            name=category.get("name", "Category"),
            show_add_button=True,
        )
        
        header.add_clicked.connect(lambda: self._on_add_node(category.get("name", "")))
        
        return header
    
    def _on_add_node(self, category_name: str):
        from ..dialogs.node_dialog import NodeDialog
        
        dialog = NodeDialog(
            parent=self,
            category_name=category_name,
            is_edit=False,
        )
        
        if dialog.exec():
            result = dialog.get_result()
            if result:
                self._add_node_to_category(category_name, result)
    
    def _add_node_to_category(self, category_name: str, node_data: dict):
        node = KnowledgeNode(
            name=node_data.get("name", ""),
            layer=node_data.get("layer", "what"),
            type=node_data.get("type", "url"),
            action=node_data.get("action", ""),
            negative_path=node_data.get("negative_path", False),
        )
        
        if self.knowledge_service.add_node(category_name, node):
            self._add_node_card(category_name, node)
            self._update_config()
    
    def _add_node_card(self, category_name: str, node: KnowledgeNode):
        if category_name not in self._category_widgets:
            return
        
        items_widget = self._category_widgets[category_name]
        il = items_widget._item_layout
        
        node_index = il.count()
        
        card = NodeCard(
            title=node.name,
            layer=node.layer,
            action=node.action,
            action_type=node.type,
            is_negative=node.negative_path,
            category_name=category_name,
            node_index=node_index,
            on_edit=self._on_node_edit,
            on_delete=self._on_node_delete,
        )
        il.addWidget(card)
    
    def _on_node_edit(self, category_name: str, node_index: int, card: NodeCard):
        from ..dialogs.node_dialog import NodeDialog
        
        node_data = {
            "name": card._title,
            "layer": card.layer,
            "action": card.action,
            "type": card.action_type,
            "negative_path": card.is_negative,
        }
        
        dialog = NodeDialog(
            parent=self,
            category_name=category_name,
            node_data=node_data,
            is_edit=True,
        )
        
        if dialog.exec():
            result = dialog.get_result()
            if result:
                self._update_node(category_name, node_index, result, card)
    
    def _update_node(self, category_name: str, node_index: int, node_data: dict, card: NodeCard):
        node = KnowledgeNode(
            name=node_data.get("name", ""),
            layer=node_data.get("layer", "what"),
            type=node_data.get("type", "url"),
            action=node_data.get("action", ""),
            negative_path=node_data.get("negative_path", False),
        )
        
        if self.knowledge_service.update_node(category_name, node_index, node):
            card.update_from_node(node)
            self._update_config()
    
    def _on_node_delete(self, category_name: str, node_index: int, card: NodeCard):
        from PySide6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self,
            "노드 삭제",
            f"'{card._title}' 노드를 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.knowledge_service.delete_node(category_name, node_index):
                card.deleteLater()
                self.refresh()
                self._update_config()
    
    def _update_config(self):
        self.config.clear()
        self.config.update(self.knowledge_service.to_config_dict())
    
    def refresh(self):
        while self.layout.count() > 0:
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self._category_widgets.clear()
        self._load_sample_data()
