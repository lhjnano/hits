"""Test core models."""

import pytest
from hits_core.models.node import Node, NodeLayer, NodeType
from hits_core.models.tree import KnowledgeTree
from hits_core.models.workflow import Workflow, WorkflowStep, StepType


def test_node_creation():
    node = Node(
        id="test-1",
        layer=NodeLayer.WHY,
        title="Test Node",
        description="Test description"
    )
    
    assert node.id == "test-1"
    assert node.layer == NodeLayer.WHY
    assert node.is_root() is True
    assert node.is_negative_path() is False


def test_node_children():
    parent = Node(id="parent", layer=NodeLayer.WHY, title="Parent")
    child = Node(id="child", layer=NodeLayer.HOW, title="Child", parent_id="parent")
    
    assert child.parent_id == "parent"
    assert len(parent.children_ids) == 0
    
    parent.add_child("child")
    assert "child" in parent.children_ids
    
    parent.remove_child("child")
    assert "child" not in parent.children_ids


def test_tree_creation():
    tree = KnowledgeTree(id="tree-1", name="Test Tree")
    
    assert tree.id == "tree-1"
    assert len(tree.nodes) == 0


def test_tree_add_node():
    tree = KnowledgeTree(id="tree-1", name="Test Tree")
    root = Node(id="root", layer=NodeLayer.WHY, title="Root")
    child = Node(id="child", layer=NodeLayer.HOW, title="Child", parent_id="root")
    
    tree.add_node(root)
    tree.add_node(child)
    
    assert len(tree.nodes) == 2
    assert "root" in tree.root_ids
    assert "child" in root.children_ids


def test_tree_get_path():
    tree = KnowledgeTree(id="tree-1", name="Test Tree")
    root = Node(id="root", layer=NodeLayer.WHY, title="Root")
    mid = Node(id="mid", layer=NodeLayer.HOW, title="Middle", parent_id="root")
    leaf = Node(id="leaf", layer=NodeLayer.WHAT, title="Leaf", parent_id="mid")
    
    tree.add_node(root)
    tree.add_node(mid)
    tree.add_node(leaf)
    
    path = tree.get_path("leaf")
    assert len(path) == 3
    assert path[0].id == "root"
    assert path[1].id == "mid"
    assert path[2].id == "leaf"


def test_negative_path():
    tree = KnowledgeTree(id="tree-1", name="Test Tree")
    normal = Node(id="normal", layer=NodeLayer.HOW, title="Normal")
    negative = Node(id="negative", layer=NodeLayer.HOW, title="Failed", node_type=NodeType.NEGATIVE_PATH)
    
    tree.add_node(normal)
    tree.add_node(negative)
    
    negative_paths = tree.get_negative_paths()
    assert len(negative_paths) == 1
    assert negative_paths[0].id == "negative"


def test_workflow_creation():
    workflow = Workflow(id="wf-1", name="Test Workflow")
    
    step1 = WorkflowStep(id="step-1", name="Start", step_type=StepType.TRIGGER)
    step2 = WorkflowStep(id="step-2", name="Do Something", step_type=StepType.ACTION)
    step2.next_steps = []
    
    workflow.add_step(step1, is_entry=True)
    step1.next_steps.append("step-2")
    workflow.add_step(step2)
    
    assert len(workflow.steps) == 2
    assert workflow.entry_step_id == "step-1"


def test_workflow_execution_order():
    workflow = Workflow(id="wf-1", name="Test Workflow")
    
    s1 = WorkflowStep(id="s1", name="Step 1", step_type=StepType.TRIGGER)
    s2 = WorkflowStep(id="s2", name="Step 2", step_type=StepType.ACTION)
    s3 = WorkflowStep(id="s3", name="Step 3", step_type=StepType.OUTCOME)
    
    workflow.add_step(s1, is_entry=True)
    s1.next_steps = ["s2"]
    workflow.add_step(s2)
    s2.next_steps = ["s3"]
    workflow.add_step(s3)
    
    order = workflow.get_execution_order()
    assert len(order) == 3
    assert order[0].id == "s1"
