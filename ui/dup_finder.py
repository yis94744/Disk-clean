"""Duplicate finder - classification + safety + real-time filter + open folder"""
import os as _os, subprocess as _sp
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QProgressBar, QComboBox,
    QMessageBox, QTextEdit, QApplication, QMenu)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QFont, QColor, QAction
from core.dup_engine import DupFinder
from utils.helpers import format_size, get_drives, get_file_extension_category, recycle_path

CAT_NAMES = {"Video":"视频","Image":"图片","Audio":"音频","Archive":"压缩包","Document":"文档","Code":"开发编程","Program":"安装程序","System":"系统驱动","Font":"字体","Mobile App":"移动应用","Web/Net":"网络/网页","Shortcut":"快捷方式","Other":"其他"}
CAT_COLORS = {"Video":"#E91E63","Image":"#4CAF50","Audio":"#2196F3","Archive":"#9C27B0","Document":"#FF9800","Code":"#00BCD4","Program":"#F44336","System":"#FF5252","Font":"#26A69A","Mobile App":"#7C4DFF","Web/Net":"#00C853","Shortcut":"#FF5722","Other":"#888"}

_KEEP_BAD_DIRS = ("/windows/", "/appdata/", "/programdata/", "/temp/", "/tmp/", "/$recycle.bin/")

def _keep_index(group):
    """Pick which copy to keep: prefer user folders over system/appdata/temp, then shortest path."""
    best, best_score = 0, None
    for i, f in enumerate(group):
        low = f.lower().replace("\\", "/")
        score = sum(1 for b in _KEEP_BAD_DIRS if b in low) * 10000 + len(f)
        if best_score is None or score < best_score:
            best, best_score = i, score
    return best

def _classify_file(fp):
    ext = _os.path.splitext(fp)[1].lower()
    if ext in (".lnk", ".url"): return "Shortcut"
    return get_file_extension_category(ext)

def _file_desc(fp):
    ext = _os.path.splitext(fp)[1].lower()
    maps = {".lnk": "\u5feb\u6377\u65b9\u5f0f\u94fe\u63a5", ".url": "\u7f51\u9875\u5feb\u6377\u65b9\u5f0f", ".exe": "\u53ef\u6267\u884c\u7a0b\u5e8f", ".dll": "\u52a8\u6001\u94fe\u63a5\u5e93", ".sys": "\u7cfb\u7edf\u9a71\u52a8", ".msi": "\u5b89\u88c5\u5305", ".zip": "ZIP\u538b\u7f29\u5305", ".rar": "RAR\u538b\u7f29\u5305", ".7z": "7z\u538b\u7f29\u5305",
            ".jpg": "JPEG\u56fe\u7247", ".jpeg": "JPEG\u56fe\u7247", ".png": "PNG\u56fe\u7247", ".gif": "GIF\u56fe\u7247", ".bmp": "\u4f4d\u56fe",
            ".mp4": "MP4\u89c6\u9891", ".avi": "AVI\u89c6\u9891", ".mkv": "MKV\u89c6\u9891", ".mp3": "MP3\u97f3\u9891", ".wav": "WAV\u97f3\u9891",
            ".pdf": "PDF\u6587\u6863", ".doc": "Word\u6587\u6863", ".docx": "Word\u6587\u6863", ".xls": "Excel\u8868\u683c", ".xlsx": "Excel\u8868\u683c",
            ".py": "Python\u4ee3\u7801", ".js": "JavaScript\u4ee3\u7801", ".ts": "TypeScript\u4ee3\u7801", ".cpp": "C++\u4ee3\u7801", ".c": "C\u4ee3\u7801", ".java": "Java\u4ee3\u7801"}
    return maps.get(ext, f"{ext} \u6587\u4ef6")

def _open_folder(fp):
    try:
        if _os.path.exists(fp):
            _sp.Popen(['explorer', '/select,', _os.path.normpath(fp)], shell=False)
    except Exception: pass

class DupFinderPage(QWidget):
    status_message = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent); self._finder = None; self._all_groups = []; self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(12, 12, 12, 8); layout.setSpacing(8)
        # 第 1 行：标题
        tb0 = QHBoxLayout()
        t = QLabel("重复文件"); t.setObjectName("pageTitle"); tb0.addWidget(t); tb0.addStretch()
        layout.addLayout(tb0)
        # 第 2 行：扫描条件（左） + 扫描操作（右）
        tb = QHBoxLayout()
        self.dc = QComboBox()
        for d in get_drives(): self.dc.addItem(d, d)
        tb.addWidget(QLabel("磁盘:")); tb.addWidget(self.dc)
        tb.addWidget(QLabel("类别:"))
        self.cat_combo = QComboBox()
        self.cat_combo.addItem("全部类别", "")
        for en, cn in CAT_NAMES.items(): self.cat_combo.addItem(cn, en)
        self.cat_combo.currentIndexChanged.connect(self._apply_filter)
        tb.addWidget(self.cat_combo)
        tb.addStretch()
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.setObjectName("greenBtn")
        self.scan_btn.clicked.connect(self._scan); tb.addWidget(self.scan_btn)
        self.stop_btn = QPushButton("停止"); self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._stop); tb.addWidget(self.stop_btn)
        layout.addLayout(tb)
        # 第 3 行：文件操作（左对齐）
        tb2 = QHBoxLayout()
        self.open_btn = QPushButton("打开目录"); self.open_btn.clicked.connect(self._open_selected)
        tb2.addWidget(self.open_btn)
        self.del_btn = QPushButton("清理选中"); self.del_btn.setObjectName("redBtn")
        self.del_btn.clicked.connect(self._delete_selected); self.del_btn.setEnabled(False); tb2.addWidget(self.del_btn)
        tb2.addStretch()
        layout.addLayout(tb2)
        self.progress = QProgressBar(); self.progress.setVisible(False); layout.addWidget(self.progress)
        self.slbl = QLabel("\u9009\u62e9\u78c1\u76d8\u5e76\u70b9\u51fb\u626b\u63cf")
        self.slbl.setStyleSheet("color:#888;"); layout.addWidget(self.slbl)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["", "\u6587\u4ef6\u540d", "\u91cd\u590d\u6570", "\u7c7b\u522b", "\u6d6a\u8d39\u7a7a\u95f4", "\u8bf4\u660e"])
        self.tree.setColumnWidth(0, 48)
        self.tree.setColumnWidth(1, 200)
        self.tree.setColumnWidth(2, 70)
        self.tree.setColumnWidth(3, 70)
        self.tree.setColumnWidth(4, 90)
        self.tree.setColumnWidth(5, 140)
        self.tree.setAlternatingRowColors(True); self.tree.setIndentation(0)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemClicked.connect(self._on_item_click); layout.addWidget(self.tree)
        self.detail = QTextEdit(); self.detail.setReadOnly(True); self.detail.setMaximumHeight(100)
        self.detail.setStyleSheet("QTextEdit{background:transparent;border:1px solid #21262d;color:#8b949e;font-size:11px;}")
        self.detail.setPlaceholderText("\u70b9\u51fb\u6587\u4ef6\u67e5\u770b\u8be6\u60c5..."); layout.addWidget(self.detail)

    def _scan(self):
        drive = self.dc.currentData()
        if not drive: return
        self.scan_btn.setEnabled(False); self.stop_btn.setVisible(True)
        self.progress.setVisible(True); self.progress.setValue(0)
        self.tree.clear(); self.detail.clear(); self._all_groups = []
        self._finder = DupFinder(); self._finder.setup([drive], min_size=1024)
        self._finder.progress.connect(self._on_progress)
        self._finder.found_group.connect(self._add_group)
        self._finder.finished.connect(self._on_done); self._finder.start()

    def _stop(self):
        if self._finder and self._finder.isRunning(): self._finder.cancel(); self._finder.wait(3000)
        self._reset_ui()

    def _on_progress(self, msg, current, total):
        self.slbl.setText(msg)
        if total > 0: self.progress.setMaximum(total); self.progress.setValue(current)

    def _add_group(self, group):
        self._all_groups.append(group)
        cat_filter = self.cat_combo.currentData() or ""
        waste = 0; valid = []
        for f in group:
            if _os.path.exists(f):
                try:
                    if len(valid) > 0: waste += _os.path.getsize(f)
                    valid.append(f)
                except OSError: valid.append(f)
        if len(valid) < 2: return
        cat = _classify_file(valid[0])
        if cat_filter and cat != cat_filter: return
        item = QTreeWidgetItem(); item.setCheckState(0, Qt.Unchecked)
        item.setText(1, _os.path.basename(valid[0]))
        item.setText(2, str(len(valid)))
        item.setText(3, CAT_NAMES.get(cat, cat))
        try: item.setForeground(3, QColor(CAT_COLORS.get(cat, "#888")))
        except: pass
        item.setText(4, format_size(waste))
        item.setText(5, f"\u4fdd\u75591\u4e2a, \u53ef\u5220{len(valid)-1}\u4e2a")
        item.setData(1, Qt.UserRole, valid); item.setData(2, Qt.UserRole, waste)
        self.tree.addTopLevelItem(item)

    def _on_item_click(self, item, col):
        if not item: return
        valid = item.data(1, Qt.UserRole)
        if not valid: return
        cat = _classify_file(valid[0]); desc = _file_desc(valid[0])
        waste = item.data(2, Qt.UserRole) or 0
        keep = _keep_index(valid)
        lines = [f"类别: {CAT_NAMES.get(cat, cat)}", f"说明: {desc}",
                 f"共 {len(valid)} 个, 浪费空间: {format_size(waste)}"]
        if cat == "Shortcut":
            lines.append("提示: 重复的快捷方式删除后不影响原文件")
        lines.append("-"*40)
        for i, f in enumerate(valid[:10]):
            m = "[保留] " if i == keep else "       "
            lines.append(f"  {m} {f}")
        if len(valid) > 10: lines.append(f"  ... 还有 {len(valid)-10} 个")
        self.detail.setText("\n".join(lines))

    def _on_done(self, groups):
        self._reset_ui(); c = len(self._all_groups)
        self.status_message.emit(f"发现 {c} 组重复文件")
        self.slbl.setText(f"扫描完成! 共 {c} 组重复文件")

    def _apply_filter(self, *_):
        cat_filter = self.cat_combo.currentData() or ""
        self.tree.clear()
        for group in self._all_groups:
            waste = 0; valid = []
            for f in group:
                if _os.path.exists(f):
                    try:
                        if len(valid) > 0: waste += _os.path.getsize(f)
                        valid.append(f)
                    except OSError: valid.append(f)
            if len(valid) < 2: continue
            cat = _classify_file(valid[0])
            if cat_filter and cat != cat_filter: continue
            item = QTreeWidgetItem(); item.setCheckState(0, Qt.Unchecked)
            item.setText(1, _os.path.basename(valid[0]))
            item.setText(2, str(len(valid)))
            item.setText(3, CAT_NAMES.get(cat, cat))
            try: item.setForeground(3, QColor(CAT_COLORS.get(cat, "#888")))
            except: pass
            item.setText(4, format_size(waste))
            item.setText(5, f"保留 1 个, 可删 {len(valid)-1} 个")
            item.setData(1, Qt.UserRole, valid); item.setData(2, Qt.UserRole, waste)
            self.tree.addTopLevelItem(item)

    def _open_selected(self):
        it = self.tree.currentItem()
        if not it:
            QMessageBox.information(self, "提示", "请先选择一个重复文件组")
            return
        valid = it.data(1, Qt.UserRole)
        if valid and len(valid) > 0:
            _open_folder(valid[0])

    def _context_menu(self, pos):
        it = self.tree.itemAt(pos)
        if not it: return
        valid = it.data(1, Qt.UserRole)
        if not valid: return
        menu = QMenu(self)
        act = QAction("打开文件所在目录", self)
        act.triggered.connect(lambda: _open_folder(valid[0]))
        menu.addAction(act)
        if len(valid) > 1:
            act_all = QAction(f"打开全部位置 ({len(valid)} 个)", self)
            act_all.triggered.connect(lambda: [_open_folder(f) for f in valid[:5]])
            menu.addAction(act_all)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _delete_selected(self):
        td = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.checkState(0) == Qt.Checked:
                v = it.data(1, Qt.UserRole)
                if v and len(v) > 1:
                    keep = _keep_index(v)
                    for j, f in enumerate(v):
                        if j != keep: td.append((f, it))
        if not td:
            QMessageBox.information(self, "提示", "请先勾选要清理的重复文件组")
            return
        sc = sum(1 for f,_ in td if f.lower().endswith(('.lnk','.url')))
        tw = sum(_os.path.getsize(f) if _os.path.exists(f) else 0 for f,_ in td)
        w = f"将把 {len(td)} 个重复文件移入回收站, 可释放 {format_size(tw)}\n"
        if sc > 0: w += f"\n注意: 其中包含 {sc} 个快捷方式, 删除后不影响原文件\n"
        w += "\n每组保留 1 个推荐路径的文件, 其余移入回收站。确定继续？"
        r = QMessageBox.warning(self, "确认清理", w, QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes: return
        d=0; fl=0
        for f,_ in td:
            if recycle_path(f): d+=1
            else: fl+=1
        msg = f"已移入回收站 {d} 个文件"
        if fl>0: msg+=f", {fl} 个失败"
        self.status_message.emit(msg); self.slbl.setText(msg)
        for i in range(self.tree.topLevelItemCount()-1,-1,-1):
            if self.tree.topLevelItem(i).checkState(0) == Qt.Checked:
                self.tree.takeTopLevelItem(i)

    def _reset_ui(self):
        self.scan_btn.setEnabled(True); self.stop_btn.setVisible(False)
        self.progress.setVisible(False); self.del_btn.setEnabled(len(self._all_groups) > 0)
