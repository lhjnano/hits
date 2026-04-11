"""Knowledge tree CRUD service."""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
import shutil


@dataclass
class KnowledgeNode:
    name: str
    layer: str = "what"
    type: str = "url"
    action: str = ""
    negative_path: bool = False

    def to_dict(self) -> dict:
        d = {"name": self.name, "layer": self.layer, "type": self.type, "action": self.action}
        if self.negative_path:
            d["negative_path"] = True
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeNode":
        return cls(
            name=data.get("name", ""),
            layer=data.get("layer", "what"),
            type=data.get("type", "url"),
            action=data.get("action", ""),
            negative_path=data.get("negative_path", False),
        )


@dataclass
class KnowledgeCategory:
    name: str
    icon: str = "📁"
    items: list = None

    def __post_init__(self):
        if self.items is None:
            self.items = []

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "icon": self.icon,
            "items": [item.to_dict() if isinstance(item, KnowledgeNode) else item for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeCategory":
        items = [KnowledgeNode.from_dict(item) if isinstance(item, dict) else item for item in data.get("items", [])]
        return cls(name=data.get("name", ""), icon=data.get("icon", "📁"), items=items)


class KnowledgeService:
    DATA_FILE = Path(__file__).parent.parent.parent / "data" / "knowledge.json"
    BACKUP_SUFFIX = ".bak"

    def __init__(self, data_path: Optional[Path] = None):
        if data_path:
            self.DATA_FILE = Path(data_path)
        self._ensure_data_file()

    def _ensure_data_file(self):
        self.DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not self.DATA_FILE.exists():
            self._save_categories([])

    def _load_categories(self) -> list[KnowledgeCategory]:
        if not self.DATA_FILE.exists():
            return []
        try:
            with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [KnowledgeCategory.from_dict(cat) for cat in data.get("categories", [])]
        except (json.JSONDecodeError, IOError):
            return []

    def _save_categories(self, categories: list[KnowledgeCategory]) -> bool:
        try:
            if self.DATA_FILE.exists():
                shutil.copy(self.DATA_FILE, str(self.DATA_FILE) + self.BACKUP_SUFFIX)
            data = {"categories": [cat.to_dict() for cat in categories]}
            with open(self.DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except IOError:
            return False

    def list_categories(self) -> list[KnowledgeCategory]:
        return self._load_categories()

    def get_category(self, category_name: str) -> Optional[KnowledgeCategory]:
        categories = self._load_categories()
        for cat in categories:
            if cat.name == category_name:
                return cat
        return None

    def add_category(self, name: str, icon: str = "📁") -> Optional[KnowledgeCategory]:
        categories = self._load_categories()
        if any(cat.name == name for cat in categories):
            return None
        new_cat = KnowledgeCategory(name=name, icon=icon)
        categories.append(new_cat)
        if self._save_categories(categories):
            return new_cat
        return None

    def update_category(self, old_name: str, new_name: str, icon: str = None) -> bool:
        categories = self._load_categories()
        for cat in categories:
            if cat.name == old_name:
                cat.name = new_name
                if icon is not None:
                    cat.icon = icon
                return self._save_categories(categories)
        return False

    def delete_category(self, category_name: str) -> bool:
        categories = self._load_categories()
        new_categories = [cat for cat in categories if cat.name != category_name]
        if len(new_categories) == len(categories):
            return False
        return self._save_categories(new_categories)

    def add_node(self, category_name: str, node: KnowledgeNode) -> bool:
        categories = self._load_categories()
        for cat in categories:
            if cat.name == category_name:
                cat.items.append(node)
                return self._save_categories(categories)
        return False

    def update_node(self, category_name: str, node_index: int, node: KnowledgeNode) -> bool:
        categories = self._load_categories()
        for cat in categories:
            if cat.name == category_name:
                if 0 <= node_index < len(cat.items):
                    cat.items[node_index] = node
                    return self._save_categories(categories)
        return False

    def delete_node(self, category_name: str, node_index: int) -> bool:
        categories = self._load_categories()
        for cat in categories:
            if cat.name == category_name:
                if 0 <= node_index < len(cat.items):
                    cat.items.pop(node_index)
                    return self._save_categories(categories)
        return False

    def get_node(self, category_name: str, node_index: int) -> Optional[KnowledgeNode]:
        category = self.get_category(category_name)
        if category and 0 <= node_index < len(category.items):
            return category.items[node_index]
        return None

    def find_node_index(self, category_name: str, node_name: str) -> int:
        category = self.get_category(category_name)
        if category:
            for i, item in enumerate(category.items):
                if item.name == node_name:
                    return i
        return -1

    def to_config_dict(self) -> dict:
        categories = self._load_categories()
        return {"categories": [cat.to_dict() for cat in categories]}
