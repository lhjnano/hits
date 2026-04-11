"""Test UI imports without requiring GUI."""

import pytest
import sys


class TestCoreImports:
    """Test hits_core imports - no GUI required."""
    
    def test_import_models(self):
        from hits_core.models import Node, KnowledgeTree, Workflow
        assert Node is not None
        assert KnowledgeTree is not None
        assert Workflow is not None
    
    def test_import_node(self):
        from hits_core.models.node import Node, NodeLayer, NodeType
        assert Node is not None
        assert NodeLayer is not None
        assert NodeType is not None
    
    def test_import_tree(self):
        from hits_core.models.tree import KnowledgeTree
        assert KnowledgeTree is not None
    
    def test_import_workflow(self):
        from hits_core.models.workflow import Workflow, WorkflowStep
        assert Workflow is not None
        assert WorkflowStep is not None
    
    def test_import_storage(self):
        from hits_core.storage import BaseStorage, RedisStorage, FileStorage
        assert BaseStorage is not None
        assert RedisStorage is not None
        assert FileStorage is not None
    
    def test_import_ai(self):
        from hits_core.ai import SemanticCompressor, SLMFilter, LLMClient
        assert SemanticCompressor is not None
        assert SLMFilter is not None
        assert LLMClient is not None
    
    def test_import_platform(self):
        from hits_core.platform import PlatformAction, is_wsl, get_platform_info
        assert PlatformAction is not None
        assert is_wsl is not None
        assert get_platform_info is not None
    
    def test_import_service(self):
        from hits_core.service import TreeService
        assert TreeService is not None
    
    def test_import_knowledge_service(self):
        from hits_core.service import KnowledgeService, KnowledgeNode, KnowledgeCategory
        assert KnowledgeService is not None
        assert KnowledgeNode is not None
        assert KnowledgeCategory is not None


class TestUIImports:
    """Test hits_ui imports - may require display."""
    
    def test_import_widgets_init(self):
        """Test widgets package __init__ imports."""
        from hits_ui.widgets import RippleButton, CategoryHeader, NodeCard
        assert RippleButton is not None
        assert CategoryHeader is not None
        assert NodeCard is not None
    
    def test_import_node_card(self):
        """Test node_card module import."""
        from hits_ui.widgets.node_card import NodeCard
        assert NodeCard is not None
    
    def test_import_ripple_button(self):
        """Test ripple_button module import."""
        from hits_ui.widgets.ripple_button import RippleButton, CategoryHeader
        assert RippleButton is not None
        assert CategoryHeader is not None
    
    def test_import_theme(self):
        """Test theme module import."""
        from hits_ui.theme import Theme
        assert Theme is not None
    
    def test_import_theme_material_dark(self):
        """Test material_dark theme import."""
        from hits_ui.theme.material_dark import Theme
        assert Theme.COLORS is not None
        assert 'primary' in Theme.COLORS
    
    def test_import_dialogs_init(self):
        """Test dialogs package __init__ imports."""
        from hits_ui.dialogs import NodeDialog
        assert NodeDialog is not None
    
    def test_import_node_dialog(self):
        """Test node_dialog module import."""
        from hits_ui.dialogs.node_dialog import NodeDialog
        assert NodeDialog is not None


class TestUIPanelImports:
    """Test panel imports - may require PySide6."""
    
    def test_import_panel_init(self):
        """Test panel package __init__ imports."""
        from hits_ui.panel import PanelWindow, TabWindow, TreeView
        assert PanelWindow is not None
        assert TabWindow is not None
        assert TreeView is not None
    
    def test_import_tree_view(self):
        """Test tree_view module - verifies node_card import path."""
        from hits_ui.panel.tree_view import TreeView
        assert TreeView is not None
    
    def test_import_window(self):
        """Test window module import."""
        from hits_ui.panel.window import PanelWindow
        assert PanelWindow is not None
    
    def test_import_tab_window(self):
        """Test tab_window module import."""
        from hits_ui.panel.tab_window import TabWindow
        assert TabWindow is not None


class TestCrossModuleImports:
    """Test cross-module import paths."""
    
    def test_tree_view_imports_node_card(self):
        """Verify tree_view can import NodeCard from widgets."""
        # This is the actual import used in tree_view.py
        from hits_ui.widgets.node_card import NodeCard
        
        # Verify it's the correct class
        assert hasattr(NodeCard, '__init__')
    
    def test_panel_window_imports_tree_view(self):
        """Verify panel_window can import TreeView."""
        from hits_ui.panel.window import PanelWindow
        from hits_ui.panel.tree_view import TreeView
        
        assert TreeView is not None
    
    def test_all_exports_accessible(self):
        """Test all __all__ exports are accessible."""
        import hits_core
        import hits_ui
        
        # Core exports
        assert hasattr(hits_core, '__version__')
        
        # UI exports
        assert hasattr(hits_ui, '__version__')
        assert hasattr(hits_ui, '__license__')


class TestConfigLoading:
    """Test configuration loading."""
    
    def test_config_exists(self):
        """Test config file exists."""
        from pathlib import Path
        config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
        assert config_path.exists(), f"Config not found at {config_path}"
    
    def test_config_loadable(self):
        """Test config can be loaded."""
        import yaml
        from pathlib import Path
        config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
        
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        assert "settings" in config
        assert "categories" in config


class TestSampleData:
    """Test sample data files."""
    
    def test_dev_handover_exists(self):
        """Test dev_handover.yaml exists."""
        from pathlib import Path
        data_path = Path(__file__).parent.parent.parent / "data" / "dev_handover.yaml"
        assert data_path.exists(), f"Sample data not found at {data_path}"
    
    def test_dev_handover_loadable(self):
        """Test dev_handover.yaml can be loaded."""
        import yaml
        from pathlib import Path
        data_path = Path(__file__).parent.parent.parent / "data" / "dev_handover.yaml"
        
        with open(data_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        assert "tree" in data
        assert "nodes" in data["tree"]
