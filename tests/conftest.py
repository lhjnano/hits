"""Pytest configuration for HITS tests."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "core: tests for hits_core package (no GUI)"
    )
    config.addinivalue_line(
        "markers", "ui: tests for hits_ui package (requires PySide6)"
    )
    config.addinivalue_line(
        "markers", "slow: slow running tests"
    )
    config.addinivalue_line(
        "markers", "redis: tests requiring Redis server"
    )
