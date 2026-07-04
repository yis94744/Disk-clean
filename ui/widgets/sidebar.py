# -*- coding: utf-8 -*-
"""Sidebar - Modern glassmorphic navigation with cartoon icons and animations"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFrame, QLabel
from PySide6.QtCore import Signal, Qt, QRectF, QPointF, QPropertyAnimation, QEasingCurve, Property, QSize
from PySide6.QtGui import (QFont, QIcon, QPixmap, QPainter, QPen, QBrush, QColor,
                            QPainterPath, QEnterEvent, QPaintEvent)
import math as _m

NAV_ITEMS = [
    ("dashboard", "仪表盘"),
    ("file_visualizer", "文件可视化"),
    ("safe_cleaner", "安全清理"),
    ("software_mgr", "软件管理"),
    ("dup_finder", "重复文件"),
    ("large_files", "大文件"),
    ("startup_mgr", "启动管理"),
    ("process_mgr", "进程管理"),
    ("system_info", "系统信息"),
    ("settings", "设置"),
]

_CARTOON_COLORS = {
    "dashboard": ("#FF6B8A", "#FF8FAB"),
    "file_visualizer": ("#FFB347", "#FFC978"),
    "safe_cleaner": ("#4ECDC4", "#7EDDD6"),
    "software_mgr": ("#A78BFA", "#C4B5FD"),
    "dup_finder": ("#60A5FA", "#93C5FD"),
    "large_files": ("#F87171", "#FCA5A5"),
    "startup_mgr": ("#34D399", "#6EE7B7"),
    "process_mgr": ("#FBBF24", "#FCD34D"),
    "system_info": ("#818CF8", "#A5B4FC"),
    "settings": ("#9CA3AF", "#D1D5DB"),
}

def _make_cartoon_icon(key, size=28):
    """Draw a cute cartoon icon for sidebar navigation."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    s = size; m = 1.5
    c1, c2 = _CARTOON_COLORS.get(key, ("#888", "#AAA"))

    if key == "dashboard":
        p.setBrush(QBrush(QColor(c1))); p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(m+2, s-m-10, 4, 8), 2, 2)
        p.drawRoundedRect(QRectF(m+8, s-m-15, 4, 13), 2, 2)
        p.setBrush(QBrush(QColor(c2)))
        p.drawRoundedRect(QRectF(m+14, s-m-7, 4, 5), 2, 2)
        p.setBrush(QBrush(QColor("#FFFFFF"))); p.setOpacity(0.5)
        p.drawEllipse(QPointF(m+4, s-m-9), 1, 1)
        p.drawEllipse(QPointF(m+10, s-m-14), 1.2, 1.2)
        p.setOpacity(1.0)
    if key == "file_visualizer":
        p.setBrush(QBrush(QColor(c1))); p.setPen(Qt.NoPen)
        path = QPainterPath()
        path.moveTo(m, s-m-14); path.lineTo(m+4, s-m-8)
        path.lineTo(m+14, s-m-8); path.lineTo(m+14, s-m-14); path.closeSubpath()
        p.drawPath(path)
        p.setBrush(QBrush(QColor(c2)))
        p.drawRoundedRect(QRectF(m, s-m-8, s-2*m, 6), 2, 2)
        p.setPen(QPen(QColor("#FFFFFF"), 1.5)); p.setOpacity(0.7)
        cx, cy = m+18, s-m-13
        p.drawLine(QPointF(cx-2, cy), QPointF(cx+2, cy))
        p.drawLine(QPointF(cx, cy-2), QPointF(cx, cy+2))
        p.setOpacity(1.0)
    if key == "safe_cleaner":
        p.setBrush(QBrush(QColor(c1))); p.setPen(Qt.NoPen)
        path = QPainterPath()
        path.moveTo(m+4, m); path.lineTo(m+12, s-2*m-5); path.lineTo(s-m-4, m)
        path.cubicTo(s-m-4, s-2*m-8, m+12, s-m, m+4, s-2*m-8); path.closeSubpath()
        p.drawPath(path)
        p.setBrush(QBrush(QColor("#FFFFFF"))); p.setOpacity(0.6)
        heart = QPainterPath()
        hx, hy = m+10, m+7
        heart.moveTo(hx, hy+2); heart.cubicTo(hx-3, hy-1, hx-1, hy+2, hx, hy+3)
        heart.cubicTo(hx+1, hy+2, hx+3, hy-1, hx, hy+2)
        p.drawPath(heart); p.setOpacity(1.0)
    if key == "software_mgr":
        p.setBrush(QBrush(QColor(c1))); p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(m, s-m-11, s-2*m, 10), 3, 3)
        p.setBrush(QBrush(QColor(c2)))
        p.drawRoundedRect(QRectF(m-1, s-m-14, s-2*m+2, 5), 2, 2)
        p.setBrush(QBrush(QColor("#FFFFFF"))); p.setOpacity(0.5)
        p.drawRect(QRectF(m+9, s-m-11, 3, 10)); p.setOpacity(1.0)
    if key == "dup_finder":
        p.setBrush(QBrush(QColor(c2))); p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(m+2, m-1, 10, 10), 3, 3)
        p.setBrush(QBrush(QColor(c1)))
        p.drawRoundedRect(QRectF(m+8, m+5, 10, 10), 3, 3)
        p.setPen(QPen(QColor("#FFFFFF"), 1.2)); p.setOpacity(0.6)
        p.drawLine(QPointF(m+9, m+10), QPointF(m+11, m+8))
        p.drawLine(QPointF(m+15, m+10), QPointF(m+13, m+12))
        p.setOpacity(1.0)
    if key == "large_files":
        p.setBrush(QBrush(QColor(c1))); p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(m+1, m, 14, 16), 3, 3)
        p.setBrush(QBrush(QColor(c2)))
        path = QPainterPath()
        path.moveTo(m+11, m); path.lineTo(m+15, m); path.lineTo(m+15, m+4); path.closeSubpath()
        p.drawPath(path)
        p.setBrush(QBrush(QColor("#FFFFFF"))); p.setOpacity(0.5)
        star = QPainterPath(); sx, sy = m+8, m+7
        for i in range(5):
            angle = -1.5708 + i * 1.25664
            star.moveTo(sx, sy)
            star.lineTo(sx + 3.5 * _m.cos(angle), sy + 3.5 * _m.sin(angle))
            angle2 = angle + 0.62832
            star.lineTo(sx + 1.5 * _m.cos(angle2), sy + 1.5 * _m.sin(angle2))
        star.closeSubpath(); p.drawPath(star); p.setOpacity(1.0)
    if key == "startup_mgr":
        p.setBrush(QBrush(QColor(c1))); p.setPen(Qt.NoPen)
        path = QPainterPath()
        path.moveTo(m+10, m-2); path.lineTo(m+6, s-m-4); path.lineTo(m+14, s-m-4); path.closeSubpath()
        p.drawPath(path)
        p.setBrush(QBrush(QColor(c2)))
        p.drawRoundedRect(QRectF(m+2, s-m-6, 6, 4), 2, 2)
        p.drawRoundedRect(QRectF(m+12, s-m-6, 6, 4), 2, 2)
        p.setBrush(QBrush(QColor("#FF6B35")))
        p.drawRoundedRect(QRectF(m+8, s-m-1, 4, 2), 1, 1)
        p.setBrush(QBrush(QColor("#FFFFFF"))); p.setOpacity(0.5)
        p.drawEllipse(QPointF(m+10, m+5), 2.5, 2.5); p.setOpacity(1.0)
    if key == "process_mgr":
        p.setBrush(QBrush(QColor(c1))); p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(m, s-m-16, s-2*m, 14), 3, 3)
        p.setBrush(QBrush(QColor(c2)))
        p.drawRoundedRect(QRectF(m+3, s-m-12, s-2*m-6, 6), 1.5, 1.5)
        p.setBrush(QBrush(QColor(c1)))
        p.drawRect(QRectF(m+5, s-m-4, 3, 4)); p.drawRect(QRectF(m+13, s-m-4, 3, 4))
        p.setBrush(QBrush(QColor("#FFFFFF"))); p.setOpacity(0.6)
        p.drawEllipse(QPointF(m+8, s-m-9), 1.5, 1.5)
        p.drawEllipse(QPointF(m+13, s-m-9), 1.2, 1.2); p.setOpacity(1.0)
    if key == "system_info":
        p.setBrush(QBrush(QColor(c1))); p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(m, m-1, s-2*m, s-2*m-6), 3, 3)
        p.setBrush(QBrush(QColor("#1E293B")))
        p.drawRoundedRect(QRectF(m+2, m+1, s-2*m-4, s-2*m-12), 2, 2)
        p.setBrush(QBrush(QColor(c2)))
        p.drawRoundedRect(QRectF(m+8, s-m-8, 4, 6), 1, 1)
        p.drawRoundedRect(QRectF(m+4, s-m-2, 12, 2.5), 1.5, 1.5)
        p.setPen(QPen(QColor("#FFFFFF"), 1.5)); p.setOpacity(0.7)
        cx2, cy2 = m+10, m+4
        p.drawPoint(QPointF(cx2, cy2))
        p.drawLine(QPointF(cx2, cy2+1.5), QPointF(cx2, cy2+5)); p.setOpacity(1.0)
    if key == "settings":
        p.setBrush(QBrush(QColor(c1))); p.setPen(Qt.NoPen)
        cx3, cy3 = s//2, s//2 - 1
        for i in range(6):
            angle = i * _m.pi / 3
            tx = cx3 + 9 * _m.cos(angle) - 2
            ty = cy3 + 9 * _m.sin(angle) - 2
            p.drawRoundedRect(QRectF(tx, ty, 4, 4), 1.5, 1.5)
        p.setBrush(QBrush(QColor(c2)))
        p.drawEllipse(QPointF(cx3, cy3), 5, 5)
        p.setBrush(QBrush(QColor("#FFFFFF"))); p.setOpacity(0.6)
        p.drawEllipse(QPointF(cx3, cy3), 2, 2); p.setOpacity(1.0)

    p.end()
    return QIcon(pix)


class AnimatedNavButton(QPushButton):
    """Navigation button with smooth hover and selection animations."""

    def __init__(self, text, icon, nav_key, parent=None):
        super().__init__(text, parent)
        self._nav_key = nav_key
        self._anim_progress = 0.0
        self._is_checked = False
        self.setIcon(icon)
        self.setIconSize(QSize(24, 24))
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setFixedHeight(42)
        self.setMinimumWidth(190)
        self.setStyleSheet(
            "QPushButton { background: transparent; border: none; "
            "color: #8899bb; text-align: left; padding: 8px 14px; "
            "font-size: 13px; font-family: Microsoft YaHei; }")
        self._hover_anim = QPropertyAnimation(self, b"anim_progress")
        self._hover_anim.setDuration(220)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._select_anim = QPropertyAnimation(self, b"anim_progress")
        self._select_anim.setDuration(300)
        self._select_anim.setEasingCurve(QEasingCurve.OutBack)

    def _get_anim_progress(self):
        return self._anim_progress

    def _set_anim_progress(self, value):
        self._anim_progress = value
        self.update()

    anim_progress = Property(float, _get_anim_progress, _set_anim_progress)

    def enterEvent(self, event: QEnterEvent):
        if not self._is_checked:
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._anim_progress)
            self._hover_anim.setEndValue(0.5)
            self._hover_anim.start()

    def leaveEvent(self, event):
        if not self._is_checked:
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._anim_progress)
            self._hover_anim.setEndValue(0.0)
            self._hover_anim.start()

    def set_checked(self, checked):
        self._is_checked = checked
        self.setChecked(checked)
        self._select_anim.stop()
        self._select_anim.setStartValue(self._anim_progress)
        self._select_anim.setEndValue(1.0 if checked else 0.0)
        self._select_anim.start()

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = self._anim_progress

        if self._is_checked:
            bg_color = QColor(100, 140, 255, int(40 + t * 20))
            accent_color = QColor(100, 140, 255, int(180 + t * 75))
        else:
            bg_color = QColor(100, 140, 255, int(t * 25))
            accent_color = QColor(100, 140, 255, int(t * 40))

        p.setBrush(QBrush(bg_color))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(4, 2, w-8, h-4), 8, 8)

        if self._is_checked:
            p.setBrush(QBrush(accent_color))
            p.drawRoundedRect(QRectF(4, 6, 3, h-12), 1.5, 1.5)

        if self._is_checked:
            text_color = QColor(int(200 + t * 55), int(210 + t * 45), int(240 + t * 15))
        else:
            text_color = QColor(int(0x88 + t * 2 * (0xCC - 0x88)),
                               int(0x99 + t * 2 * (0xD6 - 0x99)),
                               int(0xBB + t * 2 * (0xF6 - 0xBB)))

        icon_size = int(22 + t * 3)
        icon = self.icon()
        if not icon.isNull():
            pix = icon.pixmap(QSize(icon_size, icon_size))
            icon_y = (h - icon_size) // 2
            p.drawPixmap(12, icon_y, pix)

        p.setPen(text_color)
        font = self.font()
        if self._is_checked:
            font.setBold(True)
        p.setFont(font)
        text_x = 12 + 26 + 4
        p.drawText(QRectF(text_x, 0, w - text_x - 8, h),
                   Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()


DEFAULT_STYLE = (
    "#sidebar { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, "
    "stop:0 #1a1a2e, stop:1 #16213e); "
    "border-right: 1px solid rgba(255,255,255,0.05); }"
    "QLabel#logo { color: #d0d0ff; font-size: 15px; font-weight: bold; "
    "padding: 20px 16px 8px 16px; background: transparent; }"
)


class Sidebar(QFrame):
    nav_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)
        self.setStyleSheet(DEFAULT_STYLE)
        self.buttons = {}
        self._clicking = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        logo = QLabel("  Disk Cleaner Pro")
        logo.setObjectName("logo")
        layout.addWidget(logo)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(
            "background: rgba(255,255,255,0.06); max-height: 1px; margin: 8px 12px;")
        layout.addWidget(sep)

        sec = QLabel("  导航菜单")
        sec.setStyleSheet(
            "color: #556688; font-size: 10px; padding: 8px 16px 4px 16px; "
            "background: transparent; font-weight: bold;")
        layout.addWidget(sec)

        for key, label in NAV_ITEMS:
            icon = _make_cartoon_icon(key)
            btn = AnimatedNavButton("  " + label, icon, key)
            btn.clicked.connect(lambda checked=False, k=key: self._on_click(k))
            layout.addWidget(btn)
            self.buttons[key] = btn

        layout.addStretch()

        ver = QLabel("  v2.0 路 Pro")
        ver.setStyleSheet(
            "color: #3a3a5a; padding: 12px 16px; font-size: 10px; background: transparent;")
        layout.addWidget(ver)

    def _on_click(self, key):
        if self._clicking:
            return
        self._clicking = True
        try:
            for k, btn in self.buttons.items():
                btn.set_checked(k == key)
            self.nav_clicked.emit(key)
        finally:
            self._clicking = False

    def set_active(self, key):
        for k, btn in self.buttons.items():
            btn.set_checked(k == key)