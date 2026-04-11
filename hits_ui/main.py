"""Main entry point for HITS GUI."""

import os
os.environ["QT_IM_MODULE"] = "ibus"

import sys
import asyncio
import threading
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase

from .panel.window import PanelWindow
from .panel.tab_window import TabWindow
from .theme.material_dark import Theme
from hits_core.collector import CollectorDaemon
from hits_core.api import start_api_server, stop_api_server


MD = Theme.COLORS

CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"

_daemon: CollectorDaemon | None = None
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None


def load_config():
    import yaml
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {"settings": {"edge": "right", "width": 300, "tab_label": "⚡"}}


def _run_asyncio_loop():
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop.run_forever()


def start_daemon(project_paths: list[str]):
    global _daemon, _thread
    
    start_api_server(port=8765)
    
    _daemon = CollectorDaemon(project_paths=project_paths)
    _daemon.setup()
    
    _thread = threading.Thread(target=_run_asyncio_loop, daemon=True)
    _thread.start()
    
    while _loop is None:
        pass
    
    asyncio.run_coroutine_threadsafe(_daemon.start(), _loop)


def stop_daemon():
    global _daemon, _loop
    
    stop_api_server()
    
    if _daemon and _loop:
        future = asyncio.run_coroutine_threadsafe(_daemon.stop(), _loop)
        future.result(timeout=5)
        
        _loop.call_soon_threadsafe(_loop.stop)


def load_fonts():
    """Load Korean and Emoji fonts from Windows in WSL or use system fonts."""
    loaded_fonts = []
    
    wsl_font_paths = [
        "/mnt/c/Windows/Fonts/malgun.ttf",
        "/mnt/c/Windows/Fonts/malgunbd.ttf",
        "/mnt/c/Windows/Fonts/NotoSansKR-VF.ttf",
        "/mnt/c/Windows/Fonts/gulim.ttc",
        "/mnt/c/Windows/Fonts/seguiemj.ttf",
    ]
    
    for font_path in wsl_font_paths:
        if Path(font_path).exists():
            try:
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id >= 0:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        loaded_fonts.extend(families)
            except Exception as e:
                print(f"[Font] Failed to load {font_path}: {e}")
    
    return loaded_fonts


def get_best_font():
    """Get the best available font for Korean and Emoji."""
    loaded = load_fonts()
    
    korean_fonts = [
        "Malgun Gothic",
        "Noto Sans KR",
        "Noto Sans CJK KR",
        "Nanum Gothic",
        "Gulim",
    ]
    
    for preferred in korean_fonts:
        for family in loaded:
            if preferred.lower() in family.lower():
                return QFont(family, 10)
    
    for family in QFontDatabase.families():
        for preferred in korean_fonts:
            if preferred.lower() in family.lower():
                return QFont(family, 10)
        if "KR" in family or "Korean" in family:
            return QFont(family, 10)
    
    font = QFont()
    font.setPointSize(10)
    return font


def main():
    if sys.platform == "darwin":
        sys.argv += ["-QPlatformTheme", "cocoa"]
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    font = get_best_font()
    app.setFont(font)
    
    app.setStyleSheet(f"""
        QToolTip {{
            background: {MD['surface2']};
            color: {MD['on_surface']};
            border: 1px solid {MD['divider']};
            border-radius: 4px;
            padding: 4px 8px;
        }}
    """)
    
    config = load_config()
    settings = config.get("settings", {})
    
    raw_paths = config.get("project_paths", [])
    project_paths = raw_paths if isinstance(raw_paths, list) else [str(Path.cwd())]
    if not project_paths:
        project_paths = [str(Path.cwd())]
    start_daemon(project_paths)
    
    panel = PanelWindow(config, settings)
    tab = TabWindow(config, panel, settings)
    
    app.aboutToQuit.connect(stop_daemon)
    
    tab.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
