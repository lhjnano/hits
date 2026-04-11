"""Tab window for panel toggle - Fixed version."""

import sys
from PySide6.QtWidgets import QWidget, QPushButton, QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ..theme.material_dark import Theme
from .window import PanelWindow


def _is_wsl():
    if sys.platform != "linux":
        return False
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower() or "wsl" in f.read().lower()
    except:
        return False


class TabWindow(QWidget):
    def __init__(self, config: dict, panel: PanelWindow, settings: dict):
        super().__init__()
        self.config = config
        self.settings = settings
        self.panel = panel
        self.edge = settings.get("edge", "right")
        self.tab_w = 28
        self.tab_h = 48
        
        self._drag = None
        self._init_screen()
        self._build_ui()
        self._place_tab()
    
    def _init_screen(self):
        screen = QApplication.primaryScreen()
        if not screen:
            screens = QApplication.screens()
            screen = screens[0] if screens else None
        
        if screen:
            sg = screen.geometry()
            self.sx, self.sy = sg.x(), sg.y()
            self.sw, self.sh = sg.width(), sg.height()
        else:
            self.sx, self.sy = 0, 0
            self.sw, self.sh = 1920, 1080
    
    def _build_ui(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setFixedSize(self.tab_w, self.tab_h)
        
        btn = QPushButton(self.settings.get("tab_label", "⚡"), self)
        btn.setGeometry(0, 0, self.tab_w, self.tab_h)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {Theme.COLORS['primary_dark']}, stop:1 {Theme.COLORS['primary']});
                color: white; border: none; font-size: 15px; border-radius: 4px;
            }}
            QPushButton:hover  {{background:{Theme.COLORS['primary_light']};}}
            QPushButton:pressed{{background:{Theme.COLORS['primary_dark']};}}
        """)
        btn.setToolTip("HITS 열기/닫기")
        btn.clicked.connect(self.toggle)
    
    def _place_tab(self):
        x = self.sx + self.sw - self.tab_w - 10 if self.edge == "right" else self.sx + 10
        y = self.sy + (self.sh - self.tab_h) // 2
        self.move(x, y)
    
    def toggle(self):
        if self.panel.isVisible():
            self.panel.hide()
        else:
            self._show_panel()
    
    def _show_panel(self):
        pw = self.settings.get("width", 320)
        ph = min(620, int(self.sh * 0.78))
        self.panel.setFixedSize(pw, ph)
        
        tab_center_y = self.y() + self.tab_h // 2
        panel_y = tab_center_y - ph // 2
        panel_y = max(self.sy + 10, min(panel_y, self.sy + self.sh - ph - 10))
        
        panel_x = (self.x() - pw - 5) if self.edge == "right" else (self.x() + self.tab_w + 5)
        self.panel.move(panel_x, panel_y)
        
        self.panel.show()
        self.panel.raise_()
    
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPos() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and self._drag:
            y = max(self.sy, min(e.globalPos().y() - self._drag.y(), self.sy + self.sh - self.tab_h))
            x = self.sx + self.sw - self.tab_w - 10 if self.edge == "right" else self.sx + 10
            self.move(x, y)
    
    def mouseReleaseEvent(self, e):
        self._drag = None
