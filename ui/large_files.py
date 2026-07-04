"""Large file finder - refined categories + open folder location"""
import os as _os, time as _time, subprocess as _sp
from datetime import datetime as _dt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QProgressBar, QComboBox,
    QSpinBox, QMessageBox, QApplication, QMenu)
from PySide6.QtCore import Signal, QTimer, QThread, QObject, Qt
from PySide6.QtGui import QFont, QColor, QAction
from utils.helpers import format_size, get_drives, get_file_extension_category

# Refined categories with more granular types
CAT_NAMES = {
    "Video":"\u89c6\u9891", "Image":"\u56fe\u7247", "Audio":"\u97f3\u9891",
    "Document":"\u6587\u6863", "Spreadsheet":"\u8868\u683c", "Presentation":"\u6f14\u793a\u6587\u7a3f",
    "Archive":"\u538b\u7f29\u5305", "DiskImage":"\u78c1\u76d8\u6620\u50cf",
    "Executable":"\u53ef\u6267\u884c\u7a0b\u5e8f", "Library":"\u52a8\u6001\u5e93", "Driver":"\u9a71\u52a8\u6587\u4ef6",
    "Code":"\u4ee3\u7801", "Config":"\u914d\u7f6e\u6587\u4ef6", "Log":"\u65e5\u5fd7\u6587\u4ef6",
    "Database":"\u6570\u636e\u5e93", "Font":"\u5b57\u4f53", "Temp":"\u4e34\u65f6\u6587\u4ef6",
    "Shortcut":"\u5feb\u6377\u65b9\u5f0f", "Certificate":"\u8bc1\u4e66/\u5bc6\u94a5",
    "VirtualDisk":"\u865a\u62df\u78c1\u76d8", "Backup":"\u5907\u4efd\u6587\u4ef6",
    "Other":"\u5176\u4ed6",
}
CAT_COLORS = {
    "Video":"#E91E63", "Image":"#4CAF50", "Audio":"#2196F3",
    "Document":"#FF9800", "Spreadsheet":"#4CAF50", "Presentation":"#FF7043",
    "Archive":"#9C27B0", "DiskImage":"#AB47BC",
    "Executable":"#F44336", "Library":"#FF5252", "Driver":"#D32F2F",
    "Code":"#00BCD4", "Config":"#78909C", "Log":"#8D6E63",
    "Database":"#7E57C2", "Font":"#26A69A", "Temp":"#BDBDBD",
    "Shortcut":"#FF5722", "Certificate":"#FFD54F",
    "VirtualDisk":"#5C6BC0", "Backup":"#66BB6A",
    "Other":"#888",
}

# Extension -> refined category mapping
EXT_CAT_MAP = {
    # Documents
    ".pdf": "Document", ".doc": "Document", ".docx": "Document", ".odt": "Document",
    ".rtf": "Document", ".tex": "Document", ".md": "Document", ".txt": "Document",
    ".wps": "Document", ".pages": "Document",
    # Spreadsheets
    ".xls": "Spreadsheet", ".xlsx": "Spreadsheet", ".csv": "Spreadsheet",
    ".ods": "Spreadsheet", ".numbers": "Spreadsheet",
    # Presentations
    ".ppt": "Presentation", ".pptx": "Presentation", ".odp": "Presentation",
    ".key": "Presentation",
    # Archives
    ".zip": "Archive", ".rar": "Archive", ".7z": "Archive", ".tar": "Archive",
    ".gz": "Archive", ".bz2": "Archive", ".xz": "Archive", ".lz": "Archive",
    # Disk images
    ".iso": "DiskImage", ".img": "DiskImage", ".dmg": "DiskImage",
    ".vhd": "DiskImage", ".vhdx": "DiskImage", ".vmdk": "DiskImage",
    # Programs
    ".exe": "Executable", ".msi": "Executable", ".bat": "Code", ".cmd": "Code",
    ".dll": "Library", ".ocx": "Library", ".sys": "Driver", ".drv": "Driver",
    # Code
    ".py": "Code", ".pyc": "Code", ".js": "Code", ".ts": "Code", ".jsx": "Code",
    ".tsx": "Code", ".cpp": "Code", ".c": "Code", ".h": "Code", ".hpp": "Code",
    ".java": "Code", ".cs": "Code", ".go": "Code", ".rs": "Code", ".rb": "Code",
    ".php": "Code", ".swift": "Code", ".kt": "Code", ".scala": "Code",
    ".lua": "Code", ".r": "Code", ".sql": "Code", ".sh": "Code",
    ".vue": "Code", ".svelte": "Code", ".html": "Code", ".css": "Code",
    ".scss": "Code", ".less": "Code", ".xml": "Code", ".json": "Config",
    ".yaml": "Config", ".yml": "Config", ".toml": "Config", ".ini": "Config",
    ".cfg": "Config", ".conf": "Config", ".env": "Config",
    # Database
    ".db": "Database", ".sqlite": "Database", ".sqlite3": "Database",
    ".mdb": "Database", ".accdb": "Database", ".dbf": "Database",
    # Fonts
    ".ttf": "Font", ".otf": "Font", ".woff": "Font", ".woff2": "Font", ".eot": "Font",
    # Temp
    ".tmp": "Temp", ".temp": "Temp", ".cache": "Temp", ".bak": "Backup",
    ".old": "Backup",
    # Logs
    ".log": "Log",
    # Certificates
    ".pem": "Certificate", ".crt": "Certificate", ".cer": "Certificate",
    ".key": "Certificate", ".p12": "Certificate", ".pfx": "Certificate",
    # Virtual disks
    ".vdi": "VirtualDisk", ".qcow2": "VirtualDisk",
}

def _refined_category(fp):
    ext = _os.path.splitext(fp)[1].lower()
    if ext in (".lnk", ".url"): return "Shortcut"
    if ext in EXT_CAT_MAP: return EXT_CAT_MAP[ext]
    return get_file_extension_category(ext)

def format_timestamp(ts): return _dt.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "-"

def _open_folder(fp):
    try:
        if _os.path.exists(fp):
            _sp.Popen(['explorer', '/select,', _os.path.normpath(fp)], shell=False)
    except Exception: pass

class _LargeFileWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(list)
    def __init__(self, drive, min_size, cat_filter):
        super().__init__()
        self.drive = drive; self.min_size = min_size; self.cat_filter = cat_filter
        self._stop = False
    def cancel(self): self._stop = True
    def run(self):
        results = []; count = 0
        try:
            for root, dirs, files in _os.walk(self.drive):
                if self._stop: break
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('System Volume Information','$Recycle.Bin','Windows')]
                for fn in files:
                    if self._stop: break
                    try:
                        fp = _os.path.join(root, fn)
                        sz = _os.path.getsize(fp)
                        if sz >= self.min_size:
                            if self.cat_filter:
                                cat = _refined_category(fp)
                                if cat != self.cat_filter: continue
                            results.append((fp, fn, sz))
                            count += 1
                            if count % 100 == 0:
                                self.progress.emit(count, format_size(sum(r[2] for r in results)))
                    except OSError: continue
        except PermissionError: pass
        results.sort(key=lambda x: x[2], reverse=True)
        self.finished.emit(results)

class LargeFilesPage(QWidget):
    status_message = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None; self._worker = None
        self._all_files = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(12,12,12,12); layout.setSpacing(8)
        tb = QHBoxLayout()
        t = QLabel("\u5927\u6587\u4ef6\u67e5\u627e")
        t.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        t.setStyleSheet("color: #e0e0e0;"); tb.addWidget(t); tb.addStretch()
        self.dc = QComboBox()
        for d in get_drives(): self.dc.addItem(d, d)
        tb.addWidget(QLabel("\u78c1\u76d8:")); tb.addWidget(self.dc)
        tb.addWidget(QLabel("\u6700\u5c0f(MB):"))
        self.ss = QSpinBox(); self.ss.setRange(1, 10000); self.ss.setValue(100); tb.addWidget(self.ss)
        tb.addWidget(QLabel("\u7c7b\u522b:"))
        self.cat_combo = QComboBox()
        self.cat_combo.addItem("\u5168\u90e8\u7c7b\u522b", "")
        for en, cn in CAT_NAMES.items(): self.cat_combo.addItem(cn, en)
        self.cat_combo.currentIndexChanged.connect(self._apply_filter)
        tb.addWidget(self.cat_combo)
        self.scan_btn = QPushButton("\u5f00\u59cb\u626b\u63cf")
        self.scan_btn.setObjectName("greenBtn")
        self.scan_btn.clicked.connect(self._scan); tb.addWidget(self.scan_btn)
        self.cancel_btn = QPushButton("\u53d6\u6d88"); self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel); tb.addWidget(self.cancel_btn)
        self.open_btn = QPushButton("\u6253\u5f00\u76ee\u5f55"); self.open_btn.clicked.connect(self._open_selected)
        tb.addWidget(self.open_btn)
        self.del_btn = QPushButton("\u5220\u9664\u9009\u4e2d")
        self.del_btn.setObjectName("redBtn")
        self.del_btn.clicked.connect(self._delete_selected); tb.addWidget(self.del_btn)
        layout.addLayout(tb)
        self.progress = QProgressBar(); self.progress.setVisible(False); layout.addWidget(self.progress)
        self.slbl = QLabel("\u9009\u62e9\u78c1\u76d8\u5e76\u70b9\u51fb\u626b\u63cf")
        self.slbl.setStyleSheet("color: #888;"); layout.addWidget(self.slbl)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["", "\u6587\u4ef6\u540d", "\u8def\u5f84", "\u5927\u5c0f", "\u7c7b\u522b", "\u4fee\u6539\u65f6\u95f4"])
        self.tree.setColumnWidth(0, 48)
        self.tree.setColumnWidth(1, 220)
        self.tree.setColumnWidth(2, 340)
        self.tree.setColumnWidth(3, 85)
        self.tree.setColumnWidth(4, 80)
        self.tree.setColumnWidth(5, 140)
        self.tree.setAlternatingRowColors(True); self.tree.setIndentation(0)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.tree)

    def _scan(self):
        drive = self.dc.currentData()
        if not drive: return
        min_size = self.ss.value() * 1024 * 1024
        self.scan_btn.setEnabled(False); self.cancel_btn.setVisible(True)
        self.progress.setVisible(True); self.progress.setValue(0)
        self.tree.clear(); self._all_files = []
        self.slbl.setText("\u626b\u63cf\u4e2d...")
        QApplication.processEvents()
        if self._thread and self._thread.isRunning():
            self._thread.quit(); self._thread.wait(2000)
        cat_filter = self.cat_combo.currentData() or ""
        self._thread = QThread()
        self._worker = _LargeFileWorker(drive, min_size, cat_filter)
        self._worker.moveToThread(self._thread)
        self._worker.progress.connect(lambda c, s: (self.progress.setValue(c), self.slbl.setText(f"  {c} \u4e2a, {s}")))
        self._worker.finished.connect(self._on_results)
        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _cancel(self):
        if self._worker: self._worker.cancel()
        if self._thread and self._thread.isRunning():
            self._thread.quit(); self._thread.wait(3000)
        self.scan_btn.setEnabled(True); self.cancel_btn.setVisible(False)
        self.progress.setVisible(False)
        self.slbl.setText("\u5df2\u53d6\u6d88")

    def _on_results(self, results):
        self._all_files = results
        self._apply_filter()

    def _apply_filter(self, *_):
        cat_filter = self.cat_combo.currentData() or ""
        self.tree.clear()
        if not self._all_files:
            self.scan_btn.setEnabled(True); self.cancel_btn.setVisible(False)
            self.progress.setVisible(False)
            return
        count = 0
        for fp, fn, sz in self._all_files:
            cat = _refined_category(fp)
            if cat_filter and cat != cat_filter: continue
            item = QTreeWidgetItem(); item.setCheckState(0, Qt.Unchecked)
            item.setText(1, fn); item.setText(2, fp)
            item.setText(3, format_size(sz))
            item.setText(4, CAT_NAMES.get(cat, cat))
            try: item.setForeground(4, QColor(CAT_COLORS.get(cat, "#888")))
            except: pass
            try: item.setText(5, format_timestamp(_os.path.getmtime(fp)))
            except: item.setText(5, "-")
            item.setData(0, Qt.UserRole, fp)
            self.tree.addTopLevelItem(item); count += 1
        self.scan_btn.setEnabled(True); self.cancel_btn.setVisible(False)
        self.progress.setVisible(False)
        self.slbl.setText(f"  {count} \u4e2a (\u5171 {len(self._all_files)} \u4e2a)")
        self.status_message.emit(f"  {count} \u4e2a\u6587\u4ef6")

    def _open_selected(self):
        it = self.tree.currentItem()
        if not it:
            QMessageBox.information(self, "\u63d0\u793a", "\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u6587\u4ef6")
            return
        fp = it.data(0, Qt.UserRole)
        if fp: _open_folder(fp)

    def _on_double_click(self, item, col):
        fp = item.data(0, Qt.UserRole)
        if fp: _open_folder(fp)

    def _context_menu(self, pos):
        it = self.tree.itemAt(pos)
        if not it: return
        fp = it.data(0, Qt.UserRole)
        if not fp: return
        menu = QMenu(self)
        act_open = QAction("\u6253\u5f00\u6587\u4ef6\u6240\u5728\u76ee\u5f55", self)
        act_open.triggered.connect(lambda: _open_folder(fp))
        menu.addAction(act_open)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _delete_selected(self):
        td = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.checkState(0) == Qt.Checked:
                fp = it.data(0, Qt.UserRole)
                if fp: td.append((fp, it.text(1)))
        if not td:
            QMessageBox.information(self, "\u63d0\u793a", "\u8bf7\u5148\u9009\u62e9\u8981\u5220\u9664\u7684\u6587\u4ef6")
            return
        names = chr(10).join(fn for fn, _ in td[:10])
        if len(td) > 10: names += chr(10) + f"...  {len(td)-10} \u4e2a"
        r = QMessageBox.warning(self, "\u786e\u8ba4\u5220\u9664",
            "\u786e\u5b9a\u8981\u5220\u9664\u4ee5\u4e0b\u6587\u4ef6\u5417\uff1f\n\n" + names,
            QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes: return
        cleaned = 0; failed = 0
        for fp, _ in td:
            try:
                if _os.path.exists(fp): _os.remove(fp); cleaned += 1
            except: failed += 1
        msg = f"  {cleaned} \u4e2a"
        if failed: msg += f", {failed} \u5931\u8d25"
        self.status_message.emit(msg)
        QMessageBox.information(self, "\u7ed3\u679c", msg)
