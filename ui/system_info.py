"""System Info - thread-safe loading with QThread + progress bar"""
import warnings
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QProgressBar)
from PySide6.QtCore import Signal, Qt, QTimer, QThread, QObject
from PySide6.QtGui import QFont
from utils.helpers import format_size
from core.system_query import SystemQuery

class _SystemWorker(QObject):
    progress = Signal(str)
    progress_value = Signal(int)
    finished = Signal(dict)

    def run(self):
        query = SystemQuery()
        query.progress.connect(self.progress.emit)
        query.progress_value.connect(self.progress_value.emit)
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
        self._loading_label = None
        self._progress = None
        self._setup_ui()
        QTimer.singleShot(500, self._start_load)

    def _setup_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16)
        tb = QHBoxLayout()
        t = QLabel("\u7cfb\u7edf\u4fe1\u606f")
        t.setObjectName("pageTitle"); tb.addWidget(t); tb.addStretch()
        r = QPushButton("\u5237\u65b0"); r.clicked.connect(self._start_load); tb.addWidget(r)
        layout.addLayout(tb)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self.content = QWidget()
        from utils.themes import panel_qss
        self.content.setStyleSheet(panel_qss())
        self._clayout = QVBoxLayout(self.content)
        self._clayout.setContentsMargins(0,0,0,0); self._clayout.setSpacing(16)
        self.scroll.setWidget(self.content); layout.addWidget(self.scroll)

    def _set_visible(self, visible):
        if visible and not self._loaded and not self._loading:
            self._start_load()

    def update_theme_styles(self):
        from utils.themes import panel_qss
        self.content.setStyleSheet(panel_qss())

    def _clear_content(self):
        while self._clayout.count():
            item = self._clayout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

    def _start_load(self):
        if self._loading: return
        self._loading = True; self._loaded = True
        self._clear_content()

        self._loading_label = QLabel("\u6b63\u5728\u8bfb\u53d6\u7cfb\u7edf\u6570\u636e...")
        self._loading_label.setStyleSheet("color:#58a6ff;font-size:16px;padding:24px;font-weight:bold;background:transparent;")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._clayout.addWidget(self._loading_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._clayout.addWidget(self._progress)
        self._clayout.addStretch()

        # Clean up previous thread
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)

        self._thread = QThread()
        self._worker = _SystemWorker()
        self._worker.moveToThread(self._thread)
        self._worker.finished.connect(self._display)
        self._worker.progress.connect(self._on_step)
        self._worker.progress_value.connect(self._on_step_value)
        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(lambda: setattr(self, '_thread', None))
        self._thread.start()

    def _on_step(self, msg):
        if self._loading_label:
            try: self._loading_label.setText(msg)
            except: pass
        self.status_message.emit(msg)

    def _on_step_value(self, value):
        if self._progress is not None:
            try: self._progress.setValue(int(value))
            except: pass

    @staticmethod
    def _temp_color(t):
        if t is None: return "#8b949e"
        if t >= 85: return "#F44336"
        if t >= 60: return "#FF9800"
        return "#4CAF50"

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

    def _hint(self, parent_layout, text):
        hl = QLabel(text)
        hl.setStyleSheet("color:#eab308;font-size:11px;background:transparent;")
        hl.setWordWrap(True)
        parent_layout.addWidget(hl)

    def _display(self, info):
        self._loading = False
        self._loading_label = None
        self._progress = None
        self._clear_content()
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
        # ── 硬盘健康 / 寿命 ──
        card, cl = self._card("\u786c\u76d8\u5065\u5eb7 / \u5bff\u547d")
        dh = info.get("disk_health") or []
        if not dh:
            self._hint(cl, "\u26a0 \u672a\u80fd\u8bfb\u53d6\u786c\u76d8\u5065\u5eb7\u6570\u636e"
                           "\uff08Get-PhysicalDisk \u4e0d\u53ef\u7528\u6216\u9700\u8981\u7ba1\u7406\u5458\u6743\u9650\uff09\u3002")
        else:
            hmap = {"Healthy": ("\u6b63\u5e38", "#4CAF50"),
                    "Warning": ("\u8b66\u544a", "#FF9800"),
                    "Unhealthy": ("\u5f02\u5e38", "#F44336")}
            for i, d in enumerate(dh):
                model = d.get("model") or f"\u786c\u76d8 #{i+1}"
                if len(model) > 30: model = model[:30] + "\u2026"
                media = d.get("media", ""); bus = d.get("bus", "")
                kind = " / ".join(x for x in
                    [media if media and media != "Unspecified" else "",
                     bus if bus and bus not in ("", "Unknown") else ""] if x)
                hn, hc = hmap.get(d.get("health", ""), ("\u672a\u77e5", "#8b949e"))
                parts = [f"\u5065\u5eb7\u72b6\u6001: {hn}"]
                wear = d.get("wear")
                if wear is not None:
                    remaining = max(0, 100 - int(wear))
                    parts.append(f"\u5269\u4f59\u5bff\u547d: {remaining}%\uff08\u5df2\u78e8\u635f {int(wear)}%\uff09")
                ttemp = d.get("temperature")
                if ttemp is not None:
                    parts.append(f"\u6e29\u5ea6: {int(ttemp)} \u00b0C")
                hours = d.get("power_on_hours")
                if hours:
                    parts.append(f"\u901a\u7535: {hours} \u5c0f\u65f6\uff08\u7ea6 {hours // 24} \u5929\uff09")
                key = model + (f"  [{kind}]" if kind else "")
                self._row(cl, key, "  \u00b7  ".join(parts), hc)
        self._clayout.addWidget(card)
        # ── 温度监控 ──
        card, cl = self._card("\u6e29\u5ea6\u76d1\u63a7")
        mon = info.get("monitor") or {}
        any_temp = False
        ct = mon.get("cpu_temp")
        if ct is not None:
            any_temp = True
            src = mon.get("cpu_temp_source") or ""
            val = f"{ct:.0f} \u00b0C" + (f"\uff08{src}\uff09" if src else "")
            self._row(cl, "CPU \u6e29\u5ea6:", val, self._temp_color(ct))
        else:
            self._row(cl, "CPU \u6e29\u5ea6:", "\u65e0\u6cd5\u8bfb\u53d6", "#8b949e")
        load = mon.get("cpu_load")
        if load is not None:
            self._row(cl, "CPU \u5360\u7528:", f"{load}%", "#e6edf3")
        for i, g in enumerate(mon.get("gpus") or []):
            gt = g.get("temp")
            if gt is not None: any_temp = True
            nm = g.get("name") or f"GPU #{i+1}"
            if len(nm) > 34: nm = nm[:34] + "\u2026"
            if gt is not None:
                val = f"{gt:.0f} \u00b0C"
                if g.get("load"):
                    val += f"\uff08\u8d1f\u8f7d {g['load']}%\uff09"
            else:
                val = "\u65e0\u6cd5\u8bfb\u53d6"
            self._row(cl, nm + ":", val, self._temp_color(gt))
        for f in (mon.get("fans") or [])[:4]:
            self._row(cl, "\u98ce\u6247:", f"{f['name']} \u2014 {f['rpm']} RPM", "#8899aa")
        if not any_temp:
            self._hint(cl, "\u26a0 \u65e0\u6cd5\u8bfb\u53d6\u6e29\u5ea6\u4f20\u611f\u5668\u3002\u8bf7\u4ee5\u7ba1\u7406\u5458\u8eab\u4efd"
                           "\u8fd0\u884c\u540e\u91cd\u8bd5\uff0c\u6216\u5b89\u88c5\u5e76\u8fd0\u884c LibreHardwareMonitor"
                           "\uff08\u5f00\u6e90\u786c\u4ef6\u76d1\u63a7\uff09\u540e\u70b9\u51fb\u5237\u65b0\uff0c"
                           "\u5373\u53ef\u83b7\u5f97\u7cbe\u786e\u7684 CPU/\u663e\u5361\u6e29\u5ea6\u3002")
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
