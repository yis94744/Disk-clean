"""安全清理页面"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QProgressBar, QMessageBox)
from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtGui import QFont
from core.cleaner_engine import CleanerEngine
from core.registry_cleaner import RegistryScanner
from utils.helpers import format_size
from utils.constants import SAFETY_LABELS

class CleanerWorker(QThread):
    progress = Signal(str)
    item_done = Signal(object)
    finished = Signal(list)

    def __init__(self, engine, items):
        super().__init__()
        self.engine = engine
        self.items = items
        # Connect signals BEFORE thread starts
        self.engine.progress.connect(self._on_progress)
        self.engine.item_updated.connect(self._on_item)
        self.engine.finished.connect(self._on_finished)

    def _on_progress(self, msg):
        self.progress.emit(msg)

    def _on_item(self, item):
        self.item_done.emit(item)

    def _on_finished(self, items):
        self.finished.emit(items)

    def run(self):
        self.engine.analyze(self.items)


class SafeCleanerPage(QWidget):
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._engine = CleanerEngine()
        self._reg_scanner = None
        self._reg_issues = []
        self._setup_ui()
        self._load_items()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Toolbar
        tb = QHBoxLayout()
        title = QLabel("安全清理")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title.setStyleSheet("color: #e0e0e0;")
        tb.addWidget(title)
        tb.addStretch()

        self.analyze_btn = QPushButton("分析可清理项")
        self.analyze_btn.setObjectName("greenBtn")
        self.analyze_btn.clicked.connect(self._analyze)
        tb.addWidget(self.analyze_btn)

        self.clean_btn = QPushButton("一键清理")
        self.clean_btn.setObjectName("redBtn")
        self.clean_btn.clicked.connect(self._clean)
        self.clean_btn.setEnabled(False)
        tb.addWidget(self.clean_btn)
        layout.addLayout(tb)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.slbl = QLabel("点击分析可清理项扫描垃圾")
        self.slbl.setStyleSheet("color: #888;")
        layout.addWidget(self.slbl)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["项目", "类别", "大小", "安全等级", "文件数", "状态"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 80)
        self.tree.setColumnWidth(3, 80)
        self.tree.setColumnWidth(4, 60)
        layout.addWidget(self.tree)

        self.total = QLabel("")
        self.total.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        self.total.setStyleSheet("color: #4CAF50; padding: 8px;")
        layout.addWidget(self.total)

        # Registry section
        reg_label = QLabel("注册表清理 - 扫描无效注册表项")
        reg_label.setStyleSheet("color: #8b949e; font-size: 12px; padding-top: 8px;")
        layout.addWidget(reg_label)

        reg_btn_row = QHBoxLayout()
        reg_btn = QPushButton("扫描注册表")
        reg_btn.clicked.connect(self._scan_reg)
        reg_btn_row.addWidget(reg_btn)

        self.reg_clean_btn = QPushButton("一键清理选中")
        self.reg_clean_btn.setObjectName("redBtn")
        self.reg_clean_btn.clicked.connect(self._clean_reg)
        self.reg_clean_btn.setEnabled(False)
        reg_btn_row.addWidget(self.reg_clean_btn)
        reg_btn_row.addStretch()
        layout.addLayout(reg_btn_row)

        self.reg_tree = QTreeWidget()
        self.reg_tree.setHeaderLabels(["项目", "类型", "描述"])
        self.reg_tree.setColumnWidth(0, 200)
        self.reg_tree.setColumnWidth(1, 100)
        self.reg_tree.setAlternatingRowColors(True)
        layout.addWidget(self.reg_tree)

    def _load_items(self):
        items = self._engine.get_clean_items()
        self.tree.clear()
        for item in items:
            ti = QTreeWidgetItem()
            ti.setText(0, item.name)
            cat_map = {"system": "系统", "browser": "浏览器", "user": "用户", "advanced": "高级"}
            ti.setText(1, cat_map.get(item.category, item.category))
            ti.setText(2, "-")
            label, color, _ = SAFETY_LABELS[item.safety_level]
            ti.setText(3, label)
            ti.setText(4, "-")
            ti.setText(5, "待分析")
            ti.setCheckState(0, Qt.Checked if item.enabled else Qt.Unchecked)
            ti.setData(0, Qt.UserRole, item)
            self.tree.addTopLevelItem(ti)

    def _analyze(self):
        self.analyze_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setMaximum(0)
        self.slbl.setText("分析中...")
        # Collect items from tree (same objects we display)
        items = []
        for i in range(self.tree.topLevelItemCount()):
            ti = self.tree.topLevelItem(i)
            it = ti.data(0, Qt.UserRole)
            if it:
                items.append(it)
                ti.setText(5, "分析中...")
        # Disconnect old engine signals (silence first-run warnings)
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            try: self._engine.progress.disconnect()
            except (TypeError, RuntimeError): pass
            try: self._engine.item_updated.disconnect()
            except (TypeError, RuntimeError): pass
            try: self._engine.finished.disconnect()
            except (TypeError, RuntimeError): pass
        self._worker = CleanerWorker(self._engine, items)
        self._worker.progress.connect(self.slbl.setText)
        self._worker.item_done.connect(self._on_done)
        self._worker.finished.connect(self._on_finish)
        self._worker.start()

    def _on_done(self, item):
        for i in range(self.tree.topLevelItemCount()):
            ti = self.tree.topLevelItem(i)
            if ti.data(0, Qt.UserRole) == item:
                ti.setText(2, format_size(item.size))
                ti.setText(4, str(item.file_count))
                ti.setText(5, "已分析")
                break

    def _on_finish(self, items):
        self.analyze_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.progress.setMaximum(100)
        self.clean_btn.setEnabled(True)
        total = sum(i.size for i in items)
        self.total.setText("总计可释放: " + format_size(total))
        self.status_message.emit("分析完成 - 可释放" + format_size(total))

    def _clean(self):
        selected = []
        for i in range(self.tree.topLevelItemCount()):
            ti = self.tree.topLevelItem(i)
            if ti.checkState(0) == Qt.Checked:
                selected.append(ti.data(0, Qt.UserRole))
        if not selected:
            return
        r = QMessageBox.question(
            self, "确认清理",
            "确认清理 " + str(len(selected)) + " 个项目？",
            QMessageBox.Yes | QMessageBox.No
        )
        if r != QMessageBox.Yes:
            return
        results = self._engine.clean(selected)
        freed = sum(r2["freed_size"] for r2 in results)
        self.total.setText("清理完成! 释放 " + format_size(freed))
        self.status_message.emit("清理完成: 释放 " + format_size(freed))

    def _scan_reg(self):
        self.reg_tree.clear()
        self._reg_issues = []
        self.slbl.setText("正在扫描注册表...")
        self.reg_clean_btn.setEnabled(False)
        # Create new scanner each time
        self._reg_scanner = RegistryScanner()
        self._reg_scanner.progress.connect(
            lambda msg: self.slbl.setText("注册表: " + msg)
        )
        self._reg_scanner.finished.connect(self._on_reg_done)
        self._reg_scanner.start()

    def _on_reg_done(self, issues):
        self._reg_issues = issues
        self.reg_tree.clear()
        count = len(issues)
        self.slbl.setText("注册表扫描完成，发现 " + str(count) + " 个问题")
        self.status_message.emit("注册表: " + str(count) + " 个问题")

        type_names = {
            "invalid_path": "无效路径",
            "broken_startup": "损坏启动项",
            "uninstall_residue": "卸载残留",
        }

        if count == 0:
            item = QTreeWidgetItem()
            item.setText(0, "未发现问题")
            item.setText(1, "-")
            item.setText(2, "注册表很干净！")
            item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            self.reg_tree.addTopLevelItem(item)
        else:
            for iss in issues:
                item = QTreeWidgetItem()
                item.setText(0, iss.value_name or "(默认)")
                item.setText(1, type_names.get(iss.issue_type, iss.issue_type))
                item.setText(2, iss.description)
                item.setCheckState(0, Qt.Checked)
                item.setData(0, Qt.UserRole, iss)
                self.reg_tree.addTopLevelItem(item)
            self.reg_clean_btn.setEnabled(True)

    def _clean_reg(self):
        cleaned = 0
        failed = 0
        for i in range(self.reg_tree.topLevelItemCount()):
            item = self.reg_tree.topLevelItem(i)
            if item.checkState(0) == Qt.Checked:
                iss = item.data(0, Qt.UserRole)
                if iss:
                    try:
                        if RegistryScanner.clean_issue(None, iss):
                            cleaned += 1
                            item.setHidden(True)
                        else:
                            failed += 1
                    except Exception:
                        failed += 1
        msg = "已清理 " + str(cleaned) + " 项"
        if failed > 0:
            msg += "，失败 " + str(failed) + " 项"
        self.slbl.setText(msg)
        self.status_message.emit(msg)
        if cleaned > 0:
            self.reg_clean_btn.setEnabled(False)