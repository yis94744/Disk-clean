"""System Info - thread-safe loading with QThread"""
import warnings
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame)
from PySide6.QtCore import Signal, Qt, QTimer, QThread, QObject
from PySide6.QtGui import QFont
from utils.helpers import format_size
from core.system_query import SystemQuery

class _SystemWorker(QObject):
    progress = Signal(str)
    finished = Signal(dict)

    def run(self):
        query = SystemQuery()
        query.progress.connect(self.progress.emit)
        query.finished.connect(self.finished.emit)
        query.query_all()

class SystemInfoPage(QWidget):
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loaded = False
        self._loading = False
        self._thread = None
        self._worker = None
        self._load_dots = 0
        self._load_timer = None
        self._loading_label = None
        self._setup_ui()
        QTimer.singleShot(500, self._start_load)

    def _setup_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16)
        tb = QHBoxLayout()
        t = QLabel("\u7cfb\u7edf\u4fe1\u606f")
        t.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        t.setStyleSheet("color:#e0e0e0;"); tb.addWidget(t); tb.addStretch()
        r = QPushButton("\u5237\u65b0"); r.clicked.connect(self._start_load); tb.addWidget(r)
        layout.addLayout(tb)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self.content = QWidget(); self.content.setStyleSheet("background:rgba(20,20,40,0.50);border-radius:10px;")
        self._clayout = QVBoxLayout(self.content)
        self._clayout.setContentsMargins(0,0,0,0); self._clayout.setSpacing(16)
        self.scroll.setWidget(self.content); layout.addWidget(self.scroll)

    def _set_visible(self, visible):
        if visible and not self._loaded and not self._loading:
            self._start_load()

    def _start_load(self):
        if self._loading: return
        self._loading = True; self._loaded = True
        while self._clayout.count():
            item = self._clayout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        if self._load_timer and self._load_timer.isActive(): self._load_timer.stop()
        self._loading_label = QLabel("\u6b63\u5728\u8bfb\u53d6\u7cfb\u7edf\u6570\u636e...")
        self._loading_label.setStyleSheet("color:#58a6ff;font-size:18px;padding:40px;font-weight:bold;background:transparent;")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._clayout.addWidget(self._loading_label)
        self._loading_label.repaint()
        self._load_dots = 0
        self._load_timer = QTimer()
        self._load_timer.timeout.connect(self._animate_loading); self._load_timer.start(400)

        # Clean up previous thread
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)

        self._thread = QThread()
        self._worker = _SystemWorker()
        self._worker.moveToThread(self._thread)
        self._worker.finished.connect(self._display)
        self._worker.progress.connect(self.status_message.emit)
        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(lambda: setattr(self, '_thread', None))
        self._thread.start()

    def _animate_loading(self):
        self._load_dots = (self._load_dots + 1) % 4
        dots = "." * self._load_dots
        if self._loading_label:
            try: self._loading_label.setText("\u6b63\u5728\u8bfb\u53d6\u7cfb\u7edf\u6570\u636e" + dots)
            except: pass

    def _card(self, title):
        card = QFrame(); card.setObjectName("card")
        card.setStyleSheet("QFrame#card{background:transparent;border:1px solid #21262d;border-radius:8px;}")
        cl = QVBoxLayout(card); cl.setContentsMargins(14,12,14,12); cl.setSpacing(6)
        tl = QLabel(title); tl.setFont(QFont("Microsoft YaHei",12,QFont.Bold))
        tl.setStyleSheet("color:#58a6ff;background:transparent;"); cl.addWidget(tl)
        return card, cl

    def _row(self, parent_layout, key, value, color="#c9d1d9"):
        row = QHBoxLayout(); row.setSpacing(8)
        kl = QLabel(key); kl.setStyleSheet("color:#8b949e;font-size:11px;min-width:90px;background:transparent;")
        row.addWidget(kl)
        vl = QLabel(str(value) if value else "-")
        vl.setStyleSheet(f"color:{color};font-size:11px;background:transparent;"); vl.setWordWrap(True)
        row.addWidget(vl, 1); parent_layout.addLayout(row)

    def _display(self, info):
        self._loading = False
        if self._load_timer and self._load_timer.isActive(): self._load_timer.stop()
        while self._clayout.count():
            item = self._clayout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        if not info:
            lbl = QLabel("\u65e0\u6cd5\u83b7\u53d6\u7cfb\u7edf\u4fe1\u606f")
            lbl.setStyleSheet("color:#8b949e;font-size:14px;padding:40px;background:transparent;")
            lbl.setAlignment(Qt.AlignCenter)
            self._clayout.addWidget(lbl)
            self._clayout.addStretch()
            return
        # OS
        card, cl = self._card("\u64cd\u4f5c\u7cfb\u7edf")
        osi = info.get("os", {})
        self._row(cl, "\u540d\u79f0:", osi.get("name", "-"), "#4CAF50")
        self._row(cl, "\u7248\u672c:", osi.get("version", "-"))
        self._row(cl, "\u6784\u5efa:", osi.get("build", "-"))
        self._row(cl, "\u67b6\u6784:", osi.get("arch", "-"))
        if osi.get("install_date"): self._row(cl, "\u5b89\u88c5\u65e5\u671f:", osi["install_date"])
        if osi.get("last_boot"): self._row(cl, "\u6700\u540e\u542f\u52a8:", osi["last_boot"])
        if osi.get("registered_user"): self._row(cl, "\u6ce8\u518c\u7528\u6237:", osi["registered_user"])
        self._clayout.addWidget(card)
        # CPU
        cpu = info.get("cpu", {})
        card, cl = self._card("\u5904\u7406\u5668 (CPU)")
        self._row(cl, "\u578b\u53f7:", cpu.get("name", "Unknown"), "#FF9800")
        c = cpu.get("cores", 0); t = cpu.get("threads", 0)
        if c: self._row(cl, "\u6838\u5fc3/\u7ebf\u7a0b:", f"{c} \u6838 / {t} \u7ebf\u7a0b")
        if cpu.get("max_speed"): self._row(cl, "\u6700\u5927\u9891\u7387:", f"{cpu['max_speed']} MHz")
        if cpu.get("l2_cache"): self._row(cl, "L2\u7f13\u5b58:", format_size(cpu["l2_cache"] * 1024))
        if cpu.get("l3_cache"): self._row(cl, "L3\u7f13\u5b58:", format_size(cpu["l3_cache"] * 1024))
        if cpu.get("socket"): self._row(cl, "\u63d2\u69fd:", cpu["socket"])
        if cpu.get("manufacturer"): self._row(cl, "\u5236\u9020\u5546:", cpu["manufacturer"])
        self._clayout.addWidget(card)
        # Memory
        card, cl = self._card("\u5185\u5b58 (RAM)")
        mem = info.get("memory", {})
        total = mem.get("total", 0)
        if total > 0:
            self._row(cl, "\u603b\u5bb9\u91cf:", format_size(total), "#4CAF50")
            self._row(cl, "\u5df2\u7528:", format_size(mem.get("used",0)) + f" ({mem.get('percent',0)}%)")
            avail = mem.get("available", 0) or (total - mem.get("used", 0))
            self._row(cl, "\u53ef\u7528:", format_size(avail))
        if mem.get("swap_total", 0) > 0: self._row(cl, "\u865a\u62df\u5185\u5b58:", format_size(mem["swap_total"]))
        sticks = mem.get("sticks", [])
        if sticks:
            self._row(cl, "\u5185\u5b58\u6761:", f"\u00d7{len(sticks)} \u6761", "#e6edf3")
            for i, s in enumerate(sticks):
                cap = format_size(s.get("capacity",0)) if s.get("capacity") else "?"
                spd = str(s["speed"]) + " MHz" if s.get("speed") else ""
                mfr = s.get("manufacturer", ""); slot = s.get("slot", "")
                lbl = f"  #{i+1}: {cap}"
                if spd: lbl += f" @ {spd}"
                if mfr: lbl += f" [{mfr}]"
                if slot: lbl += f" ({slot})"
                self._row(cl, "", lbl, "#8899aa")
        self._clayout.addWidget(card)
        # GPU
        gpus = info.get("gpu", [])
        if gpus:
            card, cl = self._card("\u663e\u5361 (GPU)")
            for i, g in enumerate(gpus):
                name = g.get("name", "Unknown")
                vram = format_size(g.get("vram",0)) if g.get("vram") else "\u672a\u77e5\u663e\u5b58"
                self._row(cl, f"\u663e\u5361 #{i+1}:", name, "#e6edf3")
                self._row(cl, "\u663e\u5b58:", vram)
                if g.get("driver"): self._row(cl, "\u9a71\u52a8:", g["driver"])
                if g.get("resolution"): self._row(cl, "\u5206\u8fa8\u7387:", g["resolution"])
                if g.get("refresh"): self._row(cl, "\u5237\u65b0\u7387:", g["refresh"] + " Hz")
        self._clayout.addWidget(card)
        # Motherboard
        card, cl = self._card("\u4e3b\u677f & BIOS")
        mb = info.get("motherboard", {})
        self._row(cl, "\u4e3b\u677f\u5236\u9020\u5546:", mb.get("manufacturer", "-"))
        self._row(cl, "\u4e3b\u677f\u578b\u53f7:", mb.get("product", "-"))
        bios = info.get("bios", {})
        self._row(cl, "BIOS\u7248\u672c:", bios.get("version", "-"))
        self._row(cl, "BIOS\u65e5\u671f:", bios.get("date", "-"))
        self._clayout.addWidget(card)
        # Disks
        disks = info.get("disks", [])
        if disks:
            card, cl = self._card("\u78c1\u76d8")
            for d in disks:
                mount = d.get("mount", "?:")
                total = d.get("total", 0); used = d.get("used", 0)
                pct = d.get("percent", 0)
                color = "#F44336" if pct > 85 else "#FF9800" if pct > 60 else "#4CAF50"
                self._row(cl, mount, format_size(used) + " / " + format_size(total) + f" (\u5df2\u7528{pct}%, \u53ef\u7528" + format_size(d.get("free",0)) + ")", color)
            self._clayout.addWidget(card)
        # Network
        adapters = info.get("network", [])
        if adapters:
            card, cl = self._card("\u7f51\u7edc\u9002\u914d\u5668")
            for ad in adapters[:4]:
                self._row(cl, ad.get("name","")[:50], ad.get("speed",""))
            self._clayout.addWidget(card)
        self._clayout.addStretch()
        self.status_message.emit("\u7cfb\u7edf\u4fe1\u606f\u52a0\u8f7d\u5b8c\u6210")
