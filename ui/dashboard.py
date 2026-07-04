"""Dashboard - 仪表盘"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QPushButton, QScrollArea)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QFont
from ui.widgets.speed_gauge import SpeedGauge
from utils.helpers import get_drives, get_drive_info, format_size
from utils.themes import size_color

class DashboardPage(QWidget):
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._first_load = True
        self._setup_ui()

    def _set_visible(self, visible):
        if visible and self._first_load:
            self._first_load = False
            QTimer.singleShot(100, self._refresh)

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        main = QWidget()
        main.setStyleSheet("background:rgba(20,20,40,0.50);border-radius:10px;")
        layout = QVBoxLayout(main)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        title = QLabel("仪表盘")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        title.setStyleSheet("color:#e0e0e0;")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.gauge = SpeedGauge()
        self.gauge.setMinimumSize(160, 160)
        self.gauge.setMaximumSize(200, 200)
        top.addWidget(self.gauge)
        top.addStretch()

        quick = QFrame()
        quick.setObjectName("card")
        ql = QVBoxLayout(quick)
        qlbl = QLabel("快捷操作")
        qlbl.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        ql.addWidget(qlbl)
        qb = QHBoxLayout()
        sb = QPushButton("扫描所有磁盘")
        sb.setObjectName("greenBtn")
        qb.addWidget(sb)
        cb = QPushButton("智能清理")
        cb.setObjectName("greenBtn")
        qb.addWidget(cb)
        qb.addStretch()
        ql.addLayout(qb)
        top.addWidget(quick)
        layout.addLayout(top)

        self.cards = QHBoxLayout()
        self.cards.setSpacing(16)
        layout.addLayout(self.cards)
        layout.addStretch()
        scroll.setWidget(main)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _card(self, t, v, s, color="#4a6cf7"):
        c = QFrame()
        c.setObjectName("card")
        c.setMinimumSize(200, 120)
        cl = QVBoxLayout(c)
        tl = QLabel(t)
        tl.setStyleSheet("color:" + color + ";font-size:12px;font-weight:bold;")
        vl = QLabel(v)
        vl.setFont(QFont("Microsoft YaHei", 22, QFont.Bold))
        vl.setStyleSheet("color:#e0e0e0;")
        sl = QLabel(s)
        sl.setStyleSheet("color:#aaa;font-size:11px;")
        cl.addWidget(tl)
        cl.addWidget(vl)
        cl.addWidget(sl)
        return c

    def _refresh(self):
        while self.cards.count():
            item = self.cards.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        drives = get_drives()
        tu = 0
        tt = 0
        for d in drives[:6]:
            info = get_drive_info(d)
            if info["total"] > 0:
                tu += info["used"]
                tt += info["total"]
                cc = size_color(info["percent"])
                dl = d.rstrip(":\\") + ":"
                self.cards.addWidget(self._card(
                    dl,
                    str(info["percent"]) + "%",
                    format_size(info["free"]) + " 可用 / " + format_size(info["total"]),
                    cc
                ))
        ov = int((1 - tu / max(tt, 1)) * 100)
        self.gauge.setValue(ov, "磁盘健康", format_size(tt - tu) + " 可用")
        self.status_message.emit("仪表盘已更新 - " + str(len(drives)) + " 个磁盘")