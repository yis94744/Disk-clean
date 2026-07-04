"""Software Manager - refined UI with card detail panel"""
import os as _os
import shutil
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QCheckBox,
    QPushButton, QTreeWidget, QTreeWidgetItem, QLineEdit, QTextEdit,
    QSplitter, QMessageBox, QProgressBar, QComboBox, QGridLayout, QScrollArea)
from PySide6.QtCore import Signal, Qt, QThread, QSize, QTimer
from PySide6.QtCore import QFileInfo
from PySide6.QtWidgets import QFileIconProvider
from PySide6.QtGui import QFont, QIcon, QPixmap, QColor, QPainter, QPen, QBrush, QPalette
from core.uninstaller import UninstallWorker, UninstallExecutor
from utils.helpers import format_size, get_drives

KNOWN_SOFTWARE = {
    "google chrome": "Google Chrome - Fast, secure web browser by Google",
    "microsoft edge": "Microsoft Edge - Modern web browser by Microsoft",
    "mozilla firefox": "Mozilla Firefox - Open-source web browser",
    "visual studio code": "VS Code - Lightweight code editor by Microsoft",
    "python": "Python programming language interpreter",
    "node.js": "JavaScript runtime built on Chrome V8 engine",
    "git": "Distributed version control system",
    "7-zip": "7-Zip - High compression ratio file archiver",
    "winrar": "WinRAR - File compression and archive manager",
    "notepad++": "Notepad++ - Free source code editor",
    "vlc media player": "VLC - Versatile media player",
    "spotify": "Spotify - Music streaming service",
    "discord": "Discord - Voice, video and text chat platform",
    "steam": "Steam - Digital game distribution platform",
    "microsoft office": "Microsoft Office productivity suite",
    "adobe acrobat": "Adobe Acrobat - PDF reader and editor",
    "java": "Java Runtime Environment",
    "docker": "Docker - Container platform",
    "wps office": "WPS Office - Free office suite",
    "everything": "Everything - Fast file search engine",
}

L = {
    "sm": "软件管理",
    "n": "名称", "v": "版本", "p": "发布者",
    "d": "磁盘", "s": "大小", "t": "类型",
    "sy": "系统", "us": "用户", "al": "全部",
    "rf": "刷新", "un": "卸载选中",
    "dl": "删除文件夹", "sh": "搜索软件",
    "sg": "扫描软件", "wn": "警告", "tp": "提示",
    "cf": "确认", "cu": "确认卸载以下软件？",
    "sf": "请先选择软件", "sw": "系统组件，不建议卸载",
    "isc": "是系统组件，确定卸载？",
    "dc": "全部完成，检查残留",
    "ui": "正在卸载", "fl": "失败",
    "nr": "未发现残留", "cd": "清理完成",
    "fr": "发现残留", "cq": "是否清除？",
    "cld": "已清除", "fld": "失败",
    "id": "安装目录", "rk": "注册表",
    "nd": "暂无介绍", "ds": "介绍",
    "lc": "位置", "dt": "安装日期", "rg": "注册表",
    "stg": "[系统组件]", "utg": "[用户软件]",
    "dct": "确认删除", "dcw": "确认删除以下文件夹？",
    "dcn": "此操作不可撤销",
    "dld": "已删除", "clc": "清理完成",
    "disp": "显示", "ge": "个软件",
    "fo": "找到", "ya": "个应用",
    "sel_hint": "选择软件查看详情",
    "log": "日志", "log_hint": "操作日志显示在此处",
    "select_all": "全选", "deselect": "取消全选",
    "selected_count": "已选",
}


# Software category definitions - name/publisher based
SOFTWARE_CATEGORIES = {
    # Browsers
    "chrome": ("browser", "Chrome", "#4285F4"),
    "edge": ("browser", "Edge", "#0078D4"),
    "firefox": ("browser", "FF", "#FF7139"),
    "opera": ("browser", "OP", "#FF1B2D"),
    "brave": ("browser", "BR", "#FB542B"),
    # Development
    "python": ("dev", "PY", "#3776AB"),
    "node.js": ("dev", "JS", "#339933"),
    "visual studio code": ("dev", "VS", "#007ACC"),
    "visual studio": ("dev", "VS", "#5C2D91"),
    "git": ("dev", "GIT", "#F05032"),
    "docker": ("dev", "DK", "#2496ED"),
    "postman": ("dev", "API", "#FF6C37"),
    "intellij": ("dev", "IJ", "#000000"),
    "pycharm": ("dev", "PC", "#21D789"),
    "webstorm": ("dev", "WS", "#07C3F2"),
    "android studio": ("dev", "AS", "#3DDC84"),
    "eclipse": ("dev", "EC", "#2C2255"),
    "sublime": ("dev", "ST", "#FF9800"),
    "notepad++": ("dev", "NP", "#90E59A"),
    "vim": ("dev", "VI", "#019733"),
    "cmake": ("dev", "CM", "#064F8C"),
    "anaconda": ("dev", "AN", "#44A833"),
    "mingw": ("dev", "MW", "#555555"),
    "gcc": ("dev", "GC", "#555555"),
    "rust": ("dev", "RS", "#DEA584"),
    # System / Microsoft
    "microsoft visual c++": ("sys", "VC", "#9B4F96"),
    "microsoft .net": ("sys", ".N", "#512BD4"),
    "microsoft windows": ("sys", "Win", "#0078D4"),
    "microsoft edge webview": ("sys", "WV", "#0078D4"),
    "microsoft office": ("office", "OF", "#D83B01"),
    "microsoft 365": ("office", "M3", "#D83B01"),
    "microsoft onedrive": ("cloud", "1D", "#0078D4"),
    "directx": ("sys", "DX", "#107C10"),
    "windows sdk": ("sys", "SDK", "#0078D4"),
    # Runtimes / Plugins
    "java(tm)": ("runtime", "JRE", "#ED8B00"),
    "java se": ("runtime", "JRE", "#ED8B00"),
    "jdk": ("runtime", "JDK", "#ED8B00"),
    "oracle": ("runtime", "OR", "#F80000"),
    ".net runtime": ("runtime", ".N", "#512BD4"),
    ".net sdk": ("runtime", ".N", "#512BD4"),
    "asp.net": ("runtime", "AS", "#512BD4"),
    "windows driver": ("driver", "DRV", "#0078D4"),
    "nvidia": ("driver", "NV", "#76B900"),
    "amd": ("driver", "AMD", "#ED1C24"),
    "intel": ("driver", "IN", "#0071C5"),
    "realtek": ("driver", "RT", "#00A4EF"),
    # Plugins / Extensions
    "plugin": ("plugin", "PL", "#FF5722"),
    "extension": ("plugin", "EX", "#FF5722"),
    "addin": ("plugin", "AD", "#FF5722"),
    # Media
    "vlc": ("media", "VLC", "#FF8800"),
    "spotify": ("media", "SP", "#1DB954"),
    "itunes": ("media", "iT", "#FB5BC5"),
    "k-lite": ("media", "KL", "#2196F3"),
    "obs studio": ("media", "OBS", "#302E31"),
    "handbrake": ("media", "HB", "#FF5722"),
    "audacity": ("media", "AU", "#0000CC"),
    "gimp": ("media", "GP", "#5C5543"),
    "blender": ("media", "BL", "#F5792A"),
    "photoshop": ("media", "PS", "#31A8FF"),
    "illustrator": ("media", "AI", "#FF9A00"),
    "adobe": ("media", "AD", "#FF0000"),
    # Games
    "steam": ("game", "ST", "#171A21"),
    "epic games": ("game", "EP", "#313131"),
    "ubisoft": ("game", "UB", "#000000"),
    "origin": ("game", "OR", "#F56C2D"),
    "battle.net": ("game", "BN", "#148EFF"),
    "minecraft": ("game", "MC", "#62B47A"),
    # Office / Productivity
    "office": ("office", "OF", "#D83B01"),
    "wps": ("office", "WP", "#E94E35"),
    "libreoffice": ("office", "LO", "#18A303"),
    "acrobat": ("office", "PDF", "#FA0F00"),
    "pdf": ("office", "PDF", "#FA0F00"),
    "notion": ("office", "NO", "#000000"),
    "evernote": ("office", "EN", "#00A82D"),
    "onenote": ("office", "ON", "#7719AA"),
    "slack": ("office", "SL", "#4A154B"),
    "teams": ("office", "TM", "#6264A7"),
    "zoom": ("office", "ZM", "#2D8CFF"),
    "discord": ("office", "DI", "#5865F2"),
    "telegram": ("office", "TG", "#26A5E4"),
    # Utilities
    "7-zip": ("tool", "7Z", "#795548"),
    "winrar": ("tool", "WR", "#2C88D4"),
    "everything": ("tool", "EV", "#FF5722"),
    "cpu-z": ("tool", "CZ", "#4CAF50"),
    "gpu-z": ("tool", "GZ", "#76B900"),
    "hwmonitor": ("tool", "HW", "#4CAF50"),
    "ccleaner": ("tool", "CC", "#D32F2F"),
    "recuva": ("tool", "RC", "#4CAF50"),
    "malwarebytes": ("tool", "MB", "#0066FF"),
    "avast": ("tool", "AV", "#FF7800"),
    "avira": ("tool", "AR", "#CC0000"),
    "bitdefender": ("tool", "BD", "#ED1C24"),
    "dropbox": ("cloud", "DB", "#0061FF"),
    "googledrive": ("cloud", "GD", "#4285F4"),
    "virtualbox": ("tool", "VB", "#183A61"),
    "vmware": ("tool", "VM", "#607078"),
    "putty": ("tool", "PT", "#024B78"),
    "wireshark": ("tool", "WS", "#1679A7"),
    "filezilla": ("tool", "FZ", "#BF0000"),
    "teamviewer": ("tool", "TV", "#004680"),
    "anydesk": ("tool", "AD", "#EF443B"),

    # --- More Dev ---
    "unity": ("dev", "UN", "#222C37"),
    "unreal": ("dev", "UE", "#313131"),
    "godot": ("dev", "GD", "#478CBF"),
    "jupyter": ("dev", "JU", "#F37626"),
    "fiddler": ("dev", "FD", "#8BC34A"),
    "nginx": ("dev", "NG", "#009639"),
    "apache": ("dev", "AP", "#D22128"),
    "tomcat": ("dev", "TC", "#F8DC75"),
    "kubernetes": ("dev", "K8", "#326CE5"),
    "terraform": ("dev", "TF", "#7B42BC"),
    "cygwin": ("dev", "CY", "#00B0E0"),
    "msys2": ("dev", "MS", "#904090"),
    "ffmpeg": ("media", "FF", "#007808"),
    "qt": ("dev", "QT", "#41CD52"),
    "electron": ("dev", "EL", "#47848F"),
    "flutter": ("dev", "FL", "#02569B"),
    "powershell": ("dev", "PW", "#5391FE"),
    "spyder": ("dev", "SP", "#FF0000"),
    "gradle": ("dev", "GR", "#02303A"),
    "maven": ("dev", "MV", "#C71A36"),
    "pip": ("dev", "PI", "#3776AB"),
    "composer": ("dev", "CP", "#885630"),

    # --- More Runtime ---
    "cuda": ("runtime", "CU", "#76B900"),
    "vulkan": ("runtime", "VK", "#A41E22"),
    "silverlight": ("runtime", "SL", "#5C2D91"),
    "bonjour": ("runtime", "BJ", "#FF8000"),

    # --- More Drivers ---
    "qualcomm": ("driver", "QC", "#3253DC"),
    "broadcom": ("driver", "BC", "#CC092F"),
    "synaptics": ("driver", "SY", "#FEBE0E"),
    "wacom": ("driver", "WA", "#111111"),
    "creative": ("driver", "CR", "#FF7300"),
    "samsung": ("driver", "SA", "#1428A0"),

    # --- More Tools ---
    "total commander": ("tool", "TC", "#336699"),
    "teracopy": ("tool", "TP", "#A3231F"),
    "beyond compare": ("tool", "BC", "#B72F2A"),
    "winmerge": ("tool", "WM", "#FFA500"),
    "aida64": ("tool", "AI", "#C5272E"),
    "crystaldiskinfo": ("tool", "CD", "#4A90D9"),
    "crystaldiskmark": ("tool", "CM", "#4A90D9"),
    "defraggler": ("tool", "DF", "#1A698A"),
    "auslogics": ("tool", "AL", "#59B942"),
    "glary": ("tool", "GU", "#E33E2C"),
    "chocolatey": ("tool", "CH", "#80B500"),
    "scoop": ("tool", "SC", "#087CB8"),
    "winget": ("tool", "WG", "#0078D4"),
    "windows terminal": ("tool", "WT", "#4D4D4D"),
    "snagit": ("media", "SN", "#F15A24"),
    "bandicam": ("media", "BD", "#28A745"),
    "faststone": ("tool", "FS", "#4472C4"),
    "flameshot": ("tool", "FH", "#E32C2C"),
    "starship": ("tool", "ST", "#DD0B78"),
    "conemu": ("tool", "CN", "#B41414"),
    "ultraedit": ("dev", "UE", "#04923B"),
    "emacs": ("dev", "EM", "#7F5AB6"),
    "neovim": ("dev", "NV", "#57A143"),

    # --- Chinese Software ---
    "qqpcmgr": ("tool", "TX", "#1296DB"),
    "ludashi": ("tool", "LD", "#FF8800"),
    "huorong": ("tool", "HR", "#E8541E"),
    "drivergenius": ("tool", "DG", "#00A0E9"),
    "youdao": ("office", "YD", "#C9161E"),
    "alipay": ("office", "AP", "#1677FF"),
    "taobao": ("office", "TB", "#FF5000"),
    "yingyongbao": ("tool", "YY", "#0288D1"),
    "quark": ("browser", "QK", "#1677FF"),
    "uc browser": ("browser", "UC", "#FF6A00"),
    "douyu": ("media", "DY", "#FF7F00"),
    "huya": ("media", "HY", "#FFD700"),
    "wangyiyun": ("media", "WY", "#C62F2F"),
    "weibo": ("office", "WB", "#E6162D"),
    "zhihu": ("office", "ZH", "#0066FF"),
    "xiecheng": ("office", "XC", "#2F7DE1"),
    "meituan": ("office", "MT", "#FFC300"),
    "pinduoduo": ("office", "PD", "#E02E24"),

    # --- Office / Communication ---
    "skype": ("office", "SK", "#00AFF0"),
    "line": ("office", "LI", "#00C300"),
    "whatsapp": ("office", "WA", "#25D366"),
    "signal": ("office", "SI", "#3A76F0"),
    "webex": ("office", "WB", "#005073"),
    "citrix": ("office", "CX", "#452170"),
    "forticlient": ("office", "FC", "#EE3124"),
    "lastpass": ("office", "LP", "#D32D27"),
    "1password": ("office", "1P", "#0094F0"),
    "bitwarden": ("office", "BW", "#175DDC"),
    "microsoft authenticator": ("office", "MA", "#0078D4"),
    "sumatrapdf": ("office", "SP", "#FAB005"),
    "calibre": ("media", "CB", "#4DACC5"),
    "kindle": ("media", "KD", "#FFA100"),
    "zotero": ("office", "ZO", "#CC2936"),
    "anki": ("office", "AK", "#0288D1"),
    "grammarly": ("office", "GR", "#15C39A"),
    "deepl": ("office", "DP", "#0F2B46"),
    "translator": ("office", "TR", "#00A7E1"),

    # --- Brands / Vendors ---
    "lenovo": ("tool", "LN", "#E2231A"),
    "dell": ("tool", "DL", "#007DB8"),
    "acer": ("tool", "AC", "#83B81A"),
    "asus": ("tool", "AU", "#00539B"),
    "msi": ("tool", "MS", "#D32F2F"),
    "gigabyte": ("tool", "GB", "#2979FF"),
    "thinkpad": ("tool", "TP", "#E60000"),
    "surface": ("tool", "SF", "#0078D4"),
    "miui": ("tool", "MI", "#FF6900"),
    "vivo": ("tool", "VI", "#415FFF"),
    "oppo": ("tool", "OP", "#1BA784"),

}

CATEGORY_LABELS = {
    "browser": "Browser / Web",
    "dev": "IDE / Dev Tool",
    "sys": "System Component",
    "runtime": "Runtime / Framework",
    "driver": "Hardware Driver",
    "plugin": "Add-in / Plugin",
    "media": "Media / Graphics",
    "game": "Game / Platform",
    "office": "Office / Productivity",
    "cloud": "Cloud / Sync",
    "tool": "Utility / Tool",
}

CATEGORY_ICON_CACHE = {}

def _get_software_category(app):
    """Categorize software by name and publisher"""
    nl = (app.name or "").lower().strip()
    pl = (app.publisher or "").lower().strip()
    combo = nl + " " + pl

    # Check name first
    for key, (cat, label, color) in SOFTWARE_CATEGORIES.items():
        if key in nl:
            return cat, label, color

    # Check publisher
    for key, (cat, label, color) in SOFTWARE_CATEGORIES.items():
        if key in pl:
            return cat, label, color

    # Default by publisher
    if any(s in pl for s in ["microsoft", "windows"]):
        return "sys", "MS", "#0078D4"
    if any(s in pl for s in ["adobe"]):
        return "media", "AD", "#FF0000"
    if any(s in pl for s in ["oracle", "ibm", "apache"]):
        return "runtime", "RT", "#ED8B00"
    if any(s in pl for s in ["google"]):
        return "browser", "GG", "#4285F4"

    return "tool", "?", "#607D8B"

def _get_category_icon(cat, label, color):
    if (cat, label) in CATEGORY_ICON_CACHE:
        return CATEGORY_ICON_CACHE[(cat, label)]
    pix = QPixmap(32, 32); pix.fill(Qt.transparent)
    p = QPainter(pix); p.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)
    p.setBrush(QBrush(c)); p.setPen(Qt.NoPen)
    p.drawRoundedRect(2, 2, 28, 28, 6, 6)
    p.setPen(QPen(QColor("#FFFFFF")))
    p.setFont(QFont("Segoe UI", 8 if len(label) > 2 else 9, QFont.Bold))
    p.drawText(pix.rect(), Qt.AlignCenter, label)
    p.end()
    icon = QIcon(pix)
    CATEGORY_ICON_CACHE[(cat, label)] = icon
    return icon

def _get_description(name):
    nl = (name or "").lower().strip()
    for key, desc in KNOWN_SOFTWARE.items():
        if key in nl or nl in key: return desc
    return ""



# --- Icon extraction helpers ---
EXTRACT_ICON_CACHE = {}

def _resolve_exe_path(app):
    candidates = []
    if app.display_icon:
        p = app.display_icon.strip(chr(34)).strip("'")
        if "," in p:
            p = p.split(",")[0].strip()
        if p and _os.path.isfile(p):
            candidates.append(p)
    if app.install_location:
        loc = app.install_location.strip(chr(34)).strip("'")
        if loc and _os.path.isdir(loc):
            try:
                for f in _os.listdir(loc):
                    fl = f.lower()
                    if fl.endswith(".exe") and not fl.startswith("unins") and not fl.startswith("setup"):
                        fp = _os.path.join(loc, f)
                        if _os.path.isfile(fp) and _os.path.getsize(fp) > 10240:
                            candidates.append(fp)
            except Exception:
                pass
    if app.uninstall_string:
        us = app.uninstall_string.strip(chr(34)).strip("'")
        if us and _os.path.isfile(us) and us.lower().endswith(".exe"):
            candidates.append(us)
    return candidates

def _extract_icon_safe(filepath):
    if filepath in EXTRACT_ICON_CACHE:
        return EXTRACT_ICON_CACHE[filepath]
    if not filepath or not _os.path.isfile(filepath):
        return None
    try:
        provider = QFileIconProvider()
        icon = provider.icon(QFileInfo(filepath))
        if icon and not icon.isNull():
            pix = icon.pixmap(32, 32)
            if pix and not pix.isNull():
                EXTRACT_ICON_CACHE[filepath] = QIcon(pix)
                return EXTRACT_ICON_CACHE[filepath]
    except Exception:
        pass
    EXTRACT_ICON_CACHE[filepath] = None
    return None

def _get_drive(path):
    if path and len(path) >= 2 and path[1] == ":": return path[:2].upper()
    return ""

class SoftwareScannerThread(QThread):
    result = Signal(list); status = Signal(str)
    def run(self):
        self.status.emit(L["sg"] + "...")
        worker = UninstallWorker(); apps = worker.scan_all()
        self.result.emit(apps)




class IconLoaderThread(QThread):
    icon_ready = Signal(str, object)

    def __init__(self, apps):
        super().__init__()
        self.apps = apps

    def run(self):
        for app in self.apps:
            name = app.name or "unknown"
            exe_paths = _resolve_exe_path(app)
            for ep in exe_paths[:3]:
                icon = _extract_icon_safe(ep)
                if icon:
                    self.icon_ready.emit(name, icon)
                    break


class SoftwareManagerPage(QWidget):
    status_message = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._apps = []; self._icon_cache = {}; self._loaded_icons = {}
        self._setup_ui(); QTimer.singleShot(200, self._load)

    def _setup_ui(self):
        self.setStyleSheet("background:rgba(20,20,40,0.50);border-radius:10px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 10); layout.setSpacing(10)

        # ===== HEADER ROW =====
        hdr = QHBoxLayout()
        title = QLabel("  " + L["sm"])
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title.setStyleSheet("color:#e0e0e0;")
        hdr.addWidget(title)
        hdr.addStretch()

        self.rf_btn = QPushButton("  " + L["rf"] + "  ")
        self.rf_btn.clicked.connect(self._load); hdr.addWidget(self.rf_btn)
        layout.addLayout(hdr)

        # ===== FILTER ROW =====
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        lbl_drive = QLabel(L["d"] + ":")
        lbl_drive.setStyleSheet("color:#8b949e;font-size:12px;font-weight:bold;")
        filter_row.addWidget(lbl_drive)

        self.drive_filter = QComboBox()
        self.drive_filter.setMinimumWidth(80); self.drive_filter.setMaximumWidth(100)
        self.drive_filter.addItem(L["al"], "all")
        for d in get_drives(): self.drive_filter.addItem(d.replace("\\", ""), d[:2])
        self.drive_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.drive_filter)

        self.sys_filter = QComboBox()
        self.sys_filter.setMinimumWidth(80); self.sys_filter.setMaximumWidth(90)
        self.sys_filter.addItem("全部", "all")
        self.sys_filter.addItem("用户软件", "user")
        self.sys_filter.addItem("系统组件", "system")
        self.sys_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.sys_filter)

        self.orphan_filter = QCheckBox("仅显示残留")
        self.orphan_filter.setStyleSheet("color:#eab308;font-size:12px;")
        self.orphan_filter.stateChanged.connect(self._apply_filters)
        filter_row.addWidget(self.orphan_filter)

        filter_row.addSpacing(16)
        lbl_search = QLabel(L["sh"] + ":")
        lbl_search.setStyleSheet("color:#8b949e;font-size:12px;font-weight:bold;")
        filter_row.addWidget(lbl_search)

        self.search = QLineEdit()
        self.search.setPlaceholderText("输入名称或发布者...")
        self.search.setMaximumWidth(260)
        self.search.textChanged.connect(self._debounce_filter)
        filter_row.addWidget(self.search)

        filter_row.addStretch()

        self.sel_all_btn = QPushButton(L["select_all"])
        self.sel_all_btn.setMaximumWidth(80); self.sel_all_btn.clicked.connect(self._select_all)
        filter_row.addWidget(self.sel_all_btn)

        self.desel_btn = QPushButton(L["deselect"])
        self.desel_btn.setMaximumWidth(80); self.desel_btn.clicked.connect(self._deselect_all)
        filter_row.addWidget(self.desel_btn)
        layout.addLayout(filter_row)

        # ===== ACTION ROW =====
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.ub = QPushButton("  " + L["un"] + "  ")
        self.ub.setObjectName("redBtn"); self.ub.clicked.connect(self._uninstall)
        action_row.addWidget(self.ub)

        self.fub = QPushButton("  强制卸载  ")
        self.fub.setObjectName("redBtn"); self.fub.clicked.connect(self._force_uninstall)
        self.fub.setToolTip("深度扫描+强制删除所有相关文件和注册表")
        action_row.addWidget(self.fub)

        self.del_btn = QPushButton("  " + L["dl"] + "  ")
        self.del_btn.setObjectName("redBtn"); self.del_btn.clicked.connect(self._delete_residue)
        action_row.addWidget(self.del_btn)

        self.orphan_clean_btn = QPushButton("  清理残留注册表  ")
        self.orphan_clean_btn.setObjectName("yellowBtn")
        self.orphan_clean_btn.clicked.connect(self._clean_orphans)
        self.orphan_clean_btn.setToolTip("一键清理所有已失效的注册表项")
        action_row.addWidget(self.orphan_clean_btn)

        self.progress = QProgressBar()
        self.progress.setMaximum(0); self.progress.setVisible(False)
        self.progress.setMaximumHeight(14)
        action_row.addWidget(self.progress)
        action_row.addStretch()

        self.info_lbl = QLabel("")
        self.info_lbl.setStyleSheet("color:#58a6ff;font-size:12px;")
        action_row.addWidget(self.info_lbl)
        layout.addLayout(action_row)

        # ===== MAIN CONTENT: Tree + Detail Panel =====
        sp = QSplitter(Qt.Horizontal)

        # --- Left: Software tree ---
        self.tree = QTreeWidget()
        self.tree.setIconSize(QSize(28, 28))
        self.tree.setHeaderLabels(["", "", L["n"], L["v"], L["p"], L["d"], L["s"], L["t"]])
        self.tree.setColumnWidth(0, 44); self.tree.setColumnWidth(1, 36)
        self.tree.setColumnWidth(2, 220); self.tree.setColumnWidth(3, 70)
        self.tree.setColumnWidth(4, 140); self.tree.setColumnWidth(5, 50)
        self.tree.setColumnWidth(6, 75); self.tree.setColumnWidth(7, 60)
        self.tree.setAlternatingRowColors(True)
        self.tree.setStyleSheet("QTreeWidget{background:transparent;alternate-background-color:transparent;}")
        self.tree.setRootIsDecorated(False)
        self.tree.itemClicked.connect(self._on_click)
        self.tree.itemChanged.connect(lambda *a: self._update_sel_count())
        sp.addWidget(self.tree)

        # --- Right: Detail panel ---
        right_panel = QFrame()
        right_panel.setStyleSheet(
            "QFrame{background:transparent;border:1px solid #30363d;border-radius:8px;}"
            "QLabel{background:transparent;}"
        )
        rl = QVBoxLayout(right_panel)
        rl.setContentsMargins(16, 16, 16, 16); rl.setSpacing(10)

        # App icon + name header
        hdr_row = QHBoxLayout()
        self.detail_icon = QLabel()
        self.detail_icon.setFixedSize(52, 52)
        self.detail_icon.setAlignment(Qt.AlignCenter)
        self.detail_icon.setStyleSheet("border:1px solid #30363d;border-radius:8px;background:transparent;")
        hdr_row.addWidget(self.detail_icon)
        hdr_row.addSpacing(12)

        name_col = QVBoxLayout()
        self.detail_name = QLabel(L["sel_hint"])
        self.detail_name.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        self.detail_name.setStyleSheet("color:#e6edf3;background:transparent;")
        name_col.addWidget(self.detail_name)

        self.detail_badge = QLabel("")
        self.detail_badge.setStyleSheet("color:#8b949e;font-size:11px;background:transparent;")
        name_col.addWidget(self.detail_badge)
        hdr_row.addLayout(name_col)
        hdr_row.addStretch()
        rl.addLayout(hdr_row)

        # Separator
        sep1 = QFrame(); sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("background:rgba(255,255,255,0.08);max-height:1px;border:none;")
        rl.addWidget(sep1)

        # Info rows (simple key-value pairs)
        info_keys = [L["v"], L["p"], L["lc"], L["s"], L["dt"], L["rg"]]
        self.detail_values = {}
        for key in info_keys:
            row = QHBoxLayout()
            row.setSpacing(8)
            kl = QLabel(key + ":")
            kl.setStyleSheet("color:#8b949e;font-size:11px;font-weight:bold;min-width:55px;background:transparent;")
            row.addWidget(kl)
            vl = QLabel("-")
            vl.setStyleSheet("color:#c9d1d9;font-size:11px;background:transparent;")
            vl.setWordWrap(True)
            row.addWidget(vl, 1)
            rl.addLayout(row)
            self.detail_values[key] = vl

        # Separator
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("background:rgba(255,255,255,0.08);max-height:1px;border:none;")
        rl.addWidget(sep2)

        # Description
        desc_title = QLabel(L["ds"] + ":")
        desc_title.setStyleSheet("color:#8b949e;font-size:11px;font-weight:bold;background:transparent;")
        rl.addWidget(desc_title)

        self.detail_desc = QLabel(L["nd"])
        self.detail_desc.setStyleSheet(
            "color:#c9d1d9;font-size:11px;padding:8px;"
            "background:transparent;border:1px solid #21262d;border-radius:4px;"
        )
        self.detail_desc.setWordWrap(True)
        self.detail_desc.setMinimumHeight(36)
        rl.addWidget(self.detail_desc)

        rl.addStretch()

        # Log section
        log_label = QLabel(L["log"] + ":")
        log_label.setStyleSheet("color:#8b949e;font-size:11px;font-weight:bold;background:transparent;")
        rl.addWidget(log_label)

        self.log = QTextEdit()
        self.log.setReadOnly(True); self.log.setMaximumHeight(100)
        self.log.setPlaceholderText(L["log_hint"])
        self.log.setStyleSheet("font-size:11px;background:transparent;border:1px solid #30363d;color:#c9d1d9;")
        rl.addWidget(self.log)

        sp.addWidget(right_panel)
        sp.setSizes([580, 440])
        layout.addWidget(sp)

    def _default_icon(self):
        pix = QPixmap(32, 32); pix.fill(Qt.transparent)
        from PySide6.QtGui import QPainter
        p = QPainter(pix); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#30363d")); p.setPen(Qt.NoPen)
        p.drawRoundedRect(2, 2, 28, 28, 6, 6)
        p.setPen(QColor("#8b949e"))
        p.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        p.drawText(pix.rect(), Qt.AlignCenter, "?")
        p.end(); return QIcon(pix)

    def _load(self):
        self.tree.clear(); self.progress.setVisible(True)
        self.status_message.emit(L["sg"] + "...")
        self._thread = SoftwareScannerThread()
        self._thread.result.connect(self._on_loaded); self._thread.start()

    def _on_loaded(self, apps):
        self._apps = apps; self._loaded_icons = {}; self._tree_built = False
        self.progress.setVisible(False)
        drives = set()
        for app in apps:
            d = _get_drive(app.install_location)
            if d: drives.add(d)
        current = self.drive_filter.currentData()
        self.drive_filter.blockSignals(True)
        self.drive_filter.clear()
        self.drive_filter.addItem(L["al"], "all")
        for d in sorted(drives): self.drive_filter.addItem(d, d)
        idx = self.drive_filter.findData(current)
        self.drive_filter.setCurrentIndex(max(idx, 0))
        self.drive_filter.blockSignals(False)
        self.search.clear()
        self._apply_filters()
        self._icon_thread = IconLoaderThread(apps)
        self._icon_thread.icon_ready.connect(self._on_icon_loaded)
        self._icon_thread.start()

    def _on_icon_loaded(self, name, icon):
        self._loaded_icons[name] = icon
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            app = item.data(2, Qt.UserRole)
            if app and (app.name or "unknown") == name:
                item.setIcon(1, icon)


    def _debounce_filter(self):
        if hasattr(self, "_filter_timer"):
            self._filter_timer.stop()
        else:
            self._filter_timer = QTimer()
            self._filter_timer.setSingleShot(True)
            self._filter_timer.timeout.connect(self._apply_filters)
        self._filter_timer.start(200)

    def _apply_filters(self):
        tx = self.search.text().lower()
        drv = self.drive_filter.currentData()
        sys_filt = self.sys_filter.currentData() if hasattr(self, "sys_filter") else "all"
        show_orphan_only = self.orphan_filter.isChecked() if hasattr(self, "orphan_filter") else False
        self.tree.clear()
        default = self._default_icon()
        # Sort by size descending (large first)
        sorted_apps = sorted(self._apps, key=lambda a: a.estimated_size or 0, reverse=True)
        for app in sorted_apps:
            if show_orphan_only and not app.is_orphan:
                continue
            if sys_filt == "user" and app.is_system:
                continue
            if sys_filt == "system" and not app.is_system:
                continue
            if tx:
                if not (tx in (app.name or "").lower() or
                        tx in (app.publisher or "").lower() or
                        tx in (app.version or "").lower()):
                    continue
            app_drive = _get_drive(app.install_location)
            if drv != "all" and app_drive != drv: continue

            item = QTreeWidgetItem()
            item.setCheckState(0, Qt.Unchecked)

            # Icon loading strategy
            ico = default
            icon_path = ""
            if app.display_icon:
                icon_path = app.display_icon.strip(chr(34)).strip("'")
                if "," in icon_path:
                    icon_path = icon_path.split(",")[0].strip()

            target_path = None
            if icon_path and _os.path.exists(icon_path):
                target_path = icon_path
            elif app.install_location:
                loc = app.install_location.strip(chr(34)).strip("'")
                if loc and _os.path.exists(loc):
                    target_path = loc

            # Try real icon via QFileIconProvider
            if target_path and target_path not in self._icon_cache:
                try:
                    provider = QFileIconProvider()
                    loaded = provider.icon(QFileInfo(target_path))
                    if loaded and not loaded.isNull():
                        self._icon_cache[target_path] = loaded
                except: pass
            if target_path and target_path in self._icon_cache:
                ico = self._icon_cache[target_path]

            # Fallback: category-based icon
            if ico is default:
                cat, label, color = _get_software_category(app)
                cat_icon = _get_category_icon(cat, label, color)
                ico = self._loaded_icons.get(app.name, cat_icon)
                item.setData(2, Qt.UserRole + 1, (cat, CATEGORY_LABELS.get(cat, "")))
            else:
                cat, label, color = _get_software_category(app)
                item.setData(2, Qt.UserRole + 1, (cat, CATEGORY_LABELS.get(cat, "")))

            item.setIcon(1, ico)
            item.setText(2, app.name or "Unknown")
            item.setText(3, app.version or "-")
            item.setText(4, app.publisher or "-")
            item.setText(5, app_drive or "-")
            item.setText(6, format_size(app.estimated_size) if app.estimated_size else "-")

            if app.is_system:
                item.setText(7, L["sy"])
                item.setForeground(2, QColor("#F44336"))
                item.setForeground(7, QColor("#F44336"))
                item.setToolTip(2, L["sw"])
            else:
                item.setText(7, L["us"])
                item.setForeground(2, QColor("#4CAF50"))
                item.setForeground(7, QColor("#4CAF50"))

            item.setData(2, Qt.UserRole, app)
            self.tree.addTopLevelItem(item)

        self._update_sel_count()
        self.status_message.emit(L["fo"] + " " + str(len(self._apps)) + L["ya"])

    def _on_click(self, item, col):
        app = item.data(2, Qt.UserRole)
        if not app: return

        # Update detail panel
        self.detail_name.setText(app.name or "Unknown")

        # Detail icon - use tree icon scaled up
        icon = item.icon(1)
        if icon and not icon.isNull():
            self.detail_icon.setPixmap(icon.pixmap(48, 48))
        else:
            self.detail_icon.setText("")

        # Update badge with system status + category
        cat_data = item.data(2, Qt.UserRole + 1)
        cat_label = cat_data[1] if cat_data else ""
        if app.is_system:
            self.detail_badge.setStyleSheet("color:#F44336;font-size:11px;font-weight:bold;background:transparent;")
            self.detail_badge.setText(L["stg"] + (" | " + cat_label if cat_label else ""))
        else:
            self.detail_badge.setStyleSheet("color:#4CAF50;font-size:11px;font-weight:bold;background:transparent;")
            self.detail_badge.setText(L["utg"] + (" | " + cat_label if cat_label else ""))

        # Update info
        self.detail_values[L["v"]].setText(app.version or "-")
        self.detail_values[L["p"]].setText(app.publisher or "-")
        self.detail_values[L["lc"]].setText(app.install_location or "-")
        self.detail_values[L["s"]].setText(format_size(app.estimated_size or 0))
        self.detail_values[L["dt"]].setText(app.install_date or "-")
        self.detail_values[L["rg"]].setText(app.registry_key or "-")

        # Description
        desc = _get_description(app.name) or L["nd"]
        self.detail_desc.setText(desc)

    def _update_sel_count(self):
        total = self.tree.topLevelItemCount()
        sel = sum(1 for i in range(total) if self.tree.topLevelItem(i).checkState(0) == Qt.Checked)
        text = L["disp"] + " " + str(total) + " / " + str(len(self._apps)) + L["ge"]
        if sel > 0:
            text += "  |  " + L["selected_count"] + ": " + str(sel) + " 个"
        self.info_lbl.setText(text)

    def _select_all(self):
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if not it.isHidden():
                app = it.data(2, Qt.UserRole)
                if app and not app.is_system:
                    it.setCheckState(0, Qt.Checked)
        self._update_sel_count()

    def _deselect_all(self):
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(0, Qt.Unchecked)
        self._update_sel_count()

    def _uninstall(self):
        sel = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.checkState(0) == Qt.Checked:
                a = it.data(2, Qt.UserRole)
                if a and not a.is_system: sel.append(a)
                elif a:
                    r = QMessageBox.question(self, L["wn"], a.name + " " + L["isc"], QMessageBox.Yes|QMessageBox.No)
                    if r == QMessageBox.Yes: sel.append(a)
        if not sel:
            QMessageBox.information(self, L["tp"], L["sf"]); return
        names = chr(10).join(a.name for a in sel[:8])
        if len(sel) > 8: names += chr(10) + "... " + str(len(sel)-8) + " more"
        r = QMessageBox.question(self, L["cf"] + " " + L["un"], L["cu"] + chr(10) + chr(10) + names, QMessageBox.Yes|QMessageBox.No)
        if r != QMessageBox.Yes: return
        self.log.clear(); self._queue = sel; self._idx = 0; self._success = []; self._failed = []; self._do_next()

    def _do_next(self):
        if self._idx >= len(self._queue):
            self.log.append("--- " + L["dc"] + "... ---")
            self._check_residues(); return
        app = self._queue[self._idx]
        self.log.append(L["ui"] + ": " + app.name)
        self.status_message.emit(L["un"] + ": " + app.name)
        ex = UninstallExecutor(); ex.output.connect(lambda s: self.log.append("  " + s))
        ex.finished.connect(self._on_done); ex.uninstall(app)

    def _on_done(self, ok, msg):
        app = self._queue[self._idx]
        status = "OK" if ok else "失败"
        self.log.append("  => " + status + ": " + msg)
        if ok:
            self._success.append(app)
        else:
            self._failed.append(app)
        self._idx += 1; self._do_next()

    def _delete_residue(self):
        sel = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.checkState(0) == Qt.Checked:
                a = it.data(2, Qt.UserRole)
                if a and not a.is_system: sel.append(a)
        if not sel:
            QMessageBox.information(self, L["tp"], L["sf"]); return
        names = chr(10).join(a.name + ": " + (a.install_location or "N/A") for a in sel[:5])
        r = QMessageBox.warning(self, L["dct"], L["dcw"] + chr(10) + chr(10) + names + chr(10) + chr(10) + L["dcn"], QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes: return
        import shutil; cleaned = 0
        for app in sel:
            if app.install_location:
                loc = app.install_location.strip(chr(34))
                if _os.path.exists(loc):
                    try:
                        if _os.path.isdir(loc): shutil.rmtree(loc, ignore_errors=True)
                        else: _os.remove(loc)
                        self.log.append(L["dld"] + ": " + loc); cleaned += 1
                    except Exception as e: self.log.append(L["fld"] + ": " + str(e))
        self.log.append(L["clc"] + " " + str(cleaned) + " " + L["ge"])
        self.status_message.emit(L["dld"] + " " + str(cleaned) + " " + L["ge"])
        self._load()

    def _force_uninstall(self):
        sel = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.checkState(0) == Qt.Checked:
                a = it.data(2, Qt.UserRole)
                if a and not a.is_system: sel.append(a)
                elif a:
                    r = QMessageBox.question(self, "警告", a.name + " 是系统软件，确定强制卸载？", QMessageBox.Yes|QMessageBox.No)
                    if r == QMessageBox.Yes: sel.append(a)
        if not sel:
            QMessageBox.information(self, "提示", "请先选择要卸载的软件"); return
        names = chr(10).join(a.name for a in sel[:8])
        if len(sel) > 8: names += chr(10) + "... 还有 " + str(len(sel)-8) + " 个"
        r = QMessageBox.warning(self, "确认强制卸载",
            "强制卸载将深度扫描并删除以下软件的所有文件和注册表:\n\n" + names +
            "\n\n此操作不可撤销，确定继续？",
            QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes: return
        self.log.clear(); self._queue = sel; self._idx = 0; self._success = []; self._failed = []
        self._do_force_next()

    def _do_force_next(self):
        if self._idx >= len(self._queue):
            self.log.append("--- 全部完成 ---")
            failed_names = [a.name for a in self._failed]
            if failed_names:
                self.log.append("以下软件强制卸载失败: " + ", ".join(failed_names))
            self.status_message.emit("强制卸载完成")
            self._load()
            return
        app = self._queue[self._idx]
        self.log.append("强制卸载: " + app.name)
        self.status_message.emit("强制卸载: " + app.name)
        ex = UninstallExecutor()
        ex.output.connect(lambda s: self.log.append("  " + s))
        ex.finished.connect(self._on_force_done)
        ex.force_uninstall(app)

    def _on_force_done(self, ok, msg):
        app = self._queue[self._idx]
        status = "成功" if ok else "失败"
        self.log.append("  => " + status + ": " + msg)
        if ok:
            self._success.append(app)
        else:
            self._failed.append(app)
        self._idx += 1
        self._do_force_next()

    def _clean_orphans(self):
        """One-click cleanup of all orphaned registry entries."""
        # Only clean confirmed orphans (level 2) by default
        confirmed = [a for a in self._apps if a.is_orphan and a.orphan_level == 2]
        suspected = [a for a in self._apps if a.is_orphan and a.orphan_level == 1]
        orphans = confirmed  # default: only confirmed
        include_suspected = False
        if suspected:
            r2 = QMessageBox.question(self, "发现可疑项",
                "确认失效: " + str(len(confirmed)) + " 条（可安全清除）\n" +
                "可疑残留: " + str(len(suspected)) + " 条（可能为组件/插件）\n\n" +
                "是否同时清理可疑项？不建议清理系统组件。",
                QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
            if r2 == QMessageBox.Yes:
                orphans = confirmed + suspected
                include_suspected = True
        if not orphans:
            QMessageBox.information(self, "提示", "没有发现残留注册表项"); return
        names = chr(10).join(a.name + " - " + (a.orphan_reason or "未知") for a in orphans[:15])
        if len(orphans) > 15: names += chr(10) + "... 还有 " + str(len(orphans)-15) + " 项"
        r = QMessageBox.warning(self, "清理残留注册表",
            "发现 " + str(len(orphans)) + " 条失效注册表:\n\n" + names +
            "\n\n这些软件的安装目录或卸载程序已不存在，仅注册表残留。确定清理？",
            QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes: return
        import winreg
        self.log.clear()
        self.log.append("=== 开始清理残留注册表 ===")
        cleaned = 0; failed = 0; perm_denied = 0
        for app in orphans:
            try:
                hive = winreg.HKEY_LOCAL_MACHINE if app.hive == "HKLM" else winreg.HKEY_CURRENT_USER
                from core.uninstaller import _delete_registry_tree
                ok, err = _delete_registry_tree(hive, app.registry_key)
                if ok:
                    self.log.append("✓ " + app.name)
                    cleaned += 1
                else:
                    if "权限不足" in str(err) or "Permission" in str(err):
                        perm_denied += 1
                    self.log.append("✗ " + app.name + " - " + str(err))
                    failed += 1
            except Exception as e:
                self.log.append("✗ " + app.name + " - " + str(e))
                failed += 1
        self.log.append("=== 完成: " + str(cleaned) + " 项, 失败: " + str(failed) + " 项 ===")
        lvl_info = " (确认失效)" if not include_suspected else " (含可疑项)"
        msg = "清理完成: " + str(cleaned) + " 项" + lvl_info
        if failed > 0:
            msg += ", 失败: " + str(failed) + " 项"
        if perm_denied > 0:
            msg += "\n\n" + str(perm_denied) + " 项因权限不足无法删除(HKLM)，请以管理员身份运行后再试"
        QMessageBox.information(self, "完成", msg)
        self.status_message.emit("已清理 " + str(cleaned) + " 条残留注册表")
        self._load()
    def _check_residues(self):
        import winreg, shutil
        residues = []
        if not self._success:
            if self._failed:
                self.log.append("所有卸载均失败，跳过残留检测")
            self.log.append("--- " + L["cd"] + " ---")
            self.status_message.emit(L["cd"])
            self._load()
            return
        if self._failed:
            self.log.append("以下卸载失败，已跳过残留检测: " + ", ".join(a.name for a in self._failed))
        for app in self._success:
            if app.install_location:
                loc = app.install_location.strip(chr(34))
                if _os.path.exists(loc): residues.append(("Files", loc, L["id"] + ": " + loc))
            for root_key, subpath in [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]:
                try:
                    key = winreg.OpenKey(root_key, subpath); i = 0
                    while True:
                        try:
                            skn = winreg.EnumKey(key, i); full = subpath + chr(92) + skn
                            sk = winreg.OpenKey(root_key, full)
                            try:
                                dn = winreg.QueryValueEx(sk, "DisplayName")[0]
                                if app.name.lower() in str(dn).lower():
                                    residues.append(("Registry", full, L["rk"] + ": " + dn))
                            except: pass
                            winreg.CloseKey(sk)
                        except OSError: break
                        i += 1
                    winreg.CloseKey(key)
                except: pass
        if not residues:
            self.log.append(L["nr"]); self.status_message.emit(L["cd"]); self._load(); return
        descs = chr(10).join(r[2] for r in residues[:10])
        if len(residues) > 10: descs += chr(10) + "... " + str(len(residues)-10) + " more"
        r = QMessageBox.question(self, L["fr"],
            L["fr"] + " " + str(len(residues)) + " " + L["fr"] + ":" + chr(10) + chr(10) + descs + chr(10) + chr(10) + L["cq"],
            QMessageBox.Yes|QMessageBox.No)
        if r == QMessageBox.Yes:
            cleaned2 = 0
            for typ, path, desc in residues:
                try:
                    if typ == "Files":
                        if _os.path.isdir(path): shutil.rmtree(path, ignore_errors=True)
                        elif _os.path.exists(path): _os.remove(path)
                    self.log.append("  " + L["cld"] + ": " + desc); cleaned2 += 1
                except Exception as e: self.log.append("  " + L["fld"] + ": " + str(e))
            self.log.append(L["clc"] + " " + str(cleaned2) + " " + L["fr"])
            self.status_message.emit(L["cld"] + " " + str(cleaned2) + " " + L["fr"])
        self._load()
