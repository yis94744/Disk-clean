# -*- coding: utf-8 -*-
"""File Visualizer - scan disk, show files by category with search/filter."""
import os as _os, subprocess as _sp
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTreeWidget, QTreeWidgetItem,
    QProgressBar, QLineEdit, QMessageBox, QTabWidget, QMenu)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QColor, QAction
from core.scanner import ScanWorker
from utils.helpers import get_drives, format_size, format_timestamp, get_file_extension_category
from utils.cache import ScanCache
from utils.themes import load_settings, size_color

CAT_COLORS = {"Video":"#E91E63","Image":"#4CAF50","Audio":"#2196F3","Archive":"#9C27B0","Document":"#FF9800","Code":"#00BCD4","Program":"#F44336","System":"#FF5252","Font":"#26A69A","Mobile App":"#7C4DFF","Web/Net":"#00C853","Shortcut":"#FF5722","Other":"#888"}
CAT_NAMES = {"Video":"视频","Image":"图片","Audio":"音频","Archive":"压缩包","Document":"文档","Code":"开发编程","Program":"安装程序","System":"系统驱动","Font":"字体","Mobile App":"移动应用","Web/Net":"网络/网页","Shortcut":"快捷方式","Other":"其他"}
SAFETY_COLORS = ["#4CAF50","#FF9800","#FF5722","#F44336"]

_CODE_EXTS = frozenset({'.py','.pyd','.js','.ts','.java','.c','.cpp','.h','.hpp','.json','.xml','.yaml','.yml','.toml','.ini','.cfg','.conf','.css','.html','.htm','.php','.rb','.go','.rs','.swift','.kt','.lua','.sql','.sh','.bat','.ps1','.cs','.vb','.r','.m','.mm','.pl','.pm','.tcl','.dart','.ex','.exs','.erl','.hs','.nim','.zig','.v','.sv','.scala','.clj','.rkt','.fs','.fsx','.psm1','.psd1','.ipynb','.md','.txt','.csv','.log'})


class SortTreeWidgetItem(QTreeWidgetItem):
    """Safe sort wrapper - uses _raw_size for column 2, text for others."""
    def __lt__(self, other):
        try:
            col = self.treeWidget().sortColumn() if self.treeWidget() else 0
        except Exception:
            col = 0
        if col == 2:
            a = getattr(self, "_raw_size", 0)
            b = getattr(other, "_raw_size", 0)
            return a < b
        return self.text(col) < other.text(col)


class FileVisualizerPage(QWidget):
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._root = None
        self._cache = ScanCache()
        self._all_flat_files = []
        self._loaded = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 6)
        layout.setSpacing(4)

        tb = QHBoxLayout()
        self.drive_combo = QComboBox(); self.drive_combo.setMinimumWidth(90)
        for d in get_drives(): self.drive_combo.addItem(d, d)
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.setObjectName("greenBtn")
        self.scan_btn.clicked.connect(self._scan)
        tb.addWidget(QLabel("磁盘:"))
        tb.addWidget(self.drive_combo)
        tb.addWidget(self.scan_btn)

        self.scan_all_btn = QPushButton("扫描全部")
        self.scan_all_btn.setObjectName("greenBtn")
        self.scan_all_btn.clicked.connect(self._scan_all)
        self.scan_all_btn.setToolTip("扫描所有磁盘驱动器")
        tb.addWidget(self.scan_all_btn)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("redBtn")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setVisible(False)
        tb.addWidget(self.stop_btn)
        tb.addStretch()
        tb.addWidget(QLabel("类别:"))
        self.cat_combo = QComboBox(); self.cat_combo.setMinimumWidth(70)
        self.cat_combo.addItem("全部", "")
        for en, cn in CAT_NAMES.items():
            self.cat_combo.addItem(cn, en)
        self.cat_combo.currentIndexChanged.connect(self._apply_filter)
        tb.addWidget(self.cat_combo)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索文件...")
        self.search_edit.setMaximumWidth(160)
        self.search_edit.textChanged.connect(self._apply_filter)
        tb.addWidget(self.search_edit)
        self.open_btn = QPushButton("打开目录")
        self.open_btn.clicked.connect(self._open_selected)
        tb.addWidget(self.open_btn)
        self.del_btn = QPushButton("删除选中")
        self.del_btn.setObjectName("redBtn")
        self.del_btn.clicked.connect(self._delete_selected)
        tb.addWidget(self.del_btn)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._rebuild_list)
        tb.addWidget(self.refresh_btn)
        layout.addLayout(tb)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.info_lbl = QLabel("")
        self.info_lbl.setStyleSheet("color:#aaa;font-size:11px;")
        layout.addWidget(self.info_lbl)

        self.tabs = QTabWidget()
        fl = QWidget(); fll = QVBoxLayout(fl); fll.setContentsMargins(0, 0, 0, 0)
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["", "文件名", "大小", "类别", "扩展名", "修改时间", "安全", "所属软件"])
        self.file_tree.setColumnWidth(0, 36)
        self.file_tree.setColumnWidth(1, 240)
        self.file_tree.setColumnWidth(2, 80)
        self.file_tree.setColumnWidth(3, 70)
        self.file_tree.setColumnWidth(4, 60)
        self.file_tree.setColumnWidth(5, 130)
        self.file_tree.setColumnWidth(6, 50)
        self.file_tree.setColumnWidth(7, 130)
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setIndentation(0)
        self.file_tree.setUniformRowHeights(True)
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._ctx_menu)
        self.file_tree.itemDoubleClicked.connect(self._on_dbl)
        fll.addWidget(self.file_tree)
        self.tabs.addTab(fl, "文件列表")

        ew = QWidget(); el = QVBoxLayout(ew); el.setContentsMargins(0, 0, 0, 0)
        self.ext_tree = QTreeWidget()
        self.ext_tree.setHeaderLabels(["扩展名", "类别", "数量", "总大小"])
        self.ext_tree.setColumnWidth(0, 80)
        self.ext_tree.setColumnWidth(1, 90)
        self.ext_tree.setColumnWidth(2, 70)
        self.ext_tree.setColumnWidth(3, 90)
        self.ext_tree.setSortingEnabled(True)
        el.addWidget(self.ext_tree)
        self.tabs.addTab(ew, "扩展名统计")
        layout.addWidget(self.tabs)

        self.status_lbl = QLabel("选择磁盘并点击扫描")
        self.status_lbl.setStyleSheet("color:#aaa;font-size:11px;")
        layout.addWidget(self.status_lbl)

    # ---- Scanning ----
    def _scan(self):
        drive = self.drive_combo.currentData()
        if not drive: return
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        if self._worker:
            try: self._worker.progress.disconnect()
            except (TypeError, RuntimeError): pass
            try: self._worker.scan_finished.disconnect()
            except (TypeError, RuntimeError): pass
            try: self._worker.status_update.disconnect()
            except (TypeError, RuntimeError): pass
        self.file_tree.clear(); self.ext_tree.clear()
        self.info_lbl.setText("")
        self.scan_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.progress.setVisible(True)
        self.progress.setMaximum(0)
        self.status_lbl.setText(f"扫描 {drive} ...")
        s = load_settings()
        scan_limit = s.get('scan_limit', 50000)
        min_size_mb = s.get('scan_min_size_mb', 1)
        self._worker = ScanWorker(drive, scan_limit=scan_limit, min_size_mb=min_size_mb)
        self._worker.progress.connect(self._on_progress)
        self._worker.scan_finished.connect(self._on_done)
        self._worker.status_update.connect(self.status_message.emit)
        self._worker.start()

    def _scan_all(self):
        import os as _os_inter
        drives = [d for d in get_drives() if d]
        if not drives:
            QMessageBox.information(self, "提示", "未检测到可用磁盘")
            return
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        # Reset state for cumulative scan
        self._all_flat_files = []
        self.file_tree.clear()
        self.ext_tree.clear()
        self.info_lbl.setText("")
        self.scan_btn.setEnabled(False)
        self.scan_all_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.progress.setVisible(True)
        self.progress.setMaximum(0)
        self._scan_all_drives = list(drives)
        self._scan_all_idx = 0
        self._scan_all_cumulative = []
        self._scan_next_drive()

    def _scan_next_drive(self):
        if self._scan_all_idx >= len(self._scan_all_drives):
            # All done - merge results
            self.status_lbl.setText("所有磁盘扫描完成，正在整理结果...")
            self._reset_ui()
            self.scan_all_btn.setEnabled(True)
            # Build fake root from cumulative results
            from core.scanner import ScanNode
            total_size = sum(getattr(f, "size", 0) for f in self._scan_all_cumulative)
            root = ScanNode("ALL", "所有磁盘", size=total_size, is_dir=True)
            root.large_files = self._scan_all_cumulative
            root.file_count = len(self._scan_all_cumulative)
            self._root = root
            self._all_flat_files = self._scan_all_cumulative
            self._display_files(root)
            self._update_charts()
            self._rebuild_list()
            self.status_lbl.setText(f"完成: {format_size(total_size)} / {len(self._scan_all_cumulative)} 个文件")
            self.status_message.emit(f"全盘扫描完成: {len(self._scan_all_cumulative)} 个文件")
            return
        drive = self._scan_all_drives[self._scan_all_idx]
        self._scan_all_idx += 1
        self.status_lbl.setText(f"扫描 {drive} ({self._scan_all_idx}/{len(self._scan_all_drives)})...")
        # Disconnect old worker signals
        if self._worker:
            try: self._worker.progress.disconnect()
            except (TypeError, RuntimeError): pass
            try: self._worker.scan_finished.disconnect()
            except (TypeError, RuntimeError): pass
            try: self._worker.status_update.disconnect()
            except (TypeError, RuntimeError): pass
        s = load_settings()
        scan_limit = s.get("scan_limit", 50000)
        min_size_mb = s.get("scan_min_size_mb", 1)
        self._worker = ScanWorker(drive, scan_limit=scan_limit, min_size_mb=min_size_mb)
        self._worker.progress.connect(self._on_progress)
        self._worker.scan_finished.connect(self._on_scan_all_drive_done)
        self._worker.status_update.connect(self.status_message.emit)
        self._worker.start()

    def _on_scan_all_drive_done(self, root_node):
        if root_node and hasattr(root_node, "large_files"):
            self._scan_all_cumulative.extend(root_node.large_files)
        self._scan_next_drive()

    def _stop(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        self._reset_ui()

    def _on_progress(self, file_count, size_str):
        self.info_lbl.setText(f"已扫描 {file_count} 个, {size_str}")
        self.progress.setMaximum(0)

    def _on_done(self, root_node):
        self._reset_ui()
        # Wait for worker thread to fully exit before touching UI
        if self._worker and self._worker.isRunning():
            self._worker.wait(5000)
        self.status_lbl.setText("[1/4] 接收扫描结果...")
        if root_node is None:
            self.status_lbl.setText("扫描失败")
            return
        self._root = root_node
        total_size = root_node.size if hasattr(root_node, "size") else 0
        total_files = root_node.file_count if hasattr(root_node, "file_count") else 0
        self.status_lbl.setText(f"[2/4] 整理 {total_files} 个文件...")
        try:
            self._display_files(root_node)
            self.status_lbl.setText("[3/4] 生成统计...")
        except Exception as e:
            self.status_lbl.setText(f"显示错误: {e}")
            self.file_tree.clear()
            return
        try:
            self._update_charts()
        except Exception as e:
            self.status_lbl.setText(f"统计错误: {e}")
        self.status_lbl.setText(f"完成: {format_size(total_size)} / {total_files} 个文件")
        self.status_message.emit(f"扫描完成: {self.drive_combo.currentText()}")
        # Force Qt to process pending events
        self._rebuild_list()
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
    def _reset_ui(self):
        self.scan_btn.setEnabled(True)
        if hasattr(self, "scan_all_btn"):
            self.scan_all_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self.progress.setVisible(False)

    # ---- File collection ----
    def _display_files(self, root_node):
        self.file_tree.clear()
        files = getattr(root_node, "large_files", [])
        seen = set()
        deduped = []
        for f in files:
            fp = getattr(f, "path", "") or ""
            if fp and fp not in seen:
                seen.add(fp)
                deduped.append(f)
        self._all_flat_files = deduped


    def _walk_tree(self, node, result):
        """Iterative: collect files >= 1MB or code files."""
        try:
            stack = [node]
            while stack:
                n = stack.pop()
                children = getattr(n, "children", None)
                if children is None:
                    continue
                for child in children:
                    try:
                        if getattr(child, "is_dir", False):
                            stack.append(child)
                        elif getattr(child, "size", 0) >= 1048576 or getattr(child, "ext", "") in _CODE_EXTS:
                            result.append(child)
                    except Exception:
                        continue
        except Exception as e:
            self.status_lbl.setText(f"遍历错误: {e}")
    def _apply_filter(self, *_):
        self._rebuild_list()

    # ---- Rebuild list ----
    _SOFTWARE_DIRS = {
        "google": "Google Chrome", "mozilla firefox": "Mozilla Firefox",
        "microsoft edge": "Microsoft Edge", "opera": "Opera Browser",
        "360": "360安全", "tencent": "腾讯",
        "qq": "QQ", "wechat": "微信", "wxwork": "企业微信",
        "dingtalk": "钉钉", "feishu": "飞书",
        "wps": "WPS Office", "microsoft office": "Microsoft Office",
        "adobe": "Adobe", "autodesk": "Autodesk",
        "jetbrains": "JetBrains IDE", "pycharm": "PyCharm",
        "vscode": "Visual Studio Code", "visual studio": "Visual Studio",
        "python": "Python", "java": "Java/JDK", "node": "Node.js",
        "git": "Git", "docker": "Docker", "mysql": "MySQL",
        "steam": "Steam", "epic games": "Epic Games",
        "discord": "Discord", "slack": "Slack", "telegram": "Telegram",
        "spotify": "Spotify", "vlc": "VLC Player", "obs": "OBS Studio",
        "notepad++": "Notepad++", "7-zip": "7-Zip", "winrar": "WinRAR",
        "everything": "Everything", "codex": "OpenAI Codex",
        "nvidia": "NVIDIA", "amd": "AMD", "intel": "Intel",
        "vmware": "VMware", "virtualbox": "VirtualBox",
        "postman": "Postman", "dbeaver": "DBeaver",
    }

    def _guess_software(self, child):
        fp = getattr(child, 'path', '') or ''
        lower = fp.lower().replace('\\', '/')
        if '/windows/system32/' in lower or '/windows/syswow64/' in lower:
            return "Windows 系统核心"
        if '/windows/winsxs/' in lower:
            return "Windows WinSxS"
        if '/windows/fonts/' in lower:
            return "Windows 字体"
        if '/windows/' in lower:
            return "Windows 系统"
        for base in ['/program files/', '/program files (x86)/']:
            if base in lower:
                idx = lower.index(base) + len(base)
                rest = fp[idx:].split('/')
                if rest and rest[0]:
                    vendor = rest[0].lower()
                    for key, display in self._SOFTWARE_DIRS.items():
                        if key in vendor: return display
                    return rest[0]
        if '/programdata/' in lower:
            idx = lower.index('/programdata/') + len('/programdata/')
            rest = fp[idx:].split('/')
            if rest and rest[0]:
                vendor = rest[0].lower()
                for key, display in self._SOFTWARE_DIRS.items():
                    if key in vendor: return display
                return rest[0] + " (数据)"
        if '/appdata/' in lower:
            if '/appdata/local/' in lower:
                idx = lower.index('/appdata/local/') + len('/appdata/local/')
                rest = fp[idx:].split('/')
                if rest and rest[0]:
                    vendor = rest[0].lower()
                    for key, display in self._SOFTWARE_DIRS.items():
                        if key in vendor: return display + " (本地)"
                    return rest[0] + " (本地)"
            if '/appdata/roaming/' in lower:
                idx = lower.index('/appdata/roaming/') + len('/appdata/roaming/')
                rest = fp[idx:].split('/')
                if rest and rest[0]:
                    vendor = rest[0].lower()
                    for key, display in self._SOFTWARE_DIRS.items():
                        if key in vendor: return display + " (Roaming)"
                    return rest[0] + " (Roaming)"
            return "应用数据"
        if '/users/' in lower:
            if '/downloads/' in lower: return "用户下载"
            if '/desktop/' in lower: return "用户桌面"
            if '/documents/' in lower: return "用户文档"
            if '/pictures/' in lower: return "用户图片"
            return "用户文件"
        if '/driverstore/' in lower or '/drivers/' in lower:
            return "驱动程序"
        if '/temp/' in lower or '/tmp/' in lower:
            return "临时文件"
        if '/logs/' in lower:
            return "日志文件"
        parent = _os.path.dirname(fp) if fp else ''
        if parent:
            pname = _os.path.basename(parent)
            if pname and len(pname) > 1:
                vendor = pname.lower()
                for key, display in self._SOFTWARE_DIRS.items():
                    if key in vendor: return display
                return pname
        return "-"

    def _rebuild_list(self):
        tx = self.search_edit.text().lower() if hasattr(self, "search_edit") else ""
        cat_filter = self.cat_combo.currentData() or "" if hasattr(self, "cat_combo") else ""
        self.file_tree.clear()
        self.file_tree.setSortingEnabled(False)
        self.file_tree.setUpdatesEnabled(False)

        all_f = self._all_flat_files if hasattr(self, "_all_flat_files") else []
        total = len(all_f)

        matched = []
        max_results = load_settings().get('max_results', 500)
        for child in all_f:
            if len(matched) >= max_results:
                break
            try:
                ce = getattr(child, "ext", "")
                cat = get_file_extension_category(ce) if ce else "Other"
                if cat_filter and cat != cat_filter:
                    continue
                name = (child.name or "").lower()
                if tx and tx not in name:
                    continue
                matched.append((child, cat, ce))
            except:
                continue

        matched.sort(key=lambda x: x[0].size, reverse=True)
        sw_cache = {}
        count = 0
        for child, cat, ce in matched:
            try:
                item = SortTreeWidgetItem()
                item.setCheckState(0, Qt.Unchecked)
                item.setText(1, child.name or "?")
                sz = child.size; item.setText(2, format_size(sz)); item._raw_size = sz; bp = min(sz/1073741824*100, 100); item.setForeground(2, QColor(size_color(bp)))
                item.setText(3, CAT_NAMES.get(cat, cat))
                item.setText(4, ce or "-")
                try:
                    item.setForeground(3, QColor(CAT_COLORS.get(cat, "#888")))
                except:
                    pass
                mt = child.mtime if hasattr(child, "mtime") and child.mtime else 0
                item.setText(5, format_timestamp(mt) if mt else "-")
                if hasattr(child, "safety") and child.safety:
                    try:
                        item.setText(6, child.safety.get("label", "-"))
                        lvl = child.safety.get("level", 3)
                        item.setForeground(6, QColor(SAFETY_COLORS[min(lvl, 3)]))
                    except:
                        item.setText(6, "-")
                else:
                    item.setText(6, "-")
                fp = getattr(child, "path", "") or ""
                if fp not in sw_cache:
                    sw_cache[fp] = self._guess_software(child)
                item.setText(7, sw_cache[fp])
                item.setData(0, Qt.UserRole, child)
                self.file_tree.addTopLevelItem(item)
                count += 1
                if count % 100 == 0:
                    from PySide6.QtWidgets import QApplication
                    QApplication.processEvents()
            except:
                continue

        self.file_tree.setSortingEnabled(True)
        self.file_tree.setUpdatesEnabled(True)
        self.file_tree.sortByColumn(2, Qt.DescendingOrder)
        QTimer.singleShot(0, lambda: self.file_tree.resizeColumnToContents(1))
        self.info_lbl.setText(f"显示 {count} 个 (共 {total} 个文件)")

    # ---- Actions ----
    def _on_dbl(self, item):
        node = item.data(0, Qt.UserRole)
        if node and hasattr(node, 'path') and _os.path.exists(node.path):
            _sp.Popen(['explorer', '/select,', _os.path.normpath(node.path)], shell=False)

    def _ctx_menu(self, pos):
        it = self.file_tree.itemAt(pos)
        if not it: return
        node = it.data(0, Qt.UserRole)
        if node and hasattr(node, 'path'):
            menu = QMenu(self)
            act = QAction("打开文件所在目录", self)
            act.triggered.connect(lambda n=node: (_sp.Popen(['explorer','/select,',_os.path.normpath(n.path)], shell=False) if _os.path.exists(n.path) else None))
            menu.addAction(act)
            menu.exec_(self.file_tree.viewport().mapToGlobal(pos))

    def _open_selected(self):
        it = self.file_tree.currentItem()
        if not it: return
        node = it.data(0, Qt.UserRole)
        if node and hasattr(node, 'path') and _os.path.exists(node.path):
            _sp.Popen(['explorer', '/select,', _os.path.normpath(node.path)], shell=False)

    def _delete_selected(self):
        td = []
        for i in range(self.file_tree.topLevelItemCount()):
            itm = self.file_tree.topLevelItem(i)
            if itm.checkState(0) == Qt.Checked:
                node = itm.data(0, Qt.UserRole)
                if node: td.append((node, itm))
        if not td:
            QMessageBox.information(self, "提示", "请先选择要删除的文件")
            return
        items = td[:10]
        names = chr(10).join(n.name + " (" + format_size(n.size) + ")" for n, _ in items)
        if len(td) > 10:
            names += chr(10) + "... 还有 " + str(len(td)-10) + " 个"
        r = QMessageBox.warning(self, "确认删除",
            "确定要删除以下文件吗？\n\n" + names + "\n\n此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes: return
        cleaned = 0; failed = 0
        for node, _ in td:
            try:
                if _os.path.exists(node.path):
                    _os.remove(node.path)
                    cleaned += 1
            except:
                failed += 1
        msg = "已删除 " + str(cleaned) + " 个"
        if failed: msg += " (" + str(failed) + " 失败)"
        self.status_message.emit(msg)
        self.status_lbl.setText(msg)
        QMessageBox.information(self, "结果", msg)

    # ---- Charts ----
    def _update_charts(self):
        all_files = self._all_flat_files
        cat_sizes = {}
        for f in all_files:
            ext = getattr(f, 'ext', '')
            cat = get_file_extension_category(ext) if ext else 'Other'
            cat_sizes[cat] = cat_sizes.get(cat, 0) + getattr(f, 'size', 0)
        self.ext_tree.clear()
        ext_stats = {}
        for f in all_files:
            ext = getattr(f, 'ext', '') or '(none)'
            if ext not in ext_stats:
                ext_stats[ext] = {"count": 0, "size": 0}
            ext_stats[ext]["count"] += 1
            ext_stats[ext]["size"] += getattr(f, "size", 0)
        for ext, stats in sorted(ext_stats.items(), key=lambda x: x[1]['size'], reverse=True)[:50]:
            item = SortTreeWidgetItem()
            item.setText(0, ext)
            cat = get_file_extension_category(ext)
            item.setText(1, CAT_NAMES.get(cat, cat) if ext != "(none)" else "-")
            item.setText(2, str(stats["count"]))
            item.setText(3, format_size(stats["size"]))
            self.ext_tree.addTopLevelItem(item)

    def _set_visible(self, visible):
        if visible and not self._loaded:
            self._loaded = True
            # Cache disabled - always need fresh scan
