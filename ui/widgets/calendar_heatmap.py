"""Calendar heatmap widget"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, QDate
from PySide6.QtGui import QPainter, QColor, QPen, QFont

class CalendarHeatmap(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setMinimumSize(600, 140); self._data = {}
    def set_data(self, data_dict): self._data = data_dict; self.update()
    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0f0f23"))
        cell, spacing, cols, rows = 14, 2, 53, 7
        today = QDate.currentDate(); start = today.addDays(-cols * rows + 1)
        for i in range(cols * rows):
            date = start.addDays(i)
            col, row = i // rows, i % rows
            x = 30 + col * (cell + spacing); y = 10 + row * (cell + spacing)
            val = self._data.get(date.toString("yyyy-MM-dd"), 0)
            if val == 0: color = QColor("#1a1a3e")
            elif val < 10: color = QColor("#1b4332")
            elif val < 50: color = QColor("#2d6a4f")
            elif val < 200: color = QColor("#40916c")
            elif val < 500: color = QColor("#52b788")
            else: color = QColor("#95d5b2")
            painter.setPen(QPen(QColor("#0f0f23"), 1)); painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, y, cell, cell), 2, 2)
        painter.setPen(QPen(QColor("#666"))); painter.setFont(QFont("Segoe UI", 9))
        for i, d in enumerate(["Mon", "Wed", "Fri"]):
            painter.drawText(2, 24 + i * 2 * (cell + spacing), d)
        painter.end()
