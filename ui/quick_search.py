# -*- coding: utf-8 -*-
"""极速搜索 - 输入文件名实时查找全盘文件（NTFS MFT 索引，Everything 同款原理）。

布局遵循全局规范：
  第 1 行：标题（左） + 索引状态 + 重建索引（右）
  第 2 行：大搜索框
  第 3 行：结果统计
  主列表：文件名 / 所在路径 / 类型
  底  部：打开文件（左） + 打开所在位置 + 说明（右）
"""
import os as _os
import subprocess as _sp

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QProgressBar, QMessageBox,
    QLineEdit)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QFont, QColor, QBrush

from core.fast_search import (FastSearchIndex, IndexBuildWorker, SearchWorker,
                              ntfs_fixed_drives)
from utils.helpers import is_admin


class QuickSearchPage(QWidget):
    status_message = Signal(str)

    RESULT_LIMIT = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.index = FastSearchIndex()
        self._build_worker = None
        self._search_worker = None
        self._search_gen = 0
        self._loaded = False
        self._setup_ui()

    # ---------- UI ----------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        # 第 1 行：标题 + 索引状态 + 重建
        row1 = QHBoxLayout()
        title = QLabel("极速搜索")
        title.setObjectName("pageTitle")
        row1.addWidget(title)
        row1.addStretch()
        self.state_lbl = QLabel("索引未构建")
        self.state_lbl.setStyleSheet("color:#8b949e;font-size:12px;")
        row1.addWidget(self.state_lbl)
        self.rebuild_btn = QPushButton("重建索引")
        self.rebuild_btn.clicked.connect(self._start_build)
        row1.addWidget(self.rebuild_btn)
        layout.addLayout(row1)

        # 第 2 行：搜索框（大）
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入文件名关键词，实时全盘查找（大小写不敏感）...")
        f = QFont("Microsoft YaHei", 13)
        self.search_edit.setFont(f)
        self.search_edit.setMinimumHeight(36)
        self.search_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.search_edit)

        # 第 3 行：进度 + 结果统计
        row3 = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(12)
        row3.addWidget(self.progress, 1)
        self.stat_lbl = QLabel("")
        self.stat_lbl.setStyleSheet("color:#8b949e;font-size:12px;")
        row3.addWidget(self.stat_lbl)
        layout.addLayout(row3)

        # 主列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["文件名", "所在路径", "类型"])
        self.tree.setColumnWidth(0, 280)
        self.tree.setColumnWidth(1, 560)
        self.tree.setColumnWidth(2, 70)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.itemDoubleClicked.connect(lambda it, col: self._open_file())
        layout.addWidget(self.tree, 1)

        # 底部：操作
        row5 = QHBoxLayout()
        self.open_btn = QPushButton("打开文件")
        self.open_btn.setObjectName("greenBtn")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._open_file)
        row5.addWidget(self.open_btn)
        self.locate_btn = QPushButton("打开所在位置")
        self.locate_btn.setEnabled(False)
        self.locate_btn.clicked.connect(self._open_location)
        row5.addWidget(self.locate_btn)
        row5.addStretch()
        hint = QLabel("双击结果直接打开；索引基于 NTFS MFT，新建/删除文件后请点「重建索引」")
        hint.setObjectName("pageHint")
        row5.addWidget(hint)
        layout.addLayout(row5)

    # ---------- 索引 ----------
    def _set_visible(self, visible):
        if visible and not self._loaded:
            self._loaded = True
            if not self.index.count:
                self._start_build()

    def _start_build(self):
        if self._build_worker and self._build_worker.isRunning():
            return
        if not is_admin():
            QMessageBox.warning(self, "需要管理员权限",
                "极速搜索依赖 NTFS MFT 直读（Everything 同款原理），需要管理员权限。\n"
                "请以管理员身份运行后再使用本功能。")
            return
        drives = ntfs_fixed_drives()
        if not drives:
            QMessageBox.warning(self, "未找到可用卷", "没有检测到本地 NTFS 磁盘。")
            return
        self.rebuild_btn.setEnabled(False)
        self.search_edit.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.state_lbl.setText("索引构建中...")
        self.slbl_placeholder()
        self._build_worker = IndexBuildWorker(self.index, drives)
        self._build_worker.progress.connect(self._on_build_progress)
        self._build_worker.done.connect(self._on_build_done)
        self._build_worker.start()

    def slbl_placeholder(self):
        self.stat_lbl.setText("")

    def _on_build_progress(self, msg):
        self.stat_lbl.setText(msg)

    def _on_build_done(self, ok, err):
        self.rebuild_btn.setEnabled(True)
        self.search_edit.setEnabled(True)
        self.progress.setVisible(False)
        if ok:
            self.state_lbl.setText(
                f"索引就绪：{self.index.count} 条（{', '.join(self.index.drives)}）"
                f"｜构建耗时 {self.index.build_seconds:.1f}s")
            self.stat_lbl.setText("输入关键词开始搜索")
            self.status_message.emit(
                f"极速搜索: 索引完成，{self.index.count} 条记录，耗时 {self.index.build_seconds:.1f}s")
            self.search_edit.setFocus()
        else:
            self.state_lbl.setText("索引构建失败")
            self.stat_lbl.setText(err or "未知错误")
            self.status_message.emit("极速搜索: 索引构建失败")

    # ---------- 搜索 ----------
    def _on_text_changed(self, text):
        self._search_gen += 1
        text = (text or "").strip()
        if not text:
            self.tree.clear()
            self.stat_lbl.setText("")
            self.open_btn.setEnabled(False)
            self.locate_btn.setEnabled(False)
            return
        if not self.index.count:
            return
        gen = self._search_gen
        self._search_worker = SearchWorker(gen, self.index, text, self.RESULT_LIMIT)
        self._search_worker.done.connect(self._on_search_done)
        self._search_worker.start()

    def _on_search_done(self, gen, keyword, elapsed_ms, _count):
        if gen != self._search_gen:
            return  # 过期结果丢弃
        results = self._search_worker.results
        self.tree.clear()
        self.tree.setUpdatesEnabled(False)
        for r in results:
            item = QTreeWidgetItem()
            item.setText(0, r["name"])
            item.setText(1, r["path"])
            item.setText(2, "文件夹" if r["is_dir"] else "文件")
            if r["is_dir"]:
                item.setForeground(2, QBrush(QColor("#e3b341")))
            item.setData(0, Qt.UserRole, r["path"])
            self.tree.addTopLevelItem(item)
        self.tree.setUpdatesEnabled(True)
        more = "（仅显示前 " + str(self.RESULT_LIMIT) + " 条）" if len(results) >= self.RESULT_LIMIT else ""
        self.stat_lbl.setText(f"找到 {len(results)} 条{more} · 耗时 {elapsed_ms:.0f} ms")
        has = bool(results)
        self.open_btn.setEnabled(has)
        self.locate_btn.setEnabled(has)

    # ---------- 操作 ----------
    def _selected_path(self):
        it = self.tree.currentItem()
        return it.data(0, Qt.UserRole) if it else None

    def _open_file(self):
        path = self._selected_path()
        if not path:
            return
        if not _os.path.exists(path):
            QMessageBox.warning(self, "无法打开",
                "该文件当前不存在——索引可能已过期，请点「重建索引」刷新。")
            return
        try:
            _os.startfile(path)
        except OSError as e:
            QMessageBox.warning(self, "打开失败", str(e))

    def _open_location(self):
        path = self._selected_path()
        if not path:
            return
        if not _os.path.exists(path):
            QMessageBox.warning(self, "无法定位",
                "该文件当前不存在——索引可能已过期，请点「重建索引」刷新。")
            return
        try:
            _sp.Popen(["explorer", "/select,", path])
        except Exception as e:
            QMessageBox.warning(self, "定位失败", str(e))
