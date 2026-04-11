"""Ripple effect button and category header."""

from PySide6.QtWidgets import QPushButton, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property, Signal
from PySide6.QtGui import QColor, QPainter, QBrush, QPen

from ..theme.material_dark import Theme


class RippleButton(QPushButton):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._ripple_pos = None
        self._ripple_radius = 0
        self._ripple_opacity = 0.0
        self._anim = QPropertyAnimation(self, b"_rr")
        self._anim.setDuration(380)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)
    
    def get_rr(self):
        return self._ripple_radius
    
    def set_rr(self, v):
        self._ripple_radius = v
        self._ripple_opacity = max(0.0, 0.32 * (1 - v / 110))
        self.update()
    
    _rr = Property(int, get_rr, set_rr)
    
    def mousePressEvent(self, e):
        self._ripple_pos = e.pos()
        self._anim.setStartValue(0)
        self._anim.setEndValue(110)
        self._anim.start()
        super().mousePressEvent(e)
    
    def paintEvent(self, e):
        super().paintEvent(e)
        if self._ripple_pos and self._ripple_opacity > 0:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            c = QColor(Theme.COLORS["ripple"])
            c.setAlphaF(self._ripple_opacity)
            p.setBrush(QBrush(c))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(self._ripple_pos, self._ripple_radius, self._ripple_radius)


class CategoryHeader(RippleButton):
    add_clicked = Signal()
    
    def __init__(self, icon: str, name: str, parent=None, show_add_button: bool = False):
        super().__init__(parent=parent)
        self.setCheckable(True)
        self._show_add = show_add_button
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 12, 0)
        layout.setSpacing(10)
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(
            f"color:{Theme.COLORS['accent']};font-size:15px;background:transparent;"
        )
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(icon_label, 0)
        
        name_label = QLabel(name)
        name_label.setStyleSheet(
            f"color:{Theme.COLORS['on_surface']};font-size:13px;font-weight:600;background:transparent;"
        )
        name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(name_label, 1)
        
        if self._show_add:
            self.add_btn = QPushButton("➕")
            self.add_btn.setFixedSize(28, 28)
            self.add_btn.setStyleSheet(f"""
                QPushButton {{
                    background:transparent;
                    color:{Theme.COLORS['on_surface_low']};
                    border:none;
                    font-size:12px;
                    border-radius:4px;
                }}
                QPushButton:hover {{
                    background:{Theme.COLORS['surface3']};
                    color:{Theme.COLORS['accent']};
                }}
            """)
            self.add_btn.clicked.connect(self._on_add_click)
            layout.addWidget(self.add_btn)
        
        self.arrow = QLabel("›")
        self.arrow.setStyleSheet(
            f"color:{Theme.COLORS['on_surface_low']};font-size:16px;background:transparent;"
        )
        self.arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.arrow)
        
        self.setFixedHeight(42)
        self._set_style(False)
        self.toggled.connect(self._set_style)
    
    def _on_add_click(self):
        self.add_clicked.emit()
    
    def _set_style(self, checked):
        self.arrow.setText("⌄" if checked else "›")
        radius = "8px 8px 0 0" if checked else "8px"
        bg = Theme.COLORS["primary_dark"] if checked else Theme.COLORS["surface2"]
        self.setStyleSheet(f"""
            QPushButton {{background:{bg};border:none;border-radius:{radius};}}
            QPushButton:hover {{background:{Theme.COLORS['surface3']};}}
            QPushButton QLabel {{background:transparent;}}
        """)
