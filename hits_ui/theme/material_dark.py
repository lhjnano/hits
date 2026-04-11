"""Material Design dark theme for HITS UI."""


class Theme:
    COLORS = {
        "primary": "#1565C0",
        "primary_light": "#1E88E5",
        "primary_dark": "#0D47A1",
        "accent": "#00BCD4",
        "surface": "#1A1A2E",
        "surface2": "#16213E",
        "surface3": "#0F3460",
        "on_surface": "#E8EAF6",
        "on_surface_med": "#9FA8DA",
        "on_surface_low": "#5C6BC0",
        "ripple": "#3F51B5",
        "divider": "#1F2A4A",
        "success": "#66BB6A",
        "danger": "#EF5350",
        "warning": "#FFA726",
    }
    
    FONTS = {
        "title": ("Noto Sans KR", 16, 700),
        "subtitle": ("Noto Sans KR", 14, 600),
        "body": ("Noto Sans KR", 12, 400),
        "caption": ("Noto Sans KR", 10, 400),
    }
    
    LAYER_COLORS = {
        "why": "#FFA726",
        "how": "#66BB6A",
        "what": "#29B6F6",
    }
    
    @classmethod
    def global_stylesheet(cls) -> str:
        return f"""
            * {{
                font-family: 'Noto Sans KR', sans-serif;
            }}
            
            QToolTip {{
                background: {cls.COLORS['surface2']};
                color: {cls.COLORS['on_surface']};
                border: 1px solid {cls.COLORS['divider']};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            
            QMenu {{
                background: {cls.COLORS['surface2']};
                color: {cls.COLORS['on_surface']};
                border: 1px solid {cls.COLORS['divider']};
            }}
            
            QMenu::item:selected {{
                background: {cls.COLORS['primary']};
            }}
        """
    
    @classmethod
    def button_style(
        cls,
        bg_color: str = None,
        text_color: str = None,
        hover_color: str = None,
    ) -> str:
        bg = bg_color or cls.COLORS["primary"]
        text = text_color or "white"
        hover = hover_color or cls.COLORS["primary_light"]
        
        return f"""
            QPushButton {{
                background: {bg};
                color: {text};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {hover};
            }}
            QPushButton:pressed {{
                background: {bg};
            }}
        """
    
    @classmethod
    def input_style(cls) -> str:
        return f"""
            QLineEdit, QTextEdit {{
                background: {cls.COLORS['surface2']};
                color: {cls.COLORS['on_surface']};
                border: 1px solid {cls.COLORS['divider']};
                border-radius: 6px;
                padding: 8px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {cls.COLORS['primary']};
            }}
        """
