"""Test storage backends."""

import pytest
import tempfile
import os
from pathlib import Path

from hits_core.models.tree import KnowledgeTree
from hits_core.models.node import Node, NodeLayer
from hits_core.storage.file_store import FileStorage


@pytest.fixture
def temp_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield FileStorage(tmpdir)


@pytest.mark.asyncio
async def test_file_storage_save_load_tree(temp_storage):
    tree = KnowledgeTree(
        id="test-tree",
        name="Test Tree",
        description="Test description"
    )
    
    result = await temp_storage.save_tree(tree)
    assert result is True
    
    loaded = await temp_storage.load_tree("test-tree")
    assert loaded is not None
    assert loaded.id == "test-tree"
    assert loaded.name == "Test Tree"


@pytest.mark.asyncio
async def test_file_storage_list_trees(temp_storage):
    tree1 = KnowledgeTree(id="tree-1", name="Tree 1")
    tree2 = KnowledgeTree(id="tree-2", name="Tree 2")
    
    await temp_storage.save_tree(tree1)
    await temp_storage.save_tree(tree2)
    
    trees = await temp_storage.list_trees()
    assert len(trees) == 2
    assert "tree-1" in trees
    assert "tree-2" in trees


@pytest.mark.asyncio
async def test_file_storage_delete_tree(temp_storage):
    tree = KnowledgeTree(id="to-delete", name="Delete Me")
    await temp_storage.save_tree(tree)
    
    result = await temp_storage.delete_tree("to-delete")
    assert result is True
    
    loaded = await temp_storage.load_tree("to-delete")
    assert loaded is None


@pytest.mark.asyncio
async def test_file_storage_with_nodes(temp_storage):
    tree = KnowledgeTree(id="tree-with-nodes", name="Tree with Nodes")
    root = Node(id="root", layer=NodeLayer.WHY, title="Root")
    child = Node(id="child", layer=NodeLayer.HOW, title="Child", parent_id="root")
    
    tree.add_node(root)
    tree.add_node(child)
    
    await temp_storage.save_tree(tree)
    
    loaded = await temp_storage.load_tree("tree-with-nodes")
    assert len(loaded.nodes) == 2
    assert "child" in loaded.nodes["root"].children_ids
