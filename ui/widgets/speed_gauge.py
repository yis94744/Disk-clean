"""Circular gauge widget - green/yellow/red glassmorphic"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from utils.themes import size_color

class SpeedGauge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(120, 120)
        self._value = 0
        self._title = ""
        self._subtitle = ""
        self._color = QColor("#22c55e")

    def setValue(self, value, title="", subtitle=""):
        self._value = min(max(value, 0), 100)
        self._title = title
        self._subtitle = subtitle
        # Free space: high=green, mid=yellow, low=red
        # value is free%, so >70=green, 35-70=yellow, <35=red
        self._color = QColor(size_color(100 - self._value))  # invert: low free = high usage = red
        self.update()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        size = min(w, h) - 20
        rect = QRectF((w - size) / 2, (h - size) / 2, size, size)

        # Semi-transparent background circle
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(20, 20, 40, 100))
        painter.drawEllipse(rect)

        # Track ring (semi-transparent gray)
        track_pen = QPen(QColor(255, 255, 255, 30), 10)
        track_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect.adjusted(8, 8, -8, -8), 90 * 16, -360 * 16)

        # Value arc with green/yellow/red color
        val_pen = QPen(self._color, 10)
        val_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(val_pen)
        span = int(360 * self._value / 100 * 16)
        painter.drawArc(rect.adjusted(8, 8, -8, -8), 90 * 16, -span)

        # Percentage text
        painter.setPen(QPen(Qt.white))
        font_size = max(size // 4, 8)
        font = QFont("Microsoft YaHei", font_size, QFont.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, f"{self._value:.0f}%")

        # Title
        if self._title:
            font = QFont("Microsoft YaHei", 10)
            painter.setFont(font)
            painter.setPen(QPen(QColor(200, 200, 200)))
            painter.drawText(QRectF(0, h - 20, w, 20), Qt.AlignCenter, self._title)

        # Subtitle
        if self._subtitle:
            font = QFont("Microsoft YaHei", 8)
            painter.setFont(font)
            painter.setPen(QPen(QColor(160, 160, 160)))
            painter.drawText(QRectF(0, h - 36, w, 20), Qt.AlignCenter, self._subtitle)

        painter.end()
