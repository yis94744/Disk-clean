# -*- coding: utf-8 -*-
"""Theme system for Disk Cleaner Pro - transparent glassmorphic"""
import json, os

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")

THEMES = {
    "deep": {
        "name": "透明深色",
        "main_bg": "transparent",
        "card_bg": "rgba(20,20,40,0.55)",
        "border": "rgba(255,255,255,0.08)",
        "text": "#e0e0e0",
        "text_dim": "#999999",
        "accent": "#58a6ff",
        "primary": "#22c55e",
        "warning": "#eab308",
        "danger": "#ef4444",
        "input_bg": "rgba(10,10,25,0.45)",
        "input_border": "rgba(255,255,255,0.10)",
        "header_bg": "rgba(15,15,35,0.65)",
        "scroll_handle": "rgba(255,255,255,0.15)",
        "sidebar_start": "rgba(15,15,40,0.70)",
        "sidebar_end": "rgba(10,10,30,0.70)",
        "sidebar_text": "#8899bb",
        "sidebar_hover": "rgba(100,140,255,0.12)",
        "sidebar_active": "rgba(100,140,255,0.22)",
    },
    "gray": {
        "name": "透明灰色",
        "main_bg": "transparent",
        "card_bg": "rgba(30,30,30,0.55)",
        "border": "rgba(255,255,255,0.08)",
        "text": "#d4d4d4",
        "text_dim": "#888888",
        "accent": "#569cd6",
        "primary": "#22c55e",
        "warning": "#eab308",
        "danger": "#ef4444",
        "input_bg": "rgba(20,20,20,0.45)",
        "input_border": "rgba(255,255,255,0.10)",
        "header_bg": "rgba(25,25,25,0.65)",
        "scroll_handle": "rgba(255,255,255,0.15)",
        "sidebar_start": "rgba(20,20,20,0.70)",
        "sidebar_end": "rgba(18,18,18,0.70)",
        "sidebar_text": "#999999",
        "sidebar_hover": "rgba(86,156,214,0.10)",
        "sidebar_active": "rgba(86,156,214,0.18)",
    },
    "edge": {
        "name": "透明锋利",
        "main_bg": "transparent",
        "card_bg": "rgba(27,27,27,0.55)",
        "border": "rgba(255,255,255,0.08)",
        "text": "#cccccc",
        "text_dim": "#858585",
        "accent": "#007acc",
        "primary": "#22c55e",
        "warning": "#eab308",
        "danger": "#ef4444",
        "input_bg": "rgba(20,20,20,0.45)",
        "input_border": "rgba(255,255,255,0.10)",
        "header_bg": "rgba(25,25,25,0.65)",
        "scroll_handle": "rgba(255,255,255,0.15)",
        "sidebar_start": "rgba(22,22,22,0.70)",
        "sidebar_end": "rgba(18,18,18,0.70)",
        "sidebar_text": "#858585",
        "sidebar_hover": "rgba(0,122,204,0.10)",
        "sidebar_active": "rgba(0,122,204,0.18)",
    },
}

def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def get_theme(theme_name="deep"):
    return THEMES.get(theme_name, THEMES["deep"])

def build_stylesheet(theme_name="deep"):
    t = get_theme(theme_name)
    return (
        f"QMainWindow{{background:transparent;}}"
        f"QWidget{{color:{t['text']};font-family:Microsoft YaHei;font-size:12px;}}"
        f"#rightPanel{{background:transparent;}}"
        f"#header{{background:{t['header_bg']};border-bottom:1px solid {t['border']};}}"
        f"QPushButton{{background:{t['input_bg']};color:{t['text']};border:1px solid {t['input_border']};border-radius:6px;padding:6px 12px;}}"
        f"QPushButton:hover{{background:{t['input_border']};border-color:{t['accent']};}}"
        f"QPushButton#primaryBtn{{background:{t['primary']};border-color:{t['primary']};color:#000;font-weight:bold;}}"
        f"QPushButton#primaryBtn:hover{{background:#16a34a;}}"
        f"QPushButton#dangerBtn{{background:{t['danger']};border-color:{t['danger']};color:#fff;}}"
        f"QPushButton#dangerBtn:hover{{background:#dc2626;}}"
        f"QFrame#card{{background:{t['card_bg']};border:1px solid {t['border']};border-radius:8px;padding:14px;}}"
        f"QTreeWidget,QTextEdit,QLineEdit,QComboBox,QSpinBox{{background:{t['input_bg']};border:1px solid {t['input_border']};border-radius:5px;color:{t['text']};}}"
        f"QTreeWidget::item:selected{{background:rgba(100,140,255,0.20);}}"
        f"QTreeWidget::item:checked{{background:rgba(34,197,94,0.15);}}"
        f"QHeaderView::section{{background:{t['card_bg']};color:{t['text_dim']};border:1px solid {t['border']};padding:4px 8px;font-weight:bold;}}"
        f"QScrollBar:vertical{{background:transparent;width:8px;}}"
        f"QScrollBar::handle:vertical{{background:{t['scroll_handle']};border-radius:4px;min-height:20px;}}"
        f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        f"QProgressBar{{background:{t['input_bg']};border:1px solid {t['input_border']};border-radius:4px;text-align:center;color:#fff;min-height:16px;max-height:16px;}}"
        f"QProgressBar::chunk{{background:{t['primary']};border-radius:3px;}}"
        f"QTabWidget::pane{{border:1px solid {t['border']};background:transparent;}}"
        f"QTabBar::tab{{background:{t['card_bg']};color:{t['text_dim']};padding:7px 14px;border:1px solid {t['border']};border-bottom:none;border-top-left-radius:5px;border-top-right-radius:5px;}}"
        f"QTabBar::tab:selected{{background:{t['input_bg']};color:#f0f6fc;}}"
        f"QCheckBox{{color:{t['text']};spacing:6px;}}"
        f"QCheckBox::indicator{{width:14px;height:14px;border:2px solid {t['scroll_handle']};border-radius:3px;}}"
        f"QCheckBox::indicator:checked{{background:{t['primary']};border-color:{t['primary']};}}"
        f"QComboBox,QComboBox QAbstractItemView{{font-size:12px;min-height:22px;}}"
        f"QSplitter::handle{{background:{t['border']};width:1px;}}"
        f"QStatusBar{{background:rgba(10,10,25,0.50);color:{t['text_dim']};border-top:1px solid {t['border']};}}"
    )

def build_sidebar_style(theme_name="deep"):
    t = get_theme(theme_name)
    return (
        f"#sidebar{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {t['sidebar_start']},stop:1 {t['sidebar_end']});border-right:1px solid rgba(255,255,255,0.05);}}"
        f"QLabel#logo{{color:#d0d0ff;font-size:15px;font-weight:bold;padding:20px 16px 8px 16px;background:transparent;}}"
        f"QPushButton#navBtn{{background:transparent;color:{t['sidebar_text']};border:none;border-radius:8px;text-align:left;padding:10px 14px;margin:1px 10px;font-size:13px;}}"
        f"QPushButton#navBtn:hover{{background:{t['sidebar_hover']};color:#ccd6f6;}}"
        f"QPushButton#navBtn:checked{{background:{t['sidebar_active']};color:#ffffff;font-weight:bold;border-left:3px solid {t['accent']};border-radius:0px 8px 8px 0px;}}"
    )

def size_color(percent):
    """Return green/yellow/red based on percentage (0-100)."""
    if percent <= 30:
        return "#22c55e"  # green
    elif percent <= 65:
        return "#eab308"  # yellow
    else:
        return "#ef4444"  # red

def size_color_bytes(used, total):
    """Return color based on usage ratio."""
    if total <= 0:
        return "#22c55e"
    ratio = used / total
    if ratio <= 0.3:
        return "#22c55e"
    elif ratio <= 0.65:
        return "#eab308"
    else:
        return "#ef4444"
