"""Startup Manager - refined categories + open folder + real disable via StartupApproved"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox, QMenu, QComboBox)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QFont, QColor, QAction
import os as _os, winreg, subprocess as _sp
from utils.helpers import recycle_path

STARTUP_APPROVED_RUN = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
DISABLED_BINARY = b"\x03\x00\x00\x00" + b"\x00" * 8  # 0x03 = disabled, + FILETIME placeholder

# Refined category definitions
CATEGORIES = {
    "\u7cfb\u7edf\u670d\u52a1": ["SecurityHealth", "WindowsDefender", "RtkAudUService", "wlidsvc", "Wlan"],
    "\u663e\u5361\u5de5\u5177": ["IgfxTray", "NvBackend", "Radeon", "GfeSDK", "AMD", "NVIDIA", "GeForce"],
    "\u97f3\u9891\u7ba1\u7406": ["RTHDVCPL", "HD Audio", "Sound", "Audio", "Realtek", "C-Media", "VIAHD"],
    "\u4e91\u670d\u52a1": ["OneDrive", "Dropbox", "GoogleDrive", "iCloud", "BaiduNetdisk", "pCloud", "Mega"],
    "\u5b89\u5168\u8f6f\u4ef6": ["Avast", "AVG", "Kaspersky", "Norton", "McAfee", "360", "Defender", "Bitdefender"],
    "\u8f93\u5165\u6cd5": ["ctfmon", "Sogou", "QQPinyin", "BaiduPinyin", "GooglePinyin", "MsCtfMonitor"],
    "\u901a\u8baf\u5de5\u5177": ["WeChat", "QQ", "DingTalk", "Teams", "Skype", "Discord", "Slack", "Telegram", "Zoom"],
    "\u6d4f\u89c8\u5668": ["Chrome", "Edge", "Firefox", "Brave", "Opera"],
    "\u5f00\u53d1\u5de5\u5177": ["VS Code", "JetBrains", "Android", "Docker", "Git", "Node.js", "Python"],
    "\u6e38\u620f\u5e73\u53f0": ["Steam", "Epic", "Ubisoft", "Origin", "GOG", "Battle.net"],
    "\u786c\u4ef6\u76d1\u63a7": ["HotKeys", "TPM", "Virtual", "VMware", "Bluetooth", "Wifi", "LAN"],
    "\u66f4\u65b0\u670d\u52a1": ["Update", "Updater", "AutoUpdate", "LiveUpdate", "AdobeGC"],
    "\u5e94\u7528\u8f6f\u4ef6": [],
}

CAT_COLORS_STARTUP = {
    "\u7cfb\u7edf\u670d\u52a1": "#58a6ff",
    "\u663e\u5361\u5de5\u5177": "#4CAF50",
    "\u97f3\u9891\u7ba1\u7406": "#00BCD4",
    "\u4e91\u670d\u52a1": "#2196F3",
    "\u5b89\u5168\u8f6f\u4ef6": "#F44336",
    "\u8f93\u5165\u6cd5": "#9C27B0",
    "\u901a\u8baf\u5de5\u5177": "#FF9800",
    "\u6d4f\u89c8\u5668": "#FF5722",
    "\u5f00\u53d1\u5de5\u5177": "#00BCD4",
    "\u6e38\u620f\u5e73\u53f0": "#E91E63",
    "\u786c\u4ef6\u76d1\u63a7": "#607D8B",
    "\u66f4\u65b0\u670d\u52a1": "#795548",
    "\u5e94\u7528\u8f6f\u4ef6": "#4CAF50",
}

def _classify_startup(name, cmd, src):
    nl = name.lower(); cl = str(cmd).lower()
    # Check system paths
    if "\\system32\\" in cl or "\\windows\\" in cl or "\\syswow64\\" in cl:
        # Further classify system items
        for cat, keywords in CATEGORIES.items():
            if cat in ("\u5e94\u7528\u8f6f\u4ef6",): continue
            for kw in keywords:
                if kw.lower() in nl or kw.lower() in cl:
                    return cat
        return "\u7cfb\u7edf\u670d\u52a1"
    # Check known software categories
    for cat, keywords in CATEGORIES.items():
        if cat == "\u7cfb\u7edf\u670d\u52a1": continue
        for kw in keywords:
            if kw.lower() in nl or kw.lower() in cl:
                return cat
    # Detect by folder name
    for part in cl.replace('\\', '/').split('/'):
        part = part.strip('"').strip("'")
        if part and len(part) > 3 and '.' not in part:
            for cat, keywords in CATEGORIES.items():
                for kw in keywords:
                    if kw.lower() in part.lower():
                        return cat
    return "\u5e94\u7528\u8f6f\u4ef6"

def _open_startup_location(entry):
    try:
        if entry.get("type") == "shortcut":
            fp = entry.get("path", entry.get("cmd", ""))
            if _os.path.exists(fp):
                _sp.Popen(['explorer', '/select,', _os.path.normpath(fp)], shell=False)
                return
        # For registry entries, open regedit to the key
        cmd = entry.get("cmd", "")
        if cmd and _os.path.exists(cmd):
            _sp.Popen(['explorer', '/select,', _os.path.normpath(cmd)], shell=False)
            return
        # Fallback: open the parent dir of cmd
        parent = _os.path.dirname(cmd)
        if parent and _os.path.exists(parent):
            _sp.Popen(['explorer', parent])
    except Exception: pass

class StartupManagerPage(QWidget):
    status_message = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent); self._entries = []; self._current_filter = None
        self._setup_ui()
        QTimer.singleShot(300, self._load)

    def _setup_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(12,12,12,12); layout.setSpacing(8)
        tb = QHBoxLayout()
        t = QLabel("\u542f\u52a8\u7ba1\u7406")
        t.setObjectName("pageTitle"); tb.addWidget(t); tb.addStretch()
        r = QPushButton("\u5237\u65b0"); r.clicked.connect(self._load); tb.addWidget(r)
        self.open_btn = QPushButton("\u6253\u5f00\u4f4d\u7f6e"); self.open_btn.clicked.connect(self._open_selected)
        tb.addWidget(self.open_btn)
        self.disable_btn = QPushButton("\u7981\u7528/\u5220\u9664")
        self.disable_btn.setObjectName("redBtn")
        self.disable_btn.clicked.connect(self._disable_selected); tb.addWidget(self.disable_btn)
        layout.addLayout(tb)

        # Filter row with combo box for refined categories
        fr = QHBoxLayout(); fr.addWidget(QLabel("\u7c7b\u522b:"))
        self.cat_combo = QComboBox()
        self.cat_combo.addItem("\u5168\u90e8", None)
        for cat_name in CATEGORIES.keys():
            self.cat_combo.addItem(cat_name, cat_name)
        self.cat_combo.currentIndexChanged.connect(lambda idx: self._apply_filter(self.cat_combo.currentData()))
        fr.addWidget(self.cat_combo); fr.addStretch(); layout.addLayout(fr)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["", "\u540d\u79f0", "\u547d\u4ee4/\u8def\u5f84", "\u4f4d\u7f6e", "\u7c7b\u522b", "\u7c7b\u578b"])
        self.tree.setColumnWidth(0, 48); self.tree.setColumnWidth(1, 220)
        self.tree.setColumnWidth(2, 350); self.tree.setColumnWidth(3, 100)
        self.tree.setColumnWidth(4, 90); self.tree.setColumnWidth(5, 70)
        self.tree.setAlternatingRowColors(True)
        self.tree.setIndentation(0)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.tree)
        self.slbl = QLabel(""); self.slbl.setStyleSheet("color:#888;"); layout.addWidget(self.slbl)

    def _load_disabled_names(self):
        """Value names marked disabled in StartupApproved (HKCU view, merged)."""
        disabled = set()
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_APPROVED_RUN)
            i = 0
            while True:
                try:
                    n, d, _ = winreg.EnumValue(key, i)
                    if isinstance(d, (bytes, bytearray)) and len(d) >= 4 and d[0] & 0x01:
                        disabled.add(n)
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except OSError:
            pass
        return disabled

    def _load(self):
        self.tree.clear(); self._entries = []
        disabled_names = self._load_disabled_names()
        # 注意：0x80000000 是 HKEY_CLASSES_ROOT，HKCU 必须用 winreg.HKEY_CURRENT_USER
        reg_root = winreg.HKEY_CURRENT_USER
        reg_lm = winreg.HKEY_LOCAL_MACHINE
        paths = [(reg_root, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU"),
                 (reg_lm, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM")]
        # Also check RunOnce and WOW6432Node
        try:
            # HKLM WOW6432Node for 32-bit apps on 64-bit
            key = winreg.OpenKey(reg_lm, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run")
            for i in range(winreg.QueryInfoKey(key)[1]):
                try:
                    n, d, _ = winreg.EnumValue(key, i)
                    cat = _classify_startup(n, str(d), "HKLM(32bit)")
                    self._entries.append({"name":n,"cmd":str(d),"source":"HKLM(32bit)","cat":cat,"hkey":reg_lm,"subkey":r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run","type":"registry","disabled":n in disabled_names})
                except OSError: continue
            winreg.CloseKey(key)
        except OSError: pass

        for hkey_val, sub, src in paths:
            try:
                key = winreg.OpenKey(hkey_val, sub)
                for i in range(winreg.QueryInfoKey(key)[1]):
                    try:
                        n, d, _ = winreg.EnumValue(key, i)
                        cat = _classify_startup(n, str(d), src)
                        self._entries.append({"name":n,"cmd":str(d),"source":src,"cat":cat,"hkey":hkey_val,"subkey":sub,"type":"registry","disabled":n in disabled_names})
                    except OSError: continue
                winreg.CloseKey(key)
            except OSError: continue

        sf = _os.path.join(_os.environ.get("APPDATA",""), "Microsoft","Windows","Start Menu","Programs","Startup")
        if _os.path.exists(sf):
            for fn in _os.listdir(sf):
                if fn.lower() == "desktop.ini":
                    continue
                fp = _os.path.join(sf, fn)
                cat = _classify_startup(fn, fp, "启动文件夹")
                self._entries.append({"name":fn,"cmd":fp,"source":"启动文件夹","cat":cat,"type":"shortcut","path":fp,"disabled":False})

        # Common startup folder
        csf = _os.path.join(_os.environ.get("PROGRAMDATA",""), "Microsoft","Windows","Start Menu","Programs","Startup")
        if _os.path.exists(csf):
            for fn in _os.listdir(csf):
                if fn.lower() == "desktop.ini":
                    continue
                fp = _os.path.join(csf, fn)
                cat = _classify_startup(fn, fp, "公共启动")
                self._entries.append({"name":fn,"cmd":fp,"source":"公共启动","cat":cat,"type":"shortcut","path":fp,"disabled":False})

        self._apply_filter(self.cat_combo.currentData())

    def _apply_filter(self, category):
        self._current_filter = category
        self.tree.clear()
        for idx, e in enumerate(self._entries):
            if category and e["cat"] != category: continue
            item = QTreeWidgetItem()
            item.setCheckState(0, Qt.Unchecked)
            item.setText(1, e["name"]); item.setText(2, e["cmd"])
            item.setText(3, e["source"]); item.setText(4, e["cat"])
            item.setText(5, ("已禁用" if e.get("disabled") else "") + e["type"])
            color = CAT_COLORS_STARTUP.get(e["cat"], "#888")
            if e.get("disabled"):
                color = "#666"
            try:
                item.setForeground(4, QColor(color))
                if e.get("disabled"):
                    item.setForeground(1, QColor("#777"))
            except: pass
            item.setData(1, Qt.UserRole, idx)
            self.tree.addTopLevelItem(item)
        filtered = self.tree.topLevelItemCount()
        self.slbl.setText(f"\u5171 {len(self._entries)} \u9879 (\u663e\u793a {filtered} \u9879)")
        self.status_message.emit(f"\u542f\u52a8\u7ba1\u7406: {len(self._entries)} \u9879")

    def _open_selected(self):
        it = self.tree.currentItem()
        if not it:
            QMessageBox.information(self, "\u63d0\u793a", "\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u542f\u52a8\u9879")
            return
        idx = it.data(1, Qt.UserRole)
        if idx is None or idx >= len(self._entries): return
        _open_startup_location(self._entries[idx])

    def _context_menu(self, pos):
        it = self.tree.itemAt(pos)
        if not it: return
        idx = it.data(1, Qt.UserRole)
        if idx is None or idx >= len(self._entries): return
        entry = self._entries[idx]
        menu = QMenu(self)
        act_open = QAction("\u6253\u5f00\u6587\u4ef6\u4f4d\u7f6e", self)
        act_open.triggered.connect(lambda: _open_startup_location(entry))
        menu.addAction(act_open)
        if entry.get("type") == "registry":
            act_reg = QAction("\u6253\u5f00\u6ce8\u518c\u8868\u4f4d\u7f6e", self)
            act_reg.triggered.connect(lambda: _sp.Popen(['regedit', '/m'], shell=False))
            menu.addAction(act_reg)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _disable_selected(self):
        td = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.checkState(0) == Qt.Checked:
                idx = it.data(1, Qt.UserRole)
                if idx is not None and idx < len(self._entries):
                    td.append((it, self._entries[idx]))
        if not td:
            QMessageBox.information(self, "\u63d0\u793a", "\u8bf7\u5148\u9009\u62e9\u8981\u7981\u7528\u7684\u542f\u52a8\u9879")
            return
        names = chr(10).join(it.text(1) for it, _ in td[:8])
        if len(td) > 8: names += chr(10) + f"... 还有 {len(td)-8} 项"
        r = QMessageBox.warning(self, "确认禁用",
            f"确定要禁用以下启动项吗？\n\n{names}\n\n"
            "注册表启动项将被禁用（可在任务管理器-启动中重新启用），\n"
            "快捷方式将移入回收站。",
            QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes: return
        cleaned = 0; failed = 0
        for it, e in td:
            try:
                if e["type"] == "registry":
                    # 写入 StartupApproved 真禁用（不删除，可随时恢复）
                    try:
                        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, STARTUP_APPROVED_RUN)
                    except OSError:
                        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_APPROVED_RUN, 0, winreg.KEY_SET_VALUE)
                    try:
                        winreg.SetValueEx(key, e["name"], 0, winreg.REG_BINARY, DISABLED_BINARY)
                    finally:
                        winreg.CloseKey(key)
                    cleaned += 1
                elif e["type"] == "shortcut":
                    fp = e.get("path", e["cmd"])
                    if _os.path.exists(fp) and recycle_path(fp): cleaned += 1
                    else: failed += 1
                else: failed += 1
            except Exception:
                failed += 1
        msg = f"已禁用 {cleaned} 项"
        if failed: msg += f", {failed} 失败"
        self.status_message.emit(msg)
        QMessageBox.information(self, "结果", msg)
        QTimer.singleShot(500, self._load)
