"""Sunburst chart widget"""
from PySide6.QtWidgets import QWidget, QToolTip
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath
import math

class SunburstWidget(QWidget):
    segment_clicked = Signal(object)
    def __init__(self, parent=None):
        super().__init__(parent); self.setMinimumSize(400, 400)
        self.setMouseTracking(True); self._data = None; self._segments = []
    def set_data(self, root_node): self._data = root_node; self._segments = []; self._layout_segments(); self.update()
    def _layout_segments(self):
        self._segments = []
        if not self._data: return
        cx, cy = self.width() / 2, self.height() / 2
        radius = min(cx, cy) - 20
        def _recurse(node, inner_r, outer_r, start_angle, span_angle, depth):
            if not node.children or depth > 3 or span_angle < 0.5:
                self._segments.append((inner_r, outer_r, start_angle, span_angle, node, depth)); return
            total = sum(c.size for c in node.children if c.size > 0)
            if total == 0: self._segments.append((inner_r, outer_r, start_angle, span_angle, node, depth)); return
            ring_w = (radius - 30) / 4; next_inner = outer_r; next_outer = min(outer_r + ring_w, radius)
            angle = start_angle
            for child in sorted(node.children, key=lambda c: c.size, reverse=True):
                if child.size <= 0: continue
                child_span = span_angle * (child.size / total)
                if child_span < 0.5: self._segments.append((next_inner, next_outer, angle, child_span, child, depth + 1))
                else: _recurse(child, next_inner, next_outer, angle, child_span, depth + 1)
                angle += child_span
        _recurse(self._data, 20, 20 + (radius - 30) / 4, 0, 360, 0)
    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0f0f23"))
        if not self._segments: return
        cx, cy = self.width() / 2, self.height() / 2
        colors = [QColor("#4CAF50"), QColor("#2196F3"), QColor("#FF9800"),
                  QColor("#9C27B0"), QColor("#E91E63"), QColor("#00BCD4"),
                  QColor("#FF5722"), QColor("#3F51B5"), QColor("#009688")]
        for inner_r, outer_r, start_angle, span, node, depth in self._segments:
            color = colors[depth % len(colors)]; painter.setPen(QPen(QColor("#1a1a3e"), 1)); painter.setBrush(color)
            path = QPainterPath(); sr = math.radians(start_angle - 90); er = math.radians(start_angle + span - 90)
            path.moveTo(cx + inner_r * math.cos(sr), cy + inner_r * math.sin(sr))
            path.arcTo(QRectF(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2), -start_angle + 90, -span)
            path.lineTo(cx + inner_r * math.cos(er), cy + inner_r * math.sin(er))
            path.arcTo(QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2), -(start_angle + span) + 90, span)
            path.closeSubpath(); painter.drawPath(path)
            mid_angle = math.radians(start_angle + span / 2 - 90); mid_r = (inner_r + outer_r) / 2
            if span > 5 and outer_r - inner_r > 15:
                painter.setPen(QPen(Qt.white)); painter.setFont(QFont("Segoe UI", 7))
                tx = cx + mid_r * math.cos(mid_angle); ty = cy + mid_r * math.sin(mid_angle)
                painter.drawText(int(tx - 30), int(ty - 6), 60, 12, Qt.AlignCenter, node.name[:12])
        painter.end()
    def mouseMoveEvent(self, event):
        pos = event.position(); cx, cy = self.width() / 2, self.height() / 2
        dx, dy = pos.x() - cx, pos.y() - cy; dist = math.sqrt(dx*dx + dy*dy)
        angle = math.degrees(math.atan2(dy, dx)) + 90
        if angle < 0: angle += 360
        for ir, ora, sa, span, node, _ in self._segments:
            if ir <= dist <= ora and sa <= angle <= sa + span:
                from utils.helpers import format_size
                QToolTip.showText(event.globalPosition().toPoint(), f"{node.name}\n{format_size(node.size)}"); return
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position(); cx, cy = self.width() / 2, self.height() / 2
            dx, dy = pos.x() - cx, pos.y() - cy; dist = math.sqrt(dx*dx + dy*dy)
            angle = math.degrees(math.atan2(dy, dx)) + 90
            if angle < 0: angle += 360
            for ir, ora, sa, span, node, _ in self._segments:
                if ir <= dist <= ora and sa <= angle <= sa + span:
                    self.segment_clicked.emit(node); return
    def resizeEvent(self, event): super().resizeEvent(event); self._layout_segments()
