"""Startup Manager - refined categories + open folder + disable"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox, QMenu, QComboBox)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QFont, QColor, QAction
import os as _os, winreg, subprocess as _sp

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
        t.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        t.setStyleSheet("color: #e0e0e0;"); tb.addWidget(t); tb.addStretch()
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

    def _load(self):
        self.tree.clear(); self._entries = []
        reg_root = 0x80000000  # HKEY_CURRENT_USER
        reg_lm = 0x80000002    # HKEY_LOCAL_MACHINE
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
                    self._entries.append({"name":n,"cmd":str(d),"source":"HKLM(32bit)","cat":cat,"hkey":reg_lm,"subkey":r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run","type":"registry"})
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
                        self._entries.append({"name":n,"cmd":str(d),"source":src,"cat":cat,"hkey":hkey_val,"subkey":sub,"type":"registry"})
                    except OSError: continue
                winreg.CloseKey(key)
            except OSError: continue

        sf = _os.path.join(_os.environ.get("APPDATA",""), "Microsoft","Windows","Start Menu","Programs","Startup")
        if _os.path.exists(sf):
            for fn in _os.listdir(sf):
                fp = _os.path.join(sf, fn)
                cat = _classify_startup(fn, fp, "\u542f\u52a8\u6587\u4ef6\u5939")
                self._entries.append({"name":fn,"cmd":fp,"source":"\u542f\u52a8\u6587\u4ef6\u5939","cat":cat,"type":"shortcut","path":fp})

        # Common startup folder
        csf = _os.path.join(_os.environ.get("PROGRAMDATA",""), "Microsoft","Windows","Start Menu","Programs","Startup")
        if _os.path.exists(csf):
            for fn in _os.listdir(csf):
                fp = _os.path.join(csf, fn)
                cat = _classify_startup(fn, fp, "\u516c\u5171\u542f\u52a8")
                self._entries.append({"name":fn,"cmd":fp,"source":"\u516c\u5171\u542f\u52a8","cat":cat,"type":"shortcut","path":fp})

        self._apply_filter(self.cat_combo.currentData())

    def _apply_filter(self, category):
        self._current_filter = category
        self.tree.clear()
        for idx, e in enumerate(self._entries):
            if category and e["cat"] != category: continue
            item = QTreeWidgetItem()
            item.setCheckState(0, Qt.Unchecked)
            item.setText(1, e["name"]); item.setText(2, e["cmd"])
            item.setText(3, e["source"]); item.setText(4, e["cat"]); item.setText(5, e["type"])
            try:
                color = CAT_COLORS_STARTUP.get(e["cat"], "#888")
                item.setForeground(4, QColor(color))
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
        if len(td) > 8: names += chr(10) + f"... \u8fd8\u6709 {len(td)-8} \u9879"
        r = QMessageBox.warning(self, "\u786e\u8ba4\u7981\u7528",
            f"\u786e\u5b9a\u8981\u7981\u7528\u4ee5\u4e0b\u542f\u52a8\u9879\u5417\uff1f\n\n{names}",
            QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes: return
        cleaned = 0; failed = 0
        for it, e in td:
            try:
                if e["type"] == "registry":
                    key = winreg.OpenKey(e["hkey"], e["subkey"], 0, winreg.KEY_SET_VALUE)
                    winreg.DeleteValue(key, e["name"]); winreg.CloseKey(key)
                    cleaned += 1
                elif e["type"] == "shortcut":
                    fp = e.get("path", e["cmd"])
                    if _os.path.exists(fp): _os.remove(fp); cleaned += 1
                else: failed += 1
                it.setHidden(True)
            except Exception as ex: failed += 1
        msg = f"\u5df2\u7981\u7528 {cleaned} \u9879"
        if failed: msg += f", {failed} \u5931\u8d25"
        self.status_message.emit(msg)
        QMessageBox.information(self, "\u7ed3\u679c", msg)
        QTimer.singleShot(500, self._load)
