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
    CATEGORY_NAMES, IMPORTANT_CLASSES)

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

        # 第 3 行：过滤器
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("类别:"))
        self.cat_combo = QComboBox()
        self.cat_combo.setMinimumWidth(100)
        self.cat_combo.addItem("全部类别", "")
        for en, cn in CATEGORY_NAMES.items():
            self.cat_combo.addItem(cn, en)
        self.cat_combo.currentIndexChanged.connect(self._apply_filter)
        row3.addWidget(self.cat_combo)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索设备/厂商...")
        self.search_edit.setMaximumWidth(170)
        self.search_edit.textChanged.connect(self._apply_filter)
        row3.addWidget(self.search_edit)
        self.only_advice = QPushButton("仅看建议更新")
        self.only_advice.setCheckable(True)
        self.only_advice.clicked.connect(self._apply_filter)
        row3.addWidget(self.only_advice)
        row3.addStretch()
        layout.addLayout(row3)

        # 主列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["设备名", "类别", "厂商", "当前版本", "驱动日期", "AI 建议"])
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
        self.summary_lbl.setText(
            f"共 {len(drivers)} 个驱动设备 | {need} 个建议检查更新")
        self.slbl.setText("扫描完成——双击设备行或点「前往选中设备官网」直达官方驱动下载页")
        self.status_message.emit(f"驱动检测: {len(drivers)} 个设备，{need} 个建议检查更新")

    # ---------- 过滤 ----------
    def _apply_filter(self):
        cat = self.cat_combo.currentData() or ""
        tx = self.search_edit.text().lower() if hasattr(self, "search_edit") else ""
        only = self.only_advice.isChecked() if hasattr(self, "only_advice") else False
        self.tree.clear()
        for d in self._drivers:
            if cat and d["cls"] != cat:
                continue
            if only and d["advice"] not in (ADVICE_CHECK, ADVICE_OLD):
                continue
            if tx and tx not in d["name"].lower() and tx not in d["maker"].lower():
                continue
            self.tree.addTopLevelItem(self._make_row(d))

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
        item.setToolTip(0, d["name"] + "\n官网: " + (d["site"] if d["site"].startswith("http") else "Windows 更新（可选更新）"))
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
