"""Disk Analyzer - scan + treemap + file list"""
import os as _os, shutil
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QComboBox, QTreeWidget, QTreeWidgetItem,
    QProgressBar, QSplitter, QLineEdit, QMessageBox)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QPen, QBrush, QFont
from ui.widgets.treemap import TreemapWidget
from core.scanner import ScanWorker
from utils.helpers import get_drives, format_size, format_timestamp, get_file_extension_category
from utils.cache import ScanCache

CAT_COLORS = {"Video":"#E91E63","Image":"#4CAF50","Audio":"#2196F3","Document":"#FF9800","Archive":"#9C27B0","Program":"#F44336","Code":"#00BCD4","Folder":"#607D8B","Other":"#888"}
CAT_NAMES_CN = {"Video":"视频","Image":"图片","Audio":"音频","Document":"文档","Archive":"压缩包","Program":"程序","Code":"代码","Folder":"文件夹","Other":"其他"}
SAFETY_COLORS = ["#4CAF50","#FF9800","#FF5722","#F44336"]
_ICON_CACHE = {}
_ICON_SIZE = 24
_EXT_COLORS = {
    ".exe":"#F44336",".dll":"#757575",".py":"#3776AB",".js":"#F7DF1E",
    ".mp4":"#E91E63",".mp3":"#2196F3",".jpg":"#4CAF50",".png":"#4CAF50",
    ".zip":"#795548",".pdf":"#F44336",".docx":"#2B579A",".xlsx":"#217346",
}

def _make_file_icon(ext, is_dir):
    key = ("dir" if is_dir else ext)
    if key in _ICON_CACHE: return _ICON_CACHE[key]
    s = _ICON_SIZE
    pix = QPixmap(s, s); pix.fill(Qt.transparent)
    p = QPainter(pix); p.setRenderHint(QPainter.Antialiasing)
    if is_dir:
        p.setBrush(QBrush(QColor("#FFB900"))); p.setPen(Qt.NoPen)
        p.drawRoundedRect(1, 3, s-2, s-4, 4, 4)
        p.drawRoundedRect(1, 1, s//2, 8, 3, 3)
    else:
        color = QColor(_EXT_COLORS.get(ext, "#607D8B"))
        p.setBrush(QBrush(color)); p.setPen(Qt.NoPen)
        p.drawRoundedRect(2, 2, s-4, s-4, 5, 5)
        label = ext.lstrip(".")[:3].upper() if ext else "?"
        p.setPen(QPen(QColor("#FFFFFF"))); p.setFont(QFont("Segoe UI", 7, QFont.Bold))
        p.drawText(pix.rect(), Qt.AlignCenter, label)
    p.end()
    icon = QIcon(pix)
    _ICON_CACHE[key] = icon
    return icon

class DiskAnalyzerPage(QWidget):
    status_message = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None; self._root = None
        self._checkboxes = {}
        self._cache = ScanCache()
        self._setup_ui()
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4); layout.setSpacing(6)
        tb = QHBoxLayout()
        self.drive_combo = QComboBox(); self.drive_combo.setMinimumWidth(100)
        for d in get_drives(): self.drive_combo.addItem(d, d)
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.setObjectName("greenBtn")
        self.scan_btn.clicked.connect(self._scan)
        tb.addWidget(QLabel("磁盘:")); tb.addWidget(self.drive_combo)
        tb.addWidget(self.scan_btn)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("redBtn")
        self.stop_btn.clicked.connect(self._stop); self.stop_btn.setVisible(False)
        tb.addWidget(self.stop_btn); tb.addStretch()
        self.del_btn = QPushButton("删除选中文件")
        self.del_btn.setObjectName("redBtn")
        self.del_btn.clicked.connect(self._delete_selected); tb.addWidget(self.del_btn)
        layout.addLayout(tb)
        self.progress = QProgressBar(); self.progress.setVisible(False); layout.addWidget(self.progress)
        self.info_lbl = QLabel(""); self.info_lbl.setStyleSheet("color:#aaa;font-size:11px;"); layout.addWidget(self.info_lbl)
        splitter = QSplitter(Qt.Horizontal); splitter.setHandleWidth(2)
        self.treemap = TreemapWidget()
        self.treemap.node_clicked.connect(self._on_treemap_node)
        self.treemap.node_right_clicked.connect(self._on_treemap_right)
        self.treemap.setMinimumHeight(300); splitter.addWidget(self.treemap)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 0, 0, 0); right_layout.setSpacing(4)
        header_row = QHBoxLayout()
        self.breadcrumb = QLabel(" / "); self.breadcrumb.setStyleSheet("color:#8b949e;font-size:11px;")
        header_row.addWidget(self.breadcrumb, 1)
        self.search_edit = QLineEdit(); self.search_edit.setPlaceholderText("搜索文件...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_list); self.search_edit.setMaximumWidth(160)
        header_row.addWidget(self.search_edit)
        select_all_btn = QPushButton("全选"); select_all_btn.setMaximumWidth(50)
        select_all_btn.clicked.connect(self._select_all); header_row.addWidget(select_all_btn)
        right_layout.addLayout(header_row)
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["", "文件名", "大小", "类别", "扩展名", "修改时间", "文件数", "安全"])
        self.file_tree.setColumnWidth(0, 32); self.file_tree.setColumnWidth(1, 200)
        self.file_tree.setColumnWidth(2, 80); self.file_tree.setColumnWidth(3, 70)
        self.file_tree.setColumnWidth(4, 70); self.file_tree.setColumnWidth(5, 110)
        self.file_tree.setColumnWidth(6, 60); self.file_tree.setColumnWidth(7, 70)
        self.file_tree.setSortingEnabled(True)
        self.file_tree.itemDoubleClicked.connect(self._on_item_dbl)
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._context_menu)
        self.file_tree.setAlternatingRowColors(True)
        right_layout.addWidget(self.file_tree)
        splitter.addWidget(right_panel)
        splitter.setSizes([450, 450]); layout.addWidget(splitter)

    def _scan(self):
        drive = self.drive_combo.currentData()
        if not drive: return
        self.file_tree.clear(); self._checkboxes.clear()
        self.info_lbl.setText(""); self.scan_btn.setEnabled(False)
        self.stop_btn.setVisible(True); self.progress.setVisible(True); self.progress.setMaximum(0)
        self._worker = ScanWorker(drive)
        self._worker.progress.connect(self._on_progress)
        self._worker.scan_finished.connect(self._on_done)
        self._worker.status_update.connect(self.status_message.emit)
        self._worker.start()

    def _stop(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel(); self._worker.wait(3000)
        self._reset_ui()

    def _on_progress(self, file_count, size_str):
        self.info_lbl.setText(f"已扫描 {file_count} 个文件, {size_str}")
        self.progress.setMaximum(0)

    def _on_done(self, root_node):
        self._reset_ui(); self._root = root_node
        if root_node:
            self.treemap.set_data(root_node)
            self._populate_list(root_node)
            self.status_message.emit("扫描完成")
        else: self.status_message.emit("扫描失败")

    def _reset_ui(self):
        self.scan_btn.setEnabled(True); self.stop_btn.setVisible(False); self.progress.setVisible(False)

    def _populate_list(self, node):
        self.file_tree.clear(); self._checkboxes.clear(); self.file_tree.setSortingEnabled(False)
        children = getattr(node, 'children', [])
        if not children: children = [node]
        for i, child in enumerate(children[:500]):
            try:
                item = QTreeWidgetItem()
                item.setCheckState(0, Qt.Unchecked)
                child_ext = getattr(child, 'ext', '')
                child_is_dir = getattr(child, 'is_dir', False)
                ico = _make_file_icon(child_ext, child_is_dir)
                if ico: item.setIcon(1, ico)
                item.setText(1, child.name or "?")
                item.setText(2, format_size(child.size) if not child_is_dir else "")
                if child_is_dir:
                    item.setText(3, "文件夹")
                    item.setText(4, "")
                    n = child.file_count if hasattr(child, 'file_count') else 0
                    item.setText(6, str(n) if n else "-")
                else:
                    cat = get_file_extension_category(child.ext) if hasattr(child, 'ext') else "Other"
                    cn = CAT_NAMES_CN.get(cat, cat)
                    item.setText(3, cn)
                    item.setText(4, (child.ext or "-") if hasattr(child, 'ext') else "-")
                    color = CAT_COLORS.get(cat, "#888")
                    try: item.setForeground(3, QColor(color))
                    except: pass
                mt = child.mtime if hasattr(child, 'mtime') and child.mtime else 0
                item.setText(5, format_timestamp(mt) if mt else "-")
                if hasattr(child, 'safety') and child.safety:
                    try:
                        item.setText(7, child.safety.get("label", "-"))
                        lvl = child.safety.get("level", 3)
                        item.setForeground(7, QColor(SAFETY_COLORS[min(lvl, 3)]))
                    except: item.setText(7, "-")
                else: item.setText(7, "-")
                item.setData(1, Qt.UserRole, child)
                self.file_tree.addTopLevelItem(item)
                self._checkboxes[i] = item
            except: continue
        self.file_tree.setSortingEnabled(True)

    def _filter_list(self):
        tx = self.search_edit.text().lower()
        for i in range(self.file_tree.topLevelItemCount()):
            itm = self.file_tree.topLevelItem(i)
            itm.setHidden(bool(tx) and tx not in itm.text(1).lower())

    def _select_all(self):
        for i in range(self.file_tree.topLevelItemCount()):
            self.file_tree.topLevelItem(i).setCheckState(0, Qt.Checked)

    def _on_treemap_node(self, node):
        try:
            self._populate_list(node)
            parts = [p for p in node.path.replace(":", "").split("\\") if p]
            self.breadcrumb.setText(" / " + " / ".join(parts[:5]))
            self.info_lbl.setText(format_size(node.size) + " / " + str(node.file_count) + " 个文件")
        except: pass

    def _on_treemap_right(self, node):
        try: self.treemap.go_up(); self._on_treemap_node(node)
        except: pass

    def _context_menu(self, pos):
        it = self.file_tree.itemAt(pos)
        if not it: return
        node = it.data(1, Qt.UserRole)
        if node and hasattr(node, 'path'):
            from PySide6.QtWidgets import QMenu
            from PySide6.QtGui import QAction
            menu = QMenu(self)
            act = QAction("打开文件所在目录", self)
            act.triggered.connect(lambda n=node: (_sp.Popen(['explorer','/select,',_os.path.normpath(n.path)], shell=False) if _os.path.exists(n.path) else None))
            menu.addAction(act)
            menu.exec_(self.file_tree.viewport().mapToGlobal(pos))

    def _on_item_dbl(self, item):
        try:
            node = item.data(1, Qt.UserRole)
            if node and node.is_dir: self.treemap.drill_down(node); self._populate_list(node)
        except: pass

    def _open_selected(self):
        it = self.file_tree.currentItem()
        if not it: return
        node = it.data(1, Qt.UserRole)
        if node:
            try:
                import subprocess as _sp
                fp = node.path if hasattr(node, 'path') else ''
                if fp and os.path.exists(fp):
                    _sp.Popen(['explorer', '/select,', os.path.normpath(fp)], shell=False)
            except: pass

    def _delete_selected(self):
        to_delete = []
        for i in range(self.file_tree.topLevelItemCount()):
            itm = self.file_tree.topLevelItem(i)
            if itm.checkState(0) == Qt.Checked:
                node = itm.data(1, Qt.UserRole)
                if node: to_delete.append((node, itm))
        if not to_delete:
            QMessageBox.information(self, "删除", "请选择要删除的文件")
            return
        items = to_delete[:10]
        names = chr(10).join(n.name + " (" + format_size(n.size) + ")" for n, _ in items)
        if len(to_delete) > 10: names += chr(10) + "... 还有 " + str(len(to_delete)-10) + " 个"
        r = QMessageBox.warning(self, "确认删除",
            "将永久删除以下文件：\n\n" + names + "\n\n此操作不可撤销，确定继续？",
            QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes: return
        cleaned = 0; failed = 0
        for node, _ in to_delete:
            try:
                if node.is_dir: shutil.rmtree(node.path, ignore_errors=True)
                elif _os.path.exists(node.path): _os.remove(node.path)
                cleaned += 1
            except: failed += 1
        msg = "已删除 " + str(cleaned) + " 个"
        if failed: msg += " (" + str(failed) + " 失败)"
        self.status_message.emit(msg)
        QMessageBox.information(self, "结果", msg)
