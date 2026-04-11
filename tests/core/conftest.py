"""Core tests package."""

import sys
from pathlib import Path

# Ensure hits_core is importable
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
