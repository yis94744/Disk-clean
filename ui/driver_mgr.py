# -*- coding: utf-8 -*-
"""驱动检测 - 扫描系统驱动、按日期/厂商给出更新建议、一键前往官网下载。

布局遵循全局规范：
  第 1 行：标题（左） + Windows 更新 / 开始扫描（右）
  第 2 行：进度条 + 状态
  第 3 行：类别过滤 + 搜索 + 仅看建议更新（左）
  主列表：设备 / 类别 / 厂商 / 当前版本 / 驱动日期 / AI 建议（双击行直达官网）
  底  部：前往选中设备官网（左） + 汇总（右）
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QProgressBar, QComboBox,
    QLineEdit, QMenu, QApplication, QMessageBox)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QBrush, QAction

from core.driver_query import (DriverScanWorker, open_site, WINDOWS_UPDATE,
    ADVICE_OK, ADVICE_CHECK, ADVICE_OLD, ADVICE_WU, ADVICE_LABELS,
    CATEGORY_NAMES, IMPORTANT_CLASSES, is_noise_device, DRIVER_GROUPS,
    group_advice)

_ADVICE_COLOR = {
    ADVICE_OK: "#4CAF50",
    ADVICE_CHECK: "#FF9800",
    ADVICE_OLD: "#F85149",
    ADVICE_WU: "#58a6ff",
}


class DriverMgrPage(QWidget):
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drivers = []
        self._worker = None
        self._loaded = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        # 第 1 行：标题 + 操作
        row1 = QHBoxLayout()
        title = QLabel("驱动检测")
        title.setObjectName("pageTitle")
        row1.addWidget(title)
        row1.addStretch()
        self.wu_btn = QPushButton("Windows 更新")
        self.wu_btn.clicked.connect(self._open_windows_update)
        self.wu_btn.setToolTip("打开 Windows 更新的「可选更新」，微软驱动的更新发布在这里")
        row1.addWidget(self.wu_btn)
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.setObjectName("greenBtn")
        self.scan_btn.clicked.connect(self._start_scan)
        row1.addWidget(self.scan_btn)
        layout.addLayout(row1)

        # 第 2 行：进度 + 状态
        row2 = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(14)
        self.progress.setRange(0, 0)  # 忙碌态
        row2.addWidget(self.progress, 1)
        self.slbl = QLabel("点击「开始扫描」检测系统驱动与更新建议")
        self.slbl.setStyleSheet("color:#8b949e;font-size:12px;")
        row2.addWidget(self.slbl)
        layout.addLayout(row2)

        # 第 3 行：过滤器（分组即分类，这里只留搜索与建议过滤）
        row3 = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索设备/厂商...")
        self.search_edit.setMaximumWidth(220)
        self.search_edit.textChanged.connect(self._apply_filter)
        row3.addWidget(self.search_edit)
        self.only_advice = QPushButton("仅看建议更新")
        self.only_advice.setCheckable(True)
        self.only_advice.clicked.connect(self._apply_filter)
        row3.addWidget(self.only_advice)
        self.show_all_chk = QPushButton("显示全部小驱动")
        self.show_all_chk.setCheckable(True)
        self.show_all_chk.setToolTip("默认隐藏 WAN Miniport、虚拟设备等碎片驱动，勾选后完整展示")
        self.show_all_chk.clicked.connect(self._apply_filter)
        row3.addWidget(self.show_all_chk)
        row3.addStretch()
        layout.addLayout(row3)

        # 主列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["硬件分类 / 设备", "类别", "厂商", "当前版本", "驱动日期", "AI 建议"])
        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 90)
        self.tree.setColumnWidth(2, 170)
        self.tree.setColumnWidth(3, 130)
        self.tree.setColumnWidth(4, 100)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.itemDoubleClicked.connect(lambda it, col: self._open_selected())
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.tree, 1)

        # 底部：官网跳转 + 汇总
        row5 = QHBoxLayout()
        self.site_btn = QPushButton("前往选中设备官网")
        self.site_btn.setEnabled(False)
        self.site_btn.clicked.connect(self._open_selected)
        row5.addWidget(self.site_btn)
        row5.addStretch()
        self.summary_lbl = QLabel("")
        self.summary_lbl.setStyleSheet("color:#4CAF50;font-size:12px;font-weight:bold;")
        row5.addWidget(self.summary_lbl)
        layout.addLayout(row5)

    # ---------- 扫描 ----------
    def _set_visible(self, visible):
        if visible and not self._loaded:
            self._loaded = True
            self._start_scan()

    def _start_scan(self):
        if self._worker and self._worker.isRunning():
            return
        self.tree.clear()
        self._drivers = []
        self.scan_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.slbl.setText("正在枚举驱动...")
        self._worker = DriverScanWorker()
        self._worker.progress.connect(self.slbl.setText)
        self._worker.finished_all.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, drivers):
        self._drivers = drivers
        self.scan_btn.setEnabled(True)
        self.progress.setVisible(False)
        self._apply_filter()
        need = sum(1 for d in drivers if d["advice"] in (ADVICE_CHECK, ADVICE_OLD))
        self.status_message.emit(f"驱动检测: {len(drivers)} 个驱动，{need} 个建议检查更新")

    # ---------- 过滤 ----------
    def _apply_filter(self):
        tx = self.search_edit.text().lower() if hasattr(self, "search_edit") else ""
        only = self.only_advice.isChecked() if hasattr(self, "only_advice") else False
        show_all = self.show_all_chk.isChecked() if hasattr(self, "show_all_chk") else False
        self.tree.clear()
        self.summary_lbl.setText("")

        # 按类别码分桶；噪音设备（WAN Miniport/虚拟设备等）归入"其它驱动"折叠组
        buckets = {gname: [] for _, gname, _ in DRIVER_GROUPS}
        buckets["其它驱动"] = []
        for d in self._drivers:
            noise = is_noise_device(d["name"], d["maker"])
            placed = False
            for codes, gname, _ in DRIVER_GROUPS:
                if d["cls"] in codes:
                    buckets[gname].append(d)
                    placed = True
                    break
            if not placed or noise:
                # 噪音设备从原组移入"其它驱动"
                if noise and placed:
                    for codes, gname, _ in DRIVER_GROUPS:
                        if d["cls"] in codes and d in buckets[gname]:
                            buckets[gname].remove(d)
                            break
                buckets["其它驱动"].append(d)

        need_groups = 0
        total_check = 0
        for codes, gname, icon in DRIVER_GROUPS:
            devs = buckets.get(gname, [])
            if only:
                devs = [d for d in devs if d["advice"] in (ADVICE_CHECK, ADVICE_OLD)]
            if tx:
                devs = [d for d in devs if tx in d["name"].lower() or tx in (d["maker"] or "").lower()]
            if not devs:
                continue
            gadv = group_advice([d["advice"] for d in devs])
            if gadv in (ADVICE_CHECK, ADVICE_OLD):
                need_groups += 1
            total_check += sum(1 for d in devs if d["advice"] in (ADVICE_CHECK, ADVICE_OLD))
            main_dev = devs[0]
            gnode = QTreeWidgetItem()
            gnode.setText(0, f"{icon} {gname}")
            gnode.setText(2, f"{len(devs)} 个设备")
            gnode.setText(3, main_dev["version"])
            gnode.setText(4, main_dev["date"])
            gnode.setText(5, ADVICE_LABELS.get(gadv, gadv))
            color = QColor(_ADVICE_COLOR.get(gadv, "#888"))
            gnode.setForeground(5, QBrush(color))
            gnode.setForeground(0, QBrush(QColor("#e9f5ec")))
            bf = gnode.font(0)
            bf.setBold(True)
            gnode.setFont(0, bf)
            gnode.setData(0, Qt.UserRole, main_dev)
            gnode.setData(0, Qt.UserRole + 1, "group")
            self.tree.addTopLevelItem(gnode)
            for d in devs:
                gnode.addChild(self._make_row(d))
        # 其它驱动（含噪音碎片）折叠展示，不参与建议计数
        others = buckets.get("其它驱动", [])
        if show_all and others:
            if tx:
                others = [d for d in others if tx in d["name"].lower() or tx in (d["maker"] or "").lower()]
            if others:
                gnode = QTreeWidgetItem()
                gnode.setText(0, f"🔧 其它驱动（WAN Miniport / 虚拟设备等碎片）")
                gnode.setText(2, f"{len(others)} 个设备")
                self.tree.addTopLevelItem(gnode)
                for d in others:
                    gnode.addChild(self._make_row(d))
        self.tree.expandAll()
        # 设备多的大组默认折叠，保持首屏聚焦显卡/声卡/网卡等重点分类
        for i in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(i)
            if g.childCount() > 10:
                g.setExpanded(False)
        self.summary_lbl.setText(
            f"共 {len(self._drivers)} 个驱动 | {need_groups} 个硬件分类建议检查更新"
            + (f" | {total_check} 个具体驱动待更新" if total_check else ""))
        self.slbl.setText("按硬件分类展示——点击分类行或设备行，再点「前往选中设备官网」直达下载页")

    def _make_row(self, d):
        item = QTreeWidgetItem()
        item.setText(0, d["name"])
        item.setText(1, CATEGORY_NAMES.get(d["cls"], d["cls"] or "—"))
        item.setText(2, d["maker"] or "—")
        item.setText(3, d["version"])
        item.setText(4, d["date"])
        item.setText(5, ADVICE_LABELS.get(d["advice"], d["advice"]))
        color = QColor(_ADVICE_COLOR.get(d["advice"], "#888"))
        item.setForeground(5, QBrush(color))
        if d["advice"] == ADVICE_OLD:
            item.setForeground(0, QBrush(QColor("#F85149")))
        item.setToolTip(0, d["name"] + "  |  官网: " +
                        (d["site"] if d["site"].startswith("http") else "Windows 更新（可选更新）"))
        item.setData(0, Qt.UserRole, d)
        return item

    # ---------- 跳转 ----------
    def _open_selected(self):
        it = self.tree.currentItem()
        if not it:
            QMessageBox.information(self, "提示", "请先选择一个驱动设备")
            return
        d = it.data(0, Qt.UserRole)
        if d and not open_site(d["site"]):
            QMessageBox.warning(self, "失败", "无法打开链接: " + d["site"])

    def _open_windows_update(self):
        open_site(WINDOWS_UPDATE)

    def _context_menu(self, pos):
        it = self.tree.itemAt(pos)
        if not it:
            return
        d = it.data(0, Qt.UserRole)
        menu = QMenu(self)
        act = QAction("前往官网下载驱动", self)
        act.triggered.connect(self._open_selected)
        menu.addAction(act)
        if d:
            act2 = QAction("复制设备名", self)
            act2.triggered.connect(lambda: (QApplication.clipboard().setText(d["name"])))
            menu.addAction(act2)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))
