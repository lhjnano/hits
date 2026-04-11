"""Font loader for bundled and system fonts."""

import sys
from pathlib import Path
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication


BUNDLED_FONTS_DIR = Path(__file__).parent.parent.parent / "assets" / "fonts"

FONT_PRIORITIES = [
    "Noto Sans KR",
    "Noto Sans CJK KR",
    "Nanum Gothic",
    "Malgun Gothic",
]


def _is_wsl() -> bool:
    """Check if running under WSL."""
    if sys.platform != "linux":
        return False
    try:
        with open("/proc/version", "r") as f:
            version = f.read().lower()
            return "microsoft" in version or "wsl" in version
    except Exception:
        return False


def _is_windows() -> bool:
    return sys.platform == "win32"


def load_bundled_fonts() -> list:
    """Load fonts from the bundled assets directory."""
    loaded = []
    
    if BUNDLED_FONTS_DIR.exists():
        font_db = QFontDatabase()
        for font_file in BUNDLED_FONTS_DIR.glob("*.ttf"):
            try:
                font_id = font_db.addApplicationFont(str(font_file))
                if font_id >= 0:
                    families = font_db.applicationFontFamilies(font_id)
                    loaded.extend(families)
            except Exception:
                pass
    
    return loaded


def load_wsl_fonts() -> list:
    """Load fonts from Windows directory when running in WSL."""
    if not _is_wsl():
        return []
    
    loaded = []
    font_db = QFontDatabase()
    
    windows_font_paths = [
        "/mnt/c/Windows/Fonts",
        "/mnt/c/Windows/Fonts/NotoSansKR-VF.ttf",
        "/mnt/c/Windows/Fonts/malgun.ttf",
        "/mnt/c/Windows/Fonts/malgunbd.ttf",
    ]
    
    for path in windows_font_paths:
        p = Path(path)
        if p.is_file() and p.suffix.lower() == ".ttf":
            try:
                font_id = font_db.addApplicationFont(str(p))
                if font_id >= 0:
                    families = font_db.applicationFontFamilies(font_id)
                    loaded.extend(families)
            except Exception:
                pass
        elif p.is_dir():
            for font_file in p.glob("*.ttf"):
                try:
                    font_id = font_db.addApplicationFont(str(font_file))
                    if font_id >= 0:
                        families = font_db.applicationFontFamilies(font_id)
                        loaded.extend(families)
                except Exception:
                    pass
    
    return list(set(loaded))


def get_best_korean_font(size: int = 10) -> QFont:
    """Get the best available Korean font."""
    
    load_bundled_fonts()
    load_wsl_fonts()
    
    font_db = QFontDatabase()
    available = font_db.families()
    
    for font_name in FONT_PRIORITIES:
        for family in available:
            if font_name.lower() in family.lower():
                return QFont(family, size)
    
    return QFont(size) if _is_wsl() else QFont()


def setup_fonts(app: QApplication = None) -> tuple:
    """Setup fonts for the application. Call this before creating widgets."""
    if app is None:
        app = QApplication.instance()
    
    loaded = []
    loaded.extend(load_bundled_fonts())
    loaded.extend(load_wsl_fonts())
    
    font = get_best_korean_font(10)
    
    if app:
        app.setFont(font)
    
    return font, loaded
