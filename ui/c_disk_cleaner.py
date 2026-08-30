# -*- coding: utf-8 -*-
"""C盘专清 - 列出 C 盘各文件夹 + 用途标识 + AI 建议 + 用户决定清理。

布局约定（与全局 UI 规范一致）：
  第 1 行：页面标题（左） + 主操作/危险操作（右）
  第 2 行：进度条 + 状态
  中  部：主列表
  底  部：汇总信息（左） + 说明（右）
"""
import os as _os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QProgressBar, QMessageBox)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QColor, QBrush

from core.c_cleaner import (build_targets, CScanTarget, CScanWorker, CCleanWorker,
                            ADVICE_CLEAN, ADVICE_CONSIDER, ADVICE_USER, ADVICE_PROTECT,
                            ADVICE_LABELS, ACT_EMPTY, ACT_DELETE, ACT_RECYCLE, ACT_FEATURE, ACT_SKIP)
from utils.helpers import format_size

_ADVICE_COLOR = {
    ADVICE_CLEAN: "#4CAF50",
    ADVICE_CONSIDER: "#FF9800",
    ADVICE_USER: "#58a6ff",
    ADVICE_PROTECT: "#F44336",
}


class CDiskCleanerPage(QWidget):
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._targets = []
        self._scan_worker = None
        self._clean_worker = None
        self._loaded = False
        self._setup_ui()

    # ---------- UI ----------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        # 第 1 行：标题 + 操作按钮
        row1 = QHBoxLayout()
        title = QLabel("C盘专清")
        title.setObjectName("pageTitle")
        row1.addWidget(title)
        row1.addStretch()
        self.analyze_btn = QPushButton("开始 AI 分析")
        self.analyze_btn.setObjectName("greenBtn")
        self.analyze_btn.clicked.connect(self._start_scan)
        row1.addWidget(self.analyze_btn)
        self.clean_btn = QPushButton("清理选中项")
        self.clean_btn.setObjectName("redBtn")
        self.clean_btn.setEnabled(False)
        self.clean_btn.clicked.connect(self._clean_selected)
        row1.addWidget(self.clean_btn)
        layout.addLayout(row1)

        # 第 2 行：进度 + 状态
        row2 = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(14)
        row2.addWidget(self.progress, 1)
        self.slbl = QLabel("点击「开始 AI 分析」扫描 C 盘各文件夹占用与可清理项")
        self.slbl.setStyleSheet("color:#8b949e;font-size:12px;")
        row2.addWidget(self.slbl)
        layout.addLayout(row2)

        # 主列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["", "文件夹", "类别", "大小", "文件数", "AI 建议", "说明 / AI 分析理由"])
        self.tree.setColumnWidth(0, 36)
        self.tree.setColumnWidth(1, 250)
        self.tree.setColumnWidth(2, 90)
        self.tree.setColumnWidth(3, 90)
        self.tree.setColumnWidth(4, 70)
        self.tree.setColumnWidth(5, 100)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree, 1)

        # 底部：汇总 + 提示
        row4 = QHBoxLayout()
        self.summary_lbl = QLabel("")
        self.summary_lbl.setStyleSheet("color:#4CAF50;font-size:12px;font-weight:bold;")
        row4.addWidget(self.summary_lbl)
        row4.addStretch()
        hint = QLabel("✅ 建议清理项已自动勾选；缓存类清理为永久删除（不进回收站），请确认后执行")
        hint.setStyleSheet("color:#8b949e;font-size:11px;")
        row4.addWidget(hint)
        layout.addLayout(row4)

    # ---------- 数据 ----------
    def _set_visible(self, visible):
        if visible and not self._loaded:
            self._loaded = True
            self._start_scan()

    def _start_scan(self):
        if self._scan_worker and self._scan_worker.isRunning():
            return
        self.tree.clear()
        self._targets = [CScanTarget(*t) for t in build_targets()]
        self.analyze_btn.setEnabled(False)
        self.clean_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, len(self._targets))
        self.progress.setValue(0)
        self._scan_worker = CScanWorker(self._targets)
        self._scan_worker.item_updated.connect(self._on_item_updated)
        self._scan_worker.progress.connect(self.slbl.setText)
        self._scan_worker.finished_all.connect(self._on_scan_done)
        self._scan_worker.start()

    def _on_item_updated(self, target):
        row = self._make_row(target)
        self.tree.addTopLevelItem(row)
        self.progress.setValue(self.progress.value() + 1)

    def _make_row(self, t):
        item = QTreeWidgetItem()
        name = _os.path.basename(t.path.rstrip("\\")) or t.path
        item.setText(1, name)
        item.setToolTip(1, t.path)
        item.setText(2, t.category)
        item.setText(3, (format_size(t.size) + ("+" if t.approximate else "")) if t.scanned else "—")
        item.setText(4, f"{t.file_count}" if t.scanned else "—")
        item.setText(5, ADVICE_LABELS.get(t.advice, t.advice))
        item.setText(6, t.reason)
        for c in (1, 2, 3, 4, 6):
            item.setToolTip(c, t.reason if c == 6 else item.text(c))
        color = QColor(_ADVICE_COLOR.get(t.advice, "#888"))
        item.setForeground(5, QBrush(color))
        if t.advice == ADVICE_PROTECT:
            item.setForeground(1, QBrush(QColor("#F44336")))
        if t.size == 0 and t.scanned:
            item.setForeground(3, QBrush(QColor("#666")))
        item.setCheckState(0, Qt.Checked if t.advice == ADVICE_CLEAN else Qt.Unchecked)
        if t.action in (ACT_SKIP,):
            # 系统勿动/用户数据行：不可勾选，防止误操作
            item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
        item.setData(0, Qt.UserRole, t)
        return item

    def _on_scan_done(self, targets):
        self.analyze_btn.setEnabled(True)
        self.progress.setVisible(False)
        clean_size = sum(t.size for t in targets if t.advice == ADVICE_CLEAN)
        consider = sum(1 for t in targets if t.advice == ADVICE_CONSIDER)
        self.clean_btn.setEnabled(True)
        self.summary_lbl.setText(
            "AI 判定可直接清理: " + format_size(clean_size) +
            "　|　另有 " + str(consider) + " 项可考虑（已列出理由，由你决定）")
        self.slbl.setText("分析完成——绿色✅项已自动勾选，取消或补充勾选后点「清理选中项」")
        self.status_message.emit("C盘专清: AI 分析完成，可直接释放 " + format_size(clean_size))
        self._update_checked_summary()

    def _on_item_changed(self, item, col):
        if col == 0:
            self._update_checked_summary()

    def _update_checked_summary(self):
        total = 0
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            t = it.data(0, Qt.UserRole)
            if t is not None and it.checkState(0) == Qt.Checked:
                total += t.size
        base = self.summary_lbl.text().split("　|　")[0]
        if total > 0:
            self.summary_lbl.setText(base + "　|　当前勾选: " + format_size(total))

    # ---------- 执行 ----------
    def _clean_selected(self):
        jobs = []
        names = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            t = it.data(0, Qt.UserRole)
            if t is None or it.checkState(0) != Qt.Checked:
                continue
            if t.action in (ACT_SKIP,):
                continue
            jobs.append((t, t.action))
            names.append("• " + it.text(1) + "（" + it.text(2) + "，" + it.text(3) + "）")
        if not jobs:
            QMessageBox.information(self, "提示", "请先勾选要清理的项目")
            return
        msg = ("将对以下 " + str(len(jobs)) + " 项执行清理：\n\n" +
               chr(10).join(names[:12]) +
               ("\n... 等共 " + str(len(jobs)) + " 项" if len(jobs) > 12 else "") +
               "\n\n⚠ 注意：临时/缓存类内容将被【永久删除，不进回收站】"
               "（均为可再生数据，被占用文件会自动跳过）。\n确定继续？")
        r = QMessageBox.warning(self, "确认清理", msg,
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        self.clean_btn.setEnabled(False)
        self.analyze_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, len(jobs))
        self.progress.setValue(0)
        self._clean_worker = CCleanWorker(jobs)
        self._clean_worker.progress.connect(self.slbl.setText)
        self._clean_worker.item_done.connect(self._on_clean_item)
        self._clean_worker.finished_all.connect(self._on_clean_done)
        self._clean_worker.start()

    def _on_clean_item(self, target, ok, freed, skipped):
        self.progress.setValue(self.progress.value() + 1)
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.data(0, Qt.UserRole) is target:
                if ok:
                    it.setText(3, format_size(0))
                    it.setText(4, "0")
                    it.setText(6, "已清理，释放 " + format_size(freed) +
                               ("（跳过占用 " + str(skipped) + " 项）" if skipped else ""))
                    it.setCheckState(0, Qt.Unchecked)
                else:
                    it.setText(6, "清理失败（权限不足或文件被占用）")
                break

    def _on_clean_done(self, total_freed, total_skipped):
        self.clean_btn.setEnabled(True)
        self.analyze_btn.setEnabled(True)
        self.progress.setVisible(False)
        msg = "清理完成! 共释放 " + format_size(total_freed)
        if total_skipped:
            msg += "（跳过占用文件 " + str(total_skipped) + " 个）"
        self.slbl.setText(msg)
        self.summary_lbl.setText("本次已释放: " + format_size(total_freed))
        self.status_message.emit(msg)
        QMessageBox.information(self, "完成", msg)
