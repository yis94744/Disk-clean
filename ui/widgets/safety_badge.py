"""Safety level badge widget"""
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from utils.constants import SAFETY_LABELS, SAFETY_STYLESHEET

class SafetyBadge(QLabel):
    def __init__(self, level=0, parent=None):
        super().__init__(parent); self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(22); self.setMinimumWidth(60); self.set_level(level)
    def set_level(self, level):
        label, color, _ = SAFETY_LABELS.get(level, ("Unknown", "#888", "gray"))
        style = SAFETY_STYLESHEET.get(level, "background: #888; color: white; border-radius: 4px; padding: 2px 8px;")
        self.setText(label); self.setStyleSheet(style)
