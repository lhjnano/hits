"""UI tests package."""

import sys
from pathlib import Path

# Ensure hits_ui is importable
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set QT_QPA_PLATFORM for headless testing
import os
if sys.platform == "linux" and "DISPLAY" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
