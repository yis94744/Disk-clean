# -*- coding: utf-8 -*-
"""Theme system for Disk Cleaner Pro - transparent glassmorphic"""
import json, os

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")

THEMES = {
    "green": {
        "name": "森林绿",
        "main_bg": "transparent",
        "card_bg": "rgba(14,32,24,0.55)",
        "panel_bg": "rgba(13,30,22,0.55)",
        "border": "rgba(126,231,135,0.16)",
        "text": "#e9f5ec",
        "text_dim": "#9fbfa9",
        "accent": "#7ee787",
        "primary": "#3fb950",
        "primary_pressed": "#2ea043",
        "warning": "#e3b341",
        "warning_pressed": "#b8860b",
        "danger": "#f85149",
        "danger_pressed": "#da3b34",
        "input_bg": "rgba(10,24,18,0.52)",
        "input_border": "rgba(126,231,135,0.20)",
        "header_bg": "rgba(12,28,21,0.68)",
        "scroll_handle": "rgba(126,231,135,0.24)",
        "sidebar_start": "rgba(14,32,24,0.84)",
        "sidebar_end": "rgba(8,20,15,0.86)",
        "sidebar_text": "#9fc4ab",
        "sidebar_hover": "rgba(63,185,80,0.14)",
        "sidebar_active": "rgba(63,185,80,0.28)",
    },
    "anime": {
        "name": "二次元",
        "main_bg": "transparent",
        "card_bg": "rgba(42,24,34,0.55)",
        "panel_bg": "rgba(28,16,24,0.55)",
        "border": "rgba(255,170,200,0.14)",
        "text": "#ffe9f2",
        "text_dim": "#c9a3b4",
        "accent": "#ff8fbf",
        "primary": "#ff6fa5",
        "primary_pressed": "#e0568c",
        "warning": "#ffb84d",
        "warning_pressed": "#d1942f",
        "danger": "#ff4d6d",
        "danger_pressed": "#d63a58",
        "input_bg": "rgba(30,16,24,0.50)",
        "input_border": "rgba(255,170,200,0.16)",
        "header_bg": "rgba(36,18,28,0.66)",
        "scroll_handle": "rgba(255,170,200,0.22)",
        "sidebar_start": "rgba(46,20,34,0.80)",
        "sidebar_end": "rgba(30,12,22,0.82)",
        "sidebar_text": "#d9a8c0",
        "sidebar_hover": "rgba(255,143,191,0.14)",
        "sidebar_active": "rgba(255,143,191,0.26)",
    },
    "deep": {
        "name": "透明深色",
        "main_bg": "transparent",
        "card_bg": "rgba(20,20,40,0.55)",
        "panel_bg": "rgba(20,20,40,0.55)",
        "border": "rgba(255,255,255,0.08)",
        "text": "#e0e0e0",
        "text_dim": "#999999",
        "accent": "#58a6ff",
        "primary": "#22c55e",
        "primary_pressed": "#16a34a",
        "warning": "#eab308",
        "warning_pressed": "#c29208",
        "danger": "#ef4444",
        "danger_pressed": "#dc2626",
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
        "panel_bg": "rgba(24,24,24,0.55)",
        "border": "rgba(255,255,255,0.08)",
        "text": "#d4d4d4",
        "text_dim": "#888888",
        "accent": "#569cd6",
        "primary": "#22c55e",
        "primary_pressed": "#16a34a",
        "warning": "#eab308",
        "warning_pressed": "#c29208",
        "danger": "#ef4444",
        "danger_pressed": "#dc2626",
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

def panel_qss(theme_name=None):
    """页面主面板底色（随主题）。"""
    t = get_theme(theme_name or load_settings().get("theme", "green"))
    return f"background:{t['panel_bg']};border-radius:10px;"

def get_theme(theme_name="green"):
    return THEMES.get(theme_name, THEMES["green"])

def build_stylesheet(theme_name="green"):
    t = get_theme(theme_name)
    return (
        f"QMainWindow{{background:transparent;}}"
        f"QWidget{{color:{t['text']};font-family:Microsoft YaHei;font-size:12px;}}"
        f"#rightPanel{{background:transparent;}}"
        f"#header{{background:{t['header_bg']};border-bottom:1px solid {t['border']};}}"
        f"QLabel#pageTitle{{font-size:17px;font-weight:bold;color:{t['text']};background:transparent;}}"
        f"QLabel#pageHint{{color:{t['text_dim']};font-size:11px;background:transparent;}}"
        f"QPushButton{{background:{t['input_bg']};color:{t['text']};border:1px solid {t['input_border']};border-radius:6px;padding:5px 14px;min-height:24px;}}"
        f"QPushButton:hover{{background:{t['input_border']};border-color:{t['accent']};}}"
        f"QPushButton:pressed{{border-color:{t['accent']};padding-top:6px;padding-bottom:4px;}}"
        f"QPushButton[pressGlow=\"true\"]{{border:2px solid {t['accent']};color:#ffffff;font-weight:bold;}}"
        f"QPushButton#primaryBtn{{background:{t['primary']};border-color:{t['primary']};color:#000;font-weight:bold;}}"
        f"QPushButton#primaryBtn:hover{{background:{t['primary_pressed']};}}"
        f"QPushButton#primaryBtn:pressed{{background:{t['primary_pressed']};padding-top:6px;padding-bottom:4px;}}"
        f"QPushButton#dangerBtn{{background:{t['danger']};border-color:{t['danger']};color:#fff;}}"
        f"QPushButton#dangerBtn:hover{{background:{t['danger_pressed']};}}"
        f"QPushButton#dangerBtn:pressed{{background:{t['danger_pressed']};padding-top:6px;padding-bottom:4px;}}"
        f"QPushButton#greenBtn{{background:{t['primary']};border:1px solid {t['primary']};color:#fff;font-weight:bold;}}"
        f"QPushButton#greenBtn:hover{{background:{t['primary_pressed']};border-color:{t['accent']};}}"
        f"QPushButton#greenBtn:pressed{{background:{t['primary_pressed']};border:2px solid {t['accent']};padding-top:6px;padding-bottom:4px;}}"
        f"QPushButton#redBtn{{background:{t['danger']};border:1px solid {t['danger']};color:#fff;}}"
        f"QPushButton#redBtn:hover{{border-color:{t['accent']};}}"
        f"QPushButton#redBtn:pressed{{background:{t['danger_pressed']};border:2px solid {t['accent']};padding-top:6px;padding-bottom:4px;}}"
        f"QPushButton#yellowBtn{{background:{t['warning']};border:1px solid {t['warning']};color:#222;font-weight:bold;}}"
        f"QPushButton#yellowBtn:hover{{background:{t['warning_pressed']};border-color:{t['accent']};}}"
        f"QPushButton#yellowBtn:pressed{{background:{t['warning_pressed']};padding-top:6px;padding-bottom:4px;}}"
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

def build_sidebar_style(theme_name="green"):
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
